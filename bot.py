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
    print("\n" + "="*60)
    print("[BOT.PY] SETUP_HOOK STARTING!")
    print("="*60 + "\n")
    
    try:
        # Connect to database FIRST
        print("[BOT.PY] Connecting to database...")
        await database.connect()
        print("[BOT.PY] OK Database connected!")
        
        # Load the main extension
        print("[BOT.PY] Loading main.py extension...")
        try:
            await bot.load_extension('main')
            print("[BOT.PY] OK main.py loaded successfully!")
        except Exception as ext_err:
            print(f"[BOT.PY] FAILED to load main.py: {ext_err}")
            import traceback
            traceback.print_exc()
            raise
        
        # Import the vote receiver function
        print("[BOT.PY] Importing start_internal_server...")
        try:
            from main import start_internal_server
            print("[BOT.PY] OK Import successful!")
            
            # Start the internal vote receiver
            print("[BOT.PY] Starting internal vote receiver on port 3002...")
            bot.loop.create_task(start_internal_server(3002))  # Pass port explicitly
            print("[BOT.PY] OK Vote receiver task created!")
        except ImportError as ie:
            print(f"[BOT.PY] WARNING Could not import start_internal_server: {ie}")
            print("[BOT.PY] Vote system will not be available!")
        
    except Exception as e:
        print(f"\n[BOT.PY] ERROR in setup_hook: {e}")
        import traceback
        traceback.print_exc()
        print()
        raise  # Re-raise to prevent silent failure
    
    print("\n" + "="*60)
    print("[BOT.PY] SETUP_HOOK COMPLETE!")
    print("="*60 + "\n")

bot.setup_hook = setup_hook
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
    # legacy: no-op; we now start the webhook in-process via setup_hook
    return None

try:
    config.HARD_RESTART_TIME = time.time()
    print("[BOT.PY] >>> Starting bot.run()...")
    print(f"[BOT.PY] Token length: {len(config.TOKEN) if config.TOKEN else 0} chars")
    print(f"[BOT.PY] Token starts with: {config.TOKEN[:20] if config.TOKEN else 'NONE'}...")
    if not config.TOKEN:
        raise RuntimeError("TOKEN is empty or not set!")
    bot.run(config.TOKEN)
except KeyboardInterrupt:
    print("[BOT.PY] STOPPED: Bot interrupted by user")
except Exception as e:
    print(f"[BOT.PY] ERROR during bot.run(): {e}")
    import traceback
    traceback.print_exc()
    raise
finally:
    print("[BOT.PY] Closing database connection...")
    asyncio.run(database.close())
    print("[BOT.PY] Bot shutdown complete")
