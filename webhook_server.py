import threading
import time
import logging
import uvicorn
import asyncio
from fastapi import FastAPI, Request
import os
import aiohttp


def _make_app(reward_coro=None, loop: asyncio.AbstractEventLoop | None = None, auth: str | None = None, internal_port: int | None = None):
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

        # If we were given a reward coroutine and loop, schedule it directly.
        if reward_coro and loop:
            try:
                asyncio.run_coroutine_threadsafe(reward_coro(user_id), loop)
            except Exception:
                try:
                    logging.exception("Failed to schedule reward coroutine for vote")
                except Exception:
                    pass
            return {"status": "ok"}

        # Otherwise forward to bot's internal HTTP endpoint if configured
        target_port = internal_port or int(os.getenv("BOT_INTERNAL_PORT", "3002"))
        if target_port:
            try:
                async with aiohttp.ClientSession() as session:
                    await session.post(f"http://127.0.0.1:{target_port}/_internal_vote", json={"user": user_id}, timeout=5)
            except Exception:
                try:
                    logging.exception("Failed to forward vote to bot internal endpoint")
                except Exception:
                    pass

        logging.info("Vote received for user %s forwarded to bot", user_id)
        return {"status": "ok"}

    return app


def start_webhook_thread(loop: asyncio.AbstractEventLoop, reward_coro, port: int = 3001, auth: str | None = None):
    """Start a FastAPI webhook server in a background thread.

    The webhook will schedule `reward_coro(user_id)` on `loop` when votes arrive.
    """
    app = _make_app(reward_coro=reward_coro, loop=loop, auth=auth)

    def _run_uvicorn():
        while True:
            try:
                uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
                time.sleep(5)
            except Exception:
                try:
                    logging.exception("FastAPI webhook crashed; restarting in 5s")
                except Exception:
                    pass
                time.sleep(5)

    t = threading.Thread(target=_run_uvicorn, daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    # allow running standalone for manual testing: uses config via env if present
    import os

    port = int(os.getenv("WEBHOOK_PORT", "3001"))
    auth = os.getenv("WEBHOOK_VERIFY")
    app = _make_app(reward_coro=None, loop=None, auth=auth)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
