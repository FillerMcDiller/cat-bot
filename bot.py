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
import os
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

intents = discord.Intents(messages=True, guilds=True)
intents.message_content = True

bot = commands.AutoShardedBot(
    command_prefix="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    help_command=None,
    chunk_guilds_at_startup=False,
    allowed_contexts=discord.app_commands.AppCommandContext(guild=True, dm_channel=False, private_channel=False),
    intents=intents,
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
        # Try to load the cat competition extension (optional)
        try:
            await bot.load_extension('cat_competition')
            print("[BOT.PY] OK cat_competition loaded successfully!")
        except Exception as ext_err:
            print(f"[BOT.PY] WARNING failed to load cat_competition extension: {ext_err}")

        # Sync again after all extensions are loaded so late-added commands appear.
        try:
            synced_commands = await bot.tree.sync()
            print(f"[BOT.PY] OK synced {len(synced_commands)} application commands after loading extensions!")
        except Exception as sync_err:
            print(f"[BOT.PY] WARNING failed to sync application commands after loading extensions: {sync_err}")
        
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
        
        # Update top.gg stats
        try:
            from main import update_topgg_stats
            from config import TOP_GG_TOKEN, MIN_SERVER_SEND
            
            if TOP_GG_TOKEN:
                server_count = len(bot.guilds)
                if server_count >= MIN_SERVER_SEND:
                    print(f"[BOT.PY] Updating top.gg stats ({server_count} servers)...")
                    success = await update_topgg_stats(TOP_GG_TOKEN, server_count)
                    if success:
                        print("[BOT.PY] OK top.gg stats updated!")
                    else:
                        print("[BOT.PY] WARNING Failed to update top.gg stats")
                else:
                    print(f"[BOT.PY] Skipping top.gg update (only {server_count} servers, need {MIN_SERVER_SEND}+)")
            else:
                print("[BOT.PY] TOP_GG_TOKEN not configured, skipping stats update")
        except Exception as e:
            print(f"[BOT.PY] WARNING Could not update top.gg stats: {e}")

        global SOURCE_WATCHER_TASK
        if SOURCE_WATCHER_TASK is None or SOURCE_WATCHER_TASK.done():
            SOURCE_WATCHER_TASK = bot.loop.create_task(_watch_source_changes())
            print("[BOT.PY] Source watcher task started.")

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

MAIN_FILE = os.path.join(os.path.dirname(__file__), "main.py")
CATPG_FILE = os.path.join(os.path.dirname(__file__), "catpg.py")
DATABASE_FILE = os.path.join(os.path.dirname(__file__), "database.py")
SOURCE_WATCHER_TASK = None


def _get_reload_signature() -> tuple[float, float, float]:
    def _mtime(path: str) -> float:
        try:
            return os.path.getmtime(path)
        except OSError:
            return 0.0

    return (_mtime(MAIN_FILE), _mtime(CATPG_FILE), _mtime(DATABASE_FILE))


async def _watch_source_changes(poll_seconds: float = 2.0):
    last_signature = _get_reload_signature()
    while True:
        await asyncio.sleep(poll_seconds)
        current_signature = _get_reload_signature()
        if current_signature == last_signature:
            continue

        last_signature = current_signature
        try:
            print("[BOT.PY] Source change detected, reloading main extension...", flush=True)
            await bot.cat_bot_reload_hook(True)  # pyright: ignore
            print("[BOT.PY] Reload complete.", flush=True)
        except Exception as e:
            print(f"[BOT.PY] Auto-reload failed: {e}", flush=True)


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
