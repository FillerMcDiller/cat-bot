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

import discord
import winuvloop
from discord.ext import commands

import config
from config import TOKEN
import database
import catpg

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
    # webhook process will be started by the launcher before bot.run


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

def _start_webhook_process():
    # Launch webhook_server.py in a new console so you get two terminals when running `python bot.py`.
    import subprocess, sys, os

    python = sys.executable
    script = os.path.join(os.path.dirname(__file__), "webhook_server.py")
    env = os.environ.copy()
    env["WEBHOOK_PORT"] = str(getattr(config, "WEBHOOK_PORT", 3001) or 3001)
    if getattr(config, "WEBHOOK_VERIFY", None):
        env["WEBHOOK_VERIFY"] = str(getattr(config, "WEBHOOK_VERIFY"))
    env["BOT_INTERNAL_PORT"] = str(getattr(config, "INTERNAL_WEBHOOK_PORT", 3002) or 3002)

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_CONSOLE

    try:
        subprocess.Popen([python, script], env=env, creationflags=creationflags)
    except Exception:
        logging.exception("Failed to spawn webhook process")

try:
    config.HARD_RESTART_TIME = time.time()
    # Spawn webhook console window before running the bot so you have two terminals.
    _start_webhook_process()
    bot.run(config.TOKEN)
finally:
    asyncio.run(database.close())
