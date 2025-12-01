# Christmas Update Features - December 1st, 2025
# This file contains all Christmas features to be integrated into main.py

import discord
import datetime
import time
from database import Profile

# NOTE: achemb() function is imported from main.py at runtime
# It's called in advent_command() and update_naughty_score()
# Make sure main.py imports from this module AFTER defining achemb

# Suppress undefined name warnings for achemb - it comes from main.py
achemb = None  # type: ignore

# =============================================================================
# DATABASE MIGRATIONS
# =============================================================================

"""
-- Add Christmas event tracking to profile table
ALTER TABLE public.profile 
ADD COLUMN advent_claimed TEXT DEFAULT '',  -- Comma-separated days claimed (e.g. "1,2,3")
ADD COLUMN advent_last_claim BIGINT DEFAULT 0,
ADD COLUMN naughty_score INTEGER DEFAULT 0,  -- Increases with stealing, etc.
ADD COLUMN nice_score INTEGER DEFAULT 0,  -- Increases with gifting, helping
ADD COLUMN santa_banned BOOLEAN DEFAULT false,  -- If true, no advent rewards
ADD COLUMN pack_festive INTEGER DEFAULT 0;

-- Add Christmas achievements
ALTER TABLE public.profile
ADD COLUMN christmas_spirit BOOLEAN DEFAULT false,  -- Catch 25 festive cats
ADD COLUMN advent_master BOOLEAN DEFAULT false,  -- Claim all 25 days
ADD COLUMN gift_giver BOOLEAN DEFAULT false,  -- Gift 10 cats during December
ADD COLUMN nice_list BOOLEAN DEFAULT false,  -- Maintain nice_score > naughty_score
ADD COLUMN naughty_list BOOLEAN DEFAULT false,  -- Get banned by Santa
ADD COLUMN festive_collector BOOLEAN DEFAULT false,  -- Open 50 festive packs
ADD COLUMN tree_decorated BOOLEAN DEFAULT false;  -- Completed the Christmas tree

-- Add Christmas tree decoration tracking
ALTER TABLE public.profile
ADD COLUMN tree_ornaments TEXT DEFAULT '',  -- Comma-separated ornament IDs collected (e.g. "1,3,5")
ADD COLUMN tree_ornament_count INTEGER DEFAULT 0;  -- Number of ornaments collected (0-8)

CREATE INDEX idx_profile_advent ON public.profile USING btree (advent_last_claim);
CREATE INDEX idx_profile_naughty_nice ON public.profile USING btree (naughty_score, nice_score);
"""

# =============================================================================
# CHRISTMAS COSMETICS DATA
# =============================================================================

CHRISTMAS_COSMETICS = {
    "badges": {
        "santa_hat": {
            "name": "🎅 Santa Hat",
            "description": "Ho ho ho!",
            "price": 500,
            "requirement": None
        },
        "snowflake": {
            "name": "❄️ Snowflake",
            "description": "Unique and special",
            "price": 750,
            "requirement": None
        },
        "candy_cane": {
            "name": "🍬 Candy Cane",
            "description": "Sweet and festive",
            "price": 600,
            "requirement": None
        },
        "advent_star": {
            "name": "⭐ Advent Star",
            "description": "Completed the advent calendar",
            "price": 0,
            "requirement": "advent_master"
        },
        "nice_badge": {
            "name": "😇 Nice List",
            "description": "Santa approves of you!",
            "price": 0,
            "requirement": "nice_list"
        },
        "naughty_badge": {
            "name": "😈 Naughty List",
            "description": "Coal for you!",
            "price": 0,
            "requirement": "naughty_list"
        }
    },
    "titles": {
        "santa_title": {
            "name": "Santa's Helper",
            "description": "Spreading Christmas cheer",
            "price": 1000,
            "requirement": None
        },
        "elf_title": {
            "name": "Head Elf",
            "description": "Master of the workshop",
            "price": 1500,
            "requirement": None
        },
        "gift_giver_title": {
            "name": "Gift Giver",
            "description": "Generous spirit",
            "price": 0,
            "requirement": "gift_giver"
        },
        "festive_title": {
            "name": "Festive Collector",
            "description": "Christmas cat enthusiast",
            "price": 0,
            "requirement": "festive_collector"
        },
        "scrooge_title": {
            "name": "Scrooge",
            "description": "Bah humbug!",
            "price": 0,
            "requirement": "naughty_list"
        }
    },
    "colors": {
        "christmas_red": {
            "name": "Christmas Red",
            "description": "🎄 Festive red color",
            "hex": "#C41E3A",
            "price": 800,
            "requirement": None
        },
        "christmas_green": {
            "name": "Christmas Green",
            "description": "🎄 Festive green color",
            "hex": "#0F8A5F",
            "price": 800,
            "requirement": None
        },
        "snow_white": {
            "name": "Snow White",
            "description": "❄️ Pure white snow",
            "hex": "#FFFAFA",
            "price": 1000,
            "requirement": None
        },
        "gold_star": {
            "name": "Gold Star",
            "description": "⭐ Shining gold",
            "hex": "#FFD700",
            "price": 1200,
            "requirement": None
        }
    },
    "effects": {
        "snowfall": {
            "name": "Snowfall",
            "description": "❄️ Let it snow!",
            "emoji": "❄️",
            "price": 2000,
            "requirement": None
        },
        "presents": {
            "name": "Presents",
            "description": "🎁 Wrapped with care",
            "emoji": "🎁",
            "price": 2500,
            "requirement": None
        },
        "christmas_lights": {
            "name": "Christmas Lights",
            "description": "💡 Twinkling lights",
            "emoji": "💡",
            "price": 3000,
            "requirement": None
        }
    }
}

# =============================================================================
# CHRISTMAS ACHIEVEMENTS
# =============================================================================

CHRISTMAS_ACHIEVEMENTS = {
    "christmas_spirit": {
        "title": "Christmas Spirit",
        "display": "🎄 Christmas Spirit",
        "description": "Catch 10 festive cats during the holiday season",
        "reward": "Festive badge, +5,000 Kibbles, Festive Pack x3"
    },
    "advent_master": {
        "title": "Advent Master",
        "display": "📅 Advent Master",
        "description": "Claim all 25 days of the advent calendar",
        "reward": "Advent Star badge, +10,000 Kibbles, Celestial Pack x2"
    },
    "gift_giver": {
        "title": "Gift Giver",
        "display": "🎁 Gift Giver",
        "description": "Gift 5 cats to other players during December",
        "reward": "Gift Giver title, +3,000 Kibbles"
    },
    "nice_list": {
        "title": "Nice List",
        "display": "😇 Nice List",
        "description": "Maintain a positive nice/naughty ratio throughout December",
        "reward": "Nice List badge, +5,000 Kibbles"
    },
    "naughty_list": {
        "title": "Naughty List",
        "display": "😈 Naughty List",
        "description": "Get banned from Santa's presents due to stealing",
        "reward": "Naughty badge and Scrooge title (coal for you!)"
    },
    "festive_collector": {
        "title": "Festive Collector",
        "display": "🎅 Festive Collector",
        "description": "Open 50 festive packs",
        "reward": "Festive Collector title, +15,000 Kibbles, Celestial Pack x5"
    }
}

# =============================================================================
# ADVENT CALENDAR COMMAND
# =============================================================================

ADVENT_REWARDS = {
    1: {"kibble": 500, "packs": {"festive": 1}, "message": "🎄 Day 1: Welcome to the advent calendar!"},
    2: {"kibble": 600, "packs": {"festive": 1}, "message": "❄️ Day 2: the snow is falling :O"},
    3: {"kibble": 700, "packs": {"festive": 2}, "message": "🎅 Day 3: santa is checking the list!!!11!!"},
    4: {"kibble": 800, "packs": {"festive": 2}, "message": "🎁 Day 4: time to wrap those presents :D"},
    5: {"kibble": 1000, "packs": {"festive": 3}, "message": "⭐ Day 5: five golden stars!!!!!"},
    6: {"kibble": 1200, "packs": {"festive": 2}, "message": "🔔 Day 6: ding dong bell ring!"},
    7: {"kibble": 1400, "packs": {"festive": 3}, "message": "🕯️ Day 7: week complete, w cat!"},
    8: {"kibble": 1600, "packs": {"festive": 3}, "message": "🎶 Day 8: jamming cat is practicing carols"},
    9: {"kibble": 1800, "packs": {"festive": 4}, "message": "🍪 Day 9: chef cat is making cookies hell yeah!"},
    10: {"kibble": 2000, "packs": {"festive": 4}, "message": "🎄 Day 10: time to decorate christmas tree cat!"},
    11: {"kibble": 2200, "packs": {"festive": 4}, "message": "❄️ Day 11: construct snowman cat :D"},
    12: {"kibble": 2500, "packs": {"festive": 5}, "message": "🎅 Day 12: santa cat has workshop tours open"},
    13: {"kibble": 2800, "packs": {"festive": 5}, "message": "🦌 Day 13: the reindeers are having a party??!?!?!?!"},
    14: {"kibble": 3000, "packs": {"festive": 6}, "message": "🎁 Day 14: two weeks of cheer!"},
    15: {"kibble": 3500, "packs": {"festive": 6}, "message": "⭐ Day 15: halfway to christmas!"},
    16: {"kibble": 4000, "packs": {"festive": 7}, "message": "🔔 Day 16: the bells are ringing louder, AHHH HELP"},
    17: {"kibble": 4500, "packs": {"festive": 7}, "message": "🕯️ Day 17: fairy lights????"},
    18: {"kibble": 5000, "packs": {"festive": 8}, "message": "🎶 Day 18: woohooo more carols, thank you jamming cat!"},
    19: {"kibble": 5500, "packs": {"festive": 8}, "message": "🍪 Day 19: gingerbread cat is.. cooking himself?"},
    20: {"kibble": 6000, "packs": {"festive": 9}, "message": "🎄 Day 20: almost christmas!"},
    21: {"kibble": 7000, "packs": {"festive": 10}, "message": "❄️ Day 21: pretty cold ngl.. brr"},
    22: {"kibble": 8000, "packs": {"festive": 10}, "message": "🎅 Day 22: santa cat is getting readyyy"},
    23: {"kibble": 9000, "packs": {"festive": 12}, "message": "🦌 Day 23: reindeer are practicing!"},
    24: {"kibble": 10000, "packs": {"festive": 15}, "message": "🎁 Day 24: christmas eve! big rewards!"},
    25: {"kibble": 25000, "packs": {"festive": 25, "celestial": 5}, "cats": {"Fine": 1}, "message": "🎄 Day 25: merry catsmas!1!!1!!! :3"}
}

async def advent_command(message: discord.Interaction):
    """Advent calendar - claim daily rewards throughout December"""
    await message.response.defer()
    
    # Check if it's December
    import datetime
    now = datetime.datetime.now()
    if now.month != 12 or now.day > 25:
        await message.followup.send(
            "🎄 The advent calendar is only available December 1-25!",
            ephemeral=True
        )
        return
    
    profile = await Profile.get_or_create(user_id=message.user.id, guild_id=message.guild.id)
    
    # Check if banned by Santa
    if profile.santa_banned:
        await message.followup.send(
            "🎅 santa has banned you from receiving advent gifts, you dip. be nice next time \n"
            "maybe next year if you improve your ways...",
            ephemeral=True
        )
        # Try to trigger naughty_list achievement if achemb is available
        try:
            await achemb(message, "naughty_list", "send")
        except NameError:
            pass  # achemb will be imported from main.py at runtime
        return
    
    # Parse claimed days
    claimed_days = []
    if profile.advent_claimed:
        claimed_days = [int(d) for d in profile.advent_claimed.split(",") if d]
    
    current_day = now.day
    
    # Check if already claimed today
    if current_day in claimed_days:
        next_day = current_day + 1 if current_day < 25 else "next year"
        await message.followup.send(
            f"🎄 You've already claimed today's reward! Come back tomorrow (Day {next_day}).",
            ephemeral=True
        )
        return
    
    # Check if trying to claim future days
    if current_day not in ADVENT_REWARDS:
        await message.followup.send(
            "🎄 This day hasn't arrived yet! Check back later.",
            ephemeral=True
        )
        return
    
    # Give rewards
    reward_data = ADVENT_REWARDS[current_day]
    
    # Add kibbles
    kibble_reward = reward_data.get("kibble", 0)
    profile.kibble = (profile.kibble or 0) + kibble_reward
    
    # Add packs
    reward_text = [f"🍖 **{kibble_reward:,} Kibbles**"]
    if "packs" in reward_data:
        for pack_type, count in reward_data["packs"].items():
            pack_attr = f"pack_{pack_type}"
            current = getattr(profile, pack_attr, 0) or 0
            setattr(profile, pack_attr, current + count)
            reward_text.append(f"📦 **{count} {pack_type.title()} Pack{'s' if count > 1 else ''}**")
    
    # Add cats (special days)
    if "cats" in reward_data:
        for cat_type, count in reward_data["cats"].items():
            cat_attr = f"cat_{cat_type}"
            current = getattr(profile, cat_attr, 0) or 0
            setattr(profile, cat_attr, current + count)
            reward_text.append(f"🐱 **{count} {cat_type} Cat{'s' if count > 1 else ''}**")
    
    # Mark as claimed
    claimed_days.append(current_day)
    profile.advent_claimed = ",".join(str(d) for d in sorted(claimed_days))
    profile.advent_last_claim = int(time.time())
    
    # Increase nice score
    profile.nice_score = (profile.nice_score or 0) + 1
    
    await profile.save()
    
    # Check for advent master achievement (all 25 days)
    if len(claimed_days) == 25:
        profile.kibble = (profile.kibble or 0) + 10000
        await profile.save()
        # Try to trigger advent_master achievement if achemb is available
        try:
            await achemb(message, "advent_master", "send")
        except NameError:
            pass  # achemb will be imported from main.py at runtime
    
    # Create embed
    embed = discord.Embed(
        title=f"🎄 Advent Calendar - Day {current_day}",
        description=reward_data["message"],
        color=0xC41E3A  # Christmas red
    )
    
    embed.add_field(
        name="🎁 Today's Rewards",
        value="\n".join(reward_text),
        inline=False
    )
    
    embed.add_field(
        name="📅 Progress",
        value=f"**{len(claimed_days)}/25** days claimed",
        inline=True
    )
    
    embed.add_field(
        name="😇 Nice Score",
        value=f"**{profile.nice_score or 0}** points",
        inline=True
    )
    
    if current_day < 25:
        embed.set_footer(text=f"Come back tomorrow for Day {current_day + 1}!")
    else:
        embed.set_footer(text="🎅 Merry Christmas! See you next year!")
    
    await message.followup.send(embed=embed)

# =============================================================================
# NAUGHTY/NICE SYSTEM
# =============================================================================

async def update_naughty_score(user_id: int, guild_id: int, amount: int):
    """Increase naughty score - call when player steals, etc."""
    profile = await Profile.get_or_create(user_id=user_id, guild_id=guild_id)
    profile.naughty_score = (profile.naughty_score or 0) + amount
    
    # Ban from Santa if too naughty (score > 10)
    if profile.naughty_score > 10 and not profile.santa_banned:
        profile.santa_banned = True
        await profile.save()
        return True  # Return True to notify user they've been banned
    
    await profile.save()
    return False

async def update_nice_score(user_id: int, guild_id: int, amount: int):
    """Increase nice score - call when player gifts cats, helps others"""
    profile = await Profile.get_or_create(user_id=user_id, guild_id=guild_id)
    profile.nice_score = (profile.nice_score or 0) + amount
    
    # Check for nice list achievement
    naughty = profile.naughty_score or 0
    nice = profile.nice_score or 0
    if nice > naughty and nice >= 20:
        profile.nice_list = True
    
    await profile.save()

# =============================================================================
# CHRISTMAS TREE DECORATION SYSTEM
# =============================================================================

# 8 Ornaments - one from each activity
TREE_ORNAMENTS = {
    1: {
        "name": "❄️ Snowflake Ornament",
        "emoji": "❄️",
        "source": "Catch 10 festive cats",
        "description": "A delicate crystalline snowflake",
        "reward_boost": "Rare cat spawns +8%"
    },
    2: {
        "name": "🎁 Present Ornament",
        "emoji": "🎁",
        "source": "Gift 5 cats to other players",
        "description": "A beautifully wrapped present",
        "reward_boost": "Kibble from adventures +15%"
    },
    3: {
        "name": "🔔 Bell Ornament",
        "emoji": "🔔",
        "source": "Claim 10 days of advent calendar",
        "description": "A golden jingle bell",
        "reward_boost": "Advent rewards +20%"
    },
    4: {
        "name": "🍬 Candy Cane Ornament",
        "emoji": "🍬",
        "source": "Open 15 festive packs",
        "description": "A classic red and white candy cane",
        "reward_boost": "Pack rarity boost +12%"
    },
    5: {
        "name": "⭐ Star Ornament",
        "emoji": "⭐",
        "source": "Reach Nice Score of 10",
        "description": "A shining golden star",
        "reward_boost": "Daily streak bonus +25%"
    },
    6: {
        "name": "🎅 Santa Ornament",
        "emoji": "🎅",
        "source": "Unlock Santa Hat cosmetic",
        "description": "A jolly Santa figurine",
        "reward_boost": "Epic+ spawn rate +10%"
    },
    7: {
        "name": "🧊 Ice Crystal Ornament",
        "emoji": "🧊",
        "source": "Battle 20 winter-themed cats",
        "description": "A sparkling blue ice crystal",
        "reward_boost": "Battle rewards +18%"
    },
    8: {
        "name": "🏆 Champion Ornament",
        "emoji": "🏆",
        "source": "Win 5 battles with cat team",
        "description": "A golden championship trophy",
        "reward_boost": "All rewards +25% (completion bonus)"
    }
}

TREE_ACHIEVEMENT = {
    "tree_decorated": {
        "title": "Christmas Tree Master",
        "display": "🎄 Christmas Tree Master",
        "description": "Collect all 8 ornaments and decorate the Christmas tree",
        "reward": "Special Christmas Tree Master badge, +50,000 Kibbles, Celestial Pack x5"
    }
}

async def check_tree_ornament_unlock(user_id: int, guild_id: int, ornament_id: int):
    """Check if a player has unlocked an ornament and add it to their tree"""
    profile = await Profile.get_or_create(user_id=user_id, guild_id=guild_id)
    
    # Parse collected ornaments
    collected = []
    if profile.tree_ornaments:
        collected = [int(o) for o in profile.tree_ornaments.split(",") if o]
    
    # If already collected, return False
    if ornament_id in collected:
        return False
    
    # Add new ornament
    collected.append(ornament_id)
    profile.tree_ornaments = ",".join(str(o) for o in sorted(collected))
    profile.tree_ornament_count = len(collected)
    
    # Check if tree is complete (all 8 ornaments)
    if len(collected) == 8 and not profile.tree_decorated:
        profile.tree_decorated = True
        # Award bonus rewards
        profile.kibble = (profile.kibble or 0) + 50000
        profile.pack_celestial = (profile.pack_celestial or 0) + 5
    
    await profile.save()
    return True

# Helper functions to track ornament progress
async def track_festive_catch(user_id: int, guild_id: int):
    """Track festive cat catches and unlock ornament #1 at 10 catches"""
    profile = await Profile.get_or_create(user_id=user_id, guild_id=guild_id)
    profile.christmas_spirit_progress = (getattr(profile, 'christmas_spirit_progress', None) or 0) + 1
    await profile.save()
    if profile.christmas_spirit_progress >= 10:
        return await check_tree_ornament_unlock(user_id, guild_id, 1)
    return False

async def track_gift_given(user_id: int, guild_id: int):
    """Track gifts and unlock ornament #2 at 5 gifts"""
    profile = await Profile.get_or_create(user_id=user_id, guild_id=guild_id)
    profile.gift_giver_progress = (getattr(profile, 'gift_giver_progress', None) or 0) + 1
    await profile.save()
    if profile.gift_giver_progress >= 5:
        return await check_tree_ornament_unlock(user_id, guild_id, 2)
    return False

async def track_advent_claim(user_id: int, guild_id: int):
    """Track advent claims and unlock ornament #3 at 10 claims"""
    profile = await Profile.get_or_create(user_id=user_id, guild_id=guild_id)
    # Check claimed days count
    claimed_days = []
    if profile.advent_claimed:
        claimed_days = [int(d) for d in profile.advent_claimed.split(",") if d]
    if len(claimed_days) >= 10:
        return await check_tree_ornament_unlock(user_id, guild_id, 3)
    return False

async def track_festive_pack_open(user_id: int, guild_id: int):
    """Track festive pack opens and unlock ornament #4 at 15 opens"""
    profile = await Profile.get_or_create(user_id=user_id, guild_id=guild_id)
    pack_festive = getattr(profile, 'pack_festive_opened', None) or 0
    pack_festive += 1
    profile.pack_festive_opened = pack_festive
    await profile.save()
    if pack_festive >= 15:
        return await check_tree_ornament_unlock(user_id, guild_id, 4)
    return False

async def track_nice_score(user_id: int, guild_id: int):
    """Check nice score and unlock ornament #5 at 10 points"""
    profile = await Profile.get_or_create(user_id=user_id, guild_id=guild_id)
    if (profile.nice_score or 0) >= 10:
        return await check_tree_ornament_unlock(user_id, guild_id, 5)
    return False

async def track_cosmetic_unlock(user_id: int, guild_id: int, cosmetic_id: str):
    """Check if santa_hat was unlocked and give ornament #6"""
    if cosmetic_id == "santa_hat":
        return await check_tree_ornament_unlock(user_id, guild_id, 6)
    return False

async def track_winter_battle(user_id: int, guild_id: int):
    """Track battles with winter cats and unlock ornament #7 at 20 battles"""
    profile = await Profile.get_or_create(user_id=user_id, guild_id=guild_id)
    winter_battles = (getattr(profile, 'winter_battles', None) or 0) + 1
    profile.winter_battles = winter_battles
    await profile.save()
    if winter_battles >= 20:
        return await check_tree_ornament_unlock(user_id, guild_id, 7)
    return False

async def track_team_battle_win(user_id: int, guild_id: int):
    """Track team battle wins and unlock ornament #8 at 5 wins"""
    profile = await Profile.get_or_create(user_id=user_id, guild_id=guild_id)
    team_wins = (getattr(profile, 'team_battle_wins', None) or 0) + 1
    profile.team_battle_wins = team_wins
    await profile.save()
    if team_wins >= 5:
        return await check_tree_ornament_unlock(user_id, guild_id, 8)
    return False

async def tree_view_command(message: discord.Interaction):
    """Display current Christmas tree decoration progress"""
    await message.response.defer()
    
    profile = await Profile.get_or_create(user_id=message.user.id, guild_id=message.guild.id)
    
    # Parse collected ornaments
    collected = []
    if profile.tree_ornaments:
        collected = [int(o) for o in profile.tree_ornaments.split(",") if o]
    
    # Create visual tree
    tree_art = """
```
       ⭐
       🎄
      🎄🎄
     🎄🎄🎄
    🎄🎄🎄🎄
   🎄🎄🎄🎄🎄
  🎄🎄🎄🎄🎄🎄
 🎄🎄🎄🎄🎄🎄🎄
🎄🎄🎄🎄🎄🎄🎄🎄
         ║ 
```
    """
    
    # Build ornament display
    ornament_display = []
    for ornament_id in range(1, 9):
        ornament = TREE_ORNAMENTS[ornament_id]
        if ornament_id in collected:
            ornament_display.append(f"{ornament['emoji']} **{ornament['name']}** ✅")
        else:
            ornament_display.append(f"⚫ *{ornament['name']}* - {ornament['source']}")
    
    # Create embed
    embed = discord.Embed(
        title="🎄 Christmas Tree Decorations",
        description=tree_art,
        color=0x0F8A5F  # Christmas green
    )
    
    embed.add_field(
        name="🎁 Ornaments Collected",
        value=f"{len(collected)}/8 ornaments",
        inline=True
    )
    
    if profile.tree_decorated:
        embed.add_field(
            name="✅ Tree Status",
            value="**COMPLETE!** 🎉\nYou've decorated the entire tree!",
            inline=True
        )
    else:
        next_ornaments = [o for o in range(1, 9) if o not in collected]
        embed.add_field(
            name="📋 Remaining",
            value=f"**{len(next_ornaments)}/8** ornaments left to collect",
            inline=True
        )
    
    embed.add_field(
        name="🎀 Ornament Collection",
        value="\n".join(ornament_display),
        inline=False
    )
    
    if profile.tree_decorated:
        embed.add_field(
            name="🏆 Bonus Rewards Earned",
            value="✨ +50,000 Kibbles\n📦 +5 Celestial Packs\n🚀 Massive boosts to all rewards!\n🏅 Achievement Unlocked!",
            inline=False
        )
        embed.set_footer(text="🎄 Christmas Tree Master! 🎄")
    else:
        embed.set_footer(text="Collect all 8 ornaments to complete your tree and earn rewards!")
    
    await message.followup.send(embed=embed)

async def tree_ornament_info_command(message: discord.Interaction, ornament_id: int):
    """View detailed info about a specific ornament"""
    await message.response.defer()
    
    if ornament_id not in TREE_ORNAMENTS:
        await message.followup.send(
            "❌ That ornament doesn't exist! Choose a number between 1-8.",
            ephemeral=True
        )
        return
    
    profile = await Profile.get_or_create(user_id=message.user.id, guild_id=message.guild.id)
    
    # Parse collected ornaments
    collected = []
    if profile.tree_ornaments:
        collected = [int(o) for o in profile.tree_ornaments.split(",") if o]
    
    ornament = TREE_ORNAMENTS[ornament_id]
    is_collected = ornament_id in collected
    
    embed = discord.Embed(
        title=f"🎄 {ornament['name']}",
        description=ornament['description'],
        color=0xC41E3A if is_collected else 0x808080
    )
    
    embed.add_field(
        name="🎯 How to Unlock",
        value=ornament['source'],
        inline=False
    )
    
    embed.add_field(
        name="⚡ Reward Boost (When Tree Complete)",
        value=ornament['reward_boost'],
        inline=False
    )
    
    embed.add_field(
        name="📊 Status",
        value="✅ **COLLECTED**" if is_collected else "⏳ **Not yet collected**",
        inline=True
    )
    
    await message.followup.send(embed=embed)

# =============================================================================
# TREE BOOST SYSTEM
# =============================================================================

def get_tree_boosts(collected_ornaments_count: int) -> dict:
    """
    Calculate active boosts based on number of ornaments collected.
    Returns dict with boost percentages for actual game mechanics.
    """
    if collected_ornaments_count == 0:
        return {}
    
    # Incremental boosts per ornament
    boosts = {
        "rare_spawn": 0.08 * collected_ornaments_count,       # 8% per ornament (max 64%)
        "kibble_adventure": 0.15 * collected_ornaments_count,  # 15% per ornament (max 120%)
        "adventure_rewards": 0.12 * collected_ornaments_count, # 12% per ornament (max 96%)
        "pack_rarity": 0.06 * collected_ornaments_count,       # 6% per ornament (max 48%)
        "daily_streak": 0.25 * collected_ornaments_count,      # 25% per ornament (max 200%)
        "epic_spawn": 0.10 * collected_ornaments_count,        # 10% per ornament (max 80%)
        "battle_rewards": 0.18 * collected_ornaments_count,    # 18% per ornament (max 144%)
    }
    
    # Tree completion bonus (all 8) - massive boost
    if collected_ornaments_count == 8:
        boosts["rare_spawn"] += 0.25
        boosts["kibble_adventure"] += 0.50
        boosts["adventure_rewards"] += 0.40
        boosts["pack_rarity"] += 0.30
        boosts["daily_streak"] += 0.50
        boosts["epic_spawn"] += 0.30
        boosts["battle_rewards"] += 0.35
    
    return boosts


# =============================================================================
# FESTIVE PACK INTEGRATION
# =============================================================================

# Add to existing pack opening logic:
"""
elif pack_type == "festive":
    # Placeholder: uses Fine cats for now
    # Replace with actual Christmas cats when they exist
    result_type = "Fine"  # TODO: Add Christmas cat types
    
    # Update festive collector achievement progress
    profile.pack_festive = (profile.pack_festive or 0) + 1
    if profile.pack_festive >= 50:
        await achemb(interaction, "festive_collector", "send")
"""

# =============================================================================
# INTEGRATION NOTES
# =============================================================================

"""
TO INTEGRATE INTO MAIN.PY:

1. Run the database migration SQL at the top

2. Add CHRISTMAS_COSMETICS to the existing COSMETICS_DATA:
   - Merge badges, titles, colors, effects into respective sections
   
3. Add CHRISTMAS_ACHIEVEMENTS to aches_data dict

4. Add TREE_ACHIEVEMENT to aches_data dict

5. Add the advent_command as a bot.tree.command:
   @bot.tree.command(description="Open the advent calendar and claim daily rewards!")
   async def advent(message: discord.Interaction):
       await advent_command(message)

6. Add tree view command:
   @bot.tree.command(description="View your Christmas tree decorations!")
   async def tree(message: discord.Interaction):
       await tree_view_command(message)

7. Add tree ornament info command:
   @bot.tree.command(description="Learn about a specific ornament!")
   async def tree_ornament(message: discord.Interaction, number: int):
       await tree_ornament_info_command(message, number)

8. Integrate naughty/nice scoring:
   - Call update_naughty_score() in the stealing logic (search for "last_steal")
   - Call update_nice_score() when gifting cats (search for "cats_gifted")
   - Add check in advent_command for santa_banned status

9. Add festive pack to pack opening logic (search for "celestial")

10. Integrate ornament unlocking:
    - After catching 10 festive cats: await check_tree_ornament_unlock(user_id, guild_id, 1)
    - After gifting 5 cats: await check_tree_ornament_unlock(user_id, guild_id, 2)
    - After claiming 10 advent days: await check_tree_ornament_unlock(user_id, guild_id, 3)
    - After opening 15 festive packs: await check_tree_ornament_unlock(user_id, guild_id, 4)
    - After reaching nice score 10: await check_tree_ornament_unlock(user_id, guild_id, 5)
    - After unlocking Santa Hat cosmetic: await check_tree_ornament_unlock(user_id, guild_id, 6)
    - After battling 20 winter cats: await check_tree_ornament_unlock(user_id, guild_id, 7)
    - After winning 5 team battles: await check_tree_ornament_unlock(user_id, guild_id, 8)

11. Apply tree boosts when calculating rewards:
    - Get boosts with: boosts = get_tree_boosts(profile.tree_ornament_count)
    - Apply to rare cat spawn rates: rare_spawn_chance * (1 + boosts.get("rare_spawn", 0))
    - Apply to kibble from adventures: kibble_amount * (1 + boosts.get("kibble_adventure", 0))
    - Apply to adventure rewards: reward_amount * (1 + boosts.get("adventure_rewards", 0))
    - Apply to pack rarity weights: increase weight of higher rarity packs by boosts.get("pack_rarity", 0)
    - Apply to daily streak: base_streak * (1 + boosts.get("daily_streak", 0))
    - Apply to epic+ spawn rates: epic_spawn_chance * (1 + boosts.get("epic_spawn", 0))
    - Apply to battle rewards: battle_reward * (1 + boosts.get("battle_rewards", 0))

12. Add check for December to enable all Christmas features

13. Display tree boosts in status messages and profile commands
    - Show current boosts when tree has ornaments
    - Show completion bonus when all 8 collected

14. Optional: Add seasonal cosmetics to players who complete the tree
    - Could unlock "Christmas Tree Master" title automatically
    - Could give special badge that appears on profile

EXAMPLE ORNAMENT UNLOCK FLOW:
1. Player catches festive cat #10
   - Call: await check_tree_ornament_unlock(user_id, guild_id, 1)
   - Ornament #1 (Snowflake) is added to their tree
   - They gain 5% catch rate boost
   - System notifies: "❄️ You've collected the Snowflake Ornament! +5% catch rate"

2. Player completes all ornaments
   - Last ornament added triggers tree_decorated = True
   - +50,000 Kibbles awarded
   - +5 Celestial Packs awarded
   - Achievement "Christmas Tree Master" unlocked
   - All boosts now include the completion bonuses
"""

# =============================================================================
# TESTING CHECKLIST
# =============================================================================

"""
ADVENT CALENDAR TESTS:
- [ ] Advent calendar claims work for each day 1-25
- [ ] Cannot claim same day twice
- [ ] Cannot claim future days
- [ ] Rewards are correctly distributed
- [ ] Advent master achievement triggers on day 25
- [ ] Naughty score increases on stealing
- [ ] Nice score increases on gifting
- [ ] Santa ban triggers at naughty_score > 10
- [ ] Banned users cannot claim advent rewards
- [ ] Christmas cosmetics appear in shop
- [ ] Christmas achievements unlock properly
- [ ] Festive packs can be opened and counted
- [ ] Features disable automatically after December

CHRISTMAS TREE TESTS:
- [ ] Tree view displays correctly with no ornaments
- [ ] Each ornament can be unlocked (1-8)
- [ ] Cannot unlock same ornament twice
- [ ] Ornament count increments correctly (0-8)
- [ ] Tree ornament info command shows correct details
- [ ] Getting boosts with 0 ornaments returns empty dict
- [ ] Getting boosts with 1-7 ornaments calculates incremental boosts
- [ ] Getting boosts with 8 ornaments includes completion bonus
- [ ] Completion boosts are significantly higher (20%+ catch rate, 50%+ kibbles)
- [ ] Tree decorated flag sets to true on 8th ornament
- [ ] Bonus rewards awarded on tree completion (50k kibble, 5 celestial packs)
- [ ] Tree Master achievement triggers on completion
- [ ] Boosts are applied to catch rates correctly
- [ ] Boosts are applied to kibble gains correctly
- [ ] Boosts are applied to pack drops correctly
- [ ] Boosts are applied to battle power correctly
- [ ] Ornament unlock notifications display properly
- [ ] Tree view embed shows correct progress

INTEGRATION TESTS:
- [ ] Ornament #1 unlocks after 10 festive catches
- [ ] Ornament #2 unlocks after 5 cat gifts
- [ ] Ornament #3 unlocks after 10 advent claims
- [ ] Ornament #4 unlocks after 15 festive pack opens
- [ ] Ornament #5 unlocks after nice score reaches 10
- [ ] Ornament #6 unlocks after unlocking Santa Hat cosmetic
- [ ] Ornament #7 unlocks after battling 20 winter cats
- [ ] Ornament #8 unlocks after winning 5 team battles
- [ ] All boosts display in user status/profile commands
- [ ] Boosts are properly removed/reset after December
- [ ] Multiple concurrent players can have different tree progress
- [ ] Database correctly stores and retrieves ornament data
"""
