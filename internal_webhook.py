import asyncio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()
WEBHOOK_PORT = 3002
WEBHOOK_AUTH = "passtest"
BOT_TOKEN = os.getenv("TOKEN")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ------------------ Webhook ------------------
@app.post("/dblwebhook")
async def handle_vote(req: Request):
    if req.headers.get("Authorization") != WEBHOOK_AUTH:
        return {"error": "unauthorized"}, 401

    data = await req.json()
    user_id = int(data.get("user"))
    print(f"Vote received from user {user_id}!")

    # Schedule vote reward on the same loop
    asyncio.create_task(reward_vote(user_id))
    return {"status": "ok"}

async def reward_vote(user_id: int):
    print(f"Rewarding vote for user {user_id}...")
    await asyncio.sleep(1)
    print(f"User {user_id} has been rewarded!")

# ------------------ Discord ------------------
@bot.event
async def on_ready():
    print(f"Bot ready! Logged in as {bot.user}")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

# ------------------ Run everything ------------------
async def main():
    # Start FastAPI in background on same loop
    config = uvicorn.Config(app, host="0.0.0.0", port=WEBHOOK_PORT, log_level="info")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    # Start Discord bot
    await bot.start(BOT_TOKEN)

    # Wait for server to finish (never, unless stopped)
    await server_task

if __name__ == "__main__":
    asyncio.run(main())
