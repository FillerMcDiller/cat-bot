import json
import os
import random
import asyncio
import logging
from typing import Dict, List, Optional

import discord
from discord.ext import commands

# We'll import helper functions from main for cat instance access
try:
    from main import get_user_cats, save_user_cats
except Exception:
    # fallback imports if extension ordering differs; they'll be resolved at runtime
    get_user_cats = None
    save_user_cats = None

DATA_PATH = "data/battles"
DECKS_FILE = os.path.join(DATA_PATH, "decks.json")
os.makedirs(DATA_PATH, exist_ok=True)

# Simple default attacks per cat 'type' (case-sensitive as in cat types list)
# Each attack: (name, multiplier, uses_turns_cost)
TYPE_ATTACKS = {
    "Donut": [("Sprinkles", 1.0), ("Glaze", 1.2), ("Devour", 1.4)],
    "Water": [("Splash", 1.0), ("Tsunami", 1.4), ("Riptide", 1.3)],
    "Fire": [("Blaze", 1.2), ("Flame Burst", 1.5), ("Ember", 1.1)],
    "Fine": [("Poke", 0.9), ("Elegant Swipe", 1.05)],
    "Nice": [("Charm", 1.0), ("Encourage", 0.8)],
    "Sus": [("Sneak", 1.0), ("Backstab", 1.35)],
    "Brave": [("Charge", 1.15), ("Taunt", 0.0)],
    "Professor": [("Lecture", 1.0), ("Experiment", 1.25)],
    # fallback
}

# Weakness mapping: defender_type -> list of attacker_types that do +25% damage
WEAKNESSES = {
    "Donut": ["Fire"],
    "Fire": ["Water"],
    "Water": ["Fire"],
}

# Simple passive effects by cat type. Values are multipliers applied on attack/defense or flags.
PASSIVES = {
    "Brave": {"attack_mult": 1.05},
    "Sus": {"crit_chance": 0.12, "crit_mult": 1.5},
    "Fine": {"defend_mult": 0.9},
    "Donut": {"hp_bonus": 5},
}

# In-memory battles: channel_id -> Battle
BATTLES: Dict[int, "Battle"] = {}


def load_decks() -> Dict[str, List[str]]:
    try:
        if os.path.exists(DECKS_FILE):
            with open(DECKS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_decks(data: Dict[str, List[str]]):
    try:
        with open(DECKS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        logging.exception("Failed saving decks")

DECKS = load_decks()


def get_deck_key(guild_id: int, user_id: int) -> str:
    return f"{guild_id}_{user_id}"


class SelectCats(discord.ui.Select):
    def __init__(self, options, min_values=1, max_values=3):
        super().__init__(placeholder="Select up to 3 cats...", min_values=min_values, max_values=max_values, options=options)

    async def callback(self, interaction: discord.Interaction):
        # handled by parent view
        pass


class CatDeckView(discord.ui.View):
    def __init__(self, author_id: int, options: List[discord.SelectOption], save_key: Optional[str] = None, timeout=120):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.select = SelectCats(options, min_values=1, max_values=3)
        self.add_item(self.select)
        self.result = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author_id

    @discord.ui.button(label="Save Deck", style=discord.ButtonStyle.success)
    async def save_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        values = self.select.values
        if not values:
            await interaction.response.send_message("Select 1-3 cats first.", ephemeral=True)
            return
        key = get_deck_key(interaction.guild.id, interaction.user.id)
        DECKS[key] = values
        save_decks(DECKS)
        await interaction.response.send_message("Deck saved!", ephemeral=True)

    @discord.ui.button(label="Use Selected", style=discord.ButtonStyle.primary)
    async def use_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.result = self.select.values
        await interaction.response.defer()
        self.stop()


class Battle:
    def __init__(self, guild_id: int, channel: discord.TextChannel, p1: discord.Member, p2: discord.Member):
        self.guild_id = guild_id
        self.channel = channel
        self.p1 = p1
        self.p2 = p2
        self.teams = {p1.id: [], p2.id: []}  # lists of instance dicts
        self.active = {p1.id: None, p2.id: None}  # active instance index
        self.turn = None  # user id whose turn
        self.message = None
        self.finished = False

    def is_ready(self):
        return len(self.teams[self.p1.id]) == 3 and len(self.teams[self.p2.id]) == 3

    def set_active_defaults(self):
        for uid in (self.p1.id, self.p2.id):
            if self.teams[uid]:
                self.active[uid] = 0

    def opponent_of(self, user_id: int) -> int:
        return self.p1.id if user_id == self.p2.id else self.p2.id

    def active_cat(self, user_id: int):
        idx = self.active.get(user_id)
        if idx is None:
            return None
        try:
            return self.teams[user_id][idx]
        except Exception:
            return None

    def is_over(self):
        # if any team has all cats hp <=0
        for uid in (self.p1.id, self.p2.id):
            alive = any(c.get("hp", 0) > 0 for c in self.teams[uid])
            if not alive:
                return True
        return False


class BattlesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            print("BattlesCog loaded")
        except Exception:
            logging.info("BattlesCog loaded")

    @commands.command(name="debug_deck")
    async def debug_deck(self, ctx: commands.Context):
        # convenience: list saved deck
        key = get_deck_key(ctx.guild.id, ctx.author.id)
        deck = DECKS.get(key)
        await ctx.send(f"Saved deck: {deck}")

    @commands.command(name="fight")
    async def fight_cmd(self, ctx: commands.Context, opponent: discord.Member = None):
        # allow text-command fallback while we don't wire slash
        if opponent is None:
            await ctx.send("Usage: !fight @opponent")
            return
        await self.start_fight(ctx.channel, ctx.author, opponent)

    async def start_fight(self, channel: discord.TextChannel, user1: discord.Member, user2: discord.Member):
        # create battle and prompt each player to select 3 cats
        battle = Battle(channel.guild.id, channel, user1, user2)
        BATTLES[channel.id] = battle

        # ask players to select decks
        await channel.send(f"{user1.mention} vs {user2.mention} — select 3 cats each. Decks can be saved with the UI.")

        async def select_for_player(user: discord.Member):
            # fetch user's cats via main.get_user_cats
            cats = []
            try:
                cats = get_user_cats(channel.guild.id, user.id)
            except Exception:
                cats = []
            if not cats:
                await channel.send(f"{user.mention} has no cats to fight with.")
                return None
            # if user has a saved deck, try to use it automatically (if instances still exist)
            key = get_deck_key(channel.guild.id, user.id)
            saved = DECKS.get(key)
            if saved:
                chosen = []
                for cid in saved:
                    for c in cats:
                        if c.get("id") == cid:
                            chosen.append(dict(c))
                            break
                if chosen:
                    try:
                        await user.send("Using your saved deck for the battle.")
                    except Exception:
                        pass
                    return chosen[:3]
            options = []
            for c in cats:
                label = f"{c.get('name','?')} ({c.get('type','?')}) HP:{c.get('hp',0)} DMG:{c.get('dmg',0)} id:{c.get('id')[:6]}"
                options.append(discord.SelectOption(label=label, value=c.get('id')))
            view = CatDeckView(user.id, options)
            msg = await user.send("Select up to 3 cats for your deck", view=view)
            # wait until they submit or timeout
            await view.wait()
            if view.result:
                # resolve selected instance dicts
                chosen = []
                for cid in view.result:
                    for c in cats:
                        if c.get('id') == cid:
                            chosen.append(dict(c))
                            break
                return chosen
            return None

        # run selection concurrently
        task1 = asyncio.create_task(select_for_player(user1))
        task2 = asyncio.create_task(select_for_player(user2))
        res1, res2 = await asyncio.gather(task1, task2)
        if not res1 or not res2:
            await channel.send("Fight cancelled — one player didn't pick a deck.")
            del BATTLES[channel.id]
            return
        battle.teams[user1.id] = res1[:3]
        battle.teams[user2.id] = res2[:3]
        battle.set_active_defaults()

        # coin toss
        first = random.choice([user1.id, user2.id])
        battle.turn = first
        await channel.send(f"Fight between {user1.mention} and {user2.mention} begins! {self.bot.get_user(first).mention} goes first.")

        # start turn loop
        await self.run_battle_loop(battle)

    async def run_battle_loop(self, battle: Battle):
        channel = battle.channel
        while not battle.finished and not battle.is_over():
            actor_id = battle.turn
            opponent_id = battle.opponent_of(actor_id)
            actor_user = channel.guild.get_member(actor_id) or await self.bot.fetch_user(actor_id)
            opp_user = channel.guild.get_member(opponent_id) or await self.bot.fetch_user(opponent_id)
            a_cat = battle.active_cat(actor_id)
            o_cat = battle.active_cat(opponent_id)
            if not a_cat or not o_cat:
                break
            # present action view
            view = BattleActionView(self, battle, actor_id)
            desc = f"Your active cat: {a_cat.get('name')} ({a_cat.get('type')}) HP:{a_cat.get('hp')} DMG:{a_cat.get('dmg')}\nOpponent: {o_cat.get('name')} ({o_cat.get('type')}) HP:{o_cat.get('hp')} DMG:{o_cat.get('dmg')}"
            msg = await channel.send(f"{actor_user.mention}'s turn. Choose an action:", embed=discord.Embed(description=desc), view=view)
            try:
                await view.wait()
            except Exception:
                pass
            # view will mutate battle or set next turn
            if battle.finished:
                break
            # simple turn swap
            battle.turn = opponent_id
        # announce winner
        if battle.is_over():
            # find winner
            if any(c.get('hp',0) > 0 for c in battle.teams[battle.p1.id]):
                winner = battle.p1
            else:
                winner = battle.p2
            await channel.send(f"Battle over! {winner.mention} wins!")
        del BATTLES[battle.channel.id]


class BattleActionView(discord.ui.View):
    def __init__(self, cog: BattlesCog, battle: Battle, actor_id: int, timeout: int = 60):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.battle = battle
        self.actor_id = actor_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.actor_id

    @discord.ui.button(label="Attack", style=discord.ButtonStyle.primary)
    async def attack(self, interaction: discord.Interaction, button: discord.ui.Button):
        # pick default attack
        a_cat = self.battle.active_cat(self.actor_id)
        o_cat = self.battle.active_cat(self.battle.opponent_of(self.actor_id))
        if not a_cat or not o_cat:
            await interaction.response.send_message("Invalid cats.", ephemeral=True)
            return
        base = int(a_cat.get('dmg', 1))
        atk_type = a_cat.get('type')
        def_type = o_cat.get('type')

        # choose an attack for the type (or fallback)
        attacks = TYPE_ATTACKS.get(atk_type, [("Bite", 1.0)])
        attack_name, atk_mult = random.choice(attacks)

        # base multiplier from weaknesses
        mult = 1.0
        if def_type in WEAKNESSES and atk_type in WEAKNESSES[def_type]:
            mult *= 1.25

        # apply passives
        atk_passive = PASSIVES.get(atk_type, {})
        def_passive = PASSIVES.get(def_type, {})
        if atk_passive.get("attack_mult"):
            mult *= float(atk_passive["attack_mult"])
        if def_passive.get("defend_mult"):
            mult *= float(def_passive["defend_mult"])

        # critical hit check
        crit = False
        crit_chance = float(atk_passive.get("crit_chance", 0))
        crit_mult = float(atk_passive.get("crit_mult", 1.5))
        if crit_chance and random.random() < crit_chance:
            crit = True
            mult *= crit_mult

        final = int(base * atk_mult * mult)
        o_cat['hp'] = max(0, o_cat.get('hp', 0) - final)
        crit_text = " (CRITICAL!)" if crit else ""
        await interaction.response.send_message(f"{a_cat.get('name')} uses {attack_name} and hits {o_cat.get('name')} for {final} damage!{crit_text} (mult {round(mult,2)})")
        # check KO
        if o_cat['hp'] <= 0:
            await interaction.followup.send(f"{o_cat.get('name')} has been knocked out!")
        self.stop()

    @discord.ui.button(label="Switch", style=discord.ButtonStyle.secondary)
    async def switch(self, interaction: discord.Interaction, button: discord.ui.Button):
        # choose next alive cat
        uid = self.actor_id
        options = []
        for idx, c in enumerate(self.battle.teams[uid]):
            options.append(discord.SelectOption(label=f"{c.get('name')} HP:{c.get('hp')}", value=str(idx)))
        sel = SwitchSelect(options)
        view = discord.ui.View()
        view.add_item(sel)
        await interaction.response.send_message("Choose a cat to switch to:", view=view, ephemeral=True)
        await view.wait()
        if sel.value is not None:
            self.battle.active[uid] = int(sel.value)
            await interaction.followup.send(f"Switched to {self.battle.active_cat(uid).get('name')}")
        self.stop()

    @discord.ui.button(label="Surrender", style=discord.ButtonStyle.danger)
    async def surrender(self, interaction: discord.Interaction, button: discord.ui.Button):
        confirm = ConfirmView(interaction.user.id)
        await interaction.response.send_message("Are you sure you want to surrender?", view=confirm, ephemeral=True)
        await confirm.wait()
        if confirm.value:
            self.battle.finished = True
            opp = self.battle.opponent_of(self.actor_id)
            await interaction.followup.send(f"{interaction.user.mention} surrendered. {self.cog.bot.get_user(opp).mention} wins!")
        self.stop()


class SwitchSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Choose cat", min_values=1, max_values=1, options=options)
        self.value = None

    async def callback(self, interaction: discord.Interaction):
        self.value = self.values[0]
        await interaction.response.defer()
        self.view.stop()


class ConfirmView(discord.ui.View):
    def __init__(self, author_id: int, timeout: int = 30):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.value = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author_id

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.danger)
    async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="No", style=discord.ButtonStyle.secondary)
    async def no(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await interaction.response.defer()
        self.stop()


def setup(bot: commands.Bot):
    bot.add_cog(BattlesCog(bot))
