# Cat Bot - A Discord bot about catching cats.
# Copyright (C) 2025 Lia Milenakos & Cat Bot Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import asyncio
import importlib
import time
import logging
import os

import discord
import winuvloop
from discord.ext import commands

import config
from config import TOKEN
import database
import catpg

from webhook import start_webhook_thread  # <- your webhook integration

winuvloop.install()

bot = commands.AutoShardedBot(
    command_prefix="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    help_command=None,
    chunk_guilds_at_startup=False,
    allowed_contexts=discord.app_commands.AppCommandContext(guild=True, dm_channel=False, private_channel=False),
    intents=discord.Intents(message_content=True, messages=True, guilds=True),
    member_cache_flags=discord.MemberCacheFlags.none(),
    allowed_mentions=discord.AllowedMentions.none(),
)


@bot.event
async def setup_hook():
    await database.connect()
    await bot.load_extension("main")

async def reload(reload_db):
    try:
        await bot.unload_extension("main")
    except commands.ExtensionNotLoaded:
        pass
    if reload_db:
        await database.close()
        importlib.reload(database)
        importlib.reload(catpg)
        await database.connect()
    await bot.load_extension("main")

bot.cat_bot_reload_hook = reload  # pyright: ignore


async def main():
    loop = asyncio.get_event_loop()

    # Start the webhook on port 3001
    webhook_auth = getattr(config, "WEBHOOK_VERIFY", "passtest")
    start_webhook_thread(loop, reward_coro=reward_vote, port=3001, auth=webhook_auth)

    # Run the Discord bot
    await bot.start(TOKEN)

async def reward_vote(user_id: int):
    """
    This coroutine is called whenever a vote is received.
    """
    try:
        logging.info("Vote received from user %s!", user_id)
        # Put your vote reward logic here
        await asyncio.sleep(0.1)  # placeholder for async DB or other operations
    except Exception:
        logging.exception("Error rewarding vote for user %s", user_id)

if __name__ == "__main__":
    config.HARD_RESTART_TIME = time.time()
    try:
        asyncio.run(main())
    finally:
        asyncio.run(database.close())
