# Catnip System Module
# Handles the dynamic bounty/mafia level system with perks and difficulty scaling
# to be imported and integrated into main.py

import asyncio
import json
import logging
import math
import os
import random
import time
from typing import List, Dict, Optional

# This should be passed from main.py or loaded locally
catnip_list = {}
cattypes = []  # Will be set from main.py
type_dict = {}  # Will be set from main.py
get_emoji = None  # Will be set from main.py

def set_catnip_context(cat_types: List[str], type_dictionary: Dict, emoji_func):
    """Set context variables from main.py"""
    global cattypes, type_dict, get_emoji
    cattypes = cat_types
    type_dict = type_dictionary
    get_emoji = emoji_func

def load_catnip_config(config_path: str = "config/catnip.json"):
    """Load catnip configuration from file"""
    global catnip_list
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            catnip_list = json.load(f)
        logging.info(f"Loaded catnip config with {len(catnip_list.get('levels', []))} levels and {len(catnip_list.get('perks', []))} perks")
        return True
    except Exception as e:
        logging.error(f"Failed to load catnip.json: {e}")
        return False

async def bounty(message, user, cattype):
    """Track bounty progress for the user when they catch a cat"""
    if user.hibernation:
        return
    
    complete = 0
    completed = 0
    title = []
    colored = 0
    
    # Process main bounties (3 total)
    for i in range(user.bounties):
        if i == 0:
            id = user.bounty_id_one
            progress = user.bounty_progress_one
            total = user.bounty_total_one
            type = user.bounty_type_one
        elif i == 1:
            id = user.bounty_id_two
            progress = user.bounty_progress_two
            total = user.bounty_total_two
            type = user.bounty_type_two
        else:  # i == 2
            id = user.bounty_id_three
            progress = user.bounty_progress_three
            total = user.bounty_total_three
            type = user.bounty_type_three
        
        if progress < total:
            if id == 0:  # Catch any cats
                progress += 1
                if progress == total:
                    complete += 1
                    title.append(f"Catch {total} cats")
            elif id == 1:  # Catch specific cat
                if cattype == type:
                    progress += 1
                    if progress == total:
                        complete += 1
                        title.append(f"Catch {total} {type} cats")
            elif id == 2:  # Catch rarity or higher
                try:
                    if cattypes.index(cattype) >= cattypes.index(type):
                        progress += 1
                        if progress == total:
                            complete += 1
                            title.append(f"Catch {total} {type} or rarer cats")
                except (ValueError, IndexError):
                    pass
        
        # Update bounty progress
        if i == 0:
            user.bounty_progress_one = progress
            if progress == total:
                completed += 1
        elif i == 1:
            user.bounty_progress_two = progress
            if progress == total:
                completed += 1
        else:
            user.bounty_progress_three = progress
            if progress == total:
                completed += 1
    
    await user.save()
    
    # Handle bonus bounty
    if catnip_list.get("levels", []) and user.catnip_level < len(catnip_list["levels"]):
        if catnip_list["levels"][user.catnip_level].get("bonus"):
            bonus_title = ""
            if user.bounty_progress_bonus < user.bounty_total_bonus:
                if user.bounty_id_bonus == 0:
                    user.bounty_progress_bonus += 1
                    bonus_title = f"Catch {user.bounty_total_bonus} cats"
                elif user.bounty_id_bonus == 1:
                    if cattype == user.bounty_type_bonus:
                        user.bounty_progress_bonus += 1
                    bonus_title = f"Catch {user.bounty_total_bonus} {cattype} cats"
                else:
                    try:
                        if cattypes.index(cattype) >= cattypes.index(user.bounty_type_bonus):
                            user.bounty_progress_bonus += 1
                    except (ValueError, IndexError):
                        pass
                    bonus_title = f"Catch {user.bounty_total_bonus} {user.bounty_type_bonus} or rarer cats"
                
                if user.bounty_progress_bonus == user.bounty_total_bonus:
                    description = "Bonus Bounty Complete!\nGo to `/catnip` to reroll a perk!"
                    # You'd send this as an embed to message.channel
                    user.reroll = False
                    user.reroll_level = 0
                
                await user.save()
    
    # Send bounty completion messages
    for i in range(complete):
        logging.debug(f"Completed bounties {completed}")
        level = user.catnip_level
        colored = int(completed / user.bounties * 10) if user.bounties > 0 else 0
        progress_line = f"\n{level} " + (get_emoji("staring_square") if get_emoji else "█") * int(colored) + "⬛" * int(10 - colored) + f" {level + 1}"
        
        if completed == user.bounties:
            description = f"{progress_line}\nAll Bounties Complete!\nGo to `/catnip` to pay up and pick a perk!"
        else:
            description = f"{progress_line}\n{completed}/{user.bounties} Bounties Complete"
        
        # Log for now (would be sent as embed to message.channel in actual implementation)
        logging.info(f"✅ {title[i]}")

async def set_mafia_offer(level: int, user):
    """Set the cost for advancing to the next catnip level"""
    if user.catnip_level == 0:
        user.catnip_amount = 0
        return
    
    if not catnip_list.get("levels") or level >= len(catnip_list["levels"]):
        return
    
    level_data = catnip_list["levels"][level]
    vt = level_data.get("cost", 100)
    
    # Find a cat type that matches the value threshold
    cattype = "Fine"
    for _ in range(100):
        cattype = random.choice(cattypes)
        value = sum(type_dict.values()) / type_dict.get(cattype, 1) if type_dict.get(cattype) else 1
        if value <= vt:
            break
    
    amount = max(1, round(vt / (sum(type_dict.values()) / type_dict.get(cattype, 1))))
    user.catnip_price = cattype
    user.catnip_amount = amount
    await user.save()

async def set_bounties(level: int, user):
    """Generate and set random bounties for a catnip level"""
    if user.catnip_level == 0:
        user.bounties = 0
        return
    
    bounties = await get_bounties(level)
    
    # Check if there's a bonus bounty for the next level
    bonus_check = False
    if catnip_list.get("levels") and level + 1 < len(catnip_list["levels"]):
        bonus_check = catnip_list["levels"][level + 1].get("bonus", False)
    
    if level == 10 and user.bounty_progress_bonus != user.bounty_total_bonus and user.catnip_active > 86400:
        bonus_check = False
    
    if bonus_check:
        bonus = bounties.pop() if bounties else None
        if bonus:
            user.bounty_id_bonus = bonus.get("id", 0)
            user.bounty_type_bonus = bonus.get("cat_type", "")
            user.bounty_total_bonus = bonus.get("amount", 1)
            user.bounty_progress_bonus = bonus.get("progress", 0)
    else:
        bounties = bounties[:-1] if bounties else []
    
    user.bounties = len(bounties)
    
    user.bounty_id_one = bounties[0].get("id") if len(bounties) > 0 else None
    user.bounty_id_two = bounties[1].get("id") if len(bounties) > 1 else None
    user.bounty_id_three = bounties[2].get("id") if len(bounties) > 2 else None
    
    user.bounty_type_one = bounties[0].get("cat_type") if len(bounties) > 0 else None
    user.bounty_type_two = bounties[1].get("cat_type") if len(bounties) > 1 else None
    user.bounty_type_three = bounties[2].get("cat_type") if len(bounties) > 2 else None
    
    user.bounty_total_one = bounties[0].get("amount", 1) if len(bounties) > 0 else 1
    user.bounty_total_two = bounties[1].get("amount", 1) if len(bounties) > 1 else 1
    user.bounty_total_three = bounties[2].get("amount", 1) if len(bounties) > 2 else 1
    
    user.bounty_progress_one = bounties[0].get("progress", 0) if len(bounties) > 0 else 0
    user.bounty_progress_two = bounties[1].get("progress", 0) if len(bounties) > 1 else 0
    user.bounty_progress_three = bounties[2].get("progress", 0) if len(bounties) > 2 else 0
    
    await user.save()

async def get_bounties(level: int) -> List[Dict]:
    """Generate random bounties for a level with difficulty scaling"""
    if not catnip_list.get("levels") or level >= len(catnip_list["levels"]):
        return []
    
    level_data = catnip_list["levels"][level + 1] if level + 1 < len(catnip_list["levels"]) else catnip_list["levels"][level]
    bounties = []
    num_bounties = level_data.get("bounty_amount", 3)
    avg_cats_needed = level_data.get("bounty_difficulty", 10)
    num_max = level_data.get("max_amount", 50)
    
    used_types = set()
    used_rarities = set()
    tries = 0
    max_tries = 1000 * num_bounties
    
    while len(bounties) < num_bounties + 1 and tries < max_tries:
        tries += 1
        bounty_type = random.choice(["rarity", "specific", "any"])
        
        variation = random.uniform(0.85, 1.15)
        if len(bounties) == num_bounties:
            variation *= 1.5
            if level == 10:
                variation *= 10
        
        if bounty_type == "rarity":
            margin = 0.2
            rarity_i = random.randint(2, len(cattypes) - 2) if len(cattypes) > 2 else 1
            
            while True:
                rarity = cattypes[rarity_i] if rarity_i < len(cattypes) else cattypes[-1]
                eligible_types = cattypes[rarity_i:]
                
                prob = sum(type_dict.get(t, 0) for t in eligible_types) / sum(type_dict.values()) if sum(type_dict.values()) > 0 else 0
                base_amount = max(1, round(avg_cats_needed * prob)) if prob > 0 else 1
                expected_total = base_amount / prob if prob > 0 else float("inf")
                
                if abs(expected_total - avg_cats_needed) / avg_cats_needed <= margin or rarity_i == 0:
                    break
                rarity_i -= 1
            
            if rarity_i in used_rarities:
                continue
            
            used_rarities.add(rarity_i)
            amount = max(1, round(base_amount * variation))
            
            if amount > num_max:
                continue
            
            bounties.append({"id": 2, "progress": 0, "cat_type": rarity, "amount": amount, "desc": f"Catch {amount} cats of {rarity} rarity and above"})
        
        elif bounty_type == "any":
            if any(b.get("id") == 0 for b in bounties):
                continue
            
            amount = max(1, round(avg_cats_needed * variation / 2))
            if amount > num_max:
                continue
            
            bounties.append({"id": 0, "progress": 0, "cat_type": "", "amount": amount, "desc": f"Catch {amount} cats of any kind"})
        
        else:  # specific
            available_types = [cat for cat in cattypes if cat not in used_types]
            if not available_types:
                continue
            
            available_types1 = available_types.copy()
            cat_type = random.choice(available_types1) if available_types1 else "Fine"
            prob = type_dict.get(cat_type, 100) / sum(type_dict.values()) if sum(type_dict.values()) > 0 else 0
            base_amount = avg_cats_needed * prob if prob > 0 else 1
            
            amount = max(1, round(base_amount * variation))
            if amount > num_max:
                continue
            
            used_types.add(cat_type)
            bounties.append({"id": 1, "progress": 0, "cat_type": cat_type, "amount": amount, "desc": f"Catch {amount} {cat_type} cats"})
    
    return bounties

async def get_perks(level: int, user) -> List[Dict]:
    """Generate 3 random perks for a catnip level"""
    if not catnip_list.get("levels") or level >= len(catnip_list["levels"]):
        return []
    
    level_data = catnip_list["levels"][level]
    rarities = list(level_data.get("weights", {}).keys())
    weights = {rarity: level_data.get("weights", {}).get(rarity, 0) for rarity in rarities}
    perks_data = catnip_list.get("perks", [])
    
    current_perks = []
    used_ids = set()
    thelist = []
    
    if user.perks:
        for perk in user.perks:
            p = perk.split("_")
            if len(p) >= 2:
                try:
                    thelist.append(perks_data[int(p[1]) - 1].get("id") if int(p[1]) - 1 < len(perks_data) else "unknown")
                except (ValueError, IndexError):
                    pass
    
    for _ in range(3):
        luck = random.randint(1, 1000) / 10
        total_weight = 0
        current_rarity = "common"
        
        for rarity, weight in weights.items():
            total_weight += weight
            if luck <= total_weight:
                current_rarity = rarity
                break
        
        tries = 0
        selected_perk = None
        
        while tries < 100:
            luck = random.randint(1, 100)
            total_weight = 0
            i = 0
            
            for perk in perks_data:
                i += 1
                total_weight += perk.get("weight", 0)
                
                if perk.get("id") in used_ids or (perk.get("exclusive") == 1 and perk.get("id") in thelist):
                    continue
                
                if all("pack" in p.get("id", "") for p in current_perks) and "pack" in perk.get("id", ""):
                    continue
                
                if luck <= total_weight:
                    rarity_idx = list(weights.keys()).index(current_rarity) if current_rarity in weights else 0
                    effect = perk.get("values", [])[rarity_idx] if rarity_idx < len(perk.get("values", [])) else 0
                    
                    if effect == 0:
                        continue
                    
                    selected_perk = {
                        "id": perk.get("id"),
                        "name": perk.get("name"),
                        "values": perk.get("values"),
                        "rarity": current_rarity,
                        "uuid": f"{rarity_idx}_{i}",
                        "effect": effect,
                    }
                    break
            
            if selected_perk:
                break
            tries += 1
        
        if selected_perk:
            used_ids.add(selected_perk["id"])
            current_perks.append(selected_perk)
    
    return current_perks

async def level_down(user, message=None, ephemeral: bool = False):
    """Handle a catnip level failure (timeout or bounty failure)"""
    if user.catnip_level == 0:
        return None
    
    user.catnip_level -= 1
    user.catnip_active = 0
    user.hibernation = True
    
    # Clear bounties
    for number in ["one", "two", "three"]:
        setattr(user, f"bounty_id_{number}", 0)
        setattr(user, f"bounty_type_{number}", "")
        setattr(user, f"bounty_total_{number}", 1)
        setattr(user, f"bounty_progress_{number}", 0)
    
    user.catnip_total_cats = 0
    user.bounty_active = False
    user.first_quote_seen = False
    
    # Remove last perk
    removed_perk = None
    if user.perks:
        h = list(user.perks)
        removed_perk = h.pop()
        user.perks = h[:]
    
    await set_bounties(user.catnip_level, user)
    await set_mafia_offer(user.catnip_level, user)
    await user.save()
    
    # Get quote
    name = "Unknown"
    quote = "Your catnip ran out..."
    
    if catnip_list.get("quotes") and user.catnip_level < len(catnip_list["quotes"]):
        quote_data = catnip_list["quotes"][user.catnip_level]
        name = quote_data.get("name", "Unknown")
        quote = quote_data.get("quotes", {}).get("leveldown", quote)
    
    removed_line = ""
    if user.perks and removed_perk:
        rarities = ["Common", "Uncommon", "Rare", "Epic", "Legendary"]
        try:
            perk_rarity = int(removed_perk.split("_")[0])
            perk_type = int(removed_perk.split("_")[1])
            if perk_type - 1 < len(catnip_list.get("perks", [])):
                perk_data = catnip_list["perks"][perk_type - 1]
                removed_line = f"\nYou lost your **{perk_data.get('name', 'Unknown')} ({rarities[perk_rarity]})** perk."
        except (ValueError, IndexError):
            pass
    
    description = f"**{name}**: *{quote}*\n\nLevel {user.catnip_level + 1} bounties failed!\nYou're now on level {user.catnip_level}.{removed_line}"
    
    logging.debug(f"Levelled down to {user.catnip_level}")
    
    return {
        "title": "❌ Mafia Level Failed",
        "description": description,
        "color": 0xFF0000  # Red
    }
