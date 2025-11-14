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
