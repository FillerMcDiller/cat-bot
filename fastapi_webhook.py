import threading
import asyncio
import logging
from fastapi import FastAPI, Request
import uvicorn


def start_inproc_webhook(loop: asyncio.AbstractEventLoop, reward_coro, port: int = 3001, auth: str | None = None):
    app = FastAPI()

    @app.post("/dblwebhook")
    async def handle_vote(req: Request):
        if auth and req.headers.get("Authorization") != auth:
            return {"error": "unauthorized"}, 401
        try:
            data = await req.json()
            user_id = int(data.get("user") or data.get("user_id"))
        except Exception:
            return {"error": "invalid payload"}, 400

        try:
            # print and schedule reward on bot loop
            try:
                print(f"vote received from {user_id}, granting rewards..", flush=True)
            except Exception:
                logging.info("vote received from %s, granting rewards..", user_id)

            # schedule reward_coro on the provided loop
            asyncio.run_coroutine_threadsafe(reward_coro(user_id), loop)
        except Exception:
            logging.exception("Failed to handle incoming vote for %s", user_id)
            return {"status": "error"}, 500

        return {"status": "ok"}

    def _run():
        try:
            try:
                print(f"[webhook] starting uvicorn on 0.0.0.0:{port}", flush=True)
            except Exception:
                logging.info("[webhook] starting uvicorn on %s:%s", "0.0.0.0", port)

            config = uvicorn.Config(app=app, host="0.0.0.0", port=port, log_level="info")
            server = uvicorn.Server(config=config)

            # server.run() will block this thread until shutdown
            server.run()

            try:
                print("[webhook] uvicorn exited", flush=True)
            except Exception:
                logging.info("[webhook] uvicorn exited")
        except Exception:
            logging.exception("Webhook uvicorn exited unexpectedly")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t
