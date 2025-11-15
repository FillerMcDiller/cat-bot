# bot_with_webhook.py
import asyncio
from fastapi import FastAPI, Request
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

    # Schedule vote reward directly in bot's loop
    bot.loop.create_task(reward_vote(user_id))
    return {"status": "ok"}

async def reward_vote(user_id: int):
    print(f"Rewarding vote for user {user_id}...")
    await asyncio.sleep(1)  # Replace with real reward logic
    print(f"User {user_id} has been rewarded!")

# ------------------ Discord ------------------
@bot.event
async def on_ready():
    print(f"Bot ready! Logged in as {bot.user}")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

# ------------------ Run everything ------------------
def start_webhook():
    uvicorn.run(app, host="0.0.0.0", port=WEBHOOK_PORT)

if __name__ == "__main__":
    # Run webhook in a separate thread
    import threading
    threading.Thread(target=start_webhook, daemon=True).start()
    print("Webhook server running...")

    # Run the bot in the main thread
    asyncio.run(bot.start(BOT_TOKEN))

