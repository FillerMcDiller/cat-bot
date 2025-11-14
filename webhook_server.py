import threading
import time
import logging
import uvicorn
import asyncio
from fastapi import FastAPI, Request


def start_webhook_thread(loop: asyncio.AbstractEventLoop, reward_coro, port: int = 3001, auth: str | None = None):
    """Start a FastAPI webhook server in a background thread.

    - `loop`: the asyncio event loop where `reward_coro` should be executed.
    - `reward_coro`: a coroutine function taking a single user_id: int.
    - `port`: TCP port to listen on.
    - `auth`: optional header value for `Authorization` to validate incoming requests.
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

        try:
            # schedule the reward coroutine on the provided loop
            asyncio.run_coroutine_threadsafe(reward_coro(user_id), loop)
        except Exception:
            try:
                logging.exception("Failed to schedule reward coroutine for vote")
            except Exception:
                pass

        return {"status": "ok"}

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
