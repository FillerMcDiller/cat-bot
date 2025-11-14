# KITTAYYYYYYY - A Discord bot about catching cats.
# Copyright (C) 2025 Lia Milenakos & KITTAYYYYYYY Contributors
# -*- coding: utf-8 -*-
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
import base64
import datetime
import io
import json
import logging
import math
import os
import platform
import random
import re
import subprocess
import sys
import time
import traceback
import uuid
from typing import Literal, Optional, Union

import aiohttp
import discord
import discord_emoji
import emoji
import psutil
from aiohttp import web
from discord import ButtonStyle
from discord.ext import commands
from discord.ui import Button, View
from PIL import Image

import topgg

import config
import msg2img
from catpg import RawSQL
from database import Channel, Prism, Profile, Reminder, User
from dotenv import load_dotenv

import time

load_dotenv()

import os

BASE_PATH = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_PATH, "config")

# Load aches.json
ACHES_FILE = os.path.join(CONFIG_PATH, "aches.json")
with open(ACHES_FILE, "r", encoding="utf-8-sig") as f:
    aches_data = json.load(f)

# Load battlepass.json
BATTLEPASS_FILE = os.path.join(CONFIG_PATH, "battlepass.json")
with open(BATTLEPASS_FILE, "r", encoding="utf-8-sig") as f:
    battlepass_data = json.load(f)

# Now you can use aches_data and battlepass_data anywhere in your bot
print("Aches loaded:", len(aches_data))
print("Battlepass loaded:", len(battlepass_data))

# Webhook server is handled by `webhook_server.py`.
# The reward logic for votes lives here below and will be scheduled by the webhook server.
async def reward_vote(user_id: int):
    # your reward logic here
    print(f"Rewarding vote for user {user_id}", flush=True)

# trigger warning, base64 encoded for your convinience
NONOWORDS = [base64.b64decode(i).decode("utf-8") for i in ["bmlja2E=", "bmlja2Vy", "bmlnYQ==", "bmlnZ2E=", "bmlnZ2Vy"]]

type_dict = {
    "Fine": 1000,
    "Nice": 750,
    "Good": 500,
    "Rare": 350,
    "Wild": 275,
    "Baby": 230,
    "Epic": 200,
    "Sus": 175,
    "Zombie": 160,
    "Brave": 150,
    "Rickroll": 125,
    "Reverse": 100,
    "Superior": 80,
    "Trash": 50,
    "Legendary": 35,
    "Mythic": 25,
    "8bit": 20,
    "Chef": 18,
    "Jamming": 17,
    "Corrupt": 15,
    "Professor": 10,
    "Water": 8.5,
    "Fire": 8.5,
    "Candy": 8,
    "Divine": 8,
    "Alien": 6,
    "Real": 5,
    "Ultimate": 3,
    "eGirl": 2,
    "TV": 1,
    "Donut": 0.5,
}

# this list stores unique non-duplicate cattypes
cattypes = list(type_dict.keys())

# Shop / Items definitions
SHOP_RESET_SECONDS = 6 * 3600  # 6 hours

# Price tiers (example values — adjust if you want different economy)
ITEM_PRICES = {
    "luck": {"I": 100, "II": 500, "III": 2500},
    "xp": {"I": 100, "II": 500, "III": 2500},
    "rains": {"I": 200, "II": 1000, "III": 5000},
    # Toys (prices are per-item purchase; toys grant multiple 'uses' when bought)
    "ball": {"I": 150, "II": 400, "III": 1200},
    # Food
    "dogtreat": {"I": 120},
    "pancakes": {"I": 5000},
}

# Human-readable item definitions
SHOP_ITEMS = {
    "luck": {
        "title": "Luck Potion",
        "tiers": {
            "I": {"desc": "+10% luck (packs, adventures, etc.)", "effect": 0.10},
            "II": {"desc": "+50% luck", "effect": 0.50},
            "III": {"desc": "+100% luck", "effect": 1.00},
        },
    },
    "xp": {
        "title": "XP Potion",
        "tiers": {
            "I": {"desc": "+10% battlepass XP from quests & adventures", "effect": 0.10},
            "II": {"desc": "+50% battlepass XP", "effect": 0.50},
            "III": {"desc": "+100% battlepass XP", "effect": 1.00},
        },
    },
    "rains": {
        "title": "Bottle o' Rains",
        "tiers": {
            "I": {"desc": "Gives 2 minutes of cat rains", "minutes": 2},
            "II": {"desc": "Gives 5 minutes of cat rains", "minutes": 5},
            "III": {"desc": "Gives 10 minutes of cat rains", "minutes": 10},
        },
    },
    # Toys for cats — each purchased toy grants a number of uses (tracked as item count)
    "ball": {
        "title": "Cat Ball",
        "tiers": {
            "I": {"desc": "Good Ball — +5 bond per use (5 uses)", "uses": 5, "bond": 5},
            "II": {"desc": "Great Ball — +10 bond per use (5 uses)", "uses": 5, "bond": 10},
            "III": {"desc": "Superior Ball — +20 bond per use (5 uses)", "uses": 5, "bond": 20},
        },
    },
    # Food items (one-time use)
    "dogtreat": {
        "title": "Dog Treat",
        "tiers": {
            "I": {"desc": "A tasty treat — +15 bond (one-time)", "bond": 15},
        },
    },
    "pancakes": {
        "title": "Pancakes",
        "tiers": {
            "I": {"desc": "Delicious pancakes — fully restores bond (one-time)", "bond": 100},
        },
    },
}

# In-memory temporary buffs applied by using potions. Keyed by string "{guild}_{user}".
# Example: ITEM_BUFFS["{guild}_{user}"] = {"luck": {"mult": 0.1, "until": 1234567890}, "xp": {...}}
ITEM_BUFFS: dict = {}
BUFFS_DB_PATH = "data/item_buffs.json"

def _ensure_buffs_db() -> dict:
    try:
        os.makedirs(os.path.dirname(BUFFS_DB_PATH), exist_ok=True)
    except Exception:
        pass
    if not os.path.exists(BUFFS_DB_PATH):
        with open(BUFFS_DB_PATH, "w", encoding="utf-8") as f:
            json.dump({}, f)
        return {}
    try:
        with open(BUFFS_DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_buffs_db(data: dict):
    try:
        os.makedirs(os.path.dirname(BUFFS_DB_PATH), exist_ok=True)
    except Exception:
        pass
    with open(BUFFS_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

def load_item_buffs():
    global ITEM_BUFFS
    db = _ensure_buffs_db()
    # keys stored as "guild_user" strings
    ITEM_BUFFS = db or {}

def save_item_buffs():
    _save_buffs_db(ITEM_BUFFS)

# Load buffs from disk at module import
try:
    load_item_buffs()
except Exception:
    ITEM_BUFFS = {}

def _get_buffs_key(guild_id: int, user_id: int) -> str:
    return f"{guild_id}_{user_id}"

def get_active_buffs(guild_id: int, user_id: int) -> dict:
    """Return active buff multipliers { 'luck': mult, 'xp': mult } and remove expired ones."""
    key = _get_buffs_key(guild_id, user_id)
    now = int(time.time())
    entry = ITEM_BUFFS.get(key, {})
    changed = False
    out = {}
    for buff_name, info in list(entry.items()):
        try:
            if info.get("until", 0) > now:
                out[buff_name] = info.get("mult", 0)
            else:
                # expired
                del entry[buff_name]
                changed = True
        except Exception:
            continue
    if changed:
        ITEM_BUFFS[key] = entry
        try:
            save_item_buffs()
        except Exception:
            pass
    return out


def _paginate_lines(lines: list[str], per_page: int = 15) -> list[str]:
    pages = []
    for i in range(0, len(lines), per_page):
        pages.append("\n".join(lines[i : i + per_page]))
    return pages


def send_paginated_embed(interaction: discord.Interaction, title: str, pages: list[str], color=None, footer: str = None, ephemeral: bool = True, locked: bool = False):
    """Send a paginated embed with Prev/Next buttons. `pages` is a list of strings for each page body."""
    if not pages:
        return

    # Resolve default color lazily so this function can be defined before Colors exists
    if color is None:
        try:
            color = Colors.brown
        except Exception:
            try:
                color = discord.Colour.from_str("#6E593C")
            except Exception:
                color = discord.Colour.dark_grey

    class Pager(View):
        def __init__(self, pages, author_id: int):
            super().__init__(timeout=300)
            self.pages = pages
            self.idx = 0
            self.author_id = author_id

        async def _render(self, interaction2: discord.Interaction):
            embed = discord.Embed(title=title, description=self.pages[self.idx], color=color)
            if footer:
                embed.set_footer(text=footer)
            try:
                await interaction2.edit_original_response(embed=embed, view=self)
            except Exception:
                try:
                    await interaction2.followup.send(embed=embed, view=self, ephemeral=ephemeral)
                except Exception:
                    pass

        @discord.ui.button(label="◀ Prev", style=ButtonStyle.secondary)
        async def prev(self, interaction2: discord.Interaction, button: Button):
            if interaction2.user.id != self.author_id and not (not locked and interaction2.user.id == interaction.user.id):
                await do_funny(interaction2)
                return
            self.idx = (self.idx - 1) % len(self.pages)
            await self._render(interaction2)

        @discord.ui.button(label="Next ▶", style=ButtonStyle.secondary)
        async def nxt(self, interaction2: discord.Interaction, button: Button):
            if interaction2.user.id != self.author_id and not (not locked and interaction2.user.id == interaction.user.id):
                await do_funny(interaction2)
                return
            self.idx = (self.idx + 1) % len(self.pages)
            await self._render(interaction2)

    # Send first page
    first = discord.Embed(title=title, description=pages[0], color=color)
    if footer:
        first.set_footer(text=footer)
    view = Pager(pages, interaction.user.id)
    try:
        return interaction.edit_original_response(embed=first, view=view)
    except Exception:
        return interaction.followup.send(embed=first, view=view, ephemeral=ephemeral)

# A small list of sample cat names for naming individual cats
cat_names = [
    "Mittens",
    "Whiskers",
    "Bella",
    "Luna",
    "Oliver",
    "Simba",
    "Chloe",
    "Leo",
    "Loki",
    "Milo",
    "Coco",
    "Nala",
    "Oscar",
    "Gizmo",
    "Pumpkin",
    "Socks",
    "Pepper",
    "Ginger",
    "Poppy",
    "Toby",
]

# Persistent per-user cat instances storage (simple JSON file to avoid DB migrations)
CAT_DB_PATH = "data/cats.json"


def _ensure_cat_db() -> dict:
    try:
        os.makedirs(os.path.dirname(CAT_DB_PATH), exist_ok=True)
    except Exception:
        pass
    if not os.path.exists(CAT_DB_PATH):
        with open(CAT_DB_PATH, "w", encoding="utf-8") as f:
            json.dump({}, f)
        return {}
    try:
        with open(CAT_DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cat_db(data: dict):
    try:
        os.makedirs(os.path.dirname(CAT_DB_PATH), exist_ok=True)
    except Exception:
        pass
    with open(CAT_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def get_user_cats(guild_id: int, user_id: int) -> list:
    db = _ensure_cat_db()
    return db.get(str(guild_id), {}).get(str(user_id), [])


def save_user_cats(guild_id: int, user_id: int, cats: list):
    db = _ensure_cat_db()
    db.setdefault(str(guild_id), {})[str(user_id)] = cats
    _save_cat_db(db)


# ----- Items DB (simple JSON storage) -----
ITEMS_DB_PATH = "data/items.json"


def _ensure_items_db() -> dict:
    try:
        os.makedirs(os.path.dirname(ITEMS_DB_PATH), exist_ok=True)
    except Exception:
        pass
    if not os.path.exists(ITEMS_DB_PATH):
        with open(ITEMS_DB_PATH, "w", encoding="utf-8") as f:
            json.dump({}, f)
        return {}
    try:
        with open(ITEMS_DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_items_db(data: dict):
    try:
        os.makedirs(os.path.dirname(ITEMS_DB_PATH), exist_ok=True)
    except Exception:
        pass
    with open(ITEMS_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def get_user_items(guild_id: int, user_id: int) -> dict:
    db = _ensure_items_db()
    return db.get(str(guild_id), {}).get(str(user_id), {})


def save_user_items(guild_id: int, user_id: int, items: dict):
    db = _ensure_items_db()
    db.setdefault(str(guild_id), {})[str(user_id)] = items
    _save_items_db(db)


# ----- Shop state (per-guild persisted rotation) -----
SHOP_STATE_PATH = "data/shop_state.json"


def _ensure_shop_state() -> dict:
    try:
        os.makedirs(os.path.dirname(SHOP_STATE_PATH), exist_ok=True)
    except Exception:
        pass
    if not os.path.exists(SHOP_STATE_PATH):
        with open(SHOP_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump({}, f)
        return {}
    try:
        with open(SHOP_STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_shop_state(data: dict):
    try:
        os.makedirs(os.path.dirname(SHOP_STATE_PATH), exist_ok=True)
    except Exception:
        pass
    with open(SHOP_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def get_guild_shop(guild_id: int) -> dict:
    db = _ensure_shop_state()
    return db.get(str(guild_id), {})


def save_guild_shop(guild_id: int, shop_data: dict):
    db = _ensure_shop_state()
    db.setdefault(str(guild_id), {})
    db[str(guild_id)] = shop_data
    _save_shop_state(db)



def _create_instances_only(guild_id: int, user_id: int, cat_type: str, amount: int):
    """Create `amount` instances in the JSON store WITHOUT touching aggregated DB counters.

    This is used to repair/sync per-instance storage when aggregated counters indicate the
    user should have instances but the JSON store is missing them.
    """
    if amount <= 0:
        return
    cats = get_user_cats(guild_id, user_id)
    for _ in range(amount):
        # ensure unique id
        while True:
            cid = uuid.uuid4().hex[:8]
            if cid not in [c.get("id") for c in cats]:
                break
        base_value = type_dict.get(cat_type, 100)
        instance = {
            "id": cid,
            "type": cat_type,
            "name": random.choice(cat_names),
            "bond": 0,
            "hp": max(1, math.ceil(base_value / 10)),
            "dmg": max(1, math.ceil(base_value / 50)),
            "acquired_at": int(time.time()),
        }
        cats.append(instance)
    save_user_cats(guild_id, user_id, cats)


async def add_cat_instances(profile: Profile, cat_type: str, amount: int):
    """Create `amount` cat instances for the given profile and increment aggregated counts.

    Each instance: {id, type, name, bond, hp, dmg, acquired_at}
    """
    try:
        guild_id = profile.guild_id
        user_id = profile.user_id
    except Exception:
        return

    cats = get_user_cats(guild_id, user_id)
    # If there's an on-adventure instance of this type, restore it first
    if amount > 0:
        for c in cats:
            if c.get("type") == cat_type and c.get("on_adventure"):
                try:
                    c["on_adventure"] = False
                    amount -= 1
                    break
                except Exception:
                    pass

    for _ in range(amount):
        # ensure unique id
        while True:
            cid = uuid.uuid4().hex[:8]
            if cid not in [c.get("id") for c in cats]:
                break
        base_value = type_dict.get(cat_type, 100)
        instance = {
            "id": cid,
            "type": cat_type,
            "name": random.choice(cat_names),
            "bond": 0,
            "hp": max(1, math.ceil(base_value / 10)),
            "dmg": max(1, math.ceil(base_value / 50)),
            "acquired_at": int(time.time()),
        }
        cats.append(instance)

    save_user_cats(guild_id, user_id, cats)

    # keep aggregated DB counters in sync
    try:
        profile[f"cat_{cat_type}"] += amount
        await profile.save()
    except Exception:
        pass


# Global tracking variables
RAIN_CHANNELS = {}  # Tracks active rain events
active_adventures = {}  # Tracks active adventures
active_reminders = {}  # Tracks active reminders
# cooldown tracker for pet actions: key = (guild_id, user_id, instance_id) -> last_pet_ts
pet_cooldowns = {}

# generate a dict with lowercase'd keys
cattype_lc_dict = {i.lower(): i for i in cattypes}

allowedemojis = []
for i in cattypes:
    allowedemojis.append(i.lower() + "cat")

pack_data = [
    {"name": "Wooden", "value": 65, "upgrade": 30, "totalvalue": 75},
    {"name": "Stone", "value": 90, "upgrade": 30, "totalvalue": 100},
    {"name": "Bronze", "value": 100, "upgrade": 30, "totalvalue": 130},
    {"name": "Silver", "value": 115, "upgrade": 30, "totalvalue": 200},
    {"name": "Gold", "value": 230, "upgrade": 30, "totalvalue": 400},
    {"name": "Platinum", "value": 630, "upgrade": 30, "totalvalue": 800},
    {"name": "Diamond", "value": 860, "upgrade": 30, "totalvalue": 1200},
    {"name": "Celestial", "value": 2000, "upgrade": 30, "totalvalue": 2000}  # is that a madeline celeste reference????
]

prism_names_start = [
    "Alpha",
    "Bravo",
    "Charlie",
    "Delta",
    "Echo",
    "Foxtrot",
    "Golf",
    "Hotel",
    "India",
    "Juliett",
    "Kilo",
    "Lima",
    "Mike",
    "November",
    "Oscar",
    "Papa",
    "Quebec",
    "Romeo",
    "Sierra",
    "Tango",
    "Uniform",
    "Victor",
    "Whiskey",
    "X-ray",
    "Yankee",
    "Zulu",
]
prism_names_end = [
    "",
    " Two",
    " Three",
    " Four",
    " Five",
    " Six",
    " Seven",
    " Eight",
    " Nine",
    " Ten",
    " Eleven",
    " Twelve",
    " Thirteen",
    " Fourteen",
    " Fifteen",
    " Sixteen",
    " Seventeen",
    " Eighteen",
    " Nineteen",
    " Twenty",
]
prism_names = []
for i in prism_names_end:
    for j in prism_names_start:
        prism_names.append(j + i)

vote_button_texts = [
    "vote please",
    "click me to vote!",
    "i need votes!",
    "vote for kittay. kittay for president!",
    "cool guys click here!",
    "vote vote vote!",
    "vote 4 kittay :P",
]

# various hints/fun facts
hints = [
    "KITTAYYYYYYY has a wiki! <https://wiki.minkos.lol>",
    "KITTAYYYYYYY is open source! <https://github.com/FillerMcDiller/cat-bot>",
]

import json, os

# --- Load achievements file safely ---
ach_list_path = "config/aches.json"
if not os.path.exists(ach_list_path) or os.path.getsize(ach_list_path) == 0:
    print("⚠️ aches.json missing or empty — creating default.")
    ach_list = {}
else:
    try:
        with open(ach_list_path, "r", encoding="utf-8") as f:
            ach_list = json.load(f)
    except json.JSONDecodeError:
        print("⚠️ aches.json is invalid — resetting to empty.")
        ach_list = {}

# --- Load battlepass file safely ---
battle_path = "config/battlepass.json"
if not os.path.exists(battle_path) or os.path.getsize(battle_path) == 0:
    print("⚠️ battlepass.json missing or empty — creating default.")
    battle = {}
else:
    try:
        with open(battle_path, "r", encoding="utf-8") as f:
            battle = json.load(f)
    except json.JSONDecodeError:
        print("⚠️ battlepass.json is invalid — resetting to empty.")
        battle = {}
import os
print("Current working directory:", os.getcwd())
print("Aches.json absolute path:", os.path.abspath("config/aches.json"))

# convert achievement json to a few other things
ach_names = ach_list.keys()
ach_titles = {value["title"].lower(): key for (key, value) in ach_list.items()}

RESTART_INTERVAL = 20        # 6 hours in seconds
WARNING_BEFORE = 60               # 1 minute warning
RESTART_WARNING_CHANNEL_ID = 123456789012345678  # replace with your channel ID

bot = commands.AutoShardedBot(
    command_prefix="!",
    intents=discord.Intents.default()
)

# Set an asyncio loop-level exception handler so unhandled exceptions are logged
def _loop_exception_handler(loop, context):
    try:
        # context may contain 'exception' or 'message'
        exc = context.get("exception")
        msg = context.get("message")
        if exc:
            logging.exception("Unhandled exception in event loop", exc_info=exc)
        else:
            logging.error("Unhandled event loop error: %s", msg)
    except Exception:
        try:
            logging.exception("Failure inside loop exception handler")
        except Exception:
            pass

try:
    _loop = asyncio.get_event_loop()
    try:
        _loop.set_exception_handler(_loop_exception_handler)
    except Exception:
        pass
except Exception:
    pass

# Hook sys.excepthook to log uncaught exceptions from threads/main
def _excepthook(type_, value, tb):
    try:
        logging.exception("Uncaught exception", exc_info=(type_, value, tb))
    except Exception:
        pass

sys.excepthook = _excepthook

# --- Discord log forwarder ---
import sys
import logging

# buffer for logs emitted before the bot is ready
_pending_discord_logs: list[str] = []

# in-memory buffer and scheduling state to avoid spamming the Discord channel
_discord_log_buffer: list[str] = []
_discord_flush_scheduled = False
_DISCORD_FLUSH_INTERVAL = 5.0  # seconds to wait before flushing accumulated logs
_DISCORD_MAX_LINES = 200

async def _post_log_batch_to_discord(lines: list[str]):
    try:
        chan_id = int(getattr(config, "RAIN_CHANNEL_ID", 0) or 0)
        if not chan_id:
            return
        ch = bot.get_channel(chan_id)
        if ch is None:
            try:
                ch = await bot.fetch_channel(chan_id)
            except Exception:
                ch = None
        if ch is None:
            return

        if not lines:
            return

        # Limit the number of lines sent to avoid flooding; indicate truncation
        send_lines = lines[:_DISCORD_MAX_LINES]
        dropped = len(lines) - len(send_lines)
        payload = "\n".join(send_lines)
        if dropped > 0:
            payload += f"\n...+{dropped} more lines suppressed..."

        # break into chunks respecting Discord message length
        maxlen = 1900
        if len(payload) <= maxlen:
            await ch.send(f"```\n{payload}\n```")
        else:
            for i in range(0, len(payload), maxlen):
                await ch.send(f"```\n{payload[i:i+maxlen]}\n```")
    except Exception:
        pass


async def _schedule_flush(delay: float = _DISCORD_FLUSH_INTERVAL):
    global _discord_flush_scheduled
    try:
        await asyncio.sleep(delay)
        # swap buffer
        if not _discord_log_buffer:
            _discord_flush_scheduled = False
            return
        lines = _discord_log_buffer.copy()
        _discord_log_buffer.clear()
        _discord_flush_scheduled = False
        await _post_log_batch_to_discord(lines)
    except Exception:
        _discord_flush_scheduled = False


class DiscordLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            # Filter noisy discord.py HTTP rate-limit messages — don't forward them
            try:
                message_text = record.getMessage() or ""
            except Exception:
                message_text = ""
            lower_msg = message_text.lower()
            # common rate-limit indicators
            if record.name.startswith("discord.http") and ("we are being rate limited" in lower_msg or "429" in lower_msg or "rate limited" in lower_msg):
                return
            if "we are being rate limited" in lower_msg or "retrying in" in lower_msg or "rate limited" in lower_msg:
                return

            # Keep log messages concise — single-line summaries
            msg = self.format(record).splitlines()[0]

            # if bot is not ready yet, store message
            try:
                if not bot or not getattr(bot, "is_ready", lambda: False)():
                    _pending_discord_logs.append(msg)
                    return
            except Exception:
                _pending_discord_logs.append(msg)
                return

            # append to in-memory buffer and schedule a flush (best-effort)
            _discord_log_buffer.append(msg)
            global _discord_flush_scheduled
            if not _discord_flush_scheduled:
                _discord_flush_scheduled = True
                try:
                    asyncio.create_task(_schedule_flush())
                except Exception:
                    _discord_flush_scheduled = False
        except Exception:
            pass


# redirect stdout/stderr to logger so print()s are captured but not spammy
class _StreamToLogger:
    def __init__(self, logger: logging.Logger, level: int = logging.INFO):
        self.logger = logger
        self.level = level

    def write(self, message: str):
        message = message.rstrip("\n")
        if not message:
            return
        # only log short, non-empty lines to prevent spam
        if len(message) > 1000:
            message = message[:1000] + "..."
        try:
            self.logger.log(self.level, message)
        except Exception:
            pass

    def flush(self):
        pass


# attach handler to root logger
_discord_handler = DiscordLogHandler()
_discord_handler.setLevel(logging.WARNING)  # only forward warnings and above by default
formatter = logging.Formatter("[%(levelname)s] %(asctime)s %(name)s: %(message)s")
_discord_handler.setFormatter(formatter)
logging.getLogger().addHandler(_discord_handler)
logging.getLogger().setLevel(logging.INFO)

# Redirect stdout/stderr into logging (will be INFO/ERROR level; handler filters by WARNING)
sys.stdout = _StreamToLogger(logging.getLogger("stdout"), logging.INFO)
sys.stderr = _StreamToLogger(logging.getLogger("stderr"), logging.ERROR)

@bot.event
async def on_ready():
    print(f"Bot ready! Logged in as {bot.user} | WS latency: {round(bot.latency*1000)}ms")


async def scheduled_restart():
    await bot.wait_until_ready()
    while not bot.is_closed():
        # Wait until 1 minute before restart
        await asyncio.sleep(RESTART_INTERVAL - WARNING_BEFORE)

        # Send warning message
        try:
            channel = bot.get_channel(RESTART_WARNING_CHANNEL_ID)
            if channel:
                await channel.send("⚠️ Bot will restart in 1 minute for maintenance. Please wait…")
        except Exception as e:
            print(f"[Restart Warning Error] {e}")

        # Wait remaining 1 minute
        await asyncio.sleep(WARNING_BEFORE)

        print("🔄 Restarting bot now...")
        await bot.close()  # clean disconnect

        # Restart process using the same Python interpreter (inside venv)
        os.execv(sys.executable, [sys.executable] + sys.argv)


async def cleanup_cooldowns():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            # your actual cleanup logic here
            print("🧹 Cleaning up cooldowns...")
            # Example: catchcooldown.clear()
        except Exception as e:
            print(f"Cleanup error: {e}")
        await asyncio.sleep(300)  # wait 5 minutes before next cleanup


# Use proper setup_hook to start background tasks safely
async def setup_hook():
    bot.loop.create_task(scheduled_restart())
    bot.loop.create_task(cleanup_cooldowns())
    # start background indexing of per-instance cats to keep JSON and DB counters in sync
    bot.loop.create_task(background_index_all_cats())
    # Ensure application commands are registered
    try:
        await bot.tree.sync()
    except Exception:
        pass

bot.setup_hook = setup_hook


async def background_index_all_cats():
    """Background task: ensure per-instance JSON and DB aggregated counters are in sync.

    - For each guild/user entry in data/cats.json, counts instances per cat type.
    - If DB aggregated counter < instance count, bump DB counter to match.
    - If DB aggregated counter > instance count, create missing instances to match the DB (so instances exist for selection flows).
    Runs once on startup and then every 30 minutes.
    """
    await bot.wait_until_ready()
    await asyncio.sleep(5)  # small delay for DB readiness
    import collections

    while not bot.is_closed():
        try:
            db = _ensure_cat_db()
            # iterate guilds
            for guild_str, users in list(db.items()):
                try:
                    guild_id = int(guild_str)
                except Exception:
                    continue
                # iterate users for this guild
                for user_str, cats in list(users.items()):
                    try:
                        user_id = int(user_str)
                    except Exception:
                        continue
                    try:
                        # count instances per type (exclude None)
                        counter = collections.Counter()
                        for c in cats:
                            try:
                                t = c.get("type")
                                if t:
                                    counter[t] += 1
                            except Exception:
                                continue

                        # fetch profile
                        try:
                            profile = await Profile.get_or_create(guild_id=guild_id, user_id=user_id)
                            await profile.refresh_from_db()
                        except Exception:
                            profile = None

                        # for each cat type seen in either counter or DB, reconcile
                        types_to_check = set(list(counter.keys()))
                        if profile:
                            for ct in cattypes:
                                try:
                                    dbcount = int(profile.get(f"cat_{ct}") or 0)
                                except Exception:
                                    dbcount = 0
                                if dbcount > 0:
                                    types_to_check.add(ct)

                        for cat_type in types_to_check:
                            inst_count = int(counter.get(cat_type, 0))
                            db_count = 0
                            if profile:
                                try:
                                    db_count = int(profile.get(f"cat_{cat_type}") or 0)
                                except Exception:
                                    db_count = 0

                            # If DB counter is less than instance count, increase DB counter to match
                            if profile and db_count < inst_count:
                                try:
                                    profile[f"cat_{cat_type}"] = inst_count
                                    await profile.save()
                                except Exception:
                                    pass

                            # If DB counter is greater than instance count, create missing instances in JSON
                            if db_count > inst_count:
                                missing = db_count - inst_count
                                if missing > 0:
                                    try:
                                        _create_instances_only(guild_id, user_id, cat_type, missing)
                                    except Exception:
                                        pass
                    except Exception:
                        # per-user failure shouldn't stop whole pass
                        continue
        except Exception:
            pass

        # run again in 30 minutes
        await asyncio.sleep(30 * 60)


funny = [
    "why did you click this this arent yours",
    "absolutely not",
    "KITTAYYYYYYY not responding, try again later",
    "you cant",
    "can you please stop",
    "try again",
    "403 not allowed",
    "stop",
    "get a life",
    "not for you",
    "no",
    "nuh uh",
    "access denied",
    "forbidden",
    "don't do this",
    "cease",
    "wrong",
    "aw dangit",
    "why don't you press buttons from your commands",
    "you're only making me angrier",
    "get a j*b",
    "stop clicking it you clicker",
]


class Colors:
    brown = 0x6E593C
    green = 0x007F0E
    yellow = 0xFFFF00
    maroon = 0x750F0E
    demonic = 0xC12929
    rose = 0xFF81C6
    red = 0xFF0000


# rain shill message for footers
rain_shill = "rains are pretty cool, you know? ☔"

# timeout for views
# higher one means buttons work for longer but uses more ram to keep track of them
VIEW_TIMEOUT = 86400

# store credits usernames to prevent excessive api calls
gen_credits = {}

    # Rate limits and cooldowns
# Reactions rate limit (50 per cycle)
reactions_ratelimit = {}

# Channel-based point laugh rate limit 
pointlaugh_ratelimit = {}

# Message-based cooldowns
message_cooldown = {}

# Command cooldowns
catchcooldown = {}
fakecooldown = {}# KITTAYYYYYYY auto-claims in the channel user last ran /vote in
# this is a failsafe to store the fact they voted until they ran that atleast once
pending_votes = []

# prevent ratelimits
casino_lock = []
slots_lock = []

# ???
rigged_users = []


# WELCOME TO THE TEMP_.._STORAGE HELL

# to prevent double catches
temp_catches_storage = []

# to prevent weird behaviour shortly after a rain
temp_rains_storage = []

# to prevent double belated battlepass progress and for "faster than 10 seconds" belated bp quest
temp_belated_storage = {}

# to prevent weird cookie things without destroying the database with load
temp_cookie_storage = {}

# active adventures storage (user_id -> adventure data)
active_adventures = {}

# adventures persistence file
ADVENTURES_PATH = "data/adventures.json"


def load_adventures():
    global active_adventures
    try:
        if os.path.exists(ADVENTURES_PATH):
            with open(ADVENTURES_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                # ensure keys are strings
                active_adventures = {str(k): v for k, v in data.items()}
    except Exception:
        active_adventures = {}


def save_adventures():
    try:
        os.makedirs(os.path.dirname(ADVENTURES_PATH), exist_ok=True)
        with open(ADVENTURES_PATH, "w", encoding="utf-8") as f:
            json.dump(active_adventures, f)
    except Exception:
        pass
# docs suggest on_ready can be called multiple times
on_ready_debounce = False

about_to_stop = False

# d.py doesnt cache app emojis so we do it on our own yippe
emojis = {}

# for mentioning it in catch message, will be auto-fetched in on_ready()
RAIN_ID = 1270470307102195752

# for dev commands, this is fetched in on_ready
OWNER_ID = 726686526133501952

# for funny stats, you can probably edit maintaince_loop to restart every X of them
loop_count = 0

# loops in dpy can randomly break, i check if is been over X minutes since last loop to restart it
last_loop_time = 0
# random rain time!
last_random_rain_time = 0


def get_emoji(name):
    global emojis
    if name in emojis.keys():
        return emojis[name]
    elif name in emoji.EMOJI_DATA:
        return name
    else:
        return "🔳"


async def fetch_perms(message: discord.Message | discord.Interaction) -> discord.Permissions:
    # this is mainly for threads where the parent isnt cached
    if isinstance(message.channel, discord.Thread) and not message.channel.parent:
        parent = message.guild.get_channel(message.channel.parent_id) or await message.guild.fetch_channel(message.channel.parent_id)
        return parent.permissions_for(message.guild.me)
    else:
        return message.channel.permissions_for(message.guild.me)


# news stuff
news_list = [
    {"title": "KITTAYYYYYYY Survey - win rains!", "emoji": "📜"},
    {"title": "New Cat Rains perks!", "emoji": "✨"},
    {"title": "KITTAYYYYYYY Christmas 2024", "emoji": "🎅"},
    {"title": "Battlepass Update", "emoji": "⬆️"},
    {"title": "Packs!", "emoji": "goldpack"},
    {"title": "Message from CEO of KITTAYYYYYYY", "emoji": "finecat"},
    {"title": "KITTAYYYYYYY Turns 3", "emoji": "🥳"},
    {"title": "100,000 SERVERS WHAT", "emoji": "🎉"},
    {"title": "Regarding recent instabilities", "emoji": "🗒️"},
    {"title": "NEW CATS, KIBBLE, AND.. ITEMS??? WOWOWOWOOWO!!!", "emoji": "🔥"},
]


# this is some common code which is run whether someone gets an achievement
async def achemb(message, ach_id, send_type, author_string=None):
    if not author_string:
        try:
            author_string = message.author
        except Exception:
            author_string = message.user
    author = author_string.id

    if not message.guild:
        return

    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=author)

    # Safely handle missing DB columns for achievements.
    # If the column doesn't exist in the profile record then __getitem__ will
    # raise KeyError (coming from catpg.Model.__getitem__). Instead of crashing
    # the bot, bail out and log a helpful message so the migration can be run.
    try:
        if profile[ach_id]:
            return
    except KeyError:
        # DB is missing the achievement column. Log and stop.
        try:
            logger = logging.getLogger(__name__)
            logger.warning(
                "Achievement column '%s' missing on profile table. Run the migration to add new achievement columns.",
                ach_id,
            )
        except Exception:
            pass
        return

    try:
        profile[ach_id] = True
        await profile.save()
    except KeyError:
        # Column was present for read but missing for write (paranoia); log and return.
        try:
            logger = logging.getLogger(__name__)
            logger.warning(
                "Failed to set achievement '%s' because the DB column is missing. Run the migration to add it.",
                ach_id,
            )
        except Exception:
            pass
        return
    ach_data = ach_list[ach_id]
    desc = ach_data["description"]
    if ach_id == "dataminer":
        desc = "Your head hurts -- you seem to have forgotten what you just did to get this."

    if ach_id != "thanksforplaying":
        embed = (
            discord.Embed(title=ach_data["title"], description=desc, color=Colors.green)
            .set_author(
                name="Achievement get!",
                icon_url="https://wsrv.nl/?url=raw.githubusercontent.com/staring-cat/emojis/main/ach.png",
            )
            .set_footer(text=f"Unlocked by {author_string.name}")
        )
    else:
        embed = (
            discord.Embed(
                title="Cataine Addict",
                description="Defeat the dog mafia\nThanks for playing! ✨",
                color=Colors.demonic,
            )
            .set_author(
                name="Demonic achievement unlocked! 🌟",
                icon_url="https://wsrv.nl/?url=raw.githubusercontent.com/staring-cat/emojis/main/demonic_ach.png",
            )
            .set_footer(text=f"Congrats to {author_string.name}!!")
        )

        embed2 = (
            discord.Embed(
                title="Cataine Addict",
                description="Defeat the dog mafia\nThanks for playing! ✨",
                color=Colors.yellow,
            )
            .set_author(
                name="Demonic achievement unlocked! 🌟",
                icon_url="https://wsrv.nl/?url=raw.githubusercontent.com/staring-cat/emojis/main/demonic_ach.png",
            )
            .set_footer(text=f"Congrats to {author_string.name}!!")
        )

    try:
        result = None
        perms = await fetch_perms(message)
        correct_perms = perms.send_messages and (not isinstance(message.channel, discord.Thread) or perms.send_messages_in_threads)
        if send_type == "reply" and correct_perms:
            result = await message.reply(embed=embed)
        elif send_type == "send" and correct_perms:
            result = await message.channel.send(embed=embed)
        elif send_type == "followup":
            result = await message.followup.send(embed=embed, ephemeral=True)
        elif send_type == "response":
            result = await message.response.send_message(embed=embed)
        await progress(message, profile, "achievement")
        await finale(message, profile)
    except Exception:
        pass

    if result and ach_id == "thanksforplaying":
        await asyncio.sleep(2)
        await result.edit(embed=embed2)
        await asyncio.sleep(2)
        await result.edit(embed=embed)
        await asyncio.sleep(2)
        await result.edit(embed=embed2)
        await asyncio.sleep(2)
        await result.edit(embed=embed)
    elif result and ach_id == "curious":
        await result.delete(delay=30)

async def _check_full_stack_and_huzzful(profile, message, cat_type: str):
    """
    Award Full Stack (64+) and Huzzful (catch eGirl).
    - profile: Profile object (guild-level inventory profile)
    - message: discord.Message or discord.Interaction used for achemb()
    - cat_type: e.g. "eGirl", "Fine"
    """
    try:
        await profile.refresh_from_db()
    except Exception:
        pass

    # Normalize the cat type to the canonical form used in the DB columns.
    # `cattype_lc_dict` maps lowercase names to canonical names (e.g. 'egirl' -> 'eGirl').
    try:
        canonical = cattype_lc_dict.get(cat_type.lower(), cat_type)
    except Exception:
        canonical = cat_type

    # Huzzful: catching an eGirl (case-insensitive)
    try:
        if canonical.lower() == "egirl":
            await achemb(message, "huzzful", "send")
    except Exception:
        # don't raise — achievement logic should never crash the bot
        pass

    # Full Stack: having 64+ of the canonical cat type (use DB column name)
    try:
        colname = f"cat_{canonical}"
        if profile[colname] >= 64:
            await achemb(message, "full_stack", "send")
    except Exception:
        pass
            
async def generate_quest(user: Profile, quest_type: str):
    while True:
        quest = random.choice(list(battle["quests"][quest_type].keys()))
        if quest in ["slots", "reminder"]:
            # removed quests
            continue
        elif quest == "prism":
            total_count = await Prism.count("guild_id = $1", user.guild_id)
            user_count = await Prism.count("guild_id = $1 AND user_id = $2", user.guild_id, user.user_id)
            global_boost = 0.06 * math.log(2 * total_count + 1)
            prism_boost = global_boost + 0.03 * math.log(2 * user_count + 1)
            if prism_boost < 0.15:
                continue
        elif quest == "news":
            global_user = await User.get_or_create(user_id=user.user_id)
            if len(news_list) <= len(global_user.news_state.strip()) and "0" not in global_user.news_state.strip()[-4:]:
                continue
        elif quest == "achievement":
            unlocked = 0
            for k in ach_names:
                if user[k] and ach_list[k]["category"] != "Hidden":
                    unlocked += 1
            if unlocked > 30:
                continue
        break

    quest_data = battle["quests"][quest_type][quest]
    if quest_type == "vote":
        user.vote_reward = random.randint(quest_data["xp_min"] // 10, quest_data["xp_max"] // 10) * 10
        user.vote_cooldown = 0
    elif quest_type == "catch":
        user.catch_reward = random.randint(quest_data["xp_min"] // 10, quest_data["xp_max"] // 10) * 10
        user.catch_quest = quest
        user.catch_cooldown = 0
    elif quest_type == "misc":
        user.misc_reward = random.randint(quest_data["xp_min"] // 10, quest_data["xp_max"] // 10) * 10
        user.misc_quest = quest
        user.misc_cooldown = 0
    await user.save()


async def refresh_quests(user):
    await user.refresh_from_db()
    start_date = datetime.datetime(2024, 12, 1)
    current_date = datetime.datetime.utcnow()
    full_months_passed = (current_date.year - start_date.year) * 12 + (current_date.month - start_date.month)
    if current_date.day < start_date.day:
        full_months_passed -= 1
    if user.season != full_months_passed:
        user.bp_history = user.bp_history + f"{user.season},{user.battlepass},{user.progress};"
        user.battlepass = 0
        user.progress = 0

        user.catch_quest = ""
        user.catch_progress = 0
        user.catch_cooldown = 1
        user.catch_reward = 0

        user.misc_quest = ""
        user.misc_progress = 0
        user.misc_cooldown = 1
        user.misc_reward = 0

        user.season = full_months_passed
        await user.save()
    if 12 * 3600 < user.vote_cooldown + 12 * 3600 < time.time():
        await generate_quest(user, "vote")
    if 12 * 3600 < user.catch_cooldown + 12 * 3600 < time.time():
        await generate_quest(user, "catch")
    if 12 * 3600 < user.misc_cooldown + 12 * 3600 < time.time():
        await generate_quest(user, "misc")


async def progress(message: discord.Message | discord.Interaction, user: Profile, quest: str, is_belated: Optional[bool] = False):
    await refresh_quests(user)
    await user.refresh_from_db()

    # progress
    quest_complete = False
    if user.catch_quest == quest:
        if user.catch_cooldown != 0:
            return
        quest_data = battle["quests"]["catch"][quest]
        user.catch_progress += 1
        if user.catch_progress >= quest_data["progress"]:
            quest_complete = True
            user.catch_cooldown = int(time.time())
            current_xp = user.progress + user.catch_reward
            user.catch_progress = 0
            user.reminder_catch = 1
    elif quest == "vote":
        if user.vote_cooldown != 0:
            return
        quest_data = battle["quests"]["vote"][quest]
        global_user = await User.get_or_create(user_id=user.user_id)
        user.vote_cooldown = global_user.vote_time_topgg

        # Weekdays 0 Mon - 6 Sun
        # double vote xp rewards if Friday, Saturday or Sunday
        voted_at = datetime.datetime.utcfromtimestamp(global_user.vote_time_topgg)
        if voted_at.weekday() >= 4:
            user.vote_reward *= 2

        streak_data = get_streak_reward(global_user.vote_streak)
        if streak_data["reward"]:
            user[f"pack_{streak_data['reward']}"] += 1

        current_xp = user.progress + user.vote_reward
        quest_complete = True
    elif user.misc_quest == quest:
        if user.misc_cooldown != 0:
            return
        quest_data = battle["quests"]["misc"][quest]
        user.misc_progress += 1
        if user.misc_progress >= quest_data["progress"]:
            quest_complete = True
            user.misc_cooldown = int(time.time())
            current_xp = user.progress + user.misc_reward
            user.misc_progress = 0
            user.reminder_misc = 1
    else:
        return

    await user.save()
    if not quest_complete:
        return

    user.quests_completed += 1

    old_xp = user.progress
    perms = await fetch_perms(message)
    level_complete_embeds = []
    if user.battlepass >= len(battle["seasons"][str(user.season)]):
        level_data = {"xp": 1500, "reward": "Stone", "amount": 1}
        level_text = "Extra Rewards"
    else:
        level_data = battle["seasons"][str(user.season)][user.battlepass]
        level_text = f"Level {user.battlepass + 1}"

    if current_xp >= level_data["xp"]:
        xp_progress = current_xp
        active_level_data = level_data
        while xp_progress >= active_level_data["xp"]:
            user.battlepass += 1
            xp_progress -= active_level_data["xp"]
            user.progress = xp_progress
            cat_emojis = None
            if active_level_data["reward"] == "Rain":
                user.rain_minutes += active_level_data["amount"]
            elif active_level_data["reward"] in ["Wooden", "Stone", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Celestial"]:
                user[f"pack_{active_level_data['reward'].lower()}"] += active_level_data["amount"]
            elif active_level_data["reward"] in cattypes:
                user[f"cat_{active_level_data['reward']}"] += active_level_data["amount"]
            await user.save()
            # after incrementing user.battlepass and saving inside the battlepass loop:
            try:
                if user.battlepass == len(battle["seasons"].get(str(user.season), [])):
                    await achemb(message, "grinder", "send")
            except Exception:
                pass
            if not cat_emojis:
                if active_level_data["reward"] == "Rain":
                    description = f"You got ☔ {active_level_data['amount']} rain minutes!"
                elif active_level_data["reward"] in cattypes:
                    description = f"You got {get_emoji(active_level_data['reward'].lower() + 'cat')} {active_level_data['amount']} {active_level_data['reward']}!"
                else:
                    description = f"You got a {get_emoji(active_level_data['reward'].lower() + 'pack')} {active_level_data['reward']} pack! Do /packs to open it!"
                title = f"Level {user.battlepass} Complete!"
            else:
                description = f"You got {cat_emojis}!"
                title = "Bonus Complete!"
            embed_level_up = discord.Embed(title=title, description=description, color=Colors.yellow)
            level_complete_embeds.append(embed_level_up)

            if user.battlepass >= len(battle["seasons"][str(user.season)]):
                active_level_data = {"xp": 1500, "reward": "Stone", "amount": 1}
                new_level_text = "Extra Rewards"
            else:
                active_level_data = battle["seasons"][str(user.season)][user.battlepass]
                new_level_text = f"Level {user.battlepass + 1}"

        embed_progress = await progress_embed(
            message,
            user,
            active_level_data,
            xp_progress,
            0,
            quest_data,
            current_xp - old_xp,
            new_level_text,
        )

    else:
        user.progress = current_xp
        await user.save()
        embed_progress = await progress_embed(
            message,
            user,
            level_data,
            current_xp,
            old_xp,
            quest_data,
            current_xp - old_xp,
            level_text,
        )

    if is_belated:
        embed_progress.set_footer(text="For catching within 3 seconds")

    if (
        perms.send_messages
        and perms.embed_links
        and (not isinstance(message.channel, discord.Thread) or perms.send_messages_in_threads)
    ):
        if level_complete_embeds:
            await message.channel.send(f"<@{user.user_id}>", embeds=level_complete_embeds + [embed_progress])
        else:
            await message.channel.send(f"<@{user.user_id}>", embed=embed_progress)


async def progress_embed(message, user, level_data, current_xp, old_xp, quest_data, diff, level_text) -> discord.Embed:
    percentage_before = int(old_xp / level_data["xp"] * 10)
    percentage_after = int(current_xp / level_data["xp"] * 10)
    percenteage_left = 10 - percentage_after

    progress_line = get_emoji("staring_square") * percentage_before + "🟨" * (percentage_after - percentage_before) + "⬛" * percenteage_left

    title = quest_data["title"] if "top.gg" not in quest_data["title"] else "Vote on Top.gg"

    if level_data["reward"] == "Rain":
        reward_text = f"☔ {level_data['amount']}m of Rain"
    elif level_data["reward"] == "random cats":
        reward_text = f"❓ {level_data['amount']} random cats"
    elif level_data["reward"] in cattypes:
        reward_text = f"{get_emoji(level_data['reward'].lower() + 'cat')} {level_data['amount']} {level_data['reward']}"
    else:
        reward_text = f"{get_emoji(level_data['reward'].lower() + 'pack')} {level_data['reward']} pack"

    global_user = await User.get_or_create(user_id=user.user_id)
    streak_data = get_streak_reward(global_user.vote_streak)
    if streak_data["reward"] and "top.gg" in quest_data["title"]:
        streak_reward = f"\n🔥 **Streak Bonus!** +1 {streak_data['emoji']} {streak_data['reward'].capitalize()} pack"
    else:
        streak_reward = ""

    return discord.Embed(
        title=f"✅ {title}",
        description=f"{progress_line}\n{current_xp}/{level_data['xp']} XP (+{diff})\nReward: {reward_text}{streak_reward}",
        color=Colors.green,
    ).set_author(name="/battlepass " + level_text)


def get_streak_reward(streak):
    if streak % 5 != 0 or streak in [0, 5]:
        return {"reward": None, "emoji": "⬛", "done_emoji": "🟦"}

    pack_type = "gold"
    # these honestly don't add that much value but feel like good milestones
    if streak % 100 == 0:
        pack_type = "diamond"
    elif streak % 25 == 0:
        pack_type = "platinum"

    return {"reward": pack_type, "emoji": get_emoji(f"{pack_type}pack"), "done_emoji": get_emoji(f"{pack_type}pack_claimed")}


# handle curious people clicking buttons
async def do_funny(message):
    await message.response.send_message(random.choice(funny), ephemeral=True)
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    user.funny += 1
    await user.save()
    await achemb(message, "curious", "send")
    if user.funny >= 50:
        await achemb(message, "its_not_working", "send")


# not :eyes:
async def debt_cutscene(message, user):
    if user.debt_seen:
        return

    user.debt_seen = True
    await user.save()

    debt_msgs = [
        "**\\*BANG\\***",
        "Your door gets slammed open and multiple man in black suits enter your room.",
        "**???**: Hello, you have unpaid debts. You owe us money. We are here to liquidate all your assets.",
        "*(oh for fu)*",
        "**You**: pls dont",
        "**???**: oh okay then we will come back to you later.",
        "They leave the room.",
        "**You**: Oh god this is bad",
        "**You**: I know of a solution though!",
        "**You**: I heard you can gamble your debts away in the slots machine!",
    ]

    for debt_msg in debt_msgs:
        await asyncio.sleep(4)
        await message.followup.send(debt_msg, ephemeral=True)


# :eyes:
async def finale(message, user):
    if user.finale_seen:
        return

    # check ach req
    for k in ach_names:
        if not user[k] and ach_list[k]["category"] != "Hidden":
            return

    user.finale_seen = True
    await user.save()
    perms = await fetch_perms(message)
    if perms.send_messages and (not isinstance(message.channel, discord.Thread) or perms.send_messages_in_threads):
        try:
            author_string = message.author
        except Exception:
            author_string = message.user
        await asyncio.sleep(5)
        await message.channel.send("...")
        await asyncio.sleep(3)
        await message.channel.send("You...")
        await asyncio.sleep(3)
        await message.channel.send("...actually did it.")
        await asyncio.sleep(3)
        await message.channel.send(
            embed=discord.Embed(
                title="True Ending achieved!",
                description="You are finally free.",
                color=Colors.rose,
            )
            .set_author(
                name="All achievements complete!",
                icon_url="https://wsrv.nl/?url=raw.githubusercontent.com/milenakos/cat-bot/main/images/cat.png",
            )
            .set_footer(text=f"Congrats to {author_string}")
        )


# function to autocomplete cat_type choices for /givecat, and /forcespawn, which also allows more than 25 options
async def cat_type_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    return [discord.app_commands.Choice(name=choice, value=choice) for choice in cattypes if current.lower() in choice.lower()][:25]


# function to autocomplete /cat, it only shows the cats you have
# Helper function to check if a user has an available cat (not on adventure)
async def get_available_cat_count(profile: Profile, cat_type: str) -> int:
    """Returns the number of available cats of the given type (excluding those on adventure and favorites).

    Prefers counting per-instance stored cats (excluding favorites and on-adventure). If instance data
    is unavailable or yields zero non-favourited instances, falls back to aggregated profile counters
    while still excluding a cat on adventure.
    """
    # Prefer instance-level counts so favourites are respected
    try:
        cats = get_user_cats(profile.guild_id, profile.user_id)
        nonfav = sum(1 for c in cats if c.get("type") == cat_type and not c.get("on_adventure") and not c.get("favorite"))
        if nonfav > 0:
            return nonfav
        # If DB counters indicate the user has cats but instance store is empty for this type,
        # create missing instances immediately so UI/ATM can operate without requiring manual inspect.
        # aggregated DB count (best-effort read). Profile may be an ORM object
        # accessed via mapping-style or attribute-style; try both.
        db_total = 0
        try:
            db_total = int(profile[f"cat_{cat_type}"] or 0)
        except Exception:
            try:
                db_total = int(getattr(profile, f"cat_{cat_type}", 0) or 0)
            except Exception:
                db_total = 0
        # count all instances of this type in JSON (including favourites/on_adventure)
        inst_total = sum(1 for c in cats if c.get("type") == cat_type)
        if db_total > inst_total:
            missing = db_total - inst_total
            # safeguard: don't create absurd amounts in one go
            if missing > 0 and missing <= 1000:
                try:
                    _create_instances_only(profile.guild_id, profile.user_id, cat_type, missing)
                    # reload cats and recompute nonfav
                    cats = get_user_cats(profile.guild_id, profile.user_id)
                    nonfav = sum(1 for c in cats if c.get("type") == cat_type and not c.get("on_adventure") and not c.get("favorite"))
                    if nonfav > 0:
                        return nonfav
                except Exception:
                    pass
    except Exception:
        # if instance storage fails, fall back to aggregated counters below
        pass

    # Fallback to aggregated profile counters
    try:
        total = int(profile[f"cat_{cat_type}"] or 0)
    except Exception:
        total = 0
    if total <= 0:
        return 0

    # exclude one if a cat of that type is currently on adventure
    user_adv = active_adventures.get(str(profile.user_id))
    if user_adv and user_adv.get("cat") == cat_type:
        return max(0, total - 1)
    return total

async def cat_command_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    user = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)
    choices = []
    user_adv = active_adventures.get(str(interaction.user.id))
    adventuring_cat = user_adv["cat"] if user_adv else None
    
    for choice in cattypes:
        total = user[f"cat_{choice}"]
        if current.lower() in choice.lower() and total > 0:
            name = choice
            if choice == adventuring_cat:
                name += f" (x{total - 1}, 1 On Adventure)"
            else:
                name += f" (x{total})"
            choices.append(discord.app_commands.Choice(name=name, value=choice))
    return choices[:25]


async def lb_type_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    return [
        discord.app_commands.Choice(name=choice, value=choice)
        for choice in ["All"] + await cats_in_server(interaction.guild_id)
        if current.lower() in choice.lower()
    ][:25]


async def cats_in_server(guild_id):
    return [cat_type for cat_type in cattypes if (await Profile.count(f'guild_id = $1 AND "cat_{cat_type}" > 0 LIMIT 1', guild_id))]


# function to autocomplete cat_type choices for /gift, which shows only cats user has and how many of them they have
async def gift_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    user = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)
    actual_user = await User.get_or_create(user_id=interaction.user.id)
    choices = []
    for choice in cattypes:
        available = await get_available_cat_count(user, choice) 
        if current.lower() in choice.lower() and available > 0:
            choices.append(discord.app_commands.Choice(name=f"{choice} (x{available})", value=choice))
    if current.lower() in "rain" and actual_user.rain_minutes > 0:
        choices.append(discord.app_commands.Choice(name=f"Rain ({actual_user.rain_minutes} minutes)", value="rain"))
    for choice in pack_data:
        if user[f"pack_{choice['name'].lower()}"] > 0:
            pack_name = choice["name"]
            pack_amount = user[f"pack_{pack_name.lower()}"]
            choices.append(discord.app_commands.Choice(name=f"{pack_name} pack (x{pack_amount})", value=pack_name.lower()))
    return choices[:25]


# function to autocomplete achievement choice for /giveachievement, which also allows more than 25 options
async def ach_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    return [
        discord.app_commands.Choice(name=val["title"], value=key)
        for (key, val) in ach_list.items()
        if (alnum(current) in alnum(key) or alnum(current) in alnum(val["title"]))
    ][:25]


# converts string to lowercase alphanumeric characters only
def alnum(string):
    return "".join(item for item in string.lower() if item.isalnum())


async def spawn_cat(ch_id, localcat=None, force_spawn=None):
    try:
        channel = await Channel.get_or_none(channel_id=int(ch_id))
        if not channel:
            raise Exception
    except Exception:
        return
    if channel.cat or channel.yet_to_spawn > time.time() + 10:
        return

    if not localcat:
        localcat = random.choices(cattypes, weights=type_dict.values())[0]
    icon = get_emoji(localcat.lower() + "cat")
    file = discord.File(
        f"images/spawn/{localcat.lower()}_cat.png",
    )
    channeley = bot.get_partial_messageable(int(ch_id))

    appearstring = '{emoji} {type} cat has appeared! Type "cat" to catch it!' if not channel.appear else channel.appear

    if channel.cat:
        # its never too late to return
        return

    try:
        message_is_sus = await channeley.send(
            appearstring.replace("{emoji}", str(icon)).replace("{type}", localcat),
            file=file,
            allowed_mentions=discord.AllowedMentions.all(),
        )
    except discord.Forbidden:
        await channel.delete()
        return
    except discord.NotFound:
        await channel.delete()
        return
    except Exception:
        return

    channel.cat = message_is_sus.id
    channel.yet_to_spawn = 0
    channel.forcespawned = bool(force_spawn)
    channel.cattype = localcat
    await channel.save()


async def postpone_reminder(interaction):
    reminder_type = interaction.data["custom_id"]
    if reminder_type == "vote":
        user = await User.get_or_create(user_id=interaction.user.id)
        user.reminder_vote = int(time.time()) + 30 * 60
        await user.save()
    else:
        guild_id = reminder_type.split("_")[1]
        user = await Profile.get_or_create(guild_id=int(guild_id), user_id=interaction.user.id)
        if reminder_type.startswith("catch"):
            user.reminder_catch = int(time.time()) + 30 * 60
        else:
            user.reminder_misc = int(time.time()) + 30 * 60
        await user.save()
    await interaction.response.send_message(f"ok, i will remind you <t:{int(time.time()) + 30 * 60}:R>", ephemeral=True)


# a loop for various maintaince which is ran every 5 minutes
async def maintaince_loop():
    global pointlaugh_ratelimit, reactions_ratelimit, last_loop_time, loop_count, catchcooldown, fakecooldown, temp_belated_storage, temp_cookie_storage, last_random_rain_time, active_adventures
    pointlaugh_ratelimit = {}
    reactions_ratelimit = {}
    catchcooldown = {}
    fakecooldown = {}
    await bot.change_presence(activity=discord.CustomActivity(name=f"Catting in {len(bot.guilds):,} servers"))

    # update cookies
    temp_temp_cookie_storage = temp_cookie_storage.copy()
    cookie_updates = []
    for cookie_id, cookies in temp_temp_cookie_storage.items():
        p = await Profile.get_or_create(guild_id=cookie_id[0], user_id=cookie_id[1])
        p.cookies = cookies
        cookie_updates.append(p)
    if cookie_updates:
        await Profile.bulk_update(cookie_updates, "cookies")
    temp_cookie_storage = {}

    # temp_belated_storage cleanup
    # clean up anything older than 1 minute
    baseflake = discord.utils.time_snowflake(datetime.datetime.utcnow() - datetime.timedelta(minutes=1))
    for id in temp_belated_storage.copy().keys():
        if id < baseflake:
            del temp_belated_storage[id]

    if config.TOP_GG_TOKEN and (not config.MIN_SERVER_SEND or len(bot.guilds) > config.MIN_SERVER_SEND):
        async with aiohttp.ClientSession() as session:
            # send server count to top.gg
            try:
                r = await session.post(
                    f"https://top.gg/api/bots/{bot.user.id}/stats",
                    headers={"Authorization": config.TOP_GG_TOKEN},
                    json={
                        "server_count": len(bot.guilds),
                    },
                )
                r.close()
            except Exception:
                print("Posting to top.gg failed.")

    # revive dead catch loops
    async for channel in Channel.limit(["channel_id"], "yet_to_spawn < $1 AND cat = 0", time.time(), refetch=False):
        await spawn_cat(str(channel.channel_id))
        await asyncio.sleep(0.1)

    # Process any completed adventures
    try:
        finished = []
        now = time.time()
        for user_id_str, adv in list(active_adventures.items()):
            if adv.get("end_time", 0) <= now:
                finished.append((int(user_id_str), adv))

        for user_id, adv in finished:
            try:
                # fetch profile and global user
                guild_id = adv.get("guild_id")
                channel_id = adv.get("channel_id")
                cat_sent = adv.get("cat")
                channel_obj = bot.get_channel(channel_id) if channel_id else None

                profile = None
                if guild_id:
                    try:
                        profile = await Profile.get_or_create(guild_id=guild_id, user_id=user_id)
                    except Exception:
                        profile = None

                global_user = await User.get_or_create(user_id=user_id)

                # Choose reward
                roll = random.random()
                reward_text = ""
                embed = discord.Embed(title="Adventure Complete!", color=Colors.green)

                # compute reward scaling based on cat rarity/value
                try:
                    base_value = type_dict.get(cat_sent, 100)
                except Exception:
                    base_value = 100
                rarity_factor = 1000.0 / float(base_value)
                # normalize multiplier into a reasonable band
                multiplier = max(0.5, min(5.0, rarity_factor / 10.0))

                # If this adventure used a specific instance, factor its bond into rewards
                inst = None
                instance_id = adv.get("instance_id")
                if instance_id:
                    try:
                        user_cats = get_user_cats(guild_id, user_id)
                        for c in user_cats:
                            if c.get("id") == instance_id:
                                inst = c
                                break
                    except Exception:
                        inst = None
                if inst:
                    try:
                        bond = inst.get("bond", 0)
                        # apply bond as a multiplier: +1% per bond point (bond 100 -> +100%)
                        multiplier = multiplier * (1 + (bond / 100.0))
                    except Exception:
                        pass

                # Load active buffs (luck/xp) for this user so we can bias adventure rewards
                try:
                    buffs = get_active_buffs(guild_id or 0, user_id)
                    luck_mult = float(buffs.get("luck", 0)) if buffs else 0
                except Exception:
                    luck_mult = 0

                # Rare lucky reward
                # base jackpot probability ~ 1/500; scale up slightly with luck_mult
                base_jackpot_prob = 1.0 / 500.0
                if random.random() < base_jackpot_prob * (1 + luck_mult):
                    # jackpot: give a legendary cat and 60 rain minutes
                    rare_cat = random.choice([c for c in cattypes if c in ["Legendary", "Mythic", "Divine"]])
                    if profile:
                        # award the rare cat as an instance
                        try:
                            await add_cat_instances(profile, rare_cat, 1)
                        except Exception:
                            try:
                                profile[f"cat_{rare_cat}"] += 1
                                await profile.save()
                            except Exception:
                                pass
                        # restore the adventuring instance if present
                        if inst:
                            try:
                                inst["on_adventure"] = False
                                save_user_cats(guild_id, user_id, user_cats)
                            except Exception:
                                pass
                        else:
                            try:
                                profile[f"cat_{cat_sent}"] += 1
                                await profile.save()
                            except Exception:
                                pass
                    # award extra rain scaled by luck
                    minutes_awarded = int(60 * multiplier * (1 + luck_mult))
                    try:
                        if profile:
                            profile.rain_minutes = (profile.rain_minutes or 0) + minutes_awarded
                            await profile.save()
                        else:
                            global_user.rain_minutes = (global_user.rain_minutes or 0) + minutes_awarded
                            await global_user.save()
                    except Exception:
                        # fallback to global user
                        try:
                            global_user.rain_minutes = (global_user.rain_minutes or 0) + minutes_awarded
                            await global_user.save()
                        except Exception:
                            pass
                    reward_text = f"🌟 Your {cat_sent} returned with a **{rare_cat}** cat and brought **{minutes_awarded}** rain minutes!"
                    embed.description = reward_text
                elif roll < 0.45:
                    # Battlepass XP reward (scaled)
                    base_xp = random.randint(100, 500)
                    # apply XP buff if present
                    xp = max(1, int(base_xp * multiplier))
                    try:
                        buffs = get_active_buffs(guild_id or 0, user_id)
                        xp_buff = float(buffs.get("xp", 0)) if buffs else 0
                        if xp_buff:
                            xp = max(1, int(xp * (1 + xp_buff)))
                    except Exception:
                        pass
                    level_embeds = []
                    level_complete = False
                    if profile:
                        old_xp = profile.progress or 0
                        current_xp = old_xp + xp

                        # Determine current level data
                        if profile.battlepass >= len(battle["seasons"][str(profile.season)]):
                            level_data = {"xp": 1500, "reward": "Stone", "amount": 1}
                        else:
                            level_data = battle["seasons"][str(profile.season)][profile.battlepass]

                        # Handle level ups and award rewards similar to progress()
                        if current_xp >= level_data["xp"]:
                            xp_progress = current_xp
                            while xp_progress >= level_data["xp"]:
                                # award this level's reward
                                active_level_data = level_data
                                profile.battlepass += 1
                                xp_progress -= active_level_data["xp"]

                                # Apply reward (profile-level packs/cats; global_user holds rain minutes)
                                try:
                                    if active_level_data["reward"] == "Rain":
                                        global_user.rain_minutes += active_level_data["amount"]
                                        await global_user.save()
                                    elif active_level_data["reward"] in [p["name"] for p in pack_data]:
                                        pack_name = active_level_data["reward"]
                                        profile[f"pack_{pack_name.lower()}"] += active_level_data["amount"]
                                    elif active_level_data["reward"] in cattypes:
                                        profile[f"cat_{active_level_data["reward"]}"] += active_level_data["amount"]
                                except Exception:
                                    pass

                                # Build a small embed announcing the level up
                                try:
                                    if active_level_data["reward"] == "Rain":
                                        description = f"You got ☔ {active_level_data['amount']}m of Rain"
                                    elif active_level_data["reward"] in cattypes:
                                        description = f"You got {get_emoji(active_level_data['reward'].lower() + 'cat')} {active_level_data['amount']} {active_level_data['reward']}!"
                                    else:
                                        description = f"You got a {get_emoji(active_level_data['reward'].lower() + 'pack')} {active_level_data['reward']} pack! Do /packs to open it!"
                                    title = f"Level {profile.battlepass} Complete!"
                                    embed_level_up = discord.Embed(title=title, description=description, color=Colors.yellow)
                                    level_embeds.append(embed_level_up)
                                except Exception:
                                    pass

                                # advance to the next level data
                                if profile.battlepass >= len(battle["seasons"][str(profile.season)]):
                                    level_data = {"xp": 1500, "reward": "Stone", "amount": 1}
                                else:
                                    level_data = battle["seasons"][str(profile.season)][profile.battlepass]

                                level_complete = True

                            profile.progress = xp_progress
                        else:
                            profile.progress = current_xp

                        # persist profile changes (cats/packs/progress/levels)
                        try:
                            await profile.save()
                        except Exception:
                            pass

                    reward_text = f"⚔️ Your {cat_sent} trained hard and brought back **{xp}** battlepass XP!"
                    if level_complete:
                        reward_text += f"\n🎉 You leveled up to level {profile.battlepass}!"
                    embed.description = reward_text
                elif roll < 0.9:
                    # Cats reward (scaled amount and possibly better cats)
                    base_amount = random.randint(1, 3)
                    amount = max(1, int(base_amount * multiplier))
                    # apply luck to increase the number of cats returned
                    try:
                        amount = max(1, int(amount * (1 + luck_mult)))
                    except Exception:
                        pass
                    amount = min(amount, 10)
                    # choose a cat type biased by type_dict
                    cat_type = random.choices(cattypes, weights=type_dict.values())[0]
                    if profile:
                        # award cats as instances
                        try:
                            await add_cat_instances(profile, cat_type, amount)
                        except Exception:
                            try:
                                profile[f"cat_{cat_type}"] += amount
                                await profile.save()
                            except Exception:
                                pass
                        # restore the adventuring instance if present
                        if inst:
                            try:
                                inst["on_adventure"] = False
                                save_user_cats(guild_id, user_id, user_cats)
                            except Exception:
                                pass
                        else:
                            try:
                                profile[f"cat_{cat_sent}"] += 1
                                await profile.save()
                            except Exception:
                                pass
                    reward_text = f"🎁 Your {cat_sent} returned with **{amount}x {cat_type}** cat(s)!"
                    embed.description = reward_text
                elif roll < 0.95:
                    # Kibble reward (small, scaled)
                    kibble_amt = max(1, int(round(10 * multiplier * random.random())))
                    # apply luck to kibble amount
                    try:
                        kibble_amt = int(round(kibble_amt * (1 + luck_mult)))
                    except Exception:
                        pass
                    if profile:
                        try:
                            profile.kibble += kibble_amt
                            await profile.save()
                        except Exception:
                            pass
                        # restore adventuring instance if present
                        if inst:
                            try:
                                inst["on_adventure"] = False
                                save_user_cats(guild_id, user_id, user_cats)
                            except Exception:
                                pass
                        else:
                            try:
                                profile[f"cat_{cat_sent}"] += 1
                                await profile.save()
                            except Exception:
                                pass
                    reward_text = f"🥣 Your {cat_sent} returned with **{kibble_amt}** Kibble!"
                    embed.description = reward_text
                else:
                    # Rain minutes (scaled)
                    base_minutes = random.randint(5, 30)
                    # apply luck to rain minutes as well
                    minutes = max(1, int(base_minutes * multiplier * (1 + luck_mult)))
                    minutes_awarded = max(1, int(base_minutes * multiplier * (1 + luck_mult)))
                    try:
                        if profile:
                            profile.rain_minutes = (profile.rain_minutes or 0) + minutes_awarded
                            await profile.save()
                        else:
                            global_user.rain_minutes = (global_user.rain_minutes or 0) + minutes_awarded
                            await global_user.save()
                    except Exception:
                        try:
                            global_user.rain_minutes = (global_user.rain_minutes or 0) + minutes_awarded
                            await global_user.save()
                        except Exception:
                            pass
                    # restore adventuring instance if present
                    if inst:
                        try:
                            inst["on_adventure"] = False
                            save_user_cats(guild_id, user_id, user_cats)
                        except Exception:
                            pass
                    else:
                        try:
                            profile[f"cat_{cat_sent}"] += 1
                            await profile.save()
                        except Exception:
                            pass
                    reward_text = f"☔ Your {cat_sent} attracted **{minutes}** minutes of Cat Rain!"
                    embed.description = reward_text

                # send notification to channel if possible, else DM the user
                try:
                    if channel_obj and channel_obj.permissions_for(bot.user).send_messages:
                        await channel_obj.send(f"<@{user_id}> {reward_text}", embed=embed)
                    else:
                        person = await bot.fetch_user(user_id)
                        await person.send(reward_text, embed=embed)
                except Exception:
                    try:
                        person = await bot.fetch_user(user_id)
                        await person.send(reward_text, embed=embed)
                    except Exception:
                        pass

                # increase bond slightly on successful return and ensure instance no longer marked on adventure
                try:
                    if inst:
                        inc = random.randint(1, 3)
                        inst["bond"] = min(100, inst.get("bond", 0) + inc)
                        inst["on_adventure"] = False
                        save_user_cats(guild_id, user_id, user_cats)
                except Exception:
                    pass

            except Exception:
                pass
            # remove from active adventures and persist
            try:
                del active_adventures[str(user_id)]
            except KeyError:
                pass
        # persist adventures file if any changes
        try:
            os.makedirs(os.path.dirname(ADVENTURES_PATH), exist_ok=True)
            with open(ADVENTURES_PATH, "w", encoding="utf-8") as f:
                json.dump(active_adventures, f)
        except Exception:
            pass
    except Exception:
        pass

    # THIS IS CONSENTUAL AND TURNED OFF BY DEFAULT DONT BAN ME
    #
    # i wont go into the details of this because its a complicated mess which took me like solid 30 minutes of planning
    #
    # vote reminders
    proccessed_users = []
    async for user in User.limit(
        ["user_id", "reminder_vote", "vote_streak"],
        "vote_time_topgg != 0 AND vote_time_topgg + 43200 < $1 AND reminder_vote != 0 AND reminder_vote < $1",
        time.time(),
    ):
        if not await Profile.count("user_id = $1 AND reminders_enabled = true LIMIT 1", user.user_id):
            continue
        await asyncio.sleep(0.1)

        view = View(timeout=VIEW_TIMEOUT)
        button = Button(
            emoji=get_emoji("topgg"),
            label=random.choice(vote_button_texts),
            url="https://top.gg/bot/1387305159264309399/vote",
        )
        view.add_item(button)

        button = Button(label="Postpone", custom_id="vote")
        button.callback = postpone_reminder
        view.add_item(button)

        try:
            user_dm = await bot.fetch_user(user.user_id)
            await user_dm.send("You can vote now!" if user.vote_streak < 10 else f"Vote now to keep your {user.vote_streak} streak going!", view=view)
        except Exception:
            pass
        # no repeat reminers for now
        user.reminder_vote = 0
        proccessed_users.append(user)

    await User.bulk_update(proccessed_users, "reminder_vote")

    # i know the next two are similiar enough to be merged but its currently dec 30 and i cant be bothered
    # catch reminders
    proccessed_users = []
    async for user in Profile.limit(
        ["id"],
        "(reminders_enabled = true AND reminder_catch != 0) AND ((catch_cooldown != 0 AND catch_cooldown + 43200 < $1) OR (reminder_catch > 1 AND reminder_catch < $1))",
        time.time(),
    ):
        await asyncio.sleep(0.1)

        await refresh_quests(user)
        await user.refresh_from_db()

        quest_data = battle["quests"]["catch"][user.catch_quest]

        embed = discord.Embed(
            title=f"{get_emoji(quest_data['emoji'])} {quest_data['title']}",
            description=f"Reward: **{user.catch_reward}** XP",
            color=Colors.green,
        )

        view = View(timeout=VIEW_TIMEOUT)
        button = Button(label="Postpone", custom_id=f"catch_{user.guild_id}")
        button.callback = postpone_reminder
        view.add_item(button)

        guild = bot.get_guild(user.guild_id)
        if not guild:
            guild_name = "a server"
        else:
            guild_name = guild.name

        try:
            user_dm = await bot.fetch_user(user.user_id)
            await user_dm.send(f"A new quest is available in {guild_name}!", embed=embed, view=view)
        except Exception:
            pass
        user.reminder_catch = 0
        proccessed_users.append(user)

    if proccessed_users:
        await Profile.bulk_update(proccessed_users, "reminder_catch")

    # misc reminders
    proccessed_users = []
    async for user in Profile.limit(
        ["id"],
        "(reminders_enabled = true AND reminder_misc != 0) AND ((misc_cooldown != 0 AND misc_cooldown + 43200 < $1) OR (reminder_misc > 1 AND reminder_misc < $1))",
        time.time(),
    ):
        await asyncio.sleep(0.1)

        await refresh_quests(user)
        await user.refresh_from_db()

        quest_data = battle.get("quests", {}).get("misc", {}).get(user.misc_quest)
        if not quest_data:
            # user's saved misc quest no longer exists in config (e.g. removed quest). Reset and skip.
            try:
                user.misc_quest = ""
                user.misc_reward = 0
                await user.save()
            except Exception:
                pass
            continue

        embed = discord.Embed(
            title=f"{get_emoji(quest_data['emoji'])} {quest_data['title']}",
            description=f"Reward: **{user.misc_reward}** XP",
            color=Colors.green,
        )

        view = View(timeout=VIEW_TIMEOUT)
        button = Button(label="Postpone", custom_id=f"misc_{user.guild_id}")
        button.callback = postpone_reminder
        view.add_item(button)

        guild = bot.get_guild(user.guild_id)
        if not guild:
            guild_name = "a server"
        else:
            guild_name = guild.name

        try:
            user_dm = await bot.fetch_user(user.user_id)
            await user_dm.send(f"A new quest is available in {guild_name}!", embed=embed, view=view)
        except Exception:
            pass
        user.reminder_misc = 0
        proccessed_users.append(user)

    if proccessed_users:
        await Profile.bulk_update(proccessed_users, "reminder_misc")

    # manual reminders
    async for reminder in Reminder.filter("time < $1", time.time()):
        try:
            user = await bot.fetch_user(reminder.user_id)
            await user.send(reminder.text)
            await asyncio.sleep(0.5)
        except Exception:
            pass
        await reminder.delete()

    # db backups
    if config.BACKUP_ID:
        backupchannel = bot.get_channel(config.BACKUP_ID)
        if not isinstance(
            backupchannel,
            Union[
                discord.TextChannel,
                discord.StageChannel,
                discord.VoiceChannel,
                discord.Thread,
            ],
        ):
            return

        if loop_count % 10 == 0:
            backup_file = "/root/backup.dump"
            try:
                # delete the previous backup file
                os.remove(backup_file)
            except Exception:
                pass

            try:
                process = await asyncio.create_subprocess_shell(f"PGPASSWORD={config.DB_PASS} pg_dump -U cat_bot -Fc -Z 9 -f {backup_file} cat_bot")
                await process.wait()
                await backupchannel.send(f"In {len(bot.guilds)} servers, loop {loop_count}.", file=discord.File(backup_file))
            except Exception as e:
                print(f"Error during backup: {e}")
        else:
            await backupchannel.send(f"In {len(bot.guilds)} servers, loop {loop_count}.")

    loop_count += 1

    # Once-per-day random cat rain
    try:
        # 86400 seconds = 24 hours
        if time.time() > last_random_rain_time + 86400:
            candidates = []
            # select channels that are currently not raining and have no active cat
            async for ch in Channel.limit(["channel_id"], "cat_rains = 0 AND cat = 0", refetch=False):
                try:
                    channel_obj = bot.get_channel(int(ch.channel_id))
                    if not channel_obj:
                        continue
                    perms = channel_obj.permissions_for(bot.user)
                    # require basic send/view perms
                    if not (perms.view_channel and perms.send_messages and perms.attach_files):
                        continue
                    candidates.append(int(ch.channel_id))
                except Exception:
                    continue

            if candidates:
                chosen = random.choice(candidates)
                channel_db = await Channel.get_or_none(channel_id=chosen)
                if channel_db:
                    rain_length = 5  # minutes
                    channel_db.cat_rains = time.time() + (rain_length * 60)
                    channel_db.yet_to_spawn = 0
                    await channel_db.save()
                    # spawn initial cat immediately
                    await spawn_cat(str(chosen))
                    last_random_rain_time = time.time()
                    try:
                        notify_ch = bot.get_channel(config.RAIN_CHANNEL_ID)
                        if notify_ch:
                            await notify_ch.send(f"🌧️ Random Cat Rain started in <#{chosen}> for {rain_length} minutes!")
                    except Exception:
                        pass
    except Exception:
        # Never crash maintenance loop because of random rain
        pass


# fetch app emojis early
async def on_connect():
    global emojis
    emojis = {emoji.name: str(emoji) for emoji in await bot.fetch_application_emojis()}


# some code which is run when bot is started
async def on_ready():
    global OWNER_ID, on_ready_debounce, gen_credits, emojis
    if on_ready_debounce:
        return
    on_ready_debounce = True
    print("cat is now online")
    # flush any pending logs that were recorded before bot was ready
    try:
        for msg in list(_pending_discord_logs):
            try:
                asyncio.create_task(_post_log_to_discord(msg))
            except Exception:
                pass
        _pending_discord_logs.clear()
    except Exception:
        pass
    
    # Start the daily random rain task
    bot.loop.create_task(schedule_daily_rain())

async def schedule_daily_rain():
    while True:
        # Wait until next day
        now = datetime.datetime.now()
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
        seconds_until_tomorrow = (tomorrow - now).total_seconds()
        await asyncio.sleep(seconds_until_tomorrow)
        
        try:
            # Pick a random time during the next day
            random_seconds = random.randint(0, 24 * 60 * 60)  # Random time in the day
            await asyncio.sleep(random_seconds)
            
            # Get a random channel that has had cat activity
            channels = await Channel.collect(filter="cat > 0")
            if not channels:
                continue
                
            channel = random.choice(channels)
            discord_channel = bot.get_channel(channel.channel_id)
            if not discord_channel:
                continue
            
            # Start a 5-minute rain
            await discord_channel.send("☔ A mysterious rain has started! Cats will spawn frequently for the next 5 minutes!")
            
            # Do the rain spawns
            for _ in range(30):  # About 30 spawns over 5 minutes
                try:
                    if random.random() < 0.8:  # 80% chance each cycle
                        await spawn_cat(discord_channel, force_spawn=True)
                except Exception as e:
                    print(f"Error in daily rain spawn: {e}")
                    continue
                    
                await asyncio.sleep(10)  # 10 second delay between spawns
                
            await discord_channel.send("The rain has stopped!")
            
        except Exception as e:
            print(f"Error in daily rain scheduler: {e}")
    emojis = {emoji.name: str(emoji) for emoji in await bot.fetch_application_emojis()}
    appinfo = bot.application
    if appinfo.team and appinfo.team.owner_id:
        OWNER_ID = appinfo.team.owner_id
    else:
        OWNER_ID = appinfo.owner.id

    testers = [
        712639066373619754,
        902862104971849769,
        709374062237057074,
        520293520418930690,
        1004128541853618197,
        839458185059500032,
    ]

    # fetch github contributors
    url = "https://api.github.com/repos/milenakos/cat-bot/contributors"
    contributors = []

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers={"User-Agent": "CatBot/1.0 https://github.com/milenakos/cat-bot"}) as response:
            if response.status == 200:
                data = await response.json()
                for contributor in data:
                    login = contributor["login"].replace("_", r"\_")
                    if login not in ["milenakos", "ImgBotApp"]:
                        contributors.append(login)
            else:
                print(f"Error: {response.status} - {await response.text()}")

    # fetch testers
    tester_users = []
    try:
        for i in testers:
            user = await bot.fetch_user(i)
            tester_users.append(user.name.replace("_", r"\_"))
    except Exception:
        # death
        pass

    gen_credits = "\n".join(
        [
            "Made by **Lia Milenakos**",
            "With contributions from **" + ", ".join(contributors) + "**",
            "Original Cat Image: **pathologicals**",
            "APIs: **catfact.ninja, weilbyte.dev, wordnik.com, thecatapi.com**",
            "Open Source Projects: **[discord.py](https://github.com/Rapptz/discord.py), [asyncpg](https://github.com/MagicStack/asyncpg), [gateway-proxy](https://github.com/Gelbpunkt/gateway-proxy)**",
            "Art, suggestions, and a lot more: **TheTrashCell**",
            "Testers: **" + ", ".join(tester_users) + "**",
            "Enjoying the bot: **You <3**",
        ]
    )

    # load persisted adventures
    try:
        load_adventures()
    except Exception:
        pass


@bot.tree.command(description="Send one of your cats on an adventure for 3 hours")
@discord.app_commands.autocomplete(cat=cat_command_autocomplete)
async def adventure(interaction: discord.Interaction, cat: Optional[str] = None):
    """Send one of the user's cats on a 3-hour adventure. Rewards are granted when it returns.

    Parameters
    ----------
    cat: Optional[str]
        Which cat to send (case-insensitive). If omitted a random owned cat is chosen.
    """
    await interaction.response.defer()
    user_id = interaction.user.id

    # single active adventure per user
    if str(user_id) in active_adventures:
        adv = active_adventures[str(user_id)]
        end = adv.get("end_time")
        await interaction.followup.send(f"You already have an active adventure returning <t:{int(end)}:R>.")
        return

    if not interaction.guild:
        await interaction.followup.send("Adventures must be started from a server.")
        return

    profile = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=user_id)

    # find available cats (not on adventure)
    owned = []
    for c in cattypes:
        try:
            available = await get_available_cat_count(profile, c)
            if available > 0:
                owned.append(c)
        except Exception:
            continue

    if not owned:
        await interaction.followup.send("You don't have any cats to send on an adventure. Get some cats first!")
        return

    # choose cat: either user-specified or random
    chosen = None
    if cat:
        # match case-insensitive to known cat types
        for c in cattypes:
            if c.lower() == cat.lower():
                chosen = c
                break
        if not chosen:
            await interaction.followup.send("I couldn't find that cat type in your collection. Pick a valid cat type.")
            return
        if chosen not in owned:
            await interaction.followup.send(f"You don't own any {chosen} cats to send.")
            return
    else:
        chosen = random.choice(owned)
    duration = 3 * 3600  # 3 hours
    end_time = time.time() + duration

    # Pick a specific instance to send on the adventure and mark it as on_adventure
    instance_id = None
    try:
        user_cats = get_user_cats(interaction.guild.id, user_id)
        for c in user_cats:
            if c.get("type") == chosen and not c.get("on_adventure"):
                c["on_adventure"] = True
                instance_id = c.get("id")
                break
        if instance_id:
            save_user_cats(interaction.guild.id, user_id, user_cats)
    except Exception:
        instance_id = None

    active_adventures[str(user_id)] = {
        "user_id": user_id,
        "guild_id": interaction.guild.id,
        "channel_id": interaction.channel.id if interaction.channel else None,
        "cat": chosen,
        "instance_id": instance_id,
        "start_time": time.time(),
        "end_time": end_time,
    }
    save_adventures()

    embed = discord.Embed(title="Adventure Started!", color=Colors.yellow)
    embed.description = f"Your **{chosen}** has left on an adventure and will return <t:{int(end_time)}:R>. Good luck!\n*(Your cat will be marked as (On Adventure) in menus)*"
    await interaction.followup.send(f"<@{user_id}>", embed=embed)



@bot.tree.command(description="Show your active adventure (if any)")
async def adventures(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    user_id = interaction.user.id
    adv = active_adventures.get(str(user_id))
    if not adv:
        await interaction.followup.send("You have no active adventures right now.")
        return

    cat = adv.get("cat")
    start = adv.get("start_time")
    end = adv.get("end_time")
    channel_id = adv.get("channel_id")
    remaining = int(end - time.time()) if end else 0

    embed = discord.Embed(title="Active Adventure", color=Colors.yellow)
    embed.add_field(name="Cat", value=str(cat or "Unknown"), inline=True)
    embed.add_field(name="Returns In", value=f"<t:{int(end)}:R>" if end else "Unknown", inline=True)
    if channel_id:
        embed.set_footer(text=f"Started in channel {channel_id}")
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="adventure_list", description="Admin: list all active adventures")
async def adventure_list(interaction: discord.Interaction):
    # allow only guild admins or bot owner
    try:
        if interaction.user.id != OWNER_ID and not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("You don't have permission to run this command.", ephemeral=True)
            return
    except Exception:
        # fallback allow owner
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("You don't have permission to run this command.", ephemeral=True)
            return

    await interaction.response.defer(ephemeral=True)
    if not active_adventures:
        await interaction.followup.send("No active adventures.")
        return

    embed = discord.Embed(title="Active Adventures", color=Colors.yellow)
    for uid_str, adv in list(active_adventures.items())[:30]:
        uid = int(uid_str)
        cat = adv.get("cat")
        guild_id = adv.get("guild_id")
        channel_id = adv.get("channel_id")
        end = adv.get("end_time")
        owner = None
        try:
            owner = await bot.fetch_user(uid)
            owner_text = owner.name
        except Exception:
            owner_text = str(uid)

        location = f"<#{channel_id}>" if channel_id else f"Guild {guild_id}"
        embed.add_field(name=f"{owner_text}", value=f"Cat: {cat}\nReturns: <t:{int(end)}:R>\nLoc: {location}", inline=False)

    await interaction.followup.send(embed=embed)


# this is all the code which is ran on every message sent
# a lot of it is for easter eggs and achievements
async def on_message(message: discord.Message):
    global emojis, last_loop_time
    
    # Fast early returns before any processing
    if not bot.user or message.author.id == bot.user.id:
        return

    text = message.content.lower()  # Cache lowercase content
    
    # Only run maintenance check after fast returns
    if time.time() > last_loop_time + 300:
        last_loop_time = time.time()
        await maintaince_loop()

    if message.guild is None:
        if text.startswith("disable"):
            # disable reminders
            try:
                user = await Profile.get_or_create(guild_id=int(text.split(" ")[1]), user_id=message.author.id)
            except Exception:
                await message.channel.send("failed. check if your guild id is correct")
                return
            user.reminders_enabled = False
            await user.save()
            await message.channel.send("reminders disabled")
        elif text == "lol_i_have_dmed_the_cat_bot_and_got_an_ach":
            await message.channel.send('which part of "send in server" was unclear?')
        else:
            await message.channel.send('good job! please send "lol_i_have_dmed_the_cat_bot_and_got_an_ach" in server to get your ach!')
        return

    perms = await fetch_perms(message)

    achs = [
        ["cat?", "startswith", "???"],
        ["catn", "exact", "catn"],
        ["cat!coupon jr0f-pzka", "exact", "coupon_user"],
        ["pineapple", "exact", "pineapple"],
        ["cat!i_like_cat_website", "exact", "website_user"],
        ["cat!i_clicked_there", "exact", "click_here"],
        ["cat!lia_is_cute", "exact", "nerd"],
        ["i read help", "exact", "patient_reader"],
        [str(bot.user.id), "in", "who_ping"],
        ["lol_i_have_dmed_the_cat_bot_and_got_an_ach", "exact", "dm"],
        ["dog", "exact", "not_quite"],
        ["egril", "exact", "egril"],
        ["-.-. .- -", "exact", "morse_cat"],
        ["tac", "exact", "reverse"],
        ["joob", "exact", "joober"],
        ["cst", "exact", "cst"],
        ["cab", "exact", "cab"],
        ["cat!n4lltvuCOKe2iuDCmc6JsU7Jmg4vmFBj8G8l5xvoDHmCoIJMcxkeXZObR6HbIV6", "veryexact", "dataminer"],
    ]

    reactions = [
        ["v1;", "custom", "why_v1"],
        ["proglet", "custom", "professor_cat"],
        ["xnopyt", "custom", "vanish"],
        ["silly", "custom", "sillycat"],
        ["indev", "vanilla", "🐸"],
        ["bleh", "custom", "blepcat"],
        ["blep", "custom", "blepcat"],
    ]

    responses = [
        ["cat!sex", "exact", "..."],
        [
            "cellua good",
            "in",
            ".".join([str(random.randint(2, 254)) for _ in range(4)]),
        ],
        [
            "https://tenor.com/view/this-cat-i-have-hired-this-cat-to-stare-at-you-hired-cat-cat-stare-gif-26392360",
            "exact",
            "https://tenor.com/view/cat-staring-cat-gif-16983064494644320763",
        ],
    ]

    # Unfunny achievement: exact message "67"
    try:
        if text.strip() == "67":
            await achemb(message, "unfunny", "send")
    except Exception:
        # never crash on achievement checks
        pass

    # here are some automation hooks for giving out purchases and similiar
    if config.RAIN_CHANNEL_ID and message.channel.id == config.RAIN_CHANNEL_ID and text.lower().startswith("cat!rain"):
        things = text.split(" ")
        user = await User.get_or_create(user_id=int(things[1]))
        if not user.rain_minutes:
            user.rain_minutes = 0

        if things[2] == "short":
            user.rain_minutes += 2
        elif things[2] == "medium":
            user.rain_minutes += 0
        elif things[2] == "long":
            user.rain_minutes += 0
        else:
            user.rain_minutes += int(things[2])
        user.premium = True
        await user.save()

        # try to dm the user the thanks msg
        try:
            person = await bot.fetch_user(int(things[1]))
            await person.send(
                f"**You have recieved {things[2]} minutes of Cat Rain!** ☔\n\nThanks for your support!\nYou can start a rain with `/rain`. By buying you also get access to `/editprofile` command as well as a role in [our Discord server](<https://discord.gg/staring>), where you can also get a decorative custom cat!\n\nEnjoy your goods!"
            )
        except Exception:
            pass

        return

    react_count = 0

    # :staring_cat: reaction on "bullshit"
    if " " not in text and len(text) > 7 and text.isalnum():
        s = text.lower()
        total_vow = 0
        total_illegal = 0
        for i in "aeuio":
            total_vow += s.count(i)
        illegal = [
            "bk",
            "fq",
            "jc",
            "jt",
            "mj",
            "qh",
            "qx",
            "vj",
            "wz",
            "zh",
            "bq",
            "fv",
            "jd",
            "jv",
            "mq",
            "qj",
            "qy",
            "vk",
            "xb",
            "zj",
            "bx",
            "fx",
            "jf",
            "jw",
            "mx",
            "qk",
            "qz",
            "vm",
            "xg",
            "zn",
            "cb",
            "fz",
            "jg",
            "jx",
            "mz",
            "ql",
            "sx",
            "vn",
            "xj",
            "zq",
            "cf",
            "gq",
            "jh",
            "jy",
            "pq",
            "qm",
            "sz",
            "vp",
            "xk",
            "zr",
            "cg",
            "gv",
            "jk",
            "jz",
            "pv",
            "qn",
            "tq",
            "vq",
            "xv",
            "zs",
            "cj",
            "gx",
            "jl",
            "kq",
            "px",
            "qo",
            "tx",
            "vt",
            "xz",
            "zx",
            "cp",
            "hk",
            "jm",
            "kv",
            "qb",
            "qp",
            "vb",
            "vw",
            "yq",
            "cv",
            "hv",
            "jn",
            "kx",
            "qc",
            "qr",
            "vc",
            "vx",
            "yv",
            "cw",
            "hx",
            "jp",
            "kz",
            "qd",
            "qs",
            "vd",
            "vz",
            "yz",
            "cx",
            "hz",
            "jq",
            "lq",
            "qe",
            "qt",
            "vf",
            "wq",
            "zb",
            "dx",
            "iy",
            "jr",
            "lx",
            "qf",
            "qv",
            "vg",
            "wv",
            "zc",
            "fk",
            "jb",
            "js",
            "mg",
            "qg",
            "qw",
            "vh",
            "wx",
            "zg",
        ]
        for j in illegal:
            if j in s:
                total_illegal += 1
        vow_perc = 0
        const_perc = len(text)
        if total_vow != 0:
            vow_perc = len(text) / total_vow
        if total_vow != len(text):
            const_perc = len(text) / (len(text) - total_vow)
        if (vow_perc <= 3 and const_perc >= 6) or total_illegal >= 2:
            try:
                if perms.add_reactions:
                    await message.add_reaction(get_emoji("staring_cat"))
                    react_count += 1
            except Exception:
                pass

    try:
        if perms.send_messages and (not message.thread or perms.send_messages_in_threads):
            if "robotop" in message.author.name.lower() and "i rate **cat" in message.content.lower():
                icon = str(get_emoji("no_ach"))
                await message.reply("**RoboTop**, I rate **you** 0 cats " + icon * 5)

            if "leafbot" in message.author.name.lower() and "hmm... i would rate cat" in message.content.lower():
                icon = str(get_emoji("no_ach")) + " "
                await message.reply("Hmm... I would rate you **0 cats**! " + icon * 5)
    except Exception:
        pass

    if message.author.bot or message.webhook_id is not None:
        return

    for ach in achs:
        if (
            (ach[1] == "startswith" and text.lower().startswith(ach[0]))
            or (ach[1] == "re" and re.search(ach[0], text.lower()))
            or (ach[1] == "exact" and ach[0] == text.lower())
            or (ach[1] == "veryexact" and ach[0] == text)
            or (ach[1] == "in" and ach[0] in text.lower())
        ):
            await achemb(message, ach[2], "reply")

    if text.lower() in [
        "mace",
        "katu",
        "kot",
        "koshka",
        "macka",
        "gat",
        "gata",
        "kocka",
        "kat",
        "poes",
        "kass",
        "kissa",
        "chat",
        "chatte",
        "gato",
        "katze",
        "gata",
        "macska",
        "kottur",
        "gatto",
        "getta",
        "kakis",
        "kate",
        "qattus",
        "qattusa",
        "katt",
        "kit",
        "kishka",
        "cath",
        "qitta",
        "katu",
        "pisik",
        "biral",
        "kyaung",
        "mao",
        "pusa",
        "kata",
        "billi",
        "kucing",
        "neko",
        "bekku",
        "mysyq",
        "chhma",
        "goyangi",
        "pucha",
        "manjar",
        "muur",
        "biralo",
        "gorbeh",
        "punai",
        "pilli",
        "kedi",
        "mushuk",
        "meo",
        "demat",
        "nwamba",
        "jangwe",
        "adure",
        "katsi",
        "bisad,",
        "paka",
        "ikati",
        "ologbo",
        "wesa",
        "popoki",
        "piqtuq",
        "negeru",
        "poti",
        "mosi",
        "michi",
        "pusi",
        "oratii",
    ]:
        await achemb(message, "multilingual", "reply")

    if perms.add_reactions:
        for r in reactions:
            if r[0] in text.lower() and reactions_ratelimit.get(message.author.id, 0) < 20:
                if r[1] == "custom":
                    em = get_emoji(r[2])
                elif r[1] == "vanilla":
                    em = r[2]

                try:
                    await message.add_reaction(em)
                    react_count += 1
                    reactions_ratelimit[message.author.id] = reactions_ratelimit.get(message.author.id, 0) + 1
                except Exception:
                    pass

    if perms.send_messages and (not message.thread or perms.send_messages_in_threads):
        for resp in responses:
            if (
                (resp[1] == "startswith" and text.lower().startswith(resp[0]))
                or (resp[1] == "re" and re.search(resp[0], text.lower()))
                or (resp[1] == "exact" and resp[0] == text.lower())
                or (resp[1] == "in" and resp[0] in text.lower())
            ):
                try:
                    await message.reply(resp[2])
                except Exception:
                    pass

    try:
        if message.author in message.mentions and perms.add_reactions:
            await message.add_reaction(get_emoji("staring_cat"))
            react_count += 1
    except Exception:
        pass

    if react_count >= 3 and perms.add_reactions:
        await achemb(message, "silly", "send")

    if (":place_of_worship:" in text or "🛐" in text) and (":cat:" in text or ":staring_cat:" in text or "🐱" in text):
        await achemb(message, "worship", "reply")

    if text.lower() in ["testing testing 1 2 3", "cat!ach"]:
        try:
            if perms.send_messages and (not message.thread or perms.send_messages_in_threads):
                await message.reply("test success")
        except Exception:
            # test failure
            pass
        await achemb(message, "test_ach", "reply")

    if text.lower() == "please do not the cat":
        user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.author.id)
        user.cat_Fine -= 1
        await user.save()
        try:
            if perms.send_messages and (not message.thread or perms.send_messages_in_threads):
                personname = message.author.name.replace("_", "\\_")
                await message.reply(f"ok then\n{personname} lost 1 fine cat!!!1!\nYou now have {user.cat_Fine:,} cats of dat type!")
        except Exception:
            pass
        await achemb(message, "pleasedonotthecat", "reply")

    if text.lower() == "please do the cat":
        thing = discord.File("images/socialcredit.jpg", filename="socialcredit.jpg")
        try:
            if perms.send_messages and perms.attach_files and (not message.thread or perms.send_messages_in_threads):
                await message.reply(file=thing)
        except Exception:
            pass
        await achemb(message, "pleasedothecat", "reply")

    if text.lower() == "car":
        file = discord.File("images/car.png", filename="car.png")
        embed = discord.Embed(title="car!", color=Colors.brown).set_image(url="attachment://car.png")
        try:
            if perms.send_messages and perms.attach_files and (not message.thread or perms.send_messages_in_threads):
                await message.reply(file=file, embed=embed)
        except Exception:
            pass
        await achemb(message, "car", "reply")

    if text.lower() == "cart":
        file = discord.File("images/cart.png", filename="cart.png")
        embed = discord.Embed(title="cart!", color=Colors.brown).set_image(url="attachment://cart.png")
        try:
            if perms.send_messages and perms.attach_files and (not message.thread or perms.send_messages_in_threads):
                await message.reply(file=file, embed=embed)
        except Exception:
            pass

    try:
        if (
            ("sus" in text.lower() or "amog" in text.lower() or "among" in text.lower() or "impost" in text.lower() or "report" in text.lower())
            and (channel := await Channel.get_or_none(channel_id=message.channel.id))
            and channel.cattype == "Sus"
        ):
            await achemb(message, "sussy", "send")
    except Exception:
        pass

    # this is run whether someone says "cat" (very complex)
    if text.lower() == "cat":
        # Fast initial checks before any DB queries
        if message.channel.id in temp_catches_storage:
            return
            
        # Combine DB queries into one operation where possible
        user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.author.id)
        channel = await Channel.get_or_none(channel_id=message.channel.id)
        
        # Early return conditions
        if not channel or not channel.cat or channel.cat in temp_catches_storage or user.timeout > time.time():
            # laugh at this user but only if conditions are right
            # (except if rain is active, we dont have perms or channel isnt setupped, or we laughed way too much already)
            if (channel and channel.cat_rains < time.time() and 
                perms.add_reactions and 
                pointlaugh_ratelimit.get(message.channel.id, 0) < 10):
                try:
                    await message.add_reaction(get_emoji("pointlaugh"))
                    pointlaugh_ratelimit[message.channel.id] = pointlaugh_ratelimit.get(message.channel.id, 0) + 1
                except Exception:
                    pass

            # belated battlepass
            if message.channel.id in temp_belated_storage:
                belated = temp_belated_storage[message.channel.id]
                if (
                    channel
                    and "users" in belated
                    and "time" in belated
                    and channel.lastcatches + 3 > int(time.time())
                    and message.author.id not in belated["users"]
                ):
                    belated["users"].append(message.author.id)
                    temp_belated_storage[message.channel.id] = belated
                    await progress(message, user, "3cats", True)
                    if channel.cattype == "Fine":
                        await progress(message, user, "2fine", True)
                    if channel.cattype == "Good":
                        await progress(message, user, "good", True)
                    if belated.get("time", 10) + int(time.time()) - channel.lastcatches < 10:
                        await progress(message, user, "under10", True)
                    if random.randint(0, 1) == 0:
                        await progress(message, user, "even", True)
                    else:
                        await progress(message, user, "odd", True)
                    if channel.cattype and channel.cattype not in ["Fine", "Nice", "Good"]:
                        await progress(message, user, "rare+", True)
                    total_count = await Prism.count("guild_id = $1", message.guild.id)
                    user_count = await Prism.count("guild_id = $1 AND user_id = $2", message.guild.id, message.author.id)
                    global_boost = 0.06 * math.log(2 * total_count + 1)
                    prism_boost = global_boost + 0.03 * math.log(2 * user_count + 1)
                    if prism_boost > random.random():
                        await progress(message, user, "prism", True)
                    if user.catch_quest == "finenice":
                        # 0 none
                        # 1 fine
                        # 2 nice
                        # 3 both
                        if channel.cattype == "Fine" and user.catch_progress in [0, 2]:
                            await progress(message, user, "finenice", True)
                        elif channel.cattype == "Nice" and user.catch_progress in [0, 1]:
                            await progress(message, user, "finenice", True)
                            await progress(message, user, "finenice", True)
        else:
            pls_remove_me_later_k_thanks = channel.cat
            temp_catches_storage.append(channel.cat)
            times = [channel.spawn_times_min, channel.spawn_times_max]
            if channel.cat_rains != 0:
                if channel.cat_rains > time.time():
                    times = [1, 2]
                else:
                    temp_rains_storage.append(message.channel.id)
                    channel.cat_rains = 0
                    try:
                        if perms.send_messages and (not message.thread or perms.send_messages_in_threads):
                            # this is pretty but i want a delay lmao
                            # await asyncio.gather(*(message.channel.send("h") for _ in range(3)))
                            for _ in range(3):
                                await message.channel.send("# :bangbang: cat rain has ended")
                                await asyncio.sleep(0.2)
                    except Exception:
                        pass
            decided_time = random.uniform(times[0], times[1])
            if channel.yet_to_spawn < time.time():
                channel.yet_to_spawn = time.time() + decided_time + 10
            elif channel.cat_rains == 0:
                decided_time = 0
            try:
                current_time = message.created_at.timestamp()
                channel.lastcatches = current_time
                cat_temp = channel.cat
                channel.cat = 0
                try:
                    if channel.cattype != "":
                        catchtime = discord.utils.snowflake_time(cat_temp)
                        le_emoji = channel.cattype
                    elif perms.read_message_history:
                        var = await message.channel.fetch_message(cat_temp)
                        catchtime = var.created_at
                        catchcontents = var.content

                        partial_type = None
                        for v in allowedemojis:
                            if v in catchcontents:
                                partial_type = v
                                break

                        if not partial_type and "thetrashcellcat" in catchcontents:
                            partial_type = "trashcat"
                            le_emoji = "Trash"
                        else:
                            if not partial_type:
                                return

                            for i in cattypes:
                                if i.lower() in partial_type:
                                    le_emoji = i
                                    break
                    else:
                        raise Exception
                except Exception:
                    try:
                        if perms.send_messages and (not message.thread or perms.send_messages_in_threads):
                            await message.channel.send(f"oopsie poopsie i cant access the original message but {message.author.mention} *did* catch a cat rn")
                    except Exception:
                        pass
                    return

                send_target = message.channel
                try:
                    # some math to make time look cool
                    then = catchtime.timestamp()
                    time_caught = round(abs(current_time - then), 3)  # cry about it
                    if time_caught >= 1:
                        time_caught = round(time_caught, 2)

                    days, time_left = divmod(time_caught, 86400)
                    hours, time_left = divmod(time_left, 3600)
                    minutes, seconds = divmod(time_left, 60)

                    caught_time = ""
                    if days:
                        caught_time = caught_time + str(int(days)) + " days "
                    if hours:
                        caught_time = caught_time + str(int(hours)) + " hours "
                    if minutes:
                        caught_time = caught_time + str(int(minutes)) + " minutes "
                    if seconds:
                        pre_time = round(seconds, 3)
                        if pre_time % 1 == 0:
                            # replace .0 with .00 basically
                            pre_time = str(int(pre_time)) + ".00"
                        caught_time = caught_time + str(pre_time) + " seconds "
                    do_time = True
                    if not caught_time:
                        caught_time = "0.000 seconds (woah) "
                    if time_caught <= 0:
                        do_time = False
                except Exception:
                    # if some of the above explodes just give up
                    do_time = False
                    caught_time = "undefined amounts of time "

                try:
                    if time_caught >= 0:
                        temp_belated_storage[message.channel.id] = {"time": time_caught, "users": [message.author.id]}
                except Exception:
                    pass

                if channel.cat_rains + 10 > time.time() or message.channel.id in temp_rains_storage:
                    do_time = False

                suffix_string = ""
                silly_amount = 1

                # add blessings
                if random.randint(1, 100) == 69:
                    # woo we got blessed thats pretty cool
                    silly_amount *= 2

                    blesser = (await User.collect("blessings_enabled = true ORDER BY RANDOM() LIMIT 1"))[0]
                    blesser.cats_blessed += 1
                    await blesser.save()

                    if blesser.blessings_anonymous:
                        blesser_text = "💫 Anonymous Supporter"
                    else:
                        blesser_text = f"{blesser.emoji or '💫'} {(await bot.fetch_user(blesser.user_id)).name}"

                    suffix_string += f"\n{blesser_text} blessed your catch and it got doubled!"

                # calculate prism boost
                total_prisms = await Prism.collect("guild_id = $1", message.guild.id)
                user_prisms = await Prism.collect("guild_id = $1 AND user_id = $2", message.guild.id, message.author.id)
                global_boost = 0.06 * math.log(2 * len(total_prisms) + 1)
                user_boost = global_boost + 0.03 * math.log(2 * len(user_prisms) + 1)
                did_boost = False
                if user_boost > random.random():
                    # determine whodunnit
                    if random.uniform(0, user_boost) > global_boost:
                        # boost from our own prism
                        prism_which_boosted = random.choice(user_prisms)
                    else:
                        # boost from any prism
                        prism_which_boosted = random.choice(total_prisms)

                    if prism_which_boosted.user_id == message.author.id:
                        boost_applied_prism = "Your prism " + prism_which_boosted.name
                    else:
                        boost_applied_prism = f"<@{prism_which_boosted.user_id}>'s prism " + prism_which_boosted.name

                    did_boost = True
                    user.boosted_catches += 1
                    prism_which_boosted.catches_boosted += 1
                    await prism_which_boosted.save()
                    try:
                        le_old_emoji = le_emoji
                        le_emoji = cattypes[cattypes.index(le_emoji) + 1]
                        normal_bump = True
                    except IndexError:
                        # :SILENCE:
                        normal_bump = False
                        if not channel.forcespawned:
                            if channel.cat_rains > time.time():
                                await message.channel.send("# ‼️‼️ RAIN EXTENDED BY 10 MINUTES ‼️‼️")
                                await message.channel.send("# ‼️‼️ RAIN EXTENDED BY 10 MINUTES ‼️‼️")
                                await message.channel.send("# ‼️‼️ RAIN EXTENDED BY 10 MINUTES ‼️‼️")
                                channel.cat_rains += 606
                            else:
                                channel.cat_rains = time.time() + 606
                            channel.yet_to_spawn = 0
                            decided_time = 6

                    if normal_bump:
                        suffix_string += f"\n{get_emoji('prism')} {boost_applied_prism} boosted this catch from a {get_emoji(le_old_emoji.lower() + 'cat')} {le_old_emoji} cat!"
                    elif not channel.forcespawned:
                        suffix_string += f"\n{get_emoji('prism')} {boost_applied_prism} tried to boost this catch, but failed! A 10m rain will start!"

                icon = get_emoji(le_emoji.lower() + "cat")

                if user.cataine_active > time.time():
                    # cataine is active
                    silly_amount *= 2
                    suffix_string += "\n🧂 cataine worked! your catch got doubled!"
                    user.cataine_activations += 1

                elif user.cataine_active != 0:
                    # cataine ran out
                    user.cataine_active = 0
                    suffix_string += "\nyour cataine buff has expired. you know where to get a new one 😏"

                if random.randint(0, 7) == 0:
                    # shill rains
                    suffix_string += f"\n😺 International Cat Day Sale! -20% </rain:{RAIN_ID}>"
                if random.randint(0, 19) == 0:
                    # diplay a hint/fun fact
                    suffix_string += "\n💡 " + random.choice(hints)

                custom_cough_strings = {
                    "Corrupt": "{username} coought{type} c{emoji}at!!!!404!\nYou now BEEP {count} cats of dCORRUPTED!!\nthis fella wa- {time}!!!!",
                    "eGirl": "{username} cowought {emoji} {type} cat~~ ^^\nYou-u now *blushes* hawe {count} cats of dat tywe~!!!\nthis fella was <3 cought in {time}!!!!",
                    "Rickroll": "{username} cought {emoji} {type} cat!!!!1!\nYou will never give up {count} cats of dat type!!!\nYou wouldn't let them down even after {time}!!!!",
                    "Sus": "{username} cought {emoji} {type} cat!!!!1!\nYou have vented infront of {count} cats of dat type!!!\nthis sussy baka was cought in {time}!!!!",
                    "Professor": "{username} caught {emoji} {type} cat!\nThou now hast {count} cats of that type!\nThis fellow was caught 'i {time}!",
                    "8bit": "{username} c0ught {emoji} {type} cat!!!!1!\nY0u n0w h0ve {count} cats 0f dat type!!!\nth1s fe11a was c0ught 1n {time}!!!!",
                    "Reverse": "!!!!{time} in cought was fella this\n!!!type dat of cats {count} have now You\n!1!!!!cat {type} {emoji} cought {username}",
                }

                if channel.cought:
                    # custom spawn message
                    coughstring = channel.cought
                elif le_emoji in custom_cough_strings:
                    # custom type message
                    coughstring = custom_cough_strings[le_emoji]
                else:
                    # default
                    coughstring = "{username} cought {emoji} {type} cat!!!!1!\nYou now have {count} cats of dat type!!!\nthis fella was cought in {time}!!!!"

                view = None
                button = None

                async def dark_market_cutscene(interaction):
                    nonlocal message
                    if interaction.user != message.author:
                        await interaction.response.send_message(
                            "the shadow you saw runs away. perhaps you need to be the one to catch the cat.",
                            ephemeral=True,
                        )
                        return
                    if user.dark_market_active:
                        await interaction.response.send_message("the shadowy figure is nowhere to be found.", ephemeral=True)
                        return
                    user.dark_market_active = True
                    await user.save()
                    await interaction.response.send_message("is someone watching after you?", ephemeral=True)

                    dark_market_followups = [
                        "you walk up to them. the dark voice says:",
                        "**???**: Hello. We have a unique deal for you.",
                        '**???**: To access our services, press "Hidden" `/achievements` tab 3 times in a row.',
                        "**???**: You won't be disappointed.",
                        "before you manage to process that, the figure disappears. will you figure out whats going on?",
                        "the only choice is to go to that place.",
                    ]

                    for phrase in dark_market_followups:
                        await asyncio.sleep(5)
                        await interaction.followup.send(phrase, ephemeral=True)

                vote_time_user = await User.get_or_create(user_id=message.author.id)
                if random.randint(0, 10) == 0 and user.cat_Fine >= 20 and not user.dark_market_active:
                    button = Button(label="You see a shadow...", style=ButtonStyle.red)
                    button.callback = dark_market_cutscene
                elif config.WEBHOOK_VERIFY and vote_time_user.vote_time_topgg + 43200 < time.time():
                    button = Button(
                        emoji=get_emoji("topgg"),
                        label=random.choice(vote_button_texts),
                        url="https://top.gg/bot/1387305159264309399/vote",
                    )
                elif random.randint(0, 20) == 0:
                    button = Button(label="Join our Discord!", url="https://discord.gg/staring")
                elif random.randint(0, 500) == 0:
                    button = Button(label="John Discord 🤠", url="https://discord.gg/staring")
                elif random.randint(0, 50000) == 0:
                    button = Button(
                        label="DAVE DISCORD 😀💀⚠️🥺",
                        url="https://discord.gg/staring",
                    )
                elif random.randint(0, 5000000) == 0:
                    button = Button(
                        label="JOHN AND DAVE HAD A SON 💀🤠😀⚠️🥺",
                        url="https://discord.gg/staring",
                    )

                if button:
                    view = View(timeout=VIEW_TIMEOUT)
                    view.add_item(button)

                # increment the dynamic cat counter safely
                key = f"cat_{le_emoji}"
                try:
                    # try mapping-style access first (some ORM wrappers support this)
                    user[key] += silly_amount
                    new_count = user[key]
                except Exception:
                    # fallback to attribute-style access (most DB models use attributes)
                    current = getattr(user, key, 0) or 0
                    new_val = current + silly_amount
                    try:
                        setattr(user, key, new_val)
                    except Exception:
                        # last resort: leave new_count as computed value
                        pass
                    new_count = new_val

                async def delete_cat():
                    try:
                        cat_spawn = send_target.get_partial_message(cat_temp)
                        await cat_spawn.delete()
                    except Exception:
                        pass

                async def send_confirm():
                    try:
                        kwargs = {}
                        if view:
                            kwargs["view"] = view

                        await send_target.send(
                            coughstring.replace("{username}", message.author.name.replace("_", "\\_"))
                            .replace("{emoji}", str(icon))
                            .replace("{type}", le_emoji)
                            .replace("{count}", f"{new_count:,}")
                            .replace("{time}", caught_time[:-1])
                            + suffix_string,
                            **kwargs,
                        )
                    except Exception:
                        pass

                await asyncio.gather(delete_cat(), send_confirm())

                user.total_catches += 1
                if do_time:
                    user.total_catch_time += time_caught

                # handle fastest and slowest catches
                if do_time and time_caught < user.time:
                    user.time = time_caught
                if do_time and time_caught > user.timeslow:
                    user.timeslow = time_caught

                if message.channel.id in temp_rains_storage:
                    temp_rains_storage.remove(message.channel.id)

                if time_caught > 0 and time_caught == int(time_caught):
                    user.perfection_count += 1

                if channel.cat_rains != 0:
                    user.rain_participations += 1

                await user.save()

                await _check_full_stack_and_huzzful(user, message, le_emoji)

                if random.randint(0, 1000) == 69:
                    await achemb(message, "lucky", "send")
                if message.content == "CAT":
                    await achemb(message, "loud_cat", "send")
                if channel.cat_rains != 0:
                    await achemb(message, "cat_rain", "send")

                await achemb(message, "first", "send")

                if user.time <= 5:
                    await achemb(message, "fast_catcher", "send")

                if user.timeslow >= 3600:
                    await achemb(message, "slow_catcher", "send")

                if time_caught in [3.14, 31.41, 31.42, 194.15, 194.16, 1901.59, 11655.92, 11655.93]:
                    await achemb(message, "pie", "send")

                if time_caught > 0 and time_caught == int(time_caught):
                    await achemb(message, "perfection", "send")

                if did_boost:
                    await achemb(message, "boosted", "send")

                if "undefined" not in caught_time and time_caught > 0:
                    raw_digits = "".join(char for char in caught_time[:-1] if char.isdigit())
                    if len(set(raw_digits)) == 1:
                        await achemb(message, "all_the_same", "send")

                # handle battlepass
                await progress(message, user, "3cats")
                if channel.cattype == "Fine":
                    await progress(message, user, "2fine")
                if channel.cattype == "Good":
                    await progress(message, user, "good")
                if time_caught >= 0 and time_caught < 10:
                    await progress(message, user, "under10")
                if time_caught >= 0 and int(time_caught) % 2 == 0:
                    await progress(message, user, "even")
                if time_caught >= 0 and int(time_caught) % 2 == 1:
                    await progress(message, user, "odd")
                if channel.cattype and channel.cattype not in ["Fine", "Nice", "Good"]:
                    await progress(message, user, "rare+")
                if did_boost:
                    await progress(message, user, "prism")
                if user.catch_quest == "finenice":
                    # 0 none
                    # 1 fine
                    # 2 nice
                    # 3 both
                    if channel.cattype == "Fine" and user.catch_progress in [0, 2]:
                        await progress(message, user, "finenice")
                    elif channel.cattype == "Nice" and user.catch_progress in [0, 1]:
                        await progress(message, user, "finenice")
                        await progress(message, user, "finenice")
            finally:
                await channel.save()
                if decided_time:
                    await asyncio.sleep(decided_time)
                    try:
                        temp_catches_storage.remove(pls_remove_me_later_k_thanks)
                    except Exception:
                        pass
                    await spawn_cat(str(message.channel.id))
                else:
                    try:
                        temp_catches_storage.remove(pls_remove_me_later_k_thanks)
                    except Exception:
                        pass

    if text.lower().startswith("cat!amount") and perms.send_messages and (not message.thread or perms.send_messages_in_threads):
        user = await User.get_or_create(user_id=message.author.id)
        try:
            user.custom_num = int(text.split(" ")[1])
            await user.save()
            await message.reply("success")
        except Exception:
            await message.reply("invalid number")

    # only letting the owner of the bot access anything past this point
    if message.author.id != OWNER_ID:
        return

    # those are "owner" commands which are not really interesting
    if text.lower().startswith("cat!sweep"):
        try:
            channel = await Channel.get_or_none(channel_id=message.channel.id)
            channel.cat = 0
            await channel.save()
            await message.reply("success")
        except Exception:
            pass
    if text.lower().startswith("cat!rain"):
        # syntax: cat!rain 553093932012011520 short
        things = text.split(" ")
        user = await User.get_or_create(user_id=int(things[1]))
        if not user.rain_minutes:
            user.rain_minutes = 0
        if things[2] == "short":
            user.rain_minutes += 2
        elif things[2] == "medium":
            user.rain_minutes += 10
        elif things[2] == "long":
            user.rain_minutes += 20
        else:
            user.rain_minutes += int(things[2])
        user.premium = True
        await user.save()
    if text.lower().startswith("cat!restart"):
        await message.reply("restarting!")
        os.system("git pull")
        if config.WEBHOOK_VERIFY:
            await vote_server.cleanup()
        await bot.cat_bot_reload_hook("db" in text)  # pyright: ignore
    if text.lower().startswith("cat!print"):
        # just a simple one-line with no async (e.g. 2+3)
        try:
            await message.reply(eval(text[9:]))
        except Exception:
            try:
                await message.reply(traceback.format_exc())
            except Exception:
                pass
    if text.lower().startswith("cat!eval"):
        # complex eval, multi-line + async support
        # requires the full `await message.channel.send(2+3)` to get the result

        # async def go():
        #  <stuff goes here>
        #
        # try:
        #  bot.loop.create_task(go())
        # except Exception:
        #  await message.reply(traceback.format_exc())

        silly_billy = text[9:]

        spaced = ""
        for i in silly_billy.split("\n"):
            spaced += "  " + i + "\n"

        intro = "async def go(message, bot):\n try:\n"
        ending = "\n except Exception:\n  await message.reply(traceback.format_exc())\nbot.loop.create_task(go(message, bot))"

        complete = intro + spaced + ending
        exec(complete)
    if text.lower().startswith("cat!news"):
        async for i in Channel.all():
            try:
                channeley = bot.get_channel(int(i.channel_id))
                if not isinstance(
                    channeley,
                    Union[
                        discord.TextChannel,
                        discord.StageChannel,
                        discord.VoiceChannel,
                        discord.Thread,
                    ],
                ):
                    continue
                if perms.send_messages and (not message.thread or perms.send_messages_in_threads):
                    await channeley.send(text[8:])
            except Exception:
                pass
    if text.lower().startswith("cat!custom"):
        stuff = text.split(" ")
        if stuff[1][0] not in "1234567890":
            stuff.insert(1, message.channel.owner_id)
        user = await User.get_or_create(user_id=int(stuff[1]))
        cat_name = " ".join(stuff[2:])
        if stuff[2] != "None" and message.reference and message.reference.message_id:
            emoji_name = re.sub(r"[^a-zA-Z0-9]", "", cat_name).lower() + "cat"
            if emoji_name in emojis.keys():
                await message.reply("emoji already exists")
                return
            og_msg = await message.channel.fetch_message(message.reference.message_id)
            if not og_msg or len(og_msg.attachments) == 0:
                await message.reply("no image found")
                return
            img_data = await og_msg.attachments[0].read()

            if og_msg.attachments[0].content_type.startswith("image/gif"):
                await bot.create_application_emoji(name=emoji_name, image=img_data)
            else:
                img = Image.open(io.BytesIO(img_data))
                img.thumbnail((128, 128))
                with io.BytesIO() as image_binary:
                    img.save(image_binary, format="PNG")
                    image_binary.seek(0)
                    await bot.create_application_emoji(name=emoji_name, image=image_binary.getvalue())
        user.custom = cat_name if cat_name != "None" else ""
        emojis = {emoji.name: str(emoji) for emoji in await bot.fetch_application_emojis()}
        await user.save()
        await message.reply("success")


# the message when cat gets added to a new server
async def on_guild_join(guild):
    def verify(ch):
        return ch and ch.permissions_for(guild.me).send_messages

    def find(patt, channels):
        for i in channels:
            if patt in i.name:
                return i

    # first to try a good channel, then whenever we cat atleast chat
    ch = find("cat", guild.text_channels)
    if not verify(ch):
        ch = find("bot", guild.text_channels)
    if not verify(ch):
        ch = find("commands", guild.text_channels)
    if not verify(ch):
        ch = find("general", guild.text_channels)

    found = False
    if not verify(ch):
        for ch in guild.text_channels:
            if verify(ch):
                found = True
                break
        if not found:
            ch = guild.owner

    # you are free to change/remove this, its just a note for general user letting them know
    unofficial_note = "**made by fillermcdiller <3**\n\n"
    if not bot.user or bot.user.id == 1387305159264309399:
        unofficial_note = ""
    try:
        if ch.permissions_for(guild.me).send_messages:
            await ch.send(
                unofficial_note
                + "Thanks for adding me!\nTo start, use `/setup` and `/help` to learn more!\nJoin the support server here: https://discord.gg/Zx6em4AEq2 \nHave a nice day/night :)"
            )
    except Exception:
        pass

    if guild.self_role:
        if guild.self_role.permissions.read_message_history:
            source = "top.gg"
        else:
            source = "direct"
        print(f"New guild: {guild.id} - {source}")


@bot.tree.command(description="Learn to use the bot")
async def help(message):
    embed1 = discord.Embed(
        title="How to Setup",
        description="Server moderator (anyone with *Manage Server* permission) needs to run `/setup` in any channel. After that, cats will start to spawn in 2-20 minute intervals inside of that channel.\nYou can customize those intervals with `/changetimings` and change the spawn message with `/changemessage`.\nCat spawns can also be forced by moderators using `/forcespawn` command.\nYou can have unlimited amounts of setupped channels at once.\nYou can stop the spawning in a channel by running `/forget`.",
        color=Colors.brown,
    ).set_thumbnail(url="https://wsrv.nl/?url=raw.githubusercontent.com/milenakos/cat-bot/main/images/cat.png")

    embed2 = (
        discord.Embed(title="How to Play", color=Colors.brown)
        .add_field(
            name="Catch Cats",
            value='Whenever a cat spawns you will see a message along the lines of "a cat has appeared", which will also display it\'s type.\nCat types can have varying rarities from 25% for Fine to hundredths of percent for rarest types.\nSo, after saying "cat" the cat will be added to your inventory.',
            inline=False,
        )
        .add_field(
            name="Viewing Your Inventory",
            value="You can view your (or anyone elses!) inventory using `/inventory` command. It will display all the cats, along with other stats.\nIt is important to note that you have a separate inventory in each server and nothing carries over, to make the experience more fair and fun.\nCheck out the leaderboards for your server by using `/leaderboards` command.\nIf you want to transfer cats, you can use the simple `/gift` or more complex `/trade` commands.",
            inline=False,
        )
        .add_field(
            name="Let's get funky!",
            value='KITTAYYYYYYY has various other mechanics to make fun funnier. You can collect various `/achievements`, for example saying "i read help", progress in the `/battlepass`, or have beef with the mafia over cataine addiction. The amount you worship is the limit!',
            inline=False,
        )
        .add_field(
            name="Other features",
            value="KITTAYYYYYYY has extra fun commands which you will discover along the way.\nAnything unclear? Check out [our wiki](https://wiki.minkos.lol) or drop us a line at our [Discord server](https://discord.gg/staring).",
            inline=False,
        )
        .set_footer(
            text=f"KITTAYYYYYYY by FillerMcDiller, {datetime.datetime.utcnow().year}",
            icon_url="https://wsrv.nl/?url=raw.githubusercontent.com/milenakos/cat-bot/main/images/cat.png",
        )
    )

    # Add a "List of Commands" button which opens a paginated command list
    class HelpView(View):
        def __init__(self, author_id: int):
            super().__init__(timeout=VIEW_TIMEOUT)
            self.author_id = author_id

        @discord.ui.button(label="List of Commands", style=ButtonStyle.green)
        async def list_commands(self, interaction2: discord.Interaction, button: Button):
            if interaction2.user.id != self.author_id:
                await do_funny(interaction2)
                return
            await interaction2.response.defer()

            # Gather all application commands from the tree
            cmds = []
            try:
                for c in bot.tree.walk_commands():
                    # some commands may be groups, use name and description
                    name = getattr(c, "name", None) or str(c)
                    desc = getattr(c, "description", "") or "No description."
                    # mark admin commands if description contains admin or command has default permissions
                    is_admin = False
                    try:
                        if "admin" in desc.lower() or desc.strip().upper().startswith("(ADMIN)"):
                            is_admin = True
                    except Exception:
                        pass
                    cmds.append({"name": name, "desc": desc, "admin": is_admin})
            except Exception:
                # fallback: minimal manual list if tree walk fails
                cmds = []

            # Categorize commands heuristically
            sections = {
                "Admin": [],
                "Economy": [],
                "Cats": [],
                "Fun": [],
                "Gambling": [],
                "Utility": [],
                "Other": [],
            }

            def categorize(cmd):
                key = (cmd["name"] + " " + cmd["desc"]).lower()
                if cmd.get("admin") or "admin" in key or "give" in key or "manage" in key:
                    return "Admin"
                if any(k in key for k in ["shop", "pack", "kibble", "buy", "sell", "rain", "battlepass", "pack"]):
                    return "Economy"
                if any(k in key for k in ["cat", "cats", "play", "catch", "inventory", "rename", "catalogue", "catpedia", "purr"]):
                    return "Cats"
                if any(k in key for k in ["slot", "slots", "pig", "tictactoe", "tiktok", "8ball", "news", "wiki", "credits"]):
                    return "Fun"
                if any(k in key for k in ["slot", "casino", "gamble", "bet", "pig"]):
                    return "Gambling"
                if any(k in key for k in ["help", "info", "stats", "getid", "last", "catpedia", "wiki", "news"]):
                    return "Utility"
                return "Other"

            for c in cmds:
                sec = categorize(c)
                sections.setdefault(sec, []).append((c["name"], c["desc"]))

            # Sort commands alphabetically within each section
            for sec in sections:
                sections[sec].sort(key=lambda x: x[0].lower())

            # Build flat lines with section headers and command lines
            lines = []
            for sec in ["Admin", "Economy", "Cats", "Fun", "Gambling", "Utility", "Other"]:
                items = sections.get(sec, [])
                if not items:
                    continue
                lines.append(f"__{sec}__")
                for name, desc in items:
                    lines.append(f"**/{name}** — {desc}")

            # Paginate: 20 lines per page
            page_size = 20
            chunks = [lines[i : i + page_size] for i in range(0, len(lines), page_size)]

            def make_embed(page_index: int) -> discord.Embed:
                embed = discord.Embed(title="All Commands", color=Colors.brown)
                embed.description = "\n".join(chunks[page_index])
                embed.set_footer(text=f"Page {page_index + 1}/{len(chunks)}")
                return embed

            if not chunks:
                await interaction2.followup.send("No commands found.", ephemeral=True)
                return

            class PagesView(View):
                def __init__(self, author_id: int):
                    super().__init__(timeout=VIEW_TIMEOUT)
                    self.page = 0
                    self.author_id = author_id

                @discord.ui.button(label="◀ Prev", style=ButtonStyle.secondary)
                async def prev_button(self, interaction3: discord.Interaction, button: Button):
                    if interaction3.user.id != self.author_id:
                        await do_funny(interaction3)
                        return
                    self.page = (self.page - 1) % len(chunks)
                    await interaction3.response.edit_message(embed=make_embed(self.page), view=self)

                @discord.ui.button(label="Next ▶", style=ButtonStyle.secondary)
                async def next_button(self, interaction3: discord.Interaction, button: Button):
                    if interaction3.user.id != self.author_id:
                        await do_funny(interaction3)
                        return
                    self.page = (self.page + 1) % len(chunks)
                    await interaction3.response.edit_message(embed=make_embed(self.page), view=self)

            await interaction2.followup.send(embed=make_embed(0), view=PagesView(interaction2.user.id), ephemeral=True)

    view = HelpView(author_id=message.user.id)
    await message.response.send_message(embeds=[embed1, embed2], view=view)


@bot.tree.command(description="Roll the credits")
async def credits(message: discord.Interaction):
    global gen_credits

    if not gen_credits:
        await message.response.send_message(
            "credits not yet ready! this is a very rare error, congrats.",
            ephemeral=True,
        )
        return

    await message.response.defer()

    embedVar = discord.Embed(title="KITTAYYYYYYY", color=Colors.brown, description=gen_credits).set_thumbnail(
        url="https://wsrv.nl/?url=raw.githubusercontent.com/milenakos/cat-bot/main/images/cat.png"
    )

    await message.followup.send(embed=embedVar)


def format_timedelta(start_timestamp, end_timestamp):
    delta = datetime.timedelta(seconds=end_timestamp - start_timestamp)
    days = delta.days
    seconds = delta.seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{days}d {hours}h {minutes}m {seconds}s"


@bot.tree.command(description="View various bot information and stats")
async def info(message: discord.Interaction):
    embed = discord.Embed(title="KITTAYYYYYYY Info", color=Colors.brown)
    try:
        git_timestamp = int(subprocess.check_output(["git", "show", "-s", "--format=%ct"]).decode("utf-8"))
    except Exception:
        git_timestamp = 0

    embed.description = f"""
**__System__**
OS Version: `{platform.system()} {platform.release()}`
Python Version: `{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}`
discord.py Version: `{discord.__version__}{"-catbot" if "localhost" in str(discord.gateway.DiscordWebSocket.DEFAULT_GATEWAY) else ""}`
CPU usage: `{psutil.cpu_percent():.1f}%`
RAM usage: `{psutil.virtual_memory().percent:.1f}%`

**__Tech__**
Hard uptime: `{format_timedelta(config.HARD_RESTART_TIME, time.time())}`
Soft uptime: `{format_timedelta(config.SOFT_RESTART_TIME, time.time())}`
Last code update: `{format_timedelta(git_timestamp, time.time()) if git_timestamp else "N/A"}`
Loops since soft restart: `{loop_count + 1:,}`
Shards: `{len(bot.shards):,}`
Guild shard: `{message.guild.shard_id:,}`

**__Global Stats__**
Guilds: `{len(bot.guilds):,}`
DB Profiles: `{await Profile.count():,}`
DB Users: `{await User.count():,}`
DB Channels: `{await Channel.count():,}`
"""

    await message.response.send_message(embed=embed)


@bot.tree.command(description="Confused? Check out the KITTAYYYYYYY Wiki!")
async def wiki(message: discord.Interaction):
    embed = discord.Embed(title="KITTAYYYYYYY Wiki", color=Colors.brown)
    embed.description = "\n".join(
        [
            "Main Page: https://wiki.minkos.lol/",
            "",
            "[KITTAYYYYYYY](https://wiki.minkos.lol/cat-bot)",
            "[Cat Spawning](https://wiki.minkos.lol/spawning)",
            "[Commands](https://wiki.minkos.lol/commands)",
            "[Cat Types](https://wiki.minkos.lol/cat-types)",
            "[Cattlepass](https://wiki.minkos.lol/cattlepass)",
            "[Achievements](https://wiki.minkos.lol/achievements)",
            "[Packs](https://wiki.minkos.lol/packs)",
            "[Trading](https://wiki.minkos.lol/trading)",
            "[Gambling](https://wiki.minkos.lol/gambling)",
            "[The Dark Market](https://wiki.minkos.lol/dark-market)",
            "[Prisms](https://wiki.minkos.lol/prisms)",
        ]
    )
    await message.response.send_message(embed=embed)
    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    await progress(message, profile, "wiki")


@bot.tree.command(description="Read The KITTAYYYYYYY Times™️")
async def news(message: discord.Interaction):
    user = await User.get_or_create(user_id=message.user.id)
    buttons = []
    current_state = user.news_state.strip()

    async def send_news(interaction: discord.Interaction):
        news_id = int(interaction.data["custom_id"])
        if interaction.user != message.user:
            await do_funny(interaction)
            return

        async def go_back(back_interaction: discord.Interaction):
            await back_interaction.response.defer()
            await regen_buttons()
            await back_interaction.edit_original_response(content="Choose an article:", view=generate_page(current_page), embed=None)

        await interaction.response.defer()

        current_state = user.news_state.strip()
        if current_state[news_id] not in "123456789":
            user.news_state = current_state[:news_id] + "1" + current_state[news_id + 1 :]
            await user.save()

        profile = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)
        await progress(interaction, profile, "news")

        view = View(timeout=VIEW_TIMEOUT)
        back_button = Button(emoji="⬅️", label="Back")
        back_button.callback = go_back
        view.add_item(back_button)

        if news_id == 0:
            embed = discord.Embed(
                title="📜 KITTAYYYYYYY Survey",
                description="Hello and welcome to The KITTAYYYYYYY Times:tm:! I kind of want to learn more about your time with KITTAYYYYYYY because I barely know about it lmao. This should only take a couple of minutes.\n\nGood high-quality responses will win FREE cat rain prizes.\n\nSurvey is closed!",
                color=Colors.brown,
                timestamp=datetime.datetime.fromtimestamp(1731168230),
            )
            await interaction.edit_original_response(content=None, view=view, embed=embed)
        elif news_id == 1:
            embed = discord.Embed(
                title="✨ New Cat Rains perks!",
                description="Hey there! Buying Cat Rains now gives you access to `/editprofile` command! You can add an image, change profile color, and add an emoji next to your name. Additionally, you will now get a special role in our [discord server](https://discord.gg/staring).\nEveryone who ever bought rains and all future buyers will get it.\nAnyone who bought these abilities separately in the past (known as 'KITTAYYYYYYY Supporter') have received 10 minutes of Rains as compensation.\n\nThis is a really cool perk and I hope you like it!",
                color=Colors.brown,
                timestamp=datetime.datetime.fromtimestamp(1732377932),
            )
            button = discord.ui.Button(label="KITTAYYYYYYY Store", url="https://catbot.shop")
            view.add_item(button)
            await interaction.edit_original_response(content=None, view=view, embed=embed)
        elif news_id == 2:
            embed = discord.Embed(
                title="☃️ KITTAYYYYYYY Christmas",
                description=f"⚡ **KITTAYYYYYYY Wrapped 2024**\nIn 2024 KITTAYYYYYYY got...\n- 🖥️ *45777* new servers!\n- 👋 *286607* new profiles!\n- {get_emoji('staring_cat')} okay so funny story due to the new 2.1 billion per cattype limit i added a few months ago 4 with 832 zeros cats were deleted... oopsie... there are currently *64105220101255* cats among the entire bot rn though\n- {get_emoji('cat_throphy')} *1518096* achievements get!\nSee last year's Wrapped [here](<https://discord.com/channels/966586000417619998/1021844042654417017/1188573593408385074>).\n\n❓ **New Year Update**\nSomething is coming...",
                color=Colors.brown,
                timestamp=datetime.datetime.fromtimestamp(1734458962),
            )
            await interaction.edit_original_response(content=None, embed=embed, view=view)
        elif news_id == 3:
            embed = discord.Embed(
                title="Battlepass is getting an update!",
                description="""## qhar?
- Huge stuff!
- Battlepass will now reset every month
- You will have 3 quests, including voting
- They refresh 12 hours after completing
- Quest reward is XP which goes towards progressing
- There are 30 battlepass levels with much better rewards (even Ultimate cats and Rain minutes!)
- Prism crafting/true ending no longer require battlepass progress.
- More fun stuff to do each day and better rewards!

## oh no what if i hate grinding?
Don't worry, quests are very easy and to complete the battlepass you will need to complete less than 3 easy quests a day.

## will you sell paid battlepass? its joever
There are currently no plans to sell a paid battlepass.""",
                color=Colors.brown,
                timestamp=datetime.datetime.fromtimestamp(1735689601),
            )
            await interaction.edit_original_response(content=None, view=view, embed=embed)
        elif news_id == 4:
            embed = discord.Embed(
                title=f"{get_emoji('goldpack')} Packs!",
                description=f"""you want more gambling? we heard you!
instead of predetermined cat rewards you now unlock Packs! packs have different rarities and have a 30% chance to upgrade a rarity when opening, then 30% for one more upgrade and so on. this means even the most common packs have a small chance to upgrade to the rarest one!
the rarities are - Wooden {get_emoji("woodenpack")}, Stone {get_emoji("stonepack")}, Bronze {get_emoji("bronzepack")}, Silver {get_emoji("silverpack")}, Gold {get_emoji("goldpack")}, Platinum {get_emoji("platinumpack")}, Diamond {get_emoji("diamondpack")} and Celestial {get_emoji("celestialpack")}!
the extra reward is now a stone pack instead of 5 random cats too!
*LETS GO GAMBLING*""",
                color=Colors.brown,
                timestamp=datetime.datetime.fromtimestamp(1740787200),
            )
            await interaction.edit_original_response(content=None, view=view, embed=embed)
        elif news_id == 5:
            embed = discord.Embed(
                title="Important Message from CEO of KITTAYYYYYYY",
                description="""(April Fools 2025)

Dear KITTAYYYYYYY users,

I hope this message finds you well. I want to take a moment to address some recent developments within our organization that are crucial for our continued success.

Our latest update has had a significant impact on our financial resources, resulting in an unexpected budget shortfall. In light of this situation, we have made the difficult decision to implement advertising on our platform to help offset these costs. We believe this strategy will not only stabilize our finances but also create new opportunities for growth.

Additionally, in our efforts to manage expenses more effectively, we have replaced all cat emojis with just the "Fine Cat" branding. This change will help us save on copyright fees while maintaining an acceptable user experience.

We are committed to resolving these challenges and aim to have everything back on track by **April 2nd**. Thank you for your understanding and continued dedication during this time. Together, we will navigate these changes and emerge stronger.

Best regards,
[Your Name]""",
                color=Colors.brown,
                timestamp=datetime.datetime.fromtimestamp(1743454803),
            )
            await interaction.edit_original_response(content=None, view=view, embed=embed)
        elif news_id == 6:
            embed = discord.Embed(
                title="🥳 KITTAYYYYYYY Turns 3",
                description="""april 21st is a special day for KITTAYYYYYYY! on this day is its birthday, and in 2025 its turning three!
happy birthda~~
...
hold on...
im recieving some news cats are starting to get caught with puzzle pieces in their teeth!
the puzzle pieces say something about having to collect a million of them...
how interesting!

update: the puzzle piece event has concluded""",
                color=Colors.brown,
                timestamp=datetime.datetime.fromtimestamp(1745242856),
            )
            await interaction.edit_original_response(content=None, view=view, embed=embed)
        elif news_id == 7:
            embed = discord.Embed(
                title="🎉 100,000 SERVERS WHAT",
                description="""wow! KITTAYYYYYYY has reached 100,000 servers! this beyond insane i never thought this would happen thanks everyone
giving away a whole bunch of rain as celebration!

1. cat stand giveaway (ENDED)
[join our discord server](<https://discord.gg/FBkXDxjqSz>) and click the first reaction under the latest newspost to join in!
there will be a total of 10 winners who will get 40 minutes each! giveaway ends july 5th.

2. art contest (ENDED)
again in our [discord server](<https://discord.gg/zrYstPe3W6>) a new channel has opened for art submissions!
top 5 people who get the most community votes will get 250, 150, 100, 50 and 50 rain minutes respectively!

3. KITTAYYYYYYY event (ENDED)
starting june 30th, for the next 5 days you will get points randomly on every catch! if you manage to collect 1,000 points before the time runs out you will get 2 minutes of rain!!

4. sale (ENDED)
starting june 30th, [catbot.shop](<https://catbot.shop>) will have a sale for the next 5 days! if everything above wasnt enough rain for your fancy you can buy some more with a discount!

aaaaaaaaaaaaaaa""",
                color=Colors.brown,
                timestamp=datetime.datetime.fromtimestamp(1751252181),
            )
            button = discord.ui.Button(label="Join our Server", url="https://discord.gg/staring")
            view.add_item(button)
            button2 = discord.ui.Button(label="KITTAYYYYYYY Store", url="https://catbot.shop")
            view.add_item(button2)
            await interaction.edit_original_response(content=None, view=view, embed=embed)

        elif news_id == 8:
            embed = discord.Embed(
                title="Regarding recent instabilities",
                description="""hello!

stuff has been kinda broken the past few days, and the past 24 hours in paricular.

it was mostly my fault, but i worked hard to fix everything and i think its mostly working now.

as a compensation i will give everyone who voted in the past 3 days 2 free gold packs! you can press the button below to claim them. (note you can only claim it in 1 server, choose wisely)

thanks for using KITTAYYYYYYY!""",
                color=Colors.brown,
                timestamp=datetime.datetime.fromtimestamp(1752689941),
            )
        
        elif news_id == 9:
            embed = discord.Embed(
                title="NEW CATS, KIBBLE, AND.. ITEMS??? WOWOWOWOOWO!!!",
                description="""hello!

stuff has been going on! i, FillerMcDiller, have added a whole bunch of new stuff to kittay!
We have added 7 (thats right!) new cat types! You can check them out in the catalog (hint: egirl is NO LONGER the best cat)
As well, there is now a new currency in KITTAYYYYYYY, KIBBLE! You can earn kibble from various activities in KITTAYYYYYYY, and spend them on a whole bunch of new items! Check out /shop to see what you can buy with it!

Anyways, I am constantly updating this bot and have many (MANY) more plans for the future, so stay tuned!
- Filler <3""",
                color=Colors.brown,
                timestamp=datetime.datetime.fromtimestamp(1752689941),
            )
            button = discord.ui.Button(label="Expired!", disabled=True)
            view.add_item(button)
            await interaction.edit_original_response(content=None, view=view, embed=embed)

    async def regen_buttons():
        nonlocal buttons
        await user.refresh_from_db()
        buttons = []
        current_state = user.news_state.strip()
        for num, article in enumerate(news_list):
            try:
                have_read_this = current_state[num] != "0"
            except Exception:
                have_read_this = False
            button = Button(
                label=article["title"],
                emoji=get_emoji(article["emoji"]),
                custom_id=str(num),
                style=ButtonStyle.green if not have_read_this else ButtonStyle.gray,
            )
            button.callback = send_news
            buttons.append(button)
        buttons = buttons[::-1]  # reverse the list so the first button is the most recent article

    await regen_buttons()

    if len(news_list) > len(current_state):
        user.news_state = current_state + "0" * (len(news_list) - len(current_state))
        await user.save()

    current_page = 0

    async def prev_page(interaction):
        nonlocal current_page
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        current_page -= 1
        await interaction.response.edit_message(view=generate_page(current_page))

    async def next_page(interaction):
        nonlocal current_page
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        current_page += 1
        await interaction.response.edit_message(view=generate_page(current_page))

    async def mark_all_as_read(interaction):
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        user.news_state = "1" * len(news_list)
        await user.save()
        await regen_buttons()
        await interaction.response.edit_message(view=generate_page(current_page))

    def generate_page(number):
        view = View(timeout=VIEW_TIMEOUT)

        # article buttons
        if current_page == 0:
            end = (number + 1) * 4
        else:
            end = len(buttons)
        for num, button in enumerate(buttons[number * 4 : end]):
            if current_page == 0:
                button.row = num
            view.add_item(button)

        # pages buttons
        if current_page != 0:
            button = Button(label="Back", row=4)
            button.callback = prev_page
            view.add_item(button)

        button = Button(
            label="Mark all as read",
            row=4,
        )
        button.callback = mark_all_as_read
        view.add_item(button)

        if current_page == 0:
            button = Button(
                label="Archive",
                row=4,
            )
            button.callback = next_page
            view.add_item(button)

        return view

    await message.response.send_message("Choose an article:", view=generate_page(current_page))
    await achemb(message, "news", "send")


@bot.tree.command(description="Read text as TikTok's TTS woman")
@discord.app_commands.describe(text="The text to be read! (300 characters max)")
async def tiktok(message: discord.Interaction, text: str):
    perms = await fetch_perms(message)
    if not perms.attach_files:
        await message.response.send_message("i cant attach files here!", ephemeral=True)
        return

    # detect n-words
    for i in NONOWORDS:
        if i in text.lower():
            await message.response.send_message("Do not.", ephemeral=True)
            return

    await message.response.defer()
    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)

    if text == "bwomp":
        file = discord.File("bwomp.mp3", filename="bwomp.mp3")
        await message.followup.send(file=file)
        await achemb(message, "bwomp", "send")
        await progress(message, profile, "tiktok")
        return

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                "https://tiktok-tts.weilnet.workers.dev/api/generation",
                json={"text": text, "voice": "en_us_001"},
                headers={"User-Agent": "CatBot/1.0 https://github.com/milenakos/cat-bot"},
            ) as response:
                stuff = await response.json()
                with io.BytesIO() as f:
                    ba = "data:audio/mpeg;base64," + stuff["data"]
                    f.write(base64.b64decode(ba))
                    f.seek(0)
                    await message.followup.send(file=discord.File(fp=f, filename="output.mp3"))
        except discord.NotFound:
            pass
        except Exception:
            await message.followup.send("i dont speak guacamole (remove non-english characters, make sure the message is below 300 characters)")

    await progress(message, profile, "tiktok")


class GiveawayView(discord.ui.View):
    def __init__(self, cat_type: str):
        super().__init__(timeout=None)  # No timeout for giveaways
        self.cat_type = cat_type
        self.participants = set()
        
    @discord.ui.button(label="Enter Giveaway!", style=ButtonStyle.green)
    async def enter_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.participants.add(interaction.user.id)
        await interaction.response.send_message("You've entered the giveaway! Good luck!", ephemeral=True)

def parse_time(time_str: str) -> int:
    """Convert a time string like '1h' or '30m' to seconds"""
    if not time_str:
        return 0
    
    units = {
        's': 1,
        'm': 60,
        'h': 3600,
        'd': 86400
    }
    
    unit = time_str[-1].lower()
    if unit not in units:
        return 0
    
    try:
        value = int(time_str[:-1])
        return value * units[unit]
    except ValueError:
        return 0

class AdminPanelModal(discord.ui.Modal):
    def __init__(self, action: str, guild: discord.Guild):
        super().__init__(title=f"Admin Panel - {action}")
        self.action = action
        self.guild = guild
        
        if action == "Give Cats":
            self.add_item(discord.ui.TextInput(label="Username", placeholder="Username or nickname to give cats to"))
            self.add_item(discord.ui.TextInput(label="Cat Type", placeholder="Cat type to give"))
            self.add_item(discord.ui.TextInput(label="Amount", placeholder="Amount to give"))
        elif action == "Give Rains":
            self.add_item(discord.ui.TextInput(label="Username", placeholder="Username or nickname to give Rains to"))
            self.add_item(discord.ui.TextInput(label="Amount", placeholder="Amount of Rain Minutes to give"))
        elif action == "Give XP":
            self.add_item(discord.ui.TextInput(label="Username", placeholder="Username or nickname to give XP to"))
            self.add_item(discord.ui.TextInput(label="Amount", placeholder="Amount of XP to give"))
        elif action == "Give Packs":
            self.add_item(discord.ui.TextInput(label="Username", placeholder="Username or nickname to give packs to"))
            self.add_item(discord.ui.TextInput(label="Pack Type", placeholder="Pack type to give"))
            self.add_item(discord.ui.TextInput(label="Amount", placeholder="Amount to give"))
        elif action == "Speak":
            self.add_item(discord.ui.TextInput(label="Message", style=discord.TextStyle.paragraph, placeholder="Message to send"))
            self.add_item(discord.ui.TextInput(label="Image URL (optional)", required=False, placeholder="URL to an image/gif"))
        elif action == "Start Giveaway":
            self.add_item(discord.ui.TextInput(label="Cat Type", placeholder="Type of cat to give away"))
            self.add_item(discord.ui.TextInput(label="Duration", placeholder="Duration (e.g. 5m, 1h)"))
            
    async def find_member(self, name: str) -> discord.Member:
        """Find a member by name, nickname, ID, or mention"""
        name = name.strip()
        print(f"[DEBUG] Searching for user: {name}")
        
        # Try to parse as ID first
        try:
            if name.isdigit():
                member = self.guild.get_member(int(name))
                if member:
                    print(f"[DEBUG] Found user by ID: {member}")
                    return member
                member = await self.guild.fetch_member(int(name))
                if member:
                    print(f"[DEBUG] Found user by ID (fetched): {member}")
                    return member
        except (ValueError, discord.NotFound, discord.HTTPException) as e:
            print(f"[DEBUG] ID lookup failed: {str(e)}")

        # Try mention format (strips <@!> or <@>)
        if name.startswith('<@') and name.endswith('>'):
            try:
                user_id = int(''.join(c for c in name if c.isdigit()))
                member = self.guild.get_member(user_id)
                if member:
                    print(f"[DEBUG] Found user by mention: {member}")
                    return member
                member = await self.guild.fetch_member(user_id)
                if member:
                    print(f"[DEBUG] Found user by mention (fetched): {member}")
                    return member
            except (ValueError, discord.NotFound, discord.HTTPException) as e:
                print(f"[DEBUG] Mention lookup failed: {str(e)}")

        # Search by name (includes partial matches)
        for member in self.guild.members:
            member_name = member.name
            member_display = member.display_name
            member_full = str(member)
            
            # Check exact matches first
            if name in [member_name, member_display, member_full]:
                print(f"[DEBUG] Found user by exact name match: {member}")
                return member
                
            # Then check partial matches
            if name in member_name or name in member_display or name in member_full:
                print(f"[DEBUG] Found user by partial name match: {member}")
                return member

        print(f"[DEBUG] No user found for: {name}")
        return None

    async def on_submit(self, interaction: discord.Interaction):
        if self.action == "Give Cats":
            member = await self.find_member(self.children[0].value)
            if not member:
                await interaction.response.send_message(f"Couldn't find user '{self.children[0].value}'!", ephemeral=True)
                return
                
            user = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=member.id)
            try:
                await add_cat_instances(user, self.children[1].value, int(self.children[2].value))
            except Exception:
                # fallback to aggregated count update
                try:
                    user[f"cat_{self.children[1].value}"] += int(self.children[2].value)
                    await user.save()
                except Exception:
                    pass
            await interaction.response.send_message(f"Gave {self.children[2].value} {self.children[1].value} cats to {member.mention}", ephemeral=True)
        
       
        elif self.action == "Give Rains":
            member = await self.find_member(self.children[0].value)
            if not member:
                await interaction.response.send_message(f"Couldn't find user '{self.children[0].value}'!", ephemeral=True)
                return
                
            user = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=member.id)
            user.rain_minutes += int(self.children[1].value)
            await user.save()
            await interaction.response.send_message(f"Gave {self.children[1].value} rains to {member.mention}", ephemeral=True)
        
        
        elif self.action == "Give XP":
            member = await self.find_member(self.children[0].value)
            if not member:
                await interaction.response.send_message(f"Couldn't find user '{self.children[0].value}'!", ephemeral=True)
                return
                
            user = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=member.id)
            user.progress += int(self.children[1].value)
            await user.save()
            await interaction.response.send_message(f"Gave {self.children[1].value} XP to {member.mention}", ephemeral=True)
        
        elif self.action == "Give Packs":
            member = await self.find_member(self.children[0].value)
            if not member:
                await interaction.response.send_message(f"Couldn't find user '{self.children[0].value}'!", ephemeral=True)
                return
                
            user = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=member.id)
            user[f"pack_{self.children[1].value.lower()}"] += int(self.children[2].value)
            await user.save()
            await interaction.response.send_message(f"Gave {self.children[2].value} {self.children[1].value} packs to {member.mention}", ephemeral=True)
        
        elif self.action == "Speak":
            embed = None
            if self.children[1].value:
                embed = discord.Embed()
                embed.set_image(url=self.children[1].value)
            await interaction.channel.send(content=self.children[0].value, embed=embed)
            await interaction.response.send_message("Message sent!", ephemeral=True)
        
        elif self.action == "Start Giveaway":
            duration = parse_time(self.children[1].value)
            if not duration:
                await interaction.response.send_message("Invalid duration format! Use format like '5m', '1h', etc.", ephemeral=True)
                return
                
            end_time = int(time.time() + duration)
            embed = discord.Embed(
                title=f"🎉 Cat Giveaway! 🎉",
                description=f"Win a {get_emoji(self.children[0].value.lower() + 'cat')} {self.children[0].value} cat!\n\n"
                          f"To enter, click the button below or say `W cat!` in chat.\n"
                          f"Giveaway ends <t:{end_time}:R> at <t:{end_time}:t>",
                color=Colors.green
            )
            view = GiveawayView(self.children[0].value)
            msg = await interaction.channel.send(embed=embed, view=view)
            await interaction.response.send_message("Giveaway started!", ephemeral=True)
            
            # Wait for giveaway duration
            await asyncio.sleep(duration)
            
            # Include people who said "W cat!"
            async for message in interaction.channel.history(after=msg):
                if message.content.lower().strip() in ["w cat!", "w cat"]:
                    view.participants.add(message.author.id)
            
            if view.participants:
                winner_id = random.choice(list(view.participants))
                winner = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=winner_id)
                try:
                    await add_cat_instances(winner, view.cat_type, 1)
                except Exception:
                    try:
                        winner[f"cat_{view.cat_type}"] += 1
                        await winner.save()
                    except Exception:
                        pass
                
                embed.description = f"🎉 Winner: <@{winner_id}>! 🎉\nYou won a {get_emoji(view.cat_type.lower() + 'cat')} {view.cat_type} cat!"
                await msg.edit(embed=embed, view=None)
                await interaction.channel.send(f"🎉 Congratulations <@{winner_id}>! You won the {view.cat_type} cat giveaway!")
            else:
                embed.description = "No one entered the giveaway 😢"
                await msg.edit(embed=embed, view=None)

class AdminPanel(discord.ui.View):
    def __init__(self, guild: discord.Guild):
        super().__init__()
        self.guild = guild
        
    @discord.ui.button(label="Give Cats", style=ButtonStyle.blurple)
    async def give_cats(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AdminPanelModal("Give Cats", self.guild))
        
    @discord.ui.button(label="Give Rains", style=ButtonStyle.blurple)
    async def give_rain(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AdminPanelModal("Give Rains", interaction.guild))
        
    @discord.ui.button(label="Give XP", style=ButtonStyle.blurple)
    async def give_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AdminPanelModal("Give XP", interaction.guild))
        
    @discord.ui.button(label="Give Packs", style=ButtonStyle.blurple)
    async def give_packs(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AdminPanelModal("Give Packs", interaction.guild))
        
    @discord.ui.button(label="Speak", style=ButtonStyle.green)
    async def speak(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AdminPanelModal("Speak", interaction.guild))
        
    @discord.ui.button(label="Start Giveaway", style=ButtonStyle.green)
    async def start_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AdminPanelModal("Start Giveaway", interaction.guild))

@bot.tree.command(description="Open the admin control panel")
@discord.app_commands.default_permissions(administrator=True)
async def admin(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
        return
        
    embed = discord.Embed(
        title="🔧 Admin Control Panel",
        description="Use the buttons below to manage KITTAYYYYYYY:",
        color=Colors.brown
    )
    await interaction.response.send_message(embed=embed, view=AdminPanel(guild=interaction.guild), ephemeral=True)

async def give_rain(channel, duration):
    # Remember the channel for rain
    channel_data = await Channel.get_or_create(channel_id=channel.id)
    channel_data.cat_rains += 1
    await channel_data.save()
    # Notify the channel that a rain event has started
    try:
        await channel.send("🌧️ A Cat Rain has started in this channel!")
    except Exception:
        pass

@bot.tree.command(description="(ADMIN) Start a cat giveaway")
@discord.app_commands.describe(
    cat_type="Type of cat to give away",
    duration="Duration (e.g. 1h, 30m, 5m, 60s)"
)
@discord.app_commands.default_permissions(administrator=True)
async def giveaway(interaction: discord.Interaction, cat_type: str, duration: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
        return
        
    if cat_type not in cattypes:
        await interaction.response.send_message(f"Invalid cat type! Valid types: {', '.join(cattypes)}", ephemeral=True)
        return
        
    duration_seconds = parse_time(duration)
    if not duration_seconds:
        await interaction.response.send_message("Invalid duration format! Use format like '5m', '1h', etc.", ephemeral=True)
        return
        
    if cat_type not in cattypes:
        await interaction.response.send_message(f"Invalid cat type! Valid types: {', '.join(cattypes)}", ephemeral=True)
        return
        
    end_time = int(time.time() + duration_seconds)
    embed = discord.Embed(
        title=f"🎉 Cat Giveaway! 🎉",
        description=f"Win a {get_emoji(cat_type.lower() + 'cat')} {cat_type} cat!\n\n"
                  f"To enter, click the button below or say `W cat!` in chat.\n"
                  f"Giveaway ends <t:{end_time}:R> at <t:{end_time}:t>",
        color=Colors.green
    )
    view = GiveawayView(cat_type)
    msg = await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("Giveaway started!", ephemeral=True)
    
    # Wait for giveaway duration
    await asyncio.sleep(duration_seconds)
    
    # Include people who said "W cat!"
    async for message in interaction.channel.history(after=msg):
        if message.content.lower().strip() in ["w cat!", "w cat"]:
            view.participants.add(message.author.id)
    
    if view.participants:
        winner_id = random.choice(list(view.participants))
        winner = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=winner_id)
        try:
            await add_cat_instances(winner, cat_type, 1)
        except Exception:
            try:
                winner[f"cat_{cat_type}"] += 1
                await winner.save()
            except Exception:
                pass
        
        embed.description = f"🎉 Winner: <@{winner_id}>! 🎉\nYou won a {get_emoji(cat_type.lower() + 'cat')} {cat_type} cat!"
        await msg.edit(embed=embed, view=None)
        await interaction.channel.send(f"🎉 Congratulations <@{winner_id}>! You won the {cat_type} cat giveaway!")
    else:
        embed.description = "No one entered the giveaway 😢"
        await msg.edit(embed=embed, view=None)

@bot.tree.command(description="(ADMIN) Prevent someone from catching cats for a certain time period")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.describe(person="A person to timeout!", timeout="How many seconds? (0 to reset)")
async def preventcatch(message: discord.Interaction, person: discord.User, timeout: int):
    if timeout < 0:
        await message.response.send_message("uhh i think time is supposed to be a number", ephemeral=True)
        return
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=person.id)
    timestamp = round(time.time()) + timeout
    user.timeout = timestamp
    await user.save()
    await message.response.send_message(
        person.name.replace("_", r"\_") + (f" can't catch cats until <t:{timestamp}:R>" if timeout > 0 else " can now catch cats again.")
    )


@bot.tree.command(description="(ADMIN) Change the cat appear timings")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.describe(
    minimum_time="In seconds, minimum possible time between spawns (leave both empty to reset)",
    maximum_time="In seconds, maximum possible time between spawns (leave both empty to reset)",
)
async def changetimings(
    message: discord.Interaction,
    minimum_time: Optional[int],
    maximum_time: Optional[int],
):
    channel = await Channel.get_or_none(channel_id=message.channel.id)
    if not channel:
        await message.response.send_message("This channel isnt setupped. Please select a valid channel.", ephemeral=True)
        return

    if not minimum_time and not maximum_time:
        # reset
        channel.spawn_times_min = 120
        channel.spawn_times_max = 1200
        await channel.save()
        await message.response.send_message("Success! This channel is now reset back to usual spawning intervals.")
    elif minimum_time and maximum_time:
        if minimum_time < 20:
            await message.response.send_message("Sorry, but minimum time must be above 20 seconds.", ephemeral=True)
            return
        if maximum_time < minimum_time:
            await message.response.send_message(
                "Sorry, but maximum time must not be less than minimum time.",
                ephemeral=True,
            )
            return

        channel.spawn_times_min = minimum_time
        channel.spawn_times_max = maximum_time
        await channel.save()

        await message.response.send_message(
            f"Success! The spawn times are now {minimum_time} to {maximum_time} seconds. Please note the changes will only apply after the next spawn."
        )
    else:
        await message.response.send_message("Please input all times.", ephemeral=True)


@bot.tree.command(description="(ADMIN) Change the cat appear and cought messages")
@discord.app_commands.default_permissions(manage_guild=True)
async def changemessage(message: discord.Interaction):
    caller = message.user
    channel = await Channel.get_or_none(channel_id=message.channel.id)
    if not channel:
        await message.response.send_message("pls setup this channel first", ephemeral=True)
        return

    # this is the silly popup when you click the button
    class InputModal(discord.ui.Modal):
        def __init__(self, type):
            super().__init__(
                title=f"Change {type} Message",
                timeout=3600,
            )

            self.type = type

            self.input = discord.ui.TextInput(
                min_length=0,
                max_length=1000,
                label="Input",
                style=discord.TextStyle.long,
                required=False,
                placeholder='{emoji} {type} has appeared! Type "cat" to catch it!',
                default=channel.appear if self.type == "Appear" else channel.cought,
            )
            self.add_item(self.input)

        async def on_submit(self, interaction: discord.Interaction):
            await channel.refresh_from_db()
            if not channel:
                await message.response.send_message("this channel is not /setup-ed", ephemeral=True)
                return
            input_value = self.input.value

            # check if all placeholders are there
            if input_value != "":
                check = ["{emoji}", "{type}"] + (["{username}", "{count}", "{time}"] if self.type == "Cought" else [])

                for i in check:
                    if i not in input_value:
                        await interaction.response.send_message(f"nuh uh! you are missing `{i}`.", ephemeral=True)
                        return
                    elif input_value.count(i) > 10:
                        await interaction.response.send_message(f"nuh uh! you are using too much of `{i}`.", ephemeral=True)
                        return

                # check there are no emojis as to not break catching
                for i in allowedemojis:
                    if i in input_value:
                        await interaction.response.send_message(f"nuh uh! you cant use `{i}`. sorry!", ephemeral=True)
                        return

                icon = get_emoji("finecat")
                await interaction.response.send_message(
                    "Success! Here is a preview:\n"
                    + input_value.replace("{emoji}", str(icon))
                    .replace("{type}", "Fine")
                    .replace("{username}", "KITTAYYYYYYY")
                    .replace("{count}", "1")
                    .replace("{time}", "69 years 420 days")
                )
            else:
                await interaction.response.send_message("Reset to defaults.")

            if self.type == "Appear":
                channel.appear = input_value
            else:
                channel.cought = input_value

            await channel.save()

    # helper to make the above popup appear
    async def ask_appear(interaction):
        nonlocal caller

        if interaction.user != caller:
            await do_funny(interaction)
            return

        modal = InputModal("Appear")
        await interaction.response.send_modal(modal)

    async def ask_catch(interaction):
        nonlocal caller

        if interaction.user != caller:
            await do_funny(interaction)
            return

        modal = InputModal("Cought")
        await interaction.response.send_modal(modal)

    embed = discord.Embed(
        title="Change appear and cought messages",
        description="""below are buttons to change them.
they are required to have all placeholders somewhere in them.
you must include the placeholders exactly like they are shown below, the values will be replaced by KITTAYYYYYYY when it uses them.
that being:

for appear:
`{emoji}`, `{type}`

for cought:
`{emoji}`, `{type}`, `{username}`, `{count}`, `{time}`

missing any of these will result in a failure.
how to do mentions: `@everyone`, `@here`, `<@userid>`, `<@&roleid>`
to get ids, run `/getid` with the thing you want to mention.
if it doesnt work make sure the bot has mention permissions.
leave blank to reset.""",
        color=Colors.brown,
    )

    button1 = Button(label="Appear Message", style=ButtonStyle.blurple)
    button1.callback = ask_appear

    button2 = Button(label="Catch Message", style=ButtonStyle.blurple)
    button2.callback = ask_catch

    view = View(timeout=VIEW_TIMEOUT)
    view.add_item(button1)
    view.add_item(button2)

    await message.response.send_message(embed=embed, view=view)


@bot.tree.command(description="Get ID of a thing")
async def getid(message: discord.Interaction, thing: discord.User | discord.Role):
    await message.response.send_message(f"The ID of {thing.mention} is {thing.id}\nyou can use it in /changemessage like this: `{thing.mention}`")


@bot.tree.command(description="Get Daily cats")
async def daily(message: discord.Interaction):
    await message.response.send_message("there is no daily cats why did you even try this")
    await achemb(message, "daily", "send")


@bot.tree.command(description="View when the last cat was caught in this channel, and when the next one might spawn")
async def last(message: discord.Interaction):
    channel = await Channel.get_or_none(channel_id=message.channel.id)
    nextpossible = ""

    try:
        lasttime = channel.lastcatches
        if int(lasttime) == 0:  # unix epoch check
            displayedtime = "forever ago"
        else:
            displayedtime = f"<t:{int(lasttime)}:R>"
    except Exception:
        displayedtime = "forever ago"

    if channel and not channel.cat:
        times = [channel.spawn_times_min, channel.spawn_times_max]
        nextpossible = f"\nthe next cat will spawn between <t:{int(lasttime) + times[0]}:R> and <t:{int(lasttime) + times[1]}:R>"

    await message.response.send_message(f"the last cat in this channel was caught {displayedtime}.{nextpossible}")


@bot.tree.command(description="View all the juicy numbers behind cat types")
async def catalogue(message: discord.Interaction):
    # Build a list of fields first, then paginate into embeds of at most 25 fields (Discord limit)
    await message.response.defer()

    fields = []
    total_weight = sum(type_dict.values())
    for cat_type in cattypes:
        in_server = await Profile.sum(f"cat_{cat_type}", f'guild_id = $1 AND "cat_{cat_type}" > 0', message.guild.id)
        title = f"{get_emoji(cat_type.lower() + 'cat')} {cat_type}"
        if in_server == 0 or not in_server:
            in_server = 0
            title = f"{get_emoji('mysterycat')} ???"

        title += f" ({round((type_dict[cat_type] / total_weight) * 100, 2)}%)"
        value = f"{round(total_weight / type_dict[cat_type], 2)} value\n{in_server:,} in this server"
        fields.append((title, value))

    # chunk into pages of 25 fields
    page_size = 25
    chunks = [fields[i : i + page_size] for i in range(0, len(fields), page_size)]

    def make_embed(page_index: int) -> discord.Embed:
        embed = discord.Embed(title=f"{get_emoji('staring_cat')} The Catalogue", color=Colors.brown)
        for name, val in chunks[page_index]:
            embed.add_field(name=name, value=val)
        embed.set_footer(text=f"Page {page_index + 1}/{len(chunks)}")
        return embed

    # If only one page, send it and return
    if len(chunks) == 1:
        await message.followup.send(embed=make_embed(0))
        return

    # Otherwise create a View with Prev/Next buttons
    class CatalogueView(View):
        def __init__(self, author_id: int):
            super().__init__(timeout=VIEW_TIMEOUT)
            self.page = 0
            self.author_id = author_id

        @discord.ui.button(label="◀ Prev", style=ButtonStyle.secondary)
        async def prev_button(self, interaction: discord.Interaction, button: Button):
            if interaction.user.id != self.author_id:
                await interaction.response.send_message("Only the command author can change pages.", ephemeral=True)
                return
            self.page = (self.page - 1) % len(chunks)
            await interaction.response.edit_message(embed=make_embed(self.page), view=self)

        @discord.ui.button(label="Next ▶", style=ButtonStyle.secondary)
        async def next_button(self, interaction: discord.Interaction, button: Button):
            if interaction.user.id != self.author_id:
                await interaction.response.send_message("Only the command author can change pages.", ephemeral=True)
                return
            self.page = (self.page + 1) % len(chunks)
            await interaction.response.edit_message(embed=make_embed(self.page), view=self)

    view = CatalogueView(author_id=message.user.id)
    await message.followup.send(embed=make_embed(0), view=view)


@bot.tree.command(name="catpedia", description="Show detailed information about a cat (Catpedia)")
@discord.app_commands.describe(catname="Name of the cat type to view")
async def catpedia(message: discord.Interaction, catname: str):
    """Show detailed information about a specific cat type.

    Displays: Name, image (if available), rarity (%), value, base HP, base DMG, and a short fun description.
    """
    await message.response.defer()

    # Normalize lookup to be case-insensitive
    match = None
    for ct in cattypes:
        if ct.lower() == catname.lower():
            match = ct
            break

    if not match:
        # allow partial matches
        for ct in cattypes:
            if catname.lower() in ct.lower():
                match = ct
                break

    if not match:
        await message.followup.send(f"Couldn't find a cat named '{catname}'. Try /catalogue to see available types.")
        return

    # Build embed data
    total_weight = sum(type_dict.values())
    rarity_pct = round((type_dict.get(match, 0) / total_weight) * 100, 2) if total_weight else 0
    value = round(total_weight / type_dict.get(match, 1), 2) if type_dict.get(match, 0) else "N/A"

    # Base stats placeholders — adjust as you design combat balancing
    base_hp = math.ceil(type_dict.get(match, 100) / 10)  # example formula
    base_dmg = max(1, math.ceil(type_dict.get(match, 100) / 50))

    # Image path: tries images/spawn/<lower>_cat.png, else fallback to images/<lower>.png
    img_path = None
    try_paths = [f"images/spawn/{match.lower()}_cat.png", f"images/{match.lower()}.png", f"images/{match.lower()}.jpg"]
    for p in try_paths:
        if os.path.exists(p):
            img_path = p
            break

    desc = (
        f"A {match} cat. {random.choice(['Loves napping in cardboard boxes.', 'Has an uncanny ability to find sunny spots.', 'May stare at you for hours without blinking.', 'Has a taste for shiny objects.'])} "
        f"{random.choice(['A friendly companion.', 'A feisty fighter.', 'Rarely shares toys.', 'Perfect for discerning collectors.'])}"
    )

    embed = discord.Embed(title=f"{get_emoji(match.lower() + 'cat')} {match}", color=Colors.brown)
    embed.add_field(name="Rarity", value=f"{rarity_pct}%")
    embed.add_field(name="Value", value=f"{value}")
    embed.add_field(name="Base HP", value=str(base_hp))
    embed.add_field(name="Base DMG", value=str(base_dmg))
    embed.add_field(name="Description", value=desc, inline=False)

    if img_path:
        try:
            file = discord.File(img_path, filename=os.path.basename(img_path))
            embed.set_image(url=f"attachment://{os.path.basename(img_path)}")
            await message.followup.send(embed=embed, file=file)
            return
        except Exception:
            pass

    await message.followup.send(embed=embed)


async def build_instances_embed(guild_id: int, user_id: int, catname: str):
    """Return an Embed for a user's instances of a given cat type, or an error string."""
    # find match
    match = None
    for ct in cattypes:
        if ct.lower() == catname.lower():
            match = ct
            break
    if not match:
        for ct in cattypes:
            if catname.lower() in ct.lower():
                match = ct
                break
    if not match:
        return f"Couldn't find a cat named '{catname}'. Try /catalogue to see available types."

    cats_list = get_user_cats(guild_id, user_id)
    filtered = [c for c in cats_list if c.get("type") == match]

    # If aggregated counters show the user has cats but the per-iinstance JSON store is empty,
    # auto-create placeholder instances to match the aggregated count. This keeps old code paths
    # that increment aggregated counters (packs, gifts, etc.) compatible with instance-based UI.
    if not filtered:
        try:
            profile = await Profile.get_or_create(guild_id=guild_id, user_id=user_id)
            total_count = profile[f"cat_{match}"] if profile else 0
        except Exception:
            total_count = 0

        existing = sum(1 for c in cats_list if c.get("type") == match)
        missing = (total_count or 0) - existing
        if missing > 0:
            # create missing instances in JSON only (don't bump aggregated counters)
            _create_instances_only(guild_id, user_id, match, missing)
            cats_list = get_user_cats(guild_id, user_id)
            filtered = [c for c in cats_list if c.get("type") == match]

    if not filtered:
        return f"You have no {match} cats."

    embed = discord.Embed(title=f"{get_emoji(match.lower() + 'cat')} Your {match} Cats", color=Colors.brown)
    lines = []
    for i, inst in enumerate(filtered, start=1):
        lines.append(f"{i}. **{inst.get('name')}** — Bond: {inst.get('bond',0)} | HP: {inst.get('hp')} | DMG: {inst.get('dmg')} (id: {inst.get('id')})")
    embed.description = "\n".join(lines[:25])
    if len(lines) > 25:
        embed.set_footer(text=f"Showing 25 of {len(lines)} — use the Next button to see more, or /play /renamecat with the index from this list")
    return embed


async def send_instances_paged(interaction: discord.Interaction, guild_id: int, user_id: int, match: str, ephemeral: bool = True):
    """Send a paginated embed (25 per page) listing instances for a given cat type.

    Assumes the caller has already deferred the interaction (so this uses followup.send).
    """
    cats_list = get_user_cats(guild_id, user_id)
    filtered = [c for c in cats_list if c.get("type") == match]
    if not filtered:
        await interaction.followup.send(f"You have no {match} cats.", ephemeral=ephemeral)
        return

    lines = [f"{i}. **{inst.get('name')}** — Bond: {inst.get('bond',0)} | HP: {inst.get('hp')} | DMG: {inst.get('dmg')} (id: {inst.get('id')})" for i, inst in enumerate(filtered, start=1)]
    page_size = 25
    chunks = [lines[i : i + page_size] for i in range(0, len(lines), page_size)]

    def make_embed(page_index: int) -> discord.Embed:
        embed = discord.Embed(title=f"{get_emoji(match.lower() + 'cat')} Your {match} Cats", color=Colors.brown)
        embed.description = "\n".join(chunks[page_index])
        embed.set_footer(text=f"Page {page_index + 1}/{len(chunks)} — Showing {len(chunks[page_index])} of {len(lines)}")
        return embed

    class InstancesView(View):
        def __init__(self, author_id: int):
            super().__init__(timeout=120)
            self.page = 0
            self.author_id = author_id
        @discord.ui.button(label="◀ Prev", style=ButtonStyle.secondary)
        async def prev_button(self, interaction2: discord.Interaction, button: Button):
            if interaction2.user.id != self.author_id:
                await do_funny(interaction2)
                return
            self.page = (self.page - 1) % len(chunks)
            await interaction2.response.edit_message(embed=make_embed(self.page), view=self)

        @discord.ui.button(label="Next ▶", style=ButtonStyle.secondary)
        async def next_button(self, interaction2: discord.Interaction, button: Button):
            if interaction2.user.id != self.author_id:
                await do_funny(interaction2)
                return
            self.page = (self.page + 1) % len(chunks)
            await interaction2.response.edit_message(embed=make_embed(self.page), view=self)

        @discord.ui.button(label="Inspect…", style=ButtonStyle.primary)
        async def inspect_button(self, interaction2: discord.Interaction, button: Button):
            """Open a modal to input the index number to inspect a single instance."""
            if interaction2.user.id != self.author_id:
                await do_funny(interaction2)
                return

            # Modal to ask for index number
            class InspectModal(discord.ui.Modal):
                def __init__(self):
                    super().__init__(title=f"Inspect a {match} instance")
                    self.index_input = discord.ui.TextInput(label="Index number (from this page)", placeholder="1", min_length=1, max_length=6, style=discord.TextStyle.short)
                    self.add_item(self.index_input)

                async def on_submit(self, modal_interaction: discord.Interaction):
                    await modal_interaction.response.defer()
                    try:
                        idx = int(self.index_input.value)
                    except Exception:
                        await modal_interaction.followup.send("Invalid number.", ephemeral=True)
                        return

                    # Recompute filtered list to ensure latest data
                    cats_list_local = get_user_cats(guild_id, modal_interaction.user.id)
                    filtered_local = [c for c in cats_list_local if c.get("type") == match]
                    if not filtered_local or idx < 1 or idx > len(filtered_local):
                        await modal_interaction.followup.send("Invalid index — run the list again to confirm indexes.", ephemeral=True)
                        return

                    inst = filtered_local[idx - 1]
                    detail_embed = build_instance_detail_embed(match, inst)
                    fav_view = FavoriteView(modal_interaction.guild.id, modal_interaction.user.id, inst.get("id"), match)
                    # set button label to reflect current state
                    try:
                        fav_btn = next((c for c in fav_view.children if isinstance(c, Button)), None)
                        if fav_btn:
                            fav_btn.label = "Unfavorite" if inst.get("favorite", False) else "Favorite"
                    except Exception:
                        pass
                    await modal_interaction.followup.send(embed=detail_embed, view=fav_view, ephemeral=ephemeral)

            try:
                await interaction2.response.send_modal(InspectModal())
            except Exception:
                # If modals fail for some reason, fallback to DM prompt
                await interaction2.response.send_message("Please enter the index to inspect as a reply to this message.", ephemeral=True)

    view = InstancesView(author_id=interaction.user.id)
    await interaction.followup.send(embed=make_embed(0), view=view, ephemeral=ephemeral)


def build_instance_detail_embed(cat_type: str, inst: dict) -> discord.Embed:
    """Build an embed showing full details for a single cat instance.

    Shows name, id, type, HP, DMG, acquired time, on_adventure, and a bond bar (0-100).
    """
    name = inst.get("name") or "Unnamed"
    cid = inst.get("id")
    bond = int(inst.get("bond", 0))
    hp = inst.get("hp")
    dmg = inst.get("dmg")
    acquired = inst.get("acquired_at")
    on_adv = inst.get("on_adventure")

    embed = discord.Embed(title=f"{get_emoji(cat_type.lower() + 'cat')} {name} — {cat_type}", color=Colors.brown)
    embed.add_field(name="ID", value=str(cid), inline=True)
    embed.add_field(name="Type", value=cat_type, inline=True)
    embed.add_field(name="HP", value=str(hp), inline=True)
    embed.add_field(name="DMG", value=str(dmg), inline=True)
    embed.add_field(name="On Adventure", value="Yes" if on_adv else "No", inline=True)

    # Bond bar: 10 segments
    filled = max(0, min(10, bond // 10))
    bar = "🟩" * filled + "⬛" * (10 - filled)
    embed.add_field(name="Bond", value=f"{bond}/100\n{bar}", inline=False)

    if acquired:
        try:
            embed.add_field(name="Acquired", value=f"<t:{int(acquired)}:f>", inline=False)
        except Exception:
            embed.add_field(name="Acquired", value=str(acquired), inline=False)

    # Favorite flag
    try:
        fav = inst.get("favorite", False)
        embed.add_field(name="Favorite", value="Yes" if fav else "No", inline=True)
    except Exception:
        pass

    # try to include an image if available
    try:
        img_path = f"images/spawn/{cat_type.lower()}_cat.png"
        if os.path.exists(img_path):
            file = discord.File(img_path, filename=os.path.basename(img_path))
            embed.set_image(url=f"attachment://{os.path.basename(img_path)}")
            # caller should send with file if desired
    except Exception:
        pass

    return embed


class FavoriteView(View):
    def __init__(self, guild_id: int, owner_id: int, inst_id: str, cat_type: str):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.inst_id = inst_id
        self.cat_type = cat_type

        # initial label will be set when view is constructed by caller if desired

    @discord.ui.button(label="Toggle Favorite", style=ButtonStyle.secondary)
    async def toggle(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.owner_id:
            await do_funny(interaction)
            return

        # load cats, find instance, toggle favorite
        cats = get_user_cats(self.guild_id, interaction.user.id)
        inst = None
        for c in cats:
            if c.get("id") == self.inst_id:
                inst = c
                break
        if not inst:
            await interaction.response.send_message("That instance was not found.", ephemeral=True)
            return

        inst["favorite"] = not bool(inst.get("favorite", False))
        save_user_cats(self.guild_id, interaction.user.id, cats)

        # rebuild embed and update message
        new_embed = build_instance_detail_embed(self.cat_type, inst)
        # update button label to reflect state
        try:
            button.label = "Unfavorite" if inst["favorite"] else "Favorite"
        except Exception:
            pass

        try:
            await interaction.response.edit_message(embed=new_embed, view=self)
        except Exception:
            # fallback: send confirmation
            await interaction.response.send_message(
                f"Set favorite = {inst['favorite']} for {inst.get('name')}", ephemeral=True
            )



async def cat_inventory_cmd(message: discord.Interaction, catname: Optional[str] = None):
    """(Internal) previously exposed as /cats — retained for internal calls if needed."""
    await message.response.defer()
    user_profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)

    if not catname:
        embed = discord.Embed(title=f"{get_emoji('staring_cat')} Your Cats", color=Colors.brown)
        for ct in cattypes:
            try:
                cnt = user_profile[f"cat_{ct}"]
            except Exception:
                cnt = 0
            if cnt:
                embed.add_field(name=f"{get_emoji(ct.lower() + 'cat')} {ct}", value=f"x{cnt}")
        await message.followup.send(embed=embed)
        return

    # normalize catname to canonical match
    match = None
    for ct in cattypes:
        if ct.lower() == catname.lower():
            match = ct
            break
    if not match:
        for ct in cattypes:
            if catname.lower() in ct.lower():
                match = ct
                break

    if not match:
        await message.followup.send(f"Couldn't find a cat named '{catname}'. Try /catalogue to see available types.")
        return

    result = await build_instances_embed(message.guild.id, message.user.id, match)
    if isinstance(result, str):
        await message.followup.send(result)
        return

    cats_list = get_user_cats(message.guild.id, message.user.id)
    filtered = [c for c in cats_list if c.get("type") == match]
    if len(filtered) > 25:
        # send a paginated view (interaction already deferred)
        await send_instances_paged(message, message.guild.id, message.user.id, match, ephemeral=False)
    else:
        # Provide an Inspect button for small lists (<=25) so users can enter an index
        class SimpleInspectView(View):
            def __init__(self, author_id: int):
                super().__init__(timeout=120)
                self.author_id = author_id

            @discord.ui.button(label="Inspect…", style=ButtonStyle.primary)
            async def inspect(self, interaction2: discord.Interaction, button: Button):
                if interaction2.user.id != self.author_id:
                    await do_funny(interaction2)
                    return

                class InspectModal(discord.ui.Modal):
                    def __init__(self):
                        super().__init__(title=f"Inspect a {match} instance")
                        self.index_input = discord.ui.TextInput(label="Index number (from this list)", placeholder="1", min_length=1, max_length=6, style=discord.TextStyle.short)
                        self.add_item(self.index_input)

                    async def on_submit(self, modal_interaction: discord.Interaction):
                        await modal_interaction.response.defer()
                        try:
                            idx = int(self.index_input.value)
                        except Exception:
                            await modal_interaction.followup.send("Invalid number.", ephemeral=True)
                            return

                        cats_list_local = get_user_cats(message.guild.id, modal_interaction.user.id)
                        filtered_local = [c for c in cats_list_local if c.get("type") == match]
                        if not filtered_local or idx < 1 or idx > len(filtered_local):
                            await modal_interaction.followup.send("Invalid index — run the list again to confirm indexes.", ephemeral=True)
                            return

                        inst = filtered_local[idx - 1]
                        detail_embed = build_instance_detail_embed(match, inst)
                        fav_view = FavoriteView(message.guild.id, modal_interaction.user.id, inst.get("id"), match)
                        try:
                            fav_btn = next((c for c in fav_view.children if isinstance(c, Button)), None)
                            if fav_btn:
                                fav_btn.label = "Unfavorite" if inst.get("favorite", False) else "Favorite"
                        except Exception:
                            pass
                        await modal_interaction.followup.send(embed=detail_embed, view=fav_view, ephemeral=True)

                try:
                    await interaction2.response.send_modal(InspectModal())
                except Exception:
                    await interaction2.response.send_message("Please enter the index to inspect as a reply to this message.", ephemeral=True)

        view = SimpleInspectView(author_id=message.user.id)
        await message.followup.send(embed=result, view=view)


@bot.tree.command(name="play", description="Play with one of your cats to increase its bond")
@discord.app_commands.describe(name="Exact name of the cat to play with")
async def play_with_cat_cmd(message: discord.Interaction, name: str):
    """Play with a cat by exact name. If multiple cats share the same name, present buttons to choose which instance."""
    await message.response.defer()

    # gather user's instances and find exact name matches (case-insensitive)
    try:
        cats_list = get_user_cats(message.guild.id, message.user.id)
    except Exception:
        cats_list = []

    matches = [(i + 1, c) for i, c in enumerate(cats_list) if (c.get("name") or "").lower() == name.lower()]

    if not matches:
        await message.followup.send(f"Couldn't find a cat named '{name}'. Check spelling or run `/cats <type>` to see your instances.", ephemeral=True)
        return

    # Helper to build an embed for a single instance
    def make_play_embed(inst: dict) -> discord.Embed:
        title = f"{get_emoji(inst.get('type', '').lower() + 'cat')} {inst.get('name')} — {inst.get('type')}"
        embed = discord.Embed(title=title, color=Colors.yellow)
        embed.add_field(name="Bond", value=f"{inst.get('bond', 0)}/100", inline=True)
        embed.add_field(name="HP", value=str(inst.get('hp')), inline=True)
        embed.add_field(name="DMG", value=str(inst.get('dmg')), inline=True)
        if inst.get('acquired_at'):
            try:
                embed.add_field(name="Acquired", value=f"<t:{int(inst.get('acquired_at'))}:f>", inline=False)
            except Exception:
                embed.add_field(name="Acquired", value=str(inst.get('acquired_at')), inline=False)
        embed.description = "Choose an action below to interact with your cat. \n\n" + (inst.get('flavor') or "")
        return embed

    # View with interactive buttons for a single instance
    class PlayView(View):
        def __init__(self, guild_id: int, owner_id: int, instance_id: str):
            super().__init__(timeout=180)
            self.guild_id = guild_id
            self.owner_id = owner_id
            self.instance_id = instance_id

        @discord.ui.button(label="Pet", style=ButtonStyle.green)
        async def pet(self, interaction2: discord.Interaction, button: Button):
            if interaction2.user.id != self.owner_id:
                await do_funny(interaction2)
                return
            await interaction2.response.defer()
            key = (self.guild_id, self.owner_id, self.instance_id)
            now_ts = time.time()
            last = pet_cooldowns.get(key, 0)
            if now_ts - last < 10:
                await interaction2.followup.send(f"You must wait {int(10 - (now_ts - last))}s before petting again.", ephemeral=True)
                return

            # fetch latest instances
            cats_now = get_user_cats(self.guild_id, self.owner_id)
            inst = next((c for c in cats_now if c.get('id') == self.instance_id), None)
            if not inst:
                await interaction2.followup.send("That instance no longer exists.", ephemeral=True)
                return

            gain = random.randint(1, 3)
            inst['bond'] = min(100, inst.get('bond', 0) + gain)
            save_user_cats(self.guild_id, self.owner_id, cats_now)
            pet_cooldowns[key] = now_ts

            # update embed in place
            try:
                new_embed = make_play_embed(inst)
                await interaction2.edit_original_response(embed=new_embed, view=self)
            except Exception:
                pass

            await interaction2.followup.send(f"You pet **{inst.get('name')}** — Bond +{gain} (now {inst['bond']}).", ephemeral=True)

        @discord.ui.button(label="Use Item", style=ButtonStyle.blurple)
        async def use_item(self, interaction2: discord.Interaction, button: Button):
            if interaction2.user.id != self.owner_id:
                await do_funny(interaction2)
                return
            await interaction2.response.defer()

            # load user's items
            items_now = get_user_items(self.guild_id, self.owner_id)
            opts = []
            emoji_map = {"luck": "luckpotion", "xp": "xppotion", "rains": "bottlerain", "ball": "goodball", "dogtreat": "dogtreat", "pancakes": "pancakes"}
            for k, v in (items_now or {}).items():
                data = SHOP_ITEMS.get(k, {})
                for tier_k, cnt in (v or {}).items():
                    if not cnt or cnt <= 0:
                        continue
                    emoji_label = get_emoji(emoji_map.get(k, k))
                    label = f"{emoji_label} {data.get('title')} {tier_k} (x{cnt})"
                    opts.append(discord.SelectOption(label=label, value=f"{k}|{tier_k}"))

            if not opts:
                await interaction2.followup.send("You have no items to use.", ephemeral=True)
                return

            parent_inter = interaction2

            class UseSelect(discord.ui.Select):
                def __init__(self, options):
                    super().__init__(placeholder="Select an item to use...", min_values=1, max_values=1, options=options)

                async def callback(self4, sel_inter: discord.Interaction):
                    if sel_inter.user.id != parent_inter.user.id:
                        await do_funny(sel_inter)
                        return
                    choice = sel_inter.data.get("values", [None])[0]
                    if not choice:
                        await sel_inter.response.send_message("Invalid selection.", ephemeral=True)
                        return
                    key_local, tier_local = choice.split("|")
                    # re-load items to avoid races
                    cur_items = get_user_items(parent_inter.guild.id, parent_inter.user.id)
                    have = cur_items.get(key_local, {}).get(tier_local, 0)
                    if have <= 0:
                        await sel_inter.response.send_message("You don't have that item anymore.", ephemeral=True)
                        return

                    # If the item targets a specific instance, apply directly to this instance
                    if key_local in ("ball", "dogtreat", "pancakes"):
                        cats_now = get_user_cats(self.guild_id, self.owner_id)
                        inst = next((c for c in cats_now if c.get('id') == self.instance_id), None)
                        if not inst:
                            await sel_inter.response.send_message("That instance no longer exists.", ephemeral=True)
                            return

                        # decrement one use
                        cur_items.setdefault(key_local, {})[tier_local] = max(0, have - 1)
                        save_user_items(parent_inter.guild.id, parent_inter.user.id, cur_items)

                        bond_amt = SHOP_ITEMS.get(key_local, {}).get('tiers', {}).get(tier_local, {}).get('bond', 0)
                        if key_local == 'pancakes' and bond_amt >= 100:
                            inst['bond'] = 100
                        else:
                            inst['bond'] = min(100, inst.get('bond', 0) + int(bond_amt))
                        save_user_cats(parent_inter.guild.id, parent_inter.user.id, cats_now)

                        # update embed in place
                        try:
                            new_embed = make_play_embed(inst)
                            await parent_inter.edit_original_response(embed=new_embed, view=self)
                        except Exception:
                            pass

                        await sel_inter.followup.send(f"Used {SHOP_ITEMS[key_local]['title']} {tier_local} on **{inst.get('name')}** — Bond now {inst['bond']}.", ephemeral=True)
                        return

                    # Default behavior for other item types (rains, luck, xp)
                    cur_items.setdefault(key_local, {})[tier_local] = max(0, have - 1)
                    save_user_items(parent_inter.guild.id, parent_inter.user.id, cur_items)

                    try:
                        if key_local == 'rains':
                            minutes = SHOP_ITEMS[key_local]['tiers'][tier_local].get('minutes', 0)
                            user_obj = await User.get_or_create(user_id=parent_inter.user.id)
                            if not user_obj.rain_minutes:
                                user_obj.rain_minutes = 0
                            user_obj.rain_minutes += int(minutes)
                            await user_obj.save()
                            await sel_inter.response.send_message(f"Used {SHOP_ITEMS[key_local]['title']} {tier_local}: added {minutes} rain minutes to your account.", ephemeral=True)
                            return

                        if key_local in ('luck', 'xp'):
                            effect = SHOP_ITEMS[key_local]['tiers'][tier_local].get('effect', 0)
                            dur_map = {'I': 3600, 'II': 10800, 'III': 21600}
                            duration = dur_map.get(tier_local, 3600)
                            now_ts = int(time.time())
                            k = _get_buffs_key(parent_inter.guild.id, parent_inter.user.id)
                            ITEM_BUFFS.setdefault(k, {})[key_local] = {"mult": effect, "until": now_ts + duration}
                            try:
                                save_item_buffs()
                            except Exception:
                                pass
                            await sel_inter.response.send_message(f"Used {SHOP_ITEMS[key_local]['title']} {tier_local}: +{int(effect*100)}% {key_local} for {duration//3600}h. Expires <t:{now_ts + duration}:R>.", ephemeral=True)
                            return

                        await sel_inter.response.send_message(f"Used {SHOP_ITEMS[key_local]['title']} {tier_local}.", ephemeral=True)
                    except Exception:
                        await sel_inter.response.send_message("Failed to apply item effect.", ephemeral=True)

            sel_view = View(timeout=120)
            sel_view.add_item(UseSelect(opts))
            try:
                await interaction2.followup.send("Choose an item to use:", view=sel_view, ephemeral=True)
            except Exception:
                await interaction2.response.send_message("Could not open item selector.", ephemeral=True)

        @discord.ui.button(label="Close", style=ButtonStyle.secondary)
        async def close(self, interaction2: discord.Interaction, button: Button):
            if interaction2.user.id != self.owner_id:
                await do_funny(interaction2)
                return
            # disable all buttons
            for child in list(self.children):
                try:
                    child.disabled = True
                except Exception:
                    pass
            try:
                await interaction2.edit_original_response(view=self)
            except Exception:
                pass

    # Present choices (if multiple matches) or show the play UI for the single match
    if len(matches) == 1:
        idx, inst = matches[0]
        # show embed + buttons
        embed = make_play_embed(inst)
        # try to attach image if available
        file_to_send = None
        try:
            img_path = f"images/spawn/{inst.get('type', '').lower()}_cat.png"
            if os.path.exists(img_path):
                file_to_send = discord.File(img_path, filename=os.path.basename(img_path))
        except Exception:
            file_to_send = None

        view = PlayView(message.guild.id, message.user.id, inst.get('id'))
        try:
            if file_to_send:
                await message.followup.send(embed=embed, view=view, file=file_to_send)
            else:
                await message.followup.send(embed=embed, view=view)
        except Exception:
            await message.followup.send(embed=embed, view=view, ephemeral=True)
        return

    # multiple matches — present a chooser with buttons for each instance that opens the PlayView
    class ChooseView(View):
        def __init__(self, author_id: int, matches_list: list[tuple[int, dict]]):
            super().__init__(timeout=120)
            self.author_id = author_id
            for idx, inst in matches_list[:25]:
                label = f"#{idx} {inst.get('type', 'Unknown')} — {inst.get('name')}"
                btn = Button(label=label, custom_id=f"choose_{idx}")

                async def cb(interaction2: discord.Interaction, button: Button, idx_local=idx):
                    if interaction2.user.id != self.author_id:
                        await do_funny(interaction2)
                        return
                    await interaction2.response.defer()
                    cats_now = get_user_cats(message.guild.id, interaction2.user.id)
                    if idx_local < 1 or idx_local > len(cats_now):
                        await interaction2.followup.send("That instance no longer exists.", ephemeral=True)
                        return
                    inst2 = cats_now[idx_local - 1]
                    if (inst2.get('name') or '').lower() != name.lower():
                        await interaction2.followup.send("The instance name no longer matches. Try the command again.", ephemeral=True)
                        return

                    embed = make_play_embed(inst2)
                    file_to_send = None
                    try:
                        img_path = f"images/spawn/{inst2.get('type', '').lower()}_cat.png"
                        if os.path.exists(img_path):
                            file_to_send = discord.File(img_path, filename=os.path.basename(img_path))
                    except Exception:
                        file_to_send = None

                    view = PlayView(message.guild.id, interaction2.user.id, inst2.get('id'))
                    try:
                        if file_to_send:
                            await interaction2.followup.send(embed=embed, view=view, file=file_to_send, ephemeral=True)
                        else:
                            await interaction2.followup.send(embed=embed, view=view, ephemeral=True)
                    except Exception:
                        await interaction2.followup.send(embed=embed, ephemeral=True)

                btn.callback = cb
                self.add_item(btn)

    view = ChooseView(author_id=message.user.id, matches_list=matches)
    await message.followup.send(f"Multiple cats named '{name}' found — choose which one to play with:", view=view, ephemeral=True)


@bot.tree.command(name="renamecat", description="Rename one of your cats")
@discord.app_commands.autocomplete(catname=cat_type_autocomplete)
@discord.app_commands.describe(catname="Cat type", index="Index from /cats view (1-based)", new_name="New name for the cat")
async def rename_cat_cmd(message: discord.Interaction, catname: str, index: int, new_name: str):
    await message.response.defer()
    match = None
    for ct in cattypes:
        if ct.lower() == catname.lower():
            match = ct
            break
    if not match:
        for ct in cattypes:
            if catname.lower() in ct.lower():
                match = ct
                break
    if not match:
        await message.followup.send(f"Couldn't find a cat type named '{catname}'.")
        return

    cats_list = get_user_cats(message.guild.id, message.user.id)
    filtered = [c for c in cats_list if c.get("type") == match]
    if not filtered or index < 1 or index > len(filtered):
        await message.followup.send(f"Invalid index — run `/cats {catname}` to see indexes.")
        return

    inst = filtered[index - 1]
    inst["name"] = new_name
    save_user_cats(message.guild.id, message.user.id, cats_list)
    await message.followup.send(f"Renamed cat #{index} ({match}) to **{new_name}**.")


async def gen_stats(profile, star):
    stats = []
    user = await User.get_or_create(user_id=profile.user_id)

    # catching
    stats.append([get_emoji("staring_cat"), "Catching"])
    stats.append(["catches", "🐈", f"Catches: {profile.total_catches:,}{star}"])
    catch_time = "---" if profile.time >= 99999999999999 else round(profile.time, 3)
    slow_time = "---" if profile.timeslow == 0 else round(profile.timeslow / 3600, 2)
    stats.append(["time_records", "⏱️", f"Fastest: {catch_time}s, Slowest: {slow_time}h"])
    if profile.total_catches - profile.rain_participations != 0:
        stats.append(
            ["average_time", "⏱️", f"Average catch time: {profile.total_catch_time / (profile.total_catches - profile.rain_participations):,.2f}s{star}"]
        )
    else:
        stats.append(["average_time", "⏱️", f"Average catch time: N/A{star}"])
    stats.append(["purrfect_catches", "✨", f"Purrfect catches: {profile.perfection_count:,}{star}"])

    # catching boosts
    stats.append([get_emoji("prism"), "Boosts"])
    prisms_crafted = await Prism.count("guild_id = $1 AND user_id = $2", profile.guild_id, profile.user_id)
    boosts_done = await Prism.sum("catches_boosted", "guild_id = $1 AND user_id = $2", profile.guild_id, profile.user_id)
    stats.append(["prism_crafted", get_emoji("prism"), f"Prisms crafted: {prisms_crafted:,}"])
    stats.append(["boosts_done", get_emoji("prism"), f"Boosts by owned prisms: {boosts_done:,}{star}"])
    stats.append(["boosted_catches", get_emoji("prism"), f"Prism-boosted catches: {profile.boosted_catches:,}{star}"])
    stats.append(["cataine_activations", "🧂", f"Cataine activations: {profile.cataine_activations:,}"])
    stats.append(["cataine_bought", "🧂", f"Cataine bought: {profile.cataine_bought:,}"])

    # voting
    stats.append([get_emoji("topgg"), "Voting"])
    stats.append(["total_votes", get_emoji("topgg"), f"Total votes: {user.total_votes:,}{star}"])
    stats.append(["current_vote_streak", "🔥", f"Current vote streak: {user.vote_streak} (max {max(user.vote_streak, user.max_vote_streak):,}){star}"])
    if user.vote_time_topgg + 43200 > time.time():
        stats.append(["can_vote", get_emoji("topgg"), f"Can vote <t:{user.vote_time_topgg + 43200}:R>"])
    else:
        stats.append(["can_vote", get_emoji("topgg"), "Can vote!"])

    # battlepass
    stats.append(["⬆️", "Cattlepass"])
    seasons_complete = 0
    levels_complete = 0
    max_level = 0
    total_xp = 0
    # past seasons
    for season in profile.bp_history.split(";"):
        if not season:
            break
        season_num, season_lvl, season_progress = map(int, season.split(","))
        if season_num == 0:
            continue
        levels_complete += season_lvl
        total_xp += season_progress
        if season_lvl > 30:
            seasons_complete += 1
            total_xp += 1500 * (season_lvl - 31)
        if season_lvl > max_level:
            max_level = season_lvl

        for num, level in enumerate(battle["seasons"][str(season_num)]):
            if num >= season_lvl:
                break
            total_xp += level["xp"]
    # current season
    if profile.season != 0:
        levels_complete += profile.battlepass
        total_xp += profile.progress
        if profile.battlepass > 30:
            seasons_complete += 1
            total_xp += 1500 * (profile.battlepass - 31)
        if profile.battlepass > max_level:
            max_level = profile.battlepass

        for num, level in enumerate(battle["seasons"][str(profile.season)]):
            if num >= profile.battlepass:
                break
            total_xp += level["xp"]
    current_packs = 0
    for pack in pack_data:
        current_packs += profile[f"pack_{pack['name'].lower()}"]
    stats.append(["quests_completed", "✅", f"Quests completed: {profile.quests_completed:,}{star}"])
    stats.append(["seasons_completed", "🏅", f"Cattlepass seasons completed: {seasons_complete:,}"])
    stats.append(["levels_completed", "✅", f"Cattlepass levels completed: {levels_complete:,}"])
    stats.append(["packs_in_inventory", get_emoji("woodenpack"), f"Packs in inventory: {current_packs:,}"])
    stats.append(["packs_opened", get_emoji("goldpack"), f"Packs opened: {profile.packs_opened:,}"])
    stats.append(["pack_upgrades", get_emoji("diamondpack"), f"Pack upgrades: {profile.pack_upgrades:,}"])
    stats.append(["highest_ever_level", "🏆", f"Highest ever Cattlepass level: {max_level:,}"])
    stats.append(["total_xp_earned", "🧮", f"Total Cattlepass XP earned: {total_xp:,}"])

    # rains & supporter
    stats.append(["☔", "Rains"])
    stats.append(["current_rain_minutes", "☔", f"Current rain minutes: {user.rain_minutes:,}"])
    stats.append(["supporter", "👑", "Ever bought rains: " + ("Yes" if user.premium else "No")])
    stats.append(["cats_caught_during_rains", "☔", f"Cats caught during rains: {profile.rain_participations:,}{star}"])
    stats.append(["rain_minutes_started", "☔", f"Rain minutes started: {profile.rain_minutes_started:,}{star}"])

    # gambling
    stats.append(["🎰", "Gambling"])
    stats.append(["casino_spins", "🎰", f"Casino spins: {profile.gambles:,}"])
    stats.append(["slot_spins", "🎰", f"Slot spins: {profile.slot_spins:,}"])
    stats.append(["slot_wins", "🎰", f"Slot wins: {profile.slot_wins:,}"])
    stats.append(["slot_big_wins", "🎰", f"Slot big wins: {profile.slot_big_wins:,}"])

    # tic tac toe
    stats.append(["⭕", "Tic Tac Toe"])
    stats.append(["ttc_games", "⭕", f"Tic Tac Toe games played: {profile.ttt_played:,}"])
    stats.append(["ttc_wins", "⭕", f"Tic Tac Toe wins: {profile.ttt_won:,}"])
    stats.append(["ttc_draws", "⭕", f"Tic Tac Toe draws: {profile.ttt_draws:,}"])
    if profile.ttt_played != 0:
        stats.append(["ttc_win_rate", "⭕", f"Tic Tac Toe win rate: {(profile.ttt_won + profile.ttt_draws) / profile.ttt_played * 100:.2f}%"])
    else:
        stats.append(["ttc_win_rate", "⭕", "Tic Tac Toe win rate: 0%"])

    if (profile.guild_id, profile.user_id) not in temp_cookie_storage.keys():
        cookies = profile.cookies
    else:
        cookies = temp_cookie_storage[(profile.guild_id, profile.user_id)]
    # misc
    stats.append(["❓", "Misc"])
    stats.append(["facts_read", "🧐", f"Facts read: {profile.facts:,}"])
    stats.append(["cookies", "🍪", f"Cookies clicked: {cookies:,}"])
    stats.append(["pig_high_score", "🎲", f"Pig high score: {profile.best_pig_score:,}"])
    stats.append(["private_embed_clicks", get_emoji("pointlaugh"), f"Private embed clicks: {profile.funny:,}"])
    stats.append(["reminders_set", "⏰", f"Reminders set: {profile.reminders_set:,}{star}"])
    stats.append(["cats_gifted", "🎁", f"Cats gifted: {profile.cats_gifted:,}{star}"])
    stats.append(["cats_received_as_gift", "🎁", f"Cats received as gift: {profile.cat_gifts_recieved:,}{star}"])
    stats.append(["trades_completed", "💱", f"Trades completed: {profile.trades_completed}{star}"])
    stats.append(["cats_traded", "💱", f"Cats traded: {profile.cats_traded:,}{star}"])
    if profile.user_id == 553093932012011520:
        stats.append(["owner", get_emoji("neocat"), "a cute catgirl :3"])
    return stats


@bot.tree.command(name="stats", description="View some advanced stats")
@discord.app_commands.rename(person_id="user")
@discord.app_commands.describe(person_id="Person to view the stats of!")
async def stats_command(message: discord.Interaction, person_id: Optional[discord.User] = None):
    await message.response.defer()
    try:
        if not person_id:
            person_id = message.user
        else:
            # Try to get member directly from the guild first
            member = message.guild.get_member(person_id.id)
            if not member:
                try:
                    member = await message.guild.fetch_member(person_id.id)
                except discord.NotFound:
                    print(f"[DEBUG] User not found in guild: {person_id.id}")
                    await message.followup.send("Couldn't find that user in this server!", ephemeral=True)
                    return
            person_id = member
    except Exception as e:
        print(f"[ERROR] Failed to resolve user in stats: {str(e)}")
        await message.followup.send("There was an error finding that user. Make sure to use their Discord name, ID, or mention them!", ephemeral=True)
        return
    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id.id)
    star = "*" if not profile.new_user else ""

    stats = await gen_stats(profile, star)
    stats_string = ""
    for stat in stats:
        if len(stat) == 2:
            # category
            stats_string += f"\n{stat[0]} __{stat[1]}__\n"
        elif len(stat) == 3:
            # stat
            stats_string += f"{stat[2]}\n"
    if star:
        stats_string += "\n\\*this stat is only tracked since February 2025"

    embedVar = discord.Embed(title=f"{person_id.name}'s Stats", color=Colors.brown, description=stats_string)
    await message.followup.send(embed=embedVar)


async def gen_inventory(message, person_id):
    # check if we are viewing our own inv or some other person
    if person_id is None:
        person_id = message.user
    me = bool(person_id == message.user)
    person = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id.id)
    user = await User.get_or_create(user_id=person_id.id)

    # around here we count aches
    unlocked = 0
    minus_achs = 0
    minus_achs_count = 0
    for k in ach_names:
        is_ach_hidden = ach_list[k]["category"] == "Hidden"
        if is_ach_hidden:
            minus_achs_count += 1
        if person[k]:
            if is_ach_hidden:
                minus_achs += 1
            else:
                unlocked += 1
    total_achs = len(ach_list) - minus_achs_count
    minus_achs = "" if minus_achs == 0 else f" + {minus_achs}"

    # count prism stuff
    prisms = await Prism.collect_limit(["name"], "guild_id = $1 AND user_id = $2", message.guild.id, person_id.id)
    total_count = await Prism.count("guild_id = $1", message.guild.id)
    user_count = len(prisms)
    global_boost = 0.06 * math.log(2 * total_count + 1)
    prism_boost = round((global_boost + 0.03 * math.log(2 * user_count + 1)) * 100, 3)
    if len(prisms) == 0:
        prism_list = "None"
    elif len(prisms) <= 3:
        prism_list = ", ".join([i.name for i in prisms])
    else:
        prism_list = f"{prisms[0].name}, {prisms[1].name}, {len(prisms) - 2} more..."

    emoji_prefix = str(user.emoji) + " " if user.emoji else ""

    if user.color:
        color = user.color
    else:
        color = "#6E593C"

    await refresh_quests(person)
    try:
        needed_xp = battle["seasons"][str(person.season)][person.battlepass]["xp"]
    except Exception:
        needed_xp = 1500

    stats = await gen_stats(person, "")
    highlighted_stat = None
    for stat in stats:
        if stat[0] == person.highlighted_stat:
            highlighted_stat = stat
            break
    if not highlighted_stat:
        for stat in stats:
            if stat[0] == "time_records":
                highlighted_stat = stat
                break

    embedVar = discord.Embed(
        title=f"{emoji_prefix}{person_id.name.replace('_', r'\_')}",
        description=f"{highlighted_stat[1]} {highlighted_stat[2]}\n{get_emoji('ach')} Achievements: {unlocked}/{total_achs}{minus_achs}\n⬆️ Battlepass Level {person.battlepass} ({person.progress}/{needed_xp} XP)",
        color=discord.Colour.from_str(color),
    )

    debt = False
    give_collector = True
    total = 0
    valuenum = 0

    # for every cat, check if on adventure
    cat_desc = ""
    user_adv = active_adventures.get(str(person_id.id))
    adventuring_cat = user_adv["cat"] if user_adv else None
    
    for i in cattypes:
        icon = get_emoji(i.lower() + "cat")
        cat_num = person[f"cat_{i}"]
        if cat_num < 0:
            debt = True
        if cat_num != 0:
            total += cat_num
            valuenum += (sum(type_dict.values()) / type_dict[i]) * cat_num
            if i == adventuring_cat:
                cat_desc += f"{icon} **{i}** {cat_num:,} (1 On Adventure)\n"
            else:
                cat_desc += f"{icon} **{i}** {cat_num:,}\n"
        else:
            give_collector = False

    if user.custom:
        icon = get_emoji(re.sub(r"[^a-zA-Z0-9]", "", user.custom).lower() + "cat")
        cat_desc += f"{icon} **{user.custom}** {user.custom_num:,}"

    if len(cat_desc) == 0:
        cat_desc = f"u hav no cats {get_emoji('cat_cry')}"

    if embedVar.description:
        embedVar.description += f"\n{get_emoji('staring_cat')} Cats: {total:,}, Value: {round(valuenum):,}\nKibble: {person.kibble:,}\n{get_emoji('prism')} Prisms: {prism_list} ({prism_boost}%)\n\n{cat_desc}"

    if user.image.startswith("https://cdn.discordapp.com/attachments/"):
        embedVar.set_thumbnail(url=user.image)

    if me:
        # give some aches if we are vieweing our own inventory
        if len(news_list) > len(user.news_state.strip()) or "0" in user.news_state.strip()[-4:]:
            embedVar.set_author(name="You have unread news! /news")

        if give_collector:
            await achemb(message, "collecter", "send")

        if person.time <= 5:
            await achemb(message, "fast_catcher", "send")
        if person.timeslow >= 3600:
            await achemb(message, "slow_catcher", "send")

        if total >= 100:
            await achemb(message, "second", "send")
        if total >= 1000:
            await achemb(message, "third", "send")
        if total >= 10000:
            await achemb(message, "fourth", "send")

        if unlocked >= 15:
            await achemb(message, "achiever", "send")

        if debt:
            bot.loop.create_task(debt_cutscene(message, person))

    return embedVar


def gen_items_embed(message, person_id) -> discord.Embed:
    """Build an embed showing a user's item inventory (from data/items.json)."""
    items = get_user_items(message.guild.id, person_id.id)
    # emoji map for items
    emoji_map = {"luck": "luckpotion", "xp": "xppotion", "rains": "bottlerain", "ball": "goodball", "dogtreat": "dogtreat", "pancakes": "pancakes"}
    embed = discord.Embed(title=f"{get_emoji('staring_cat')} {person_id.name}'s Items", color=Colors.brown)
    if not items:
        embed.description = "No items yet. Visit /shop to buy items!"
        return embed

    lines = []
    # format per-category
    # extend emoji map for new items
    emoji_map.update({"ball": "goodball", "dogtreat": "dogtreat", "pancakes": "pancakes"})
    for key, data in SHOP_ITEMS.items():
        title = data.get('title')
        emoji_label = get_emoji(emoji_map.get(key, key))
        title_display = f"{emoji_label} {title}"
        tiers = []
        for tier_key in sorted(data.get('tiers', {}).keys()):
            cnt = items.get(key, {}).get(tier_key, 0)
            tiers.append(f"{tier_key}: {cnt}")
        if tiers:
            lines.append(f"**{title_display}** — {', '.join(tiers)}")

    embed.description = "\n".join(lines)
    return embed


@bot.tree.command(description="View your inventory")
@discord.app_commands.rename(person_id="user")
@discord.app_commands.describe(person_id="Person to view the inventory of!")
async def inventory(message: discord.Interaction, person_id: Optional[discord.User] = None):
    await message.response.defer()
    try:
        if not person_id:
            person_id = message.user
        else:
            # Try to get member directly from the guild first
            member = message.guild.get_member(person_id.id)
            if not member:
                try:
                    member = await message.guild.fetch_member(person_id.id)
                except discord.NotFound:
                    print(f"[DEBUG] User not found in guild: {person_id.id}")
                    await message.followup.send("Couldn't find that user in this server!", ephemeral=True)
                    return
            person_id = member
    except Exception as e:
        print(f"[ERROR] Failed to resolve user in inventory: {str(e)}")
        await message.followup.send("There was an error finding that user. Make sure to use their Discord name, ID, or mention them!", ephemeral=True)
        return
    person = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id.id)
    user = await User.get_or_create(user_id=message.user.id)
    stats = await gen_stats(person, "")

    async def edit_profile(interaction: discord.Interaction):
        if interaction.user.id != person_id.id:
            await do_funny(interaction)
            return

        def stat_select(category):
            options = [discord.SelectOption(emoji="⬅️", label="Back", value="back")]
            track = False
            for stat in stats:
                if len(stat) == 2:
                    track = bool(stat[1] == category)
                if len(stat) == 3 and track:
                    options.append(discord.SelectOption(value=stat[0], emoji=stat[1], label=stat[2]))

            select = discord.ui.Select(placeholder="Edit highlighted stat... (2/2)", options=options)

            async def select_callback(interaction: discord.Interaction):
                await interaction.response.defer()
                if select.values[0] == "back":
                    view = View(timeout=VIEW_TIMEOUT)
                    view.add_item(category_select())
                    await interaction.edit_original_response(view=view)
                else:
                    # update the stat
                    person.highlighted_stat = select.values[0]
                    await person.save()
                    await interaction.edit_original_response(content="Highlighted stat updated!", embed=None, view=None)

            select.callback = select_callback
            return select

        def category_select():
            options = []
            for stat in stats:
                if len(stat) != 2:
                    continue
                options.append(discord.SelectOption(emoji=stat[0], label=stat[1], value=stat[1]))

            select = discord.ui.Select(placeholder="Edit highlighted stat... (1/2)", options=options)

            async def select_callback(interaction: discord.Interaction):
                # im 13 and this is deep (nesting)
                # and also please dont think about the fact this is async inside of sync :3
                await interaction.response.defer()
                view = View(timeout=VIEW_TIMEOUT)
                view.add_item(stat_select(select.values[0]))
                await interaction.edit_original_response(view=view)

            select.callback = select_callback
            return select

        highlighted_stat = None
        for stat in stats:
            if stat[0] == person.highlighted_stat:
                highlighted_stat = stat
                break
        if not highlighted_stat:
            for stat in stats:
                if stat[0] == "time_records":
                    highlighted_stat = stat
                    break

        view = View(timeout=VIEW_TIMEOUT)
        view.add_item(category_select())

        if user.premium:
            if not user.color:
                user.color = "#6E593C"
            description = f"""👑 __Supporter Settings__
Global, change with `/editprofile`.
**Color**: {user.color.lower() if user.color.upper() not in ["", "#6E593C"] else "Default"}
**Emoji**: {user.emoji if user.emoji else "None"}
**Image**: {"Yes" if user.image.startswith("https://cdn.discordapp.com/attachments/") else "No"}

__Highlighted Stat__
{highlighted_stat[1]} {highlighted_stat[2]}"""

            embed = discord.Embed(
                title=f"{(user.emoji + ' ') if user.emoji else ''}Edit Profile", description=description, color=discord.Colour.from_str(user.color)
            )
            if user.image.startswith("https://cdn.discordapp.com/attachments/"):
                embed.set_thumbnail(url=user.image)

        else:
            description = f"""👑 __Supporter Settings__
Global, buy anything from [the store](https://catbot.shop) to unlock.
👑 **Color**
👑 **Emoji**
👑 **Image**

__Highlighted Stat__
{highlighted_stat[1]} {highlighted_stat[2]}"""

            embed = discord.Embed(title="Edit Profile", description=description, color=Colors.brown)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    embedVar = await gen_inventory(message, person_id)

    embedVar.set_footer(text=rain_shill)

    if person_id.id == message.user.id:
        view = View(timeout=VIEW_TIMEOUT)
        btn = Button(emoji="📝", label="Edit", style=discord.ButtonStyle.blurple)
        btn.callback = edit_profile
        view.add_item(btn)
        # More details button: opens a small selector to pick a cat type and view instances
        async def more_details_callback(interaction: discord.Interaction):
            if interaction.user.id != message.user.id:
                await do_funny(interaction)
                return
            # build a paginated select menu of cattypes (Discord limits options to 25)
            per_page = 25
            pages = [cattypes[i : i + per_page] for i in range(0, len(cattypes), per_page)]
            page = 0

            class CatSelectView(View):
                def __init__(self, author_id: int):
                    super().__init__(timeout=120)
                    self.author_id = author_id
                    self.page = 0
                    self.select = self.build_select()
                    self.add_item(self.select)

                    # Prev/Next buttons only if multiple pages
                    if len(pages) > 1:
                        prev_btn = Button(label="◀ Prev", style=ButtonStyle.secondary)
                        next_btn = Button(label="Next ▶", style=ButtonStyle.secondary)
                        prev_btn.callback = self.prev_page
                        next_btn.callback = self.next_page
                        self.add_item(prev_btn)
                        self.add_item(next_btn)

                def build_select(self):
                    opts = [discord.SelectOption(label=ct, emoji=get_emoji(ct.lower() + "cat"), value=ct) for ct in pages[self.page]]
                    select = discord.ui.Select(placeholder="Select a cat type to inspect...", options=opts, min_values=1, max_values=1, custom_id=f"catselect_{uuid.uuid4().hex}")

                    async def select_callback(interaction: discord.Interaction):
                        if interaction.user.id != self.author_id:
                            await do_funny(interaction)
                            return
                        await interaction.response.defer()
                        chosen = select.values[0]
                        # allow build_instances_embed to auto-sync missing instances
                        result = await build_instances_embed(interaction.guild.id, interaction.user.id, chosen)
                        if isinstance(result, str):
                            await interaction.followup.send(result, ephemeral=True)
                            return

                        # after auto-sync, check how many instances exist and page if needed
                        cats_list = get_user_cats(interaction.guild.id, interaction.user.id)
                        filtered = [c for c in cats_list if c.get("type") == chosen]
                        if len(filtered) > 25:
                            await send_instances_paged(interaction, interaction.guild.id, interaction.user.id, chosen, ephemeral=True)
                        else:
                            await interaction.followup.send(embed=result, ephemeral=True)

                        # disable the select and navigation so it can't be reused and cause interaction errors
                        try:
                            for child in list(self.children):
                                try:
                                    child.disabled = True
                                except Exception:
                                    pass
                            await interaction.edit_original_response(view=self)
                        except Exception:
                            pass

                        try:
                            self.stop()
                        except Exception:
                            pass

                    select.callback = select_callback
                    return select

                async def prev_page(self, interaction: discord.Interaction):
                    if interaction.user.id != self.author_id:
                        await do_funny(interaction)
                        return
                    self.page = (self.page - 1) % len(pages)
                    # rebuild view safely
                    try:
                        self.clear_items()
                    except Exception:
                        pass
                    self.select = self.build_select()
                    self.add_item(self.select)
                    if len(pages) > 1:
                        prev_btn = Button(label="◀ Prev", style=ButtonStyle.secondary, custom_id=f"prev_{uuid.uuid4().hex}")
                        next_btn = Button(label="Next ▶", style=ButtonStyle.secondary, custom_id=f"next_{uuid.uuid4().hex}")
                        prev_btn.callback = self.prev_page
                        next_btn.callback = self.next_page
                        self.add_item(prev_btn)
                        self.add_item(next_btn)
                    await interaction.response.edit_message(view=self)

                async def next_page(self, interaction: discord.Interaction):
                    if interaction.user.id != self.author_id:
                        await do_funny(interaction)
                        return
                    self.page = (self.page + 1) % len(pages)
                    try:
                        self.clear_items()
                    except Exception:
                        pass
                    self.select = self.build_select()
                    self.add_item(self.select)
                    if len(pages) > 1:
                        prev_btn = Button(label="◀ Prev", style=ButtonStyle.secondary, custom_id=f"prev_{uuid.uuid4().hex}")
                        next_btn = Button(label="Next ▶", style=ButtonStyle.secondary, custom_id=f"next_{uuid.uuid4().hex}")
                        prev_btn.callback = self.prev_page
                        next_btn.callback = self.next_page
                        self.add_item(prev_btn)
                        self.add_item(next_btn)
                    await interaction.response.edit_message(view=self)

            sel_view = CatSelectView(author_id=interaction.user.id)
            await interaction.response.send_message("Choose a cat type:", view=sel_view, ephemeral=True)

        more_btn = Button(label="More details..", style=discord.ButtonStyle.gray)
        more_btn.callback = more_details_callback
        view.add_item(more_btn)
        # Add switch button to items view
        async def switch_to_items(interaction2: discord.Interaction):
            if interaction2.user.id != message.user.id:
                await do_funny(interaction2)
                return
            items_embed = gen_items_embed(message, message.user)
            # View with switch back button and (for owner) a "Use Item" flow
            class ItemsView(View):
                def __init__(self):
                    super().__init__(timeout=VIEW_TIMEOUT)

                @discord.ui.button(label="Back to Cats", style=ButtonStyle.secondary)
                async def back(self, interaction3: discord.Interaction, button: Button):
                    if interaction3.user.id != message.user.id:
                        await do_funny(interaction3)
                        return
                    await interaction3.response.edit_message(embed=embedVar, view=view)

                @discord.ui.button(label="Use Item", style=ButtonStyle.blurple)
                async def use_item(self, interaction3: discord.Interaction, button: Button):
                    if interaction3.user.id != message.user.id:
                        await do_funny(interaction3)
                        return
                    await interaction3.response.defer()
                    items_now = get_user_items(message.guild.id, message.user.id)
                    opts = []
                    emoji_map = {"luck": "luckpotion", "xp": "xppotion", "rains": "bottlerain"}
                    for k, v in items_now.items():
                        data = SHOP_ITEMS.get(k, {})
                        for tier_k, cnt in (v or {}).items():
                            if not cnt or cnt <= 0:
                                continue
                            emoji_label = get_emoji(emoji_map.get(k, k))
                            label = f"{emoji_label} {data.get('title')} {tier_k} (x{cnt})"
                            opts.append(discord.SelectOption(label=label, value=f"{k}|{tier_k}"))

                    if not opts:
                        await interaction3.followup.send("You have no items to use.", ephemeral=True)
                        return

                    class UseSelect(discord.ui.Select):
                        def __init__(self, options):
                            super().__init__(placeholder="Select an item to use...", min_values=1, max_values=1, options=options)

                        async def callback(self4, sel_inter: discord.Interaction):
                            if sel_inter.user.id != message.user.id:
                                await do_funny(sel_inter)
                                return
                            choice = sel_inter.data.get("values", [None])[0]
                            if not choice:
                                await sel_inter.response.send_message("Invalid selection.", ephemeral=True)
                                return
                            key_local, tier_local = choice.split("|")
                            # re-load items to avoid races
                            cur_items = get_user_items(message.guild.id, message.user.id)
                            have = cur_items.get(key_local, {}).get(tier_local, 0)
                            if have <= 0:
                                await sel_inter.response.send_message("You don't have that item anymore.", ephemeral=True)
                                return

                            # Special handling for toys/food which must be applied to a specific cat instance
                            if key_local in ("ball", "dogtreat", "pancakes"):
                                # Ask the user for the exact cat name via modal
                                class TargetModal(discord.ui.Modal):
                                    def __init__(self):
                                        super().__init__(title="Use item on which cat?")
                                        self.name_input = discord.ui.TextInput(label="Exact cat name", placeholder="Fluffy", max_length=100)
                                        self.add_item(self.name_input)

                                    async def on_submit(self2, modal_inter: discord.Interaction):
                                        if modal_inter.user.id != message.user.id:
                                            await do_funny(modal_inter)
                                            return
                                        await modal_inter.response.defer()
                                        target_name = self2.name_input.value.strip()
                                        cats_list = get_user_cats(modal_inter.guild.id, modal_inter.user.id)
                                        matches_local = [(i + 1, c) for i, c in enumerate(cats_list) if (c.get("name") or "").lower() == target_name.lower()]
                                        if not matches_local:
                                            await modal_inter.followup.send(f"Couldn't find a cat named '{target_name}'.", ephemeral=True)
                                            return

                                        async def apply_to_instance(idx_local: int, inst_local: dict):
                                            # decrement one use
                                            cur_items2 = get_user_items(message.guild.id, message.user.id)
                                            cur_have = cur_items2.get(key_local, {}).get(tier_local, 0)
                                            if cur_have <= 0:
                                                await modal_inter.followup.send("You don't have that item anymore.", ephemeral=True)
                                                return
                                            cur_items2.setdefault(key_local, {})[tier_local] = max(0, cur_have - 1)
                                            save_user_items(message.guild.id, message.user.id, cur_items2)

                                            bond_amt = SHOP_ITEMS.get(key_local, {}).get('tiers', {}).get(tier_local, {}).get('bond', 0)
                                            if key_local == 'pancakes' and bond_amt >= 100:
                                                inst_local['bond'] = 100
                                            else:
                                                inst_local['bond'] = min(100, inst_local.get('bond', 0) + int(bond_amt))
                                            save_user_cats(modal_inter.guild.id, modal_inter.user.id, cats_list)
                                            await modal_inter.followup.send(f"Used {SHOP_ITEMS[key_local]['title']} {tier_local} on **{inst_local.get('name')}** — Bond now {inst_local['bond']}.", ephemeral=True)

                                        # if single match, apply directly
                                        if len(matches_local) == 1:
                                            _, inst = matches_local[0]
                                            await apply_to_instance(matches_local[0][0], inst)
                                            return

                                        # multiple matches — present chooser
                                        class ChooseTargetView(View):
                                            def __init__(self, author_id: int, matches_list: list[tuple[int, dict]]):
                                                super().__init__(timeout=120)
                                                self.author_id = author_id
                                                for idxm, instm in matches_list[:25]:
                                                    labelm = f"#{idxm} {instm.get('type','Unknown')} — {instm.get('name')}"
                                                    btnm = Button(label=labelm, custom_id=f"choose_target_{idxm}")

                                                    async def cbm(inter: discord.Interaction, button: Button, idx_localm=idxm):
                                                        if inter.user.id != self.author_id:
                                                            await do_funny(inter)
                                                            return
                                                        await inter.response.defer()
                                                        cats_now2 = get_user_cats(inter.guild.id, inter.user.id)
                                                        if idx_localm < 1 or idx_localm > len(cats_now2):
                                                            await inter.followup.send("That instance no longer exists.", ephemeral=True)
                                                            return
                                                        inst_selected = cats_now2[idx_localm - 1]
                                                        await apply_to_instance(idx_localm, inst_selected)
                                                        # disable buttons
                                                        for child in list(self.children):
                                                            try:
                                                                child.disabled = True
                                                            except Exception:
                                                                pass
                                                        try:
                                                            await inter.edit_original_response(view=self)
                                                        except Exception:
                                                            pass

                                                    btnm.callback = cbm
                                                    self.add_item(btnm)

                                        view_targets = ChooseTargetView(modal_inter.user.id, matches_local)
                                        await modal_inter.followup.send(f"Multiple cats named '{target_name}' found — choose which one:", view=view_targets, ephemeral=True)

                                try:
                                    await sel_inter.response.send_modal(TargetModal())
                                except Exception:
                                    await sel_inter.response.send_message("Could not open target modal.", ephemeral=True)
                                return

                            # Default behavior for other item types (existing handling: rains, luck, xp)
                            # decrement one use
                            cur_items.setdefault(key_local, {})[tier_local] = max(0, have - 1)
                            save_user_items(message.guild.id, message.user.id, cur_items)

                            # apply effects
                            try:
                                if key_local == 'rains':
                                    minutes = SHOP_ITEMS[key_local]['tiers'][tier_local].get('minutes', 0)
                                    user_obj = await User.get_or_create(user_id=message.user.id)
                                    if not user_obj.rain_minutes:
                                        user_obj.rain_minutes = 0
                                    user_obj.rain_minutes += int(minutes)
                                    await user_obj.save()
                                    await sel_inter.response.send_message(f"Used {SHOP_ITEMS[key_local]['title']} {tier_local}: added {minutes} rain minutes to your account.", ephemeral=True)
                                    return

                                if key_local in ('luck', 'xp'):
                                    effect = SHOP_ITEMS[key_local]['tiers'][tier_local].get('effect', 0)
                                    # durations: I=1h, II=3h, III=6h
                                    dur_map = {'I': 3600, 'II': 10800, 'III': 21600}
                                    duration = dur_map.get(tier_local, 3600)
                                    now_ts = int(time.time())
                                    k = (message.guild.id, message.user.id)
                                    ITEM_BUFFS.setdefault(k, {})[key_local] = {"mult": effect, "until": now_ts + duration}
                                    try:
                                        save_item_buffs()
                                    except Exception:
                                        pass
                                    await sel_inter.response.send_message(f"Used {SHOP_ITEMS[key_local]['title']} {tier_local}: +{int(effect*100)}% {key_local} for {duration//3600}h. Expires <t:{now_ts + duration}:R>.", ephemeral=True)
                                    return

                                # fallback
                                await sel_inter.response.send_message(f"Used {SHOP_ITEMS[key_local]['title']} {tier_local}.", ephemeral=True)
                            except Exception:
                                await sel_inter.response.send_message("Failed to apply item effect.", ephemeral=True)

                    sel_view = View(timeout=120)
                    sel_view.add_item(UseSelect(opts))
                    try:
                        await interaction3.followup.send("Choose an item to use:", view=sel_view, ephemeral=True)
                    except Exception:
                        await interaction3.response.send_message("Could not open item selector.", ephemeral=True)

            try:
                await interaction2.response.edit_message(embed=items_embed, view=ItemsView())
            except Exception:
                await interaction2.followup.send(embed=items_embed, ephemeral=True)

        switch_btn = Button(label="Switch to Items", style=ButtonStyle.gray)
        switch_btn.callback = switch_to_items
        view.add_item(switch_btn)
        await message.followup.send(embed=embedVar, view=view)
    else:
        # show view for other user's inventory with switch button
        view_other = View(timeout=VIEW_TIMEOUT)
        async def switch_to_items_other(interaction2: discord.Interaction):
            items_embed = gen_items_embed(message, person_id)
            class BackViewOther(View):
                def __init__(self):
                    super().__init__(timeout=VIEW_TIMEOUT)

                @discord.ui.button(label="Back to Cats", style=ButtonStyle.secondary)
                async def back(self, interaction3: discord.Interaction, button: Button):
                    await interaction3.response.edit_message(embed=embedVar, view=view_other)

            try:
                await interaction2.response.edit_message(embed=items_embed, view=BackViewOther())
            except Exception:
                await interaction2.followup.send(embed=items_embed, ephemeral=True)

        switch_btn_other = Button(label="Switch to Items", style=ButtonStyle.gray)
        switch_btn_other.callback = switch_to_items_other
        view_other.add_item(switch_btn_other)
        await message.followup.send(embed=embedVar, view=view_other)


@bot.tree.command(description="its raining cats")
async def rain(message: discord.Interaction):
    user = await User.get_or_create(user_id=message.user.id)
    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    user.rain_minutes = 0
    if not user.rain_minutes:
        user.rain_minutes = 0
        await user.save()

    if not user.claimed_free_rain:
        user.rain_minutes += 2
        user.claimed_free_rain = True
        await user.save()

    server_rains = ""
    server_minutes = profile.rain_minutes
    if server_minutes > 0:
        server_rains = f" (+**{server_minutes}** bonus minutes)"

    embed = discord.Embed(
        title="☔ Cat Rains",
        description=f"""Cat Rains are power-ups which spawn cats instantly for a limited amounts of time in channel of your choice.

You can get those by buying them at the [store](<https://catbot.shop>) or by winning them in an event.
As a bonus, you will get access to /editprofile command!
Fastest times are not saved during rains.

You currently have **{user.rain_minutes}** minutes of rains{server_rains}.""",
        color=Colors.brown,
    )

    # this is the silly popup when you click the button
    class RainModal(discord.ui.Modal):
        def __init__(self, type):
            super().__init__(
                title="Start a Cat Rain!",
                timeout=36000,
            )

            self.input = discord.ui.TextInput(
                min_length=1,
                max_length=10,
                label="Duration in minutes",
                style=discord.TextStyle.short,
                required=True,
                placeholder="2",
            )
            self.add_item(self.input)

        async def on_submit(self, interaction: discord.Interaction):
            try:
                duration = int(self.input.value)
            except Exception:
                await interaction.response.send_message("number pls", ephemeral=True)
                return
            await do_rain(interaction, duration)

    async def do_rain(interaction, rain_length):
        # i LOOOOVE checks
        user = await User.get_or_create(user_id=interaction.user.id)
        profile = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)
        channel = await Channel.get_or_none(channel_id=interaction.channel.id)

        if not user.rain_minutes:
            user.rain_minutes = 0
            await user.save()

        if not user.claimed_free_rain:
            user.rain_minutes += 2
            user.claimed_free_rain = True
            await user.save()

        if about_to_stop:
            await interaction.response.send_message("the bot is about to stop. please try again later.", ephemeral=True)
            return

        if rain_length < 1 or rain_length > 60:
            await interaction.response.send_message("pls input a number 1-60", ephemeral=True)
            return

        if rain_length > user.rain_minutes + profile.rain_minutes or user.rain_minutes < 0:
            await interaction.response.send_message(
                "you dont have enough rain! buy some more [here](<https://catbot.shop>)",
                ephemeral=True,
            )
            return

        if not channel:
            await interaction.response.send_message("please run this in a setupped channel.", ephemeral=True)
            return

        if channel.cat:
            await interaction.response.send_message("please catch the cat in this channel first.", ephemeral=True)
            return

        if channel.cat_rains != 0 or message.channel.id in temp_rains_storage:
            await interaction.response.send_message("there is already a rain running!", ephemeral=True)
            return

        channel_permissions = await fetch_perms(message)
        needed_perms = {
            "View Channel": channel_permissions.view_channel,
            "Send Messages": channel_permissions.send_messages,
            "Attach Files": channel_permissions.attach_files,
        }
        if isinstance(message.channel, discord.Thread):
            needed_perms["Send Messages in Threads"] = channel_permissions.send_messages_in_threads

        for name, value in needed_perms.copy().items():
            if value:
                needed_perms.pop(name)

        missing_perms = list(needed_perms.keys())
        if len(missing_perms) != 0:
            needed_perms = "\n- ".join(missing_perms)
            await interaction.response.send_message(
                f":x: Missing Permissions! Please give me the following:\n- {needed_perms}\nHint: try setting channel permissions if server ones don't work."
            )
            return

        if not isinstance(
            message.channel,
            Union[
                discord.TextChannel,
                discord.StageChannel,
                discord.VoiceChannel,
                discord.Thread,
            ],
        ):
            return

        profile.rain_minutes_started += rain_length
        channel.cat_rains = time.time() + (rain_length * 60)
        channel.yet_to_spawn = 0
        await channel.save()
        await spawn_cat(str(message.channel.id))
        if profile.rain_minutes:
            if rain_length > profile.rain_minutes:
                user.rain_minutes -= rain_length - profile.rain_minutes
                profile.rain_minutes = 0
            else:
                profile.rain_minutes -= rain_length
        else:
            user.rain_minutes -= rain_length
        await user.save()
        await profile.save()
        await interaction.response.send_message(f"{rain_length}m cat rain was started by {interaction.user.mention}, ending <t:{int(channel.cat_rains)}:R>!")
        try:
            ch = bot.get_channel(config.RAIN_CHANNEL_ID)
            await ch.send(f"{interaction.user.id} started {rain_length}m rain in {interaction.channel.id} ({user.rain_minutes} left)")
        except Exception:
            pass

    async def rain_modal(interaction):
        modal = RainModal(interaction.user)
        await interaction.response.send_modal(modal)

    button = Button(label="Rain!", style=ButtonStyle.blurple)
    button.callback = rain_modal

    shopbutton = Button(
        emoji="🛒",
        label="Store (-20%!)",
        url="https://catbot.shop",
    )

    view = View(timeout=VIEW_TIMEOUT)
    view.add_item(button)
    view.add_item(shopbutton)

    await message.response.send_message(embed=embed, view=view)


@bot.tree.command(description="Open the Kibble Shop — items rotate/reset every 6 hours")
async def shop(message: discord.Interaction):
    await message.response.defer()
    guild_id = message.guild.id
    user_id = message.user.id

    # compute reset timer
    now = int(time.time())
    reset_window = now // SHOP_RESET_SECONDS
    next_reset = (reset_window + 1) * SHOP_RESET_SECONDS
    remaining = max(0, next_reset - now)

    embed = discord.Embed(title="Kibble Shop", color=Colors.brown)
    embed.description = f"Shop resets every 6 hours. Next reset <t:{int(next_reset)}:R> (in {remaining//3600}h {(remaining%3600)//60}m).\n\nChoose an item to buy with Kibble. Items affect packs, adventures, battlepass XP, or give rains."

    # choose or load 3 items for this guild's shop (persist across restarts until next reset)
    emoji_map = {"luck": "luckpotion", "xp": "xppotion", "rains": "bottlerain"}

    guild_shop = get_guild_shop(guild_id)
    now = int(time.time())
    # If no shop state or expired, pick 3 random items out of all available tiers
    if not guild_shop or guild_shop.get("next_reset", 0) <= now:
        # build list of all possible (key, tier)
        all_items = []
        for key, data in SHOP_ITEMS.items():
            for tier_key in data.get("tiers", {}).keys():
                price = ITEM_PRICES.get(key, {}).get(tier_key, 0)
                all_items.append({"key": key, "tier": tier_key, "price": price})
        chosen = random.sample(all_items, k=min(3, len(all_items))) if all_items else []
        next_reset = ((now // SHOP_RESET_SECONDS) + 1) * SHOP_RESET_SECONDS
        guild_shop = {"items": chosen, "next_reset": next_reset}
        save_guild_shop(guild_id, guild_shop)

    # Build embed showing only the 3 selected items (with emojis in embed titles)
    for item in guild_shop.get("items", []):
        key = item.get("key")
        tier_key = item.get("tier")
        price = item.get("price") or ITEM_PRICES.get(key, {}).get(tier_key, 0)
        data = SHOP_ITEMS.get(key, {})
        tier_data = data.get("tiers", {}).get(tier_key, {})
        emoji_label = get_emoji(emoji_map.get(key, key))
        title = f"{emoji_label} {data.get('title')} {tier_key}"
        desc = f"{tier_data.get('desc')} — **{price:,} Kibble**"
        embed.add_field(name=title, value=desc, inline=False)

    # View with purchase buttons
    class ShopView(View):
        def __init__(self):
            super().__init__(timeout=VIEW_TIMEOUT)

    view = ShopView()

    # add buy buttons only for the selected items
    for item in guild_shop.get("items", []):
        key = item.get("key")
        tier_key = item.get("tier")
        price = item.get("price") or ITEM_PRICES.get(key, {}).get(tier_key, 0)
        data = SHOP_ITEMS.get(key, {})
        label = f"Buy: {data.get('title')} {tier_key} — {price:,} K"
        btn = Button(label=label[:80], style=ButtonStyle.blurple)

        async def make_buy_cb(interaction: discord.Interaction, key_local=key, tier_local=tier_key, price_local=price):
            if interaction.user.id != user_id:
                await do_funny(interaction)
                return
            await interaction.response.defer()
            profile = await Profile.get_or_create(guild_id=guild_id, user_id=user_id)
            await profile.refresh_from_db()
            if profile.kibble < price_local:
                await interaction.followup.send("You don't have enough Kibble.", ephemeral=True)
                return
            # subtract and save
            profile.kibble = max(0, profile.kibble - price_local)
            await profile.save()
            # award item — if the tier defines 'uses', buying one increments by that many uses
            items = get_user_items(guild_id, user_id)
            uses = SHOP_ITEMS.get(key_local, {}).get('tiers', {}).get(tier_local, {}).get('uses', 1)
            items.setdefault(key_local, {})[tier_local] = items.get(key_local, {}).get(tier_local, 0) + int(uses)
            save_user_items(guild_id, user_id, items)
            await interaction.followup.send(f"Purchased {SHOP_ITEMS[key_local]['title']} {tier_local} for {price_local:,} Kibble.", ephemeral=True)

        btn.callback = make_buy_cb
        view.add_item(btn)

    # add refresh button
    async def refresh_cb(interaction: discord.Interaction):
        if interaction.user.id != user_id:
            await do_funny(interaction)
            return
        await interaction.response.defer()
        await shop(interaction)

    refresh_btn = Button(label="Refresh", style=ButtonStyle.secondary)
    refresh_btn.callback = refresh_cb
    view.add_item(refresh_btn)

    await message.followup.send(embed=embed, view=view)


@bot.tree.command(description="Buy Cat Rains!")
async def store(message: discord.Interaction):
    await message.response.send_message("☔ Cat rains make cats spawn instantly! Make your server active, get more cats and have fun!\n<https://catbot.shop>")


if config.DONOR_CHANNEL_ID:

    @bot.tree.command(description="(SUPPORTER) Bless random KITTAYYYYYYY users with doubled cats!")
    async def bless(message: discord.Interaction):
        user = await User.get_or_create(user_id=message.user.id)
        do_edit = False

        async def toggle_bless(interaction):
            if interaction.user.id != message.user.id:
                await do_funny(interaction)
                return
            nonlocal do_edit, user
            do_edit = True
            await interaction.response.defer()
            await user.refresh_from_db()
            user.blessings_enabled = not user.blessings_enabled
            await user.save()
            await regen(interaction)

        async def toggle_anon(interaction):
            if interaction.user.id != message.user.id:
                await do_funny(interaction)
                return
            nonlocal do_edit, user
            do_edit = True
            await interaction.response.defer()
            await user.refresh_from_db()
            user.blessings_anonymous = not user.blessings_anonymous
            await user.save()
            await regen(interaction)

        async def regen(interaction):
            if user.blessings_anonymous:
                blesser = "💫 Anonymous Supporter"
            else:
                blesser = f"{user.emoji or '💫'} {message.user.name}"

            embed = discord.Embed(
                color=Colors.brown,
                title="🌠 Cat Blessings",
                description=f"""When enabled, random KITTAYYYYYYY users will have their cats blessed by you - and their catches will be doubled!

Blessings are currently **{"enabled" if user.blessings_enabled else "disabled"}**.
Cats blessed: **{user.cats_blessed}**

Blessing message preview:
{blesser} blessed your catch and it got doubled!
""",
            )

            view = View(timeout=VIEW_TIMEOUT)
            if not user.premium:
                button = Button(label="Supporter Required!", url="https://catbot.shop", emoji="👑")
                view.add_item(button)
            else:
                button = Button(
                    emoji="🌟",
                    label=f"{'Disable' if user.blessings_enabled else 'Enable'} Blessings",
                    style=discord.ButtonStyle.red if user.blessings_enabled else discord.ButtonStyle.green,
                )
                button.callback = toggle_bless
                view.add_item(button)

                button = Button(
                    emoji="🕵️",
                    label=f"{'Disable' if user.blessings_anonymous else 'Enable'} Anonymity",
                    style=discord.ButtonStyle.red if user.blessings_anonymous else discord.ButtonStyle.green,
                )
                button.callback = toggle_anon
                view.add_item(button)

            if do_edit:
                await message.edit_original_response(embed=embed, view=view)
            else:
                await message.response.send_message(embed=embed, view=view)

        await regen(message)

    @bot.tree.command(description="(SUPPORTER) Customize your profile!")
    @discord.app_commands.rename(provided_emoji="emoji")
    @discord.app_commands.describe(
        color="Color for your profile in hex form (e.g. #6E593C)",
        provided_emoji="A default Discord emoji to show near your username.",
        image="A square image to show in top-right corner of your profile.",
    )
    async def editprofile(
        message: discord.Interaction,
        color: Optional[str],
        provided_emoji: Optional[str],
        image: Optional[discord.Attachment],
    ):
        if not config.DONOR_CHANNEL_ID:
            return

        user = await User.get_or_create(user_id=message.user.id)
        if not user.premium:
            await message.response.send_message(
                "👑 This feature is supporter-only!\nBuy anything from KITTAYYYYYYY Store to unlock profile customization!\n<https://catbot.shop>"
            )
            return

        if provided_emoji and discord_emoji.to_discord(provided_emoji.strip(), get_all=False, put_colons=False):
            user.emoji = provided_emoji.strip()

        if color:
            match = re.search(r"^#(?:[0-9a-fA-F]{3}){1,2}$", color)
            if match:
                user.color = match.group(0)
        if image:
            # reupload image
            channeley = bot.get_channel(config.DONOR_CHANNEL_ID)
            file = await image.to_file()
            if not isinstance(
                channeley,
                Union[
                    discord.TextChannel,
                    discord.StageChannel,
                    discord.VoiceChannel,
                    discord.Thread,
                ],
            ):
                raise ValueError
            msg = await channeley.send(file=file)
            user.image = msg.attachments[0].url
        await user.save()
        embedVar = await gen_inventory(message, message.user)
        await message.response.send_message("Success! Here is a preview:", embed=embedVar)


class PackButton(discord.ui.Button):
    def __init__(self, pack_name: str, pack_count: int):
        super().__init__(
            emoji=get_emoji(pack_name.lower() + "pack"),
            label=f"{pack_name} ({pack_count:,})",
            style=ButtonStyle.blurple,
            custom_id=f"pack_{pack_name}"
        )
        self.pack_name = pack_name

    async def callback(self, interaction: discord.Interaction):
        view: PacksView = self.view
        await view.handle_pack_open(interaction, self.pack_name)

class OpenAllButton(discord.ui.Button):
    def __init__(self, total_packs: int):
        super().__init__(
            label=f"Open all! ({total_packs:,})",
            style=ButtonStyle.blurple,
            custom_id="open_all"
        )

    async def callback(self, interaction: discord.Interaction):
        view: PacksView = self.view
        await view.handle_open_all(interaction)

class PacksView(discord.ui.View):
    def __init__(self, user: Profile):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.user = user
        
        # Add buttons for each pack type
        for pack in pack_data:
            try:
                pack_name = pack['name']
                pack_count = user[f"pack_{pack_name.lower()}"]
                if pack_count > 0:
                    self.add_item(PackButton(pack_name, pack_count))
            except Exception:
                continue
                
        # Add "Open All" button if total packs > 10
        total_packs = sum(user[f"pack_{p['name'].lower()}"] for p in pack_data)
        if total_packs > 10:
            self.add_item(OpenAllButton(total_packs))
            
        if not self.children:  # No buttons added
            self.add_item(discord.ui.Button(label="No packs available!", disabled=True))

    async def handle_pack_open(self, interaction: discord.Interaction, pack_name: str):
        if interaction.user.id != self.user.user_id:
            await do_funny(interaction)
            return

        level = next((i for i, p in enumerate(pack_data) if p["name"] == pack_name), 0)
        
        await interaction.response.defer()
        await self.user.refresh_from_db()
        
        if self.user[f"pack_{pack_name.lower()}"] < 1:
            return
            
        chosen_type, cat_amount, upgrades, reward_texts, kibble = await self.get_pack_rewards(level)
        self.user[f"cat_{chosen_type}"] += cat_amount
        self.user.pack_upgrades += upgrades
        self.user.packs_opened += 1
        self.user[f"pack_{pack_name.lower()}"] -= 1
        if kibble:
            self.user.kibble += kibble
        await self.user.save()
        
        try:
            if self.user[f"cat_{chosen_type}"] >= 64:
                await achemb(interaction, "full_stack", "send")
        except Exception:
            pass
            
        embed = discord.Embed(title=reward_texts[0], color=Colors.brown)
        await interaction.edit_original_response(embed=embed)
        
        for reward_text in reward_texts[1:]:
            await asyncio.sleep(1)
            things = reward_text.split("\n", 1)
            embed = discord.Embed(title=things[0], description=things[1], color=Colors.brown)
            await interaction.edit_original_response(embed=embed)
            
        await asyncio.sleep(1)
        new_view = PacksView(self.user)
        await interaction.edit_original_response(view=new_view)

    async def handle_open_all(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.user_id:
            await do_funny(interaction)
            return

        await interaction.response.defer()
        await self.user.refresh_from_db()

        pack_results = []
        for pack in pack_data:
            pack_name = pack['name'].lower()
            pack_count = self.user[f"pack_{pack_name}"]
            if pack_count > 0:
                level = next((i for i, p in enumerate(pack_data) if p["name"].lower() == pack_name), 0)
                chosen_type, cat_amount, upgrades, _, kibble = await self.get_pack_rewards(level, is_single=False)
                pack_results.append(f"{get_emoji(pack_name + 'pack')} {pack_count}x")
                self.user[f"cat_{chosen_type}"] += cat_amount
                self.user.pack_upgrades += upgrades
                self.user.packs_opened += pack_count
                self.user[f"pack_{pack_name}"] = 0
                if kibble:
                    # multiplied by count of packs processed
                    self.user.kibble += kibble * pack_count

        await self.user.save()
        
        embed = discord.Embed(
            title="Mass Pack Opening!",
            description=" ".join(pack_results),
            color=Colors.brown
        )
        await interaction.edit_original_response(embed=embed)
        
        await asyncio.sleep(1)
        new_view = PacksView(self.user)
        await interaction.edit_original_response(view=new_view)

    async def get_pack_rewards(self, level: int, is_single=True):
        reward_texts = []
        build_string = ""
        upgrades = 0
        kibble_reward = 0
        
        # Original pack reward logic preserved
        while random.randint(1, 100) <= pack_data[level]["upgrade"]:
            if is_single:
                reward_texts.append(f"{get_emoji(pack_data[level]['name'].lower() + 'pack')} {pack_data[level]['name']}\n" + build_string)
                build_string = f"Upgraded from {get_emoji(pack_data[level]['name'].lower() + 'pack')} {pack_data[level]['name']}!\n" + build_string
            else:
                build_string += f" -> {get_emoji(pack_data[level + 1]['name'].lower() + 'pack')}"
            level += 1
            upgrades += 1
        
        final_level = pack_data[level]
        if is_single:
            reward_texts.append(f"{get_emoji(final_level['name'].lower() + 'pack')} {final_level['name']}\n" + build_string)

        # Select cat type and amount
        goal_value = final_level["value"]
        chosen_type = random.choice(cattypes)
        cat_emoji = get_emoji(chosen_type.lower() + "cat")
        pre_cat_amount = goal_value / (sum(type_dict.values()) / type_dict[chosen_type])
        # Apply active luck buff (if any) to increase chance of better rewards
        try:
            buffs = get_active_buffs(self.user.guild_id, self.user.user_id)
            luck_mult = float(buffs.get("luck", 0)) if buffs else 0
        except Exception:
            luck_mult = 0

        # increase fractional success chance slightly with luck
        adj_threshold = random.random() - (luck_mult * 0.15)
        
        if pre_cat_amount % 1 > random.random():
            cat_amount = math.ceil(pre_cat_amount)
        else:
            cat_amount = math.floor(pre_cat_amount)
            
        if pre_cat_amount < 1:
            if is_single:
                reward_texts.append(reward_texts[-1] + f"\n{round(pre_cat_amount * 100, 2)}% chance for a {cat_emoji} {chosen_type} cat")
                reward_texts.append(reward_texts[-1] + ".")
                reward_texts.append(reward_texts[-1] + ".")
                reward_texts.append(reward_texts[-1] + ".")
            else:
                build_string += f" {round(pre_cat_amount * 100, 2)}% {cat_emoji}? "
            if cat_amount == 1:
                if is_single:
                    reward_texts.append(reward_texts[-1] + "\n✅ Success!")
                else:
                    build_string += f"✅ -> {cat_emoji} 1"
            else:
                if is_single:
                    reward_texts.append(reward_texts[-1] + "\n❌ Fail!")
                else:
                    build_string += f"❌ -> {get_emoji('finecat')} 1"
                chosen_type = "Fine"
                cat_amount = 1
        elif not is_single:
            build_string += f" {cat_emoji} {cat_amount:,}"
            
        # small chance to also award some kibble based on pack tier
        try:
            kibble_reward = random.randint(0, max(1, final_level.get("totalvalue", 100) // 12)) if random.random() < 0.25 else 0
            # apply luck multiplier to kibble
            if luck_mult and kibble_reward:
                kibble_reward = int(round(kibble_reward * (1 + luck_mult)))
        except Exception:
            kibble_reward = 0

        if is_single:
            if kibble_reward:
                reward_texts.append(reward_texts[-1] + f"\nAlso gained {kibble_reward:,} Kibble!")
            reward_texts.append(reward_texts[-1] + f"\nYou got {get_emoji(chosen_type.lower() + 'cat')} {cat_amount:,} {chosen_type} cats!")
            return chosen_type, cat_amount, upgrades, reward_texts, kibble_reward
            
        return chosen_type, cat_amount, upgrades, build_string, kibble_reward
    
    @discord.ui.button(label="Refresh", style=ButtonStyle.secondary, custom_id="refresh")
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.user_id:
            await do_funny(interaction)
            return
            
        await self.user.refresh_from_db()
        new_view = PacksView(self.user)
        await interaction.response.edit_message(view=new_view)
    
    async def open_pack_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.user_id:
            await do_funny(interaction)
            return
            
        pack_name = button.custom_id.split('_')[1]
        level = next((i for i, p in enumerate(pack_data) if p["name"] == pack_name), 0)
        
        await interaction.response.defer()
        await self.user.refresh_from_db()
        
        if self.user[f"pack_{pack_name.lower()}"] < 1:
            return
            
        chosen_type, cat_amount, upgrades, reward_texts, kibble = await self.get_pack_rewards(level)
        self.user[f"cat_{chosen_type}"] += cat_amount
        self.user.pack_upgrades += upgrades
        self.user.packs_opened += 1
        self.user[f"pack_{pack_name.lower()}"] -= 1
        if kibble:
            self.user.kibble += kibble
        await self.user.save()
        
        try:
            if self.user[f"cat_{chosen_type}"] >= 64:
                await achemb(interaction, "full_stack", "send")
        except Exception:
            pass
            
        embed = discord.Embed(title=reward_texts[0], color=Colors.brown)
        await interaction.edit_original_response(embed=embed)
        
        for reward_text in reward_texts[1:]:
            await asyncio.sleep(1)
            things = reward_text.split("\n", 1)
            embed = discord.Embed(title=things[0], description=things[1], color=Colors.brown)
            await interaction.edit_original_response(embed=embed)
            
        await asyncio.sleep(1)
        new_view = PacksView(self.user)
        await interaction.edit_original_response(view=new_view)

@bot.tree.command(description="View and open packs")
async def packs(message: discord.Interaction):
    await message.response.defer()
    
    try:
        user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
        description = "Each pack starts at one of eight tiers of increasing value - Wooden, Stone, Bronze, Silver, Gold, Platinum, Diamond, or Celestial - and can repeatedly move up tiers with a 30% chance per upgrade. This means that even a pack starting at Wooden, through successive upgrades, can reach the Celestial tier.\n[Chance Info](<https://catbot.minkos.lol/packs>)\n\nClick the buttons below to start opening packs!"
        embed = discord.Embed(title=f"{get_emoji('bronzepack')} Packs", description=description, color=Colors.brown)
        
        view = PacksView(user)
        await message.followup.send(embed=embed, view=view)
        
    except Exception as e:
        await message.followup.send(f"Error loading packs: {str(e)}", ephemeral=True)
    def gen_view(user):
        try:
            print("[DEBUG] Starting view generation")
            view = discord.ui.View(timeout=VIEW_TIMEOUT)
            empty = True
            total_amount = 0
            print("[DEBUG] Checking packs:", pack_data)
            
            for pack in pack_data:
                try:
                    pack_name = pack['name'].lower()
                    print(f"[DEBUG] Checking pack {pack_name}")
                    pack_count = user[f"pack_{pack_name}"]
                    print(f"[DEBUG] User has {pack_count} of {pack_name}")
                    
                    if pack_count < 1:
                        continue
                        
                    empty = False
                    total_amount += pack_count
                    
                    button = discord.ui.Button(
                        emoji=get_emoji(pack_name + "pack"),
                        label=f"{pack['name']} ({pack_count:,})",
                        style=ButtonStyle.blurple,
                        custom_id=pack["name"],
                    )
                    button.callback = open_pack
                    view.add_item(button)
                    print(f"[DEBUG] Added button for {pack_name}")
                except Exception as e:
                    print(f"[ERROR] Failed to process pack {pack.get('name', 'unknown')}: {e}")
                    continue
            
            print(f"[DEBUG] View generation complete. Empty: {empty}, Total: {total_amount}")
            if empty:
                view.add_item(discord.ui.Button(label="No packs left!", disabled=True))
                
            if total_amount > 10:
                button = discord.ui.Button(
                    label=f"Open all! ({total_amount:,})", 
                    style=ButtonStyle.blurple,
                    custom_id="open_all"
                )
                button.callback = open_all_packs
                view.add_item(button)
                
            return view
        except Exception as e:
            print(f"[ERROR] Failed to generate view: {e}")
            # Return a basic view with an error message
            view = discord.ui.View(timeout=VIEW_TIMEOUT)
            view.add_item(discord.ui.Button(label="Error loading packs", disabled=True))
            return view

    def get_pack_rewards(level: int, is_single=True, guild_id: int = None, user_id: int = None):
        # returns cat_type, cat_amount, upgrades, verbal_output
        reward_texts = []
        build_string = ""
        upgrades = 0
        if not is_single:
            build_string = get_emoji(pack_data[level]["name"].lower() + "pack")

        # bump rarity
        while random.randint(1, 100) <= pack_data[level]["upgrade"]:
            if is_single:
                reward_texts.append(f"{get_emoji(pack_data[level]['name'].lower() + 'pack')} {pack_data[level]['name']}\n" + build_string)
                build_string = f"Upgraded from {get_emoji(pack_data[level]['name'].lower() + 'pack')} {pack_data[level]['name']}!\n" + build_string
            else:
                build_string += f" -> {get_emoji(pack_data[level + 1]['name'].lower() + 'pack')}"
            level += 1
            upgrades += 1
        final_level = pack_data[level]
        if is_single:
            reward_texts.append(f"{get_emoji(final_level['name'].lower() + 'pack')} {final_level['name']}\n" + build_string)

        # select cat type
        goal_value = final_level["value"]
        chosen_type = random.choice(cattypes)
        cat_emoji = get_emoji(chosen_type.lower() + "cat")
        pre_cat_amount = goal_value / (sum(type_dict.values()) / type_dict[chosen_type])

        # apply luck buff if present (module-level persistent buffs)
        try:
            if guild_id and user_id:
                buffs = get_active_buffs(guild_id, user_id)
                luck_mult = float(buffs.get("luck", 0)) if buffs else 0
            else:
                luck_mult = 0
        except Exception:
            luck_mult = 0

        if pre_cat_amount % 1 > random.random():
            cat_amount = math.ceil(pre_cat_amount)
        else:
            cat_amount = math.floor(pre_cat_amount)
        if pre_cat_amount < 1:
            if is_single:
                reward_texts.append(
                    reward_texts[-1] + f"\n{round(pre_cat_amount * 100, 2)}% chance for a {get_emoji(chosen_type.lower() + 'cat')} {chosen_type} cat"
                )
                reward_texts.append(reward_texts[-1] + ".")
                reward_texts.append(reward_texts[-1] + ".")
                reward_texts.append(reward_texts[-1] + ".")
            else:
                build_string += f" {round(pre_cat_amount * 100, 2)}% {cat_emoji}? "
            if cat_amount == 1:
                # success
                if is_single:
                    reward_texts.append(reward_texts[-1] + "\n✅ Success!")
                else:
                    build_string += f"✅ -> {cat_emoji} 1"
            else:
                # fail
                if is_single:
                    reward_texts.append(reward_texts[-1] + "\n❌ Fail!")
                else:
                    build_string += f"❌ -> {get_emoji('finecat')} 1"
                chosen_type = "Fine"
                cat_amount = 1
        elif not is_single:
            build_string += f" {cat_emoji} {cat_amount:,}"
        # small chance to award kibble
        try:
            kibble_reward = random.randint(0, max(1, final_level.get("totalvalue", 100) // 12)) if random.random() < 0.25 else 0
            if luck_mult and kibble_reward:
                kibble_reward = int(round(kibble_reward * (1 + luck_mult)))
        except Exception:
            kibble_reward = 0

        if is_single:
            if kibble_reward:
                reward_texts.append(reward_texts[-1] + f"\nAlso gained {kibble_reward:,} Kibble!")
            reward_texts.append(reward_texts[-1] + f"\nYou got {get_emoji(chosen_type.lower() + 'cat')} {cat_amount:,} {chosen_type} cats!")
            return chosen_type, cat_amount, upgrades, reward_texts, kibble_reward
        return chosen_type, cat_amount, upgrades, build_string, kibble_reward

    async def open_pack(interaction: discord.Interaction):
            if interaction.user != message.user:
                await do_funny(interaction)
                return
            await interaction.response.defer()
            pack = interaction.data["custom_id"]
            await user.refresh_from_db()
            if user[f"pack_{pack.lower()}"] < 1:
                return
            level = next((i for i, p in enumerate(pack_data) if p["name"] == pack), 0)

            chosen_type, cat_amount, upgrades, reward_texts, kibble = get_pack_rewards(level, guild_id=message.guild.id, user_id=message.user.id)
            user[f"cat_{chosen_type}"] += cat_amount
            user.pack_upgrades += upgrades
            user.packs_opened += 1
            user[f"pack_{pack.lower()}"] -= 1
            if kibble:
                user.kibble += kibble
            await user.save()
            # after single-pack open save: check for full stack / huzzful
            try:
                await _check_full_stack_and_huzzful(user, interaction, chosen_type)
            except Exception:
                pass

            embed = discord.Embed(title=reward_texts[0], color=Colors.brown)
            await interaction.edit_original_response(embed=embed, view=None)
            for reward_text in reward_texts[1:]:
                await asyncio.sleep(1)
                things = reward_text.split("\n", 1)
                embed = discord.Embed(title=things[0], description=things[1], color=Colors.brown)
                await interaction.edit_original_response(embed=embed)
            await asyncio.sleep(1)
            await interaction.edit_original_response(view=gen_view(user))

    async def open_all_packs(interaction: discord.Interaction):
        if interaction.user != message.user:
            await do_funny(interaction)
            return
        await interaction.response.defer()
        await user.refresh_from_db()
        pack_names = [pack["name"] for pack in pack_data]
        total_pack_count = sum(user[f"pack_{pack_id.lower()}"] for pack_id in pack_names)
        if total_pack_count < 1:
            return

        display_cats = total_pack_count >= 50
        results_header = []
        results_detail = []
        results_percat = {cat: 0 for cat in cattypes}
        total_upgrades = 0
        for level, pack in enumerate(pack_names):
            pack_id = f"pack_{pack.lower()}"
            this_packs_count = user[pack_id]
            if this_packs_count < 1:
                continue
            results_header.append(f"{this_packs_count:,}x {get_emoji(pack.lower() + 'pack')}")
            for _ in range(this_packs_count):
                chosen_type, cat_amount, upgrades, rewards, kibble = get_pack_rewards(level, is_single=False, guild_id=message.guild.id, user_id=message.user.id)
                total_upgrades += upgrades
                if not display_cats:
                    results_detail.append(rewards)
                results_percat[chosen_type] += cat_amount
                if kibble:
                    user.kibble += kibble
            user[pack_id] = 0

        user.packs_opened += total_pack_count
        user.pack_upgrades += total_upgrades
        for cat_type, cat_amount in results_percat.items():
            user[f"cat_{cat_type}"] += cat_amount
        await user.save()
        # after bulk packs save: award Full Stack if any cat crossed the 64 threshold
        try:
            for cat_type, cat_amount in results_percat.items():
                if user[f"cat_{cat_type}"] >= 64:
                    await achemb(interaction, "full_stack", "send")
        except Exception:
            pass

        final_header = f"Opened {total_pack_count:,} packs!"
        pack_list = "**" + ", ".join(results_header) + "**"
        final_result = "\n".join(results_detail)
        if display_cats or len(final_result) > 4000 - len(pack_list):
            half_result = []
            for cat in cattypes:
                if results_percat[cat] == 0:
                    continue
                half_result.append(f"{get_emoji(cat.lower() + 'cat')} {results_percat[cat]:,} {cat} cats!")
            final_result = "\n".join(half_result)

        embed = discord.Embed(title=final_header, description=pack_list, color=Colors.brown)
        await interaction.edit_original_response(embed=embed, view=None)
        await asyncio.sleep(1)
        embed = discord.Embed(title=final_header, description=pack_list + "\n\n" + final_result, color=Colors.brown)
        await interaction.edit_original_response(embed=embed)
        await asyncio.sleep(1)
        await interaction.edit_original_response(view=gen_view(user))

async def packs(message: discord.Interaction):
    try:
        print(f"[DEBUG] /packs command started for user {message.user.id}")
        await message.response.defer()  # Prevent the command from timing out
        print("[DEBUG] Response deferred")
        
        try:
            user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
            print(f"[DEBUG] User profile fetched: {user is not None}")
        except Exception as e:
            print(f"[ERROR] Failed to get profile: {e}")
            await message.followup.send("Failed to load profile. Please try again.", ephemeral=True)
            return
            
        description = "Each pack starts at one of eight tiers of increasing value - Wooden, Stone, Bronze, Silver, Gold, Platinum, Diamond, or Celestial - and can repeatedly move up tiers with a 30% chance per upgrade. This means that even a pack starting at Wooden, through successive upgrades, can reach the Celestial tier.\n[Chance Info](<https://catbot.minkos.lol/packs>)\n\nClick the buttons below to start opening packs!"
        embed = discord.Embed(title=f"{get_emoji('bronzepack')} Packs", description=description, color=Colors.brown)
        
        # Show adventure status if one is active
        user_adv = active_adventures.get(str(message.user.id))
        if user_adv:
            print(f"[DEBUG] User has active adventure: {user_adv['cat']}")
            embed.add_field(
                name="Active Adventure", 
                value=f"You have a {user_adv['cat']} cat on an adventure that returns <t:{int(user_adv['end_time'])}:R>!\nPacks will be awarded when your cat returns.",
                inline=False
            )
            
        print("[DEBUG] Generating view")
        view = gen_view(user)
        print("[DEBUG] View generated")
        
        print("[DEBUG] Sending followup")
        await message.followup.send(embed=embed, view=view)
        print("[DEBUG] Command completed successfully")
        
    except Exception as e:
        print(f"[ERROR] Unhandled error in /packs: {e}")
        try:
            await message.followup.send("An error occurred while loading packs. Please try again.", ephemeral=True)
        except Exception:
            pass


@bot.tree.command(description="Attempt to steal a cat from another player (1 hour cooldown)")
@discord.app_commands.describe(target="The player to attempt to steal from")
async def steal(interaction: discord.Interaction, target: discord.User):
    if interaction.user.id == target.id:
        await interaction.response.send_message("You can't steal from yourself!", ephemeral=True)
        return

    # Get profiles
    thief = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)
    victim = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=target.id)
    
    # Check cooldown
    now = time.time()
    if float(now) - float(thief.last_steal or 0) < 3600:  # 1 hour cooldown
        remaining = int(3600 - (now - thief.last_steal))
        await interaction.response.send_message(
            f"You must wait {remaining // 60}m {remaining % 60}s before stealing again!",
            ephemeral=True
        )
        return

    # Check if target has any cats
    available_cats = []
    for cat_type in cattypes:
        if victim[f"cat_{cat_type}"] > 0:
            user_adv = active_adventures.get(str(target.id))
            if user_adv and user_adv["cat"] == cat_type:
                continue  # Skip cats that are on adventure
            available_cats.append(cat_type)

    if not available_cats:
        await interaction.response.send_message(
            f"{target.name} has no cats available to steal!",
            ephemeral=True
        )
        return

    # Calculate success chance based on rarity
    chosen_type = random.choice(available_cats)
    base_chance = {
        "Fine": 50,
        "Nice": 40,
        "Good": 30,
        "Rare": 20,
        "Epic": 10,
        "Legendary": 5,
        "Mythic": 3,
        "Ultimate": 2,
        "Professor": 1,
        "eGirl": 1,
        "Donut": 0.25,
    }.get(chosen_type, 50)

    success = random.randint(1, 100) <= base_chance

    await interaction.response.defer()

    if success:
        # Transfer one cat
        victim[f"cat_{chosen_type}"] -= 1
        thief[f"cat_{chosen_type}"] += 1
        thief.last_steal = now
        await victim.save()
        await thief.save()

        embed = discord.Embed(
            title="🦹‍♂️ Successful Heist!",
            description=f"You successfully stole 1 {get_emoji(chosen_type.lower() + 'cat')} {chosen_type} cat from {target.name}!",
            color=Colors.green
        )
        await interaction.followup.send(embed=embed)

        # DM the victim
        try:
            victim_embed = discord.Embed(
                title="😿 Cat Stolen!",
                description=f"{interaction.user.name} stole 1 {get_emoji(chosen_type.lower() + 'cat')} {chosen_type} cat from you!",
                color=Colors.red
            )
            await target.send(embed=victim_embed)
        except:
            pass  # Ignore if we can't DM
    else:
        thief.last_steal = now
        await thief.save()
        embed = discord.Embed(
            title="🚨 Heist Failed!",
            description=f"You failed to steal a {get_emoji(chosen_type.lower() + 'cat')} {chosen_type}  cat from {target.name}!",
            color=Colors.red
        )
        await interaction.followup.send(embed=embed)

@bot.tree.command(description="why would anyone think a cattlepass would be a good idea")
async def battlepass(message: discord.Interaction):
    current_mode = ""
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    global_user = await User.get_or_create(user_id=message.user.id)

    async def toggle_reminders(interaction: discord.Interaction):
        nonlocal current_mode
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        await interaction.response.defer()
        await user.refresh_from_db()
        if not user.reminders_enabled:
            try:
                await interaction.user.send(
                    f"You have enabled reminders in {interaction.guild.name}. You can disable them in the /battlepass command in that server or by saying `disable {interaction.guild.id}` here any time."
                )
            except Exception:
                await interaction.followup.send(
                    "Failed. Ensure you have DMs open by going to Server > Privacy Settings > Allow direct messages from server members."
                )
                return

        user.reminders_enabled = not user.reminders_enabled
        await user.save()

        view = View(timeout=VIEW_TIMEOUT)
        button = Button(emoji="🔄", label="Refresh", style=ButtonStyle.blurple)
        button.callback = gen_main
        view.add_item(button)

        if user.reminders_enabled:
            button = Button(emoji="🔕", style=ButtonStyle.blurple)
        else:
            button = Button(label="Enable Reminders", emoji="🔔", style=ButtonStyle.green)
        button.callback = toggle_reminders
        view.add_item(button)

        await interaction.followup.send(
            f"Reminders are now {'enabled' if user.reminders_enabled else 'disabled'}.",
            ephemeral=True,
        )
        await interaction.edit_original_response(view=view)

    async def gen_main(interaction, first=False):
        nonlocal current_mode
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        await interaction.response.defer()
        current_mode = "Main"

        await refresh_quests(user)

        await global_user.refresh_from_db()
        if global_user.vote_time_topgg + 12 * 3600 > time.time():
            await progress(message, user, "vote")
            await global_user.refresh_from_db()

        await user.refresh_from_db()

        # season end
        now = datetime.datetime.utcnow()

        if now.month == 12:
            next_month = datetime.datetime(now.year + 1, 1, 1)
        else:
            next_month = datetime.datetime(now.year, now.month + 1, 1)

        timestamp = int(time.mktime(next_month.timetuple()))

        description = f"Season ends <t:{timestamp}:R>\n\n"

        # vote
        streak_string = ""
        if global_user.vote_streak >= 5 and global_user.vote_time_topgg + 24 * 3600 > time.time():
            streak_string = f" (🔥 {global_user.vote_streak}x streak)"
        if user.vote_cooldown != 0:
            description += f"✅ ~~Vote on Top.gg~~\n- Refreshes <t:{int(user.vote_cooldown + 12 * 3600)}:R>{streak_string}\n"
        else:
            # inform double vote xp during weekends
            is_weekend = now.weekday() >= 4

            if is_weekend:
                description += "-# *Double Vote XP During Weekends*\n"

            description += f"{get_emoji('topgg')} [Vote on Top.gg](https://top.gg/bot/1387305159264309399/vote)\n"

            if is_weekend:
                description += f"- Reward: ~~{user.vote_reward}~~ **{user.vote_reward * 2}** XP"
            else:
                description += f"- Reward: {user.vote_reward} XP"

            next_streak_data = get_streak_reward(global_user.vote_streak + 1)
            if next_streak_data["reward"] and global_user.vote_time_topgg + 24 * 3600 > time.time():
                description += f" + {next_streak_data['emoji']} 1 {next_streak_data['reward'].capitalize()} pack"

            description += f"{streak_string}\n"

        # catch
        catch_quest = battle["quests"]["catch"][user.catch_quest]
        if user.catch_cooldown != 0:
            description += f"✅ ~~{catch_quest['title']}~~\n- Refreshes <t:{int(user.catch_cooldown + 12 * 3600 if user.catch_cooldown + 12 * 3600 < timestamp else timestamp)}:R>\n"
        else:
            progress_string = ""
            if catch_quest["progress"] != 1:
                if user.catch_quest == "finenice":
                    try:
                        real_progress = ["need both", "need Nice", "need Fine", "done"][user.catch_progress]
                    except IndexError:
                        real_progress = "error"
                    progress_string = f" ({real_progress})"
                else:
                    progress_string = f" ({user.catch_progress}/{catch_quest['progress']})"
            description += f"{get_emoji(catch_quest['emoji'])} {catch_quest['title']}{progress_string}\n- Reward: {user.catch_reward} XP\n"

        # misc
        misc_quest = battle.get("quests", {}).get("misc", {}).get(user.misc_quest)
        if not misc_quest:
            # missing quest - show placeholder and avoid crash
            misc_quest = {"title": "Unknown Quest", "emoji": "mystery", "progress": 1}
        if user.misc_cooldown != 0:
            description += f"✅ ~~{misc_quest['title']}~~\n- Refreshes <t:{int(user.misc_cooldown + 12 * 3600 if user.misc_cooldown + 12 * 3600 < timestamp else timestamp)}:R>\n\n"
        else:
            progress_string = ""
            if misc_quest.get("progress", 1) != 1:
                progress_string = f" ({user.misc_progress}/{misc_quest.get('progress',1)})"
            description += f"{get_emoji(misc_quest.get('emoji','mystery'))} {misc_quest.get('title','Unknown Quest')}{progress_string}\n- Reward: {user.misc_reward} XP\n\n"

        if user.battlepass >= len(battle["seasons"][str(user.season)]):
            description += f"**Extra Rewards** [{user.progress}/1500 XP]\n"
            colored = int(user.progress / 150)
            description += get_emoji("staring_square") * colored + "⬛" * (10 - colored) + "\nReward: " + get_emoji("stonepack") + " Stone pack\n\n"
        else:
            level_data = battle["seasons"][str(user.season)][user.battlepass]
            description += f"**Level {user.battlepass + 1}/30** [{user.progress}/{level_data['xp']} XP]\n"
            colored = int(user.progress / level_data["xp"] * 10)
            description += f"**{user.battlepass}** " + get_emoji("staring_square") * colored + "⬛" * (10 - colored) + f" **{user.battlepass + 1}**\n"

            if level_data["reward"] == "Rain":
                description += f"Reward: ☔ {level_data['amount']} minutes of rain\n\n"
            elif level_data["reward"] in cattypes:
                description += f"Reward: {get_emoji(level_data['reward'].lower() + 'cat')} {level_data['amount']} {level_data['reward']} cats\n\n"
            else:
                description += f"Reward: {get_emoji(level_data['reward'].lower() + 'pack')} {level_data['reward']} pack\n\n"

        # next reward
        levels = battle["seasons"][str(user.season)]
        for num, level_data in enumerate(levels):
            claimed_suffix = "_claimed" if num < user.battlepass else ""
            if level_data["reward"] == "Rain":
                description += get_emoji(str(level_data["amount"]) + "rain" + claimed_suffix)
            elif level_data["reward"] in cattypes:
                description += get_emoji(level_data["reward"].lower() + "cat" + claimed_suffix)
            else:
                description += get_emoji(level_data["reward"].lower() + "pack" + claimed_suffix)
            if num % 10 == 9:
                description += "\n"
        if user.battlepass >= len(battle["seasons"][str(user.season)]) - 1:
            description += f"*Extra:* {get_emoji('stonepack')} per 1500 XP"

        # Split description if too long
        if len(description) > 6000:  # Leave some buffer for other content
            # Split on double newlines to keep sections together
            sections = description.split('\n\n')
            primary_desc = []
            secondary_desc = []
            current_length = 0
            
            for section in sections:
                if current_length + len(section) + 2 < 3500:  # Leave room for transition text
                    primary_desc.append(section)
                    current_length += len(section) + 2  # +2 for \n\n
                else:
                    secondary_desc.append(section)
            
            # Create embeds
            embedVar = discord.Embed(
                title=f"Cattlepass Season {user.season}",
                description='\n\n'.join(primary_desc) + "\n\n*See next message for rewards...*",
                color=Colors.brown,
            ).set_footer(text=rain_shill)
            
            # Create secondary embed
            if secondary_desc:
                embedVar2 = discord.Embed(
                    title=f"Cattlepass Season {user.season} (Rewards)",
                    description='\n\n'.join(secondary_desc),
                    color=Colors.brown,
                ).set_footer(text=rain_shill)
        else:
            embedVar = discord.Embed(
                title=f"Cattlepass Season {user.season}",
                description=description,
                color=Colors.brown,
            ).set_footer(text=rain_shill)
        view = View(timeout=VIEW_TIMEOUT)

        button = Button(emoji="🔄", label="Refresh", style=ButtonStyle.blurple)
        button.callback = gen_main
        view.add_item(button)

        if user.reminders_enabled:
            button = Button(emoji="🔕", style=ButtonStyle.blurple)
        else:
            button = Button(label="Enable Reminders", emoji="🔔", style=ButtonStyle.green)
        button.callback = toggle_reminders
        view.add_item(button)

        if len(news_list) > len(global_user.news_state.strip()) or "0" in global_user.news_state.strip()[-4:]:
            embedVar.set_author(name="You have unread news! /news")

        if first:
            # Send embeds
            if len(description) > 6000 and 'embedVar2' in locals():
                await interaction.followup.send(embed=embedVar, view=view)
                await interaction.channel.send(embed=embedVar2)
            else:
                await interaction.followup.send(embed=embedVar, view=view)
        else:
            # Edit original response
            if len(description) > 6000 and 'embedVar2' in locals():
                await interaction.edit_original_response(embed=embedVar, view=view)
                await interaction.channel.send(embed=embedVar2)
            else:
                await interaction.edit_original_response(embed=embedVar, view=view)

    await gen_main(message, True)


@bot.tree.command(description="vote for KITTAYYYYYYY")
async def vote(message: discord.Interaction):
    embed = discord.Embed(
        title="Vote for KITTAYYYYYYY",
        color=Colors.brown,
        description="Vote for KITTAYYYYYYY on top.gg!",
    )
    view = View(timeout=1)
    button = Button(label="Vote!", url="https://top.gg/bot/1387305159264309399/vote", emoji=get_emoji("topgg"))
    view.add_item(button)
    await message.response.send_message(embed=embed, view=view)


@bot.tree.command(description="cat prisms are a special power up")
@discord.app_commands.describe(person="Person to view the prisms of")
async def prism(message: discord.Interaction, person: Optional[discord.User]):
    icon = get_emoji("prism")
    page_number = 0

    if not person:
        person_id = message.user
    else:
        person_id = person

    user_prisms = await Prism.collect("guild_id = $1 AND user_id = $2", message.guild.id, person_id.id)
    all_prisms = await Prism.collect("guild_id = $1", message.guild.id)
    total_count = len(all_prisms)
    user_count = len(user_prisms)
    global_boost = 0.06 * math.log(2 * total_count + 1)
    user_boost = round((global_boost + 0.03 * math.log(2 * user_count + 1)) * 100, 3)
    prism_texts = []

    if person_id == message.user and user_count != 0:
        await achemb(message, "prism", "send")

    order_map = {name: index for index, name in enumerate(prism_names)}
    prisms = all_prisms if not person else user_prisms
    prisms.sort(key=lambda p: order_map.get(p.name, float("inf")))

    for prism in prisms:
        prism_texts.append(f"{icon} **{prism.name}** {f'Owner: <@{prism.user_id}>' if not person else ''}\n<@{prism.creator}> crafted <t:{prism.time}:D>")

    if len(prisms) == 0:
        prism_texts.append("No prisms found!")

    async def confirm_craft(interaction: discord.Interaction):
        await interaction.response.defer()
        user = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)

        # check we still can craft
        for i in cattypes:
            if user["cat_" + i] < 1:
                await interaction.followup.send("You don't have enough cats. Nice try though.", ephemeral=True)
                return

        if await Prism.count("guild_id = $1", interaction.guild.id) >= len(prism_names):
            await interaction.followup.send("This server has reached the prism limit.", ephemeral=True)
            return

        if not isinstance(
            message.channel,
            Union[
                discord.TextChannel,
                discord.VoiceChannel,
                discord.StageChannel,
                discord.Thread,
            ],
        ):
            return

        # determine the next name
        for selected_name in prism_names:
            if not await Prism.get_or_none(guild_id=message.guild.id, name=selected_name):
                break

        youngest_prism = await Prism.collect("guild_id = $1 ORDER BY time DESC LIMIT 1", message.guild.id)
        if youngest_prism:
            selected_time = max(round(time.time()), youngest_prism[0].time + 1)
        else:
            selected_time = round(time.time())

        # actually take away cats
        for i in cattypes:
            user["cat_" + i] -= 1
        await user.save()

        # create the prism
        await Prism.create(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            creator=interaction.user.id,
            time=selected_time,
            name=selected_name,
        )
        await message.followup.send(f"{icon} {interaction.user.mention} has created prism {selected_name}!")
        await achemb(interaction, "prism", "send")
        await achemb(interaction, "collecter", "send")

    async def craft_prism(interaction: discord.Interaction):
        user = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)

        found_cats = await cats_in_server(interaction.guild.id)
        missing_cats = []
        for i in cattypes:
            if user[f"cat_{i}"] > 0:
                continue
            if i in found_cats:
                missing_cats.append(get_emoji(i.lower() + "cat"))
            else:
                missing_cats.append(get_emoji("mysterycat"))

        if len(missing_cats) == 0:
            view = View(timeout=VIEW_TIMEOUT)
            confirm_button = Button(label="Craft!", style=ButtonStyle.blurple, emoji=icon)
            confirm_button.callback = confirm_craft
            description = "The crafting recipe is __ONE of EVERY cat type__.\nContinue crafting?"
        else:
            view = View(timeout=VIEW_TIMEOUT)
            confirm_button = Button(label="Not enough cats!", style=ButtonStyle.red, disabled=True)
            description = "The crafting recipe is __ONE of EVERY cat type__.\nYou are missing " + "".join(missing_cats)

        view.add_item(confirm_button)
        await interaction.response.send_message(description, view=view, ephemeral=True)

    async def prev_page(interaction):
        nonlocal page_number
        page_number -= 1
        embed, view = gen_page()
        await interaction.response.edit_message(embed=embed, view=view)

    async def next_page(interaction):
        nonlocal page_number
        page_number += 1
        embed, view = gen_page()
        await interaction.response.edit_message(embed=embed, view=view)

    def gen_page():
        target = "" if not person else f"{person_id.name}'s"

        embed = discord.Embed(
            title=f"{icon} {target} Cat Prisms",
            color=Colors.brown,
            description="Prisms are a tradeable power-up which occasionally bumps cat rarity up by one. Each prism crafted gives everyone an increased chance to get upgraded, plus additional chance for prism owners.\n\n",
        ).set_footer(
            text=f"{total_count} Total Prisms | Global boost: {round(global_boost * 100, 3)}%\n{person_id.name}'s prisms | Owned: {user_count} | Personal boost: {user_boost}%"
        )

        embed.description += "\n".join(prism_texts[page_number * 26 : (page_number + 1) * 26])

        view = View(timeout=VIEW_TIMEOUT)

        craft_button = Button(label="Craft!", style=ButtonStyle.blurple, emoji=icon)
        craft_button.callback = craft_prism
        view.add_item(craft_button)

        prev_button = Button(label="<-", disabled=bool(page_number == 0))
        prev_button.callback = prev_page
        view.add_item(prev_button)

        next_button = Button(label="->", disabled=bool(page_number == (len(prism_texts) + 1) // 26))
        next_button.callback = next_page
        view.add_item(next_button)

        return embed, view

    embed, view = gen_page()
    await message.response.send_message(embed=embed, view=view)


@bot.tree.command(description="Pong")
async def ping(message: discord.Interaction):
    try:
        latency = round(bot.latency * 1000)
    except Exception:
        latency = "infinite"
    if latency == 0:
        # probably using gateway proxy, try fetching latency from metrics
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get("http://localhost:7878/metrics") as response:
                    data = await response.text()
                    total_latencies = 0
                    total_shards = 0
                    for line in data.split("\n"):
                        if line.startswith("gateway_shard_latency{shard="):
                            if "NaN" in line:
                                continue
                            try:
                                total_latencies += float(line.split(" ")[1])
                                total_shards += 1
                            except Exception:
                                pass
                    latency = round((total_latencies / total_shards) * 1000)
            except Exception:
                pass
    await message.response.send_message(f"🏓 cat has brain delay of {latency} ms {get_emoji('staring_cat')}")
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    await progress(message, user, "ping")


@bot.tree.command(description="play a relaxing game of tic tac toe")
@discord.app_commands.describe(person="who do you want to play with? (choose KITTAYYYYYYY for ai)")
async def tictactoe(message: discord.Interaction, person: discord.Member):
    do_edit = False
    board = [None, None, None, None, None, None, None, None, None]

    players = [message.user, person]
    random.shuffle(players)
    bot_is_playing = person == bot.user
    current_turn = 0

    def check_win(board):
        combinations = [
            # rows
            [0, 1, 2],
            [3, 4, 5],
            [6, 7, 8],
            # columns
            [0, 3, 6],
            [1, 4, 7],
            [2, 5, 8],
            # diagonals
            [0, 4, 8],
            [2, 4, 6],
        ]

        for combination in combinations:
            if board[combination[0]] == board[combination[1]] == board[combination[2]] and board[combination[0]] is not None:
                return combination

        return [-1]

    def minimax(board, depth, is_maximizing, alpha, beta, bot_symbol, human_symbol):
        wins = check_win(board)
        if wins != [-1]:
            if board[wins[0]] == bot_symbol:
                return 10 - depth  # Bot wins (good for bot)
            elif board[wins[0]] == human_symbol:
                return -10 + depth  # Human wins (bad for bot)

        if all(cell is not None for cell in board):
            return 0

        if is_maximizing:
            max_eval = float("-inf")
            for i in range(9):
                if board[i] is None:
                    board[i] = bot_symbol
                    eval = minimax(board, depth + 1, False, alpha, beta, bot_symbol, human_symbol)
                    board[i] = None
                    max_eval = max(max_eval, eval)
                    alpha = max(alpha, eval)
                    if beta <= alpha:
                        break
            return max_eval
        else:
            min_eval = float("inf")
            for i in range(9):
                if board[i] is None:
                    board[i] = human_symbol
                    eval = minimax(board, depth + 1, True, alpha, beta, bot_symbol, human_symbol)
                    board[i] = None
                    min_eval = min(min_eval, eval)
                    beta = min(beta, eval)
                    if beta <= alpha:
                        break
            return min_eval

    def get_best_move(board):
        best_score = float("-inf")
        best_move = None

        bot_turn = None
        human_turn = None
        for i, player in enumerate(players):
            if player.bot:
                bot_turn = i
            else:
                human_turn = i

        bot_symbol = "❌" if bot_turn == 0 else "⭕"
        human_symbol = "❌" if human_turn == 0 else "⭕"

        for i in range(9):
            if board[i] is None:
                board[i] = bot_symbol
                score = minimax(board, 0, False, float("-inf"), float("inf"), bot_symbol, human_symbol)
                board[i] = None

                if score > best_score:
                    best_score = score
                    best_move = i

        return best_move

    async def finish_turn():
        nonlocal do_edit, current_turn

        view = View(timeout=VIEW_TIMEOUT)
        wins = check_win(board)
        tie = True
        for cell_num, cell in enumerate(board):
            if cell is None:
                tie = False
                button = Button(emoji=get_emoji("empty"), custom_id=str(cell_num), row=cell_num // 3, disabled=wins != [-1])
            else:
                button = Button(emoji=cell, row=cell_num // 3, disabled=True, style=ButtonStyle.green if cell_num in wins else ButtonStyle.gray)
            button.callback = play
            view.add_item(button)

        if wins != [-1]:
            if board[wins[0]] == "❌":
                second_line = f"{players[0].mention} (X) won!"
                await end_game(0)
            elif board[wins[0]] == "⭕":
                second_line = f"{players[1].mention} (O) won!"
                await end_game(1)
        elif tie:
            second_line = "its a tie!"
            await end_game(-1)
        else:
            second_line = f"{players[current_turn].mention}'s turn ({'X' if current_turn == 0 else 'O'})"

        if do_edit:
            await message.edit_original_response(content=f"{players[0].mention} (X) vs {players[1].mention} (O)\n{second_line}", view=view)
        else:
            await message.response.send_message(f"{players[0].mention} (X) vs {players[1].mention} (O)\n{second_line}", view=view)
            do_edit = True

        if bot_is_playing and players[current_turn].bot and wins == [-1] and not tie:
            await asyncio.sleep(1)
            best_move = get_best_move(board)
            if best_move is not None:
                board[best_move] = "❌" if current_turn == 0 else "⭕"
                current_turn = 1 - current_turn
                await finish_turn()

    async def play(interaction):
        nonlocal current_turn
        cell_num = int(interaction.data["custom_id"])
        if board[cell_num] is not None:
            await interaction.response.send_message("That spot is already taken!", ephemeral=True)
            return
        if players[current_turn] != interaction.user:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return
        await interaction.response.defer()
        board[cell_num] = "❌" if current_turn == 0 else "⭕"
        current_turn = 1 - current_turn
        await finish_turn()

    async def end_game(winner):
        if players[0] == players[1]:
            # self-play
            user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
            await progress(message, user, "ttc")
            return
        users = [
            await Profile.get_or_create(guild_id=message.guild.id, user_id=players[0].id),
            await Profile.get_or_create(guild_id=message.guild.id, user_id=players[1].id),
        ]
        users[0].ttt_played += 1
        users[1].ttt_played += 1
        if winner != -1:
            users[winner].ttt_won += 1
            await achemb(message, "ttt_win", "send", players[winner])
        else:
            users[0].ttt_draws += 1
            users[1].ttt_draws += 1
        await users[0].save()
        await users[1].save()
        await progress(message, users[0], "ttc")
        await progress(message, users[1], "ttc")

    await finish_turn()


@bot.tree.command(description="dont select a person to make an everyone vs you game")
@discord.app_commands.describe(person="Who do you want to play with?")
async def rps(message: discord.Interaction, person: Optional[discord.Member]):
    clean_name = message.user.name.replace("_", "\\_")
    picks = {"Rock": [], "Paper": [], "Scissors": []}
    mappings = {"Rock": ["Paper", "Rock", "Scissors"], "Paper": ["Scissors", "Paper", "Rock"], "Scissors": ["Rock", "Scissors", "Paper"]}
    vs_picks = {}
    players = []

    async def pick(interaction):
        nonlocal players
        if person and interaction.user.id not in [message.user.id, person.id]:
            await do_funny(interaction)
            return

        await interaction.response.defer()

        thing = interaction.data["custom_id"]
        if person or interaction.user != message.user:
            if interaction.user.id in players:
                return
            if person:
                vs_picks[interaction.user.name.replace("_", "\\_")] = thing
            else:
                picks[thing].append(interaction.user.name.replace("_", "\\_"))
            players.append(interaction.user.id)
            if person and person.id == bot.user.id:
                players.append(bot.user.id)
                vs_picks[bot.user.name.replace("_", "\\_")] = mappings[thing][0]
            if not person or len(players) == 1:
                await interaction.edit_original_response(content=f"Players picked: {len(players)}")
                return

        result = mappings[thing]

        if not person:
            description = f"{clean_name} picked: __{thing}__\n\n"
            for num, i in enumerate(["Winners", "Tie", "Losers"]):
                if picks[result[num]]:
                    peoples = "\n".join(picks[result[num]])
                else:
                    peoples = "No one"
                description += f"**{i}** ({result[num]})\n{peoples}\n\n"
        else:
            description = f"{clean_name} picked: __{vs_picks[clean_name]}__\n\n{clean_name_2} picked: __{vs_picks[clean_name_2]}__\n\n"
            result = mappings[vs_picks[clean_name]].index(vs_picks[clean_name_2])
            if result == 0:
                description += f"**Winner**: {clean_name_2}!"
            elif result == 1:
                description += "It's a **Tie**!"
            else:
                description += f"**Winner**: {clean_name}!"

        embed = discord.Embed(
            title=f"{clean_name_2} vs {clean_name}",
            description=description,
            color=Colors.brown,
        )
        await interaction.edit_original_response(content=None, embed=embed, view=None)

    if person:
        clean_name_2 = person.name.replace("_", "\\_")
    else:
        clean_name_2 = "Rock Paper Scissors"

    if person:
        description = "Pick what to play!"
    else:
        description = "Any amount of users can play. The game ends when the person who ran the command picks. Max time is 24 hours."
    embed = discord.Embed(
        title=f"{clean_name_2} vs {clean_name}",
        description=description,
        color=Colors.brown,
    )
    view = View(timeout=24 * 3600)
    for i in ["Rock", "Paper", "Scissors"]:
        button = Button(label=i, custom_id=i)
        button.callback = pick
        view.add_item(button)
    await message.response.send_message("Players picked: 0", embed=embed, view=view)


@bot.tree.command(description="you feel like making cookies")
async def cookie(message: discord.Interaction):
    cookie_id = (message.guild.id, message.user.id)
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    if cookie_id not in temp_cookie_storage.keys():
        temp_cookie_storage[cookie_id] = user.cookies

    async def bake(interaction):
        if interaction.user != message.user:
            await do_funny(interaction)
            return
        await interaction.response.defer()
        if cookie_id in temp_cookie_storage:
            curr = temp_cookie_storage[cookie_id]
        else:
            await user.refresh_from_db()
            curr = user.cookies
        curr += 1
        temp_cookie_storage[cookie_id] = curr
        view.children[0].label = f"{curr:,}"
        await interaction.edit_original_response(view=view)
        if curr < 5:
            await achemb(interaction, "cookieclicker", "send")
        if 5100 > curr >= 5000:
            await achemb(interaction, "cookiesclicked", "send")

    view = View(timeout=VIEW_TIMEOUT)
    button = Button(emoji="🍪", label=f"{temp_cookie_storage[cookie_id]:,}", style=ButtonStyle.blurple)
    button.callback = bake
    view.add_item(button)
    await message.response.send_message(view=view)


@bot.tree.command(description="give cats now")
@discord.app_commands.rename(cat_type="type")
@discord.app_commands.describe(
    person="Whom to gift?",
    cat_type="im gonna airstrike your house from orbit",
    amount="And how much?",
)
@discord.app_commands.autocomplete(cat_type=gift_autocomplete)
async def gift(
    message: discord.Interaction,
    person: discord.User,
    cat_type: str,
    amount: Optional[int],
):
    if amount is None:
        # default the amount to 1
        amount = 1
    person_id = person.id

    if amount <= 0 or message.user.id == person_id:
        # haha skill issue
        await message.response.send_message("no", ephemeral=True)
        if message.user.id == person_id:
            await achemb(message, "lonely", "send")
        return

    if cat_type in cattypes:
        user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
        # if we even have enough available cats (not on adventure)
        available = await get_available_cat_count(user, cat_type)
        if available >= amount:
            reciever = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id)
            user[f"cat_{cat_type}"] -= amount
            reciever[f"cat_{cat_type}"] += amount
            try:
                user.cats_gifted += amount
                reciever.cat_gifts_recieved += amount
            except Exception:
                pass
            await user.save()
            await reciever.save()
            content = f"Successfully transfered {amount:,} {cat_type} cats from {message.user.mention} to <@{person_id}>!"

            # handle tax
            if amount >= 5:
                tax_amount = round(amount * 0.2)
                tax_debounce = False

                async def pay(interaction):
                    nonlocal tax_debounce
                    if interaction.user.id == message.user.id and not tax_debounce:
                        tax_debounce = True
                        await interaction.response.defer()
                        await user.refresh_from_db()
                        try:
                            # transfer tax
                            user[f"cat_{cat_type}"] -= tax_amount

                            try:
                                await interaction.edit_original_response(view=None)
                            except Exception:
                                pass
                            await interaction.followup.send(f"Tax of {tax_amount:,} {cat_type} cats was withdrawn from your account!")
                        finally:
                            # always save to prevent issue with exceptions leaving bugged state
                            await user.save()
                        await achemb(message, "good_citizen", "send")
                        if user[f"cat_{cat_type}"] < 0:
                            bot.loop.create_task(debt_cutscene(interaction, user))
                    else:
                        await do_funny(interaction)

                async def evade(interaction):
                    if interaction.user.id == message.user.id:
                        await interaction.response.defer()
                        try:
                            await interaction.edit_original_response(view=None)
                        except Exception:
                            pass
                        await interaction.followup.send(f"You evaded the tax of {tax_amount:,} {cat_type} cats.")
                        await achemb(message, "secret", "send")
                    else:
                        await do_funny(interaction)

                button = Button(label="Pay 20% tax", style=ButtonStyle.green)
                button.callback = pay

                button2 = Button(label="Evade the tax", style=ButtonStyle.red)
                button2.callback = evade

                myview = View(timeout=VIEW_TIMEOUT)

                myview.add_item(button)
                myview.add_item(button2)

                await message.response.send_message(content, view=myview, allowed_mentions=discord.AllowedMentions(users=True))
            else:
                await message.response.send_message(content, allowed_mentions=discord.AllowedMentions(users=True))

            # handle aches
            await achemb(message, "donator", "send")
            await achemb(message, "anti_donator", "send", person)
            if person_id == bot.user.id and cat_type == "Ultimate" and int(amount) >= 5:
                await achemb(message, "rich", "send")
            if person_id == bot.user.id:
                await achemb(message, "sacrifice", "send")
            if cat_type == "Nice" and int(amount) == 69:
                await achemb(message, "nice", "send")

            await progress(message, user, "gift")
        else:
            await message.response.send_message("no", ephemeral=True)
    elif cat_type.lower() == "kibble":
        # gift kibble (per-server currency)
        user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
        if user.kibble >= amount:
            reciever = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id)
            user.kibble -= amount
            reciever.kibble += amount
            await user.save()
            await reciever.save()
            content = f"Successfully transferred {amount:,} Kibble from {message.user.mention} to <@{person_id}>!"
            await message.response.send_message(content, allowed_mentions=discord.AllowedMentions(users=True))
            await achemb(message, "donator", "send")
            await achemb(message, "anti_donator", "send", person)
            await progress(message, user, "gift")
        else:
            await message.response.send_message("no", ephemeral=True)
    elif cat_type.lower() == "rain":
        if person_id == bot.user.id:
            await message.response.send_message("you can't sacrifice rains", ephemeral=True)
            return

        actual_user = await User.get_or_create(user_id=message.user.id)
        actual_receiver = await User.get_or_create(user_id=person_id)
        if actual_user.rain_minutes >= amount:
            actual_user.rain_minutes -= amount
            actual_receiver.rain_minutes += amount
            await actual_user.save()
            await actual_receiver.save()
            content = f"Successfully transfered {amount:,} minutes of rain from {message.user.mention} to <@{person_id}>!"

            await message.response.send_message(content, allowed_mentions=discord.AllowedMentions(users=True))

            # handle aches
            await achemb(message, "donator", "send")
            await achemb(message, "anti_donator", "send", person)
        else:
            await message.response.send_message("no", ephemeral=True)

        try:
            ch = bot.get_channel(config.RAIN_CHANNEL_ID)
            await ch.send(f"{message.user.id} gave {amount}m to {person_id}")
        except Exception:
            pass
    elif cat_type.lower() in [i["name"].lower() for i in pack_data]:
        cat_type = cat_type.lower()
        # packs um also this seems to be repetetive uh
        user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
        # if we even have enough packs
        if user[f"pack_{cat_type}"] >= amount:
            reciever = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id)
            user[f"pack_{cat_type}"] -= amount
            reciever[f"pack_{cat_type}"] += amount
            await user.save()
            await reciever.save()
            content = f"Successfully transfered {amount:,} {cat_type} packs from {message.user.mention} to <@{person_id}>!"

            await message.response.send_message(content, allowed_mentions=discord.AllowedMentions(users=True))

            # handle aches
            await achemb(message, "donator", "send")
            await achemb(message, "anti_donator", "send", person)
            if person_id == bot.user.id:
                await achemb(message, "sacrifice", "send")

            await progress(message, user, "gift")
        else:
            await message.response.send_message("no", ephemeral=True)
    else:
        await message.response.send_message("bro what", ephemeral=True)


@bot.tree.command(description="Trade stuff!")
@discord.app_commands.rename(person_id="user")
@discord.app_commands.describe(person_id="why would you need description")
async def trade(message: discord.Interaction, person_id: discord.User):
    person1 = message.user
    person2 = person_id

    blackhole = False

    person1accept = False
    person2accept = False

    person1value = 0
    person2value = 0

    person1gives = {}
    person2gives = {}

    user1 = await Profile.get_or_create(guild_id=message.guild.id, user_id=person1.id)
    user2 = await Profile.get_or_create(guild_id=message.guild.id, user_id=person2.id)

    if not bot.user:
        return

    # do the funny
    if person2.id == bot.user.id:
        person2gives["eGirl"] = 9999999

    # this is the deny button code
    async def denyb(interaction):
        nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives, blackhole
        if interaction.user != person1 and interaction.user != person2:
            await do_funny(interaction)
            return

        await interaction.response.defer()
        blackhole = True
        person1gives = {}
        person2gives = {}
        try:
            await interaction.edit_original_response(
                content=f"{interaction.user.mention} has cancelled the trade.",
                embed=None,
                view=None,
            )
        except Exception:
            pass

    # this is the accept button code
    async def acceptb(interaction):
        nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives, person1value, person2value, user1, user2, blackhole
        if interaction.user != person1 and interaction.user != person2:
            await do_funny(interaction)
            return

        # clicking accept again would make you un-accept
        if interaction.user == person1:
            person1accept = not person1accept
        elif interaction.user == person2:
            person2accept = not person2accept

        await interaction.response.defer()
        await update_trade_embed(interaction)

        if person1accept and person2 == bot.user:
            await achemb(message, "desperate", "send")

        if blackhole:
            await update_trade_embed(interaction)

        if person1accept and person2accept:
            blackhole = True
            await user1.refresh_from_db()
            await user2.refresh_from_db()
            actual_user1 = await User.get_or_create(user_id=person1.id)
            actual_user2 = await User.get_or_create(user_id=person2.id)

            # check if we have enough things (person could have moved them during the trade)
            error = False
            person1prismgive = 0
            person2prismgive = 0
            for k, v in person1gives.items():
                if k in prism_names:
                    person1prismgive += 1
                    prism = await Prism.get_or_none(guild_id=interaction.guild.id, name=k)
                    if not prism or prism.user_id != person1.id:
                        error = True
                        break
                    continue
                elif k == "rains":
                    if actual_user1.rain_minutes < v:
                        error = True
                        break
                elif k in cattypes:
                    if user1[f"cat_{k}"] < v:
                        error = True
                        break
                elif k == "kibble":
                    if user1.kibble < v:
                        error = True
                        break
                elif user1[f"pack_{k.lower()}"] < v:
                    error = True
                    break

            for k, v in person2gives.items():
                if k in prism_names:
                    person2prismgive += 1
                    prism = await Prism.get_or_none(guild_id=interaction.guild.id, name=k)
                    if not prism or prism.user_id != person2.id:
                        error = True
                        break
                    continue
                elif k == "rains":
                    if actual_user2.rain_minutes < v:
                        error = True
                        break
                elif k in cattypes:
                    if user2[f"cat_{k}"] < v:
                        error = True
                        break
                elif k == "kibble":
                    if user2.kibble < v:
                        error = True
                        break
                elif user2[f"pack_{k.lower()}"] < v:
                    error = True
                    break

            if error:
                try:
                    await interaction.edit_original_response(
                        content="Uh oh - some of the cats/prisms/packs/rains disappeared while trade was happening",
                        embed=None,
                        view=None,
                    )
                except Exception:
                    await interaction.followup.send("Uh oh - some of the cats/prisms/packs/rains disappeared while trade was happening")
                return

            # exchange
            cat_count = 0
            for k, v in person1gives.items():
                if k in prism_names:
                    move_prism = await Prism.get_or_none(guild_id=message.guild.id, name=k)
                    move_prism.user_id = person2.id
                    await move_prism.save()
                elif k == "rains":
                    actual_user1.rain_minutes -= v
                    actual_user2.rain_minutes += v
                    try:
                        ch = bot.get_channel(config.RAIN_CHANNEL_ID)
                        await ch.send(f"{actual_user1.user_id} traded {v}m to {actual_user2.user_id}")
                    except Exception:
                        pass
                elif k in cattypes:
                    cat_count += v
                    user1[f"cat_{k}"] -= v
                    user2[f"cat_{k}"] += v
                elif k == "kibble":
                    # transfer kibble
                    user1.kibble -= v
                    user2.kibble += v
                else:
                    user1[f"pack_{k.lower()}"] -= v
                    user2[f"pack_{k.lower()}"] += v

            for k, v in person2gives.items():
                if k in prism_names:
                    move_prism = await Prism.get_or_none(guild_id=message.guild.id, name=k)
                    move_prism.user_id = person1.id
                    await move_prism.save()
                elif k == "rains":
                    actual_user2.rain_minutes -= v
                    actual_user1.rain_minutes += v
                    try:
                        ch = bot.get_channel(config.RAIN_CHANNEL_ID)
                        await ch.send(f"{actual_user2.user_id} traded {v}m to {actual_user1.user_id}")
                    except Exception:
                        pass
                elif k in cattypes:
                    cat_count += v
                    user1[f"cat_{k}"] += v
                    user2[f"cat_{k}"] -= v
                elif k == "kibble":
                    # transfer kibble
                    user1.kibble += v
                    user2.kibble -= v
                else:
                    user1[f"pack_{k.lower()}"] += v
                    user2[f"pack_{k.lower()}"] -= v

            user1.cats_traded += cat_count
            user2.cats_traded += cat_count
            user1.trades_completed += 1
            user2.trades_completed += 1

            await user1.save()
            await user2.save()
            await actual_user1.save()
            await actual_user2.save()
            # after both profiles saved: check for full stack
            try:
                for cat in cattypes:
                    try:
                        if user1[f"cat_{cat}"] >= 64:
                            await achemb(message, "full_stack", "send")
                    except Exception:
                        pass
                    try:
                        if user2[f"cat_{cat}"] >= 64:
                            await achemb(message, "full_stack", "send")
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                await interaction.edit_original_response(content="Trade finished!", view=None)
            except Exception:
                await interaction.followup.send()

            await achemb(message, "extrovert", "send")
            await achemb(message, "extrovert", "send", person2)

            if cat_count >= 1000:
                await achemb(message, "capitalism", "send")
                await achemb(message, "capitalism", "send", person2)

            if cat_count == 0:
                await achemb(message, "absolutely_nothing", "send")
                await achemb(message, "absolutely_nothing", "send", person2)

            if person2value - person1value >= 100:
                await achemb(message, "profit", "send")
            if person1value - person2value >= 100:
                await achemb(message, "profit", "send", person2)

            if person1value > person2value:
                await achemb(message, "scammed", "send")
            if person2value > person1value:
                await achemb(message, "scammed", "send", person2)

            if person1value == person2value and person1gives != person2gives:
                await achemb(message, "perfectly_balanced", "send")
                await achemb(message, "perfectly_balanced", "send", person2)

            await progress(message, user1, "trade")
            await progress(message, user2, "trade")

    # add cat code
    async def addb(interaction):
        nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives
        if interaction.user != person1 and interaction.user != person2:
            await do_funny(interaction)
            return

        currentuser = 1 if interaction.user == person1 else 2

        # all we really do is spawn the modal
        modal = TradeModal(currentuser)
        await interaction.response.send_modal(modal)

    # this is ran like everywhere when you do anything
    # it updates the embed
    async def gen_embed():
        nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives, blackhole, person1value, person2value

        if blackhole:
            # no way thats fun
            await achemb(message, "blackhole", "send")
            await achemb(message, "blackhole", "send", person2)
            return discord.Embed(color=Colors.brown, title="Blackhole", description="How Did We Get Here?"), None

        view = View(timeout=VIEW_TIMEOUT)

        accept = Button(label="Accept", style=ButtonStyle.green)
        accept.callback = acceptb

        deny = Button(label="Deny", style=ButtonStyle.red)
        deny.callback = denyb

        add = Button(label="Offer...", style=ButtonStyle.blurple)
        add.callback = addb

        view.add_item(accept)
        view.add_item(deny)
        view.add_item(add)

        person1name = person1.name.replace("_", "\\_")
        person2name = person2.name.replace("_", "\\_")
        coolembed = discord.Embed(
            color=Colors.brown,
            title=f"{person1name} and {person2name} trade",
            description="no way",
        )

        # a single field for one person
        def field(personaccept, persongives, person, number):
            nonlocal coolembed, person1value, person2value
            icon = "⬜"
            if personaccept:
                icon = "✅"
            valuestr = ""
            valuenum = 0
            total = 0
            for k, v in persongives.items():
                if v == 0:
                    continue
                if k in prism_names:
                    # prisms
                    valuestr += f"{get_emoji('prism')} {k}\n"
                    for v2 in type_dict.values():
                        valuenum += sum(type_dict.values()) / v2
                elif k == "rains":
                    # rains
                    valuestr += f"☔ {v:,}m of Cat Rains\n"
                    valuenum += 900 * v
                elif k in cattypes:
                    # cats
                    valuenum += (sum(type_dict.values()) / type_dict[k]) * v
                    total += v
                    aicon = get_emoji(k.lower() + "cat")
                    valuestr += f"{aicon} {k} {v:,}\n"
                elif k == "kibble":
                    # kibble currency
                    valuenum += v
                    valuestr += f"🍖 {v:,} Kibble\n"
                else:
                    # packs
                    valuenum += sum([i["totalvalue"] if i["name"] == k else 0 for i in pack_data]) * v
                    aicon = get_emoji(k.lower() + "pack")
                    valuestr += f"{aicon} {k} {v:,}\n"
            if not valuestr:
                valuestr = "Nothing offered!"
            else:
                valuestr += f"*Total value: {round(valuenum):,}\nTotal cats: {round(total):,}*"
                if number == 1:
                    person1value = round(valuenum)
                else:
                    person2value = round(valuenum)
            personname = person.name.replace("_", "\\_")
            coolembed.add_field(name=f"{icon} {personname}", inline=True, value=valuestr)

        field(person1accept, person1gives, person1, 1)
        field(person2accept, person2gives, person2, 2)

        return coolembed, view

    # this is wrapper around gen_embed() to edit the mesage automatically
    async def update_trade_embed(interaction):
        embed, view = await gen_embed()
        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception:
            await achemb(message, "blackhole", "send")
            await achemb(message, "blackhole", "send", person2)

    # lets go add cats modal thats fun
    class TradeModal(discord.ui.Modal):
        def __init__(self, currentuser):
            super().__init__(
                title="Add to the trade",
                timeout=3600,
            )
            self.currentuser = currentuser

            self.cattype = discord.ui.TextInput(
                label='Cat or Pack Type, Prism Name or "Rain"',
                placeholder="Fine / Wooden / Alpha / Rain",
            )
            self.add_item(self.cattype)

            self.amount = discord.ui.TextInput(label="Amount to offer", placeholder="1", required=False)
            self.add_item(self.amount)

        # this is ran when user submits
        async def on_submit(self, interaction: discord.Interaction):
            nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives
            value = self.amount.value if self.amount.value else 1
            await user1.refresh_from_db()
            await user2.refresh_from_db()

            try:
                if int(value) < 0:
                    person1accept = False
                    person2accept = False
            except Exception:
                await interaction.response.send_message("invalid amount", ephemeral=True)
                return

            # handle prisms
            if (pname := " ".join(i.capitalize() for i in self.cattype.value.split())) in prism_names:
                try:
                    prism = await Prism.get_or_none(guild_id=interaction.guild.id, name=pname)
                    if not prism:
                        raise Exception
                except Exception:
                    await interaction.response.send_message("this prism doesnt exist", ephemeral=True)
                    return
                if prism.user_id != interaction.user.id:
                    await interaction.response.send_message("this is not your prism", ephemeral=True)
                    return
                if (self.currentuser == 1 and pname in person1gives.keys()) or (self.currentuser == 2 and pname in person2gives.keys()):
                    await interaction.response.send_message("you already added this prism", ephemeral=True)
                    return

                if self.currentuser == 1:
                    person1gives[pname] = 1
                else:
                    person2gives[pname] = 1
                await interaction.response.defer()
                await update_trade_embed(interaction)
                return

            # handle packs
            if self.cattype.value.capitalize() in [i["name"] for i in pack_data]:
                pname = self.cattype.value.capitalize()
                if self.currentuser == 1:
                    if user1[f"pack_{pname.lower()}"] < int(value):
                        await interaction.response.send_message("you dont have enough packs", ephemeral=True)
                        return
                    new_val = person1gives.get(pname, 0) + int(value)
                    if new_val >= 0:
                        person1gives[pname] = new_val
                    else:
                        await interaction.response.send_message("skibidi toilet", ephemeral=True)
                        return
                else:
                    if user2[f"pack_{pname.lower()}"] < int(value):
                        await interaction.response.send_message("you dont have enough packs", ephemeral=True)
                        return
                    new_val = person2gives.get(pname, 0) + int(value)
                    if new_val >= 0:
                        person2gives[pname] = new_val
                    else:
                        await interaction.response.send_message("skibidi toilet", ephemeral=True)
                        return
                await interaction.response.defer()
                await update_trade_embed(interaction)
                return

            # handle rains
            if "rain" in self.cattype.value.lower():
                user = await User.get_or_create(user_id=interaction.user.id)
                try:
                    if user.rain_minutes < int(value) or int(value) < 1:
                        await interaction.response.send_message("you dont have enough rains", ephemeral=True)
                        return
                except Exception:
                    await interaction.response.send_message("please enter a number for amount", ephemeral=True)
                    return

                if self.currentuser == 1:
                    try:
                        person1gives["rains"] += int(value)
                    except Exception:
                        person1gives["rains"] = int(value)
                else:
                    try:
                        person2gives["rains"] += int(value)
                    except Exception:
                        person2gives["rains"] = int(value)
                await interaction.response.defer()
                await update_trade_embed(interaction)
                return

            # handle kibble
            if "kibble" in self.cattype.value.lower():
                try:
                    amt = int(value)
                    if amt < 1:
                        raise Exception
                except Exception:
                    await interaction.response.send_message("please enter a number for amount", ephemeral=True)
                    return
                # ensure the user has enough kibble
                if self.currentuser == 1:
                    if user1.kibble < amt:
                        await interaction.response.send_message("you dont have enough kibble", ephemeral=True)
                        return
                    person1gives["kibble"] = person1gives.get("kibble", 0) + amt
                else:
                    if user2.kibble < amt:
                        await interaction.response.send_message("you dont have enough kibble", ephemeral=True)
                        return
                    person2gives["kibble"] = person2gives.get("kibble", 0) + amt

                await interaction.response.defer()
                await update_trade_embed(interaction)
                return

            lc_input = self.cattype.value.lower()

            # loop through the cat types and find the correct one using lowercased user input.
            cname = cattype_lc_dict.get(lc_input, None)

            # if no cat type was found, the user input was invalid. as cname is still `None`
            if cname is None:
                await interaction.response.send_message("add a valid cat/pack/prism name 💀💀💀", ephemeral=True)
                return

            try:
                if self.currentuser == 1:
                    currset = person1gives[cname]
                else:
                    currset = person2gives[cname]
            except Exception:
                currset = 0

            try:
                if int(value) + currset < 0 or int(value) == 0:
                    raise Exception
            except Exception:
                await interaction.response.send_message("plz number?", ephemeral=True)
                return

            if (self.currentuser == 1 and user1[f"cat_{cname}"] < int(value) + currset) or (
                self.currentuser == 2 and user2[f"cat_{cname}"] < int(value) + currset
            ):
                await interaction.response.send_message(
                    "hell naww dude you dont even have that many cats 💀💀💀",
                    ephemeral=True,
                )
                return

            # OKE SEEMS GOOD LETS ADD CATS TO THE TRADE
            if self.currentuser == 1:
                try:
                    person1gives[cname] += int(value)
                    if person1gives[cname] == 0:
                        person1gives.pop(cname)
                except Exception:
                    person1gives[cname] = int(value)
            else:
                try:
                    person2gives[cname] += int(value)
                    if person2gives[cname] == 0:
                        person2gives.pop(cname)
                except Exception:
                    person2gives[cname] = int(value)

            await interaction.response.defer()
            await update_trade_embed(interaction)

    embed, view = await gen_embed()
    if not view:
        await message.response.send_message(embed=embed)
    else:
        await message.response.send_message(person2.mention, embed=embed, view=view, allowed_mentions=discord.AllowedMentions(users=True))

    if person1 == person2:
        await achemb(message, "introvert", "send")


@bot.tree.command(description="Get Cat Image, does not add a cat to your inventory")
@discord.app_commands.rename(cat_type="type")
@discord.app_commands.describe(cat_type="select a cat type ok")
@discord.app_commands.autocomplete(cat_type=cat_command_autocomplete)
async def cat(message: discord.Interaction, cat_type: Optional[str]):
    if cat_type and cat_type not in cattypes:
        await message.response.send_message("bro what", ephemeral=True)
        return

    perms = await fetch_perms(message)
    if not perms.attach_files:
        await message.response.send_message("i cant attach files here!", ephemeral=True)
        return

    # check the user has the cat if required
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    if cat_type:
        available = await get_available_cat_count(user, cat_type)
        if available <= 0:
            await message.response.send_message("you dont have any available cats of that type (they might be on an adventure)", ephemeral=True)
            return

    image = f"images/spawn/{cat_type.lower()}_cat.png" if cat_type else "images/cat.png"
    file = discord.File(image, filename=image)
    await message.response.send_message(file=file)


@bot.tree.command(description="Get Cursed Cat")
async def cursed(message: discord.Interaction):
    perms = await fetch_perms(message)
    if not perms.attach_files:
        await message.response.send_message("i cant attach files here!", ephemeral=True)
        return
    file = discord.File("images/cursed.jpg", filename="cursed.jpg")
    await message.response.send_message(file=file)


@bot.tree.command(description="Get Your balance")
async def bal(message: discord.Interaction):
    perms = await fetch_perms(message)
    if not perms.send_messages:
        await message.response.send_message("i cant send messages here!", ephemeral=True)
        return
    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    embed = discord.Embed(title="Kibble balance", color=Colors.brown, description=f"You have {profile.kibble:,} Kibble.")
    await message.response.send_message(embed=embed)


@bot.tree.command(description="Convert cats to Kibble via the CatATM (irreversible)")
async def atm(message: discord.Interaction):
    """Open an ATM embed with a button to select cat type and amount to convert."""
    await message.response.defer()
    guild_id = message.guild.id
    owner_id = message.user.id

    embed = discord.Embed(
        title="CatATM",
        description="Convert your cats into Kibble. This is irreversible. Click the button below to choose a cat type and amount to convert.",
        color=Colors.brown,
    )

    class OpenATMView(View):
        def __init__(self, author_id: int):
            super().__init__(timeout=120)
            self.author_id = author_id

        @discord.ui.button(label="Convert cats", style=ButtonStyle.danger)
        async def open_modal(self, interaction: discord.Interaction, button: Button):
            if interaction.user.id != self.author_id:
                await do_funny(interaction)
                return
            # Build a dropdown (Select) of cat types the user can convert (per-instance availability checked)
            profile = await Profile.get_or_create(guild_id=guild_id, user_id=owner_id)
            options = []
            for ct in cattypes:
                try:
                    avail = await get_available_cat_count(profile, ct)
                except Exception:
                    avail = 0
                if avail > 0:
                    label = f"{ct} (x{avail})"
                    options.append(discord.SelectOption(label=label, value=ct, description=f"You have {avail} available"))

            if not options:
                # Nothing to list — complete next bit: inform user and return
                await interaction.response.send_message("You have no convertible cats (all either favourite or on adventure).", ephemeral=True)
                return

            class CatTypeSelect(discord.ui.Select):
                def __init__(self, opts: list[discord.SelectOption]):
                    super().__init__(placeholder="Choose a cat type to convert...", min_values=1, max_values=1, options=opts)

                async def callback(self2, select_interaction: discord.Interaction):
                    if select_interaction.user.id != owner_id:
                        await do_funny(select_interaction)
                        return
                    chosen = select_interaction.data.get("values", [None])[0]
                    if not chosen:
                        await select_interaction.response.send_message("No cat type selected.", ephemeral=True)
                        return
                    # refresh profile and available count
                    prof = await Profile.get_or_create(guild_id=guild_id, user_id=owner_id)
                    avail_now = await get_available_cat_count(prof, chosen)
                    if avail_now <= 0:
                        await select_interaction.response.edit_message(content="Selected cat type is no longer available.", embed=None, view=None)
                        return

                    # build amount options (1,5,10,all capped to avail_now)
                    amount_options = []
                    for n in [1, 5, 10, 25, 50]:
                        if n <= avail_now:
                            amount_options.append(discord.SelectOption(label=str(n), value=str(n)))
                    if avail_now not in [1,5,10,25,50]:
                        amount_options.append(discord.SelectOption(label=f"All ({avail_now})", value=str(avail_now)))

                    class AmountSelect(discord.ui.Select):
                        def __init__(self, opts: list[discord.SelectOption]):
                            super().__init__(placeholder="Choose amount to convert...", min_values=1, max_values=1, options=opts)

                        async def callback(self3, amt_inter: discord.Interaction):
                            if amt_inter.user.id != owner_id:
                                await do_funny(amt_inter)
                                return
                            amt_val = amt_inter.data.get("values", [None])[0]
                            try:
                                amt_int = int(amt_val)
                                if amt_int < 1:
                                    raise Exception
                            except Exception:
                                await amt_inter.response.send_message("Invalid amount selected.", ephemeral=True)
                                return

                            # proceed to instance selection (same logic as before)
                            chosen_ct = chosen
                            amt = amt_int
                            prof_now = await Profile.get_or_create(guild_id=guild_id, user_id=owner_id)
                            available2 = await get_available_cat_count(prof_now, chosen_ct)
                            if available2 <= 0:
                                await amt_inter.response.send_message("You don't have any available cats of that type to convert.", ephemeral=True)
                                return
                            if amt > available2:
                                await amt_inter.response.send_message(f"You only have {available2} available {chosen_ct} cats to convert.", ephemeral=True)
                                return

                            user_cats = get_user_cats(guild_id, owner_id)
                            candidates = [c for c in user_cats if c.get("type") == chosen_ct and not c.get("on_adventure") and not c.get("favorite")]
                            def cand_key(x):
                                try:
                                    bondv = int(x.get("bond", 0))
                                except Exception:
                                    bondv = 0
                                try:
                                    at = int(x.get("acquired_at") or 0)
                                except Exception:
                                    at = 0
                                return (bondv, at)
                            candidates.sort(key=cand_key)

                            try:
                                per_value = sum(type_dict.values()) / type_dict.get(chosen_ct, 100)
                            except Exception:
                                per_value = 100
                            kib_per = max(1, int(round(per_value)))

                            sel_limit = amt
                            max_display = max(0, 25 - 2)
                            display_cands = candidates[:max_display]
                            if not display_cands:
                                await amt_inter.response.send_message("No available instances to select. Have you tried inspecting them in your inventory? (More Details > [cat type])", ephemeral=True)
                                return

                            sel_embed = discord.Embed(
                                title=f"Select up to {sel_limit} {chosen_ct} instance(s)",
                                description=("Click instance buttons to toggle selection.\n"
                                             "Selected instances are shown below. When ready, press Proceed to confirm conversion (may destroy cats)."),
                                color=Colors.brown,
                            )
                            sel_embed.add_field(name="Selected (0)", value="No instances selected yet.", inline=False)

                            class SelectionView(View):
                                def __init__(self, owner_id: int, candidates: list[dict], limit: int):
                                    super().__init__(timeout=180)
                                    self.owner_id = owner_id
                                    self.candidates = candidates
                                    self.limit = limit
                                    self.selected = []
                                    for c in candidates:
                                        cid = c.get('id')
                                        lbl = f"#{cid} {c.get('name') or 'Unnamed'} (bond {c.get('bond',0)})"
                                        btn = Button(label=lbl, style=ButtonStyle.secondary)
                                        async def make_cb(interaction2: discord.Interaction, cid_local=cid, btn_local=btn):
                                            if interaction2.user.id != self.owner_id:
                                                await do_funny(interaction2)
                                                return
                                            if cid_local in self.selected:
                                                self.selected.remove(cid_local)
                                                try:
                                                    btn_local.style = ButtonStyle.secondary
                                                    btn_local.label = btn_local.label.replace('✅ ', '')
                                                except Exception:
                                                    pass
                                            else:
                                                if len(self.selected) >= self.limit:
                                                    await interaction2.response.send_message(f"You can only select up to {self.limit} instances.", ephemeral=True)
                                                    return
                                                self.selected.append(cid_local)
                                                try:
                                                    btn_local.style = ButtonStyle.success
                                                    btn_local.label = '✅ ' + btn_local.label
                                                except Exception:
                                                    pass
                                            selected_objs = [next((x for x in self.candidates if x.get('id') == sid), None) for sid in self.selected]
                                            lines = [f"#{x.get('id')} {x.get('name')} (bond {x.get('bond',0)})" for x in selected_objs if x]
                                            if not lines:
                                                lines = ["No instances selected yet."]
                                            new_embed = discord.Embed(title=sel_embed.title, description=sel_embed.description, color=Colors.brown)
                                            new_embed.add_field(name=f"Selected ({len(lines)})", value="\n".join(lines), inline=False)
                                            try:
                                                await interaction2.response.edit_message(embed=new_embed, view=self)
                                            except Exception:
                                                try:
                                                    await interaction2.followup.send("Selection updated.", ephemeral=True)
                                                except Exception:
                                                    pass
                                        btn.callback = make_cb
                                        self.add_item(btn)

                                    proceed = Button(label="Proceed", style=ButtonStyle.danger)
                                    cancel = Button(label="Cancel", style=ButtonStyle.secondary)

                                    async def proceed_cb(interaction2: discord.Interaction):
                                        if interaction2.user.id != self.owner_id:
                                            await do_funny(interaction2)
                                            return
                                        if not self.selected:
                                            await interaction2.response.send_message("No instances selected.", ephemeral=True)
                                            return
                                        if len(self.selected) > self.limit:
                                            await interaction2.response.send_message(f"You selected too many instances (max {self.limit}).", ephemeral=True)
                                            return
                                        selected_objs = [next((x for x in self.candidates if x.get('id') == sid), None) for sid in self.selected]
                                        selected_objs = [s for s in selected_objs if s]
                                        total_kibble_local = kib_per * len(selected_objs)
                                        confirm_embed2 = discord.Embed(
                                            title="WARNING: Final confirmation",
                                            description=(f"Converting these {len(selected_objs)} cat(s) will permanently remove them and grant {total_kibble_local:,} Kibble.\n"
                                                         "This action cannot be undone. Are you sure?"),
                                            color=Colors.maroon,
                                        )
                                        lines2 = [f"#{s.get('id')} {s.get('name')} (bond {s.get('bond',0)})" for s in selected_objs]
                                        if lines2:
                                            confirm_embed2.add_field(name="Selected instances", value="\n".join(lines2), inline=False)

                                        class FinalConfirmView(View):
                                            def __init__(self, owner_id: int):
                                                super().__init__(timeout=120)
                                                self.owner_id = owner_id

                                            @discord.ui.button(label="Confirm Conversion", style=ButtonStyle.danger)
                                            async def final_confirm(self3, interaction3: discord.Interaction, button: Button):
                                                if interaction3.user.id != self3.owner_id:
                                                    await do_funny(interaction3)
                                                    return
                                                await interaction3.response.defer()
                                                try:
                                                    profile_now = await Profile.get_or_create(guild_id=guild_id, user_id=owner_id)
                                                    cats_now = get_user_cats(guild_id, owner_id)
                                                    ids_to_remove = set(s.get('id') for s in selected_objs)
                                                    cats_after = [c for c in cats_now if c.get('id') not in ids_to_remove]
                                                    save_user_cats(guild_id, owner_id, cats_after)
                                                    try:
                                                        profile_now[f"cat_{chosen_ct}"] = max(0, profile_now[f"cat_{chosen_ct}"] - len(selected_objs))
                                                    except Exception:
                                                        pass
                                                    profile_now.kibble += kib_per * len(selected_objs)
                                                    await profile_now.save()
                                                    await interaction3.edit_original_response(content=f"Converted {len(selected_objs)} {chosen_ct} cat(s) into {kib_per * len(selected_objs):,} Kibble.", embed=None, view=None)
                                                except Exception:
                                                    await interaction3.edit_original_response(content="Conversion failed.", embed=None, view=None)

                                            @discord.ui.button(label="Cancel", style=ButtonStyle.secondary)
                                            async def final_cancel(self3, interaction3: discord.Interaction, button: Button):
                                                if interaction3.user.id != self3.owner_id:
                                                    await do_funny(interaction3)
                                                    return
                                                await interaction3.response.edit_message(content="Conversion cancelled.", embed=None, view=None)

                                        try:
                                            await interaction2.response.edit_message(embed=confirm_embed2, view=FinalConfirmView(self.owner_id))
                                        except Exception:
                                            try:
                                                await interaction2.followup.send(embed=confirm_embed2, view=FinalConfirmView(self.owner_id), ephemeral=True)
                                            except Exception:
                                                pass

                                    async def cancel_cb(interaction2: discord.Interaction):
                                        if interaction2.user.id != self.owner_id:
                                            await do_funny(interaction2)
                                            return
                                        await interaction2.response.edit_message(content="Selection cancelled.", embed=None, view=None)

                                    proceed.callback = proceed_cb
                                    cancel.callback = cancel_cb
                                    self.add_item(proceed)
                                    self.add_item(cancel)

                            # send selection view
                            try:
                                await amt_inter.response.edit_message(embed=sel_embed, view=SelectionView(owner_id, display_cands, sel_limit))
                            except Exception:
                                try:
                                    await amt_inter.followup.send(embed=sel_embed, view=SelectionView(owner_id, display_cands, sel_limit), ephemeral=True)
                                except Exception:
                                    pass

                    amt_view = View(timeout=120)
                    amt_view.add_item(AmountSelect(amount_options))
                    try:
                        await select_interaction.response.edit_message(content="Choose amount to convert:", embed=None, view=amt_view)
                    except Exception:
                        await select_interaction.followup.send("Choose amount to convert:", view=amt_view, ephemeral=True)

            ct_view = View(timeout=120)
            ct_view.add_item(CatTypeSelect(options))
            try:
                await interaction.response.send_message("Choose a cat type to convert:", view=ct_view, ephemeral=True)
            except Exception:
                await interaction.response.send_message("Could not open selection UI.", ephemeral=True)

    view = OpenATMView(owner_id)
    await message.followup.send(embed=embed, view=view)


@bot.tree.command(description="Brew some coffee to catch cats more efficiently")
async def brew(message: discord.Interaction):
    await message.response.send_message("HTTP 418: I'm a teapot. <https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/418>")
    await achemb(message, "coffee", "send")


@bot.tree.command(description="Gamble your life savings away in our totally-not-rigged catsino!")
async def casino(message: discord.Interaction):
    if message.user.id + message.guild.id in casino_lock:
        await message.response.send_message(
            "you get kicked out of the catsino because you are already there, and two of you playing at once would cause a glitch in the universe",
            ephemeral=True,
        )
        await achemb(message, "paradoxical_gambler", "send")
        return

    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    # funny global gamble counter cus funny
    total_sum = await Profile.sum("gambles", "gambles > 0")
    embed = discord.Embed(
        title="🎲 The Catsino",
        description=f"One spin costs 5 {get_emoji('finecat')} Fine cats\nSo far you gambled {profile.gambles} times.\nAll KITTAYYYYYYY users gambled {total_sum:,} times.",
        color=Colors.maroon,
    )

    async def spin(interaction):
        nonlocal message
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        if message.user.id + message.guild.id in casino_lock:
            await interaction.response.send_message(
                "you get kicked out of the catsino because you are already there, and two of you playing at once would cause a glitch in the universe",
                ephemeral=True,
            )
            return

        await profile.refresh_from_db()
        if profile.cat_Fine < 5:
            await interaction.response.send_message("you are too broke now", ephemeral=True)
            await achemb(interaction, "broke", "send")
            return

        await interaction.response.defer()
        amount = random.randint(1, 5)
        casino_lock.append(message.user.id + message.guild.id)
        profile.cat_Fine += amount - 5
        profile.gambles += 1
        await profile.save()

        if profile.gambles >= 10:
            await achemb(message, "gambling_one", "send")
        if profile.gambles >= 50:
            await achemb(message, "gambling_two", "send")

        variants = [
            f"{get_emoji('egirlcat')} 1 eGirl cats",
            f"{get_emoji('egirlcat')} 3 eGirl cats",
            f"{get_emoji('ultimatecat')} 2 Ultimate cats",
            f"{get_emoji('corruptcat')} 7 Corrupt cats",
            f"{get_emoji('divinecat')} 4 Divine cats",
            f"{get_emoji('epiccat')} 10 Epic cats",
            f"{get_emoji('professorcat')} 5 Professor cats",
            f"{get_emoji('realcat')} 2 Real cats",
            f"{get_emoji('legendarycat')} 5 Legendary cats",
            f"{get_emoji('mythiccat')} 2 Mythic cats",
            f"{get_emoji('8bitcat')} 7 8bit cats",
        ]

        random.shuffle(variants)
        icon = "🎲"

        for i in variants:
            embed = discord.Embed(title=f"{icon} The Catsino", description=f"**{i}**", color=Colors.maroon)
            try:
                await interaction.edit_original_response(embed=embed, view=None)
            except Exception:
                pass
            await asyncio.sleep(1)

        embed = discord.Embed(
            title=f"{icon} The Catsino",
            description=f"You won:\n**{get_emoji('finecat')} {amount} Fine cats**",
            color=Colors.maroon,
        )

        button = Button(label="Spin", style=ButtonStyle.blurple)
        button.callback = spin

        myview = View(timeout=VIEW_TIMEOUT)
        myview.add_item(button)

        casino_lock.remove(message.user.id + message.guild.id)

        try:
            await interaction.edit_original_response(embed=embed, view=myview)
        except Exception:
            await interaction.followup.send(embed=embed, view=myview)

    button = Button(label="Spin", style=ButtonStyle.blurple)
    button.callback = spin

    myview = View(timeout=VIEW_TIMEOUT)
    myview.add_item(button)

    await message.response.send_message(embed=embed, view=myview)


@bot.tree.command(description="oh no")
async def slots(message: discord.Interaction):
    if message.user.id + message.guild.id in slots_lock:
        await message.response.send_message(
            "you get kicked from the slot machine because you are already there, and two of you playing at once would cause a glitch in the universe",
            ephemeral=True,
        )
        await achemb(message, "paradoxical_gambler", "send")
        return

    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    total_spins, total_wins, total_big_wins = (
        await Profile.sum("slot_spins", "slot_spins > 0"),
        await Profile.sum("slot_wins", "slot_wins > 0"),
        await Profile.sum("slot_big_wins", "slot_big_wins > 0"),
    )
    embed = discord.Embed(
        title=":slot_machine: The Slot Machine",
        description=f"__Your stats__\n{profile.slot_spins:,} spins\n{profile.slot_wins:,} wins\n{profile.slot_big_wins:,} big wins\n\n__Global stats__\n{total_spins:,} spins\n{total_wins:,} wins\n{total_big_wins:,} big wins",
        color=Colors.maroon,
    )

    async def remove_debt(interaction):
        nonlocal message
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        await profile.refresh_from_db()

        # remove debt
        for i in cattypes:
            profile[f"cat_{i}"] = max(0, profile[f"cat_{i}"])

        await profile.save()
        await interaction.response.send_message("You have removed your debts! Life is wonderful!", ephemeral=True)
        await achemb(interaction, "debt", "send")

    async def spin(interaction):
        nonlocal message
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        if message.user.id + message.guild.id in slots_lock:
            await interaction.response.send_message(
                "you get kicked from the slot machine because you are already there, and two of you playing at once would cause a glitch in the universe",
                ephemeral=True,
            )
            return
        await profile.refresh_from_db()

        await interaction.response.defer()
        slots_lock.append(message.user.id + message.guild.id)
        profile.slot_spins += 1
        await profile.save()

        await achemb(interaction, "slots", "send")
        await progress(message, profile, "slots")
        await progress(message, profile, "slots2")

        variants = ["🍒", "🍋", "🍇", "🔔", "⭐", ":seven:"]
        reel_durations = [random.randint(9, 12), random.randint(15, 22), random.randint(25, 28)]
        random.shuffle(reel_durations)

        # the k number is much cycles it will go before stopping + 1
        col1 = random.choices(variants, k=reel_durations[0])
        col2 = random.choices(variants, k=reel_durations[1])
        col3 = random.choices(variants, k=reel_durations[2])

        if message.user.id in rigged_users:
            col1[len(col1) - 2] = ":seven:"
            col2[len(col2) - 2] = ":seven:"
            col3[len(col3) - 2] = ":seven:"

        blank_emoji = get_emoji("empty")
        for slot_loop_ind in range(1, max(reel_durations) - 1):
            current1 = min(len(col1) - 2, slot_loop_ind)
            current2 = min(len(col2) - 2, slot_loop_ind)
            current3 = min(len(col3) - 2, slot_loop_ind)
            desc = ""
            for offset in [-1, 0, 1]:
                if offset == 0:
                    desc += f"➡️ {col1[current1 + offset]} {col2[current2 + offset]} {col3[current3 + offset]} ⬅️\n"
                else:
                    desc += f"{blank_emoji} {col1[current1 + offset]} {col2[current2 + offset]} {col3[current3 + offset]} {blank_emoji}\n"
            embed = discord.Embed(
                title=":slot_machine: The Slot Machine",
                description=desc,
                color=Colors.maroon,
            )
            try:
                await interaction.edit_original_response(embed=embed, view=None)
            except Exception:
                pass
            await asyncio.sleep(0.5)

        await profile.refresh_from_db()
        big_win = False
        if col1[current1] == col2[current2] == col3[current3]:
            profile.slot_wins += 1
            if col1[current1] == ":seven:":
                desc = "**BIG WIN!**\n\n" + desc
                profile.slot_big_wins += 1
                big_win = True
                await profile.save()
                await achemb(interaction, "big_win_slots", "send")
            else:
                desc = "**You win!**\n\n" + desc
                await profile.save()
            await achemb(interaction, "win_slots", "send")
        else:
            desc = "**You lose!**\n\n" + desc

        button = Button(label="Spin", style=ButtonStyle.blurple)
        button.callback = spin

        myview = View(timeout=VIEW_TIMEOUT)
        myview.add_item(button)

        if big_win:
            # check if user has debt in any cat type
            has_debt = False
            for i in cattypes:
                if profile[f"cat_{i}"] < 0:
                    has_debt = True
                    break
            if has_debt:
                desc += "\n\n**You can remove your debt!**"
                button = Button(label="Remove Debt", style=ButtonStyle.blurple)
                button.callback = remove_debt
                myview.add_item(button)

        slots_lock.remove(message.user.id + message.guild.id)

        embed = discord.Embed(title=":slot_machine: The Slot Machine", description=desc, color=Colors.maroon)

        try:
            await interaction.edit_original_response(embed=embed, view=myview)
        except Exception:
            await interaction.followup.send(embed=embed, view=myview)

    button = Button(label="Spin", style=ButtonStyle.blurple)
    button.callback = spin

    myview = View(timeout=VIEW_TIMEOUT)
    myview.add_item(button)

    await message.response.send_message(embed=embed, view=myview)


@bot.tree.command(description="roll a dice")
async def roll(message: discord.Interaction, sides: Optional[int]):
    if sides is not None and sides < 1:
        await message.response.send_message("please get a life", ephemeral=True)
        return
    if not sides:
        sides = 6

    # loosely based on this wikipedia article
    # https://en.wikipedia.org/wiki/Dice
    dice_names = {
        1: '"dice"',
        2: "coin",
        4: "tetrahedron",
        5: "triangular prism",
        6: "cube",
        7: "pentagonal prism",
        8: "octahedron",
        9: "hexagonal prism",
        10: "pentagonal trapezohedron",
        12: "dodecahedron",
        14: "heptagonal trapezohedron",
        16: "octagonal bipyramid",
        18: "rounded rhombicuboctahedron",
        20: "icosahedron",
        24: "triakis octahedron",
        30: "rhombic triacontahedron",
        34: "heptadecagonal trapezohedron",
        48: "disdyakis dodecahedron",
        50: "icosipentagonal trapezohedron",
        60: "deltoidal hexecontahedron",
        100: "zocchihedron",
        120: "disdyakis triacontahedron",
    }

    if sides in dice_names.keys():
        dice = dice_names[sides]
    else:
        dice = f"d{sides}"

    if sides == 2:
        coinflipresult = random.randint(1, 2)
        if coinflipresult == 2:
            side = "tails"
        else:
            side = "heads"
        await message.response.send_message(f"🪙 your coin lands on **{side}** ({coinflipresult})")
    else:
        await message.response.send_message(f"🎲 your {dice} lands on **{random.randint(1, sides)}**")
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    await progress(message, user, "roll")


@bot.tree.command(description="get a super accurate rating of something")
@discord.app_commands.describe(thing="The thing or person to check", stat="The stat to check")
async def rate(message: discord.Interaction, thing: str, stat: str):
    if len(thing) > 100 or len(stat) > 100:
        await message.response.send_message("thats kinda long", ephemeral=True)
        return
    if thing.lower() == "/rate" and stat.lower() == "correct":
        await message.response.send_message("/rate is 100% correct")
    else:
        await message.response.send_message(f"{thing} is {random.randint(0, 100)}% {stat}")
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    await progress(message, user, "rate")


@bot.tree.command(name="8ball", description="ask the magic catball")
@discord.app_commands.describe(question="your question to the catball")
async def eightball(message: discord.Interaction, question: str):
    if len(question) > 300:
        await message.response.send_message("thats kinda long", ephemeral=True)
        return

    catball_responses = [
        # positive
        "it is certain",
        "it is decidedly so",
        "without a doubt",
        "yes definitely",
        "you may rely on it",
        "as i see it, yes",
        "most likely",
        "outlook good",
        "yes",
        "signs point to yes",
        # negative
        "dont count on it",
        "my reply is no",
        "my sources say no",
        "outlook not so good",
        "very doubtful",
        "most likely not",
        "unlikely",
        "no definitely",
        "no",
        "signs point to no",
        # neutral
        "reply hazy, try again",
        "ask again later",
        "better not tell you now",
        "cannot predict now",
        "concetrate and ask again",
    ]

    await message.response.send_message(f"{question}\n:8ball: **{random.choice(catball_responses)}**")
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    await progress(message, user, "catball")
    await achemb(message, "balling", "send")


@bot.tree.command(description="the most engaging boring game")
async def pig(message: discord.Interaction):
    score = 0

    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)

    async def roll(interaction: discord.Interaction):
        nonlocal score
        if interaction.user != message.user:
            await do_funny(interaction)
            return

        await interaction.response.defer()

        if score == 0:
            # dont roll 1 on first roll
            roll_result = random.randint(2, 6)
        else:
            roll_result = random.randint(1, 6)

        if roll_result == 1:
            # gg
            last_score = score
            score = 0
            view = View(timeout=3600)
            button = Button(label="Play Again", emoji="🎲", style=ButtonStyle.blurple)
            button.callback = roll
            view.add_item(button)
            await interaction.edit_original_response(
                content=f"*Oops!* You rolled a **1** and lost your {last_score} score...\nFinal score: 0\nBetter luck next time!", view=view
            )
        else:
            score += roll_result
            view = View(timeout=3600)
            button = Button(label="Roll", emoji="🎲", style=ButtonStyle.blurple)
            button.callback = roll
            button2 = Button(label="Save & Finish")
            button2.callback = finish
            view.add_item(button)
            view.add_item(button2)
            await interaction.edit_original_response(content=f"🎲 +{roll_result}\nCurrent score: {score:,}", view=view)

    async def finish(interaction: discord.Interaction):
        nonlocal score
        if interaction.user != message.user:
            await do_funny(interaction)
            return

        await interaction.response.defer()

        await profile.refresh_from_db()

        if score > profile.best_pig_score:
            profile.best_pig_score = score
            await profile.save()

        if score >= 20:
            await progress(message, profile, "pig")
        if score >= 50:
            await achemb(interaction, "pig50", "send")
        if score >= 100:
            await achemb(interaction, "pig100", "send")

        last_score = score
        score = 0
        view = View(timeout=3600)
        button = Button(label="Play Again", emoji="🎲", style=ButtonStyle.blurple)
        button.callback = roll
        view.add_item(button)
        await interaction.edit_original_response(content=f"*Congrats!*\nYou finished with {last_score} score!", view=view)

    view = View(timeout=3600)
    button = Button(label="Play!", emoji="🎲", style=ButtonStyle.blurple)
    button.callback = roll
    view.add_item(button)
    await message.response.send_message(
        f"🎲 Pig is a simple dice game. You repeatedly roll a die. The number it lands on gets added to your score, then you can either roll the die again, or finish and save your current score. However, if you roll a 1, you lose and your score gets voided.\n\nYour current best score is **{profile.best_pig_score:,}**.",
        view=view,
    )


@bot.tree.command(description="get a reminder in the future (+- 5 minutes)")
@discord.app_commands.describe(
    days="in how many days",
    hours="in how many hours",
    minutes="in how many minutes (+- 5 minutes)",
    text="what to remind",
)
async def remind(
    message: discord.Interaction,
    days: Optional[int],
    hours: Optional[int],
    minutes: Optional[int],
    text: Optional[str],
):
    if not days:
        days = 0
    if not hours:
        hours = 0
    if not minutes:
        minutes = 0
    if not text:
        text = "Reminder!"

    goal_time = int(time.time() + (days * 86400) + (hours * 3600) + (minutes * 60))
    if goal_time > time.time() + (86400 * 365 * 20):
        await message.response.send_message("cats do not live for that long", ephemeral=True)
        return
    if len(text) > 1900:
        await message.response.send_message("thats too long", ephemeral=True)
        return
    if goal_time < 0:
        await message.response.send_message("cat cant time travel (yet)", ephemeral=True)
        return
    await message.response.send_message(f"🔔 ok, <t:{goal_time}:R> (+- 5 min) ill remind you of:\n{text}")
    msg = await message.original_response()
    message_link = msg.jump_url
    text += f"\n\n*This is a [reminder](<{message_link}>) you set.*"
    await Reminder.create(user_id=message.user.id, text=text, time=goal_time)
    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    profile.reminders_set += 1
    await profile.save()
    await achemb(message, "reminder", "send")  # the ai autocomplete thing suggested this and its actually a cool ach
    await progress(message, profile, "reminder")  # the ai autocomplete thing also suggested this though profile wasnt defined


@bot.tree.command(name="random", description="Get a random cat")
async def random_cat(message: discord.Interaction):
    await message.response.defer()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                "https://api.thecatapi.com/v1/images/search", headers={"User-Agent": "CatBot/1.0 https://github.com/milenakos/cat-bot"}
            ) as response:
                data = await response.json()
                await message.followup.send(data[0]["url"])
                await achemb(message, "randomizer", "send")
        except Exception:
            await message.followup.send("no cats :(")


if config.WORDNIK_API_KEY:

    @bot.tree.command(description="define a word")
    async def define(message: discord.Interaction, word: str):
        word = word.lower()
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"https://api.wordnik.com/v4/word.json/{word}/definitions?api_key={config.WORDNIK_API_KEY}&useCanonical=true&includeTags=false&includeRelated=false&limit=69",
                    headers={"User-Agent": "CatBot/1.0 https://github.com/milenakos/cat-bot"},
                ) as response:
                    data = await response.json()

                    # lazily filter some things
                    text = (await response.text()).lower()
                    for test in ["vulgar", "slur", "offensive", "profane", "insult", "abusive", "derogatory"]:
                        if test in text:
                            await message.response.send_message(f"__{message.user.name}__\na stupid idiot (result was filtered)", ephemeral=True)
                            return

                    # sometimes the api returns results without definitions, so we search for the first one which has a definition
                    for i in data:
                        if "text" in i.keys():
                            clean_data = re.sub(re.compile("<.*?>"), "", i["text"])
                            await message.response.send_message(
                                f"__{word}__\n{clean_data}\n-# [{i['attributionText']}](<{i['attributionUrl']}>) Powered by [Wordnik](<{i['wordnikUrl']}>)"
                            )
                            await achemb(message, "define", "send")
                            return

                    raise Exception
            except Exception:
                await message.response.send_message("no definition found", ephemeral=True)


@bot.tree.command(name="fact", description="get a random cat fact")
async def cat_fact(message: discord.Interaction):
    facts = [
        "you love cats",
        f"KITTAYYYYYYY is in {len(bot.guilds):,} servers",
        "cat",
        "cats are the best",
    ]

    # give a fact from the list or the API
    if random.randint(0, 10) == 0:
        await message.response.send_message(random.choice(facts))
    else:
        await message.response.defer()
        async with aiohttp.ClientSession() as session:
            async with session.get("https://catfact.ninja/fact", headers={"User-Agent": "CatBot/1.0 https://github.com/milenakos/cat-bot"}) as response:
                if response.status == 200:
                    data = await response.json()
                    await message.followup.send(data["fact"])
                else:
                    await message.followup.send("failed to fetch a cat fact.")

    if not isinstance(
        message.channel,
        Union[
            discord.TextChannel,
            discord.StageChannel,
            discord.VoiceChannel,
            discord.Thread,
        ],
    ):
        return

    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    user.facts += 1
    await user.save()
    if user.facts >= 10:
        await achemb(message, "fact_enjoyer", "send")

    try:
        channel = await Channel.get_or_none(channel_id=message.channel.id)
        if channel and channel.cattype == "Professor":
            await achemb(message, "nerd_battle", "send")
    except Exception:
        pass


async def light_market(message):
    cataine_prices = [
        [10, "Fine"],
        [30, "Fine"],
        [20, "Good"],
        [15, "Rare"],
        [20, "Wild"],
        [10, "Epic"],
        [20, "Sus"],
        [15, "Rickroll"],
        [7, "Superior"],
        [5, "Legendary"],
        [3, "8bit"],
        [4, "Divine"],
        [3, "Real"],
        [2, "Ultimate"],
        [1, "eGirl"],
    ]
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    if user.cataine_active < int(time.time()):
        count = user.cataine_week
        lastweek = user.recent_week
        embed = discord.Embed(
            title="The Mafia Hideout",
            description="you break down the door. the cataine machine lists what it needs.",
        )

        if lastweek != datetime.datetime.utcnow().isocalendar()[1]:
            lastweek = datetime.datetime.utcnow().isocalendar()[1]
            count = 0
            user.cataine_week = 0
            user.recent_week = datetime.datetime.utcnow().isocalendar()[1]
            await user.save()

        state = random.getstate()
        random.seed(datetime.datetime.utcnow().isocalendar()[1])
        deals = []

        r = range(random.randint(3, 5))
        for i in r:
            # 3-5 prices are possible per week
            deals.append(random.randint(0, 14))

        deals.sort()

        for i in r:
            deals[i] = cataine_prices[deals[i]]

        random.setstate(state)
        if count < len(deals):
            deal = deals[count]
        else:
            embed = discord.Embed(
                title="The Mafia Hideout",
                description="you have used up all of your cataine for the week. please come back later.",
            )
            await message.followup.send(embed=embed, ephemeral=True)
            return

        type = deal[1]
        amount = deal[0]
        embed.add_field(
            name="🧂 12h of Cataine",
            value=f"Price: {get_emoji(type.lower() + 'cat')} {amount} {type}",
        )

        async def make_cataine(interaction):
            nonlocal message, type, amount
            await user.refresh_from_db()
            available = await get_available_cat_count(user, type)
            if available < amount or user.cataine_active > time.time():
                return
            user[f"cat_{type}"] -= amount
            user.cataine_active = int(time.time()) + 43200
            user.cataine_week += 1
            user.cataine_bought += 1
            await user.save()
            await interaction.response.send_message(
                "The machine spools down. Your cat catches will be doubled for the next 12 hours.",
                ephemeral=True,
            )

        myview = View(timeout=VIEW_TIMEOUT)

        if user[f"cat_{type}"] >= amount:
            button = Button(label="Buy", style=ButtonStyle.blurple)
        else:
            button = Button(
                label="You don't have enough cats!",
                disabled=True,
            )
        button.callback = make_cataine

        myview.add_item(button)

        await message.followup.send(embed=embed, view=myview, ephemeral=True)
    else:
        embed = discord.Embed(
            title="The Mafia Hideout",
            description=f"the machine is recovering. you can use machine again <t:{user.cataine_active}:R>.",
        )
        await message.followup.send(embed=embed, ephemeral=True)


async def dark_market(message):
    cataine_prices = [
        [5, "Fine"],
        [5, "Good"],
        [4, "Wild"],
        [4, "Epic"],
        [3, "Brave"],
        [3, "Reverse"],
        [2, "Trash"],
        [2, "Mythic"],
        [1, "Corrupt"],
        [1, "Divine"],
        [100, "eGirl"],
    ]
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    if user.cataine_active < int(time.time()):
        level = user.dark_market_level
        embed = discord.Embed(
            title="The Dark Market",
            description="after entering the secret code, they let you in. today's deal is:",
        )
        embed.set_author(name="Click here to open Wiki", url="https://wiki.minkos.lol/en/dark-market")
        deal = cataine_prices[level] if level < len(cataine_prices) else cataine_prices[-1]
        type = deal[1]
        amount = deal[0]
        embed.add_field(
            name="🧂 12h of Cataine",
            value=f"Price: {get_emoji(type.lower() + 'cat')} {amount} {type}",
        )

        async def buy_cataine(interaction):
            nonlocal message, type, amount
            await user.refresh_from_db()
            if user[f"cat_{type}"] < amount or user.cataine_active > time.time():
                return
            user[f"cat_{type}"] -= amount
            user.cataine_active = int(time.time()) + 43200
            user.dark_market_level += 1
            user.cataine_bought += 1
            await user.save()
            await interaction.response.send_message(
                "Thanks for buying! Your cat catches will be doubled for the next 12 hours.",
                ephemeral=True,
            )

        debounce = False

        async def complain(interaction):
            nonlocal debounce
            if debounce:
                return
            debounce = True

            person = interaction.user
            phrases = [
                "*Because of my addiction I'm paying them a fortune.*",
                f"**{person}**: Hey, I'm not fine with those prices.",
                "**???**: Hmm?",
                "**???**: Oh.",
                "**???**: It seems you don't understand.",
                "**???**: We are the ones setting prices, not you.",
                f"**{person}**: Give me a more fair price or I will report you to the police.",
                "**???**: Huh?",
                "**???**: Well, it seems like you chose...",
                "# DEATH",
                "**???**: Better start running :)",
                "*Uh oh.*",
            ]

            await interaction.response.send_message("*That's not funny anymore. Those prices are insane.*", ephemeral=True)
            await asyncio.sleep(5)
            for i in phrases:
                await interaction.followup.send(i, ephemeral=True)
                await asyncio.sleep(5)

            # there is actually no time pressure anywhere but try to imagine there is
            counter = 0

            async def step(interaction):
                nonlocal counter
                counter += 1
                await interaction.response.defer()
                if counter == 30:
                    try:
                        await interaction.edit_original_response(view=None)
                    except Exception:
                        pass

                    final_cutscene_followups = [
                        "You barely manage to turn around a corner and hide to run away.",
                        "You quietly get to the police station and tell them everything.",
                        "## The next day.",
                        "A nice day outside. You open the news:",
                        "*Dog Mafia, the biggest cataine distributor, was finally caught after anonymous report.*",
                        "HUH? It was dogs all along...",
                    ]

                    for phrase in final_cutscene_followups:
                        await asyncio.sleep(5)
                        await interaction.followup.send(phrase, ephemeral=True)

                    await asyncio.sleep(5)
                    user.story_complete = True
                    await user.save()
                    await achemb(interaction, "thanksforplaying", "send")

            run_view = View(timeout=VIEW_TIMEOUT)
            button = Button(label="RUN", style=ButtonStyle.green)
            button.callback = step
            run_view.add_item(button)

            await interaction.followup.send(
                "RUN!\nSpam the button a lot of times as fast as possible to run away!",
                view=run_view,
                ephemeral=True,
            )

        myview = View(timeout=VIEW_TIMEOUT)

        if level >= len(cataine_prices) - 1:
            button = Button(label="What???", style=ButtonStyle.red)
            button.callback = complain
        else:
            if user[f"cat_{type}"] >= amount:
                button = Button(label="Buy", style=ButtonStyle.blurple)
            else:
                button = Button(
                    label="You don't have enough cats!",
                    disabled=True,
                )
            button.callback = buy_cataine
        myview.add_item(button)

        await message.followup.send(embed=embed, view=myview, ephemeral=True)
    else:
        embed = discord.Embed(
            title="The Dark Market",
            description=f"you already bought from us recently. you can do next purchase <t:{user.cataine_active}:R>.",
        )
        await message.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(description="View your achievements")
async def achievements(message: discord.Interaction):
    # this is very close to /inv's ach counter
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    if user.funny >= 50:
        await achemb(message, "its_not_working", "send")

    unlocked = 0
    minus_achs = 0
    minus_achs_count = 0
    for k in ach_names:
        is_ach_hidden = ach_list[k]["category"] == "Hidden"
        if is_ach_hidden:
            minus_achs_count += 1
        if user[k]:
            if is_ach_hidden:
                minus_achs += 1
            else:
                unlocked += 1
    total_achs = len(ach_list) - minus_achs_count
    minus_achs = "" if minus_achs == 0 else f" + {minus_achs}"

    hidden_counter = 0

    # this is a single page of the achievement list
    async def gen_new(category):
        nonlocal message, unlocked, total_achs, hidden_counter

        unlocked = 0
        minus_achs = 0
        minus_achs_count = 0

        for k in ach_names:
            is_ach_hidden = ach_list[k]["category"] == "Hidden"
            if is_ach_hidden:
                minus_achs_count += 1
            if user[k]:
                if is_ach_hidden:
                    minus_achs += 1
                else:
                    unlocked += 1

        total_achs = len(ach_list) - minus_achs_count

        if minus_achs != 0:
            minus_achs = f" + {minus_achs}"
        else:
            minus_achs = ""

        hidden_suffix = ""

        if category == "Hidden":
            hidden_suffix = '\n\nThis is a "Hidden" category. Achievements here only show up after you complete them.'
            hidden_counter += 1
        else:
            hidden_counter = 0

        newembed = discord.Embed(
            title=category,
            description=f"Achievements unlocked (total): {unlocked}/{total_achs}{minus_achs}{hidden_suffix}",
            color=Colors.brown,
        ).set_footer(text=rain_shill)

        global_user = await User.get_or_create(user_id=message.user.id)
        if len(news_list) > len(global_user.news_state.strip()) or "0" in global_user.news_state.strip()[-4:]:
            newembed.set_author(name="You have unread news! /news")

        for k, v in ach_list.items():
            if v["category"] == category:
                if k == "thanksforplaying":
                    if user[k]:
                        newembed.add_field(
                            name=str(get_emoji("demonic_ach")) + " Cataine Addict",
                            value="Defeat the dog mafia",
                            inline=True,
                        )
                    else:
                        newembed.add_field(
                            name=str(get_emoji("no_demonic_ach")) + " Thanks For Playing",
                            value="Complete the story",
                            inline=True,
                        )
                    continue

                icon = str(get_emoji("no_ach")) + " "
                if user[k]:
                    newembed.add_field(
                        name=str(get_emoji("ach")) + " " + v["title"],
                        value=v["description"],
                        inline=True,
                    )
                elif category != "Hidden":
                    newembed.add_field(
                        name=icon + v["title"],
                        value="???" if v["is_hidden"] else v["description"],
                        inline=True,
                    )

        return newembed

    # creates buttons at the bottom of the full view
    def insane_view_generator(category):
        myview = View(timeout=VIEW_TIMEOUT)
        buttons_list = []

        async def callback_hell(interaction):
            thing = interaction.data["custom_id"]
            await interaction.response.defer()
            try:
                await interaction.edit_original_response(embed=await gen_new(thing), view=insane_view_generator(thing))
            except Exception:
                pass

            if hidden_counter == 3 and user.dark_market_active:
                if not user.story_complete:
                    # open the totally not suspicious dark market
                    await dark_market(message)
                else:
                    await light_market(message)
                await achemb(message, "dark_market", "followup")

            if hidden_counter == 20:
                await achemb(interaction, "darkest_market", "send")

        for num, i in enumerate(["Cat Hunt", "Commands", "Random", "Silly", "Hard", "Hidden"]):
            if category == i:
                buttons_list.append(Button(label=i, custom_id=i, style=ButtonStyle.green, row=num // 3))
            else:
                buttons_list.append(Button(label=i, custom_id=i, style=ButtonStyle.blurple, row=num // 3))
            buttons_list[-1].callback = callback_hell

        for j in buttons_list:
            myview.add_item(j)
        return myview

    await message.response.send_message(
        embed=await gen_new("Cat Hunt"),
        ephemeral=True,
        view=insane_view_generator("Cat Hunt"),
    )

    if unlocked >= 15:
        await achemb(message, "achiever", "send")


@bot.tree.command(name="catch", description="Catch someone in 4k")
async def catch_tip(message: discord.Interaction):
    await message.response.send_message(
        f'Nope, that\'s the wrong way to do this.\nRight Click/Long Hold a message you want to catch > Select `Apps` in the popup > "{get_emoji("staring_cat")} catch"',
        ephemeral=True,
    )


async def catch(interaction: discord.Interaction, msg: discord.Message):
    user = interaction.user
    now = time.time()

    # Cooldown check first
    if user.id in catchcooldown and catchcooldown[user.id] + 6 > now:
        await interaction.response.send_message("your phone is overheating bro chill", ephemeral=True)
        return

    catchcooldown[user.id] = now  # immediately update cooldown

    perms = await fetch_perms(interaction)
    if not perms.attach_files:
        await interaction.response.send_message("i cant attach files here!", ephemeral=True)
        return

    # Defer response right away (so Discord doesn't timeout)
    await interaction.response.defer(thinking=True)

    # Run image conversion in a thread pool
    event_loop = asyncio.get_event_loop()
    result = await event_loop.run_in_executor(None, msg2img.msg2img, msg)

    await interaction.followup.send("caught in 4k", file=result)
    await achemb(interaction, "4k", "send")

    if msg.author.id == bot.user.id and "caught in 4k" in msg.content:
        await achemb(interaction, "8k", "send")

    try:
        is_cat = (await Channel.get_or_none(channel_id=interaction.channel.id)).cat
    except Exception:
        is_cat = False

    if int(is_cat) == int(msg.id):
        await achemb(interaction, "not_like_that", "send")



@bot.tree.command(description="View the leaderboards")
@discord.app_commands.rename(leaderboard_type="type")
@discord.app_commands.describe(
    leaderboard_type="The leaderboard type to view!",
    cat_type="The cat type to view (only for the Cats leaderboard)",
    locked="Whether to remove page switch buttons to prevent tampering",
)
@discord.app_commands.autocomplete(cat_type=lb_type_autocomplete)
async def leaderboards(
    message: discord.Interaction,
    leaderboard_type: Optional[Literal["Cats", "Value", "Fast", "Slow", "Battlepass", "Cookies", "Pig"]],
    cat_type: Optional[str],
    locked: Optional[bool],
):
    if not leaderboard_type:
        leaderboard_type = "Cats"
    if not locked:
        locked = False
    if cat_type and cat_type not in cattypes + ["All"]:
        await message.response.send_message("invalid cattype", ephemeral=True)
        return

    # this fat function handles a single page
    async def lb_handler(interaction, type, do_edit=None, specific_cat="All"):
        if specific_cat is None:
            specific_cat = "All"

        nonlocal message
        if do_edit is None:
            do_edit = True
        await interaction.response.defer()

        messager = None
        interactor = None

        # leaderboard top amount
        show_amount = 15

        string = ""
        if type == "Cats":
            unit = "cats"

            if specific_cat != "All":
                result = await Profile.collect_limit(
                    ["user_id", f"cat_{specific_cat}"], f'guild_id = $1 AND "cat_{specific_cat}" > 0 ORDER BY "cat_{specific_cat}" DESC', message.guild.id
                )
                final_value = f"cat_{specific_cat}"
            else:
                # dynamically generate sum expression, cast each value to bigint first to handle large totals
                cat_columns = [f'CAST("cat_{c}" AS BIGINT)' for c in cattypes]
                sum_expression = RawSQL("(" + " + ".join(cat_columns) + ") AS final_value")
                result = await Profile.collect_limit(["user_id", sum_expression], "guild_id = $1 ORDER BY final_value DESC", message.guild.id)
                final_value = "final_value"

                # find rarest
                rarest = None
                for i in cattypes[::-1]:
                    non_zero_count = await Profile.collect_limit("user_id", f'guild_id = $1 AND "cat_{i}" > 0', message.guild.id)
                    if len(non_zero_count) != 0:
                        rarest = i
                        rarest_holder = non_zero_count
                        break

                if rarest and specific_cat != rarest:
                    catmoji = get_emoji(rarest.lower() + "cat")
                    rarest_holder = [f"<@{i.user_id}>" for i in rarest_holder]
                    joined = ", ".join(rarest_holder)
                    if len(rarest_holder) > 10:
                        joined = f"{len(rarest_holder)} people"
                    string = f"Rarest cat: {catmoji} ({joined}'s)\n\n"
        elif type == "Value":
            unit = "value"
            sums = []
            for cat_type in cattypes:
                if not cat_type:
                    continue
                weight = sum(type_dict.values()) / type_dict[cat_type]
                sums.append(f'({weight}) * "cat_{cat_type}"')
            total_sum_expr = RawSQL("(" + " + ".join(sums) + ") AS final_value")
            result = await Profile.collect_limit(["user_id", total_sum_expr], "guild_id = $1 ORDER BY final_value DESC", message.guild.id)
            final_value = "final_value"
        elif type == "Fast":
            unit = "sec"
            result = await Profile.collect_limit(["user_id", "time"], "guild_id = $1 AND time < 99999999999999 ORDER BY time ASC", message.guild.id)
            final_value = "time"
        elif type == "Slow":
            unit = "h"
            result = await Profile.collect_limit(["user_id", "timeslow"], "guild_id = $1 AND timeslow > 0 ORDER BY timeslow DESC", message.guild.id)
            final_value = "timeslow"
        elif type == "Battlepass":
            start_date = datetime.datetime(2024, 12, 1)
            current_date = datetime.datetime.utcnow()
            full_months_passed = (current_date.year - start_date.year) * 12 + (current_date.month - start_date.month)
            bp_season = battle["seasons"][str(full_months_passed)]
            if current_date.day < start_date.day:
                full_months_passed -= 1
            result = await Profile.collect_limit(
                ["user_id", "battlepass", "progress"],
                "guild_id = $1 AND season = $2 AND (battlepass > 0 OR progress > 0) ORDER BY battlepass DESC, progress DESC",
                message.guild.id,
                full_months_passed,
            )
            final_value = "battlepass"
        elif type == "Cookies":
            unit = "cookies"
            result = await Profile.collect_limit(["user_id", "cookies"], "guild_id = $1 AND cookies > 0 ORDER BY cookies DESC", message.guild.id)
            string = "Cookie leaderboard updates every 5 min\n\n"
            final_value = "cookies"
        elif type == "Pig":
            unit = "score"
            result = await Profile.collect_limit(
                ["user_id", "best_pig_score"], "guild_id = $1 AND best_pig_score > 0 ORDER BY best_pig_score DESC", message.guild.id
            )
            final_value = "best_pig_score"
        else:
            # qhar
            return

        # find the placement of the person who ran the command and optionally the person who pressed the button
        interactor_placement = 0
        messager_placement = 0
        for index, position in enumerate(result):
            if position["user_id"] == interaction.user.id:
                interactor_placement = index + 1
                interactor = position[final_value]
                if type == "Battlepass":
                    if position[final_value] >= len(bp_season):
                        lv_xp_req = 1500
                    else:
                        lv_xp_req = bp_season[int(position[final_value]) - 1]["xp"]
                    interactor_perc = math.floor((100 / lv_xp_req) * position["progress"])
            if interaction.user != message.user and position["user_id"] == message.user.id:
                messager_placement = index + 1
                messager = position[final_value]
                if type == "Battlepass":
                    if position[final_value] >= len(bp_season):
                        lv_xp_req = 1500
                    else:
                        lv_xp_req = bp_season[int(position[final_value]) - 1]["xp"]
                    messager_perc = math.floor((100 / lv_xp_req) * position["progress"])

        if type == "Slow":
            if interactor:
                interactor = round(interactor / 3600, 2)
            if messager:
                messager = round(messager / 3600, 2)

        if type == "Fast":
            if interactor:
                interactor = round(interactor, 3)
            if messager:
                messager = round(messager, 3)

        # dont show placements if they arent defined
        if interactor and type != "Fast":
            if interactor <= 0:
                interactor_placement = 0
            interactor = round(interactor)
        elif interactor and type == "Fast" and interactor >= 99999999999999:
            interactor_placement = 0

        if messager and type != "Fast":
            if messager <= 0:
                messager_placement = 0
            messager = round(messager)
        elif messager and type == "Fast" and messager >= 99999999999999:
            messager_placement = 0

        emoji = ""
        if type == "Cats" and specific_cat != "All":
            emoji = get_emoji(specific_cat.lower() + "cat")

        # the little place counter
        current = 1
        leader = False
        for i in result[:show_amount]:
            num = i[final_value]

            if type == "Battlepass":
                if i[final_value] >= len(bp_season):
                    lv_xp_req = 1500
                else:
                    lv_xp_req = bp_season[int(i[final_value]) - 1]["xp"]
                prog_perc = math.floor((100 / lv_xp_req) * i["progress"])
                string += f"{current}. Level **{num}** *({prog_perc}%)*: <@{i['user_id']}>\n"
            else:
                if type == "Slow":
                    if num <= 0:
                        break
                    num = round(num / 3600, 2)
                elif type == "Value":
                    if num <= 0:
                        break
                    num = round(num)
                elif type == "Fast":
                    if num >= 99999999999999:
                        break
                    num = round(num, 3)
                elif type in ["Cookies", "Cats", "Pig"] and num <= 0:
                    break
                string = string + f"{current}. {emoji} **{num:,}** {unit}: <@{i['user_id']}>\n"

            if message.user.id == i["user_id"] and current <= 5:
                leader = True
            current += 1

        # add the messager and interactor
        if messager_placement > show_amount or interactor_placement > show_amount:
            string = string + "...\n"

            # setting up names
            include_interactor = interactor_placement > show_amount and str(interaction.user.id) not in string
            include_messager = messager_placement > show_amount and str(message.user.id) not in string
            interactor_line = ""
            messager_line = ""
            if include_interactor:
                if type == "Battlepass":
                    interactor_line = f"{interactor_placement}\\. Level **{interactor}** *({interactor_perc}%)*: {interaction.user.mention}\n"
                else:
                    interactor_line = f"{interactor_placement}\\. {emoji} **{interactor:,}** {unit}: {interaction.user.mention}\n"
            if include_messager:
                if type == "Battlepass":
                    messager_line = f"{messager_placement}\\. Level **{messager}** *({messager_perc}%)*: {message.user.mention}\n"
                else:
                    messager_line = f"{messager_placement}\\. {emoji} **{messager:,}** {unit}: {message.user.mention}\n"

            # sort them correctly!
            if messager_placement > interactor_placement:
                # interactor should go first
                string += interactor_line
                string += messager_line
            else:
                # messager should go first
                string += messager_line
                string += interactor_line

        title = type + " Leaderboard"
        if type == "Cats":
            title = f"{specific_cat} {title}"
        title = "🏅 " + title

        # If there are many results, paginate the textual leaderboard instead of one giant embed
        if len(result) > show_amount or len(string) > 3500:
            # build full lines for all results
            lines = []
            current = 1
            emoji_out = emoji
            for i in result:
                num = i[final_value]
                if type == "Battlepass":
                    if i[final_value] >= len(bp_season):
                        lv_xp_req = 1500
                    else:
                        lv_xp_req = bp_season[int(i[final_value]) - 1]["xp"]
                    prog_perc = math.floor((100 / lv_xp_req) * i["progress"])
                    lines.append(f"{current}. Level **{num}** *({prog_perc}%)*: <@{i['user_id']}>")
                else:
                    if type == "Slow":
                        if num <= 0:
                            continue
                        num = round(num / 3600, 2)
                    elif type == "Value":
                        if num <= 0:
                            continue
                        num = round(num)
                    elif type == "Fast":
                        if num >= 99999999999999:
                            continue
                        num = round(num, 3)
                    elif type in ["Cookies", "Cats", "Pig"] and num <= 0:
                        continue
                    lines.append(f"{current}. {emoji_out} **{num:,}** {unit}: <@{i['user_id']}>")
                current += 1

            # add messager/interactor lines if they were beyond the shown amount
            if messager_placement > show_amount or interactor_placement > show_amount:
                if messager_placement > interactor_placement:
                    if interactor_placement > show_amount:
                        lines.append(interactor_line)
                    if messager_placement > show_amount:
                        lines.append(messager_line)
                else:
                    if messager_placement > show_amount:
                        lines.append(messager_line)
                    if interactor_placement > show_amount:
                        lines.append(interactor_line)

            pages = _paginate_lines(lines, per_page=15)
            # send a paginated embed
            await send_paginated_embed(interaction, title, pages, color=Colors.brown, footer=rain_shill, ephemeral=False, locked=locked)
            return

        embedVar = discord.Embed(title=title, description=string.rstrip(), color=Colors.brown).set_footer(text=rain_shill)

        global_user = await User.get_or_create(user_id=message.user.id)

        if len(news_list) > len(global_user.news_state.strip()) or "0" in global_user.news_state.strip()[-4:]:
            embedVar.set_author(name=f"{message.user} has unread news! /news")

        # handle funny buttons
        myview = View(timeout=VIEW_TIMEOUT)

        if type == "Cats":
            dd_opts = [Option(label="All", emoji=get_emoji("staring_cat"), value="All")]

            for i in await cats_in_server(message.guild.id):
                dd_opts.append(Option(label=i, emoji=get_emoji(i.lower() + "cat"), value=i))

            dropdown = Select(
                "cat_type_dd",
                placeholder="Select a cat type",
                opts=dd_opts,
                selected=specific_cat,
                on_select=lambda interaction, option: lb_handler(interaction, type, True, option),
                disabled=locked,
            )

        emojied_options = {"Cats": "🐈", "Value": "🧮", "Fast": "⏱️", "Slow": "💤", "Battlepass": "⬆️", "Cookies": "🍪", "Pig": "🎲"}
        options = [Option(label=k, emoji=v) for k, v in emojied_options.items()]
        lb_select = Select(
            "lb_type",
            placeholder=type,
            opts=options,
            on_select=lambda interaction, type: lb_handler(interaction, type, True),
        )

        if not locked:
            myview.add_item(lb_select)
            if type == "Cats":
                myview.add_item(dropdown)

        # just send if first time, otherwise edit existing
        try:
            if not do_edit:
                raise Exception
            await interaction.edit_original_response(embed=embedVar, view=myview)
        except Exception:
            await interaction.followup.send(embed=embedVar, view=myview)

        if leader:
            await achemb(message, "leader", "send")

    await lb_handler(message, leaderboard_type, False, cat_type)


@bot.tree.command(description="(ADMIN) Give cats to people")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.rename(person_id="user")
@discord.app_commands.describe(person_id="who", amount="how many (negatives to remove)", cat_type="what")
@discord.app_commands.autocomplete(cat_type=cat_type_autocomplete)
async def givecat(message: discord.Interaction, person_id: discord.User, cat_type: str, amount: Optional[int]):
    if amount is None:
        amount = 1
    if cat_type not in cattypes:
        await message.response.send_message("bro what", ephemeral=True)
        return

    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id.id)
    user[f"cat_{cat_type}"] += amount
    await user.save()
    await message.response.send_message(f"gave {person_id.mention} {amount:,} {cat_type} cats", allowed_mentions=discord.AllowedMentions(users=True))


@bot.tree.command(name="setup", description="(ADMIN) Setup cat in current channel")
@discord.app_commands.default_permissions(manage_guild=True)
async def setup_channel(message: discord.Interaction):
    if await Channel.get_or_none(channel_id=message.channel.id):
        await message.response.send_message(
            "bruh you already setup cat here are you dumb\n\nthere might already be a cat sitting in chat. type `cat` to catch it."
        )
        return

    try:
        channel_permissions = await fetch_perms(message)
        needed_perms = {
            "View Channel": channel_permissions.view_channel,
            "Send Messages": channel_permissions.send_messages,
            "Attach Files": channel_permissions.attach_files,
        }
        if isinstance(message.channel, discord.Thread):
            needed_perms["Send Messages in Threads"] = channel_permissions.send_messages_in_threads

        for name, value in needed_perms.copy().items():
            if value:
                needed_perms.pop(name)

        missing_perms = list(needed_perms.keys())
        if len(missing_perms) != 0:
            needed_perms = "\n- ".join(missing_perms)
            await message.response.send_message(
                f":x: Missing Permissions! Please give me the following:\n- {needed_perms}\nHint: try setting channel permissions if server ones don't work."
            )
            return

        await Channel.create(channel_id=message.channel.id)
    except Exception:
        await message.response.send_message("this channel gives me bad vibes.")
        return

    await spawn_cat(str(message.channel.id))
    await message.response.send_message(f"ok, now i will also send cats in <#{message.channel.id}>")


@bot.tree.command(description="(ADMIN) Undo the setup")
@discord.app_commands.default_permissions(manage_guild=True)
async def forget(message: discord.Interaction):
    if channel := await Channel.get_or_none(channel_id=message.channel.id):
        await channel.delete()
        await message.response.send_message(f"ok, now i wont send cats in <#{message.channel.id}>")
    else:
        await message.response.send_message("your an idiot there is literally no cat setupped in this channel you stupid")


@bot.tree.command(description="LMAO TROLLED SO HARD :JOY:")
async def fake(message: discord.Interaction):
    if message.user.id in fakecooldown and fakecooldown[message.user.id] + 60 > time.time():
        await message.response.send_message("your phone is overheating bro chill", ephemeral=True)
        return
    file = discord.File("images/australian cat.png", filename="australian cat.png")
    icon = get_emoji("egirlcat")
    perms = await fetch_perms(message)
    if not isinstance(
        message.channel,
        Union[
            discord.TextChannel,
            discord.VoiceChannel,
            discord.StageChannel,
            discord.Thread,
        ],
    ):
        return
    fakecooldown[message.user.id] = time.time()
    try:
        if not perms.send_messages or not perms.attach_files:
            raise Exception
        await message.response.send_message(
            str(icon) + ' eGirl cat hasn\'t appeared! Type "cat" to catch ratio!',
            file=file,
        )
    except Exception:
        await message.response.send_message("i dont have perms lmao here is the ach anyways", ephemeral=True)
        pass
    await achemb(message, "trolled", "followup")


@bot.tree.command(description="(ADMIN) Force cats to appear")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.rename(cat_type="type")
@discord.app_commands.describe(cat_type="select a cat type ok")
@discord.app_commands.autocomplete(cat_type=cat_type_autocomplete)
async def forcespawn(message: discord.Interaction, cat_type: Optional[str]):
    if cat_type and cat_type not in cattypes:
        await message.response.send_message("bro what", ephemeral=True)
        return

    ch = await Channel.get_or_none(channel_id=message.channel.id)
    if ch is None:
        await message.response.send_message("this channel is not /setup-ed", ephemeral=True)
        return
    if ch.cat:
        await message.response.send_message("there is already a cat", ephemeral=True)
        return
    ch.yet_to_spawn = 0
    await ch.save()
    await spawn_cat(str(message.channel.id), cat_type, True)
    await message.response.send_message("done!\n**Note:** you can use `/givecat` to give yourself cats, there is no need to spam this")


@bot.tree.command(description="(ADMIN) Give achievements to people")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.rename(person_id="user", ach_id="name")
@discord.app_commands.describe(person_id="who", ach_id="name or id of the achievement")
@discord.app_commands.autocomplete(ach_id=ach_autocomplete)
async def giveachievement(message: discord.Interaction, person_id: discord.User, ach_id: str):
    # check if ach is real
    try:
        valid = ach_id in ach_names
    except KeyError:
        valid = False

    if not valid and ach_id.lower() in ach_titles.keys():
        ach_id = ach_titles[ach_id.lower()]
        valid = True

    person = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id.id)

    if valid and ach_id == "thanksforplaying":
        await message.response.send_message("HAHAHHAHAH\nno", ephemeral=True)
        return

    if valid:
        # if it is, do the thing
        reverse = person[ach_id]
        person[ach_id] = not reverse
        await person.save()
        color, title, icon = (
            Colors.green,
            "Achievement forced!",
            "https://wsrv.nl/?url=raw.githubusercontent.com/staring-cat/emojis/main/ach.png",
        )
        if reverse:
            color, title, icon = (
                Colors.red,
                "Achievement removed!",
                "https://wsrv.nl/?url=raw.githubusercontent.com/staring-cat/emojis/main/no_ach.png",
            )
        ach_data = ach_list[ach_id]
        embed = (
            discord.Embed(
                title=ach_data["title"],
                description=ach_data["description"],
                color=color,
            )
            .set_author(name=title, icon_url=icon)
            .set_footer(text=f"for {person_id.name}")
        )
        await message.response.send_message(person_id.mention, embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
    else:
        await message.response.send_message("i cant find that achievement! try harder next time.", ephemeral=True)


@bot.tree.command(description="(ADMIN) Reset people")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.rename(person_id="user")
@discord.app_commands.describe(person_id="who")
async def reset(message: discord.Interaction, person_id: discord.User):
    async def confirmed(interaction):
        if interaction.user.id == message.user.id:
            await interaction.response.defer()
            try:
                og = await interaction.original_response()
                profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id.id)
                profile.guild_id = og.id
                await profile.save()
                async for p in Prism.filter("guild_id = $1 AND user_id = $2", message.guild.id, person_id.id):
                    p.guild_id = og.id
                    await p.save()
                await interaction.edit_original_response(
                    content=f"Done! rip {person_id.mention}. f's in chat.\njoin our discord to rollback: <https://discord.gg/staring>", view=None
                )
            except Exception:
                await interaction.edit_original_response(
                    content="ummm? this person isnt even registered in KITTAYYYYYYY wtf are you wiping?????",
                    view=None,
                )
        else:
            await do_funny(interaction)

    view = View(timeout=VIEW_TIMEOUT)
    button = Button(style=ButtonStyle.red, label="Confirm")
    button.callback = confirmed
    view.add_item(button)
    await message.response.send_message(f"Are you sure you want to reset {person_id.mention}?", view=view, allowed_mentions=discord.AllowedMentions(users=True))


@bot.tree.command(description="(HIGH ADMIN) [VERY DANGEROUS] Reset all KITTAYYYYYYY data of this server")
@discord.app_commands.default_permissions(administrator=True)
async def nuke(message: discord.Interaction):
    warning_text = "⚠️ This will completely reset **all** KITTAYYYYYYY progress of **everyone** in this server. Spawn channels and their settings *will not be affected*.\nPress the button 5 times to continue."
    counter = 5

    async def gen(counter):
        lines = [
            "",
            "I'm absolutely sure! (1)",
            "I understand! (2)",
            "You can't undo this! (3)",
            "This is dangerous! (4)",
            "Reset everything! (5)",
        ]
        view = View(timeout=VIEW_TIMEOUT)
        button = Button(label=lines[max(1, counter)], style=ButtonStyle.red)
        button.callback = count
        view.add_item(button)
        return view

    async def count(interaction: discord.Interaction):
        nonlocal message, counter
        if interaction.user.id == message.user.id:
            await interaction.response.defer()
            counter -= 1
            if counter == 0:
                # ~~Scary!~~ Not anymore!
                # how this works is we basically change the server id to the message id and then add user with id of 0 to mark it as deleted
                # this can be rolled back decently easily by asking user for the id of nuking message

                changed_profiles = []
                changed_prisms = []

                async for i in Profile.filter("guild_id = $1", message.guild.id):
                    i.guild_id = interaction.message.id
                    changed_profiles.append(i)

                async for i in Prism.filter("guild_id = $1", message.guild.id):
                    i.guild_id = interaction.message.id
                    changed_prisms.append(i)

                if changed_profiles:
                    await Profile.bulk_update(changed_profiles, "guild_id")
                if changed_prisms:
                    await Prism.bulk_update(changed_prisms, "guild_id")
                await Profile.create(guild_id=interaction.message.id, user_id=0)

                try:
                    await interaction.edit_original_response(
                        content="Done. If you want to roll this back, please contact us in our discord: <https://discord.gg/staring>.",
                        view=None,
                    )
                except Exception:
                    await interaction.followup.send("Done. If you want to roll this back, please contact us in our discord: <https://discord.gg/staring>.")
            else:
                view = await gen(counter)
                try:
                    await interaction.edit_original_response(content=warning_text, view=view)
                except Exception:
                    pass
        else:
            await do_funny(interaction)

    view = await gen(counter)
    await message.response.send_message(warning_text, view=view)


async def recieve_vote(request):
    if request.headers.get("authorization", "") != config.WEBHOOK_VERIFY:
        return web.Response(text="bad", status=403)
    request_json = await request.json()

    user = await User.get_or_create(user_id=int(request_json["user"]))
    if user.vote_time_topgg + 43100 > time.time():
        # top.gg is NOT realiable with their webhooks, but we politely pretend they are
        return web.Response(text="you fucking dumb idiot", status=200)

    if user.vote_streak < 10:
        extend_time = 24
    elif user.vote_streak < 20:
        extend_time = 36
    elif user.vote_streak < 50:
        extend_time = 48
    elif user.vote_streak < 100:
        extend_time = 60
    else:
        extend_time = 72

    user.reminder_vote = 1
    user.total_votes += 1
    if user.vote_time_topgg + extend_time * 3600 <= time.time():
        # streak end
        if user.max_vote_streak < user.vote_streak:
            user.max_vote_streak = user.vote_streak
        user.vote_streak = 1
    else:
        user.vote_streak += 1
    user.vote_time_topgg = time.time()

    try:
        channeley = await bot.fetch_user(int(request_json["user"]))

        if user.vote_streak == 1:
            streak_progress = "🟦⬛⬛⬛⬛⬛⬛⬛⬛⬛\n⬆️"
        else:
            streak_progress = ""
            if user.vote_streak > 0:
                streak_progress += get_streak_reward(user.vote_streak - 1)["done_emoji"]
            streak_progress += get_streak_reward(user.vote_streak)["done_emoji"]

            for i in range(user.vote_streak + 1, user.vote_streak + 9):
                streak_progress += get_streak_reward(i)["emoji"]

            streak_progress += f"\n{get_emoji('empty')}⬆️"

        special_reward = math.ceil(user.vote_streak / 25) * 25
        if special_reward not in range(user.vote_streak, user.vote_streak + 9):
            streak_progress += f"\nNext Special Reward: {get_streak_reward(special_reward)['emoji']} at {special_reward} streak"

        await channeley.send(
            "\n".join(
                [
                    "Thanks for voting! To claim your rewards, run `/battlepass` in every server you want.",
                    f"You can vote again <t:{int(time.time()) + 43200}:R>.",
                    "",
                    f":fire: **Streak:** {user.vote_streak:,} (expires <t:{int(time.time()) + extend_time * 3600}:R>)",
                    f"{streak_progress}",
                ]
            )
        )
    except Exception:
        pass

    await user.save()

    # Trigger reward handling across guild profiles for this user
    try:
        asyncio.create_task(reward_vote(int(request_json["user"])))
    except Exception:
        pass

    # Log the vote to the central cat log channel (best-effort)
    try:
        asyncio.create_task(log_vote_to_channel(int(request_json["user"]), source="aiohttp"))
    except Exception:
        pass

    return web.Response(text="ok", status=200)


async def check_supporter(request):
    if request.headers.get("authorization", "") != config.WEBHOOK_VERIFY:
        return web.Response(text="bad", status=403)
    request_json = await request.json()

    user = await User.get_or_create(user_id=int(request_json["user"]))
    return web.Response(text="1" if user.premium else "0", status=200)


# KITTAYYYYYYY uses glitchtip (sentry alternative) for errors, here u can instead implement some other logic like dming the owner
async def on_error(*args, **kwargs):
    # Previously this raised, which could crash the bot process on uncaught errors.
    # Instead, log the error and continue so the process doesn't exit silently.
    try:
        logging.exception("on_error called with args=%s kwargs=%s", args, kwargs)
    except Exception:
        pass
    return


async def setup(bot2):
    global bot, RAIN_ID, vote_server

    for command in bot.tree.walk_commands():
        # copy all the commands
        command.guild_only = True
        bot2.tree.add_command(command)

    context_menu_command = discord.app_commands.ContextMenu(name="catch", callback=catch)
    context_menu_command.guild_only = True
    bot2.tree.add_command(context_menu_command)

    # copy all the events
    bot2.on_ready = on_ready
    bot2.on_guild_join = on_guild_join
    bot2.on_message = on_message
    bot2.on_connect = on_connect
    bot2.on_error = on_error

    if config.WEBHOOK_VERIFY:
        app = web.Application()
        app.add_routes([web.post("/", recieve_vote), web.get("/supporter", check_supporter)])
        vote_server = web.AppRunner(app)
        await vote_server.setup()
        site = web.TCPSite(vote_server, "0.0.0.0", 8069)
        await site.start()

    # finally replace the fake bot with the real one
    bot = bot2

    config.SOFT_RESTART_TIME = time.time()

    app_commands = await bot.tree.sync()
    for i in app_commands:
        if i.name == "rain":
            RAIN_ID = i.id

    if bot.is_ready() and not on_ready_debounce:
        await on_ready()


async def teardown(bot):
    cookie_updates = []
    for cookie_id, cookies in temp_cookie_storage.items():
        p = await Profile.get_or_create(guild_id=cookie_id[0], user_id=cookie_id[1])
        p.cookies = cookies
        cookie_updates.append(p)

    if cookie_updates:
        await Profile.bulk_update(cookie_updates, "cookies")

    if config.WEBHOOK_VERIFY:
        await vote_server.cleanup()


# Reusable UI components
class Option:
    def __init__(self, label, emoji, value=None):
        self.label = label
        self.emoji = emoji
        self.value = value if value is not None else label


class Select(discord.ui.Select):
    on_select = None

    def __init__(
        self,
        id: str,
        placeholder: str,
        opts: list[Option],
        selected: str = None,
        on_select: callable = None,
        disabled: bool = False,
    ):
        options = []
        if on_select is not None:
            self.on_select = on_select

        for opt in opts:
            options.append(discord.SelectOption(label=opt.label, value=opt.value, emoji=opt.emoji, default=opt.value == selected))

        super().__init__(
            placeholder=placeholder,
            options=options,
            custom_id=id,
            max_values=1,
            min_values=1,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction):
        if self.on_select is not None and callable(self.on_select):
            await self.on_select(interaction, self.values[0])
# --- BEGIN: Cat Breeding feature (updated: average-based chances instead of "always better") ---
def _breed_candidates(parent_a: str, parent_b: str) -> list[str]:
    """
    Return the candidate pool for offspring.
    Changed: include all cat types as possible offspring so chances are centered
    around the averaged rarity of parents (instead of requiring strictly rarer).
    """
    try:
        # validate parents exist
        _ = cattypes.index(parent_a)
        _ = cattypes.index(parent_b)
    except ValueError:
        return []
    # allow every cat type to be possible (weights will bias toward the average)
    return cattypes[:]


def _breed_raw_weights(parent_a: str, parent_b: str, candidates: list[str]) -> list[float]:
    """
    Produce raw weights for the candidate pool using averaged parent rarity.

    New approach:
    - Operate on the log of type_dict values (log-scale) so distance is scale-invariant.
      This prevents very-common types (large numeric values) from dominating purely
      because their numeric value is larger.
    - Compute a Gaussian (exp(-dist^2 / (2*sigma^2))) on the log-scale around the
      parents' averaged log-value to prefer candidates near the parents' average.
    - Multiply by a small rarity factor (based on 1/value) so genuinely rarer cats
      get a boost when appropriate (alpha controls strength).
    - Add a tiny eps floor to keep candidates possible.
    """
    if not candidates:
        return []

    # parent log-average
    log_parent_a = math.log(type_dict[parent_a])
    log_parent_b = math.log(type_dict[parent_b])
    avg_log = (log_parent_a + log_parent_b) / 2.0

    # precompute logs and basic ranges
    values = [type_dict[t] for t in candidates]
    log_values = [math.log(v) for v in values]
    max_log = max(log_values)
    min_log = min(log_values)
    log_range = max_log - min_log if max_log > min_log else 1.0

    # sigma tuned to cover the spread; prevents extremely narrow distributions
    sigma = max(log_range / 4.0, 0.25)

    # rarity factor: transform value -> 1/value, normalize to [0..1]
    inv_values = [1.0 / v for v in values]
    max_inv = max(inv_values)
    # alpha controls how strongly we bias toward rarer cats (0 = no bias)
    alpha = 0.6

    eps = 1e-9
    raw = []
    for lv, inv, t in zip(log_values, inv_values, candidates):
        # closeness on log-scale (Gaussian)
        diff = lv - avg_log
        closeness = math.exp(-(diff * diff) / (2.0 * sigma * sigma))

        # normalized rarity in [0..1]
        rarity_norm = inv / max_inv if max_inv > 0 else 0.0

        # combine closeness with a mild rarity bias
        weight = closeness * (rarity_norm ** alpha)

        raw.append(weight + eps)

    return raw


def breed_chances(parent_a: str, parent_b: str) -> dict[str, float]:
    """
    Return a dict mapping candidate cat types -> percentage chance (0..100).
    Candidates are the full set of cattypes; probabilities are derived by how
    close each cat's spawn value is to the averaged parent spawn value.
    """
    candidates = _breed_candidates(parent_a, parent_b)
    if not candidates:
        return {}

    raw = _breed_raw_weights(parent_a, parent_b, candidates)
    total = sum(raw)
    if total <= 0:
        # fallback: equal probability
        prob = 1 / len(candidates)
        return {c: prob * 100 for c in candidates}

    return {candidates[i]: (raw[i] / total) * 100.0 for i in range(len(candidates))}


def _pick_breed_result(parent_a: str, parent_b: str) -> Optional[str]:
    """
    Return a chosen cat type (string) or None if parents invalid.
    Uses averaged-parent weighting (see _breed_raw_weights).
    """
    candidates = _breed_candidates(parent_a, parent_b)
    if not candidates:
        return None

    raw = _breed_raw_weights(parent_a, parent_b, candidates)
    choice = random.choices(candidates, weights=raw, k=1)[0]
    return choice


@bot.tree.command(description="Breed two cats to get an offspring (chances are based on parents' averaged rarity)")
@discord.app_commands.rename(first="first_cat", second="second_cat")
@discord.app_commands.autocomplete(first=cat_command_autocomplete, second=cat_command_autocomplete)
async def breed(message: discord.Interaction, first: str, second: str):
        """
        Command: /breed <first> <second>
        - Consumes one of each specified cat type from the caller's server inventory.
        - Produces an offspring whose probability distribution is centered on the
          average spawn/rarity value of both parents (not required to be strictly rarer).
        """
        # basic validation
        if first not in cattypes or second not in cattypes:
            await message.response.send_message("invalid cat type", ephemeral=True)
            return

        profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)

        # check ownership (if same type, need 2 copies)
        needed_first = 1
        needed_second = 1
        if first == second:
            needed_first = 2

        if profile[f"cat_{first}"] < needed_first or profile[f"cat_{second}"] < needed_second:
            await message.response.send_message("you don't have enough of those cats to breed!", ephemeral=True)
            return

        # prepare chance table (now averaged-based over whole cat list)
        chances = breed_chances(first, second)
        if not chances:
            await message.response.send_message("Breeding failed: invalid parents or no candidates.", ephemeral=True)
            return

        # perform the breeding: consume parents first (atomic-ish)
        profile[f"cat_{first}"] -= needed_first
        if second != first:
            profile[f"cat_{second}"] -= needed_second

        # pick offspring
        offspring = _pick_breed_result(first, second)
        if not offspring:
            # restore and abort (shouldn't happen)
            profile[f"cat_{first}"] += needed_first
            if second != first:
                profile[f"cat_{second}"] += needed_second
            await profile.save()
            await message.response.send_message("Breeding failed unexpectedly, nothing changed.", ephemeral=True)
            return

        # award offspring
        profile[f"cat_{offspring}"] += 1
        await profile.save()

        # award "Freak 😼" for performing a successful breed
        try:
            await achemb(message, "freak", "send")
        except Exception:
            pass

        # genetic special-case checks
        try:
            chances_map = breed_chances(first, second)
            chance_percent = chances_map.get(offspring, 0.0)
            total_val = sum(type_dict.values())
            # higher numeric "value" = more rare in UI (we keep same metric used elsewhere)
            parent_vals = [total_val / type_dict[first], total_val / type_dict[second]]
            offspring_val = total_val / type_dict[offspring]

            # Genetically gifted: offspring <1% chance AND higher value than both parents
            if chance_percent < 1.0 and offspring_val > max(parent_vals):
                await achemb(message, "genetically_gifted", "send")

            # Tylenol: offspring is worse (lower value) than both parents
            if offspring_val < min(parent_vals):
                await achemb(message, "tylenol", "send")
        except Exception:
            pass

        # Full stack / huzzful check for the awarded offspring
        try:
            await _check_full_stack_and_huzzful(profile, message, offspring)
        except Exception:
            pass

        # display chance table sorted by descending chance
        chance_lines = []
        for cat_type, pct in sorted(chances.items(), key=lambda kv: kv[1], reverse=True):
            chance_lines.append(f"{get_emoji(cat_type.lower() + 'cat')} {cat_type}: {pct:.2f}%")

        reply_text = (
            f"{message.user.mention} bred {get_emoji(first.lower() + 'cat')} {first} + {get_emoji(second.lower() + 'cat')} {second} -> {get_emoji(offspring.lower() + 'cat')} {offspring}!\n\n"
            "Offspring chances (centered on averaged parent rarity):\n" + "\n".join(chance_lines)
        )

        await message.response.send_message(reply_text)
# --- END: Cat Breeding feature ---

async def reward_vote(user_id: int):
    """Apply vote rewards to all guild profiles for the given user_id.

    This completes the 'vote' quest for any Profile in which the vote quest is available
    (i.e. profile.vote_cooldown == 0). It mirrors the logic from progress(..., quest='vote')
    but runs without a discord interaction.
    """
    try:
        global_user = await User.get_or_create(user_id=user_id)
    except Exception:
        return

    # iterate servers the bot is in and apply to each Profile for this user
    for guild in list(bot.guilds):
        try:
            profile = await Profile.get_or_create(guild_id=guild.id, user_id=user_id)
            # only apply if a vote quest is currently available
            if getattr(profile, "vote_cooldown", 0) != 0:
                continue

            # ensure there's a vote_reward; if not, generate a sensible one
            try:
                qdata = battle.get("quests", {}).get("vote", {}).get("vote", {})
                if not getattr(profile, "vote_reward", 0):
                    profile.vote_reward = random.randint(qdata.get("xp_min", 250) // 10, qdata.get("xp_max", 350) // 10) * 10
            except Exception:
                if not getattr(profile, "vote_reward", 0):
                    profile.vote_reward = 300

            # set cooldown to user's recorded vote time
            try:
                profile.vote_cooldown = int(global_user.vote_time_topgg or int(time.time()))
            except Exception:
                profile.vote_cooldown = int(time.time())

            # double on Fri/Sat/Sun per progress()
            try:
                voted_at = datetime.datetime.utcfromtimestamp(int(global_user.vote_time_topgg or time.time()))
                if voted_at.weekday() >= 4:
                    profile.vote_reward = int(profile.vote_reward) * 2
            except Exception:
                pass

            # give streak pack if applicable
            try:
                streak_data = get_streak_reward(global_user.vote_streak)
                if streak_data.get("reward"):
                    profile[f"pack_{streak_data['reward']}"] += 1
            except Exception:
                pass

            # compute xp and apply to battlepass progression (mirror of progress())
            try:
                current_xp = (profile.progress or 0) + int(profile.vote_reward or 0)
            except Exception:
                current_xp = int(getattr(profile, "vote_reward", 0) or 0)

            profile.quests_completed = (profile.quests_completed or 0) + 1

            # determine level data loop
            try:
                if profile.battlepass >= len(battle.get("seasons", {}).get(str(profile.season), [])):
                    level_data = {"xp": 1500, "reward": "Stone", "amount": 1}
                else:
                    level_data = battle["seasons"][str(profile.season)][profile.battlepass]
            except Exception:
                level_data = {"xp": 1500, "reward": "Stone", "amount": 1}

            # apply level ups
            try:
                if current_xp >= level_data["xp"]:
                    xp_progress = current_xp
                    active_level_data = level_data
                    while xp_progress >= active_level_data["xp"]:
                        profile.battlepass += 1
                        xp_progress -= active_level_data["xp"]
                        profile.progress = xp_progress
                        # award rewards
                        try:
                            if active_level_data["reward"] == "Rain":
                                profile.rain_minutes = (profile.rain_minutes or 0) + active_level_data["amount"]
                            elif active_level_data["reward"] in [p["name"] for p in pack_data]:
                                profile[f"pack_{active_level_data['reward'].lower()}"] += active_level_data["amount"]
                            elif active_level_data["reward"] in cattypes:
                                profile[f"cat_{active_level_data['reward']}"] += active_level_data["amount"]
                        except Exception:
                            pass
                        try:
                            await profile.save()
                        except Exception:
                            pass
                        # advance to next level_data
                        if profile.battlepass >= len(battle.get("seasons", {}).get(str(profile.season), [])):
                            active_level_data = {"xp": 1500, "reward": "Stone", "amount": 1}
                        else:
                            active_level_data = battle["seasons"][str(profile.season)][profile.battlepass]
                else:
                    profile.progress = current_xp
                try:
                    await profile.save()
                except Exception:
                    pass
            except Exception:
                try:
                    profile.progress = current_xp
                    await profile.save()
                except Exception:
                    pass

        except Exception:
            # per-guild failure shouldn't stop others
            continue


async def log_vote_to_channel(user_id: int, source: str = "unknown"):
    """Send a short log message to the configured cat log channel (uses RAIN_CHANNEL_ID).

    This is intentionally defensive: it won't raise if the channel is missing or the bot
    lacks permissions.
    """
    try:
        chan_id = int(getattr(config, "RAIN_CHANNEL_ID", 0) or 0)
        if not chan_id:
            return
        ch = None
        try:
            ch = bot.get_channel(chan_id)
        except Exception:
            ch = None
        if ch is None:
            try:
                ch = await bot.fetch_channel(chan_id)
            except Exception:
                ch = None
        if ch is None:
            return

        text = f"Vote received: <@{user_id}> (ID: {user_id}) — source: {source}"
        try:
            await ch.send(text)
        except Exception:
            # fallback: attempt to send a shorter message
            try:
                await ch.send(f"Vote received: {user_id} — {source}")
            except Exception:
                pass
    except Exception:
        pass
