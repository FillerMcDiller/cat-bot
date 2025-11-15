import os
import asyncio
import logging
from typing import Optional

import uvicorn
from fastapi import FastAPI, Request
import aiohttp


WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "3001"))
INTERNAL_PORT = int(os.getenv("INTERNAL_WEBHOOK_PORT", "3002"))
WEBHOOK_AUTH = os.getenv("WEBHOOK_VERIFY")

app = FastAPI()


@app.post("/dblwebhook")
async def handle_vote(req: Request):
    # optional auth check
    if WEBHOOK_AUTH:
        header = req.headers.get("Authorization")
        if header != WEBHOOK_AUTH:
            return {"error": "unauthorized"}

    try:
        data = await req.json()
        user_id = int(data.get("user") or data.get("user_id"))
    except Exception:
        return {"error": "invalid payload"}

    # forward to internal bot endpoint with retries
    target = f"http://127.0.0.1:{INTERNAL_PORT}/_internal_vote"
    last_exc: Optional[Exception] = None
    for attempt in range(5):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(target, json={"user": user_id}, timeout=5) as resp:
                    if resp.status == 200:
                        return {"status": "ok"}
                    else:
                        text = await resp.text()
                        logging.warning("Forwarded vote but got status %s: %s", resp.status, text)
        except Exception as e:
            last_exc = e
            logging.warning("Attempt %s: failed to forward vote to %s: %s", attempt + 1, target, e)
            await asyncio.sleep(0.5 * (attempt + 1))

    logging.exception("Failed to forward vote after retries", exc_info=last_exc)
    return {"status": "error"}


def run():
    print(f"Starting external webhook server on 0.0.0.0:{WEBHOOK_PORT}, forwarding to 127.0.0.1:{INTERNAL_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=WEBHOOK_PORT, log_level="info")


if __name__ == "__main__":
    run()
import threading
import time
import logging
import asyncio
from fastapi import FastAPI, Request

def _make_app(reward_coro=None, loop: asyncio.AbstractEventLoop | None = None, auth: str | None = None):
    """
    Create a FastAPI app that calls `reward_coro(user_id)` when a vote arrives.
    """
    app = FastAPI()

    @app.post("/dblwebhook")
    async def handle_vote(req: Request):
        if auth and req.headers.get("Authorization") != auth:
            return {"error": "unauthorized"}, 401

        try:
            data = await req.json()
            user_id = int(data.get("user"))
        except Exception:
            return {"error": "invalid payload"}, 400

        if reward_coro and loop:
            try:
                # schedule reward on bot's event loop
                asyncio.run_coroutine_threadsafe(reward_coro(user_id), loop)
                logging.info("Vote received from user %s!", user_id)
            except Exception:
                logging.exception("Failed to schedule reward coroutine for vote")

        return {"status": "ok"}

    return app


def start_webhook_thread(loop: asyncio.AbstractEventLoop, reward_coro, port: int = 3001, auth: str | None = None):
    """
    Start the FastAPI webhook server in a background thread.
    """
    app = _make_app(reward_coro=reward_coro, loop=loop, auth=auth)

    def _run_uvicorn():
        while True:
            try:
                import uvicorn
                uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
                time.sleep(5)
            except Exception:
                logging.exception("FastAPI webhook crashed; restarting in 5s")
                time.sleep(5)

    t = threading.Thread(target=_run_uvicorn, daemon=True)
    t.start()
    return t
