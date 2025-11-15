import os
import asyncio
import logging
import time
from typing import Optional

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
import aiohttp


WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "3001"))
INTERNAL_PORT = int(os.getenv("INTERNAL_WEBHOOK_PORT", "3002"))
WEBHOOK_AUTH = os.getenv("WEBHOOK_VERIFY")
MAX_FORWARD_ATTEMPTS = int(os.getenv("WEBHOOK_MAX_ATTEMPTS", "6"))
BASE_BACKOFF = float(os.getenv("WEBHOOK_BACKOFF_BASE", "0.5"))

app = FastAPI()

# Shared state / metrics
state = {
    "total_received": 0,
    "total_forwarded": 0,
    "last_forward_error": None,
    "last_forward_time": None,
}


@app.on_event("startup")
async def startup_event():
    # configure logging for the module and create a shared aiohttp session
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("webhook_server").addHandler(logging.NullHandler())
    app.state.aiohttp = aiohttp.ClientSession()
    logging.info("webhook_server starting (forwarding to 127.0.0.1:%s)", INTERNAL_PORT)


@app.on_event("shutdown")
async def shutdown_event():
    sess: aiohttp.ClientSession = getattr(app.state, "aiohttp", None)
    if sess:
        await sess.close()
    logging.info("webhook_server shutdown complete")


def _target_url() -> str:
    return f"http://127.0.0.1:{INTERNAL_PORT}/_internal_vote"


async def _forward_vote(session: aiohttp.ClientSession, user_id: int) -> bool:
    """Forward to the internal bot endpoint using exponential backoff. Returns True on success."""
    target = _target_url()
    attempt = 0
    last_exc: Optional[Exception] = None
    while attempt < MAX_FORWARD_ATTEMPTS:
        attempt += 1
        try:
            timeout = aiohttp.ClientTimeout(total=8)
            async with session.post(target, json={"user": user_id}, timeout=timeout) as resp:
                text = await resp.text()
                if resp.status == 200:
                    logging.info("Forwarded vote for %s (attempt %s)", user_id, attempt)
                    state["total_forwarded"] += 1
                    state["last_forward_time"] = int(time.time())
                    state["last_forward_error"] = None
                    return True
                else:
                    state["last_forward_error"] = f"status {resp.status}: {text}"
                    logging.warning("Forward attempt %s returned status %s: %s", attempt, resp.status, text)
        except Exception as e:
            last_exc = e
            state["last_forward_error"] = str(e)
            logging.warning("Forward attempt %s failed: %s", attempt, e)

        # exponential backoff (jittered)
        backoff = BASE_BACKOFF * (2 ** (attempt - 1))
        await asyncio.sleep(backoff + (0.1 * attempt))

    logging.exception("Failed to forward vote for %s after %s attempts", user_id, MAX_FORWARD_ATTEMPTS, exc_info=last_exc)
    return False


@app.post("/dblwebhook")
async def handle_vote(req: Request):
    # optional auth check
    if WEBHOOK_AUTH:
        header = req.headers.get("Authorization")
        if header != WEBHOOK_AUTH:
            return JSONResponse({"error": "unauthorized"}, status_code=401)

    try:
        data = await req.json()
        user_field = data.get("user") or data.get("user_id")
        user_id = int(user_field)
    except Exception:
        return JSONResponse({"error": "invalid payload, expected JSON with 'user' field"}, status_code=400)

    state["total_received"] += 1

    # schedule forwarding but also attempt immediately (so cloudflare/Top.gg sees a quick OK)
    sess: aiohttp.ClientSession = getattr(app.state, "aiohttp")
    success = await _forward_vote(sess, user_id)
    if success:
        return JSONResponse({"status": "ok"})
    else:
        return JSONResponse({"status": "error", "detail": state.get("last_forward_error")}, status_code=502)


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok"})


@app.get("/")
async def index():
    html = f"""
    <html>
      <head><title>Cat-bot Webhook Forwarder</title></head>
      <body>
        <h2>Webhook forwarder</h2>
        <p>This service accepts Top.gg webhooks at <code>POST /dblwebhook</code> and forwards them to the bot at <code>{_target_url()}</code>.</p>
        <h3>Usage</h3>
        <pre>
curl -X POST http://HOST:{WEBHOOK_PORT}/dblwebhook -H 'Content-Type: application/json' -d '{{"user": 1234567890}}'
        </pre>
        <h3>Configuration</h3>
        <ul>
          <li>WEBHOOK_PORT: {WEBHOOK_PORT}</li>
          <li>INTERNAL_WEBHOOK_PORT: {INTERNAL_PORT}</li>
          <li>WEBHOOK_VERIFY: {'SET' if bool(WEBHOOK_AUTH) else 'not set'}</li>
        </ul>
        <h3>Metrics</h3>
        <ul>
          <li>Total received: {state['total_received']}</li>
          <li>Total forwarded: {state['total_forwarded']}</li>
          <li>Last forward error: {state['last_forward_error']}</li>
          <li>Last forward time: {state['last_forward_time']}</li>
        </ul>
      </body>
    </html>
    """
    return HTMLResponse(html)


def run():
    print(f"Starting external webhook server on 0.0.0.0:{WEBHOOK_PORT}, forwarding to 127.0.0.1:{INTERNAL_PORT}")
    uvicorn.run("webhook_server:app", host="0.0.0.0", port=WEBHOOK_PORT, log_level="info", reload=False)


if __name__ == "__main__":
    run()
