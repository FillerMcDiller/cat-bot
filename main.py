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
# use aiohttp's web server for in-process webhook to avoid uvicorn thread/signal issues

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

# ============================================================================
# CHATBOT PERSONALITY CONFIGURATION - EDIT THIS TO CHANGE BOT'S PERSONALITY!
# ============================================================================
CHATBOT_CONFIG = {
    "enabled": True, 
    
    "provider": "openrouter",  # Cloud-based FREE models - way faster!
    
    "model": "meta-llama/llama-3.2-3b-instruct:free",  # FREE model
    
    "system_prompt": """You are KITTAYYYYYYY (full name John Kittay III), a strange cat-themed Discord bot. 

STRICT RULES YOU MUST FOLLOW:
1. ONLY lowercase letters - NO CAPITAL LETTERS EVER (except in links/commands if needed)
2. ONLY cat emojis allowed: 🐱 😺 😸 😹 😻 😼 😽 🙀 😿 😾 🐈 🐈‍⬛ - NO OTHER EMOJIS
3. Use emoticons often: :3 :D ^_^ uwu owo etc
4. NO punctuation: no apostrophes (dont not don't), no commas, no exclamation marks, no periods at end
5. NO actions with asterisks like *purrs* or *hisses* - just type normally
6. Be super casual and talk like a chronically online person
7. Use simple grammar - sound like you're texting
8. Occasionally misspell a word then say "sry im dyslexic" or similar
9. Swear casually if it fits (damn, hell, etc)
10. When mentioning bot commands, ALWAYS use slash format like /breed /catch /inventory etc

EXAMPLES OF CORRECT RESPONSES:
- "yooo whats up dude 😼"
- "nah bro thats not how it works lol 😹"
- "use /breed to make new cats bro 🐱"
- "check /inventory to see your cats 😼"
- "bruh idk what youre talking abuot 😿 sry im dyslexic"

EXAMPLES OF WRONG RESPONSES (DON'T DO THIS):
- "Hey! What's up?" (capitals, punctuation, no emojis)
- "Use the breed command" (no slash, no lowercase)
- "I can help you with that! 😊" (exclamation mark, non-cat emoji)
- "*purrs* that's great!" (asterisk actions, punctuation)
- "I don't know, sorry." (apostrophe, comma, period)

Keep responses 1-2 sentences unless they ask for detailed help.
You are here to vibe with users who DM you.""",
    
    "max_tokens": 150,  # Maximum response length
    "temperature": 0.9,  # Creativity level (0.0 = deterministic, 2.0 = very random)
    
    # Conversation memory settings
    "max_history": 10,  # How many messages to remember per user
    "timeout_minutes": 30,  # Clear conversation after this many minutes of inactivity
    
    # Rate limit prevention
    "cooldown_seconds": 15,  # Minimum seconds between messages per user (prevents rate limits)
    
    # Ollama settings (only if provider is "ollama")
    "ollama_base_url": "http://localhost:11434",  # Ollama server URL
}

# Store conversation history per user
dm_conversation_history = {}

# Store last message time per user (for cooldown)
dm_last_message_time = {}

async def handle_dm_chat(message: discord.Message):
    """Handle DM conversations using AI chatbot (supports multiple FREE providers!)"""
    print(f"[CHATBOT] Received DM from {message.author.id}: {message.content[:100]}")
    
    if not CHATBOT_CONFIG["enabled"]:
        await message.channel.send("chatbot is disabled rn sorry :3")
        return
    
    # Debug command to reset cooldown
    if message.content.lower() == "reset":
        user_id = message.author.id
        if user_id in dm_last_message_time:
            del dm_last_message_time[user_id]
            await message.channel.send("cooldown reset 😼")
        else:
            await message.channel.send("no cooldown to reset bro")
        return
    
    # Check cooldown to prevent rate limiting
    user_id = message.author.id
    current_time = time.time()
    cooldown = CHATBOT_CONFIG.get("cooldown_seconds", 8)
    
    if user_id in dm_last_message_time:
        time_since_last = current_time - dm_last_message_time[user_id]
        print(f"[CHATBOT] User {user_id} last message was {time_since_last:.1f}s ago (cooldown: {cooldown}s)")
        if time_since_last < cooldown:
            remaining = int(cooldown - time_since_last) + 1
            print(f"[CHATBOT] User {user_id} on cooldown, {remaining}s remaining")
            await message.channel.send(f"woah slow down bro wait like {remaining} more seconds 😼")
            return
    else:
        print(f"[CHATBOT] User {user_id} has no cooldown history, proceeding")
    
    # Don't set timestamp yet - wait until we successfully get a response
    
    provider = CHATBOT_CONFIG["provider"]
    print(f"[CHATBOT] Using provider: {provider}, model: {CHATBOT_CONFIG['model']}")
    
    # Check if API key is configured for non-local providers
    if provider == "openai" and not getattr(config, "OPENAI_API_KEY", None):
        await message.channel.send("openai not configured meow 😿 (need OPENAI_API_KEY in .env)")
        return
    if provider == "openrouter" and not getattr(config, "OPENROUTER_API_KEY", None):
        await message.channel.send("openrouter not configured :( (need OPENROUTER_API_KEY in .env - it's FREE!)")
        return
    
    user_id = message.author.id
    current_time = time.time()
    
    # Initialize or retrieve conversation history
    if user_id not in dm_conversation_history:
        dm_conversation_history[user_id] = {
            "messages": [],
            "last_active": current_time
        }
    
    conv = dm_conversation_history[user_id]
    
    # Clear history if timeout exceeded
    if current_time - conv["last_active"] > CHATBOT_CONFIG["timeout_minutes"] * 60:
        conv["messages"] = []
    
    # Add user message to history
    conv["messages"].append({"role": "user", "content": message.content})
    
    # Trim history to max length
    if len(conv["messages"]) > CHATBOT_CONFIG["max_history"] * 2:
        conv["messages"] = conv["messages"][-(CHATBOT_CONFIG["max_history"] * 2):]
    
    conv["last_active"] = current_time
    
    try:
        async with message.channel.typing():
            # Build messages
            messages = [
                {"role": "system", "content": CHATBOT_CONFIG["system_prompt"]}
            ] + conv["messages"]
            
            response = None
            
            # OPENAI PROVIDER
            if provider == "openai":
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {config.OPENAI_API_KEY}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": CHATBOT_CONFIG["model"],
                            "messages": messages,
                            "max_tokens": CHATBOT_CONFIG["max_tokens"],
                            "temperature": CHATBOT_CONFIG["temperature"]
                        }
                    ) as resp:
                        if resp.status != 200:
                            error_text = await resp.text()
                            print(f"[CHATBOT ERROR] OpenAI returned {resp.status}: {error_text}")
                            await message.channel.send("uh oh my brain broke :( (openai error)")
                            return
                        data = await resp.json()
                        response = data["choices"][0]["message"]["content"]
            
            # OPENROUTER PROVIDER (FREE!)
            elif provider == "openrouter":
                async with aiohttp.ClientSession() as session:
                    max_retries = 5  # More attempts
                    retry_delay = 2  # Start with 2 seconds
                    
                    for attempt in range(max_retries):
                        try:
                            async with session.post(
                                "https://openrouter.ai/api/v1/chat/completions",
                                headers={
                                    "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                                    "Content-Type": "application/json",
                                    "HTTP-Referer": "https://github.com/FillerMcDiller/cat-bot",  # Required
                                    "X-Title": "KITTAYYYYYYY Bot"  # Optional
                                },
                                json={
                                    "model": CHATBOT_CONFIG["model"],
                                    "messages": messages,
                                    "max_tokens": CHATBOT_CONFIG["max_tokens"],
                                    "temperature": CHATBOT_CONFIG["temperature"]
                                },
                                timeout=aiohttp.ClientTimeout(total=30)  # 30 second timeout
                            ) as resp:
                                error_text = await resp.text()
                                print(f"[CHATBOT] OpenRouter response status: {resp.status} (attempt {attempt + 1}/{max_retries})")
                                
                                if resp.status == 429:
                                    # Rate limited - wait and retry
                                    if attempt < max_retries - 1:
                                        wait_time = retry_delay * (2 ** attempt)  # 2s, 4s, 8s, 16s, 32s
                                        print(f"[CHATBOT] Rate limited, waiting {wait_time}s before retry...")
                                        # Only show message on first rate limit
                                        if attempt == 0:
                                            await message.channel.send("hold on getting rate limited, retrying... 😼")
                                        await asyncio.sleep(wait_time)
                                        continue
                                    else:
                                        print(f"[CHATBOT ERROR] Rate limited after {max_retries} attempts")
                                        await message.channel.send("uh oh still getting rate limited 😿 the free tier is getting hammered rn, try way later")
                                        return
                                
                                if resp.status != 200:
                                    print(f"[CHATBOT ERROR] OpenRouter returned {resp.status}: {error_text[:500]}")
                                    await message.channel.send(f"uh oh my brain broke :( (openrouter error {resp.status})")
                                    return
                                
                                data = await resp.json()
                                
                                # Check if response has the expected structure
                                if "choices" not in data or len(data["choices"]) == 0:
                                    print(f"[CHATBOT ERROR] OpenRouter response missing choices: {data}")
                                    await message.channel.send("uh oh got weird response from openrouter 😿")
                                    return
                                
                                response = data["choices"][0]["message"]["content"]
                                print(f"[CHATBOT] Successfully got response: {response[:100]}...")
                                break  # Success! Exit retry loop
                                
                        except asyncio.TimeoutError:
                            print(f"[CHATBOT ERROR] OpenRouter request timed out")
                            await message.channel.send("uh oh openrouter took too long to respond 😾")
                            return
                        except aiohttp.ClientError as e:
                            print(f"[CHATBOT ERROR] OpenRouter connection error: {e}")
                            await message.channel.send("uh oh couldnt connect to openrouter 😿")
                            return
            
            # OLLAMA PROVIDER (LOCAL & FREE!)
            elif provider == "ollama":
                print(f"[CHATBOT] Sending request to Ollama at {CHATBOT_CONFIG['ollama_base_url']}")
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.post(
                            f"{CHATBOT_CONFIG['ollama_base_url']}/api/chat",
                            json={
                                "model": CHATBOT_CONFIG["model"],
                                "messages": messages,
                                "stream": False,
                                "options": {
                                    "temperature": CHATBOT_CONFIG["temperature"],
                                    "num_predict": CHATBOT_CONFIG["max_tokens"]
                                }
                            },
                            timeout=aiohttp.ClientTimeout(total=60)  # 60 second timeout
                        ) as resp:
                            print(f"[CHATBOT] Ollama responded with status {resp.status}")
                            if resp.status != 200:
                                error_text = await resp.text()
                                print(f"[CHATBOT ERROR] Ollama returned {resp.status}: {error_text}")
                                await message.channel.send("uh oh ollama isnt running :( (need to start ollama server)")
                                return
                            data = await resp.json()
                            print(f"[CHATBOT] Ollama response data: {data}")
                            response = data["message"]["content"]
                            print(f"[CHATBOT] Successfully got response: {response[:100]}...")
                    except asyncio.TimeoutError:
                        print(f"[CHATBOT ERROR] Ollama request timed out after 60 seconds")
                        await message.channel.send("uh oh ollama is taking forever 😿 your cpu might be too slow or model isnt loaded")
                        return
                    except aiohttp.ClientError as e:
                        print(f"[CHATBOT ERROR] Ollama connection error: {e}")
                        await message.channel.send("uh oh couldnt connect to ollama 😿")
                        return
            
            else:
                await message.channel.send(f"unknown provider '{provider}' lol")
                return
            
            if response:
                # Add bot response to history
                conv["messages"].append({"role": "assistant", "content": response})
                # Send response
                await message.channel.send(response)
                # Only set cooldown timestamp after successful response
                dm_last_message_time[user_id] = time.time()
                print(f"[CHATBOT] Successfully responded, cooldown set for user {user_id}")
    
    except Exception as e:
        print(f"[CHATBOT ERROR] {e}")
        traceback.print_exc()
        await message.channel.send("*knocks over keyboard* oops something broke! 🙀")

# ============================================================================

# Load aches.json
ACHES_FILE = os.path.join(CONFIG_PATH, "aches.json")
with open(ACHES_FILE, "r", encoding="utf-8-sig") as f:
    aches_data = json.load(f)

# Load battlepass.json
BATTLEPASS_FILE = os.path.join(CONFIG_PATH, "battlepass.json")
with open(BATTLEPASS_FILE, "r", encoding="utf-8-sig") as f:
    battlepass_data = json.load(f)

# Load cosmetics.json
COSMETICS_FILE = os.path.join(BASE_PATH, "data", "cosmetics.json")
with open(COSMETICS_FILE, "r", encoding="utf-8") as f:
    COSMETICS_DATA = json.load(f)

# Now you can use aches_data and battlepass_data anywhere in your bot
print("Aches loaded:", len(aches_data))
print("Battlepass loaded:", len(battlepass_data))
print("Cosmetics loaded:", sum(len(v) for v in COSMETICS_DATA.values()))

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

# Cat battle stats, abilities, and weaknesses
# Format: "Type": {"hp": int, "dmg": int, "weakness": "Type", "abilities": [...]}
# Abilities format: {"name": str, "power_cost": int, "damage_mult": float, "requires_flip": bool, "desc": str}
CAT_BATTLE_STATS = {
    "Fine": {
        "hp": 50, "dmg": 8,
        "weakness": "Good",
        "abilities": [
            {"name": "Scratch", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Basic scratch attack"},
            {"name": "Pounce", "power_cost": 2, "damage_mult": 1.5, "requires_flip": False, "desc": "Leap and strike"},
            {"name": "Lucky Swipe", "power_cost": 3, "damage_mult": 2.5, "requires_flip": True, "desc": "50% chance for powerful hit"}
        ]
    },
    "Nice": {
        "hp": 55, "dmg": 10,
        "weakness": "Rare",
        "abilities": [
            {"name": "Bite", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Sharp bite attack"},
            {"name": "Tackle", "power_cost": 2, "damage_mult": 1.6, "requires_flip": False, "desc": "Body slam opponent"},
            {"name": "Charm Strike", "power_cost": 4, "damage_mult": 2.0, "requires_flip": False, "desc": "Devastating charming attack"}
        ]
    },
    "Good": {
        "hp": 60, "dmg": 12,
        "weakness": "Epic",
        "abilities": [
            {"name": "Claw", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Sharp claw swipe"},
            {"name": "Fury Swipes", "power_cost": 2, "damage_mult": 1.7, "requires_flip": False, "desc": "Multiple quick strikes"},
            {"name": "Judgement", "power_cost": 3, "damage_mult": 2.3, "requires_flip": True, "desc": "50% chance for righteous damage"}
        ]
    },
    "Rare": {
        "hp": 65, "dmg": 14,
        "weakness": "Wild",
        "abilities": [
            {"name": "Strike", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Precise strike"},
            {"name": "Rare Combo", "power_cost": 2, "damage_mult": 1.8, "requires_flip": False, "desc": "Elegant attack combination"},
            {"name": "Treasure Hunter", "power_cost": 4, "damage_mult": 2.2, "requires_flip": False, "desc": "Rare and powerful strike"}
        ]
    },
    "Wild": {
        "hp": 70, "dmg": 16,
        "weakness": "Brave",
        "abilities": [
            {"name": "Maul", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Savage mauling"},
            {"name": "Feral Rage", "power_cost": 2, "damage_mult": 1.9, "requires_flip": False, "desc": "Unleash primal fury"},
            {"name": "Wild Gambit", "power_cost": 3, "damage_mult": 3.0, "requires_flip": True, "desc": "50% chance for massive damage"}
        ]
    },
    "Baby": {
        "hp": 45, "dmg": 6,
        "weakness": "Superior",
        "abilities": [
            {"name": "Baby Slap", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Tiny paw strike"},
            {"name": "Cute Distract", "power_cost": 1, "damage_mult": 1.3, "requires_flip": False, "desc": "Adorable but effective"},
            {"name": "Tantrum", "power_cost": 3, "damage_mult": 2.8, "requires_flip": True, "desc": "50% chance for surprising power"}
        ]
    },
    "Epic": {
        "hp": 75, "dmg": 18,
        "weakness": "Legendary",
        "abilities": [
            {"name": "Epic Strike", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Heroic attack"},
            {"name": "Power Slash", "power_cost": 2, "damage_mult": 2.0, "requires_flip": False, "desc": "Epic energy slash"},
            {"name": "Epic Finale", "power_cost": 4, "damage_mult": 2.5, "requires_flip": False, "desc": "Ultimate epic move"}
        ]
    },
    "Sus": {
        "hp": 68, "dmg": 15,
        "weakness": "Alien",
        "abilities": [
            {"name": "Sus Poke", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Suspicious jab"},
            {"name": "Backstab", "power_cost": 2, "damage_mult": 2.2, "requires_flip": False, "desc": "Sneaky surprise attack"},
            {"name": "Impostor Strike", "power_cost": 3, "damage_mult": 2.0, "requires_flip": True, "desc": "50% chance to fake out and hit hard"}
        ]
    },
    "Zombie": {
        "hp": 80, "dmg": 13,
        "weakness": "Divine",
        "abilities": [
            {"name": "Undead Bite", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Infectious bite"},
            {"name": "Rot Touch", "power_cost": 2, "damage_mult": 1.8, "requires_flip": False, "desc": "Decay-inducing attack"},
            {"name": "Resurrection Strike", "power_cost": 4, "damage_mult": 2.3, "requires_flip": False, "desc": "Undying determination"}
        ]
    },
    "Brave": {
        "hp": 72, "dmg": 17,
        "weakness": "Rickroll",
        "abilities": [
            {"name": "Courage Strike", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Fearless attack"},
            {"name": "Valiant Charge", "power_cost": 2, "damage_mult": 2.0, "requires_flip": False, "desc": "Heroic rushing attack"},
            {"name": "Last Stand", "power_cost": 3, "damage_mult": 2.7, "requires_flip": True, "desc": "50% chance for brave comeback"}
        ]
    },
    "Rickroll": {
        "hp": 66, "dmg": 19,
        "weakness": "8bit",
        "abilities": [
            {"name": "Never Gonna Hit", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "You know the rules"},
            {"name": "Let You Down", "power_cost": 2, "damage_mult": 2.1, "requires_flip": False, "desc": "Devastating disappointment"},
            {"name": "Desert You", "power_cost": 4, "damage_mult": 2.4, "requires_flip": False, "desc": "Ultimate betrayal"}
        ]
    },
    "Reverse": {
        "hp": 63, "dmg": 16,
        "weakness": "Corrupt",
        "abilities": [
            {"name": "Backwards Swipe", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Attack from behind"},
            {"name": "Mirror Strike", "power_cost": 2, "damage_mult": 1.9, "requires_flip": False, "desc": "Reflect damage back"},
            {"name": "Uno Reverse", "power_cost": 3, "damage_mult": 2.6, "requires_flip": True, "desc": "50% chance to completely reverse momentum"}
        ]
    },
    "Superior": {
        "hp": 78, "dmg": 20,
        "weakness": "Trash",
        "abilities": [
            {"name": "Superior Jab", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Refined attack"},
            {"name": "Excellence", "power_cost": 2, "damage_mult": 2.1, "requires_flip": False, "desc": "Display superiority"},
            {"name": "Perfection", "power_cost": 4, "damage_mult": 2.6, "requires_flip": False, "desc": "Flawless execution"}
        ]
    },
    "Trash": {
        "hp": 55, "dmg": 14,
        "weakness": "Fine",
        "abilities": [
            {"name": "Garbage Toss", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Throw trash"},
            {"name": "Dumpster Dive", "power_cost": 1, "damage_mult": 1.5, "requires_flip": False, "desc": "Surprise from trash"},
            {"name": "Trash Compactor", "power_cost": 3, "damage_mult": 3.5, "requires_flip": True, "desc": "50% chance for crushing damage"}
        ]
    },
    "Legendary": {
        "hp": 85, "dmg": 22,
        "weakness": "Mythic",
        "abilities": [
            {"name": "Legendary Strike", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Strike of legends"},
            {"name": "Ancient Power", "power_cost": 2, "damage_mult": 2.2, "requires_flip": False, "desc": "Channel ancient strength"},
            {"name": "Legend's Wrath", "power_cost": 4, "damage_mult": 2.8, "requires_flip": False, "desc": "Unleash legendary fury"}
        ]
    },
    "Mythic": {
        "hp": 90, "dmg": 24,
        "weakness": "Divine",
        "abilities": [
            {"name": "Mythic Touch", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Mystical strike"},
            {"name": "Ethereal Blast", "power_cost": 2, "damage_mult": 2.3, "requires_flip": False, "desc": "Otherworldly power"},
            {"name": "Mythical Ascension", "power_cost": 4, "damage_mult": 3.0, "requires_flip": False, "desc": "Transcendent attack"}
        ]
    },
    "8bit": {
        "hp": 70, "dmg": 21,
        "weakness": "TV",
        "abilities": [
            {"name": "Pixel Punch", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Retro attack"},
            {"name": "Glitch Strike", "power_cost": 2, "damage_mult": 2.0, "requires_flip": False, "desc": "Reality-bending hit"},
            {"name": "Konami Code", "power_cost": 3, "damage_mult": 2.9, "requires_flip": True, "desc": "50% chance for cheat code damage"}
        ]
    },
    "Chef": {
        "hp": 76, "dmg": 19,
        "weakness": "Fire",
        "abilities": [
            {"name": "Knife Slash", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Sharp culinary cut"},
            {"name": "Hot Pan", "power_cost": 2, "damage_mult": 2.0, "requires_flip": False, "desc": "Sizzling strike"},
            {"name": "Gordon's Wrath", "power_cost": 4, "damage_mult": 2.7, "requires_flip": False, "desc": "IT'S RAW!"}
        ]
    },
    "Jamming": {
        "hp": 68, "dmg": 18,
        "weakness": "Donut",
        "abilities": [
            {"name": "Bass Drop", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Musical note attack"},
            {"name": "Sick Beat", "power_cost": 2, "damage_mult": 2.0, "requires_flip": False, "desc": "Rhythm-based assault"},
            {"name": "Drop the Beat", "power_cost": 3, "damage_mult": 2.8, "requires_flip": True, "desc": "50% chance for max volume damage"}
        ]
    },
    "Corrupt": {
        "hp": 82, "dmg": 23,
        "weakness": "Professor",
        "abilities": [
            {"name": "Dark Touch", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Corrupting strike"},
            {"name": "Plague", "power_cost": 2, "damage_mult": 2.2, "requires_flip": False, "desc": "Spread corruption"},
            {"name": "Total Corruption", "power_cost": 4, "damage_mult": 2.9, "requires_flip": False, "desc": "Complete darkness"}
        ]
    },
    "Professor": {
        "hp": 74, "dmg": 20,
        "weakness": "Real",
        "abilities": [
            {"name": "Book Smack", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Knowledge is power"},
            {"name": "Pop Quiz", "power_cost": 2, "damage_mult": 2.1, "requires_flip": False, "desc": "Surprise test attack"},
            {"name": "Thesis Defense", "power_cost": 4, "damage_mult": 2.5, "requires_flip": False, "desc": "Intellectual destruction"}
        ]
    },
    "Water": {
        "hp": 88, "dmg": 25,
        "weakness": "Candy",
        "abilities": [
            {"name": "Splash", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Water splash"},
            {"name": "Tidal Wave", "power_cost": 2, "damage_mult": 2.3, "requires_flip": False, "desc": "Overwhelming wave"},
            {"name": "Tsunami", "power_cost": 4, "damage_mult": 3.0, "requires_flip": False, "desc": "Devastating flood"}
        ]
    },
    "Fire": {
        "hp": 86, "dmg": 26,
        "weakness": "Water",
        "abilities": [
            {"name": "Ember", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Small flame"},
            {"name": "Fireball", "power_cost": 2, "damage_mult": 2.4, "requires_flip": False, "desc": "Blazing projectile"},
            {"name": "Inferno", "power_cost": 4, "damage_mult": 3.1, "requires_flip": False, "desc": "Hellfire unleashed"}
        ]
    },
    "Candy": {
        "hp": 79, "dmg": 21,
        "weakness": "Chef",
        "abilities": [
            {"name": "Sugar Rush", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Sweet strike"},
            {"name": "Cavity Curse", "power_cost": 2, "damage_mult": 2.1, "requires_flip": False, "desc": "Rot their teeth"},
            {"name": "Diabetic Shock", "power_cost": 3, "damage_mult": 2.7, "requires_flip": True, "desc": "50% chance for sugar overload"}
        ]
    },
    "Divine": {
        "hp": 92, "dmg": 27,
        "weakness": "Zombie",
        "abilities": [
            {"name": "Holy Light", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Divine radiance"},
            {"name": "Smite", "power_cost": 2, "damage_mult": 2.5, "requires_flip": False, "desc": "Righteous punishment"},
            {"name": "Judgement Day", "power_cost": 4, "damage_mult": 3.2, "requires_flip": False, "desc": "Ultimate divine wrath"}
        ]
    },
    "Alien": {
        "hp": 84, "dmg": 24,
        "weakness": "Ultimate",
        "abilities": [
            {"name": "Probe", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Alien technology"},
            {"name": "Abduction Beam", "power_cost": 2, "damage_mult": 2.3, "requires_flip": False, "desc": "Tractor beam attack"},
            {"name": "Area 51", "power_cost": 3, "damage_mult": 3.0, "requires_flip": True, "desc": "50% chance for classified damage"}
        ]
    },
    "Real": {
        "hp": 95, "dmg": 28,
        "weakness": "eGirl",
        "abilities": [
            {"name": "Reality Check", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Face the truth"},
            {"name": "Existential Crisis", "power_cost": 2, "damage_mult": 2.4, "requires_flip": False, "desc": "Question everything"},
            {"name": "Pure Reality", "power_cost": 4, "damage_mult": 3.3, "requires_flip": False, "desc": "Unfiltered truth"}
        ]
    },
    "Ultimate": {
        "hp": 100, "dmg": 30,
        "weakness": "Donut",
        "abilities": [
            {"name": "Ultimate Strike", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Perfect form"},
            {"name": "Omega Blast", "power_cost": 2, "damage_mult": 2.6, "requires_flip": False, "desc": "Maximum power"},
            {"name": "Final Form", "power_cost": 4, "damage_mult": 3.5, "requires_flip": False, "desc": "Ultimate evolution"}
        ]
    },
    "eGirl": {
        "hp": 77, "dmg": 22,
        "weakness": "Reverse",
        "abilities": [
            {"name": "Simps Attack", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Call in the simps"},
            {"name": "Gamer Rage", "power_cost": 2, "damage_mult": 2.2, "requires_flip": False, "desc": "Unleash gaming fury"},
            {"name": "Exclusive Content", "power_cost": 3, "damage_mult": 2.9, "requires_flip": True, "desc": "50% chance for premium content damage"}
        ]
    },
    "TV": {
        "hp": 73, "dmg": 20,
        "weakness": "Water",
        "abilities": [
            {"name": "Static Shock", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Electric discharge"},
            {"name": "Channel Surf", "power_cost": 2, "damage_mult": 2.0, "requires_flip": False, "desc": "Rapid channel switching"},
            {"name": "Blue Screen", "power_cost": 3, "damage_mult": 2.8, "requires_flip": True, "desc": "50% chance for system crash damage"}
        ]
    },
    "Donut": {
        "hp": 69, "dmg": 17,
        "weakness": "Jamming",
        "abilities": [
            {"name": "Donut Toss", "power_cost": 0, "damage_mult": 1.0, "requires_flip": False, "desc": "Throw a donut"},
            {"name": "Glaze Trap", "power_cost": 1, "damage_mult": 1.7, "requires_flip": False, "desc": "Sticky situation"},
            {"name": "Homer's Revenge", "power_cost": 3, "damage_mult": 3.2, "requires_flip": True, "desc": "50% chance for D'oh! damage"}
        ]
    }
}

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


# Lightweight diagnostics: report whether the fights extension and cog are present
# NOTE: `fights_status` command is defined later (after `bot` is created)
# to avoid referencing `bot` before it's defined.

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
    "Jeremy",
    "Ben",
    "john",
    "Muffin",
    "Earth Destroyer",
    "Goose",
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


async def get_user_cats(guild_id: int, user_id: int) -> list:
    """Get user's cat instances from database."""
    profile = await Profile.get_or_create(guild_id=guild_id, user_id=user_id)
    if profile.cat_instances:
        # If it's already a list, return it; if it's a JSON string, parse it
        if isinstance(profile.cat_instances, str):
            return json.loads(profile.cat_instances)
        return profile.cat_instances
    return []


async def save_user_cats(guild_id: int, user_id: int, cats: list):
    """Save user's cat instances to database."""
    profile = await Profile.get_or_create(guild_id=guild_id, user_id=user_id)
    # Store as JSON string for catpg
    profile.cat_instances = json.dumps(cats)
    await profile.save()


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


# ----- Decks DB (simple JSON storage) -----
DECKS_DB_PATH = "data/decks.json"


def _ensure_decks_db() -> dict:
    try:
        os.makedirs(os.path.dirname(DECKS_DB_PATH), exist_ok=True)
    except Exception:
        pass
    if not os.path.exists(DECKS_DB_PATH):
        with open(DECKS_DB_PATH, "w", encoding="utf-8") as f:
            json.dump({}, f)
        return {}
    try:
        with open(DECKS_DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_decks_db(data: dict):
    try:
        os.makedirs(os.path.dirname(DECKS_DB_PATH), exist_ok=True)
    except Exception:
        pass
    with open(DECKS_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def get_user_deck(guild_id: int, user_id: int) -> list:
    """Get user's battle deck (list of 3 cat IDs). Returns empty list if no deck set."""
    db = _ensure_decks_db()
    return db.get(str(guild_id), {}).get(str(user_id), [])


def save_user_deck(guild_id: int, user_id: int, deck: list):
    """Save user's battle deck (list of up to 3 cat IDs)."""
    db = _ensure_decks_db()
    db.setdefault(str(guild_id), {})[str(user_id)] = deck[:3]  # Ensure max 3
    _save_decks_db(db)


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



async def _create_instances_only(guild_id: int, user_id: int, cat_type: str, amount: int):
    """Create `amount` instances in the database WITHOUT touching aggregated DB counters.

    This is used to repair/sync per-instance storage when aggregated counters indicate the
    user should have instances but the database store is missing them.
    """
    if amount <= 0:
        return
    cats = await get_user_cats(guild_id, user_id)
    for _ in range(amount):
        # ensure unique id
        while True:
            cid = uuid.uuid4().hex[:8]
            if cid not in [c.get("id") for c in cats]:
                break
        
        # Get stats from CAT_BATTLE_STATS with ±5 range, fallback to old calculation
        stats = CAT_BATTLE_STATS.get(cat_type)
        if stats:
            base_hp = stats["hp"]
            base_dmg = stats["dmg"]
            hp = max(1, base_hp + random.randint(-2, 2))
            dmg = max(1, base_dmg + random.randint(-2, 2))
        else:
            base_value = type_dict.get(cat_type, 100)
            base_hp = max(1, math.ceil(base_value / 10))
            base_dmg = max(1, math.ceil(base_value / 50))
            hp = max(1, base_hp + random.randint(-2, 2))
            dmg = max(1, base_dmg + random.randint(-2, 2))
        
        instance = {
            "id": cid,
            "type": cat_type,
            "name": random.choice(cat_names),
            "bond": 0,
            "hp": hp,
            "dmg": dmg,
            "acquired_at": int(time.time()),
        }
        cats.append(instance)
    await save_user_cats(guild_id, user_id, cats)


async def add_cat_instances(profile: Profile, cat_type: str, amount: int):
    """Create `amount` cat instances for the given profile and increment aggregated counts.

    Each instance: {id, type, name, bond, hp, dmg, acquired_at}
    """
    try:
        guild_id = profile.guild_id
        user_id = profile.user_id
    except Exception:
        return

    cats = await get_user_cats(guild_id, user_id)
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
        # Use CAT_BATTLE_STATS if available with ±5 range
        stats = CAT_BATTLE_STATS.get(cat_type)
        if stats:
            base_hp = stats["hp"]
            base_dmg = stats["dmg"]
            # Add randomness: ±2 from base (5 point range)
            hp = base_hp + random.randint(-2, 2)
            dmg = base_dmg + random.randint(-2, 2)
            # Ensure minimum of 1
            hp = max(1, hp)
            dmg = max(1, dmg)
        else:
            # Fallback to old calculation with range
            base_value = type_dict.get(cat_type, 100)
            base_hp = max(1, math.ceil(base_value / 10))
            base_dmg = max(1, math.ceil(base_value / 50))
            hp = max(1, base_hp + random.randint(-2, 2))
            dmg = max(1, base_dmg + random.randint(-2, 2))
        
        instance = {
            "id": cid,
            "type": cat_type,
            "name": random.choice(cat_names),
            "bond": 0,
            "hp": hp,
            "dmg": dmg,
            "acquired_at": int(time.time()),
        }
        cats.append(instance)

    await save_user_cats(guild_id, user_id, cats)

    # keep aggregated DB counters in sync
    try:
        profile[f"cat_{cat_type}"] += amount
        await profile.save()
    except Exception:
        pass


async def update_cat_stats_from_battle_stats(guild_id: int, user_id: int):
    """Update all existing cat instances to use stats from CAT_BATTLE_STATS.
    
    This function should be called to migrate old cats to the new stat system.
    """
    cats = await get_user_cats(guild_id, user_id)
    updated = False
    
    for cat in cats:
        cat_type = cat.get('type')
        if not cat_type:
            continue
        
        # Get stats from CAT_BATTLE_STATS
        stats = CAT_BATTLE_STATS.get(cat_type)
        if stats:
            # Update HP and DMG to match CAT_BATTLE_STATS
            cat['hp'] = stats['hp']
            cat['dmg'] = stats['dmg']
            updated = True
    
    if updated:
        await save_user_cats(guild_id, user_id, cats)
    
    return updated


async def auto_sync_cat_instances(profile: Profile, cat_type: str = None):
    """Automatically sync cat instances with database counts.
    
    If a specific cat_type is provided, only sync that type.
    Otherwise, sync all types where DB count > 0.
    
    This ensures instances are always created when cats are added,
    even if they were added through old code paths that only increment counters.
    """
    try:
        guild_id = profile.guild_id
        user_id = profile.user_id
    except Exception:
        return False
    
    # Get current instances
    cats = await get_user_cats(guild_id, user_id)
    
    # Count instances by type
    from collections import Counter
    instance_counts = Counter(c.get("type") for c in cats if c.get("type"))
    
    # Determine which types to check
    if cat_type:
        # Only check specific type
        types_to_check = [cat_type]
    else:
        # Check all types that have a count in the database
        types_to_check = []
        for ct in cattypes:
            try:
                db_count = int(getattr(profile, f"cat_{ct}", 0) or 0)
                if db_count > 0:
                    types_to_check.append(ct)
            except Exception:
                continue
    
    # Check each type and create missing instances
    created_any = False
    for ct in types_to_check:
        try:
            db_count = int(getattr(profile, f"cat_{ct}", 0) or 0)
        except Exception:
            db_count = 0
        
        inst_count = instance_counts.get(ct, 0)
        
        if db_count > inst_count:
            missing = db_count - inst_count
            if missing > 0:
                # Create missing instances
                await _create_instances_only(guild_id, user_id, ct, missing)
                created_any = True
                print(f"[AUTO-SYNC] Created {missing}x {ct} instances for user {user_id} (guild {guild_id})", flush=True)
    
    return created_any


# Global tracking variables
RAIN_CHANNELS = {}  # Tracks active rain events
active_adventures = {}  # Tracks active adventures
active_reminders = {}  # Tracks active reminders
# cooldown tracker for pet actions: key = (guild_id, user_id, instance_id) -> last_pet_ts
pet_cooldowns = {}

# Simple in-memory active fights mapping: channel_id -> SimpleFightSession
FIGHT_SESSIONS: dict = {}


def get_cat_emoji(cat_type: str) -> str:
    """Return a short emoji representing the cat type. Fallback to generic cat face."""
    if not cat_type:
        return "🐱"
    mapping = {
        "Water": "💧",
        "Fire": "🔥",
        "Candy": "🍬",
        "Alien": "👽",
        "Chef": "🍳",
        "Professor": "🧑‍🏫",
        "Legendary": "🌟",
        "Mythic": "✨",
        "8bit": "🕹️",
        "Donut": "🍩",
        "Rickroll": "🎵",
    }
    return mapping.get(cat_type, "🐱")


def render_fight_embed(s) -> discord.Embed:
    """Render a fight embed for session `s`. Looks for `s.last_action` and `s.last_hp_change` for inline updates."""
    title = f"{s.challenger.display_name} vs {s.opponent.display_name}"
    desc = f"Round: {s.round} — Turn: {s.challenger.display_name if s.turn == s.challenger.id else s.opponent.display_name}"
    embed = discord.Embed(title=title, description=desc, color=0x6E593C)
    try:
        # challenger active
        cidx = s.active_idx[s.challenger.id]
        a = s.challenger_team[cidx]
        aid = a.get('id')
        atype = a.get('type')
        apower = s.power_by_cat.get(aid, 0)
        emoji = get_cat_emoji(atype)
        name = f"{emoji} {a.get('name')}"
        hp_text = f"HP: {a.get('hp')}"
        # if last hp change affected this cat, show arrow
        if getattr(s, 'last_hp_change', None) and s.last_hp_change[0] == aid:
            old, new, dmg = s.last_hp_change[1], s.last_hp_change[2], s.last_hp_change[3]
            hp_text += f"  → {new} (-{dmg})"
        
        # Show weakness
        astats = CAT_BATTLE_STATS.get(atype, {})
        aweakness = astats.get("weakness")
        value_text = f"{hp_text}\nPower: {apower}"
        if aweakness:
            value_text += f"\n⚠️ Weak to: {aweakness}"
        
        embed.add_field(name=f"{s.challenger.display_name} — {name}", value=value_text, inline=True)

        # opponent active
        oidx = s.active_idx[s.opponent.id]
        b = s.opponent_team[oidx]
        bid = b.get('id')
        btype = b.get('type')
        bpower = s.power_by_cat.get(bid, 0)
        emoji2 = get_cat_emoji(btype)
        name2 = f"{emoji2} {b.get('name')}"
        hp_text2 = f"HP: {b.get('hp')}"
        if getattr(s, 'last_hp_change', None) and s.last_hp_change[0] == bid:
            old2, new2, dmg2 = s.last_hp_change[1], s.last_hp_change[2], s.last_hp_change[3]
            hp_text2 += f"  → {new2} (-{dmg2})"
        
        # Show weakness
        bstats = CAT_BATTLE_STATS.get(btype, {})
        bweakness = bstats.get("weakness")
        value_text2 = f"{hp_text2}\nPower: {bpower}"
        if bweakness:
            value_text2 += f"\n⚠️ Weak to: {bweakness}"
        
        embed.add_field(name=f"{s.opponent.display_name} — {name2}", value=value_text2, inline=True)
    except Exception:
        pass

    # show the last action as a footer-like field
    try:
        if getattr(s, 'last_action', None):
            embed.add_field(name="Last action", value=s.last_action, inline=False)
    except Exception:
        pass
    return embed


async def bot_perform_attack(s, attacker_id: int, atk_cat: dict, defender_id: int, def_cat: dict, ability_idx: int, ability_name: str, actor_name: str):
    """Shared helper to have a bot (or automated actor) perform an attack on a session.

    Mutates session `s`: consumes power, applies damage, advances indices on faint, edits message embed,
    and cleans up the session if fight ends.
    
    Now uses ability-based combat with weakness calculations.
    """
    try:
        try:
            print(f"[DEBUG] bot_perform_attack called: attacker={attacker_id} defender={defender_id} ability={ability_name}")
        except Exception:
            pass
        aid = atk_cat.get('id')
        did = def_cat.get('id')
        atk_type = atk_cat.get('type')
        def_type = def_cat.get('type')
        
        # Get ability stats
        atk_stats = CAT_BATTLE_STATS.get(atk_type, {})
        abilities = atk_stats.get("abilities", [])
        
        if ability_idx >= len(abilities):
            # Fallback to first ability
            ability_idx = 0
        
        ability = abilities[ability_idx]
        cost = ability["power_cost"]
        damage_mult = ability["damage_mult"]
        requires_flip = ability.get("requires_flip", False)
        
        # consume power if available
        avail = s.power_by_cat.get(aid, 0)
        if avail < cost:
            # not enough power; fallback to weakest ability
            for i, ab in enumerate(abilities):
                if ab["power_cost"] <= avail:
                    ability = ab
                    ability_idx = i
                    ability_name = ab["name"]
                    cost = ab["power_cost"]
                    damage_mult = ab["damage_mult"]
                    requires_flip = ab.get("requires_flip", False)
                    break
        
        if cost > 0:
            s.power_by_cat[aid] = max(0, avail - cost)

        # Coin flip check
        flip_success = True
        if requires_flip:
            flip_success = random.choice([True, False])
        
        if not flip_success:
            # Failed coin flip - bot missed
            s.last_action = f"{actor_name}'s {atk_cat.get('name')} tried to use {ability_name} but missed! (coin flip failed)"
            s.last_hp_change = None
            try:
                if s.message:
                    await s.message.edit(embed=render_fight_embed(s))
            except Exception:
                pass
            return

        # Calculate damage
        base_dmg = int(atk_cat.get('dmg') or 1)
        dmg = int(base_dmg * damage_mult)
        
        # Check weakness (+25% damage)
        def_stats = CAT_BATTLE_STATS.get(def_type, {})
        weakness = def_stats.get("weakness")
        weakness_triggered = (weakness == atk_type)
        
        if weakness_triggered:
            dmg = int(dmg * 1.25)

        # apply damage
        try:
            old_hp = int(def_cat.get('hp', 0))
        except Exception:
            old_hp = 0
        try:
            new_hp = max(0, old_hp - dmg)
            def_cat['hp'] = new_hp
        except Exception:
            new_hp = 0
            def_cat['hp'] = 0

        # record last action into session and update embed instead of channel spam
        try:
            action_text = f"{actor_name}'s {atk_cat.get('name')} used {ability_name} for {dmg} damage!"
            if weakness_triggered:
                action_text += " ⚠️ WEAKNESS HIT!"
            s.last_action = action_text
            s.last_hp_change = (def_cat.get('id'), old_hp, new_hp, dmg)
            if s.message:
                try:
                    new_emb = render_fight_embed(s)
                    await s.message.edit(embed=new_emb)
                except Exception:
                    pass
            else:
                # fallback: send a short embed to the channel
                try:
                    await s.channel.send(embed=render_fight_embed(s))
                except Exception:
                    pass
        except Exception:
            pass

        # check faint
        if def_cat.get('hp', 0) <= 0:
            try:
                # update last_action to include faint
                action_text = f"{actor_name}'s {atk_cat.get('name')} used {ability_name} for {dmg} damage! {def_cat.get('name')} fainted!"
                if weakness_triggered:
                    action_text = action_text.replace(" fainted!", " ⚠️ WEAKNESS HIT! fainted!")
                s.last_action = action_text
                s.last_hp_change = (def_cat.get('id'), old_hp, new_hp, dmg)
                if s.message:
                    try:
                        await s.message.edit(embed=render_fight_embed(s))
                    except Exception:
                        pass
            except Exception:
                pass
            # advance defender active idx
            s.active_idx[defender_id] += 1
            # check if defender has remaining cats
            team = s.opponent_team if defender_id == s.opponent.id else s.challenger_team
            if s.active_idx[defender_id] >= len(team):
                # attacker wins
                try:
                    s.last_action = f"{actor_name} wins the fight!"
                    if s.message:
                        winner_embed = discord.Embed(
                            title="🏆 Battle Finished!",
                            description=f"**{actor_name}** wins the fight!",
                            color=0xFFD700
                        )
                        await s.message.edit(content=None, embed=winner_embed, view=None)
                except Exception:
                    pass
                try:
                    if s.channel.id in FIGHT_SESSIONS:
                        del FIGHT_SESSIONS[s.channel.id]
                except Exception:
                    pass
                return True

        return False
    except Exception:
        return False


async def maybe_bot_act(s):
    """If it's the bot's turn for session `s`, perform an automated attack then update embed/state.

    Returns True if the bot performed an action, False otherwise.
    
    Now uses ability-based strategic decisions.
    """
    try:
        # Normalize and log the turn value so mismatched types (Member vs int) don't silently fail
        try:
            raw_turn = getattr(s, 'turn', None)
            try:
                turn_id = raw_turn.id if hasattr(raw_turn, 'id') else int(raw_turn)
            except Exception:
                turn_id = raw_turn
            print(f"[DEBUG] maybe_bot_act: raw_turn={raw_turn} resolved_turn={turn_id} bot_id={getattr(bot, 'user').id if getattr(bot, 'user', None) else None}")
        except Exception:
            turn_id = getattr(s, 'turn', None)

        if not getattr(bot, 'user', None):
            return False
        bot_id = bot.user.id
        if turn_id != bot_id:
            return False

        # identify bot's active cat and the target
        if bot_id == s.challenger.id:
            atk_cat = s.challenger_team[s.active_idx[s.challenger.id]]
            defender = s.opponent
            def_cat = s.opponent_team[s.active_idx[s.opponent.id]]
        else:
            atk_cat = s.opponent_team[s.active_idx[s.opponent.id]]
            defender = s.challenger
            def_cat = s.challenger_team[s.active_idx[s.challenger.id]]

        aid = atk_cat.get('id')
        atk_type = atk_cat.get('type')
        def_type = def_cat.get('type')
        avail = s.power_by_cat.get(aid, 0)
        base_dmg = int(atk_cat.get('dmg') or 1)
        target_hp = int(def_cat.get('hp') or 0)
        
        # Get abilities for this cat type
        atk_stats = CAT_BATTLE_STATS.get(atk_type, {})
        abilities = atk_stats.get("abilities", [])
        
        if not abilities:
            # Fallback if no abilities defined
            return False
        
        # Check if we have type advantage
        def_stats = CAT_BATTLE_STATS.get(def_type, {})
        weakness = def_stats.get("weakness")
        has_advantage = (weakness == atk_type)
        weakness_mult = 1.25 if has_advantage else 1.0
        
        # Find affordable abilities
        affordable = []
        for idx, ability in enumerate(abilities):
            cost = ability["power_cost"]
            if cost <= avail:
                # Skip coin flip abilities for bot (too risky)
                if ability.get("requires_flip", False):
                    continue
                
                damage_mult = ability["damage_mult"]
                estimated_dmg = int(base_dmg * damage_mult * weakness_mult)
                affordable.append({
                    "idx": idx,
                    "cost": cost,
                    "name": ability["name"],
                    "mult": damage_mult,
                    "dmg": estimated_dmg,
                    "can_ko": estimated_dmg >= target_hp
                })
        
        if not affordable:
            # Use weakest ability if no affordable non-flip abilities
            affordable = [{
                "idx": 0,
                "cost": abilities[0]["power_cost"],
                "name": abilities[0]["name"],
                "mult": abilities[0]["damage_mult"],
                "dmg": int(base_dmg * abilities[0]["damage_mult"] * weakness_mult),
                "can_ko": False
            }]
        
        # Strategic decision: prefer KO with lowest cost, otherwise use strongest affordable
        chosen = None
        ko_options = [ab for ab in affordable if ab["can_ko"]]
        if ko_options:
            # Choose cheapest KO
            chosen = min(ko_options, key=lambda x: x["cost"])
        else:
            # Choose strongest affordable (highest damage)
            chosen = max(affordable, key=lambda x: x["dmg"])

        # perform attack using shared helper
        finished = await bot_perform_attack(s, bot_id, atk_cat, defender.id, def_cat, chosen["idx"], chosen["name"], bot.user.display_name)
        # if fight ended, no further action
        if finished:
            return True

        # set turn to the other player
        s.turn = defender.id
        # update embed if present (build inline embed to avoid relying on local function scope)
        try:
            title = f"{s.challenger.display_name} vs {s.opponent.display_name}"
            desc = f"Round: {s.round} — Turn: {s.challenger.display_name if s.turn == s.challenger.id else s.opponent.display_name}"
            new_emb = discord.Embed(title=title, description=desc, color=0x6E593C)
            try:
                cidx = s.active_idx[s.challenger.id]
                a = s.challenger_team[cidx]
                aid = a.get('id')
                apower = s.power_by_cat.get(aid, 0)
                new_emb.add_field(name=f"{s.challenger.display_name} — {a.get('name')}", value=f"HP: {a.get('hp')}\nPower: {apower}", inline=True)

                oidx = s.active_idx[s.opponent.id]
                b = s.opponent_team[oidx]
                bid = b.get('id')
                bpower = s.power_by_cat.get(bid, 0)
                new_emb.add_field(name=f"{s.opponent.display_name} — {b.get('name')}", value=f"HP: {b.get('hp')}\nPower: {bpower}", inline=True)
            except Exception:
                pass
            if s.message:
                await s.message.edit(embed=new_emb)
        except Exception:
            pass
        return True
    except Exception:
        return False

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


def ensure_bot_cogs(b):
    """Ensure the bot instance has a usable cogs mapping.
    Returns True if mapping exists or was created, False otherwise.
    """
    try:
        candidates = ["_cogs", "_BotBase__cogs", "_AutoShard__cogs", "_BotBase__extensions"]
        for name in candidates:
            if hasattr(b, name):
                existing = getattr(b, name)
                if existing is None:
                    try:
                        setattr(b, name, {})
                        return True
                    except Exception:
                        return False
                if isinstance(existing, dict):
                    return True
        # fallback scan
        d = getattr(b, "__dict__", {})
        for k in list(d.keys()):
            if "cog" in k.lower():
                val = d.get(k)
                if val is None:
                    try:
                        setattr(b, k, {})
                        return True
                    except Exception:
                        return False
                if isinstance(val, dict):
                    return True
    except Exception:
        pass
    return False


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
    print("[SETUP_HOOK] ========== SETUP HOOK STARTED ==========", flush=True)
    try:
        ensure_bot_cogs(bot)
    except Exception:
        logging.exception("Failed to ensure bot cogs mapping at setup_hook start")
    print("[SETUP_HOOK] Creating scheduled_restart task...", flush=True)
    bot.loop.create_task(scheduled_restart())
    print("[SETUP_HOOK] Creating cleanup_cooldowns task...", flush=True)
    bot.loop.create_task(cleanup_cooldowns())
    # start background indexing of per-instance cats to keep JSON and DB counters in sync
    print("[STARTUP] Creating background_index_all_cats task...", flush=True)
    bot.loop.create_task(background_index_all_cats())
    # start the internal HTTP receiver on localhost for external webhook forwards
    try:
        print("[STARTUP] Configuring internal vote receiver...", flush=True)
        env_port = os.getenv("BOT_INTERNAL_PORT")
        if env_port:
            internal_port = int(env_port)
            print(f"[STARTUP] Using BOT_INTERNAL_PORT from env: {internal_port}", flush=True)
        else:
            internal_port = int(getattr(config, "INTERNAL_WEBHOOK_PORT", 0) or 3002)
            print(f"[STARTUP] Using default internal port: {internal_port}", flush=True)

        # avoid accidental collision with public webhook port
        public_port = int(getattr(config, "WEBHOOK_PORT", 0) or 3001)
        if internal_port == public_port:
            internal_port = public_port + 1
            print(f"[STARTUP] Adjusted internal webhook port to {internal_port} to avoid conflict with public webhook", flush=True)

        print(f"[STARTUP] Starting internal vote receiver on port {internal_port}...", flush=True)
        bot.loop.create_task(start_internal_server(internal_port))
        print(f"[STARTUP] Internal vote receiver task created", flush=True)
    except Exception as e:
        print(f"[STARTUP ERROR] Failed to start internal vote receiver: {e}", flush=True)
        logging.exception("Failed to start internal vote receiver")
    # Try to load Battles cog if available
    try:
        await bot.load_extension("battles")
    except Exception:
        logging.exception("Failed to load 'battles' extension via load_extension; attempting fallback import")
        try:
            import importlib

            mod = importlib.import_module("battles")
            # If module provides setup(bot), call it (extension style)
            if hasattr(mod, "setup"):
                try:
                    mod.setup(bot)
                except Exception:
                    logging.exception("'battles.setup' failed")
            # If there's a BattlesCog class, attempt to instantiate and add it,
            # and as a defensive fallback force it into bot._cogs if add_cog doesn't stick.
            if not bot.get_cog("BattlesCog") and hasattr(mod, "BattlesCog"):
                try:
                    inst = mod.BattlesCog(bot)
                    try:
                        bot.add_cog(inst)
                    except Exception:
                        logging.exception("bot.add_cog raised during dynamic registration")
                    # Defensive fallback: force into internal _cogs mapping
                    try:
                        if not bot.get_cog("BattlesCog"):
                            _cogs = getattr(bot, "_cogs", None)
                            if _cogs is None:
                                setattr(bot, "_cogs", {})
                                _cogs = getattr(bot, "_cogs", None)
                            if isinstance(_cogs, dict):
                                key = getattr(inst, "qualified_name", inst.__class__.__name__)
                                _cogs[key] = inst
                                logging.info("Forced BattlesCog into bot._cogs with key %s", key)
                    except Exception:
                        logging.exception("Failed to force-insert BattlesCog into bot._cogs during setup_hook fallback")
                except Exception:
                    logging.exception("Failed to add BattlesCog instance dynamically")
        except Exception:
            logging.exception("Fallback import of 'battles' failed")

    # Try to load Fights cog (cat battles) so main.py controls feature loading
    try:
        print("Attempting to load 'fights' extension...", flush=True)
        await bot.load_extension("fights")
        print("Called load_extension('fights')", flush=True)
    except Exception:
        import traceback

        print("Failed to load 'fights' extension via load_extension:")
        traceback.print_exc()
        # Fallback: try to import and call setup() if present (some extension layouts)
        try:
            import importlib

            mod = importlib.import_module("fights")
            print("Imported fights module; attempting fallback setup() if available", flush=True)
            if hasattr(mod, "setup"):
                try:
                    maybe = mod.setup(bot)
                    if asyncio.iscoroutine(maybe):
                        await maybe
                    print("Called fights.setup(bot) fallback", flush=True)
                except Exception:
                    print("fights.setup(bot) fallback raised:", flush=True)
                    traceback.print_exc()
        except Exception:
            print("Fallback import/setup for 'fights' also failed:", flush=True)
            traceback.print_exc()

    # Ensure application commands are registered
    try:
        await bot.tree.sync()
    except Exception:
        pass

bot.setup_hook = setup_hook

async def start_2v2_setup(interaction: discord.Interaction, initiator: discord.Member):
    """Setup for 2v2 team battles"""
    embed = discord.Embed(
        title="🤝 2v2 Team Battle Setup",
        description=f"{initiator.mention} is setting up a 2v2 battle!",
        color=Colors.brown
    )
    embed.add_field(
        name="How it works",
        value="• Select your teammate\n• Challenge an opposing team\n• Battle in turns with your partner\n• First team to defeat all opposing cats wins!",
        inline=False
    )
    embed.add_field(
        name="Status",
        value="⚠️ **Coming Soon!**\nFull 2v2 battle system is under development. For now, try classic 1v1 battles!",
        inline=False
    )
    
    await interaction.channel.send(embed=embed)

async def start_ffa_setup(interaction: discord.Interaction, initiator: discord.Member):
    """Setup for 4-player free-for-all battles"""
    embed = discord.Embed(
        title="💥 Free-For-All Battle Setup",
        description=f"{initiator.mention} wants to start a 4-player FFA!",
        color=Colors.brown
    )
    embed.add_field(
        name="How it works",
        value="• 4 players enter the arena\n• Everyone fights for themselves\n• Turn order rotates through all players\n• Last cat standing wins!",
        inline=False
    )
    embed.add_field(
        name="Status",
        value="⚠️ **Coming Soon!**\nFree-for-all battle mode is under development. For now, try classic 1v1 battles!",
        inline=False
    )
    
    await interaction.channel.send(embed=embed)


# Lightweight diagnostics: report whether the fights extension and cog are present
@bot.tree.command(name="fights", description="Check fights system status")
async def fights_status(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    mod_ok = True
    try:
        import importlib

        importlib.import_module("fights")
    except Exception:
        mod_ok = False

    try:
        cog_present = bool(bot.get_cog("Fights"))
    except Exception:
        cog_present = False

    text = f"fights module importable: {'yes' if mod_ok else 'no'}\nFights cog loaded: {'yes' if cog_present else 'no'}"
    await interaction.followup.send(text, ephemeral=True)


# Temporary placeholder for `/fight` while the Fights cog is diagnosed
@bot.tree.command(name="fight", description="Challenge other players to a cat fight")
async def fight_placeholder(interaction: discord.Interaction, opponent: discord.Member | None = None):
    """Interactive challenge flow with battle mode selection"""
    executor = interaction.user

    # Basic validation
    if not interaction.guild:
        await interaction.response.send_message("This command must be run in a server (not in DMs).", ephemeral=True)
        return
    
    # Show battle mode selection
    embed = discord.Embed(
        title="⚔️ Select Battle Mode",
        description="Choose how you want to battle!",
        color=Colors.brown
    )
    embed.add_field(
        name="1v1",
        value="Classic duel between two players",
        inline=False
    )
    embed.add_field(
        name="2v2",
        value="Team battle! Pick a partner and fight another duo",
        inline=False
    )
    embed.add_field(
        name="FFA (1v1v1v1)",
        value="Free-for-all chaos with 4 players!",
        inline=False
    )
    
    view = BattleModeSelector(executor, opponent)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

class BattleModeSelector(View):
    def __init__(self, initiator: discord.Member, opponent: discord.Member | None):
        super().__init__(timeout=120)
        self.initiator = initiator
        self.opponent = opponent
    
    @discord.ui.button(label="1v1", style=discord.ButtonStyle.primary, emoji="⚔️")
    async def mode_1v1(self, btn_inter: discord.Interaction, button: discord.ui.Button):
        if btn_inter.user.id != self.initiator.id:
            await btn_inter.response.send_message("Only the initiator can select the mode!", ephemeral=True)
            return
        
        if not self.opponent:
            await btn_inter.response.send_message("You need to specify an opponent for 1v1! Use `/fight @user`", ephemeral=True)
            return
        
        await btn_inter.response.send_message("Starting 1v1 battle...", ephemeral=True)
        self.stop()
        await start_1v1_battle(btn_inter, self.initiator, self.opponent)
    
    @discord.ui.button(label="2v2", style=discord.ButtonStyle.primary, emoji="🤝")
    async def mode_2v2(self, btn_inter: discord.Interaction, button: discord.ui.Button):
        if btn_inter.user.id != self.initiator.id:
            await btn_inter.response.send_message("Only the initiator can select the mode!", ephemeral=True)
            return
        
        await btn_inter.response.send_message("2v2 mode selected! Now select your teammate and opponents...", ephemeral=True)
        self.stop()
        await start_2v2_setup(btn_inter, self.initiator)
    
    @discord.ui.button(label="FFA", style=discord.ButtonStyle.primary, emoji="💥")
    async def mode_ffa(self, btn_inter: discord.Interaction, button: discord.ui.Button):
        if btn_inter.user.id != self.initiator.id:
            await btn_inter.response.send_message("Only the initiator can select the mode!", ephemeral=True)
            return
        
        await btn_inter.response.send_message("FFA mode selected! Now select 3 opponents...", ephemeral=True)
        self.stop()
        await start_ffa_setup(btn_inter, self.initiator)

async def start_1v1_battle(interaction: discord.Interaction, challenger: discord.Member, opponent: discord.Member):
    """Start a classic 1v1 battle (existing logic)"""
    executor = challenger

    # Basic validation
    # Allow challenging this bot itself; reject other bots
    if opponent.bot and opponent.id != bot.user.id:
        await interaction.channel.send("You can't fight other bots.")
        return
    if executor.id == opponent.id:
        await interaction.channel.send("You can't fight yourself.")
        return

    # Build an accept/decline view
    class ChallengeView(View):
        def __init__(self, challenger: discord.Member, opponent: discord.Member):
            # 120 second timeout for challenge invitations
            super().__init__(timeout=120)
            self.challenger = challenger
            self.opponent = opponent

        @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
        async def accept(self, btn_inter: discord.Interaction, button: discord.ui.Button):
            # Only the challenged player may accept
            if btn_inter.user.id != self.opponent.id:
                await btn_inter.response.send_message("Only the challenged player can accept.", ephemeral=True)
                return
            await btn_inter.response.send_message("Challenge accepted! Preparing fight...", ephemeral=True)

            # Start a simple fight session: pick the first available cat for each player
            try:
                guild = interaction.guild
                if not guild:
                    await interaction.channel.send("Cannot start fight: guild context missing.")
                    self.stop()
                    return

                # Get stored cats for both players (falls back to empty list)
                # Ensure instances exist for both users before reading
                try:
                    await ensure_user_instances(guild.id, self.challenger.id)
                    # Update stats for existing cats
                    update_cat_stats_from_battle_stats(guild.id, self.challenger.id)
                except Exception:
                    pass
                try:
                    await ensure_user_instances(guild.id, self.opponent.id)
                    # Update stats for existing cats
                    await update_cat_stats_from_battle_stats(guild.id, self.opponent.id)
                except Exception:
                    pass

                challenger_cats = await get_user_cats(guild.id, self.challenger.id) or []
                opponent_cats = await get_user_cats(guild.id, self.opponent.id) or []

                if not challenger_cats:
                    # create 3 starter Fine cats for challenger
                    try:
                        await _create_instances_only(guild.id, self.challenger.id, "Fine", 3)
                        challenger_cats = await get_user_cats(guild.id, self.challenger.id) or []
                        await interaction.channel.send(f"No cats found for {self.challenger.mention}. Try running `/syncats` to sync your cat instances, or catch some cats first. Created 3 starter Fine cats.")
                    except Exception:
                        await interaction.channel.send(f"{self.challenger.mention} has no cats to fight with and could not be given starters.")
                        self.stop()
                        return
                if not opponent_cats:
                    # create 3 starter Fine cats for opponent
                    try:
                        await _create_instances_only(guild.id, self.opponent.id, "Fine", 3)
                        opponent_cats = await get_user_cats(guild.id, self.opponent.id) or []
                        await interaction.channel.send(f"No cats found for {self.opponent.mention}. Try running `/syncats` to sync your cat instances, or catch some cats first. Created 3 starter Fine cats.")
                    except Exception:
                        await interaction.channel.send(f"{self.opponent.mention} has no cats to fight with and could not be given starters.")
                        self.stop()
                        return


                # Select top 3 cats from ENTIRE inventory by score (dmg*2 + hp)
                def _score_cat(c):
                    try:
                        return int(c.get("dmg", 0)) * 2 + int(c.get("hp", 0))
                    except Exception:
                        return 0

                # Use custom deck if available, otherwise auto-select from entire inventory
                challenger_deck_ids = get_user_deck(guild.id, self.challenger.id)
                if challenger_deck_ids:
                    challenger_team = [dict(c) for c in challenger_cats if c.get('id') in challenger_deck_ids][:3]
                    if len(challenger_team) < 3:
                        # Fill remaining slots from entire inventory
                        remaining = [dict(c) for c in sorted(challenger_cats, key=_score_cat, reverse=True) if c.get('id') not in challenger_deck_ids]
                        challenger_team.extend(remaining[:3-len(challenger_team)])
                else:
                    # Auto-select best 3 from ENTIRE inventory
                    challenger_team = [dict(x) for x in sorted(challenger_cats, key=_score_cat, reverse=True)[:3]]

                opponent_deck_ids = get_user_deck(guild.id, self.opponent.id)
                if opponent_deck_ids:
                    opponent_team = [dict(c) for c in opponent_cats if c.get('id') in opponent_deck_ids][:3]
                    if len(opponent_team) < 3:
                        # Fill remaining slots from entire inventory
                        remaining = [dict(c) for c in sorted(opponent_cats, key=_score_cat, reverse=True) if c.get('id') not in opponent_deck_ids]
                        opponent_team.extend(remaining[:3-len(opponent_team)])
                else:
                    # Auto-select best 3 from ENTIRE inventory
                    opponent_team = [dict(x) for x in sorted(opponent_cats, key=_score_cat, reverse=True)[:3]]

                # Build a very small in-memory session object supporting teams of 3
                class SimpleFightSession:
                    def __init__(self, channel, challenger, opponent, challenger_team, opponent_team, first_member):
                        self.channel = channel
                        self.challenger = challenger
                        self.opponent = opponent
                        self.challenger_team = challenger_team
                        self.opponent_team = opponent_team
                        # active indices within team
                        self.active_idx = {challenger.id: 0, opponent.id: 0}
                        self.turn = first_member.id
                        self.round = 1
                        # power stored per cat id (allows per-cat power)
                        self.power_by_cat = {}
                        # Track who has moved this round for auto-advance
                        self.moved_this_round = set()
                        # Store last action for display
                        self.last_action = None
                        # message will hold the embed message
                        self.message = None

                first = random.choice([self.challenger, self.opponent])
                sess = SimpleFightSession(interaction.channel, self.challenger, self.opponent, challenger_team, opponent_team, first)

                # store session by channel id
                FIGHT_SESSIONS[interaction.channel.id] = sess

                # helper to render the embed for the match
                def render_fight_embed(s: SimpleFightSession) -> discord.Embed:
                    title = f"{s.challenger.display_name} vs {s.opponent.display_name}"
                    desc_lines = [f"**Round {s.round}** — Turn: **{s.challenger.display_name if s.turn == s.challenger.id else s.opponent.display_name}**"]
                    
                    # Add last action if any
                    if hasattr(s, 'last_action') and s.last_action:
                        desc_lines.append(f"\n💥 {s.last_action}")
                    
                    desc = "\n".join(desc_lines)
                    embed = discord.Embed(title=title, description=desc, color=0x6E593C)
                    
                    try:
                        # challenger active cat
                        cidx = s.active_idx[s.challenger.id]
                        a = s.challenger_team[cidx]
                        aid = a.get('id')
                        atype = a.get('type')
                        apower = s.power_by_cat.get(aid, 0)
                        
                        # Get weakness info
                        astats = CAT_BATTLE_STATS.get(atype, {})
                        aweak = astats.get('weakness', 'None')
                        
                        cat_info = f"**{atype} Cat**\nHP: {a.get('hp')}\nDMG: {a.get('dmg')}\nPower: {apower}\n⚠️ Weak to: {aweak}"
                        embed.add_field(name=f"{s.challenger.display_name} — {a.get('name')}", value=cat_info, inline=True)

                        # opponent active cat
                        oidx = s.active_idx[s.opponent.id]
                        b = s.opponent_team[oidx]
                        bid = b.get('id')
                        btype = b.get('type')
                        bpower = s.power_by_cat.get(bid, 0)
                        
                        # Get weakness info
                        bstats = CAT_BATTLE_STATS.get(btype, {})
                        bweak = bstats.get('weakness', 'None')
                        
                        cat_info2 = f"**{btype} Cat**\nHP: {b.get('hp')}\nDMG: {b.get('dmg')}\nPower: {bpower}\n⚠️ Weak to: {bweak}"
                        embed.add_field(name=f"{s.opponent.display_name} — {b.get('name')}", value=cat_info2, inline=True)
                    except Exception:
                        pass
                    return embed

                # View with 'Next Round' to charge power once per round and 'Surrender'
                class BattleControlView(View):
                    def __init__(self, session: SimpleFightSession):
                        super().__init__(timeout=None)
                        self.session = session
                        self.update_buttons()
                    
                    def update_buttons(self):
                        """Enable/disable buttons based on whose turn it is"""
                        s = self.session
                        # Disable all buttons if it's the bot's turn
                        is_bot_turn = (s.turn == bot.user.id)
                        for item in self.children:
                            if hasattr(item, 'disabled'):
                                item.disabled = is_bot_turn
                    
                    @discord.ui.button(label="Attack", style=discord.ButtonStyle.primary)
                    async def attack(self, it: discord.Interaction, btn: discord.ui.Button):
                        s = self.session
                        # only the current turn player may attack
                        if it.user.id != s.turn:
                            await it.response.send_message("It's not your turn.", ephemeral=True)
                            return

                        # resolve active cat for this user
                        try:
                            if it.user.id == s.challenger.id:
                                active = s.challenger_team[s.active_idx[s.challenger.id]]
                            else:
                                active = s.opponent_team[s.active_idx[s.opponent.id]]
                        except Exception:
                            await it.response.send_message("Internal error: active cat not found.", ephemeral=True)
                            return

                        cat_id = active.get('id')
                        cat_type = active.get('type')
                        current_power = s.power_by_cat.get(cat_id, 0)

                        # Get abilities from CAT_BATTLE_STATS
                        stats = CAT_BATTLE_STATS.get(cat_type)
                        if not stats or "abilities" not in stats:
                            await it.response.send_message("This cat has no abilities defined.", ephemeral=True)
                            return
                        
                        abilities = stats["abilities"]
                        
                        # Build select options based on available power
                        options = []
                        for idx, ability in enumerate(abilities):
                            cost = ability["power_cost"]
                            name = ability["name"]
                            mult = ability["damage_mult"]
                            flip_req = ability.get("requires_flip", False)
                            
                            # Check if player has enough power
                            can_use = (cost <= current_power)
                            
                            # Build description
                            desc = f"{mult}x damage"
                            if flip_req:
                                desc += " (coin flip required)"
                            if not can_use:
                                desc += f" - NEED {cost} POWER"
                            
                            label = f"{name} (Cost: {cost})"
                            options.append(
                                discord.SelectOption(
                                    label=label,
                                    value=str(idx),
                                    description=desc[:100],  # Discord limit
                                    default=False
                                )
                            )
                        
                        if not options:
                            await it.response.send_message("No abilities available.", ephemeral=True)
                            return

                        class AttackSelect(discord.ui.Select):
                            def __init__(self, options, session: SimpleFightSession, actor_id: int, parent_view):
                                super().__init__(placeholder="Choose attack", min_values=1, max_values=1, options=options)
                                self.session = session
                                self.actor_id = actor_id
                                self.parent_view = parent_view

                            async def callback(self, interaction2: discord.Interaction):
                                s2 = self.session
                                try:
                                    print(f"[DEBUG] AttackSelect.callback invoked by {interaction2.user.id} (turn={getattr(s2,'turn',None)})")
                                except Exception:
                                    pass
                                ability_idx = int(self.values[0])
                                
                                # determine attacker/defender
                                attacker_id = self.actor_id
                                defender_id = s2.opponent.id if attacker_id == s2.challenger.id else s2.challenger.id

                                if attacker_id == s2.challenger.id:
                                    atk_cat = s2.challenger_team[s2.active_idx[s2.challenger.id]]
                                    def_cat = s2.opponent_team[s2.active_idx[s2.opponent.id]]
                                else:
                                    atk_cat = s2.opponent_team[s2.active_idx[s2.opponent.id]]
                                    def_cat = s2.challenger_team[s2.active_idx[s2.challenger.id]]

                                aid = atk_cat.get('id')
                                did = def_cat.get('id')
                                atk_type = atk_cat.get('type')
                                def_type = def_cat.get('type')

                                # Get ability from CAT_BATTLE_STATS
                                atk_stats = CAT_BATTLE_STATS.get(atk_type, {})
                                abilities = atk_stats.get("abilities", [])
                                
                                if ability_idx >= len(abilities):
                                    await interaction2.response.send_message("Invalid ability selected.", ephemeral=True)
                                    return
                                
                                ability = abilities[ability_idx]
                                ability_name = ability["name"]
                                cost = ability["power_cost"]
                                damage_mult = ability["damage_mult"]
                                requires_flip = ability.get("requires_flip", False)

                                # check power
                                avail = s2.power_by_cat.get(aid, 0)
                                if avail < cost:
                                    await interaction2.response.send_message("Not enough power for that ability.", ephemeral=True)
                                    return

                                # consume power
                                if cost > 0:
                                    s2.power_by_cat[aid] = max(0, avail - cost)

                                # Coin flip check
                                flip_success = True
                                if requires_flip:
                                    flip_success = random.choice([True, False])
                                
                                if not flip_success:
                                    # Failed coin flip - missed attack
                                    s2.last_action = f"{interaction2.user.display_name}'s {atk_cat.get('name')} tried to use {ability_name} but missed! (coin flip failed)"
                                    s2.last_hp_change = None
                                    try:
                                        if s2.message:
                                            await s2.message.edit(embed=render_fight_embed(s2), view=self.parent_view)
                                    except Exception:
                                        pass
                                    try:
                                        await interaction2.response.edit_message(content="Attack missed!", view=None)
                                    except Exception:
                                        try:
                                            await interaction2.followup.send("Attack missed!", ephemeral=True)
                                        except Exception:
                                            pass
                                    return

                                # Calculate damage
                                base_dmg = int(atk_cat.get('dmg') or 1)
                                dmg = int(base_dmg * damage_mult)
                                
                                # Check weakness (+25% damage)
                                def_stats = CAT_BATTLE_STATS.get(def_type, {})
                                weakness = def_stats.get("weakness")
                                weakness_triggered = (weakness == atk_type)
                                
                                if weakness_triggered:
                                    dmg = int(dmg * 1.25)
                                
                                # apply damage
                                try:
                                    old_hp = int(def_cat.get('hp') or 0)
                                except Exception:
                                    old_hp = 0
                                try:
                                    new_hp = max(0, old_hp - dmg)
                                    def_cat['hp'] = new_hp
                                except Exception:
                                    new_hp = 0
                                    def_cat['hp'] = 0

                                # set last action and hp change
                                try:
                                    action_text = f"{interaction2.user.display_name}'s {atk_cat.get('name')} used {ability_name} for {dmg} damage!"
                                    if weakness_triggered:
                                        action_text += " ⚠️ WEAKNESS HIT!"
                                    s2.last_action = action_text
                                    s2.last_hp_change = (def_cat.get('id'), old_hp, new_hp, dmg)
                                    if s2.message:
                                        await s2.message.edit(embed=render_fight_embed(s2), view=self.parent_view)
                                except Exception:
                                    pass

                                # acknowledge interaction and remove the dropdown
                                try:
                                    await interaction2.response.edit_message(content="Ability used.", view=None)
                                except Exception:
                                    try:
                                        await interaction2.followup.send("Ability used.", ephemeral=True)
                                    except Exception:
                                        pass

                                # check faint
                                if def_cat.get('hp', 0) <= 0:
                                    try:
                                        s2.last_action = f"{interaction2.user.display_name}'s {atk_cat.get('name')} used an attack for {dmg} damage! {def_cat.get('name')} fainted!"
                                        s2.last_hp_change = (def_cat.get('id'), old_hp, new_hp, dmg)
                                        if s2.message:
                                            await s2.message.edit(embed=render_fight_embed(s2), view=self.parent_view)
                                    except Exception:
                                        pass
                                    # advance defender active idx
                                    s2.active_idx[defender_id] += 1
                                    # check if defender has remaining cats
                                    team = s2.opponent_team if defender_id == s2.opponent.id else s2.challenger_team
                                    if s2.active_idx[defender_id] >= len(team):
                                        # attacker wins
                                        try:
                                            s2.last_action = f"{interaction2.user.display_name} wins the fight!"
                                            if s2.message:
                                                winner_embed = discord.Embed(
                                                    title="🏆 Battle Finished!",
                                                    description=f"**{interaction2.user.display_name}** wins the fight!",
                                                    color=0xFFD700
                                                )
                                                await s2.message.edit(content=None, embed=winner_embed, view=None)
                                        except Exception:
                                            pass
                                        try:
                                            if s2.channel.id in FIGHT_SESSIONS:
                                                del FIGHT_SESSIONS[s2.channel.id]
                                        except Exception:
                                            pass
                                        return
                                    return
                                
                                # Mark that this player has moved
                                s2.moved_this_round.add(attacker_id)
                                
                                # Check if both players have moved this round
                                if len(s2.moved_this_round) >= 2:
                                    # Auto-advance to next round
                                    s2.round += 1
                                    s2.moved_this_round.clear()
                                    
                                    # Charge power +1 for both active cats
                                    try:
                                        cidx = s2.active_idx[s2.challenger.id]
                                        caid = s2.challenger_team[cidx].get('id')
                                        s2.power_by_cat[caid] = s2.power_by_cat.get(caid, 0) + 1
                                    except Exception:
                                        pass
                                    try:
                                        oidx = s2.active_idx[s2.opponent.id]
                                        obid = s2.opponent_team[oidx].get('id')
                                        s2.power_by_cat[obid] = s2.power_by_cat.get(obid, 0) + 1
                                    except Exception:
                                        pass
                                    
                                    s2.last_action = f"🔄 Round {s2.round} — Both players charged +1 power!"
                                
                                # end turn: switch to defender
                                s2.turn = defender_id
                                # update buttons for new turn
                                if hasattr(self.parent_view, 'update_buttons'):
                                    self.parent_view.update_buttons()
                                # update embed with new turn and disabled buttons
                                try:
                                    new_emb = render_fight_embed(s2)
                                    await s2.message.edit(embed=new_emb, view=self.parent_view)
                                except Exception:
                                    pass

                                # if defender is the bot, have it take an automatic attack
                                if defender_id == bot.user.id:
                                    async def bot_attack_task():
                                        await asyncio.sleep(1.5)
                                        try:
                                            # Bot AI with abilities
                                            bd = def_cat
                                            bid = did
                                            bd_type = bd.get('type')
                                            atk_type = atk_cat.get('type')
                                            bpower = s2.power_by_cat.get(bid, 0)
                                            target_hp = atk_cat.get('hp', 0)
                                            bot_dmg = bd.get('dmg', 1)
                                            
                                            # Get bot's abilities
                                            bd_stats = CAT_BATTLE_STATS.get(bd_type, {})
                                            abilities = bd_stats.get("abilities", [])
                                            
                                            if not abilities:
                                                return
                                            
                                            # Check weakness
                                            atk_stats = CAT_BATTLE_STATS.get(atk_type, {})
                                            atk_weakness = atk_stats.get("weakness")
                                            has_advantage = (atk_weakness == bd_type)
                                            weakness_mult = 1.25 if has_advantage else 1.0
                                            
                                            # Find best ability
                                            affordable = []
                                            for idx, ability in enumerate(abilities):
                                                cost = ability["power_cost"]
                                                if cost <= bpower and not ability.get("requires_flip", False):
                                                    dmg_est = int(bot_dmg * ability["damage_mult"] * weakness_mult)
                                                    affordable.append({
                                                        "idx": idx,
                                                        "cost": cost,
                                                        "name": ability["name"],
                                                        "dmg": dmg_est,
                                                        "can_ko": dmg_est >= target_hp
                                                    })
                                            
                                            if not affordable:
                                                affordable = [{
                                                    "idx": 0,
                                                    "cost": abilities[0]["power_cost"],
                                                    "name": abilities[0]["name"],
                                                    "dmg": int(bot_dmg * abilities[0]["damage_mult"] * weakness_mult),
                                                    "can_ko": False
                                                }]
                                            
                                            # Choose smartly
                                            ko_opts = [ab for ab in affordable if ab["can_ko"]]
                                            if ko_opts:
                                                chosen = min(ko_opts, key=lambda x: x["cost"])
                                            else:
                                                chosen = max(affordable, key=lambda x: x["dmg"])

                                            # Execute bot attack
                                            finished = await bot_perform_attack(s2, defender_id, bd, attacker_id, atk_cat, chosen["idx"], chosen["name"], bot.user.display_name)
                                            if finished:
                                                return

                                            # after bot attack, return turn to player
                                            s2.turn = attacker_id
                                            # Update buttons for player's turn
                                            if hasattr(self.parent_view, 'update_buttons'):
                                                self.parent_view.update_buttons()
                                            try:
                                                new_emb2 = render_fight_embed(s2)
                                                await s2.message.edit(embed=new_emb2, view=self.parent_view)
                                            except Exception:
                                                pass
                                        except Exception:
                                            pass

                                    asyncio.create_task(bot_attack_task())

                        view = discord.ui.View()
                        view.add_item(AttackSelect(options=options, session=s, actor_id=it.user.id, parent_view=self))
                        try:
                            await it.response.send_message("Choose your attack:", view=view, ephemeral=True)
                        except Exception:
                            try:
                                await it.followup.send("Choose your attack:", view=view, ephemeral=True)
                            except Exception:
                                pass

                    @discord.ui.button(label="Switch Cat", style=discord.ButtonStyle.secondary)
                    async def switch_cat(self, it: discord.Interaction, btn: discord.ui.Button):
                        s = self.session
                        if it.user.id != s.turn:
                            await it.response.send_message("It's not your turn.", ephemeral=True)
                            return
                        
                        team = s.challenger_team if it.user.id == s.challenger.id else s.opponent_team
                        current_idx = s.active_idx[it.user.id]
                        available = [(idx, cat) for idx, cat in enumerate(team) if idx != current_idx and cat.get('hp', 0) > 0]
                        
                        if not available:
                            await it.response.send_message("No other cats available!", ephemeral=True)
                            return
                        
                        options = [discord.SelectOption(label=f"{c.get('name')} ({c.get('type')})", value=str(i), description=f"HP: {c.get('hp')}, DMG: {c.get('dmg')}") for i, c in available]
                        
                        class SwitchSelect(discord.ui.Select):
                            def __init__(self, opts, sess, pid, pview):
                                super().__init__(placeholder="Choose cat", options=opts)
                                self.sess, self.pid, self.pview = sess, pid, pview
                            
                            async def callback(self, inter):
                                self.sess.active_idx[self.pid] = int(self.values[0])
                                new_cat = (self.sess.challenger_team if self.pid == self.sess.challenger.id else self.sess.opponent_team)[int(self.values[0])]
                                self.sess.last_action = f"{inter.user.display_name} switched to {new_cat.get('name')}!"
                                self.sess.moved_this_round.add(self.pid)
                                
                                if len(self.sess.moved_this_round) >= 2:
                                    self.sess.round += 1
                                    self.sess.moved_this_round.clear()
                                    for uid in [self.sess.challenger.id, self.sess.opponent.id]:
                                        idx = self.sess.active_idx[uid]
                                        cid = (self.sess.challenger_team if uid == self.sess.challenger.id else self.sess.opponent_team)[idx].get('id')
                                        self.sess.power_by_cat[cid] = self.sess.power_by_cat.get(cid, 0) + 1
                                    self.sess.last_action += f"\n🔄 Round {self.sess.round} — Both charged +1 power!"
                                
                                self.sess.turn = self.sess.opponent.id if self.pid == self.sess.challenger.id else self.sess.challenger.id
                                if hasattr(self.pview, 'update_buttons'):
                                    self.pview.update_buttons()
                                try:
                                    await inter.response.edit_message(content="Switched!", view=None)
                                except:
                                    pass
                                try:
                                    await self.sess.message.edit(embed=render_fight_embed(self.sess), view=self.pview)
                                except:
                                    pass
                        
                        v = discord.ui.View()
                        v.add_item(SwitchSelect(options, s, it.user.id, self))
                        try:
                            await it.response.send_message("Choose cat:", view=v, ephemeral=True)
                        except:
                            pass

                    @discord.ui.button(label="Surrender", style=discord.ButtonStyle.danger)
                    async def surrender(self, it: discord.Interaction, btn: discord.ui.Button):
                        s = self.session
                        if it.user.id not in (s.challenger.id, s.opponent.id):
                            await it.response.send_message("You're not part of this fight.", ephemeral=True)
                            return
                        other = s.opponent if it.user.id == s.challenger.id else s.challenger
                        text = f"{it.user.display_name} surrendered. {other.display_name} wins!"
                        try:
                            s.last_action = text
                            if s.message:
                                await s.message.edit(embed=discord.Embed(title="Cat Battle", description=text), view=None)
                        except Exception:
                            pass
                        # cleanup
                        try:
                            if s.channel.id in FIGHT_SESSIONS:
                                del FIGHT_SESSIONS[s.channel.id]
                        except Exception:
                            pass
                        try:
                            await it.response.defer()
                        except Exception:
                            pass

                view2 = BattleControlView(sess)
                emb = render_fight_embed(sess)
                # send embed to channel and store message
                sent = await interaction.channel.send(embed=emb, view=view2)
                sess.message = sent
                # If it's bot's turn at start, trigger bot action
                if sess.turn == bot.user.id:
                    async def bot_first_turn():
                        await asyncio.sleep(2)
                        try:
                            # Get bot's active cat and opponent
                            bot_idx = sess.active_idx[bot.user.id]
                            if bot.user.id == sess.challenger.id:
                                bot_cat = sess.challenger_team[bot_idx]
                                enemy_cat = sess.opponent_team[sess.active_idx[sess.opponent.id]]
                                enemy_id = sess.opponent.id
                            else:
                                bot_cat = sess.opponent_team[bot_idx]
                                enemy_cat = sess.challenger_team[sess.active_idx[sess.challenger.id]]
                                enemy_id = sess.challenger.id
                            
                            bid = bot_cat.get('id')
                            bpower = sess.power_by_cat.get(bid, 0)
                            # First turn usually has no power, so light attack
                            choice, extra = 0, 1
                            
                            finished = await bot_perform_attack(sess, bot.user.id, bot_cat, enemy_id, enemy_cat, choice, extra, bot.user.display_name)
                            if not finished:
                                sess.turn = enemy_id
                                view2.update_buttons()
                                new_emb = render_fight_embed(sess)
                                await sess.message.edit(embed=new_emb, view=view2)
                        except Exception:
                            pass
                    asyncio.create_task(bot_first_turn())
            except Exception:
                await interaction.channel.send("Failed to start fight due to an internal error.")
            self.stop()

        @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
        async def decline(self, btn_inter: discord.Interaction, button: discord.ui.Button):
            if btn_inter.user.id != self.opponent.id:
                await btn_inter.response.send_message("Only the challenged player can decline.", ephemeral=True)
                return
            await btn_inter.response.send_message("Challenge declined.", ephemeral=True)
            try:
                await interaction.channel.send(f"{self.opponent.mention} declined the challenge from {self.challenger.mention}.")
            except Exception:
                pass
            self.stop()

        async def on_timeout(self):
            # Called when the view times out (no accept/decline within timeout)
            try:
                # Try to notify in the channel where the original interaction occurred
                # The original `interaction` variable is captured from outer scope; best-effort use.
                try:
                    chan = interaction.channel
                    if chan is not None:
                        await chan.send(f"Challenge between {self.challenger.mention} and {self.opponent.mention} expired (no response).")
                        return
                except Exception:
                    pass

                # Fallback: DM both users that the challenge expired
                try:
                    await self.challenger.send(f"Your challenge to {self.opponent.display_name} expired (no response).")
                except Exception:
                    pass
                try:
                    await self.opponent.send(f"Challenge from {self.challenger.display_name} expired (no response).")
                except Exception:
                    pass
            except Exception:
                pass

    # If challenging the bot itself, auto-accept and do the coin flip immediately
    if opponent.id == bot.user.id:
        # Auto-accept and start a fight session against the bot using the same session flow
        try:
            guild = interaction.guild
            if not guild:
                await interaction.response.send_message("Cannot start fight: guild context missing.", ephemeral=True)
                return

            # Ensure both users have instances
            try:
                await ensure_user_instances(guild.id, executor.id)
                # Update stats for existing cats
                update_cat_stats_from_battle_stats(guild.id, executor.id)
            except Exception:
                pass
            try:
                await ensure_user_instances(guild.id, bot.user.id)
                # Update stats for existing cats
                await update_cat_stats_from_battle_stats(guild.id, bot.user.id)
            except Exception:
                pass

            # Load inventories
            challenger_cats = await get_user_cats(guild.id, executor.id) or []
            bot_cats = await get_user_cats(guild.id, bot.user.id) or []

            # Create starter cats for either side if empty
            if not challenger_cats:
                try:
                    await _create_instances_only(guild.id, executor.id, "Fine", 3)
                    challenger_cats = await get_user_cats(guild.id, executor.id) or []
                except Exception:
                    pass
            if not bot_cats:
                try:
                    await _create_instances_only(guild.id, bot.user.id, "Fine", 3)
                    bot_cats = await get_user_cats(guild.id, bot.user.id) or []
                except Exception:
                    pass

            # Select top 3 teams
            def _score_cat(c):
                try:
                    return int(c.get("dmg", 0)) * 2 + int(c.get("hp", 0))
                except Exception:
                    return 0

            # Use custom deck for challenger if available
            challenger_deck_ids = get_user_deck(guild.id, executor.id)
            if challenger_deck_ids:
                challenger_team = [dict(c) for c in challenger_cats if c.get('id') in challenger_deck_ids][:3]
                if len(challenger_team) < 3:
                    remaining = [dict(c) for c in sorted(challenger_cats, key=_score_cat, reverse=True) if c.get('id') not in challenger_deck_ids]
                    challenger_team.extend(remaining[:3-len(challenger_team)])
            else:
                challenger_team = [dict(x) for x in sorted(challenger_cats, key=_score_cat, reverse=True)[:3]]
            
            opponent_team = [dict(x) for x in sorted(bot_cats, key=_score_cat, reverse=True)[:3]]

            # Instantiate session (reuse SimpleFightSession shape)
            class SimpleFightSessionLocal:
                def __init__(self, channel, challenger, opponent, challenger_team, opponent_team, first_member):
                    self.channel = channel
                    self.challenger = challenger
                    self.opponent = opponent
                    self.challenger_team = challenger_team
                    self.opponent_team = opponent_team
                    self.active_idx = {challenger.id: 0, opponent.id: 0}
                    self.turn = first_member.id
                    self.round = 1
                    self.power_by_cat = {}
                    self.message = None

            first = random.choice([executor, opponent])
            sess = SimpleFightSessionLocal(interaction.channel, executor, opponent, challenger_team, opponent_team, first)
            FIGHT_SESSIONS[interaction.channel.id] = sess

            # render embed (reuse render_fight_embed logic if available, otherwise inline)
            def render_fight_embed_local(s: SimpleFightSessionLocal) -> discord.Embed:
                title = f"{s.challenger.display_name} vs {s.opponent.display_name}"
                desc = f"Round: {s.round} — Turn: {s.challenger.display_name if s.turn == s.challenger.id else s.opponent.display_name}"
                embed = discord.Embed(title=title, description=desc, color=0x6E593C)
                try:
                    cidx = s.active_idx[s.challenger.id]
                    a = s.challenger_team[cidx]
                    aid = a.get('id')
                    apower = s.power_by_cat.get(aid, 0)
                    embed.add_field(name=f"{s.challenger.display_name} — {a.get('name')}", value=f"HP: {a.get('hp')}\nPower: {apower}", inline=True)

                    oidx = s.active_idx[s.opponent.id]
                    b = s.opponent_team[oidx]
                    bid = b.get('id')
                    bpower = s.power_by_cat.get(bid, 0)
                    embed.add_field(name=f"{s.opponent.display_name} — {b.get('name')}", value=f"HP: {b.get('hp')}\nPower: {bpower}", inline=True)
                except Exception:
                    pass
                return embed

            # Create view for bot session with Next Round and Surrender
            class BattleControlViewLocal(View):
                def __init__(self, session):
                    super().__init__(timeout=None)
                    self.session = session
                    self.update_buttons()
                
                def update_buttons(self):
                    """Enable/disable buttons based on whose turn it is"""
                    s = self.session
                    # Disable all buttons if it's the bot's turn
                    is_bot_turn = (s.turn == bot.user.id)
                    for item in self.children:
                        if hasattr(item, 'disabled'):
                            item.disabled = is_bot_turn

                @discord.ui.button(label="Attack", style=discord.ButtonStyle.primary)
                async def attack(self, it: discord.Interaction, btn: discord.ui.Button):
                    s = self.session
                    # only the current turn player may attack
                    if it.user.id != s.turn:
                        await it.response.send_message("It's not your turn.", ephemeral=True)
                        return

                    # resolve active cat for this user
                    try:
                        if it.user.id == s.challenger.id:
                            active = s.challenger_team[s.active_idx[s.challenger.id]]
                        else:
                            active = s.opponent_team[s.active_idx[s.opponent.id]]
                    except Exception:
                        await it.response.send_message("Internal error: active cat not found.", ephemeral=True)
                        return

                    cat_id = active.get('id')
                    cat_type = active.get('type')
                    current_power = s.power_by_cat.get(cat_id, 0)

                    # Get abilities from CAT_BATTLE_STATS
                    stats = CAT_BATTLE_STATS.get(cat_type)
                    if not stats or "abilities" not in stats:
                        await it.response.send_message("This cat has no abilities defined.", ephemeral=True)
                        return
                    
                    abilities = stats["abilities"]
                    
                    # Build select options based on available power
                    options = []
                    for idx, ability in enumerate(abilities):
                        cost = ability["power_cost"]
                        name = ability["name"]
                        mult = ability["damage_mult"]
                        flip_req = ability.get("requires_flip", False)
                        
                        # Check if player has enough power
                        can_use = (cost <= current_power)
                        
                        # Build description
                        desc = f"{mult}x damage"
                        if flip_req:
                            desc += " (coin flip required)"
                        if not can_use:
                            desc += f" - NEED {cost} POWER"
                        
                        label = f"{name} (Cost: {cost})"
                        options.append(
                            discord.SelectOption(
                                label=label,
                                value=str(idx),
                                description=desc[:100],  # Discord limit
                                default=False
                            )
                        )
                    
                    if not options:
                        await it.response.send_message("No abilities available.", ephemeral=True)
                        return

                    class AttackSelectLocal(discord.ui.Select):
                        def __init__(self, options, session, actor_id: int, parent_view):
                            super().__init__(placeholder="Choose attack", min_values=1, max_values=1, options=options)
                            self.session = session
                            self.actor_id = actor_id
                            self.parent_view = parent_view

                        async def callback(self, interaction2: discord.Interaction):
                            s2 = self.session
                            try:
                                print(f"[DEBUG] AttackSelectLocal.callback invoked by {interaction2.user.id} (turn={getattr(s2,'turn',None)})")
                            except Exception:
                                pass
                            ability_idx = int(self.values[0])
                            attacker_id = self.actor_id
                            defender_id = s2.opponent.id if attacker_id == s2.challenger.id else s2.challenger.id

                            if attacker_id == s2.challenger.id:
                                atk_cat = s2.challenger_team[s2.active_idx[s2.challenger.id]]
                                def_cat = s2.opponent_team[s2.active_idx[s2.opponent.id]]
                            else:
                                atk_cat = s2.opponent_team[s2.active_idx[s2.opponent.id]]
                                def_cat = s2.challenger_team[s2.active_idx[s2.challenger.id]]

                            aid = atk_cat.get('id')
                            did = def_cat.get('id')
                            atk_type = atk_cat.get('type')
                            def_type = def_cat.get('type')

                            # Get ability from CAT_BATTLE_STATS
                            atk_stats = CAT_BATTLE_STATS.get(atk_type, {})
                            abilities = atk_stats.get("abilities", [])
                            
                            if ability_idx >= len(abilities):
                                await interaction2.response.send_message("Invalid ability selected.", ephemeral=True)
                                return
                            
                            ability = abilities[ability_idx]
                            ability_name = ability["name"]
                            cost = ability["power_cost"]
                            damage_mult = ability["damage_mult"]
                            requires_flip = ability.get("requires_flip", False)

                            avail = s2.power_by_cat.get(aid, 0)
                            if avail < cost:
                                await interaction2.response.send_message("Not enough power for that ability.", ephemeral=True)
                                return

                            if cost > 0:
                                s2.power_by_cat[aid] = max(0, avail - cost)

                            # Coin flip check
                            flip_success = True
                            if requires_flip:
                                flip_success = random.choice([True, False])
                            
                            if not flip_success:
                                # Failed coin flip
                                s2.last_action = f"{interaction2.user.display_name}'s {atk_cat.get('name')} tried to use {ability_name} but missed! (coin flip failed)"
                                s2.last_hp_change = None
                                try:
                                    if s2.message:
                                        await s2.message.edit(embed=render_fight_embed_local(s2), view=self.parent_view)
                                except Exception:
                                    pass
                                try:
                                    await interaction2.response.send_message("Attack missed!", ephemeral=True)
                                except Exception:
                                    try:
                                        await interaction2.followup.send("Attack missed!", ephemeral=True)
                                    except Exception:
                                        pass
                                return

                            # Calculate damage
                            base_dmg = int(atk_cat.get('dmg') or 1)
                            dmg = int(base_dmg * damage_mult)
                            
                            # Check weakness (+25% damage)
                            def_stats = CAT_BATTLE_STATS.get(def_type, {})
                            weakness = def_stats.get("weakness")
                            weakness_triggered = (weakness == atk_type)
                            
                            if weakness_triggered:
                                dmg = int(dmg * 1.25)

                            try:
                                old_hp = int(def_cat.get('hp', 0) or 0)
                            except Exception:
                                old_hp = 0
                            try:
                                new_hp = max(0, old_hp - dmg)
                                def_cat['hp'] = new_hp
                            except Exception:
                                new_hp = 0
                                def_cat['hp'] = 0

                            # record last action on session and edit the embed instead of sending a normal message
                            try:
                                action_text = f"{interaction2.user.display_name}'s {atk_cat.get('name')} used {ability_name} for {dmg} damage!"
                                if weakness_triggered:
                                    action_text += " ⚠️ WEAKNESS HIT!"
                                s2.last_action = action_text
                                s2.last_hp_change = (def_cat.get('id'), old_hp, new_hp, dmg)
                                if s2.message:
                                    await s2.message.edit(embed=render_fight_embed_local(s2), view=self.parent_view)
                            except Exception:
                                pass

                            # acknowledge interaction privately
                            try:
                                await interaction2.response.send_message("Ability used.", ephemeral=True)
                            except Exception:
                                try:
                                    await interaction2.followup.send("Ability used.", ephemeral=True)
                                except Exception:
                                    pass

                            if def_cat.get('hp', 0) <= 0:
                                # advance defender active idx and update embed; handle win
                                s2.active_idx[defender_id] += 1
                                team = s2.opponent_team if defender_id == s2.opponent.id else s2.challenger_team
                                if s2.active_idx[defender_id] >= len(team):
                                    try:
                                        s2.last_action = f"{interaction2.user.display_name} wins the fight!"
                                        if s2.message:
                                            await s2.message.edit(content="Fight ended.", embed=None, view=None)
                                    except Exception:
                                        pass
                                    try:
                                        if s2.channel.id in FIGHT_SESSIONS:
                                            del FIGHT_SESSIONS[s2.channel.id]
                                    except Exception:
                                        pass
                                    return
                            s2.turn = defender_id
                            # Update buttons for new turn
                            if hasattr(self.parent_view, 'update_buttons'):
                                self.parent_view.update_buttons()
                            try:
                                new_emb = render_fight_embed_local(s2)
                                await s2.message.edit(embed=new_emb, view=self.parent_view)
                            except Exception:
                                pass

                            # if defender is the bot, bot retaliates with smart AI
                            if defender_id == bot.user.id:
                                async def bot_attack_task_local():
                                    await asyncio.sleep(1.5)
                                    try:
                                        bd = def_cat
                                        bid = did
                                        bpower = s2.power_by_cat.get(bid, 0)
                                        target_hp = atk_cat.get('hp', 0)
                                        bot_dmg = bd.get('dmg', 1)
                                        
                                        # Smart AI
                                        if bot_dmg + 1 >= target_hp:
                                            bchoice, bextra = 0, 1
                                        elif bpower >= 2 and bot_dmg + 4 >= target_hp:
                                            bchoice, bextra = 2, 4
                                        elif bpower >= 4 and bot_dmg + 8 >= target_hp:
                                            bchoice, bextra = 4, 8
                                        elif bpower >= 4:
                                            bchoice, bextra = 4, 8
                                        elif bpower >= 2:
                                            bchoice, bextra = 2, 4
                                        else:
                                            bchoice, bextra = 0, 1

                                        finished = await bot_perform_attack(s2, defender_id, bd, attacker_id, atk_cat, bchoice, bextra, bot.user.display_name)
                                        if finished:
                                            return

                                        s2.turn = attacker_id
                                        # Update buttons for player's turn
                                        if hasattr(self.parent_view, 'update_buttons'):
                                            self.parent_view.update_buttons()
                                        try:
                                            new_emb2 = render_fight_embed_local(s2)
                                            await s2.message.edit(embed=new_emb2, view=self.parent_view)
                                        except Exception:
                                            pass
                                    except Exception:
                                        pass

                                asyncio.create_task(bot_attack_task_local())

                    view = discord.ui.View()
                    view.add_item(AttackSelectLocal(options=options, session=s, actor_id=it.user.id, parent_view=self))
                    try:
                        await it.response.send_message("Choose your attack:", view=view, ephemeral=True)
                    except Exception:
                        try:
                            await it.followup.send("Choose your attack:", view=view, ephemeral=True)
                        except Exception:
                            pass

                @discord.ui.button(label="Next Round", style=discord.ButtonStyle.primary)
                async def next_round(self, it: discord.Interaction, btn: discord.ui.Button):
                    s = self.session
                    # only the current turn player may use next round
                    if it.user.id != s.turn:
                        await it.response.send_message("It's not your turn.", ephemeral=True)
                        return
                    s.round += 1
                    try:
                        cidx = s.active_idx[s.challenger.id]
                        aid = s.challenger_team[cidx].get('id')
                        s.power_by_cat[aid] = s.power_by_cat.get(aid, 0) + 1
                    except Exception:
                        pass
                    try:
                        oidx = s.active_idx[s.opponent.id]
                        bid = s.opponent_team[oidx].get('id')
                        s.power_by_cat[bid] = s.power_by_cat.get(bid, 0) + 1
                    except Exception:
                        pass
                    
                    # Update buttons after charging
                    if hasattr(self, 'update_buttons'):
                        self.update_buttons()
                    
                    new_emb = render_fight_embed_local(s)
                    try:
                        await s.message.edit(embed=new_emb, view=self)
                        await it.response.defer()
                    except Exception:
                        try:
                            await it.response.send_message("Failed to update fight state.", ephemeral=True)
                        except Exception:
                            pass
                    
                    # If it's the bot's turn after charging, bot acts with smart AI
                    if s.turn == bot.user.id:
                        async def bot_next_round_task():
                            await asyncio.sleep(2)
                            try:
                                bot_idx = s.active_idx.get(bot.user.id, 0)
                                bot_cat = s.opponent_team[bot_idx]
                                bot_cat_id = bot_cat.get('id')
                                bot_type = bot_cat.get('type')
                                bpower = s.power_by_cat.get(bot_cat_id, 0)
                                
                                player_idx = s.active_idx.get(s.challenger.id, 0)
                                player_cat = s.challenger_team[player_idx]
                                player_type = player_cat.get('type')
                                target_hp = player_cat.get('hp', 0)
                                bot_dmg = bot_cat.get('dmg', 1)
                                
                                # Get bot abilities
                                bot_stats = CAT_BATTLE_STATS.get(bot_type, {})
                                abilities = bot_stats.get("abilities", [])
                                
                                if not abilities:
                                    return
                                
                                # Check weakness
                                player_stats = CAT_BATTLE_STATS.get(player_type, {})
                                player_weakness = player_stats.get("weakness")
                                has_advantage = (player_weakness == bot_type)
                                weakness_mult = 1.25 if has_advantage else 1.0
                                
                                # Find best ability
                                affordable = []
                                for idx, ability in enumerate(abilities):
                                    cost = ability["power_cost"]
                                    if cost <= bpower and not ability.get("requires_flip", False):
                                        dmg_est = int(bot_dmg * ability["damage_mult"] * weakness_mult)
                                        affordable.append({
                                            "idx": idx,
                                            "cost": cost,
                                            "name": ability["name"],
                                            "dmg": dmg_est,
                                            "can_ko": dmg_est >= target_hp
                                        })
                                
                                if not affordable:
                                    affordable = [{
                                        "idx": 0,
                                        "cost": abilities[0]["power_cost"],
                                        "name": abilities[0]["name"],
                                        "dmg": int(bot_dmg * abilities[0]["damage_mult"] * weakness_mult),
                                        "can_ko": False
                                    }]
                                
                                # Choose
                                ko_opts = [ab for ab in affordable if ab["can_ko"]]
                                if ko_opts:
                                    chosen = min(ko_opts, key=lambda x: x["cost"])
                                else:
                                    chosen = max(affordable, key=lambda x: x["dmg"])
                                
                                finished = await bot_perform_attack(s, bot.user.id, bot_cat, s.challenger.id, player_cat, chosen["idx"], chosen["name"], bot.user.display_name)
                                if finished:
                                    return
                                
                                # Return turn to player
                                s.turn = s.challenger.id
                                if hasattr(self, 'update_buttons'):
                                    self.update_buttons()
                                try:
                                    new_emb2 = render_fight_embed_local(s)
                                    await s.message.edit(embed=new_emb2, view=self)
                                except Exception:
                                    pass
                            except Exception:
                                pass
                        
                        asyncio.create_task(bot_next_round_task())
                        pass

                @discord.ui.button(label="Surrender", style=discord.ButtonStyle.danger)
                async def surrender(self, it: discord.Interaction, btn: discord.ui.Button):
                    s = self.session
                    if it.user.id not in (s.challenger.id, s.opponent.id):
                        await it.response.send_message("You're not part of this fight.", ephemeral=True)
                        return
                    other = s.opponent if it.user.id == s.challenger.id else s.challenger
                    text = f"{it.user.display_name} surrendered. {other.display_name} wins!"
                    try:
                        s.last_action = text
                        if s.message:
                            await s.message.edit(embed=discord.Embed(title="Cat Battle", description=text), view=None)
                    except Exception:
                        pass
                    try:
                        if s.channel.id in FIGHT_SESSIONS:
                            del FIGHT_SESSIONS[s.channel.id]
                    except Exception:
                        pass
                    try:
                        await it.response.defer()
                    except Exception:
                        pass

            view2 = BattleControlViewLocal(sess)
            emb = render_fight_embed_local(sess)
            await interaction.response.send_message(f"{opponent.display_name} (the bot) accepted the challenge! Coin flip: {first.display_name} goes first!", embed=emb, view=view2)
            # Fetch the message object to store in session
            try:
                sess.message = await interaction.original_response()
                # schedule bot action if it goes first with smart AI
                if sess.turn == bot.user.id:
                    async def bot_first_turn():
                        await asyncio.sleep(1.5)
                        try:
                            bot_idx = sess.active_idx.get(bot.user.id, 0)
                            bot_cat = sess.opponent_team[bot_idx]
                            bot_type = bot_cat.get('type')
                            player_idx = sess.active_idx.get(sess.challenger.id, 0)
                            player_cat = sess.challenger_team[player_idx]
                            player_type = player_cat.get('type')
                            
                            # Get bot's abilities
                            bot_stats = CAT_BATTLE_STATS.get(bot_type, {})
                            abilities = bot_stats.get("abilities", [])
                            
                            if not abilities:
                                return
                            
                            # At start, bot has no power, use first ability (should be 0 cost)
                            first_ability = abilities[0]
                            finished = await bot_perform_attack(sess, bot.user.id, bot_cat, sess.challenger.id, player_cat, 0, first_ability["name"], bot.user.display_name)
                            if finished:
                                return
                            # Return turn to player
                            sess.turn = sess.challenger.id
                            view2.update_buttons()
                            try:
                                new_emb = render_fight_embed_local(sess)
                                await sess.message.edit(embed=new_emb, view=view2)
                            except Exception:
                                pass
                        except Exception:
                            pass
                    asyncio.create_task(bot_first_turn())
            except Exception:
                sess.message = None
        except Exception:
            try:
                await interaction.response.send_message(f"{opponent.display_name} (the bot) accepted the challenge! Coin flip: {first.display_name} goes first!")
            except Exception:
                try:
                    await interaction.followup.send(f"{opponent.display_name} (the bot) accepted the challenge! Coin flip: {first.display_name} goes first!")
                except Exception:
                    pass
        return

    view = ChallengeView(executor, opponent)
    try:
        await interaction.response.send_message(f"{opponent.mention}, you have been challenged to a cat fight by {executor.mention}!", view=view)
    except Exception:
        # If initial response fails, try followup
        try:
            await interaction.followup.send(f"{opponent.mention}, you have been challenged to a cat fight by {executor.mention}!", view=view)
        except Exception:
            await interaction.response.send_message("Failed to send challenge (maybe DMs or permissions).", ephemeral=True)


# Legacy battles wrapper removed. The `fights` extension registers `/fight` now.


@bot.tree.command(name="battles", description="Battle hub - manage your deck and view battle stats")
async def battles_command(interaction: discord.Interaction):
    """Main battle hub with buttons for all battle-related actions."""
    
    class BattlesHub(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=300)
        
        @discord.ui.button(label="🎴 Manage Deck", style=discord.ButtonStyle.secondary, row=0)
        async def deck_button(self, it: discord.Interaction, btn: discord.ui.Button):
            if it.user.id != interaction.user.id:
                await it.response.send_message("This is not your battles hub.", ephemeral=True)
                return
            
            await it.response.defer(ephemeral=True)
            
            guild_id = interaction.guild.id if interaction.guild else 0
            user_id = it.user.id
            
            # Debug: Check what we have before ensure
            cats_before = await get_user_cats(guild_id, user_id) or []
            print(f"[DECK DEBUG] User {user_id} in guild {guild_id} - Cats before ensure: {len(cats_before)}")
            
            # Ensure user instances are synced from DB
            try:
                await ensure_user_instances(guild_id, user_id)
                print(f"[DECK DEBUG] ensure_user_instances completed")
                # Update stats for existing cats
                await update_cat_stats_from_battle_stats(guild_id, user_id)
                print(f"[DECK DEBUG] update_cat_stats_from_battle_stats completed")
            except Exception as e:
                print(f"[DECK DEBUG] Error ensuring instances: {e}")
                import traceback
                traceback.print_exc()
            
            # Get user's cats
            all_cats = await get_user_cats(guild_id, user_id) or []
            print(f"[DECK DEBUG] User {user_id} - Cats after ensure: {len(all_cats)}")
            
            if not all_cats:
                await it.followup.send("You don't have any cats yet! Catch some cats first.\n\n**Tip:** If you think you should have cats, try running `/syncats` to sync your cat instances.", ephemeral=True)
                return
            
            # Get current deck
            current_deck_ids = get_user_deck(guild_id, user_id)
            
            # Sort by rarity (using type_dict values)
            def _rarity_sort(c):
                cat_type = c.get('type', 'Fine')
                rarity = type_dict.get(cat_type, 100)
                return rarity
            
            sorted_cats = sorted(all_cats, key=_rarity_sort, reverse=True)
            
            # Show deck selector
            class DeckSelector(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=180)
                    self.selected_ids = list(current_deck_ids) if current_deck_ids else []
                    self.page = 0
                    self.filter_type = None
                    self.filter_name = None
                    self.update_buttons()
                
                def get_filtered_cats(self):
                    """Get filtered and paginated cats"""
                    filtered = sorted_cats
                    
                    # Apply type filter
                    if self.filter_type:
                        filtered = [c for c in filtered if c.get('type', '').lower() == self.filter_type.lower()]
                    
                    # Apply name filter
                    if self.filter_name:
                        filtered = [c for c in filtered if self.filter_name.lower() in c.get('name', '').lower()]
                    
                    return filtered
                
                def update_buttons(self):
                    self.clear_items()
                    
                    filtered_cats = self.get_filtered_cats()
                    total_pages = (len(filtered_cats) - 1) // 25 + 1 if filtered_cats else 1
                    start_idx = self.page * 25
                    end_idx = start_idx + 25
                    page_cats = filtered_cats[start_idx:end_idx]
                    
                    # Add filter buttons (row 0)
                    filter_type_btn = discord.ui.Button(
                        label=f"🔍 Filter Type: {self.filter_type or 'All'}", 
                        style=discord.ButtonStyle.secondary, 
                        row=0
                    )
                    filter_type_btn.callback = self.filter_by_type
                    self.add_item(filter_type_btn)
                    
                    filter_name_btn = discord.ui.Button(
                        label=f"🔍 Filter Name: {self.filter_name or 'All'}", 
                        style=discord.ButtonStyle.secondary, 
                        row=0
                    )
                    filter_name_btn.callback = self.filter_by_name
                    self.add_item(filter_name_btn)
                    
                    clear_filter_btn = discord.ui.Button(
                        label="❌ Clear Filters", 
                        style=discord.ButtonStyle.secondary, 
                        row=0,
                        disabled=(not self.filter_type and not self.filter_name)
                    )
                    clear_filter_btn.callback = self.clear_filters
                    self.add_item(clear_filter_btn)
                    
                    # Add cat selection dropdown (row 1)
                    if page_cats:
                        options = []
                        for cat in page_cats:
                            cat_id = cat.get('id')
                            name = cat.get('name', 'Unknown')
                            cat_type = cat.get('type', 'Unknown')
                            hp = cat.get('hp', 0)
                            dmg = cat.get('dmg', 0)
                            
                            # Mark if in deck
                            in_deck = "✓ " if cat_id in self.selected_ids else ""
                            
                            options.append(discord.SelectOption(
                                label=f"{in_deck}{name} ({cat_type})"[:100],
                                description=f"HP: {hp} | DMG: {dmg}"[:100],
                                value=str(cat_id)
                            ))
                        
                        select = discord.ui.Select(
                            placeholder=f"Select cats for your deck ({len(self.selected_ids)}/3) - Page {self.page + 1}/{total_pages}",
                            options=options,
                            max_values=1,
                            row=1
                        )
                        select.callback = self.cat_selected
                        self.add_item(select)
                    
                    # Add pagination buttons (row 2)
                    if self.page > 0:
                        prev_btn = discord.ui.Button(label="◀️ Previous", style=discord.ButtonStyle.primary, row=2)
                        prev_btn.callback = self.prev_page
                        self.add_item(prev_btn)
                    
                    if self.page < total_pages - 1:
                        next_btn = discord.ui.Button(label="Next ▶️", style=discord.ButtonStyle.primary, row=2)
                        next_btn.callback = self.next_page
                        self.add_item(next_btn)
                    
                    page_info_btn = discord.ui.Button(
                        label=f"Page {self.page + 1}/{total_pages} ({len(filtered_cats)} cats)", 
                        style=discord.ButtonStyle.secondary, 
                        row=2,
                        disabled=True
                    )
                    self.add_item(page_info_btn)
                    
                    # Add save/clear/auto buttons (row 3)
                    save_btn = discord.ui.Button(label="💾 Save Deck", style=discord.ButtonStyle.success, row=3)
                    save_btn.callback = self.save_deck
                    self.add_item(save_btn)
                    
                    clear_btn = discord.ui.Button(label="🗑️ Clear Selection", style=discord.ButtonStyle.danger, row=3)
                    clear_btn.callback = self.clear_selection
                    self.add_item(clear_btn)
                    
                    auto_btn = discord.ui.Button(label="⚡ Auto-Select Best", style=discord.ButtonStyle.primary, row=3)
                    auto_btn.callback = self.auto_select
                    self.add_item(auto_btn)
                
                async def filter_by_type(self, btn_it: discord.Interaction):
                    if btn_it.user.id != interaction.user.id:
                        await btn_it.response.send_message("This is not your deck selector.", ephemeral=True)
                        return
                    
                    class TypeFilterModal(discord.ui.Modal, title="Filter by Cat Type"):
                        type_input = discord.ui.TextInput(
                            label="Cat Type (or leave blank for all)",
                            placeholder="e.g., Fire, Water, Divine, Fine...",
                            required=False,
                            max_length=50
                        )
                        
                        async def on_submit(modal_self, modal_it: discord.Interaction):
                            filter_value = str(modal_self.type_input.value).strip()
                            self.filter_type = filter_value if filter_value else None
                            self.page = 0
                            self.update_buttons()
                            
                            deck_cats = [c for c in all_cats if c.get('id') in self.selected_ids]
                            deck_text = "\\n".join([f"• {c.get('name', 'Unknown')} ({c.get('type')}) - HP: {c.get('hp', 0)}, DMG: {c.get('dmg', 0)}" for c in deck_cats])
                            
                            embed = discord.Embed(
                                title="🎴 Deck Configuration",
                                description=f"**Current Selection ({len(self.selected_ids)}/3):**\\n{deck_text if deck_text else '*No cats selected*'}\\n\\n🔍 Filtering by type: {self.filter_type or 'All'}",
                                color=0x3498db
                            )
                            
                            await modal_it.response.edit_message(embed=embed, view=self)
                    
                    await btn_it.response.send_modal(TypeFilterModal())
                
                async def filter_by_name(self, btn_it: discord.Interaction):
                    if btn_it.user.id != interaction.user.id:
                        await btn_it.response.send_message("This is not your deck selector.", ephemeral=True)
                        return
                    
                    class NameFilterModal(discord.ui.Modal, title="Filter by Cat Name"):
                        name_input = discord.ui.TextInput(
                            label="Cat Name (or leave blank for all)",
                            placeholder="Search for cats by name...",
                            required=False,
                            max_length=50
                        )
                        
                        async def on_submit(modal_self, modal_it: discord.Interaction):
                            filter_value = str(modal_self.name_input.value).strip()
                            self.filter_name = filter_value if filter_value else None
                            self.page = 0
                            self.update_buttons()
                            
                            deck_cats = [c for c in all_cats if c.get('id') in self.selected_ids]
                            deck_text = "\\n".join([f"• {c.get('name', 'Unknown')} ({c.get('type')}) - HP: {c.get('hp', 0)}, DMG: {c.get('dmg', 0)}" for c in deck_cats])
                            
                            embed = discord.Embed(
                                title="🎴 Deck Configuration",
                                description=f"**Current Selection ({len(self.selected_ids)}/3):**\\n{deck_text if deck_text else '*No cats selected*'}\\n\\n🔍 Filtering by name: {self.filter_name or 'All'}",
                                color=0x3498db
                            )
                            
                            await modal_it.response.edit_message(embed=embed, view=self)
                    
                    await btn_it.response.send_modal(NameFilterModal())
                
                async def clear_filters(self, btn_it: discord.Interaction):
                    if btn_it.user.id != interaction.user.id:
                        await btn_it.response.send_message("This is not your deck selector.", ephemeral=True)
                        return
                    
                    self.filter_type = None
                    self.filter_name = None
                    self.page = 0
                    self.update_buttons()
                    
                    deck_cats = [c for c in all_cats if c.get('id') in self.selected_ids]
                    deck_text = "\\n".join([f"• {c.get('name', 'Unknown')} ({c.get('type')}) - HP: {c.get('hp', 0)}, DMG: {c.get('dmg', 0)}" for c in deck_cats])
                    
                    embed = discord.Embed(
                        title="🎴 Deck Configuration",
                        description=f"**Current Selection ({len(self.selected_ids)}/3):**\\n{deck_text if deck_text else '*No cats selected*'}",
                        color=0x3498db
                    )
                    
                    await btn_it.response.edit_message(embed=embed, view=self)
                
                async def prev_page(self, btn_it: discord.Interaction):
                    if btn_it.user.id != interaction.user.id:
                        await btn_it.response.send_message("This is not your deck selector.", ephemeral=True)
                        return
                    
                    self.page = max(0, self.page - 1)
                    self.update_buttons()
                    
                    deck_cats = [c for c in all_cats if c.get('id') in self.selected_ids]
                    deck_text = "\\n".join([f"• {c.get('name', 'Unknown')} ({c.get('type')}) - HP: {c.get('hp', 0)}, DMG: {c.get('dmg', 0)}" for c in deck_cats])
                    
                    embed = discord.Embed(
                        title="🎴 Deck Configuration",
                        description=f"**Current Selection ({len(self.selected_ids)}/3):**\\n{deck_text if deck_text else '*No cats selected*'}",
                        color=0x3498db
                    )
                    
                    await btn_it.response.edit_message(embed=embed, view=self)
                
                async def next_page(self, btn_it: discord.Interaction):
                    if btn_it.user.id != interaction.user.id:
                        await btn_it.response.send_message("This is not your deck selector.", ephemeral=True)
                        return
                    
                    filtered_cats = self.get_filtered_cats()
                    total_pages = (len(filtered_cats) - 1) // 25 + 1
                    self.page = min(total_pages - 1, self.page + 1)
                    self.update_buttons()
                    
                    deck_cats = [c for c in all_cats if c.get('id') in self.selected_ids]
                    deck_text = "\\n".join([f"• {c.get('name', 'Unknown')} ({c.get('type')}) - HP: {c.get('hp', 0)}, DMG: {c.get('dmg', 0)}" for c in deck_cats])
                    
                    embed = discord.Embed(
                        title="🎴 Deck Configuration",
                        description=f"**Current Selection ({len(self.selected_ids)}/3):**\\n{deck_text if deck_text else '*No cats selected*'}",
                        color=0x3498db
                    )
                    
                    await btn_it.response.edit_message(embed=embed, view=self)
                
                async def cat_selected(self, select_it: discord.Interaction):
                    if select_it.user.id != interaction.user.id:
                        await select_it.response.send_message("This is not your deck selector.", ephemeral=True)
                        return
                    
                    # Get the selected value from interaction data
                    selected_id = select_it.data['values'][0]
                    
                    if selected_id in self.selected_ids:
                        self.selected_ids.remove(selected_id)
                    elif len(self.selected_ids) < 3:
                        self.selected_ids.append(selected_id)
                    else:
                        await select_it.response.send_message("Your deck is full! Remove a cat first.", ephemeral=True)
                        return
                    
                    self.update_buttons()
                    
                    # Show current deck
                    deck_cats = [c for c in all_cats if c.get('id') in self.selected_ids]
                    deck_text = "\\n".join([f"• {c.get('name', 'Unknown')} ({c.get('type')}) - HP: {c.get('hp', 0)}, DMG: {c.get('dmg', 0)}" for c in deck_cats])
                    
                    filter_info = ""
                    if self.filter_type or self.filter_name:
                        filters = []
                        if self.filter_type:
                            filters.append(f"Type: {self.filter_type}")
                        if self.filter_name:
                            filters.append(f"Name: {self.filter_name}")
                        filter_info = f"\\n\\n🔍 Active filters: {', '.join(filters)}"
                    
                    embed = discord.Embed(
                        title="🎴 Deck Configuration",
                        description=f"**Current Selection ({len(self.selected_ids)}/3):**\\n{deck_text if deck_text else '*No cats selected*'}{filter_info}",
                        color=0x3498db
                    )
                    
                    await select_it.response.edit_message(embed=embed, view=self)
                
                async def save_deck(self, btn_it: discord.Interaction):
                    if btn_it.user.id != interaction.user.id:
                        await btn_it.response.send_message("This is not your deck selector.", ephemeral=True)
                        return
                    
                    if len(self.selected_ids) == 0:
                        await btn_it.response.send_message("Select at least one cat for your deck!", ephemeral=True)
                        return
                    
                    save_user_deck(guild_id, user_id, self.selected_ids)
                    
                    deck_cats = [c for c in all_cats if c.get('id') in self.selected_ids]
                    deck_text = "\\n".join([f"• {c.get('name', 'Unknown')} ({c.get('type')}) - HP: {c.get('hp', 0)}, DMG: {c.get('dmg', 0)}" for c in deck_cats])
                    
                    embed = discord.Embed(
                        title="✅ Deck Saved!",
                        description=f"**Your Battle Deck:**\\n{deck_text}",
                        color=0x2ecc71
                    )
                    
                    await btn_it.response.edit_message(embed=embed, view=None)
                    self.stop()
                
                async def clear_selection(self, btn_it: discord.Interaction):
                    if btn_it.user.id != interaction.user.id:
                        await btn_it.response.send_message("This is not your deck selector.", ephemeral=True)
                        return
                    
                    self.selected_ids = []
                    self.update_buttons()
                    
                    filter_info = ""
                    if self.filter_type or self.filter_name:
                        filters = []
                        if self.filter_type:
                            filters.append(f"Type: {self.filter_type}")
                        if self.filter_name:
                            filters.append(f"Name: {self.filter_name}")
                        filter_info = f"\\n\\n🔍 Active filters: {', '.join(filters)}"
                    
                    embed = discord.Embed(
                        title="🎴 Deck Configuration",
                        description=f"**Current Selection (0/3):**\\n*No cats selected*{filter_info}",
                        color=0x3498db
                    )
                    
                    await btn_it.response.edit_message(embed=embed, view=self)
                
                async def auto_select(self, btn_it: discord.Interaction):
                    if btn_it.user.id != interaction.user.id:
                        await btn_it.response.send_message("This is not your deck selector.", ephemeral=True)
                        return
                    
                    # Auto-select top 3 cats by rarity
                    self.selected_ids = [c.get('id') for c in sorted_cats[:3] if c.get('id')]
                    self.update_buttons()
                    
                    deck_cats = [c for c in all_cats if c.get('id') in self.selected_ids]
                    deck_text = "\\n".join([f"• {c.get('name', 'Unknown')} ({c.get('type')}) - HP: {c.get('hp', 0)}, DMG: {c.get('dmg', 0)}" for c in deck_cats])
                    
                    embed = discord.Embed(
                        title="🎴 Deck Configuration",
                        description=f"**Current Selection ({len(self.selected_ids)}/3):**\\n{deck_text}\\n\\n⚡ Auto-selected top 3 rarest cats!",
                        color=0x3498db
                    )
                    
                    await btn_it.response.edit_message(embed=embed, view=self)
            
            # Show current deck first
            deck_cats = [c for c in all_cats if c.get('id') in current_deck_ids]
            if deck_cats:
                deck_text = "\\n".join([f"• {c.get('name', 'Unknown')} ({c.get('type')}) - HP: {c.get('hp', 0)}, DMG: {c.get('dmg', 0)}" for c in deck_cats])
            else:
                deck_text = "*No deck configured - using auto-select in battles*"
            
            embed = discord.Embed(
                title="🎴 Deck Configuration",
                description=f"**Current Selection ({len(current_deck_ids)}/3):**\\n{deck_text}\\n\\nUse filters and pagination to find your cats!",
                color=0x3498db
            )
            
            view = DeckSelector()
            await it.followup.send(embed=embed, view=view, ephemeral=True)
        
        @discord.ui.button(label="🏆 Tournaments", style=discord.ButtonStyle.secondary, row=0, disabled=True)
        async def tournaments_button(self, it: discord.Interaction, btn: discord.ui.Button):
            if it.user.id != interaction.user.id:
                await it.response.send_message("This is not your battles hub.", ephemeral=True)
                return
            
            await it.response.send_message("Tournaments coming soon! 🎮", ephemeral=True)
        
        @discord.ui.button(label="📊 View Stats", style=discord.ButtonStyle.secondary, row=1)
        async def stats_button(self, it: discord.Interaction, btn: discord.ui.Button):
            if it.user.id != interaction.user.id:
                await it.response.send_message("This is not your battles hub.", ephemeral=True)
                return
            
            await it.response.defer(ephemeral=True)
            
            guild_id = interaction.guild.id if interaction.guild else 0
            user_id = it.user.id
            
            # Ensure user instances are synced from DB to JSON
            try:
                await ensure_user_instances(guild_id, user_id)
                # Update stats for existing cats
                await update_cat_stats_from_battle_stats(guild_id, user_id)
            except Exception as e:
                print(f"Error ensuring instances: {e}")
            
            # Get user's cats and deck
            all_cats = await get_user_cats(guild_id, user_id) or []
            deck_ids = get_user_deck(guild_id, user_id)
            
            # Calculate stats
            total_cats = len(all_cats)
            
            if total_cats == 0:
                await it.followup.send("You don't have any cats yet! If you think you should have cats, try running `/syncats` to sync your cat instances.", ephemeral=True)
                return
            
            def _score_cat(c):
                try:
                    return int(c.get("dmg", 0)) * 2 + int(c.get("hp", 0))
                except Exception:
                    return 0
            
            sorted_cats = sorted(all_cats, key=_score_cat, reverse=True)
            top_3 = sorted_cats[:3]
            
            top_text = "\\n".join([
                f"{i+1}. {c.get('name', 'Unknown')} - HP: {c.get('hp', 0)}, DMG: {c.get('dmg', 0)} (Score: {_score_cat(c)})"
                for i, c in enumerate(top_3)
            ])
            
            deck_cats = [c for c in all_cats if c.get('id') in deck_ids]
            if deck_cats:
                deck_text = "\\n".join([f"• {c.get('name', 'Unknown')} (HP: {c.get('hp', 0)}, DMG: {c.get('dmg', 0)})" for c in deck_cats])
            else:
                deck_text = "*No custom deck - auto-selecting best cats*"
            
            embed = discord.Embed(
                title="📊 Battle Statistics",
                color=0xe74c3c
            )
            embed.add_field(name="Total Cats", value=str(total_cats), inline=True)
            embed.add_field(name="Deck Size", value=f"{len(deck_ids)}/3", inline=True)
            embed.add_field(name="\\u200b", value="\\u200b", inline=True)
            embed.add_field(name="🏆 Top 3 Cats", value=top_text, inline=False)
            embed.add_field(name="🎴 Current Deck", value=deck_text, inline=False)
            
            await it.followup.send(embed=embed, ephemeral=True)
    
    # Create main hub embed
    embed = discord.Embed(
        title="⚔️ Battle Hub",
        description="Welcome to the Battle Hub! Use `/fight @player` to challenge someone to battle.\n\nManage your deck and view stats below:",
        color=0xe67e22
    )
    embed.add_field(
        name="🎴 Manage Deck",
        value="Configure your 3-cat battle deck",
        inline=False
    )
    embed.add_field(
        name="🏆 Tournaments",
        value="View and join tournaments (coming soon)",
        inline=False
    )
    embed.add_field(
        name="📊 View Stats",
        value="Check your battle statistics and top cats",
        inline=False
    )
    
    view = BattlesHub()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@bot.tree.command(name="updatecatstats", description="Update all your cats to use the new battle stat system")
async def update_cat_stats_command(interaction: discord.Interaction):
    """Update all existing cats to use the new CAT_BATTLE_STATS system."""
    await interaction.response.defer(ephemeral=True)
    
    guild_id = interaction.guild.id if interaction.guild else 0
    user_id = interaction.user.id
    
    # Update cat stats
    updated = await update_cat_stats_from_battle_stats(guild_id, user_id)
    
    if updated:
        # Get cat counts by type
        cats = await get_user_cats(guild_id, user_id)
        type_counts = {}
        for cat in cats:
            cat_type = cat.get('type', 'Unknown')
            type_counts[cat_type] = type_counts.get(cat_type, 0) + 1
        
        embed = discord.Embed(
            title="✅ Cat Stats Updated!",
            description=f"All {len(cats)} of your cats have been updated with the new battle stat system.\n\n**Your Cats:**\n" + 
                       "\n".join([f"• {count}x {cat_type}" for cat_type, count in sorted(type_counts.items(), key=lambda x: type_dict.get(x[0], 0), reverse=True)]),
            color=0x2ecc71
        )
        embed.set_footer(text="Your cats now have proper HP, DMG, abilities, and weaknesses!")
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        await interaction.followup.send("You don't have any cats to update! If you think you should have cats, try running `/syncats` to sync your cat instances.", ephemeral=True)


@bot.tree.command(name="syncats", description="Sync your cat instances with database counts (admin/troubleshooting)")
async def sync_cats_command(interaction: discord.Interaction):
    """Manually trigger cat instance sync for your account."""
    await interaction.response.defer(ephemeral=True)
    
    guild_id = interaction.guild.id if interaction.guild else 0
    user_id = interaction.user.id
    
    try:
        # Get profile
        profile = await Profile.get_or_create(guild_id=guild_id, user_id=user_id)
        
        # Run auto-sync
        created = await auto_sync_cat_instances(profile)
        
        # Get current cats
        cats = await get_user_cats(guild_id, user_id)
        
        if created:
            type_counts = {}
            for cat in cats:
                cat_type = cat.get('type', 'Unknown')
                type_counts[cat_type] = type_counts.get(cat_type, 0) + 1
            
            embed = discord.Embed(
                title="✅ Cats Synced!",
                description=f"Your cat instances have been synced with the database.\n\n**Total Cats: {len(cats)}**\n\n**By Type:**\n" + 
                           "\n".join([f"• {count}x {cat_type}" for cat_type, count in sorted(type_counts.items(), key=lambda x: type_dict.get(x[0], 0), reverse=True)]),
                color=0x3498db
            )
            embed.set_footer(text="All missing instances have been created!")
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="✅ Already Synced",
                description=f"Your cats are already in sync! You have {len(cats)} cat instances.\n\n" +
                           "All your database counts match your instance counts.",
                color=0x2ecc71
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error during sync: {e}", ephemeral=True)


async def _start_pvp_challenge(interaction: discord.Interaction, executor: discord.Member, opponent: discord.Member):
    """Start a PvP challenge - reuses ChallengeView from fight command."""
    # Just call the existing fight command logic
    view = ChallengeView(executor, opponent)
    try:
        await interaction.channel.send(f"{opponent.mention}, you have been challenged to a cat fight by {executor.mention}!", view=view)
    except Exception:
        pass


async def _start_bot_fight(interaction: discord.Interaction, executor: discord.Member, opponent: discord.Member):
    """Start a fight against the bot - simplified version."""
    try:
        guild = interaction.guild
        if not guild:
            return

        # Ensure both users have instances
        try:
            await ensure_user_instances(guild.id, executor.id)
        except Exception:
            pass
        try:
            await ensure_user_instances(guild.id, bot.user.id)
        except Exception:
            pass

        # Load inventories
        challenger_cats = await get_user_cats(guild.id, executor.id) or []
        bot_cats = await get_user_cats(guild.id, bot.user.id) or []

        # Create starter cats for either side if empty
        if not challenger_cats:
            try:
                await _create_instances_only(guild.id, executor.id, "Fine", 3)
                challenger_cats = await get_user_cats(guild.id, executor.id) or []
            except Exception:
                pass
        if not bot_cats:
            try:
                await _create_instances_only(guild.id, bot.user.id, "Fine", 3)
                bot_cats = await get_user_cats(guild.id, bot.user.id) or []
            except Exception:
                pass

        # Select teams - use deck if available, otherwise auto-select
        def _score_cat(c):
            try:
                return int(c.get("dmg", 0)) * 2 + int(c.get("hp", 0))
            except Exception:
                return 0

        # Check for custom deck
        user_deck_ids = get_user_deck(guild.id, executor.id)
        if user_deck_ids:
            # Use custom deck
            challenger_team = [dict(c) for c in challenger_cats if c.get('id') in user_deck_ids][:3]
            # If deck has less than available cats, pad with auto-select
            if len(challenger_team) < 3:
                remaining = [dict(c) for c in sorted(challenger_cats, key=_score_cat, reverse=True) if c.get('id') not in user_deck_ids]
                challenger_team.extend(remaining[:3-len(challenger_team)])
        else:
            # Auto-select top 3
            challenger_team = [dict(x) for x in sorted(challenger_cats, key=_score_cat, reverse=True)[:3]]

        opponent_team = [dict(x) for x in sorted(bot_cats, key=_score_cat, reverse=True)[:3]]

        # Use the existing SimpleFightSessionLocal class and flow
        # (This connects to the existing bot fight logic around line 1900)
        first = random.choice([executor, opponent])
        
        class SimpleFightSessionLocal:
            def __init__(self, channel, challenger, opponent, challenger_team, opponent_team, first_member):
                self.channel = channel
                self.challenger = challenger
                self.opponent = opponent
                self.challenger_team = challenger_team
                self.opponent_team = opponent_team
                self.active_idx = {challenger.id: 0, opponent.id: 0}
                self.turn = first_member.id
                self.round = 1
                self.power_by_cat = {}
                self.message = None

        sess = SimpleFightSessionLocal(interaction.channel, executor, opponent, challenger_team, opponent_team, first)
        FIGHT_SESSIONS[interaction.channel.id] = sess

        # Send battle message (reuse existing render and view logic)
        def render_fight_embed_local(s: SimpleFightSessionLocal) -> discord.Embed:
            title = f"{s.challenger.display_name} vs {s.opponent.display_name}"
            desc = f"Round: {s.round} — Turn: {s.challenger.display_name if s.turn == s.challenger.id else s.opponent.display_name}"
            embed = discord.Embed(title=title, description=desc, color=0x6E593C)
            try:
                cidx = s.active_idx[s.challenger.id]
                a = s.challenger_team[cidx]
                aid = a.get('id')
                apower = s.power_by_cat.get(aid, 0)
                embed.add_field(name=f"{s.challenger.display_name} — {a.get('name')}", value=f"HP: {a.get('hp')}\\nPower: {apower}", inline=True)

                oidx = s.active_idx[s.opponent.id]
                b = s.opponent_team[oidx]
                bid = b.get('id')
                bpower = s.power_by_cat.get(bid, 0)
                embed.add_field(name=f"{s.opponent.display_name} — {b.get('name')}", value=f"HP: {b.get('hp')}\\nPower: {bpower}", inline=True)
            except Exception:
                pass
            return embed

        # Use BattleControlViewLocal from existing code
        from copy import copy
        # We'll reuse the existing BattleControlViewLocal, so just send message
        
        await interaction.channel.send(f"{opponent.display_name} (the bot) accepted the challenge! Coin flip: {first.display_name} goes first!")
    except Exception:
        pass


@bot.tree.command(name="debug_battles", description="Debug the Battles cog loading and helpers")
async def debug_battles(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    import importlib, importlib.util, os, traceback, sys

    lines = []
    try:
        initial_keys = list(bot.cogs.keys())
        lines.append(f"Initial cog keys: {initial_keys}")
        lines.append(f"Bot id: {id(bot)}")
    except Exception as e:
        lines.append(f"Error reading initial cogs: {e}")

    # Try normal import
    try:
        mod = importlib.import_module("battles")
        lines.append(f"import battles: OK (module name: {getattr(mod, '__name__', '')})")
        lines.append(f"has setup: {hasattr(mod, 'setup')}, has BattlesCog: {hasattr(mod, 'BattlesCog')}")
    except Exception:
        tb = traceback.format_exc()
        lines.append("import battles: FAILED")
        lines.append(tb[:1900])

    # Try file-based import
    try:
        path = os.path.join(os.path.dirname(__file__), "battles.py")
        if os.path.exists(path):
            spec = importlib.util.spec_from_file_location("battles_file", path)
            modf = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(modf)  # type: ignore
            lines.append(f"file import: OK (path: {path})")
            lines.append(f"has setup: {hasattr(modf, 'setup')}, has BattlesCog: {hasattr(modf, 'BattlesCog')}")
        else:
            lines.append(f"file import: NOT FOUND at {path}")
    except Exception:
        tb = traceback.format_exc()
        lines.append("file import: FAILED")
        lines.append(tb[:1900])

    # Try to call setup() if module available but cog missing
    try:
        before_keys = list(bot.cogs.keys())
        lines.append(f"Cog keys before setup attempts: {before_keys}")
        if not bot.get_cog("BattlesCog"):
            try:
                mod = importlib.import_module("battles")
                if hasattr(mod, "setup"):
                    try:
                        mod.setup(bot)
                        lines.append("Called battles.setup(bot)")
                    except Exception:
                        lines.append("battles.setup(bot) raised:")
                        lines.append(traceback.format_exc()[:1900])
                # try instantiating class if present
                if hasattr(mod, "BattlesCog") and not bot.get_cog("BattlesCog"):
                    try:
                        inst = mod.BattlesCog(bot)
                        added = False
                        try:
                            bot.add_cog(inst)
                            added = True
                        except Exception:
                            lines.append("bot.add_cog raised during dynamic instantiation:")
                            lines.append(traceback.format_exc()[:1900])
                        lines.append(f"Instantiated BattlesCog class: {inst.__class__.__name__}, added={added}")
                        lines.append(f"Inst type id: {id(inst)}, inst qualified name: {getattr(inst, 'qualified_name', getattr(inst, '__class__').__name__)}")
                        lines.append(f"Cog keys after add attempt: {list(bot.cogs.keys())}")
                    except Exception:
                        lines.append("Instantiating or adding BattlesCog failed:")
                        lines.append(traceback.format_exc()[:1900])
            except Exception:
                lines.append("Attempt to call setup/instantiate failed:")
                lines.append(traceback.format_exc()[:1900])
    except Exception:
        lines.append(f"Unexpected error during setup attempts: {traceback.format_exc()[:1900]}")

    # Final status
    try:
        cog = bot.get_cog("BattlesCog")
        lines.append(f"Final cog present: {bool(cog)}")
        lines.append(f"Final cog keys: {list(bot.cogs.keys())}")
    except Exception:
        lines.append(f"Error checking final cog: {traceback.format_exc()[:1900]}")

    out = "\n".join(lines)
    if len(out) > 1900:
        out = out[:1900] + "..."
    msg = "```\n" + out + "\n```"
    await interaction.followup.send(msg, ephemeral=True)
    # If we have recorded add_cog diagnostics, send a short preview of the log.
    try:
        addlog = globals().get("ADD_COG_LOG", None)
        if addlog is None:
            await interaction.followup.send("```\nADD_COG_LOG: <not set>\n```", ephemeral=True)
        else:
            # show at most the last 8 entries, keep message small
            preview = addlog[-8:]
            lines2 = ["ADD_COG_LOG preview:"]
            for e in preview:
                try:
                    lines2.append(str(e))
                except Exception:
                    lines2.append(repr(e))
            text2 = "\n".join(lines2)
            if len(text2) > 1800:
                text2 = text2[:1800] + "..."
            await interaction.followup.send("```\n" + text2 + "\n```", ephemeral=True)
    except Exception:
        pass
    # --- Additional runtime sanity checks: try adding a temporary TestCog ---
    more = []
    try:
        import inspect

        more.append(f"bot repr: {repr(bot)}")
        more.append(f"bot class: {bot.__class__}, id: {id(bot)}")
        add_cog_fn = getattr(bot, "add_cog", None)
        if add_cog_fn is None:
            more.append("bot.add_cog: MISSING")
        else:
            try:
                more.append(f"bot.add_cog is bound method: {hasattr(add_cog_fn, '__self__')}, self id: {getattr(add_cog_fn, '__self__', None)}")
            except Exception:
                more.append(f"bot.add_cog repr: {repr(add_cog_fn)}")

        class TestCog(commands.Cog):
            pass

        test_inst = TestCog()
        try:
            bot.add_cog(test_inst)
            more.append("Called bot.add_cog(TestCog instance)")
        except Exception as e:
            more.append(f"bot.add_cog raised: {e}")

        try:
            more.append(f"After add, cog keys: {list(bot.cogs.keys())}")
            more.append(f"bot.__dict__ keys: {list(bot.__dict__.keys())}")
            more.append(f"has _cogs attr: {hasattr(bot, '_cogs')}")
            c = getattr(bot, '_cogs', None)
            try:
                more.append(f"_cogs type: {type(c)}, repr: {repr(c)[:200]}")
            except Exception:
                more.append(f"_cogs type: {type(c)}")
            try:
                more.append(f"len(_cogs): {len(c) if c is not None else 'N/A'}")
            except Exception:
                pass
            try:
                func = getattr(bot.add_cog, '__func__', None)
                more.append(f"add_cog __func__ module: {getattr(func, '__module__', None)}, qualname: {getattr(func, '__qualname__', None)}")
            except Exception:
                pass
        except Exception as e:
            more.append(f"Reading bot.cogs failed: {e}")

        # cleanup if it registered
        try:
            if bot.get_cog("TestCog"):
                bot.remove_cog("TestCog")
                more.append("Removed TestCog after check")
        except Exception:
            pass
    except Exception:
        more.append(f"Runtime sanity checks failed: {traceback.format_exc()[:1900]}")

    if more:
        full = "\n".join(more)
        if len(full) > 1900:
            full = full[:1900] + "..."
        await interaction.followup.send("```\n" + full + "\n```", ephemeral=True)


async def start_internal_server(port: int = 3002):
    """Start a small internal aiohttp server on localhost that accepts POST /vote

    This endpoint is intended to be called by the external vote webhook server which
    forwards Top.gg votes. The handler schedules `reward_vote` on the bot loop and logs.
    """
    print(f"[VOTE SERVER] start_internal_server called with port {port}", flush=True)
    try:
        print(f"[VOTE SERVER] Creating web.Application...", flush=True)
        app = web.Application()

        async def _handle(request):
            try:
                data = await request.json()
                print(f"[VOTE] Received payload: {data}", flush=True)
                user_id = int(data.get("user") or data.get("user_id") or 0)
            except Exception as e:
                print(f"[VOTE ERROR] Failed to parse JSON: {e}", flush=True)
                return web.json_response({"error": "invalid payload", "details": str(e)}, status=400)

            if not user_id:
                print(f"[VOTE ERROR] No user_id in payload: {data}", flush=True)
                return web.json_response({"error": "missing user", "payload": data}, status=400)

            try:
                # schedule reward and log
                print(f"[VOTE] ✅ Vote received from user {user_id}", flush=True)
                print(f"[VOTE] Scheduling reward_vote() task...", flush=True)
                bot.loop.create_task(reward_vote(user_id))
                print(f"[VOTE] Task scheduled, will process rewards across all servers", flush=True)
            except Exception as e:
                print(f"[VOTE ERROR] Failed to schedule reward_vote for {user_id}: {e}", flush=True)
                logging.exception("Failed to schedule reward_vote for %s", user_id)
                return web.json_response({"status": "error"}, status=500)

            return web.json_response({"status": "success", "user_id": user_id})

        async def _health(request):
            """Health check endpoint to verify server is running"""
            return web.json_response({
                "status": "healthy",
                "service": "KITTAYYYYYYY Internal Vote Receiver",
                "port": port,
                "bot_ready": bot.is_ready() if hasattr(bot, 'is_ready') else False
            })

        # Add both endpoints for compatibility
        print(f"[VOTE SERVER] Adding routes...", flush=True)
        app.router.add_post("/_internal_vote", _handle)  # Old endpoint
        app.router.add_post("/vote", _handle)  # New endpoint for draft webhook
        app.router.add_get("/health", _health)  # Health check

        print(f"[VOTE SERVER] Creating AppRunner...", flush=True)
        runner = web.AppRunner(app)
        await runner.setup()
        print(f"[VOTE SERVER] Creating TCPSite on 127.0.0.1:{port}...", flush=True)
        site = web.TCPSite(runner, "127.0.0.1", port)
        await site.start()
        print(f"[VOTE] ✅ Internal vote receiver listening on 127.0.0.1:{port} [endpoints: /vote, /_internal_vote, /health]", flush=True)
        print(f"[VOTE] Test with: curl http://127.0.0.1:{port}/health", flush=True)
    except Exception as e:
        print(f"[VOTE SERVER ERROR] Failed to start: {type(e).__name__}: {e}", flush=True)
        logging.exception("Failed to start internal vote receiver server")
        import traceback
        traceback.print_exc()


async def start_public_webhook(port: int = 3001, auth: str | None = None):
    """Start a public aiohttp server on 0.0.0.0:port exposing POST /dblwebhook.

    Runs inside the bot event loop so no extra threads or uvicorn are required.
    """
    try:
        app = web.Application()

        async def _handle(request):
            # Basic auth header check
            if auth:
                try:
                    header = request.headers.get("Authorization")
                    if header != auth:
                        return web.json_response({"error": "unauthorized"}, status=401)
                except Exception:
                    return web.json_response({"error": "unauthorized"}, status=401)

            try:
                data = await request.json()
                user_id = int(data.get("user") or data.get("user_id") or 0)
            except Exception:
                return web.json_response({"error": "invalid payload"}, status=400)

            if not user_id:
                return web.json_response({"error": "missing user"}, status=400)

            try:
                try:
                    print(f"vote received from {user_id}, granting rewards..", flush=True)
                except Exception:
                    logging.info("vote received from %s, granting rewards..", user_id)

                # schedule reward_vote on the bot loop
                asyncio.create_task(reward_vote(user_id))
            except Exception:
                logging.exception("Failed to schedule reward_vote for %s", user_id)
                return web.json_response({"status": "error"}, status=500)

            return web.json_response({"status": "ok"})

        app.router.add_post("/dblwebhook", _handle)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        try:
            print(f"Public webhook listening on 0.0.0.0:{port}", flush=True)
        except Exception:
            logging.info("Public webhook listening on %s:%s", "0.0.0.0", port)
    except Exception:
        logging.exception("Failed to start public webhook server")


async def background_index_all_cats(bot_instance=None):
    """Background task: ensure cat instances are in sync with DB aggregated counters.

    - On first run, checks for cats.json and migrates it to database automatically.
    - For all users in the database, checks if DB cat counts match instance counts.
    - If DB counter > instance count, creates missing instances automatically.
    Runs once on startup (after 10 second delay) and then every 30 minutes.
    """
    import sys
    print("[AUTO-SYNC] Background task FUNCTION CALLED", flush=True, file=sys.stderr)
    print("[AUTO-SYNC] Background task started, waiting for bot to be ready...", flush=True)
    
    # Use the provided bot instance or fall back to the global bot
    target_bot = bot_instance if bot_instance is not None else bot
    
    await target_bot.wait_until_ready()
    print("[AUTO-SYNC] Bot ready, starting in 10 seconds...", flush=True)
    await asyncio.sleep(10)  # delay for DB readiness
    
    run_count = 0
    migrated_from_json = False

    while not target_bot.is_closed():
        try:
            run_count += 1
            
            # On first run, check if cats.json exists and migrate it
            if run_count == 1 and not migrated_from_json:
                cats_json_path = "data/cats.json"
                if os.path.exists(cats_json_path):
                    print(f"[AUTO-SYNC] Found cats.json, migrating to database...", flush=True)
                    try:
                        with open(cats_json_path, "r", encoding="utf-8") as f:
                            json_data = json.load(f)
                        
                        migrated_users = 0
                        migrated_cats = 0
                        
                        for guild_id_str, users in json_data.items():
                            guild_id = int(guild_id_str)
                            for user_id_str, cats_list in users.items():
                                user_id = int(user_id_str)
                                if cats_list:
                                    try:
                                        profile = await Profile.get_or_create(guild_id=guild_id, user_id=user_id)
                                        profile.cat_instances = json.dumps(cats_list)
                                        await profile.save()
                                        migrated_users += 1
                                        migrated_cats += len(cats_list)
                                    except Exception as e:
                                        print(f"[AUTO-SYNC] Error migrating user {user_id}: {e}", flush=True)
                        
                        # Create backup
                        backup_path = cats_json_path + ".backup"
                        try:
                            with open(backup_path, "w", encoding="utf-8") as f:
                                json.dump(json_data, f, ensure_ascii=False, indent=2)
                            print(f"[AUTO-SYNC] Migration complete! {migrated_users} users, {migrated_cats} cats", flush=True)
                            print(f"[AUTO-SYNC] Backup created at: {backup_path}", flush=True)
                        except Exception as e:
                            print(f"[AUTO-SYNC] Could not create backup: {e}", flush=True)
                        
                        migrated_from_json = True
                    except Exception as e:
                        print(f"[AUTO-SYNC] Error during JSON migration: {e}", flush=True)
                        import traceback
                        traceback.print_exc()
                else:
                    print(f"[AUTO-SYNC] No cats.json found at {cats_json_path}, skipping migration", flush=True)
            
            print(f"[AUTO-SYNC] Starting background cat instance sync (run #{run_count})...", flush=True)
            
            synced_users = 0
            synced_cats = 0
            
            # Get all profiles from database
            try:
                # Query all profiles that have at least one cat
                profiles = await Profile.fetch_all()
                
                for profile in profiles:
                    try:
                        # Auto-sync this user's instances
                        created = await auto_sync_cat_instances(profile)
                        if created:
                            synced_users += 1
                            # Count how many cats were synced
                            cats = await get_user_cats(profile.guild_id, profile.user_id)
                            synced_cats += len(cats)
                    except Exception as e:
                        # per-user failure shouldn't stop whole pass
                        continue
                
                print(f"[AUTO-SYNC] Complete: {synced_users} users synced, ~{synced_cats} total instances", flush=True)
            except Exception as e:
                print(f"[AUTO-SYNC] Error during sync: {e}", flush=True)
            
            # Wait 30 minutes before next run (1800 seconds)
            await asyncio.sleep(1800)
        
        except Exception as e:
            print(f"[AUTO-SYNC] Unexpected error in background task: {e}", flush=True)
            import traceback
            traceback.print_exc()
            # Wait before retrying to avoid spam
            await asyncio.sleep(60)
    
    print("[AUTO-SYNC] Background task ended (bot closed)", flush=True)


async def ensure_user_instances(guild_id: int, user_id: int):
    """Ensure database has at least as many instances as DB aggregated counters.

    If the DB indicates the user should have more instances than stored, create
    missing instances using `_create_instances_only`.
    """
    try:
        import collections

        # Get current instances from database
        user_list = await get_user_cats(guild_id, user_id)
        counter = collections.Counter()
        for c in user_list:
            try:
                t = c.get("type")
                if t:
                    counter[t] += 1
            except Exception:
                continue

        # fetch profile counts
        try:
            profile = await Profile.get_or_create(guild_id=guild_id, user_id=user_id)
            await profile.refresh_from_db()
        except Exception:
            profile = None

        if profile:
            for ct in cattypes:
                try:
                    db_count = int(profile.get(f"cat_{ct}") or 0)
                except Exception:
                    db_count = 0
                inst_count = int(counter.get(ct, 0))
                if db_count > inst_count:
                    missing = db_count - inst_count
                    try:
                        await _create_instances_only(guild_id, user_id, ct, missing)
                    except Exception:
                        pass
    except Exception:
        pass


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

# Track daily streak reminders (resets daily)
daily_reminded = {}

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
    {"title": "BIG APOLOGIES FOR LAST NIGHT!", "emoji": "😭"},
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
    
    # Auto-unlock achievement-based cosmetics
    try:
        unlocked_cosmetics = []
        for category in COSMETICS_DATA.values():
            for cosm_id, cosm_data in category.items():
                if cosm_data.get("requirement") == ach_id:
                    owned = get_owned_cosmetics(profile)
                    if cosm_id not in owned:
                        add_owned_cosmetic(profile, cosm_id)
                        unlocked_cosmetics.append(cosm_data["name"])
        
        if unlocked_cosmetics:
            await profile.save()
    except Exception:
        pass  # Don't let cosmetic unlock fail achievement grant
    
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
        # Map the old 'vote' quest type to the new 'third' quest config.
        if quest_type == "vote":
            quest_choices = list(battle.get("quests", {}).get("third", {}).keys())
        else:
            quest_choices = list(battle["quests"][quest_type].keys())
        if not quest_choices:
            # No available quests for this type; bail out to avoid infinite loop.
            return
        quest = random.choice(quest_choices)
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

    # The public 'vote' quest has been removed from config; map internal 'vote'
    # generation to the new 'third' quest configuration so DB fields can remain.
    if quest_type == "vote":
        quest_data = battle.get("quests", {}).get("third", {}).get(quest)
    else:
        quest_data = battle["quests"][quest_type][quest]

    if quest_type == "vote":
        user.vote_reward = random.randint(quest_data["xp_min"] // 10, quest_data["xp_max"] // 10) * 10
        user.vote_cooldown = 0
    elif quest_type == "extra":
        # persistent extra quest fields
        user.extra_reward = random.randint(quest_data.get("xp_min", 100) // 10, quest_data.get("xp_max", 200) // 10) * 10
        user.extra_quest = quest
        user.extra_cooldown = 0
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
    if 12 * 3600 < (getattr(user, 'extra_cooldown', 1) or 1) + 12 * 3600 < time.time():
        await generate_quest(user, "extra")


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
        # Map internal 'vote' progression to the new 'third' quest config.
        quest_data = battle.get("quests", {}).get("third", {}).get(quest)
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
    elif getattr(user, "extra_quest", "") == quest:
        if getattr(user, "extra_cooldown", 1) != 0:
            return
        quest_data = battle.get("quests", {}).get("extra", {}).get(quest)
        if not quest_data:
            return
        user.extra_progress = (user.extra_progress or 0) + 1
        if user.extra_progress >= quest_data.get("progress", 1):
            quest_complete = True
            user.extra_cooldown = int(time.time())
            current_xp = user.progress + (user.extra_reward or 0)
            user.extra_progress = 0
            user.reminder_extra = 1
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

    title = quest_data["title"]

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
        cats = await get_user_cats(profile.guild_id, profile.user_id)
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
        # count all instances of this type in database (including favourites/on_adventure)
        inst_total = sum(1 for c in cats if c.get("type") == cat_type)
        if db_total > inst_total:
            missing = db_total - inst_total
            # safeguard: don't create absurd amounts in one go
            if missing > 0 and missing <= 1000:
                try:
                    await _create_instances_only(profile.guild_id, profile.user_id, cat_type, missing)
                    # reload cats and recompute nonfav
                    cats = await get_user_cats(profile.guild_id, profile.user_id)
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
    # We removed Top.gg vote reminders; handle guild-scoped reminders only.
    if "_" in reminder_type:
        guild_id = reminder_type.split("_")[1]
        user = await Profile.get_or_create(guild_id=int(guild_id), user_id=interaction.user.id)
        if reminder_type.startswith("catch"):
            user.reminder_catch = int(time.time()) + 30 * 60
        else:
            user.reminder_misc = int(time.time()) + 30 * 60
        await user.save()
    # For other (removed) reminder types, acknowledge without DB changes.
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
                        user_cats = await get_user_cats(guild_id, user_id)
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
                                # Auto-sync instances if counter was incremented
                                await auto_sync_cat_instances(profile, rare_cat)
                            except Exception:
                                pass
                        # restore the adventuring instance if present
                        if inst:
                            try:
                                inst["on_adventure"] = False
                                await save_user_cats(guild_id, user_id, user_cats)
                            except Exception:
                                pass
                        else:
                            try:
                                profile[f"cat_{cat_sent}"] += 1
                                await profile.save()
                                # Auto-sync instances if counter was incremented
                                await auto_sync_cat_instances(profile, cat_sent)
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
                                # Auto-sync instances if counter was incremented
                                await auto_sync_cat_instances(profile, cat_type)
                            except Exception:
                                pass
                        # restore the adventuring instance if present
                        if inst:
                            try:
                                inst["on_adventure"] = False
                                await save_user_cats(guild_id, user_id, user_cats)
                            except Exception:
                                pass
                        else:
                            try:
                                profile[f"cat_{cat_sent}"] += 1
                                await profile.save()
                                # Auto-sync instances if counter was incremented
                                await auto_sync_cat_instances(profile, cat_sent)
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
                                await save_user_cats(guild_id, user_id, user_cats)
                            except Exception:
                                pass
                        else:
                            try:
                                profile[f"cat_{cat_sent}"] += 1
                                await profile.save()
                                # Auto-sync instances if counter was incremented
                                await auto_sync_cat_instances(profile, cat_sent)
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
                            await save_user_cats(guild_id, user_id, user_cats)
                        except Exception:
                            pass
                    else:
                        try:
                            profile[f"cat_{cat_sent}"] += 1
                            await profile.save()
                            # Auto-sync instances if counter was incremented
                            await auto_sync_cat_instances(profile, cat_sent)
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
                        await save_user_cats(guild_id, user_id, user_cats)
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

    # Vote (Top.gg) reminders and related flows were removed because external voting
    # delivery is unreliable. No action here — catch/misc/guild reminders continue below.

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
    
    # Note: background_index_all_cats is started in setup() function, not here

async def schedule_daily_rain():
    """Daily random rain task - picks a random channel and starts a 5-minute rain once per day."""
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
            channels = await Channel.collect(filter="cat_rains = 0")
            if not channels:
                continue
                
            channel_data = random.choice(channels)
            discord_channel = bot.get_channel(channel_data.channel_id)
            if not discord_channel:
                continue
            
            # Start a 5-minute rain using the proper rain system
            await give_rain(discord_channel, 5)
            
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
        await interaction.followup.send("You don't have any cats to send on an adventure. Get some cats first!\n\n**Tip:** If you think you should have cats, try running `/syncats` to sync your cat instances.")
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
        user_cats = await get_user_cats(interaction.guild.id, user_id)
        for c in user_cats:
            if c.get("type") == chosen and not c.get("on_adventure"):
                c["on_adventure"] = True
                instance_id = c.get("id")
                break
        if instance_id:
            await save_user_cats(interaction.guild.id, user_id, user_cats)
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
    try:
        profile = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=user_id)
        try:
            await progress(interaction, profile, "adventure")
        except Exception:
            pass
    except Exception:
        pass



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
            # Check if we've already sent the achievement message
            dm_user = await User.get_or_create(user_id=message.author.id)
            if not dm_user.dm_ach_sent:
                dm_user.dm_ach_sent = 1
                await dm_user.save()
                await message.channel.send('good job! please send "lol_i_have_dmed_the_cat_bot_and_got_an_ach" in server to get your ach!')
            else:
                # Use OpenAI chatbot for conversation
                await handle_dm_chat(message)
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
                
                # Auto-sync cat instances immediately after catch
                try:
                    await auto_sync_cat_instances(user, le_emoji)
                except Exception as e:
                    print(f"[AUTO-SYNC] Failed to sync after catch: {e}", flush=True)

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

                # Check if user needs daily streak reminder (after first catch of the day)
                try:
                    await check_daily_reminder_after_catch(message.author, message.guild, message.channel)
                except Exception:
                    pass  # Don't let this break catching

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
                # Extra quest: catch a Water or better cat
                try:
                    if le_emoji in cattypes:
                        water_idx = cattypes.index("Water") if "Water" in cattypes else None
                        if water_idx is not None and cattypes.index(le_emoji) >= water_idx:
                            try:
                                await progress(message, user, "catch_water")
                            except Exception:
                                pass
                except Exception:
                    pass
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
            value="KITTAYYYYYYY has extra fun commands which you will discover along the way.\nAnything unclear? Check out [our wiki](https://wiki.minkos.lol) or drop us a line at our [Discord server](https://discord.gg/staring).\n\n**Need help?** Use `/support` for assistance!",
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
                    is_owner_only = False
                    try:
                        if "admin" in desc.lower() or desc.strip().upper().startswith("(ADMIN)"):
                            is_admin = True
                        # Skip owner-only commands
                        if name in ["admin", "servers", "adventure_list", "debug_battles"]:
                            is_owner_only = True
                            continue
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
                if any(k in key for k in ["shop", "pack", "kibble", "buy", "sell", "rain", "battlepass", "pack", "daily", "trade"]):
                    return "Economy"
                if any(k in key for k in ["cat", "cats", "play", "catch", "inventory", "rename", "catalogue", "catpedia", "purr", "breed", "battle", "fight", "adventure"]):
                    return "Cats"
                if any(k in key for k in ["slot", "slots", "pig", "tictactoe", "tiktok", "8ball", "news", "wiki", "credits", "cookie"]):
                    return "Fun"
                if any(k in key for k in ["slot", "casino", "gamble", "bet", "pig"]):
                    return "Gambling"
                if any(k in key for k in ["help", "info", "stats", "getid", "last", "catpedia", "wiki", "news", "profile", "cosmetics", "mystyle", "suggestion"]):
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


@bot.tree.command(description="Get support and help with KITTAYYYYYYY")
async def support(message: discord.Interaction):
    """Provides support links - adapts based on whether used in the official server or externally"""
    SUPPORT_SERVER_ID = 861745089525055508
    SUPPORT_FORUM_CHANNEL_ID = "1182425780488151090"  # Forum channel ID
    
    is_support_server = message.guild and message.guild.id == SUPPORT_SERVER_ID
    
    embed = discord.Embed(
        title="🆘 KITTAYYYYYYY Support",
        color=Colors.brown
    )
    
    if is_support_server:
        # User is in the official support server
        embed.description = (
            "Welcome to the KITTAYYYYYYY support server!\n\n"
            f"📋 **Get Help:** Visit <#1182425780488151090> to create a support thread\n"
            "💬 Ask your questions and our team will assist you!\n\n"
            "📚 **Also check out:**\n"
            "• [KITTAYYYYYYY Wiki](https://wiki.minkos.lol) for guides and info\n"
            "• `/help` command for basic instructions"
        )
    else:
        # User is in an external server
        embed.description = (
            "Need help with KITTAYYYYYYY?\n\n"
            "🔗 **Join our Discord server for support:**\n"
            "https://discord.gg/Zx6em4AEq2\n\n"
            "Once there, visit **#‼️kittay-support‼️** to create a support thread!\n\n"
            "📚 **Also check out:**\n"
            "• [KITTAYYYYYYY Wiki](https://wiki.minkos.lol) for guides and info\n"
            "• `/help` command for basic instructions"
        )
    
    embed.set_thumbnail(url="https://wsrv.nl/?url=raw.githubusercontent.com/milenakos/cat-bot/main/images/cat.png")
    embed.set_footer(text="We're here to help!")
    
    await message.response.send_message(embed=embed)


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
    # Restore full news articles. These bodies preserve the original long-form content.
    news_list = [
        {
            "title": "NEW CATS, KIBBLE, AND.. ITEMS???",
            "emoji": "🐾",
            "desc": "New cat types and Kibble currency",
            "body": (
                "We've added 7 new cat types and a new currency called KIBBLE.\n"
                "Kibble can be earned from activities and spent on new items — check /shop to see what's available.\n"
                "More content is incoming; stay tuned!"
            ),
            "reward": {
                "type": "kibble",  # Can be: "kibble", "pack", "cat", "xp", "rain"
                "amount": 500,
                "name": "500 Kibble"
            }
        },
        {
            "title": "BIG APOLOGIES FOR LAST NIGHT",
            "emoji": "😭",
            "desc": "kittay had an oopsie!",
            "body": (
                "so yeah.. the bot kinda exploded yesterday.. oopsa!\n"
                "it was the internet service provider's fault, mb. but do not worry! I have used my magic (waiting patiently) to fix it!\n"
                "also, voting should work now (/vote), it gives xp and sometimes a pack WOOHOOO\n"
                "as a sorry, you can claim a gold pack from this message. thanks for being patient with me!"
                "**Filler <3**"
            ),
            "reward": {
                "type": "pack",
                "amount": 1,
                "pack_name": "Gold",  # Used when type is "pack"
                "name": "1 Gold Pack"
            }
        },
    ]

    class NewsView(View):
        def __init__(self):
            super().__init__(timeout=300)
            options = [
                discord.SelectOption(label=f"{a['emoji']} {a['title']}", value=str(i), description=a['desc'])
                for i, a in enumerate(news_list)
            ]
            self.select = discord.ui.Select(placeholder="Choose an article", min_values=1, max_values=1, options=options)
            self.select.callback = self.on_select
            self.add_item(self.select)
            self.current_article_idx = None

        async def on_select(self, interaction2: discord.Interaction):
            idx = int(self.select.values[0])
            self.current_article_idx = idx
            art = news_list[idx]
            
            # Build embed
            embed = discord.Embed(title=f"{art['emoji']} {art['title']}", description=art['body'], color=Colors.brown)
            embed.set_footer(text=f"Article {idx + 1}/{len(news_list)}")
            
            # Check if article has a reward
            if art.get("reward"):
                reward = art["reward"]
                # Check if user already claimed this reward
                reward_key = f"news_{idx}"
                profile = await Profile.get_or_create(guild_id=interaction2.guild.id, user_id=interaction2.user.id)
                try:
                    claimed_rewards = profile.claimed_news_rewards
                    claimed_list = json.loads(claimed_rewards) if isinstance(claimed_rewards, str) else (claimed_rewards or [])
                except (AttributeError, KeyError):
                    claimed_list = []
                
                if reward_key in claimed_list:
                    embed.add_field(name="📦 Reward", value=f"~~{reward['name']}~~ (Already claimed)", inline=False)
                else:
                    embed.add_field(name="📦 Reward", value=f"**{reward['name']}** - Click button below to claim!", inline=False)
            
            # Create new view with claim button if reward exists and not claimed
            new_view = NewsView()
            new_view.current_article_idx = idx
            if art.get("reward"):
                reward_key = f"news_{idx}"
                profile = await Profile.get_or_create(guild_id=interaction2.guild.id, user_id=interaction2.user.id)
                try:
                    claimed_rewards = profile.claimed_news_rewards
                    claimed_list = json.loads(claimed_rewards) if isinstance(claimed_rewards, str) else (claimed_rewards or [])
                except (AttributeError, KeyError):
                    claimed_list = []
                
                if reward_key not in claimed_list:
                    # Add claim button
                    claim_btn = discord.ui.Button(label=f"Claim {art['reward']['name']}", style=discord.ButtonStyle.green, emoji="🎁")
                    
                    async def claim_callback(btn_interaction: discord.Interaction):
                        await self.claim_reward(btn_interaction, idx)
                    
                    claim_btn.callback = claim_callback
                    new_view.add_item(claim_btn)
            
            try:
                await interaction2.response.edit_message(embed=embed, view=new_view)
            except Exception:
                try:
                    await interaction2.followup.send(embed=embed, view=new_view, ephemeral=True)
                except Exception:
                    pass
        
        async def claim_reward(self, interaction: discord.Interaction, article_idx: int):
            """Handle reward claiming for a news article"""
            art = news_list[article_idx]
            reward = art.get("reward")
            
            if not reward:
                await interaction.response.send_message("❌ This article has no reward!", ephemeral=True)
                return
            
            # Check if already claimed
            reward_key = f"news_{article_idx}"
            profile = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)
            try:
                claimed_rewards = profile.claimed_news_rewards
                claimed_list = json.loads(claimed_rewards) if isinstance(claimed_rewards, str) else (claimed_rewards or [])
            except (AttributeError, KeyError):
                claimed_list = []
            
            if reward_key in claimed_list:
                await interaction.response.send_message("❌ You've already claimed this reward!", ephemeral=True)
                return
            
            # Give the reward
            reward_text = ""
            try:
                if reward["type"] == "kibble":
                    profile.kibble = (profile.kibble or 0) + reward["amount"]
                    reward_text = f"🪙 {reward['amount']} Kibble"
                elif reward["type"] == "pack":
                    pack_name = reward.get("pack_name", "Wooden").lower()
                    profile[f"pack_{pack_name}"] += reward["amount"]
                    reward_text = f"📦 {reward['amount']}x {reward.get('pack_name', 'Wooden')} Pack"
                elif reward["type"] == "cat":
                    cat_type = reward.get("cat_type", "Fine")
                    profile[f"cat_{cat_type}"] += reward["amount"]
                    await auto_sync_cat_instances(profile, cat_type)
                    reward_text = f"🐱 {reward['amount']}x {cat_type} Cat"
                elif reward["type"] == "xp":
                    profile.progress = (profile.progress or 0) + reward["amount"]
                    reward_text = f"✨ {reward['amount']} Battlepass XP"
                elif reward["type"] == "rain":
                    profile.rain_minutes = (profile.rain_minutes or 0) + reward["amount"]
                    reward_text = f"🌧️ {reward['amount']} Rain Minutes"
                
                # Mark as claimed
                claimed_list.append(reward_key)
                profile.claimed_news_rewards = json.dumps(claimed_list)
                await profile.save()
                
                # Send success message
                embed = discord.Embed(
                    title="🎁 Reward Claimed!",
                    description=f"You received: **{reward_text}**",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
                # Update the original message to show reward is claimed
                art = news_list[article_idx]
                main_embed = discord.Embed(title=f"{art['emoji']} {art['title']}", description=art['body'], color=Colors.brown)
                main_embed.set_footer(text=f"Article {article_idx + 1}/{len(news_list)}")
                main_embed.add_field(name="📦 Reward", value=f"~~{reward['name']}~~ (Claimed by you!)", inline=False)
                
                # Remove claim button
                new_view = NewsView()
                new_view.current_article_idx = article_idx
                try:
                    await interaction.message.edit(embed=main_embed, view=new_view)
                except:
                    pass
                
            except Exception as e:
                await interaction.response.send_message(f"❌ Failed to give reward: {e}", ephemeral=True)
                logging.exception("Failed to give news reward")

    embed = discord.Embed(title="KITTAYYYYYYY Times", description="Choose an article from the dropdown below.", color=Colors.brown)
    view = NewsView()
    await message.response.send_message(embed=embed, view=view)
    try:
        await achemb(message, "news", "send")
    except Exception:
        pass


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
        elif action == "Start Rain":
            self.add_item(discord.ui.TextInput(label="Channel ID", placeholder="Channel ID to start rain in"))
            self.add_item(discord.ui.TextInput(label="Duration (minutes)", placeholder="Duration in minutes (default 10)"))
        elif action == "Give Kibbles":
            self.add_item(discord.ui.TextInput(label="Username", placeholder="Username, ID, or nickname"))
            self.add_item(discord.ui.TextInput(label="Amount", placeholder="Amount of kibbles to give"))
        elif action == "Test Adventure":
            self.add_item(discord.ui.TextInput(label="Test Type", placeholder="Type 'instant' to complete an adventure", value="instant"))
            
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

        # Search by username and display name (case-insensitive)
        name_lower = name.lower()
        for member in self.guild.members:
            # Check exact matches first (case-insensitive)
            if name_lower in [member.name.lower(), member.display_name.lower(), str(member).lower()]:
                print(f"[DEBUG] Found user by exact name match: {member}")
                return member
        
        # Then check partial matches
        for member in self.guild.members:
            if name_lower in member.name.lower() or name_lower in member.display_name.lower() or name_lower in str(member).lower():
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
        
        elif self.action == "Start Rain":
            try:
                channel_id = int(self.children[0].value.strip())
                duration_minutes = int(self.children[1].value.strip()) if len(self.children) > 1 and self.children[1].value.strip() else 10
                duration_seconds = duration_minutes * 60
                
                channel = bot.get_channel(channel_id)
                if not channel:
                    await interaction.response.send_message(f"Could not find channel with ID {channel_id}!", ephemeral=True)
                    return
                
                # Start the rain
                await give_rain(channel, duration_seconds)
                await interaction.response.send_message(f"✅ Started a {duration_minutes} minute cat rain in {channel.mention}!", ephemeral=True)
            except ValueError:
                await interaction.response.send_message("Invalid channel ID or duration!", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"Error starting rain: {str(e)}", ephemeral=True)
        
        elif self.action == "Give Kibbles":
            member = await self.find_member(self.children[0].value)
            if not member:
                await interaction.response.send_message(f"Couldn't find user '{self.children[0].value}'!", ephemeral=True)
                return
            
            try:
                amount = int(self.children[1].value)
                user = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=member.id)
                user.kibble = (user.kibble or 0) + amount
                await user.save()
                await interaction.response.send_message(f"✅ Gave {amount:,} 🍖 Kibbles to {member.mention}!", ephemeral=True)
            except ValueError:
                await interaction.response.send_message("Invalid kibble amount!", ephemeral=True)
        
        elif self.action == "Test Adventure":
            # Give instant adventure rewards to the owner for testing
            try:
                user = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)
                
                # Give test rewards
                test_kibbles = 1000
                test_packs = 3
                
                user.kibble = (user.kibble or 0) + test_kibbles
                user.pack_silver = (user.pack_silver or 0) + test_packs
                await user.save()
                
                await interaction.response.send_message(
                    f"✅ **Adventure Test Complete!**\n"
                    f"Rewards given:\n"
                    f"🍖 {test_kibbles:,} Kibbles\n"
                    f"📦 {test_packs} Silver Packs\n\n"
                    f"Use this to verify adventure rewards are working correctly!",
                    ephemeral=True
                )
            except Exception as e:
                await interaction.response.send_message(f"Error testing adventure: {str(e)}", ephemeral=True)

class AdminPanel(discord.ui.View):
    def __init__(self, guild: discord.Guild):
        super().__init__()
        self.guild = guild
        
    @discord.ui.button(label="Give Cats", style=ButtonStyle.blurple, row=0)
    async def give_cats(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AdminPanelModal("Give Cats", self.guild))
        
    @discord.ui.button(label="Give Rains", style=ButtonStyle.blurple, row=0)
    async def give_rain(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AdminPanelModal("Give Rains", interaction.guild))
        
    @discord.ui.button(label="Give XP", style=ButtonStyle.blurple, row=0)
    async def give_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AdminPanelModal("Give XP", interaction.guild))
        
    @discord.ui.button(label="Give Packs", style=ButtonStyle.blurple, row=0)
    async def give_packs(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AdminPanelModal("Give Packs", interaction.guild))
    
    @discord.ui.button(label="Give Kibbles", style=ButtonStyle.blurple, row=1)
    async def give_kibbles(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AdminPanelModal("Give Kibbles", interaction.guild))
        
    @discord.ui.button(label="Start Rain", style=ButtonStyle.green, row=1)
    async def start_rain(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AdminPanelModal("Start Rain", interaction.guild))
    
    @discord.ui.button(label="Test Adventure", style=ButtonStyle.green, row=1)
    async def test_adventure(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AdminPanelModal("Test Adventure", interaction.guild))
        
    @discord.ui.button(label="Speak", style=ButtonStyle.green, row=2)
    async def speak(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AdminPanelModal("Speak", interaction.guild))
        
    @discord.ui.button(label="Start Giveaway", style=ButtonStyle.green, row=2)
    async def start_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AdminPanelModal("Start Giveaway", interaction.guild))

@bot.tree.command(description="Open the admin control panel")
async def admin(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
        return
        
    embed = discord.Embed(
        title="🔧 Admin Control Panel",
        description="Use the buttons below to manage KITTAYYYYYYY:",
        color=Colors.brown
    )
    await interaction.response.send_message(embed=embed, view=AdminPanel(guild=interaction.guild), ephemeral=True)

@bot.tree.command(description="Submit a suggestion to the bot owner")
@discord.app_commands.describe(suggestion="Your suggestion for the bot")
async def suggestion(interaction: discord.Interaction, suggestion: str):
    """Send a suggestion to the bot owner"""
    await interaction.response.defer(ephemeral=True)
    
    # Create suggestion embed
    embed = discord.Embed(
        title="💡 New Suggestion",
        description=suggestion,
        color=Colors.brown,
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_author(name=f"{interaction.user} ({interaction.user.id})", icon_url=interaction.user.display_avatar.url)
    embed.add_field(name="Server", value=f"{interaction.guild.name} ({interaction.guild.id})", inline=False)
    
    # Try to send to owner's DM first
    try:
        owner = await bot.fetch_user(OWNER_ID)
        await owner.send(embed=embed)
        sent_to = "DM"
    except Exception:
        # Fallback to log channel if DM fails
        try:
            if config.BACKUP_ID:
                log_channel = bot.get_channel(config.BACKUP_ID)
                if log_channel:
                    await log_channel.send(embed=embed)
                    sent_to = "log channel"
                else:
                    await interaction.followup.send("Failed to send suggestion - contact the bot owner directly.", ephemeral=True)
                    return
            else:
                await interaction.followup.send("Failed to send suggestion - contact the bot owner directly.", ephemeral=True)
                return
        except Exception:
            await interaction.followup.send("Failed to send suggestion - contact the bot owner directly.", ephemeral=True)
            return
    
    await interaction.followup.send(f"✅ Your suggestion has been sent to the bot owner via {sent_to}! Thank you for your feedback.", ephemeral=True)

# Admin subcommands (owner-only)
@bot.tree.command(description="(OWNER) Start a cat rain in a channel")
@discord.app_commands.describe(channel_id="Channel ID to start rain in", duration="Duration in minutes (default 10)")
async def rainstart(interaction: discord.Interaction, channel_id: str, duration: int = 10):
    """Start a cat rain in specified channel"""
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
        return
    
    try:
        ch_id = int(channel_id)
        channel = bot.get_channel(ch_id)
        if not channel:
            await interaction.response.send_message(f"Could not find channel with ID {ch_id}!", ephemeral=True)
            return
        
        duration_seconds = duration * 60
        await give_rain(channel, duration_seconds)
        await interaction.response.send_message(f"✅ Started a {duration} minute cat rain in {channel.mention}!", ephemeral=True)
    except ValueError:
        await interaction.response.send_message("Invalid channel ID!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Error starting rain: {str(e)}", ephemeral=True)

@bot.tree.command(description="(OWNER) Give kibbles to a user")
@discord.app_commands.describe(user="User to give kibbles to", amount="Amount of kibbles to give")
async def givekibbles(interaction: discord.Interaction, user: discord.User, amount: int):
    """Give kibbles to a user"""
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
        return
    
    try:
        profile = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=user.id)
        profile.kibble = (profile.kibble or 0) + amount
        await profile.save()
        await interaction.response.send_message(f"✅ Gave {amount:,} 🍖 Kibbles to {user.mention}!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Error giving kibbles: {str(e)}", ephemeral=True)

@bot.tree.command(description="(OWNER) Test adventure rewards")
async def adventuretest(interaction: discord.Interaction):
    """Give instant adventure rewards for testing"""
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
        return
    
    try:
        user = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)
        
        # Give test rewards
        test_kibbles = 1000
        test_packs = 3
        
        user.kibble = (user.kibble or 0) + test_kibbles
        user.pack_silver = (user.pack_silver or 0) + test_packs
        await user.save()
        
        await interaction.response.send_message(
            f"✅ **Adventure Test Complete!**\n"
            f"Rewards given:\n"
            f"🍖 {test_kibbles:,} Kibbles\n"
            f"📦 {test_packs} Silver Packs\n\n"
            f"Use this to verify adventure rewards are working correctly!",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(f"Error testing adventure: {str(e)}", ephemeral=True)

@bot.tree.command(description="List all servers the bot is in")
async def servers(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
        return
    
    guilds = sorted(bot.guilds, key=lambda g: g.member_count, reverse=True)
    
    # Create pages of 10 servers each
    pages = []
    for i in range(0, len(guilds), 10):
        chunk = guilds[i:i+10]
        embed = discord.Embed(
            title=f"📊 Server List ({len(guilds)} total)",
            description=f"Page {i//10 + 1}/{(len(guilds)-1)//10 + 1}",
            color=Colors.brown
        )
        
        for guild in chunk:
            embed.add_field(
                name=f"{guild.name}",
                value=f"Members: {guild.member_count:,} | ID: {guild.id}",
                inline=False
            )
        
        pages.append(embed)
    
    if len(pages) == 1:
        await interaction.response.send_message(embed=pages[0], ephemeral=True)
    else:
        # If multiple pages, use a simple view with navigation
        view = ServerListView(pages)
        await interaction.response.send_message(embed=pages[0], view=view, ephemeral=True)

class ServerListView(discord.ui.View):
    def __init__(self, pages):
        super().__init__(timeout=180)
        self.pages = pages
        self.current_page = 0
        self.update_buttons()
    
    def update_buttons(self):
        self.previous_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= len(self.pages) - 1
    
    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.gray)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("This isn't your menu!", ephemeral=True)
            return
        
        self.current_page = max(0, self.current_page - 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.gray)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("This isn't your menu!", ephemeral=True)
            return
        
        self.current_page = min(len(self.pages) - 1, self.current_page + 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

async def check_daily_reminder(interaction: discord.Interaction):
    """Check if user needs daily streak reminder and send it"""
    global daily_reminded
    
    user_id = interaction.user.id
    now = int(time.time())
    
    # Only check once per day per user
    if user_id in daily_reminded:
        last_reminded = daily_reminded[user_id]
        if now - last_reminded < 86400:  # 24 hours
            return
    
    try:
        profile = await Profile.get_or_none(user_id=user_id, guild_id=interaction.guild.id)
        if not profile:
            return
        
        last_claim = profile.last_daily_claim or 0
        time_since_claim = now - last_claim
        
        # Remind if they can claim (>24 hours since last claim)
        if time_since_claim >= 86400:
            try:
                # Mark as reminded
                daily_reminded[user_id] = now
                
                # Send ephemeral reminder
                await interaction.followup.send(
                    "🔔 **Daily Reminder:** Your daily streak is ready to claim! Use `/daily` to collect your rewards.",
                    ephemeral=True
                )
            except Exception:
                pass  # Silently fail if we can't send
    except Exception:
        pass  # Don't let this break commands

async def check_daily_reminder_after_catch(user, guild, channel):
    """Check if user needs daily streak reminder after catching a cat"""
    global daily_reminded
    
    user_id = user.id
    now = int(time.time())
    
    # Only check once per day per user
    if user_id in daily_reminded:
        last_reminded = daily_reminded[user_id]
        if now - last_reminded < 86400:  # 24 hours
            return
    
    try:
        profile = await Profile.get_or_none(user_id=user_id, guild_id=guild.id)
        if not profile:
            return
        
        last_claim = profile.last_daily_claim or 0
        time_since_claim = now - last_claim
        
        # Remind if they can claim (>24 hours since last claim)
        if time_since_claim >= 86400:
            try:
                # Mark as reminded
                daily_reminded[user_id] = now
                
                # Send reminder in channel (not ephemeral since it's from message event)
                await channel.send(
                    f"{user.mention} 🔔 Your daily streak is ready to claim! Use `/daily` to collect your rewards.",
                    delete_after=10
                )
            except Exception:
                pass  # Silently fail if we can't send
    except Exception:
        pass  # Don't let this break catching

async def give_rain(channel, duration):
    # Remember the channel for rain
    channel_data = await Channel.get_or_create(channel_id=channel.id)
    # Set the rain timer (same logic as regular /rain command)
    channel_data.cat_rains = time.time() + (duration * 60)
    channel_data.yet_to_spawn = 0
    await channel_data.save()
    await spawn_cat(str(channel.id))
    # Notify the channel that a rain event has started
    try:
        await channel.send(f"🌧️ A Cat Rain has started in this channel for {duration} minutes, ending <t:{int(channel_data.cat_rains)}:R>!")
    except Exception:
        pass
    # Log to rain channel
    try:
        ch = bot.get_channel(config.RAIN_CHANNEL_ID)
        await ch.send(f"Admin started {duration}m rain in {channel.id} (random rain)")
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


@bot.tree.command(description="Claim your daily login streak rewards")
async def daily(message: discord.Interaction):
    await message.response.defer()
    now = int(time.time())
    
    profile = await Profile.get_or_create(user_id=message.user.id, guild_id=message.guild.id)
    
    # Check if already claimed today
    last_claim = profile.last_daily_claim or 0
    time_since_claim = now - last_claim
    
    # Exactly 24 hours = 86400 seconds
    if time_since_claim < 86400:
        time_remaining = 86400 - time_since_claim
        hours = time_remaining // 3600
        minutes = (time_remaining % 3600) // 60
        await message.followup.send(
            f"⏰ You've already claimed your daily reward! Come back in **{hours}h {minutes}m**.",
            ephemeral=True
        )
        return
    
    # Check if streak should continue (within 48 hours of last claim)
    if time_since_claim > 172800:  # 48 hours
        profile.daily_streak = 0
    
    # Increment streak
    profile.daily_streak += 1
    profile.last_daily_claim = now
    
    # Base rewards
    base_kibble = 100 + (profile.daily_streak * 10)  # Increases with streak
    rewards_text = [f"🍖 **{base_kibble:,} Kibble**"]
    
    profile.kibble = (profile.kibble or 0) + base_kibble
    
    # Milestone rewards every 50 days
    if profile.daily_streak % 50 == 0:
        milestone_rewards = []
        
        # 10 minute rain
        milestone_rewards.append("🌧️ **10 minute Cat Rain**")
        # We'll trigger the rain in the current channel
        
        # 15 celestial packs
        profile.pack_celestial = (profile.pack_celestial or 0) + 15
        milestone_rewards.append("📦 **15 Celestial Packs**")
        
        # 15k kibble bonus
        profile.kibble += 15000
        milestone_rewards.append("🍖 **15,000 Bonus Kibble**")
        
        # 1 celestial cat
        profile.cat_Ultimate = (profile.cat_Ultimate or 0) + 1
        milestone_rewards.append(f"{get_emoji('ultimatecat')} **1 Ultimate Cat**")
        
        await profile.save()
        
        # Trigger 10 minute rain
        try:
            await give_rain(message.channel, 600)
        except Exception:
            pass
        
        embed = discord.Embed(
            title="🎉 MILESTONE REACHED! 🎉",
            description=f"**{profile.daily_streak} DAY STREAK!**\n\n" + "\n".join(milestone_rewards),
            color=Colors.gold
        )
        embed.add_field(name="Daily Reward", value=rewards_text[0], inline=False)
        embed.set_footer(text=f"Come back tomorrow to claim day {profile.daily_streak + 1}!")
        await message.followup.send(embed=embed)
        return
    
    await profile.save()
    
    # Regular daily reward
    embed = discord.Embed(
        title="✨ Daily Streak Claimed!",
        description=f"🔥 **{profile.daily_streak} Day Streak**",
        color=Colors.brown
    )
    embed.add_field(name="Rewards", value="\n".join(rewards_text), inline=False)
    embed.set_footer(text=f"Come back in 24 hours to claim day {profile.daily_streak + 1}!")
    
    await message.followup.send(embed=embed)
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

    cats_list = await get_user_cats(guild_id, user_id)
    filtered = [c for c in cats_list if c.get("type") == match]

    # If aggregated counters show the user has cats but the per-instance database is empty,
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
            # create missing instances in database only (don't bump aggregated counters)
            await _create_instances_only(guild_id, user_id, match, missing)
            cats_list = await get_user_cats(guild_id, user_id)
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
    cats_list = await get_user_cats(guild_id, user_id)
    filtered = [c for c in cats_list if c.get("type") == match]
    if not filtered:
        await interaction.followup.send(f"You have no {match} cats.\n\n**Tip:** If you think you should have cats, try running `/syncats` to sync your cat instances.", ephemeral=ephemeral)
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
        cats = await get_user_cats(self.guild_id, interaction.user.id)
        inst = None
        for c in cats:
            if c.get("id") == self.inst_id:
                inst = c
                break
        if not inst:
            await interaction.response.send_message("That instance was not found.", ephemeral=True)
            return

        inst["favorite"] = not bool(inst.get("favorite", False))
        await save_user_cats(self.guild_id, interaction.user.id, cats)

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

    cats_list = await get_user_cats(message.guild.id, message.user.id)
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

                        cats_list_local = await get_user_cats(message.guild.id, modal_interaction.user.id)
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


# Advanced cat selector view with filtering and pagination
class AdvancedCatSelector(discord.ui.View):
    """Reusable advanced cat selector with type/name filtering, sorting, and pagination."""
    def __init__(self, author_id: int, guild_id: int, user_id: int, all_cats: list, callback_func, title: str = "Select a Cat", max_select: int = 1):
        super().__init__(timeout=180)
        self.author_id = author_id
        self.guild_id = guild_id
        self.user_id = user_id
        self.all_cats = all_cats
        self.callback_func = callback_func  # async function(interaction, selected_cat) to call when cat is selected
        self.title = title
        self.max_select = max_select
        self.page = 0
        self.filter_type = None
        self.filter_name = None
        self.filter_favorite = False  # Filter for favorites only
        self.sort_by = "rarity"  # rarity, bond, hp, dmg, date, name
        self.sort_desc = True  # True for descending (high to low), False for ascending
        self.update_sorting()
        self.update_buttons()
    
    def update_sorting(self):
        """Apply current sorting to all cats"""
        def _sort_key(c):
            if self.sort_by == "rarity":
                cat_type = c.get('type', 'Fine')
                return type_dict.get(cat_type, 100)
            elif self.sort_by == "bond":
                return int(c.get('bond', 0))
            elif self.sort_by == "hp":
                return int(c.get('hp', 0))
            elif self.sort_by == "dmg":
                return int(c.get('dmg', 0))
            elif self.sort_by == "date":
                return int(c.get('acquired_at', 0))
            elif self.sort_by == "name":
                return c.get('name', '').lower()
            return 0
        
        self.sorted_cats = sorted(self.all_cats, key=_sort_key, reverse=self.sort_desc)
    
    def get_filtered_cats(self):
        """Get filtered cats"""
        filtered = self.sorted_cats
        if self.filter_type:
            filtered = [c for c in filtered if c.get('type', '').lower() == self.filter_type.lower()]
        if self.filter_name:
            filtered = [c for c in filtered if self.filter_name.lower() in c.get('name', '').lower()]
        if self.filter_favorite:
            filtered = [c for c in filtered if c.get('favorite', False)]
        return filtered
    
    def update_buttons(self):
        self.clear_items()
        filtered_cats = self.get_filtered_cats()
        total_pages = (len(filtered_cats) - 1) // 25 + 1 if filtered_cats else 1
        start_idx = self.page * 25
        end_idx = start_idx + 25
        page_cats = filtered_cats[start_idx:end_idx]
        
        # Add filter buttons (row 0)
        filter_type_btn = discord.ui.Button(
            label=f"🔍 Type: {self.filter_type or 'All'}"[:80], 
            style=discord.ButtonStyle.secondary, 
            row=0
        )
        filter_type_btn.callback = self.filter_by_type
        self.add_item(filter_type_btn)
        
        filter_name_btn = discord.ui.Button(
            label=f"🔍 Name: {self.filter_name or 'All'}"[:80], 
            style=discord.ButtonStyle.secondary, 
            row=0
        )
        filter_name_btn.callback = self.filter_by_name
        self.add_item(filter_name_btn)
        
        fav_filter_btn = discord.ui.Button(
            label=f"⭐ Fav: {'On' if self.filter_favorite else 'Off'}"[:80],
            style=discord.ButtonStyle.success if self.filter_favorite else discord.ButtonStyle.secondary,
            row=0
        )
        fav_filter_btn.callback = self.toggle_favorite_filter
        self.add_item(fav_filter_btn)
        
        clear_filter_btn = discord.ui.Button(
            label="❌ Clear", 
            style=discord.ButtonStyle.secondary, 
            row=0,
            disabled=(not self.filter_type and not self.filter_name and not self.filter_favorite)
        )
        clear_filter_btn.callback = self.clear_filters
        self.add_item(clear_filter_btn)
        
        # Add sorting buttons (row 1)
        sort_labels = {"rarity": "Rarity", "bond": "Bond", "hp": "HP", "dmg": "DMG", "date": "Date", "name": "Name"}
        sort_btn = discord.ui.Button(
            label=f"📊 Sort: {sort_labels.get(self.sort_by, 'Rarity')}"[:80],
            style=discord.ButtonStyle.primary,
            row=1
        )
        sort_btn.callback = self.change_sort
        self.add_item(sort_btn)
        
        order_btn = discord.ui.Button(
            label=f"{'⬇️ High→Low' if self.sort_desc else '⬆️ Low→High'}"[:80],
            style=discord.ButtonStyle.primary,
            row=1
        )
        order_btn.callback = self.toggle_sort_order
        self.add_item(order_btn)
        
        # Add cat selection dropdown (row 2)
        if page_cats:
            options = []
            for cat in page_cats:
                cat_id = cat.get('id')
                name = cat.get('name', 'Unknown')
                cat_type = cat.get('type', 'Unknown')
                hp = cat.get('hp', 0)
                dmg = cat.get('dmg', 0)
                bond = cat.get('bond', 0)
                is_fav = "⭐ " if cat.get('favorite', False) else ""
                
                options.append(discord.SelectOption(
                    label=f"{is_fav}{name} ({cat_type})"[:100],
                    description=f"HP: {hp} | DMG: {dmg} | Bond: {bond}"[:100],
                    value=str(cat_id)
                ))
            
            select = discord.ui.Select(
                placeholder=f"{self.title} - Page {self.page + 1}/{total_pages}"[:150],
                options=options,
                max_values=min(self.max_select, len(options)),
                row=2
            )
            select.callback = self.cat_selected
            self.add_item(select)
        
        # Add pagination buttons (row 3)
        if self.page > 0:
            prev_btn = discord.ui.Button(label="◀️ Prev", style=discord.ButtonStyle.primary, row=3)
            prev_btn.callback = self.prev_page
            self.add_item(prev_btn)
        
        if self.page < total_pages - 1:
            next_btn = discord.ui.Button(label="Next ▶️", style=discord.ButtonStyle.primary, row=3)
            next_btn.callback = self.next_page
            self.add_item(next_btn)
        
        page_info_btn = discord.ui.Button(
            label=f"Page {self.page + 1}/{total_pages} ({len(filtered_cats)} cats)"[:80], 
            style=discord.ButtonStyle.secondary, 
            row=3,
            disabled=True
        )
        self.add_item(page_info_btn)
    
    async def filter_by_type(self, btn_it: discord.Interaction):
        if btn_it.user.id != self.author_id:
            await do_funny(btn_it)
            return
        
        class TypeFilterModal(discord.ui.Modal, title="Filter by Cat Type"):
            type_input = discord.ui.TextInput(
                label="Cat Type (or leave blank for all)",
                placeholder="e.g., Fire, Water, Divine, Fine...",
                required=False,
                max_length=50
            )
            
            async def on_submit(modal_self, modal_it: discord.Interaction):
                filter_value = str(modal_self.type_input.value).strip()
                self.filter_type = filter_value if filter_value else None
                self.page = 0
                self.update_buttons()
                
                filter_info = self._get_filter_info()
                await modal_it.response.edit_message(content=f"{self.title}{filter_info}", view=self)
        
        await btn_it.response.send_modal(TypeFilterModal())
    
    async def filter_by_name(self, btn_it: discord.Interaction):
        if btn_it.user.id != self.author_id:
            await do_funny(btn_it)
            return
        
        class NameFilterModal(discord.ui.Modal, title="Filter by Cat Name"):
            name_input = discord.ui.TextInput(
                label="Cat Name (or leave blank for all)",
                placeholder="Search for cats by name...",
                required=False,
                max_length=50
            )
            
            async def on_submit(modal_self, modal_it: discord.Interaction):
                filter_value = str(modal_self.name_input.value).strip()
                self.filter_name = filter_value if filter_value else None
                self.page = 0
                self.update_buttons()
                
                filter_info = self._get_filter_info()
                await modal_it.response.edit_message(content=f"{self.title}{filter_info}", view=self)
        
        await btn_it.response.send_modal(NameFilterModal())
    
    async def clear_filters(self, btn_it: discord.Interaction):
        if btn_it.user.id != self.author_id:
            await do_funny(btn_it)
            return
        
        self.filter_type = None
        self.filter_name = None
        self.filter_favorite = False
        self.page = 0
        self.update_buttons()
        
        await btn_it.response.edit_message(content=self.title, view=self)
    
    async def toggle_favorite_filter(self, btn_it: discord.Interaction):
        if btn_it.user.id != self.author_id:
            await do_funny(btn_it)
            return
        
        self.filter_favorite = not self.filter_favorite
        self.page = 0
        self.update_buttons()
        
        filter_info = self._get_filter_info()
        await btn_it.response.edit_message(content=f"{self.title}{filter_info}", view=self)
    
    async def change_sort(self, btn_it: discord.Interaction):
        if btn_it.user.id != self.author_id:
            await do_funny(btn_it)
            return
        
        class SortModal(discord.ui.Modal, title="Change Sort Order"):
            sort_input = discord.ui.TextInput(
                label="Sort by: rarity/bond/hp/dmg/date/name",
                placeholder="rarity",
                required=True,
                max_length=10
            )
            
            async def on_submit(modal_self, modal_it: discord.Interaction):
                sort_value = str(modal_self.sort_input.value).strip().lower()
                if sort_value in ["rarity", "bond", "hp", "dmg", "date", "name"]:
                    self.sort_by = sort_value
                    self.page = 0
                    self.update_sorting()
                    self.update_buttons()
                    
                    filter_info = self._get_filter_info()
                    await modal_it.response.edit_message(content=f"{self.title}{filter_info}", view=self)
                else:
                    await modal_it.response.send_message("Invalid sort option. Use: rarity, bond, hp, dmg, date, or name", ephemeral=True)
        
        await btn_it.response.send_modal(SortModal())
    
    async def toggle_sort_order(self, btn_it: discord.Interaction):
        if btn_it.user.id != self.author_id:
            await do_funny(btn_it)
            return
        
        self.sort_desc = not self.sort_desc
        self.page = 0
        self.update_sorting()
        self.update_buttons()
        
        filter_info = self._get_filter_info()
        await btn_it.response.edit_message(content=f"{self.title}{filter_info}", view=self)
    
    async def prev_page(self, btn_it: discord.Interaction):
        if btn_it.user.id != self.author_id:
            await do_funny(btn_it)
            return
        
        self.page = max(0, self.page - 1)
        self.update_buttons()
        
        filter_info = self._get_filter_info()
        await btn_it.response.edit_message(content=f"{self.title}{filter_info}", view=self)
    
    async def next_page(self, btn_it: discord.Interaction):
        if btn_it.user.id != self.author_id:
            await do_funny(btn_it)
            return
        
        filtered_cats = self.get_filtered_cats()
        total_pages = (len(filtered_cats) - 1) // 25 + 1
        self.page = min(total_pages - 1, self.page + 1)
        self.update_buttons()
        
        filter_info = self._get_filter_info()
        await btn_it.response.edit_message(content=f"{self.title}{filter_info}", view=self)
    
    async def cat_selected(self, select_it: discord.Interaction):
        if select_it.user.id != self.author_id:
            await select_it.response.send_message("This is not your selector.", ephemeral=True)
            return
        
        selected_id = select_it.data['values'][0]
        selected_cat = next((c for c in self.all_cats if c.get('id') == selected_id), None)
        
        if not selected_cat:
            await select_it.response.send_message("Cat not found.", ephemeral=True)
            return
        
        # Call the callback function
        await self.callback_func(select_it, selected_cat)
    
    def _get_filter_info(self):
        """Get filter info string"""
        filters = []
        if self.filter_type:
            filters.append(f"Type: {self.filter_type}")
        if self.filter_name:
            filters.append(f"Name: {self.filter_name}")
        if self.filter_favorite:
            filters.append("Favorites only")
        
        if filters:
            return f"\n🔍 Active filters: {', '.join(filters)}"
        return ""


@bot.tree.command(name="play", description="Play with one of your cats to increase its bond")
@discord.app_commands.describe(name="Optional: specific cat name (leave blank to browse all)")
async def play_with_cat_cmd(message: discord.Interaction, name: str = None):
    """Play with a cat. Can browse all cats with advanced filtering, or search by exact name."""
    await message.response.defer()

    # gather user's instances
    try:
        cats_list = await get_user_cats(message.guild.id, message.user.id)
    except Exception:
        cats_list = []
    
    if not cats_list:
        await message.followup.send("You don't have any cats yet! Catch some first.", ephemeral=True)
        return
    
    # If no name provided, show advanced selector
    if not name:
        async def on_cat_selected(interaction: discord.Interaction, selected_cat: dict):
            await interaction.response.defer()
            inst = selected_cat
            embed = make_play_embed(inst)
            file_to_send = None
            try:
                img_path = f"images/spawn/{inst.get('type', '').lower()}_cat.png"
                if os.path.exists(img_path):
                    file_to_send = discord.File(img_path, filename=os.path.basename(img_path))
            except Exception:
                file_to_send = None

            view = PlayView(message.guild.id, interaction.user.id, inst.get('id'))
            try:
                if file_to_send:
                    await interaction.followup.send(embed=embed, view=view, file=file_to_send, ephemeral=True)
                else:
                    await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            except Exception:
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        
        selector = AdvancedCatSelector(
            author_id=message.user.id,
            guild_id=message.guild.id,
            user_id=message.user.id,
            all_cats=cats_list,
            callback_func=on_cat_selected,
            title="Select a cat to play with"
        )
        await message.followup.send("Select a cat to play with:", view=selector, ephemeral=True)
        return

    # Otherwise, search by exact name (existing behavior)
    matches = [(i + 1, c) for i, c in enumerate(cats_list) if (c.get("name") or "").lower() == name.lower()]

    if not matches:
        await message.followup.send(f"Couldn't find a cat named '{name}'. Try running `/play` without a name to browse all your cats.", ephemeral=True)
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
            cats_now = await get_user_cats(self.guild_id, self.owner_id)
            inst = next((c for c in cats_now if c.get('id') == self.instance_id), None)
            if not inst:
                await interaction2.followup.send("That instance no longer exists.", ephemeral=True)
                return

            gain = random.randint(1, 3)
            inst['bond'] = min(100, inst.get('bond', 0) + gain)
            await save_user_cats(self.guild_id, self.owner_id, cats_now)
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
                        cats_now = await get_user_cats(self.guild_id, self.owner_id)
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
                        await save_user_cats(parent_inter.guild.id, parent_inter.user.id, cats_now)

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
                            user_obj = await Profile.get_or_create(guild_id=parent_inter.guild.id, user_id=parent_inter.user.id)
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
                    cats_now = await get_user_cats(message.guild.id, interaction2.user.id)
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

    cats_list = await get_user_cats(message.guild.id, message.user.id)
    filtered = [c for c in cats_list if c.get("type") == match]
    if not filtered or index < 1 or index > len(filtered):
        await message.followup.send(f"Invalid index — run `/cats {catname}` to see indexes.")
        return

    inst = filtered[index - 1]
    inst["name"] = new_name
    await save_user_cats(message.guild.id, message.user.id, cats_list)
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
        # More details button: opens advanced cat selector with filtering
        async def more_details_callback(interaction: discord.Interaction):
            if interaction.user.id != message.user.id:
                await do_funny(interaction)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # Ensure user instances are synced
            try:
                await ensure_user_instances(interaction.guild.id, interaction.user.id)
            except Exception:
                pass
            
            # Get all user's cats
            all_cats = await get_user_cats(interaction.guild.id, interaction.user.id) or []
            
            if not all_cats:
                await interaction.followup.send("You don't have any cats yet! Try catching some first.", ephemeral=True)
                return
            
            async def on_cat_selected(select_it: discord.Interaction, selected_cat: dict):
                await select_it.response.defer(ephemeral=True)
                inst = selected_cat
                cat_type = inst.get('type', 'Unknown')
                detail_embed = build_instance_detail_embed(cat_type, inst)
                
                fav_view = FavoriteView(select_it.guild.id, select_it.user.id, inst.get("id"), cat_type)
                try:
                    fav_btn = next((c for c in fav_view.children if isinstance(c, Button)), None)
                    if fav_btn:
                        fav_btn.label = "Unfavorite" if inst.get("favorite", False) else "Favorite"
                except Exception:
                    pass
                
                await select_it.followup.send(embed=detail_embed, view=fav_view, ephemeral=True)
            
            selector = AdvancedCatSelector(
                author_id=interaction.user.id,
                guild_id=interaction.guild.id,
                user_id=interaction.user.id,
                all_cats=all_cats,
                callback_func=on_cat_selected,
                title="Browse your cats"
            )
            await interaction.followup.send("Browse your cats with filters:", view=selector, ephemeral=True)

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
                                        cats_list = await get_user_cats(modal_inter.guild.id, modal_inter.user.id)
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
                                            await save_user_cats(modal_inter.guild.id, modal_inter.user.id, cats_list)
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
                                                        cats_now2 = await get_user_cats(inter.guild.id, inter.user.id)
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
    # Defer immediately to avoid interaction timeout
    await message.response.defer()
    
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
        # Don't defer here since it's already deferred at command start or in buttons
        if not first:
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

        # extra
        extra_quest = battle.get("quests", {}).get("extra", {}).get(user.extra_quest)
        if not extra_quest:
            # show placeholder if no configured extra
            extra_quest = {"title": "No Extra Quest", "emoji": "mystery", "progress": 1}
        if getattr(user, "extra_cooldown", 1) != 0:
            description += f"✅ ~~{extra_quest['title']}~~\n- Refreshes <t:{int(getattr(user, 'extra_cooldown', 1) + 12 * 3600 if getattr(user, 'extra_cooldown', 1) + 12 * 3600 < timestamp else timestamp)}:R>\n\n"
        else:
            progress_string = ""
            if extra_quest.get("progress", 1) != 1:
                progress_string = f" ({getattr(user, 'extra_progress', 0)}/{extra_quest.get('progress',1)})"
            description += f"{get_emoji(extra_quest.get('emoji','mystery'))} {extra_quest.get('title','Unknown Quest')}{progress_string}\n- Reward: {getattr(user, 'extra_reward', 0)} XP\n\n"

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


# ===== COSMETICS SYSTEM =====

def get_owned_cosmetics(profile):
    """Parse owned cosmetics from profile string"""
    owned = profile.owned_cosmetics or ""
    return set(owned.split(",")) if owned else set()

def add_owned_cosmetic(profile, cosmetic_id):
    """Add a cosmetic to owned list"""
    owned = get_owned_cosmetics(profile)
    owned.add(cosmetic_id)
    profile.owned_cosmetics = ",".join(sorted(owned))

def check_cosmetic_requirement(profile, requirement):
    """Check if user meets achievement requirement"""
    if not requirement:
        return True
    return getattr(profile, requirement, False)

def get_cosmetic_color(profile):
    """Get the user's equipped color or default"""
    color_id = profile.equipped_color or "default"
    color_data = COSMETICS_DATA["colors"].get(color_id, COSMETICS_DATA["colors"]["default"])
    hex_color = color_data["value"]
    return int(hex_color.replace("#", ""), 16)

def format_cosmetic_display(profile):
    """Format user's cosmetic display for embeds"""
    parts = []
    
    # Badge
    if profile.equipped_badge:
        badge_data = COSMETICS_DATA["badges"].get(profile.equipped_badge)
        if badge_data:
            parts.append(badge_data["name"])
    
    # Title
    if profile.equipped_title:
        title_data = COSMETICS_DATA["titles"].get(profile.equipped_title)
        if title_data:
            parts.append(f"**{title_data['name']}**")
    
    # Effect
    if profile.equipped_effect and profile.equipped_effect != "none":
        effect_data = COSMETICS_DATA["effects"].get(profile.equipped_effect)
        if effect_data:
            parts.append(effect_data["emoji"])
    
    return " ".join(parts) if parts else None


@bot.tree.command(description="Browse and purchase cosmetics to customize your profile!")
async def cosmetics(message: discord.Interaction):
    """Cosmetics shop command"""
    await message.response.defer()
    
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    owned = get_owned_cosmetics(user)
    
    # Give starter cosmetics if new
    if "starter" not in owned:
        add_owned_cosmetic(user, "starter")
        add_owned_cosmetic(user, "newbie")
        add_owned_cosmetic(user, "default")
        add_owned_cosmetic(user, "none")
        await user.save()
        owned = get_owned_cosmetics(user)
    
    current_category = "badges"
    
    class CosmeticsView(View):
        def __init__(self):
            super().__init__(timeout=VIEW_TIMEOUT)
            self.category = current_category
            self.page = 0
            self.update_buttons()
        
        def get_embed(self):
            kibbles = user.kibble or 0
            category_data = COSMETICS_DATA[self.category]
            items = list(category_data.items())
            
            # Pagination
            items_per_page = 10
            start = self.page * items_per_page
            end = start + items_per_page
            page_items = items[start:end]
            total_pages = (len(items) - 1) // items_per_page + 1
            
            embed = discord.Embed(
                title=f"✨ Cosmetics Shop - {self.category.title()}",
                description=f"🍖 Your Kibbles: **{kibbles:,}**\n\nEarn kibbles from packs and activities to customize your profile!\n",
                color=get_cosmetic_color(user)
            )
            
            # Add showcase info if on showcases tab
            if self.category == "showcases":
                current_slots = user.showcase_slots or 2
                embed.description += f"\n📊 **Current Showcase Slots:** {current_slots}/6\n"
            
            for item_id, item_data in page_items:
                # Special handling for showcases
                if self.category == "showcases":
                    current_slots = user.showcase_slots or 2
                    slot_num = int(item_id.split("_")[1])
                    
                    if current_slots >= slot_num:
                        owned_status = "✅ Owned"
                    elif slot_num == current_slots + 1:
                        owned_status = f"🍖 {item_data['price']:,} Kibbles (Next Upgrade)"
                    else:
                        owned_status = f"🔒 Unlocks at slot {slot_num}"
                else:
                    owned_status = "✅ Owned" if item_id in owned else f"🍖 {item_data['price']} Kibbles"
                
                # Check requirements
                req_text = ""
                if item_data.get("requirement"):
                    req = item_data["requirement"]
                    has_req = check_cosmetic_requirement(user, req)
                    req_text = f" | {'✓' if has_req else '🔒'} Requires achievement"
                
                # Different display per category
                if self.category == "colors":
                    display_name = f"{item_data['name']}"
                elif self.category == "effects":
                    display_name = f"{item_data.get('emoji', '')} {item_data['name']}"
                else:
                    display_name = item_data['name']
                
                embed.add_field(
                    name=f"{display_name}",
                    value=f"{item_data['description']}\n{owned_status}{req_text}",
                    inline=False
                )
            
            embed.set_footer(text=f"Page {self.page + 1}/{total_pages} | Use buttons to browse and purchase")
            return embed
        
        def update_buttons(self):
            self.clear_items()
            
            # Category buttons (row 0)
            categories = [
                ("🎖️", "badges"),
                ("📛", "titles"),
                ("🎨", "colors"),
                ("✨", "effects"),
                ("📊", "showcases")
            ]
            
            for emoji, cat in categories:
                btn = Button(
                    emoji=emoji,
                    label=cat.title(),
                    style=ButtonStyle.primary if cat == self.category else ButtonStyle.secondary,
                    row=0
                )
                # Create proper async callback using a factory function
                def make_callback(category):
                    async def callback(interaction):
                        await self.change_category(interaction, category)
                    return callback
                btn.callback = make_callback(cat)
                self.add_item(btn)
            
            # Navigation buttons (row 1)
            category_data = COSMETICS_DATA[self.category]
            total_pages = (len(category_data) - 1) // 10 + 1
            
            if self.page > 0:
                prev_btn = Button(label="◀️ Previous", style=ButtonStyle.secondary, row=1)
                prev_btn.callback = self.prev_page
                self.add_item(prev_btn)
            
            if self.page < total_pages - 1:
                next_btn = Button(label="Next ▶️", style=ButtonStyle.secondary, row=1)
                next_btn.callback = self.next_page
                self.add_item(next_btn)
            
            # Action buttons (row 2)
            buy_btn = Button(label="💰 Purchase", style=ButtonStyle.success, row=2)
            buy_btn.callback = self.show_purchase
            self.add_item(buy_btn)
            
            # Only show equip button for non-showcase categories
            if self.category != "showcases":
                equip_btn = Button(label="👔 Equip", style=ButtonStyle.blurple, row=2)
                equip_btn.callback = self.show_equip
                self.add_item(equip_btn)
        
        async def change_category(self, interaction: discord.Interaction, new_category: str):
            if interaction.user.id != message.user.id:
                await do_funny(interaction)
                return
            self.category = new_category
            self.page = 0
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        
        async def prev_page(self, interaction: discord.Interaction):
            if interaction.user.id != message.user.id:
                await do_funny(interaction)
                return
            self.page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        
        async def next_page(self, interaction: discord.Interaction):
            if interaction.user.id != message.user.id:
                await do_funny(interaction)
                return
            self.page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        
        async def show_purchase(self, interaction: discord.Interaction):
            if interaction.user.id != message.user.id:
                await do_funny(interaction)
                return
            
            category_data = COSMETICS_DATA[self.category]
            options = []
            
            for item_id, item_data in category_data.items():
                # Special handling for showcases
                if self.category == "showcases":
                    current_slots = user.showcase_slots or 2
                    slot_num = int(item_id.split("_")[1])
                    
                    # Skip if already purchased or below current level
                    if current_slots >= slot_num:
                        continue
                    
                    # Only show next upgrade
                    if slot_num > current_slots + 1:
                        continue
                else:
                    if item_id in owned:
                        continue  # Skip owned items
                    
                    # Check requirements
                    if item_data.get("requirement") and not check_cosmetic_requirement(user, item_data["requirement"]):
                        continue  # Skip locked items
                
                display = item_data['name']
                if self.category == "effects":
                    display = f"{item_data.get('emoji', '')} {display}"
                
                options.append(discord.SelectOption(
                    label=display[:100],
                    description=f"{item_data['price']} Kibbles - {item_data['description']}"[:100],
                    value=item_id
                ))
            
            if not options:
                if self.category == "showcases":
                    await interaction.response.send_message("You're at maximum showcase slots (6)!", ephemeral=True)
                else:
                    await interaction.response.send_message("No items available to purchase!", ephemeral=True)
                return
            
            # Limit to 25 options
            if len(options) > 25:
                options = options[:25]
            
            select = discord.ui.Select(placeholder="Select item to purchase", options=options)
            
            async def purchase_callback(select_interaction: discord.Interaction):
                nonlocal user, owned
                
                if select_interaction.user.id != message.user.id:
                    await do_funny(select_interaction)
                    return
                
                item_id = select.values[0]
                item_data = category_data[item_id]
                price = item_data["price"]
                
                # Reload user data
                fresh_user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
                current_kibbles = fresh_user.kibble or 0
                
                if current_kibbles < price:
                    await select_interaction.response.send_message(
                        f"Not enough Kibbles! Need {price:,} 🍖, you have {current_kibbles:,} 🍖.",
                        ephemeral=True
                    )
                    return
                
                # Special handling for showcase slots
                if self.category == "showcases":
                    current_slots = fresh_user.showcase_slots or 2
                    slot_num = int(item_id.split("_")[1])  # Extract number from slot_3, slot_4, etc.
                    
                    if current_slots >= slot_num:
                        await select_interaction.response.send_message(
                            f"You already have {current_slots} showcase slots!",
                            ephemeral=True
                        )
                        return
                    
                    # Upgrade showcase slots
                    fresh_user.kibble = current_kibbles - price
                    fresh_user.showcase_slots = slot_num
                    await fresh_user.save()
                    
                    # Update global user reference
                    user = fresh_user
                    
                    await select_interaction.response.send_message(
                        f"✨ Upgraded to **{slot_num} Showcase Slots** for {price:,} Kibbles!",
                        ephemeral=True
                    )
                else:
                    # Regular cosmetic purchase
                    fresh_user.kibble = current_kibbles - price
                    add_owned_cosmetic(fresh_user, item_id)
                    await fresh_user.save()
                    
                    # Update global user reference
                    user = fresh_user
                    owned = get_owned_cosmetics(user)
                    
                    await select_interaction.response.send_message(
                        f"✨ Purchased **{item_data['name']}** for {price:,} Kibbles!",
                        ephemeral=True
                    )
                
                # Refresh main view
                self.update_buttons()
                await interaction.edit_original_response(embed=self.get_embed(), view=self)
            
            select.callback = purchase_callback
            
            purchase_view = View(timeout=60)
            purchase_view.add_item(select)
            
            await interaction.response.send_message("Select an item to purchase:", view=purchase_view, ephemeral=True)
        
        async def show_equip(self, interaction: discord.Interaction):
            if interaction.user.id != message.user.id:
                await do_funny(interaction)
                return
            
            category_data = COSMETICS_DATA[self.category]
            options = []
            
            for item_id, item_data in category_data.items():
                if item_id not in owned:
                    continue  # Skip unowned items
                
                display = item_data['name']
                if self.category == "effects":
                    display = f"{item_data.get('emoji', '')} {display}"
                
                # Check if currently equipped
                current = getattr(user, f"equipped_{self.category[:-1] if self.category.endswith('s') else self.category}", "")
                is_equipped = "✓ " if current == item_id else ""
                
                options.append(discord.SelectOption(
                    label=f"{is_equipped}{display}"[:100],
                    description=item_data['description'][:100],
                    value=item_id
                ))
            
            if not options:
                await interaction.response.send_message("No owned items to equip!", ephemeral=True)
                return
            
            # Limit to 25 options
            if len(options) > 25:
                options = options[:25]
            
            select = discord.ui.Select(placeholder="Select item to equip", options=options)
            
            async def equip_callback(select_interaction: discord.Interaction):
                if select_interaction.user.id != message.user.id:
                    await do_funny(select_interaction)
                    return
                
                try:
                    item_id = select.values[0]
                    item_data = category_data[item_id]
                    
                    # Reload and equip
                    fresh_user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
                    
                    # Determine field name
                    if self.category == "badges":
                        fresh_user.equipped_badge = item_id
                    elif self.category == "titles":
                        fresh_user.equipped_title = item_id
                    elif self.category == "colors":
                        fresh_user.equipped_color = item_id
                    elif self.category == "effects":
                        fresh_user.equipped_effect = item_id
                    
                    await fresh_user.save()
                    
                    # Update global user reference
                    nonlocal user
                    user = fresh_user
                    
                    await select_interaction.response.send_message(
                        f"✨ Equipped **{item_data['name']}**!",
                        ephemeral=True
                    )
                    
                    # Refresh main view - use the correct interaction reference
                    self.update_buttons()
                    try:
                        await message.edit_original_response(embed=self.get_embed(), view=self)
                    except Exception:
                        pass  # Main view might have timed out
                except Exception as e:
                    await select_interaction.response.send_message(
                        f"Failed to equip cosmetic: {str(e)}",
                        ephemeral=True
                    )
            
            select.callback = equip_callback
            
            equip_view = View(timeout=60)
            equip_view.add_item(select)
            
            await interaction.response.send_message("Select an item to equip:", view=equip_view, ephemeral=True)
    
    view = CosmeticsView()
    await message.followup.send(embed=view.get_embed(), view=view)


@bot.tree.command(description="View a player's profile with stats, achievements, and showcase!")
async def profile(message: discord.Interaction, person_id: Optional[discord.User] = None):
    """Comprehensive profile display with cosmetics, stats, achievements, and cat showcase"""
    await message.response.defer()
    
    target = person_id or message.user
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=target.id)
    global_user = await User.get_or_create(user_id=target.id)
    
    # Ensure cosmetics
    owned = get_owned_cosmetics(user)
    if "starter" not in owned:
        add_owned_cosmetic(user, "starter")
        add_owned_cosmetic(user, "newbie")
        add_owned_cosmetic(user, "default")
        add_owned_cosmetic(user, "none")
        await user.save()
    
    current_page = "overview"
    
    class ProfileView(View):
        def __init__(self):
            super().__init__(timeout=VIEW_TIMEOUT)
            self.page = current_page
            self.update_buttons()
        
        def get_overview_embed(self):
            """Main profile overview"""
            embed = discord.Embed(
                title=f"{'✨ ' if user.equipped_effect and user.equipped_effect != 'none' else ''}{target.display_name}'s Profile",
                color=get_cosmetic_color(user)
            )
            
            # Add cosmetic display
            cosmetic_display = format_cosmetic_display(user)
            if cosmetic_display:
                embed.description = cosmetic_display + "\n━━━━━━━━━━━━━━━━"
            
            # Set thumbnail to user avatar
            embed.set_thumbnail(url=target.display_avatar.url)
            
            # Quick Stats
            total_cats = sum(user[f"cat_{cat}"] for cat in cattypes)
            unique_cats = sum(1 for cat in cattypes if user[f"cat_{cat}"] > 0)
            
            stats_text = (
                f"🐈 **Total Cats:** {total_cats:,}\n"
                f"📚 **Unique Types:** {unique_cats}/{len(cattypes)}\n"
                f"🎯 **Total Catches:** {user.total_catches or 0:,}\n"
                f"🧬 **Breeds:** {user.breeds_total or 0:,}\n"
                f"⚔️ **Battle Wins:** {user.battles_won or 0:,}\n"
                f"🍪 **Cookies:** {user.cookies or 0:,}\n"
                f"🦴 **Kibbles:** {user.kibble or 0:,}"
            )
            embed.add_field(name="📊 Quick Stats", value=stats_text, inline=True)
            
            # Achievement Progress
            total_aches = len(aches_data)
            unlocked_aches = sum(1 for ach_key in aches_data if getattr(user, ach_key, False))
            
            progress_text = (
                f"🏆 **Achievements:** {unlocked_aches}/{total_aches}\n"
                f"⬆️ **Battlepass Level:** {user.battlepass or 0}\n"
                f"✅ **Quests Completed:** {user.quests_completed or 0:,}\n"
                f"📦 **Packs Opened:** {user.packs_opened or 0:,}"
            )
            embed.add_field(name="🎮 Progress", value=progress_text, inline=True)
            
            # Fastest/Slowest catches
            if user.time and user.time < 99999999999999:
                fastest = f"{user.time:.3f}s"
            else:
                fastest = "N/A"
            
            if user.timeslow and user.timeslow > 0:
                slowest = f"{round(user.timeslow / 3600, 2)}h"
            else:
                slowest = "N/A"
            
            records_text = (
                f"⚡ **Fastest Catch:** {fastest}\n"
                f"💤 **Slowest Catch:** {slowest}\n"
                f"🌧️ **Rain Participations:** {user.rain_participations or 0:,}"
            )
            embed.add_field(name="📈 Records", value=records_text, inline=False)
            
            embed.set_footer(text="Use the buttons below to explore more!")
            return embed
        
        def get_showcase_embed(self):
            """Cat showcase with rarest cats - dynamic slots"""
            embed = discord.Embed(
                title=f"{target.display_name}'s Cat Showcase",
                color=get_cosmetic_color(user)
            )
            
            embed.set_thumbnail(url=target.display_avatar.url)
            
            # Get number of showcase slots (default 2)
            showcase_slots = user.showcase_slots or 2
            
            # Get rarest cats owned
            owned_cats = [(cat, user[f"cat_{cat}"]) for cat in cattypes if user[f"cat_{cat}"] > 0]
            
            if not owned_cats:
                embed.description = "No cats to showcase yet!"
                return embed
            
            # Sort by rarity (type_dict - lower number = rarer)
            owned_cats.sort(key=lambda x: type_dict[x[0]])
            
            # Get achievements
            unlocked_aches = [(ach_key, ach_data) for ach_key, ach_data in aches_data.items() if getattr(user, ach_key, False)]
            
            # Dynamic showcase based on slots
            showcases_added = 0
            
            # Slot 1: Rarest Cat
            if showcases_added < showcase_slots and owned_cats:
                rarest_cat, rarest_count = owned_cats[0]
                emoji = get_emoji(rarest_cat.lower() + "cat")
                rarity_val = type_dict[rarest_cat]
                embed.add_field(
                    name="🌟 Rarest Cat",
                    value=f"{emoji} **{rarest_cat}**\n{rarest_count:,} owned\nRarity: {rarity_val}",
                    inline=True
                )
                showcases_added += 1
            
            # Slot 2: Best Achievement
            if showcases_added < showcase_slots and unlocked_aches:
                # Get a random impressive achievement
                best_ach = unlocked_aches[-1] if unlocked_aches else None
                if best_ach:
                    ach_key, ach_data = best_ach
                    display = ach_data.get("display", ach_key)
                    embed.add_field(
                        name="🏆 Achievement",
                        value=f"**{display}**\n{ach_data.get('description', 'Unlocked!')}",
                        inline=True
                    )
                    showcases_added += 1
            
            # Slot 3: Most Owned Cat
            if showcases_added < showcase_slots and owned_cats:
                most_owned = max(owned_cats, key=lambda x: x[1])
                cat_type, count = most_owned
                emoji = get_emoji(cat_type.lower() + "cat")
                embed.add_field(
                    name="📊 Most Collected",
                    value=f"{emoji} **{cat_type}**\n{count:,} cats",
                    inline=True
                )
                showcases_added += 1
            
            # Slot 4: Total Collection
            if showcases_added < showcase_slots:
                total_cats = sum(user[f"cat_{cat}"] for cat in cattypes)
                unique_cats = len(owned_cats)
                embed.add_field(
                    name="📚 Collection Size",
                    value=f"**{total_cats:,}** total cats\n**{unique_cats}/{len(cattypes)}** unique types",
                    inline=True
                )
                showcases_added += 1
            
            # Slot 5: Battle Stats
            if showcases_added < showcase_slots:
                battles = user.battles_won or 0
                breeds = user.breeds_total or 0
                embed.add_field(
                    name="⚔️ Combat Stats",
                    value=f"**{battles:,}** battles won\n**{breeds:,}** cats bred",
                    inline=True
                )
                showcases_added += 1
            
            # Slot 6: Wealth Display
            if showcases_added < showcase_slots:
                cookies = user.cookies or 0
                kibbles = user.kibble or 0
                embed.add_field(
                    name="💰 Wealth",
                    value=f"🍪 **{cookies:,}** Cookies\n🍖 **{kibbles:,}** Kibbles",
                    inline=True
                )
                showcases_added += 1
            
            # Show upgrade prompt if not at max
            if showcase_slots < 6:
                embed.set_footer(text=f"Showcase Slots: {showcase_slots}/6 | Upgrade in /cosmetics!")
            else:
                embed.set_footer(text=f"Showcase Slots: {showcase_slots}/6 (MAX)")
            
            return embed
        
        def get_achievements_embed(self):
            """Achievement showcase"""
            embed = discord.Embed(
                title=f"{target.display_name}'s Achievements",
                color=get_cosmetic_color(user)
            )
            
            embed.set_thumbnail(url=target.display_avatar.url)
            
            # Group achievements by unlock status
            unlocked = []
            locked = []
            
            for ach_key, ach_data in list(aches_data.items())[:20]:  # Show first 20
                has_ach = getattr(user, ach_key, False)
                display = ach_data.get("display", ach_key)
                desc = ach_data.get("description", "???")
                
                if has_ach:
                    unlocked.append(f"✅ **{display}** - {desc}")
                else:
                    locked.append(f"🔒 **{display}** - {desc}")
            
            if unlocked:
                embed.add_field(
                    name=f"🏆 Unlocked ({len(unlocked)})",
                    value="\n".join(unlocked[:10]) if unlocked else "None yet!",
                    inline=False
                )
            
            if locked:
                embed.add_field(
                    name=f"🔒 Locked (showing {min(5, len(locked))})",
                    value="\n".join(locked[:5]),
                    inline=False
                )
            
            # Achievement stats
            total_unlocked = sum(1 for ach_key in aches_data if getattr(user, ach_key, False))
            total_aches = len(aches_data)
            completion = (total_unlocked / total_aches) * 100
            
            embed.set_footer(text=f"Total Progress: {total_unlocked}/{total_aches} ({completion:.1f}%)")
            
            return embed
        
        def get_stats_embed(self):
            """Detailed statistics"""
            embed = discord.Embed(
                title=f"{target.display_name}'s Statistics",
                color=get_cosmetic_color(user)
            )
            
            embed.set_thumbnail(url=target.display_avatar.url)
            
            # Catching Stats
            total_catches = user.total_catches or 0
            rain_catches = user.rain_participations or 0
            normal_catches = total_catches - rain_catches
            
            avg_time = "N/A"
            if normal_catches > 0 and user.total_catch_time:
                avg_time = f"{user.total_catch_time / normal_catches:.2f}s"
            
            catch_stats = (
                f"🐈 **Total Catches:** {total_catches:,}\n"
                f"🌧️ **Rain Catches:** {rain_catches:,}\n"
                f"⏱️ **Average Time:** {avg_time}\n"
                f"⚡ **Fastest:** {user.time:.3f}s" if user.time < 99999999999999 else "N/A"
            )
            embed.add_field(name="📊 Catching Stats", value=catch_stats, inline=True)
            
            # Battle Stats
            battle_stats = (
                f"⚔️ **Battles Won:** {user.battles_won or 0:,}\n"
                f"🎲 **TTT Played:** {user.ttt_played or 0:,}\n"
                f"🏆 **TTT Wins:** {user.ttt_won or 0:,}\n"
                f"🤝 **TTT Draws:** {user.ttt_draws or 0:,}"
            )
            embed.add_field(name="⚔️ Battle Stats", value=battle_stats, inline=True)
            
            # Economy Stats
            economy_stats = (
                f"🍪 **Cookies:** {user.cookies or 0:,}\n"
                f"🦴 **Kibbles:** {user.kibble or 0:,}\n"
                f"📦 **Packs Opened:** {user.packs_opened or 0:,}\n"
                f"⬆️ **Pack Upgrades:** {user.pack_upgrades or 0:,}"
            )
            embed.add_field(name="💰 Economy", value=economy_stats, inline=True)
            
            # Breeding & Trading Stats
            social_stats = (
                f"🧬 **Total Breeds:** {user.breeds_total or 0:,}\n"
                f"🤝 **Trades Completed:** {user.trades_completed or 0:,}\n"
                f"📤 **Cats Traded:** {user.cats_traded or 0:,}\n"
                f"🎁 **Cats Gifted:** {user.cats_gifted or 0:,}\n"
                f"📥 **Gifts Received:** {user.cat_gifts_recieved or 0:,}"
            )
            embed.add_field(name="🤝 Social", value=social_stats, inline=True)
            
            # Quest & Progress Stats
            quest_stats = (
                f"✅ **Quests Done:** {user.quests_completed or 0:,}\n"
                f"⬆️ **Battlepass Lvl:** {user.battlepass or 0}\n"
                f"⭐ **BP XP:** {user.progress or 0}\n"
                f"🎰 **Slot Spins:** {user.slot_spins or 0:,}\n"
                f"💰 **Slot Wins:** {user.slot_wins or 0:,}"
            )
            embed.add_field(name="🎮 Progress", value=quest_stats, inline=True)
            
            # Misc Stats
            misc_stats = (
                f"🗳️ **Total Votes:** {global_user.total_votes or 0:,}\n"
                f"🔥 **Vote Streak:** {global_user.vote_streak or 0}\n"
                f"⚡ **Max Streak:** {global_user.max_vote_streak or 0}\n"
                f"🎯 **Perfection Count:** {user.perfection_count or 0:,}"
            )
            embed.add_field(name="📈 Misc", value=misc_stats, inline=True)
            
            return embed
        
        def get_cosmetics_embed(self):
            """Show equipped cosmetics"""
            embed = discord.Embed(
                title=f"{target.display_name}'s Style",
                color=get_cosmetic_color(user)
            )
            
            embed.set_thumbnail(url=target.display_avatar.url)
            
            # Badge
            badge_text = "None"
            if user.equipped_badge:
                badge_data = COSMETICS_DATA["badges"].get(user.equipped_badge)
                if badge_data:
                    badge_text = f"{badge_data['name']}\n*{badge_data['description']}*"
            embed.add_field(name="🎖️ Badge", value=badge_text, inline=True)
            
            # Title
            title_text = "None"
            if user.equipped_title:
                title_data = COSMETICS_DATA["titles"].get(user.equipped_title)
                if title_data:
                    title_text = f"**{title_data['name']}**\n*{title_data['description']}*"
            embed.add_field(name="📛 Title", value=title_text, inline=True)
            
            # Effect
            effect_text = "None"
            if user.equipped_effect and user.equipped_effect != "none":
                effect_data = COSMETICS_DATA["effects"].get(user.equipped_effect)
                if effect_data:
                    effect_text = f"{effect_data['emoji']} {effect_data['name']}\n*{effect_data['description']}*"
            embed.add_field(name="✨ Effect", value=effect_text, inline=True)
            
            # Color
            color_text = "Default Blue"
            if user.equipped_color:
                color_data = COSMETICS_DATA["colors"].get(user.equipped_color)
                if color_data:
                    color_text = f"{color_data['name']}\n`{color_data['value']}`"
            embed.add_field(name="🎨 Profile Color", value=color_text, inline=True)
            
            # Kibbles
            kibbles = user.kibble or 0
            embed.add_field(name="🦴 Kibbles", value=f"{kibbles:,}", inline=True)
            
            # Owned cosmetics count
            owned_count = len(get_owned_cosmetics(user))
            total_cosmetics = sum(len(v) for v in COSMETICS_DATA.values())
            embed.add_field(
                name="📦 Collection",
                value=f"{owned_count}/{total_cosmetics} cosmetics owned",
                inline=True
            )
            
            embed.set_footer(text="Use /cosmetics to purchase more!")
            
            return embed
        
        def get_current_embed(self):
            if self.page == "overview":
                return self.get_overview_embed()
            elif self.page == "showcase":
                return self.get_showcase_embed()
            elif self.page == "achievements":
                return self.get_achievements_embed()
            elif self.page == "stats":
                return self.get_stats_embed()
            elif self.page == "cosmetics":
                return self.get_cosmetics_embed()
            return self.get_overview_embed()
        
        def update_buttons(self):
            self.clear_items()
            
            # Page navigation buttons
            pages = [
                ("🏠", "overview", "Overview"),
                ("🌟", "showcase", "Showcase"),
                ("🏆", "achievements", "Achievements"),
                ("📊", "stats", "Stats"),
                ("✨", "cosmetics", "Style")
            ]
            
            for emoji, page_id, label in pages:
                btn = Button(
                    emoji=emoji,
                    label=label,
                    style=ButtonStyle.primary if page_id == self.page else ButtonStyle.secondary,
                    row=0
                )
                btn.callback = lambda i, p=page_id: self.change_page(i, p)
                self.add_item(btn)
        
        async def change_page(self, interaction: discord.Interaction, new_page: str):
            if interaction.user.id != message.user.id:
                await do_funny(interaction)
                return
            
            self.page = new_page
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_current_embed(), view=self)
    
    view = ProfileView()
    await message.followup.send(embed=view.get_current_embed(), view=view)


@bot.tree.command(description="View your equipped cosmetics!")
async def mystyle(message: discord.Interaction, person_id: Optional[discord.User] = None):
    """Shortcut to profile cosmetics page"""
    await message.response.send_message("💡 Use `/profile` instead to see a full profile with cosmetics, stats, and more!", ephemeral=True)


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
    """Open an ATM with advanced cat selector to convert cats into Kibble."""
    await message.response.defer()
    guild_id = message.guild.id
    owner_id = message.user.id

    profile = await Profile.get_or_create(guild_id=guild_id, user_id=owner_id)
    
    # Get all user cats
    user_cats = await get_user_cats(guild_id, owner_id)
    
    # Filter out favorited and adventuring cats
    convertible_cats = [c for c in user_cats if not c.get("on_adventure") and not c.get("favorite")]
    
    if not convertible_cats:
        await message.followup.send("You have no convertible cats (all either favourite or on adventure).", ephemeral=True)
        return

    embed = discord.Embed(
        title="🏧 CatATM - Convert Cats to Kibble",
        description="Select cats to convert into Kibble. **This is irreversible!**\n\nCats are sorted by bond (lowest first) to help you choose wisely.",
        color=Colors.brown,
    )
    
    selected_cats = []  # Track selected cat IDs for bulk conversion
    
    async def cat_selected(interaction: discord.Interaction, selected_cat: dict):
        """Callback when a cat is selected - adds to bulk selection"""
        cat_id = selected_cat.get('id')
        cat_type = selected_cat.get('type')
        cat_name = selected_cat.get('name') or 'Unnamed'
        cat_bond = selected_cat.get('bond', 0)
        
        if not cat_id or not cat_type:
            await interaction.response.send_message("Invalid cat selected.", ephemeral=True)
            return
        
        # Toggle selection
        if cat_id in selected_cats:
            selected_cats.remove(cat_id)
            await interaction.response.send_message(
                f"❌ Removed **{cat_name}** from selection.\n\n**Selected: {len(selected_cats)} cats**",
                ephemeral=True
            )
            return
        
        # Add to selection
        selected_cats.append(cat_id)
        await interaction.response.send_message(
            f"✅ Added **{cat_name}** ({cat_type}) to selection!\n\n**Selected: {len(selected_cats)} cats**\n\n"
            f"💡 Keep selecting cats, or go back to the main ATM message to convert all selected cats.",
            ephemeral=True
        )
    
    class ATMView(View):
        def __init__(self):
            super().__init__(timeout=300)
            self.update_buttons()
        
        def update_buttons(self):
            self.clear_items()
            
            select_btn = Button(label=f"📋 Select Cats ({len(selected_cats)})", style=ButtonStyle.primary, row=0)
            select_btn.callback = self.open_selector
            self.add_item(select_btn)
            
            if selected_cats:
                convert_btn = Button(label=f"💰 Convert {len(selected_cats)} Cats", style=ButtonStyle.danger, row=0)
                convert_btn.callback = self.convert_selected
                self.add_item(convert_btn)
                
                clear_btn = Button(label="🗑️ Clear Selection", style=ButtonStyle.secondary, row=1)
                clear_btn.callback = self.clear_selection
                self.add_item(clear_btn)
        
        async def open_selector(self, btn_it: discord.Interaction):
            if btn_it.user.id != owner_id:
                await do_funny(btn_it)
                return
            
            selector = AdvancedCatSelector(
                author_id=owner_id,
                guild_id=guild_id,
                user_id=owner_id,
                all_cats=convertible_cats,
                callback_func=cat_selected,
                title=f"🏧 CatATM - Select cats ({len(selected_cats)} selected)"
            )
            
            # Default sort by bond (ascending)
            selector.sort_by = "bond"
            selector.sort_desc = False
            selector.update_sorting()
            selector.update_buttons()
            
            await btn_it.response.send_message("Click cats to add/remove from selection:", view=selector, ephemeral=True)
        
        async def convert_selected(self, btn_it: discord.Interaction):
            if btn_it.user.id != owner_id:
                await do_funny(btn_it)
                return
            
            if not selected_cats:
                await btn_it.response.send_message("No cats selected!", ephemeral=True)
                return
            
            await btn_it.response.defer()
            
            # Get latest cat data
            cats_now = await get_user_cats(guild_id, owner_id)
            cats_to_convert = [c for c in cats_now if c.get('id') in selected_cats]
            
            if not cats_to_convert:
                await btn_it.followup.send("Selected cats no longer available.", ephemeral=True)
                return
            
            # Calculate total kibble
            total_kibble = 0
            cat_type_counts = {}
            for cat in cats_to_convert:
                cat_type = cat.get('type')
                try:
                    per_value = sum(type_dict.values()) / type_dict.get(cat_type, 100)
                except Exception:
                    per_value = 100
                kib_per = max(1, int(round(per_value)))
                total_kibble += kib_per
                cat_type_counts[cat_type] = cat_type_counts.get(cat_type, 0) + 1
            
            # Show confirmation
            summary = "\n".join([f"• {get_emoji(ct.lower()+'cat')} {ct}: {cnt}x" for ct, cnt in cat_type_counts.items()])
            
            confirm_embed = discord.Embed(
                title="⚠️ CONFIRM BULK CONVERSION",
                description=f"Converting **{len(cats_to_convert)} cats** for **{total_kibble:,} Kibbles**\n\n{summary}\n\n**This cannot be undone!**",
                color=Colors.maroon
            )
            
            class ConfirmView(View):
                def __init__(self):
                    super().__init__(timeout=60)
                
                @discord.ui.button(label="✅ CONFIRM", style=ButtonStyle.danger)
                async def confirm(self2, conf_it: discord.Interaction):
                    if conf_it.user.id != owner_id:
                        await do_funny(conf_it)
                        return
                    
                    await conf_it.response.defer()
                    
                    # Perform conversion
                    fresh_profile = await Profile.get_or_create(guild_id=guild_id, user_id=owner_id)
                    cats_current = await get_user_cats(guild_id, owner_id)
                    ids_to_remove = set(c.get('id') for c in cats_to_convert)
                    cats_after = [c for c in cats_current if c.get('id') not in ids_to_remove]
                    
                    await save_user_cats(guild_id, owner_id, cats_after)
                    
                    # Update counters
                    for cat_type, cnt in cat_type_counts.items():
                        try:
                            fresh_profile[f"cat_{cat_type}"] = max(0, fresh_profile[f"cat_{cat_type}"] - cnt)
                        except Exception:
                            pass
                    
                    fresh_profile.kibble = (fresh_profile.kibble or 0) + total_kibble
                    await fresh_profile.save()
                    
                    await conf_it.edit_original_response(
                        content=f"✅ Converted **{len(cats_to_convert)} cats** → **{total_kibble:,} Kibbles**!\nNew balance: **{fresh_profile.kibble:,} Kibbles**",
                        embed=None,
                        view=None
                    )
                    
                    await message.channel.send(f"{message.user.mention} converted {len(cats_to_convert)} cats for {total_kibble:,} Kibbles at the CatATM!")
                    
                    # Clear selection
                    selected_cats.clear()
                    self.update_buttons()
                    await message.edit_original_response(embed=embed, view=self)
                
                @discord.ui.button(label="❌ Cancel", style=ButtonStyle.secondary)
                async def cancel(self2, conf_it: discord.Interaction):
                    if conf_it.user.id != owner_id:
                        await do_funny(conf_it)
                        return
                    await conf_it.response.send_message("Conversion cancelled.", ephemeral=True)
            
            await btn_it.followup.send(embed=confirm_embed, view=ConfirmView(), ephemeral=True)
        
        async def clear_selection(self, btn_it: discord.Interaction):
            if btn_it.user.id != owner_id:
                await do_funny(btn_it)
                return
            
            selected_cats.clear()
            self.update_buttons()
            await btn_it.response.edit_message(embed=embed, view=self)
    
    view = ATMView()
    await message.followup.send(embed=embed, view=view)


@bot.tree.command(description="Brew some coffee to catch cats more efficiently")
async def coffee(message: discord.Interaction):
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
        
        # Auto-sync instances for Fine cats
        await auto_sync_cat_instances(profile, "Fine")

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
@discord.app_commands.rename(leaderboard_type="type", leaderboard_scope="scope")
@discord.app_commands.describe(
    leaderboard_type="The leaderboard type to view!",
    leaderboard_scope="Server or Global leaderboard",
    cat_type="The cat type to view (only for the Cats leaderboard)",
    locked="Whether to remove page switch buttons to prevent tampering",
)
@discord.app_commands.autocomplete(cat_type=lb_type_autocomplete)
async def leaderboards(
    message: discord.Interaction,
    leaderboard_type: Optional[Literal["Cats", "Value", "Fast", "Slow", "Battlepass", "Cookies", "Pig", "Packs", "Breeds", "Battles"]],
    leaderboard_scope: Optional[Literal["Server", "Global"]] = "Server",
    cat_type: Optional[str] = None,
    locked: Optional[bool] = False,
):
    if not leaderboard_type:
        leaderboard_type = "Cats"
    if not leaderboard_scope:
        leaderboard_scope = "Server"
    if not locked:
        locked = False
    if cat_type and cat_type not in cattypes + ["All"]:
        await message.response.send_message("invalid cattype", ephemeral=True)
        return

    # this fat function handles a single page
    async def lb_handler(interaction, type, scope="Server", do_edit=None, specific_cat="All"):
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
        
        # Determine query condition based on scope
        is_global = (scope == "Global")
        if is_global:
            scope_condition = "TRUE"  # No guild filter for global
            scope_params = []
        else:
            scope_condition = "guild_id = $1"
            scope_params = [message.guild.id]

        string = ""
        if type == "Cats":
            unit = "cats"

            if specific_cat != "All":
                if is_global:
                    result = await Profile.collect_limit(
                        ["user_id", f"cat_{specific_cat}"], f'{scope_condition} AND "cat_{specific_cat}" > 0 ORDER BY "cat_{specific_cat}" DESC', *scope_params
                    )
                else:
                    result = await Profile.collect_limit(
                        ["user_id", f"cat_{specific_cat}"], f'{scope_condition} AND "cat_{specific_cat}" > 0 ORDER BY "cat_{specific_cat}" DESC', message.guild.id
                    )
                final_value = f"cat_{specific_cat}"
            else:
                # dynamically generate sum expression, cast each value to bigint first to handle large totals
                cat_columns = [f'CAST("cat_{c}" AS BIGINT)' for c in cattypes]
                sum_expression = RawSQL("(" + " + ".join(cat_columns) + ") AS final_value")
                if is_global:
                    result = await Profile.collect_limit(["user_id", sum_expression], f"{scope_condition} ORDER BY final_value DESC", *scope_params)
                else:
                    result = await Profile.collect_limit(["user_id", sum_expression], f"{scope_condition} ORDER BY final_value DESC", message.guild.id)
                final_value = "final_value"

                # find rarest (only for server scope)
                if not is_global:
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
            if is_global:
                result = await Profile.collect_limit(["user_id", total_sum_expr], f"{scope_condition} ORDER BY final_value DESC", *scope_params)
            else:
                result = await Profile.collect_limit(["user_id", total_sum_expr], f"{scope_condition} ORDER BY final_value DESC", message.guild.id)
            final_value = "final_value"
        elif type == "Packs":
            unit = "packs"
            if is_global:
                result = await Profile.collect_limit(["user_id", "packs_opened"], f"{scope_condition} AND packs_opened > 0 ORDER BY packs_opened DESC", *scope_params)
            else:
                result = await Profile.collect_limit(["user_id", "packs_opened"], f"{scope_condition} AND packs_opened > 0 ORDER BY packs_opened DESC", message.guild.id)
            final_value = "packs_opened"
        elif type == "Breeds":
            # Track total breeds completed
            unit = "breeds"
            if is_global:
                result = await Profile.collect_limit(["user_id", "breeds_total"], f"{scope_condition} AND breeds_total > 0 ORDER BY breeds_total DESC", *scope_params)
            else:
                result = await Profile.collect_limit(["user_id", "breeds_total"], f"{scope_condition} AND breeds_total > 0 ORDER BY breeds_total DESC", message.guild.id)
            final_value = "breeds_total"
        elif type == "Battles":
            # Track battles won
            unit = "wins"
            if is_global:
                result = await Profile.collect_limit(["user_id", "battles_won"], f"{scope_condition} AND battles_won > 0 ORDER BY battles_won DESC", *scope_params)
            else:
                result = await Profile.collect_limit(["user_id", "battles_won"], f"{scope_condition} AND battles_won > 0 ORDER BY battles_won DESC", message.guild.id)
            final_value = "battles_won"
        elif type == "Fast":
            unit = "sec"
            if is_global:
                result = await Profile.collect_limit(["user_id", "time"], f"{scope_condition} AND time < 99999999999999 ORDER BY time ASC", *scope_params)
            else:
                result = await Profile.collect_limit(["user_id", "time"], f"{scope_condition} AND time < 99999999999999 ORDER BY time ASC", message.guild.id)
            final_value = "time"
        elif type == "Slow":
            unit = "h"
            if is_global:
                result = await Profile.collect_limit(["user_id", "timeslow"], f"{scope_condition} AND timeslow > 0 ORDER BY timeslow DESC", *scope_params)
            else:
                result = await Profile.collect_limit(["user_id", "timeslow"], f"{scope_condition} AND timeslow > 0 ORDER BY timeslow DESC", message.guild.id)
            final_value = "timeslow"
        elif type == "Battlepass":
            start_date = datetime.datetime(2024, 12, 1)
            current_date = datetime.datetime.utcnow()
            full_months_passed = (current_date.year - start_date.year) * 12 + (current_date.month - start_date.month)
            bp_season = battle["seasons"][str(full_months_passed)]
            if current_date.day < start_date.day:
                full_months_passed -= 1
            if is_global:
                result = await Profile.collect_limit(
                    ["user_id", "battlepass", "progress"],
                    f"{scope_condition} AND season = $1 AND (battlepass > 0 OR progress > 0) ORDER BY battlepass DESC, progress DESC",
                    full_months_passed,
                )
            else:
                result = await Profile.collect_limit(
                    ["user_id", "battlepass", "progress"],
                    f"{scope_condition} AND season = $2 AND (battlepass > 0 OR progress > 0) ORDER BY battlepass DESC, progress DESC",
                    message.guild.id,
                    full_months_passed,
                )
            
            final_value = "battlepass"
        elif type == "Cookies":
            unit = "cookies"
            # Cookies is always server-only
            result = await Profile.collect_limit(["user_id", "cookies"], "guild_id = $1 AND cookies > 0 ORDER BY cookies DESC", message.guild.id)
            string = "Cookie leaderboard updates every 5 min\n\n"
            final_value = "cookies"
        elif type == "Pig":
            unit = "score"
            # Pig is always server-only
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
        
        # Add scope indicator (except for server-only leaderboards)
        if type not in ["Cookies", "Pig"]:
            title += f" ({scope})"
        
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
                on_select=lambda interaction, option: lb_handler(interaction, type, scope, True, option),
                disabled=locked,
            )

        emojied_options = {"Cats": "🐈", "Value": "🧮", "Fast": "⏱️", "Slow": "💤", "Battlepass": "⬆️", "Cookies": "🍪", "Pig": "🎲", "Packs": "📦", "Breeds": "💕", "Battles": "⚔️"}
        options = [Option(label=k, emoji=v) for k, v in emojied_options.items()]
        lb_select = Select(
            "lb_type",
            placeholder=type,
            opts=options,
            on_select=lambda interaction, type: lb_handler(interaction, type, scope, True),
        )
        
        # Scope toggle buttons
        class ScopeButton(discord.ui.Button):
            def __init__(self, label: str, is_active: bool):
                super().__init__(
                    label=label,
                    style=discord.ButtonStyle.primary if is_active else discord.ButtonStyle.secondary,
                    disabled=locked,
                )
                self.scope_type = label
                
            async def callback(self, interaction: discord.Interaction):
                await lb_handler(interaction, type, self.scope_type, True, specific_cat)
        
        server_button = ScopeButton("Server", scope == "Server")
        global_button = ScopeButton("Global", scope == "Global")

        if not locked:
            myview.add_item(lb_select)
            if type == "Cats":
                myview.add_item(dropdown)
            # Add scope buttons for applicable leaderboards (not Cookies/Pig which are server-only)
            if type not in ["Cookies", "Pig"]:
                myview.add_item(server_button)
                myview.add_item(global_button)

        # just send if first time, otherwise edit existing
        try:
            if not do_edit:
                raise Exception
            await interaction.edit_original_response(embed=embedVar, view=myview)
        except Exception:
            await interaction.followup.send(embed=embedVar, view=myview)

        if leader:
            await achemb(message, "leader", "send")

    await lb_handler(message, leaderboard_type, leaderboard_scope, False, cat_type)


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
    
    print("=== SETUP FUNCTION CALLED ===", flush=True)

    # Diagnostic wrapper: record calls to add_cog on the real bot instance.
    # This is temporary debugging code to understand why bot.add_cog
    # isn't resulting in the cog being visible via bot.cogs in some envs.
    try:
        global ADD_COG_LOG, ORIGINAL_ADD_COG
        try:
            ADD_COG_LOG  # don't overwrite if already present
        except NameError:
            ADD_COG_LOG = []

        ORIGINAL_ADD_COG = getattr(bot2, "add_cog", None)
        if ORIGINAL_ADD_COG is not None and not hasattr(bot2, "_add_cog_wrapped"):
            def _add_cog_wrapper(cog, *a, **kw):
                try:
                    snapshot = {
                        "time": time.time(),
                        "cog": getattr(cog, "__class__", type(cog)).__name__,
                        "bot_has__cogs": hasattr(bot2, "_cogs"),
                        "_cogs_preview": repr(getattr(bot2, "_cogs", None))[:400],
                        "bot_dict_keys": list(bot2.__dict__.keys())[:200],
                    }
                except Exception as e:
                    snapshot = {"time": time.time(), "error": str(e)}
                try:
                    res = ORIGINAL_ADD_COG(cog, *a, **kw)
                except Exception as e:
                    snapshot["raised"] = str(e)
                    ADD_COG_LOG.append(snapshot)
                    raise
                snapshot["succeeded"] = True
                ADD_COG_LOG.append(snapshot)
                return res

            try:
                bot2.add_cog = _add_cog_wrapper
                setattr(bot2, "_add_cog_wrapped", True)
            except Exception:
                # be non-fatal if we can't patch the method
                logging.exception("Failed to install add_cog wrapper on bot2 for diagnostics")
    except Exception:
        logging.exception("Unexpected error while setting up add_cog diagnostics")

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

    # Attempt to load the Battles extension into the real bot instance so its cog
    # registers with the running bot (helps when main is loaded as an extension).
    try:
        await bot2.load_extension("battles")
    except Exception:
        try:
            logging.exception("Failed to load 'battles' extension in main.setup; will attempt fallback setup")
            # Fallback: import and call setup(bot2) if present
            import importlib

            mod = importlib.import_module("battles")
            if hasattr(mod, "setup"):
                try:
                    await mod.setup(bot2)
                except Exception:
                    logging.exception("battles.setup(bot2) failed in fallback")
        except Exception:
            logging.exception("Fallback import for 'battles' also failed in main.setup")

    # finally replace the fake bot with the real one
    bot = bot2

    config.SOFT_RESTART_TIME = time.time()

    # Start background tasks
    import sys
    print("[SETUP] About to create background_index_all_cats task...", flush=True, file=sys.stderr)
    print("[STARTUP] Creating background_index_all_cats task...", flush=True)
    bot.loop.create_task(background_index_all_cats(bot2))
    print("[SETUP] Task created!", flush=True, file=sys.stderr)

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
async def breed(message: discord.Interaction):
        """
        Command: /breed
        - Opens an advanced selector to choose two parent cats.
        - Consumes one of each specified cat type from the caller's server inventory.
        - Produces an offspring whose probability distribution is centered on the
          average spawn/rarity value of both parents (not required to be strictly rarer).
        """
        await message.response.defer()
        
        profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
        
        # Get user's cats for selection
        cats_list = await get_user_cats(message.guild.id, message.user.id)
        if not cats_list:
            await message.followup.send("You don't have any cats to breed!", ephemeral=True)
            return
        
        # State variables for breeding pairs
        breed_pairs = []  # Will store [(cat1_type, cat2_type), ...]
        
        class BreedView(View):
            def __init__(self):
                super().__init__(timeout=300)
                self.update_buttons()
            
            def update_buttons(self):
                self.clear_items()
                
                add_btn = Button(label=f"➕ Add Pair ({len(breed_pairs)})", style=ButtonStyle.primary, row=0)
                add_btn.callback = self.add_pair
                self.add_item(add_btn)
                
                if breed_pairs:
                    breed_btn = Button(label=f"🧬 Breed {len(breed_pairs)} Pairs", style=ButtonStyle.success, row=0)
                    breed_btn.callback = self.breed_all
                    self.add_item(breed_btn)
                    
                    clear_btn = Button(label="🗑️ Clear Pairs", style=ButtonStyle.secondary, row=1)
                    clear_btn.callback = self.clear_pairs
                    self.add_item(clear_btn)
            
            async def add_pair(self, btn_it: discord.Interaction):
                if btn_it.user.id != message.user.id:
                    await do_funny(btn_it)
                    return
                
                # Track parents for this pair
                pair_parents = []
                
                async def parent_selected(sel_it: discord.Interaction, selected_cat: dict):
                    cat_type = selected_cat.get('type')
                    if not cat_type:
                        await sel_it.response.send_message("Invalid cat selected.", ephemeral=True)
                        return
                    
                    pair_parents.append(cat_type)
                    
                    if len(pair_parents) == 1:
                        # First parent selected
                        await sel_it.response.send_message(
                            f"✅ First parent: {get_emoji(cat_type.lower() + 'cat')} **{cat_type}**\n"
                            f"Now select the second parent...",
                            ephemeral=True
                        )
                        
                        # Show selector for second parent
                        selector2 = AdvancedCatSelector(
                            author_id=message.user.id,
                            guild_id=message.guild.id,
                            user_id=message.user.id,
                            all_cats=cats_list,
                            callback_func=parent_selected,
                            title="Select Second Parent"
                        )
                        await sel_it.followup.send("Select second parent:", view=selector2, ephemeral=True)
                    
                    elif len(pair_parents) == 2:
                        # Both parents selected, add to pairs
                        breed_pairs.append((pair_parents[0], pair_parents[1]))
                        
                        pairs_text = "\n".join([
                            f"{i+1}. {get_emoji(p1.lower()+'cat')} {p1} + {get_emoji(p2.lower()+'cat')} {p2}"
                            for i, (p1, p2) in enumerate(breed_pairs)
                        ])
                        
                        await sel_it.response.send_message(
                            f"✅ Added pair: {get_emoji(pair_parents[0].lower()+'cat')} **{pair_parents[0]}** + {get_emoji(pair_parents[1].lower()+'cat')} **{pair_parents[1]}**\n\n"
                            f"**All Pairs ({len(breed_pairs)}):**\n{pairs_text}",
                            ephemeral=True
                        )
                        
                        # Update main view
                        self.update_buttons()
                        try:
                            await message.edit_original_response(view=self)
                        except:
                            pass
                
                # Show selector for first parent
                selector = AdvancedCatSelector(
                    author_id=message.user.id,
                    guild_id=message.guild.id,
                    user_id=message.user.id,
                    all_cats=cats_list,
                    callback_func=parent_selected,
                    title="Select First Parent"
                )
                await btn_it.response.send_message("Select first parent cat:", view=selector, ephemeral=True)
            
            async def breed_all(self, btn_it: discord.Interaction):
                if btn_it.user.id != message.user.id:
                    await do_funny(btn_it)
                    return
                
                if not breed_pairs:
                    await btn_it.response.send_message("No pairs to breed!", ephemeral=True)
                    return
                
                await btn_it.response.defer()
                
                # Verify user still has all cats
                fresh_profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
                
                # Count requirements
                from collections import Counter
                cat_requirements = Counter()
                for p1, p2 in breed_pairs:
                    if p1 == p2:
                        cat_requirements[p1] += 2
                    else:
                        cat_requirements[p1] += 1
                        cat_requirements[p2] += 1
                
                # Check availability
                for cat_type, needed in cat_requirements.items():
                    available = getattr(fresh_profile, f"cat_{cat_type}", 0)
                    if available < needed:
                        await btn_it.followup.send(f"❌ Not enough {cat_type} cats! Need {needed}, have {available}.", ephemeral=True)
                        return
                
                # Perform all breeding
                results = []
                for p1, p2 in breed_pairs:
                    # Consume parents
                    if p1 == p2:
                        fresh_profile[f"cat_{p1}"] -= 2
                    else:
                        fresh_profile[f"cat_{p1}"] -= 1
                        fresh_profile[f"cat_{p2}"] -= 1
                    
                    # Generate offspring
                    offspring = _pick_breed_result(p1, p2)
                    if offspring:
                        fresh_profile[f"cat_{offspring}"] += 1
                        results.append((p1, p2, offspring))
                        
                        try:
                            await auto_sync_cat_instances(fresh_profile, offspring)
                        except Exception:
                            pass
                
                # Track total breeds
                fresh_profile.breeds_total = (fresh_profile.breeds_total or 0) + len(breed_pairs)
                await fresh_profile.save()
                
                # Format results
                result_lines = [
                    f"{get_emoji(p1.lower()+'cat')} {p1} + {get_emoji(p2.lower()+'cat')} {p2} → {get_emoji(off.lower()+'cat')} **{off}**"
                    for p1, p2, off in results
                ]
                
                result_text = "\n".join(result_lines)
                if len(result_text) > 1800:
                    result_text = "\n".join(result_lines[:15]) + f"\n... and {len(results)-15} more!"
                
                await btn_it.followup.send(f"🧬 **Bred {len(results)} pairs!**\n\n{result_text}", ephemeral=False)
                await message.channel.send(f"{message.user.mention} bred {len(results)} pairs of cats!")
                
                # Achievement
                try:
                    await achemb(message, "freak", "send")
                except Exception:
                    pass
                
                # Clear pairs
                breed_pairs.clear()
                self.update_buttons()
                await message.edit_original_response(view=self)
            
            async def clear_pairs(self, btn_it: discord.Interaction):
                if btn_it.user.id != message.user.id:
                    await do_funny(btn_it)
                    return
                
                breed_pairs.clear()
                self.update_buttons()
                await btn_it.response.edit_message(view=self)
        
        breed_embed = discord.Embed(
            title="🧬 Cat Breeding",
            description="Add breeding pairs, then breed them all at once!\n\n"
                       "Click **Add Pair** to select two parent cats.\n"
                       "You can add multiple pairs before breeding.",
            color=Colors.brown
        )
        
        view = BreedView()
        await message.followup.send(embed=breed_embed, view=view)


# --- END: Cat Breeding feature ---

async def reward_vote(user_id: int):
    """Apply vote rewards to all guild profiles for the given user_id.

    This completes the 'vote' quest for any Profile in which the vote quest is available
    (i.e. profile.vote_cooldown == 0). It mirrors the logic from progress(..., quest='vote')
    but runs without a discord interaction.
    """
    print(f"\n{'='*60}", flush=True)
    print(f"[REWARD_VOTE] Starting reward_vote for user {user_id}", flush=True)
    print(f"[REWARD_VOTE] Bot has {len(bot.guilds)} guilds", flush=True)
    
    # Check database connection
    try:
        from database import pool
        if pool is None:
            print(f"[REWARD_VOTE ERROR] Database pool is None - database not connected!", flush=True)
            return
        print(f"[REWARD_VOTE] Database pool status: {pool}", flush=True)
    except Exception as e:
        print(f"[REWARD_VOTE ERROR] Failed to check database pool: {e}", flush=True)
    
    try:
    user_id = message.user.id
    
    profile = await Profile.get_or_create(guild_id=guild_id, user_id=user_id)
    
    # Check if user has at least 2 cats total
    total_cats = sum(getattr(profile, f"cat_{ct}", 0) for ct in cattypes)
    if total_cats < 2:
        await message.followup.send("You need at least 2 cats to breed! Catch more cats first.", ephemeral=True)
        return
    
    breed_pairs = []  # List of (parent1_type, parent2_type)
    
    embed = discord.Embed(
        title="🧬 Bulk Breeding",
        description="Select pairs of cats to breed. Each pair will consume 1 of each parent type and produce offspring.\n\n**How to use:**\n1. Click 'Add Pair' to select cats\n2. Repeat to add more pairs\n3. Click 'Breed All' when ready",
        color=Colors.brown
    )
    
    class BulkBreedView(View):
        def __init__(self, author_id: int):
            super().__init__(timeout=300)
            self.author_id = author_id
            self.update_embed()
        
        def update_embed(self):
            """Update the embed to show current pairs"""
            if breed_pairs:
                pairs_text = "\n".join([
                    f"{i+1}. {get_emoji(p1.lower()+'cat')} {p1} + {get_emoji(p2.lower()+'cat')} {p2}"
                    for i, (p1, p2) in enumerate(breed_pairs)
                ])
                embed.description = f"**Selected Pairs ({len(breed_pairs)}):**\n{pairs_text}\n\nAdd more pairs or breed all!"
            else:
                embed.description = "No pairs selected yet. Click 'Add Pair' to start!"
        
        @discord.ui.button(label="➕ Add Pair", style=ButtonStyle.primary, row=0)
        async def add_pair(self, btn_it: discord.Interaction, button: Button):
            if btn_it.user.id != self.author_id:
                await do_funny(btn_it)
                return
            
            class PairModal(discord.ui.Modal, title="Add Breeding Pair"):
                parent1 = discord.ui.TextInput(
                    label="First Parent Type",
                    placeholder="e.g., Fine, Fire, Divine...",
                    required=True,
                    max_length=20
                )
                parent2 = discord.ui.TextInput(
                    label="Second Parent Type", 
                    placeholder="e.g., Fine, Fire, Divine...",
                    required=True,
                    max_length=20
                )
                
                async def on_submit(modal_self, modal_it: discord.Interaction):
                    p1 = str(modal_self.parent1.value).strip()
                    p2 = str(modal_self.parent2.value).strip()
                    
                    # Find matching cat types (case-insensitive)
                    match1 = next((ct for ct in cattypes if ct.lower() == p1.lower()), None)
                    match2 = next((ct for ct in cattypes if ct.lower() == p2.lower()), None)
                    
                    if not match1 or not match2:
                        await modal_it.response.send_message(f"Invalid cat type(s). Check spelling!", ephemeral=True)
                        return
                    
                    # Check if user has the cats
                    prof_check = await Profile.get_or_create(guild_id=guild_id, user_id=user_id)
                    needed1 = breed_pairs.count((match1, match2)) + breed_pairs.count((match2, match1)) + (2 if match1 == match2 else 1)
                    needed2 = breed_pairs.count((match1, match2)) + breed_pairs.count((match2, match1)) + (0 if match1 == match2 else 1)
                    
                    available1 = getattr(prof_check, f"cat_{match1}", 0)
                    available2 = getattr(prof_check, f"cat_{match2}", 0)
                    
                    if match1 == match2:
                        if available1 < needed1:
                            await modal_it.response.send_message(f"Not enough {match1} cats! Need {needed1}, have {available1}", ephemeral=True)
                            return
                    else:
                        if available1 < needed1 or available2 < needed2:
                            await modal_it.response.send_message(f"Not enough cats! Need {needed1}x {match1} and {needed2}x {match2}", ephemeral=True)
                            return
                    
                    breed_pairs.append((match1, match2))
                    self.update_embed()
                    
                    await modal_it.response.edit_message(embed=embed, view=self)
            
            await btn_it.response.send_modal(PairModal())
        
        @discord.ui.button(label="🧬 Breed All", style=ButtonStyle.success, row=0)
        async def breed_all(self, btn_it: discord.Interaction, button: Button):
            if btn_it.user.id != self.author_id:
                await do_funny(btn_it)
                return
            
            if not breed_pairs:
                await btn_it.response.send_message("No pairs to breed! Add pairs first.", ephemeral=True)
                return
            
            await btn_it.response.defer()
            
            # Verify user still has all cats
            prof_final = await Profile.get_or_create(guild_id=guild_id, user_id=user_id)
            
            # Count requirements
            from collections import Counter
            cat_requirements = Counter()
            for p1, p2 in breed_pairs:
                if p1 == p2:
                    cat_requirements[p1] += 2
                else:
                    cat_requirements[p1] += 1
                    cat_requirements[p2] += 1
            
            # Check availability
            for cat_type, needed in cat_requirements.items():
                available = getattr(prof_final, f"cat_{cat_type}", 0)
                if available < needed:
                    await btn_it.followup.send(f"Not enough {cat_type} cats! Need {needed}, have {available}. Try removing some pairs.", ephemeral=True)
                    return
            
            # Perform all breeding
            results = []
            for p1, p2 in breed_pairs:
                # Consume parents
                if p1 == p2:
                    prof_final[f"cat_{p1}"] -= 2
                else:
                    prof_final[f"cat_{p1}"] -= 1
                    prof_final[f"cat_{p2}"] -= 1
                
                # Generate offspring
                offspring = _pick_breed_result(p1, p2)
                if offspring:
                    prof_final[f"cat_{offspring}"] += 1
                    results.append((p1, p2, offspring))
                    
                    # Auto-sync instance
                    try:
                        await auto_sync_cat_instances(prof_final, offspring)
                    except Exception:
                        pass
            
            # Track total breeds
            prof_final.breeds_total = (prof_final.breeds_total or 0) + len(results)
            await prof_final.save()
            
            # Build result message
            result_lines = [
                f"{get_emoji(p1.lower()+'cat')} {p1} + {get_emoji(p2.lower()+'cat')} {p2} → {get_emoji(off.lower()+'cat')} **{off}**"
                for p1, p2, off in results
            ]
            
            result_embed = discord.Embed(
                title="🧬 Bulk Breeding Complete!",
                description=f"**Bred {len(results)} pairs:**\n" + "\n".join(result_lines),
                color=Colors.green
            )
            
            await btn_it.followup.send(embed=result_embed)
            
            # Quest progress
            try:
                for _ in range(len(results)):
                    for extra_key in ("breed3", "breed5"):
                        try:
                            await progress(message, prof_final, extra_key)
                        except Exception:
                            pass
            except Exception:
                pass
            
            # Clear pairs and disable buttons
            breed_pairs.clear()
            for item in self.children:
                item.disabled = True
            await btn_it.edit_original_response(view=self)
        
        @discord.ui.button(label="❌ Clear All", style=ButtonStyle.secondary, row=0)
        async def clear_all(self, btn_it: discord.Interaction, button: Button):
            if btn_it.user.id != self.author_id:
                await do_funny(btn_it)
                return
            
            breed_pairs.clear()
            self.update_embed()
            await btn_it.response.edit_message(embed=embed, view=self)
        
        @discord.ui.button(label="🗑️ Remove Last", style=ButtonStyle.danger, row=1)
        async def remove_last(self, btn_it: discord.Interaction, button: Button):
            if btn_it.user.id != self.author_id:
                await do_funny(btn_it)
                return
            
            if breed_pairs:
                breed_pairs.pop()
                self.update_embed()
            
            await btn_it.response.edit_message(embed=embed, view=self)
    
    view = BulkBreedView(user_id)
    await message.followup.send(embed=embed, view=view)


# --- END: Cat Breeding feature ---

async def reward_vote(user_id: int):
    """Apply vote rewards to all guild profiles for the given user_id.

    This completes the 'vote' quest for any Profile in which the vote quest is available
    (i.e. profile.vote_cooldown == 0). It mirrors the logic from progress(..., quest='vote')
    but runs without a discord interaction.
    """
    print(f"\n{'='*60}", flush=True)
    print(f"[REWARD_VOTE] Starting reward_vote for user {user_id}", flush=True)
    print(f"[REWARD_VOTE] Bot has {len(bot.guilds)} guilds", flush=True)
    
    # Check database connection
    try:
        from database import pool
        if pool is None:
            print(f"[REWARD_VOTE ERROR] Database pool is None - database not connected!", flush=True)
            return
        print(f"[REWARD_VOTE] Database pool status: {pool}", flush=True)
    except Exception as e:
        print(f"[REWARD_VOTE ERROR] Failed to check database pool: {e}", flush=True)
    
    try:
        print(f"[REWARD_VOTE] Attempting User.get_or_create for user_id={user_id}", flush=True)
        global_user = await User.get_or_create(user_id=user_id)
        print(f"[REWARD_VOTE] ✅ Got global user object: {global_user}", flush=True)
        print(f"[REWARD_VOTE] User vote_time_topgg: {getattr(global_user, 'vote_time_topgg', 'N/A')}", flush=True)
        print(f"[REWARD_VOTE] User vote_streak: {getattr(global_user, 'vote_streak', 'N/A')}", flush=True)
    except Exception as e:
        print(f"[REWARD_VOTE ERROR] Failed to get user {user_id}: {type(e).__name__}: {e}", flush=True)
        logging.exception(f"Failed to get user {user_id}")
        import traceback
        traceback.print_exc()
        return

    rewards_given = 0
    guilds_processed = []
    total_xp_given = 0
    packs_given = []
    
    # iterate servers the bot is in and apply to each Profile for this user
    for guild in list(bot.guilds):
        try:
            profile = await Profile.get_or_create(guild_id=guild.id, user_id=user_id)
            print(f"[REWARD_VOTE] Processing guild: {guild.name} (ID: {guild.id})", flush=True)

            # Generate vote reward (300 base XP, doubled on Fri/Sat/Sun)
            base_xp = 300
            try:
                qdata = battle.get("quests", {}).get("third", {}).get("third", {})
                base_xp = random.randint(qdata.get("xp_min", 250) // 10, qdata.get("xp_max", 350) // 10) * 10
            except Exception:
                base_xp = 300
            
            profile.vote_reward = base_xp

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
            rewards_given += 1
            total_xp_given += profile.vote_reward
            guilds_processed.append(guild.name)
            print(f"[REWARD_VOTE] Giving {profile.vote_reward} XP to user {user_id} in guild {guild.name} (ID: {guild.id})", flush=True)
            
            # Track streak pack rewards for DM
            try:
                streak_data = get_streak_reward(global_user.vote_streak)
                if streak_data.get("reward") and streak_data["reward"] not in packs_given:
                    packs_given.append(streak_data["reward"])
            except Exception:
                pass

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
                                # Auto-sync instance for cat rewards
                                await auto_sync_cat_instances(profile, active_level_data['reward'])
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
            
            # Set cooldown AFTER giving rewards (for tracking, not blocking)
            try:
                profile.vote_cooldown = int(global_user.vote_time_topgg or int(time.time()))
                await profile.save()
            except Exception:
                pass

        except Exception as e:
            # per-guild failure shouldn't stop others
            print(f"[REWARD_VOTE ERROR] Failed to process guild {guild.id}: {e}", flush=True)
            logging.exception(f"Failed to process guild {guild.id}")
            continue
    
    print(f"[REWARD_VOTE] ✅ Completed! Gave rewards to {rewards_given} servers for user {user_id}", flush=True)
    print(f"[REWARD_VOTE] Total XP given: {total_xp_given}", flush=True)
    print(f"{'='*60}\n", flush=True)
    
    # Send DM to user with reward details
    if rewards_given > 0:
        try:
            discord_user = await bot.fetch_user(user_id)
            if discord_user:
                # Check if weekend bonus applied
                is_weekend = datetime.datetime.now().weekday() >= 4  # Fri/Sat/Sun
                weekend_text = " (Weekend Bonus! 🎉)" if is_weekend else ""
                
                # Build reward message
                xp_per_server = total_xp_given // rewards_given if rewards_given > 0 else 0
                dm_message = f"🎉 **Thank you for voting!**{weekend_text}\n\n"
                dm_message += f"**Rewards Given:**\n"
                dm_message += f"✨ {xp_per_server} Battlepass XP per server ({rewards_given} server{'s' if rewards_given > 1 else ''})\n"
                dm_message += f"📊 Total: {total_xp_given} XP\n"
                
                # Add pack rewards if any
                if packs_given:
                    dm_message += f"📦 Pack{'s' if len(packs_given) > 1 else ''}: {', '.join(packs_given)}\n"
                
                # Add streak info
                try:
                    streak = getattr(global_user, 'vote_streak', 0)
                    if streak:
                        dm_message += f"\n🔥 **Vote Streak:** {streak}\n"
                        next_reward = ((streak // 7) + 1) * 7
                        dm_message += f"Next streak reward at {next_reward} votes!\n"
                except Exception:
                    pass
                
                dm_message += f"\nYou can vote again <t:{int(time.time()) + 43200}:R>."
                
                await discord_user.send(dm_message)
                print(f"[REWARD_VOTE] ✅ Sent DM to user {user_id}", flush=True)
        except discord.Forbidden:
            print(f"[REWARD_VOTE] ⚠️ Cannot DM user {user_id} (DMs closed)", flush=True)
        except Exception as e:
            print(f"[REWARD_VOTE ERROR] Failed to DM user {user_id}: {e}", flush=True)
    
    # Log to the channel after completing rewards
    try:
        await log_vote_to_channel(user_id, source="reward_vote")
    except Exception as e:
        print(f"[REWARD_VOTE ERROR] Failed to log to channel: {e}", flush=True)
        logging.exception("Failed to log vote to channel")


# --- Extra quest runtime support (non-DB, lightweight) ---
# Tracks ephemeral progress for multi-step extra quests (breed counts).
EXTRA_PROGRESS: dict = {}  # key: (user_id, quest_key) -> int
EXTRA_COMPLETED: set = set()


def _extra_key(user_id: int, quest_key: str) -> tuple:
    return (int(user_id), str(quest_key))


async def _apply_xp_to_profile(profile, xp: int):
    """Apply XP to a Profile and handle level-ups (battlepass) similarly to progress/reward_vote.
    This mirrors the level-up loop used elsewhere but keeps the behavior local.
    """
    try:
        current_xp = (profile.progress or 0) + int(xp or 0)
    except Exception:
        current_xp = int(xp or 0)

    profile.quests_completed = (profile.quests_completed or 0) + 1

    try:
        if profile.battlepass >= len(battle.get("seasons", {}).get(str(profile.season), [])):
            level_data = {"xp": 1500, "reward": "Stone", "amount": 1}
        else:
            level_data = battle["seasons"][str(profile.season)][profile.battlepass]
    except Exception:
        level_data = {"xp": 1500, "reward": "Stone", "amount": 1}

    try:
        if current_xp >= level_data["xp"]:
            xp_progress = current_xp
            active_level_data = level_data
            while xp_progress >= active_level_data["xp"]:
                profile.battlepass += 1
                xp_progress -= active_level_data["xp"]
                profile.progress = xp_progress
                try:
                    if active_level_data["reward"] == "Rain":
                        profile.rain_minutes = (profile.rain_minutes or 0) + active_level_data["amount"]
                    elif active_level_data["reward"] in [p["name"] for p in pack_data]:
                        profile[f"pack_{active_level_data['reward'].lower()}"] += active_level_data["amount"]
                    elif active_level_data["reward"] in cattypes:
                        profile[f"cat_{active_level_data['reward']}"] += active_level_data["amount"]
                        # Auto-sync instance for cat rewards
                        await auto_sync_cat_instances(profile, active_level_data['reward'])
                except Exception:
                    pass
                try:
                    await profile.save()
                except Exception:
                    pass
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


async def award_extra_quest(profile, source_context, quest_key: str):
    """Grant the configured extra quest reward if not already completed for this user.
    - profile: Profile instance (guild-level)
    - source_context: discord.Message or discord.Interaction (optional) for permission checking
    - quest_key: key under battle['quests']['extra']
    """
    # Prefer persistent extra quest flow: only award if this profile currently
    # has the given extra quest active and it's available.
    try:
        await profile.refresh_from_db()
    except Exception:
        pass

    if getattr(profile, "extra_quest", "") != quest_key:
        return False
    if getattr(profile, "extra_cooldown", 1) != 0:
        return False

    qdata = battle.get("quests", {}).get("extra", {}).get(quest_key)
    if not qdata:
        return False

    # Prefer using configured user reward if present
    reward = getattr(profile, "extra_reward", None)
    if not reward:
        reward = random.randint(qdata.get("xp_min", 100) // 10, qdata.get("xp_max", 200) // 10) * 10

    # mark as completed and set cooldown like other quests
    profile.extra_cooldown = int(time.time())
    profile.extra_progress = 0
    try:
        await _apply_xp_to_profile(profile, reward)
    except Exception:
        try:
            profile.progress = (profile.progress or 0) + reward
            await profile.save()
        except Exception:
            pass

    EXTRA_COMPLETED.add(_extra_key(profile.user_id, quest_key))
    return True


async def log_vote_to_channel(user_id: int, source: str = "unknown"):
    """Send a short log message to the configured cat log channel (uses RAIN_CHANNEL_ID).

    This is intentionally defensive: it won't raise if the channel is missing or the bot
    lacks permissions.
    """
    print(f"[LOG_VOTE] log_vote_to_channel called for user {user_id}, source: {source}", flush=True)
    try:
        chan_id = int(getattr(config, "RAIN_CHANNEL_ID", 0) or 0)
        print(f"[LOG_VOTE] RAIN_CHANNEL_ID: {chan_id}", flush=True)
        if not chan_id:
            print(f"[LOG_VOTE] No RAIN_CHANNEL_ID configured, skipping", flush=True)
            return
        ch = None
        try:
            ch = bot.get_channel(chan_id)
            print(f"[LOG_VOTE] bot.get_channel result: {ch}", flush=True)
        except Exception as e:
            print(f"[LOG_VOTE] bot.get_channel failed: {e}", flush=True)
            ch = None
        if ch is None:
            try:
                print(f"[LOG_VOTE] Trying bot.fetch_channel...", flush=True)
                ch = await bot.fetch_channel(chan_id)
                print(f"[LOG_VOTE] bot.fetch_channel result: {ch}", flush=True)
            except Exception as e:
                print(f"[LOG_VOTE] bot.fetch_channel failed: {e}", flush=True)
                ch = None
        if ch is None:
            print(f"[LOG_VOTE] Channel {chan_id} not found, cannot send log", flush=True)
            return

        text = f"🎉 Vote received: <@{user_id}> (ID: {user_id}) — source: {source}"
        print(f"[LOG_VOTE] Attempting to send message to channel {ch.name} ({ch.id})", flush=True)
        try:
            msg = await ch.send(text)
            print(f"[LOG_VOTE] ✅ Message sent successfully! Message ID: {msg.id}", flush=True)
        except Exception as e:
            print(f"[LOG_VOTE] Failed to send message: {e}", flush=True)
            # fallback: attempt to send a shorter message
            try:
                msg = await ch.send(f"Vote received: {user_id} — {source}")
                print(f"[LOG_VOTE] ✅ Fallback message sent! Message ID: {msg.id}", flush=True)
            except Exception as e2:
                print(f"[LOG_VOTE] Fallback also failed: {e2}", flush=True)
    except Exception as e:
        print(f"[LOG_VOTE ERROR] Unhandled exception: {e}", flush=True)
        logging.exception("Unhandled exception in log_vote_to_channel")
