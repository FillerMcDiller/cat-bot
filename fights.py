import asyncio
import json
import os
import random
from typing import Dict, List

import discord
from discord.ext import commands

import importlib
import cat_modifiers


def _get_main():
    try:
        return importlib.import_module("main")
    except Exception:
        return None

BASE = os.path.dirname(__file__)
DECKS_PATH = os.path.join(BASE, "data", "fight_decks.json")


def _ensure_decks():
    try:
        os.makedirs(os.path.dirname(DECKS_PATH), exist_ok=True)
    except Exception:
        pass
    if not os.path.exists(DECKS_PATH):
        with open(DECKS_PATH, "w", encoding="utf-8") as f:
            json.dump({}, f)
        return {}
    try:
        with open(DECKS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_decks(data: dict):
    try:
        os.makedirs(os.path.dirname(DECKS_PATH), exist_ok=True)
    except Exception:
        pass
    with open(DECKS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


# Simple ability and type definitions
TYPE_WEAKNESSES = {
    "Water": ["Fire"],
    "Fire": ["Water"],
    "Donut": ["Fire"],
}


# Build an ability catalog at import time using the main module's type/rarity data.
def _build_cat_abilities():
    abilities: dict = {}
    try:
        mm = _get_main()
        type_values = getattr(mm, "type_dict", {}) or {}
        cattypes = getattr(mm, "cattypes", list(type_values.keys())) or list(type_values.keys())
    except Exception:
        type_values = {}
        cattypes = []

    # Template suffixes for variety
    primary_suffixes = ["Strike", "Bite", "Swipe", "Paw", "Blast", "Smash"]
    special_suffixes = ["Special", "Trick", "Burst", "Surge", "Wave", "Shower"]

    for t in cattypes:
        base = int(type_values.get(t, 100) or 100)
        # scale primary power by rarity/value: higher value -> stronger
        primary_power = max(3, base // 15)
        # create 1-2 attacks; rarer types more likely to get 2
        attacks = []
        name1 = f"{t} {random.choice(primary_suffixes)}"
        attacks.append({"name": name1, "power": primary_power + random.randint(0, 3), "turn": True})

        # secondary ability: chance depends on base value
        if base > 200 or random.random() < 0.6:
            name2 = f"{t} {random.choice(special_suffixes)}"
            # second ability tends to be slightly weaker and sometimes passive
            power2 = max(1, primary_power - random.randint(0, 2))
            consumes = random.random() < 0.7
            attacks.append({"name": name2, "power": power2 + random.randint(0, 2), "turn": consumes})

        abilities[t] = {"type": t, "attacks": attacks}

    # Small, handcrafted overrides for special-flavored types
    if "Donut" in abilities:
        abilities["Donut"] = {
            "type": "Donut",
            "attacks": [
                {"name": "Sprinkles", "power": max(5, abilities["Donut"]["attacks"][0]["power"]), "turn": True},
                {"name": "Sticky Glaze", "power": max(3, 2), "turn": False},
            ],
        }
    if "Water" in abilities:
        abilities["Water"] = {
            "type": "Water",
            "attacks": [
                {"name": "Splash", "power": max(6, abilities["Water"]["attacks"][0]["power"]), "turn": True},
                {"name": "Soak", "power": max(3, 2), "turn": False},
            ],
        }
    if "Fire" in abilities:
        abilities["Fire"] = {
            "type": "Fire",
            "attacks": [
                {"name": "Flame Paw", "power": max(7, abilities["Fire"]["attacks"][0]["power"]), "turn": True},
                {"name": "Hot Breath", "power": max(5, 4), "turn": True},
            ],
        }

    return abilities


# initialize CAT_ABILITIES using current main.py type data
CAT_ABILITIES = _build_cat_abilities()


def get_cat_display_stats(cat: dict) -> dict:
    """Get cat's displayed stats with modifiers applied. Returns {hp, dmg}."""
    if not cat:
        return {"hp": 0, "dmg": 0}
    
    modifiers = cat.get("modifiers", [])
    if modifiers:
        return cat_modifiers.apply_stat_multipliers(cat)
    return {"hp": cat.get("hp", 0), "dmg": cat.get("dmg", 0)}


class FightSession:
    def __init__(self, ctx: commands.Context, challenger: discord.Member, opponent: discord.Member):
        self.ctx = ctx
        self.guild = ctx.guild
        self.channel = ctx.channel
        self.challenger = challenger
        self.opponent = opponent
        self.teams = {challenger.id: [], opponent.id: []}  # list of cat instances
        self.active = {challenger.id: 0, opponent.id: 0}
        self.turn = None
        self.message = None
        self.finished = False

    def active_cat(self, user_id: int):
        team = self.teams.get(user_id, [])
        idx = self.active.get(user_id, 0)
        if idx < len(team):
            return team[idx]
        return None

    # small helpers for embed-updates
    def set_last_action(self, text: str, target_id: str | None = None, old_hp: int = 0, new_hp: int = 0, dmg: int = 0):
        self.last_action = text
        if target_id is not None:
            self.last_hp_change = (target_id, old_hp, new_hp, dmg)
        else:
            self.last_hp_change = None


class Fights(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sessions: Dict[int, FightSession] = {}

    @commands.hybrid_command(name="deck_save")
    async def deck_save(self, ctx: commands.Context, name: str):
        """Save a deck of 3 cats under a given name (interactive select via DM)."""
        mm = _get_main()
        if not mm:
            await ctx.reply("Internal error: user cat data unavailable.")
            return
        cats = await mm.get_user_cats(ctx.guild.id, ctx.author.id)
        if not cats:
            await ctx.reply("You have no cats to save as a deck.")
            return

        options = []
        for c in cats[:25]:
            label = f"{c.get('name')} ({c.get('type')})"
            value = c.get('id')
            display_stats = get_cat_display_stats(c)
            desc = f"HP:{display_stats.get('hp')} DMG:{display_stats.get('dmg')}"
            options.append(discord.SelectOption(label=label, value=value, description=desc))

        select = DeckSelect(options=options, placeholder=f"Select 3 cats to save as '{name}'", owner=ctx.author, guild_id=ctx.guild.id, deck_name=name)
        view = discord.ui.View(timeout=60)
        view.add_item(select)
        try:
            await ctx.author.send(f"Select 3 cats to save as deck '{name}':", view=view)
            await ctx.reply("I sent you a DM to pick cats for your deck.", ephemeral=True)
        except Exception:
            await ctx.reply("I couldn't DM you. Please enable DMs from server members.", ephemeral=True)

    @commands.hybrid_command(name="deck_list")
    async def deck_list(self, ctx: commands.Context):
        """List saved decks for you in this guild."""
        data = _ensure_decks()
        guild = str(ctx.guild.id)
        user = str(ctx.author.id)
        out = []
        try:
            decks = data.get(guild, {}).get(user, {})
            for k, v in (decks.items() if decks else []):
                out.append(f"{k}: {len(v)} cats")
        except Exception:
            decks = {}

        if not out:
            await ctx.reply("You have no saved decks in this server.")
            return
        await ctx.reply("\n".join(out))

    @commands.hybrid_command(name="deck_load")
    async def deck_load(self, ctx: commands.Context, name: str):
        """Show a saved deck's cats."""
        data = _ensure_decks()
        guild = str(ctx.guild.id)
        user = str(ctx.author.id)
        decks = data.get(guild, {}).get(user, {})
        if not decks or name not in decks:
            await ctx.reply("No such deck saved.")
            return
        ids = decks[name]
        mm = _get_main()
        if not mm:
            await ctx.reply("Internal error: user cat data unavailable.")
            return
        cats = await mm.get_user_cats(ctx.guild.id, ctx.author.id)
        cats_found = [next((c for c in cats if c.get('id') == cid), None) for cid in ids]
        found = []
        for c in cats_found:
            if c:
                display_stats = get_cat_display_stats(c)
                found.append(f"{c.get('name')} ({c.get('type')}) HP:{display_stats.get('hp')} DMG:{display_stats.get('dmg')}")
        if not found:
            await ctx.reply("Saved deck has no matching cats (they may have been deleted).")
            return
        await ctx.reply("\n".join(found))

    @commands.hybrid_command(name="deck_delete")
    async def deck_delete(self, ctx: commands.Context, name: str):
        """Delete a saved deck by name."""
        data = _ensure_decks()
        g = str(ctx.guild.id)
        u = str(ctx.author.id)
        if g in data and u in data[g] and name in data[g][u]:
            try:
                del data[g][u][name]
                _save_decks(data)
                await ctx.reply(f"Deleted deck '{name}'.")
            except Exception:
                await ctx.reply("Failed to delete deck due to an error.")
        else:
            await ctx.reply("No such deck saved.")

    @commands.hybrid_command(name="deck_rename")
    async def deck_rename(self, ctx: commands.Context, old_name: str, new_name: str):
        """Rename a saved deck."""
        data = _ensure_decks()
        g = str(ctx.guild.id)
        u = str(ctx.author.id)
        if g in data and u in data[g] and old_name in data[g][u]:
            try:
                if new_name in data[g][u]:
                    await ctx.reply("A deck with the new name already exists.")
                    return
                data[g][u][new_name] = data[g][u].pop(old_name)
                _save_decks(data)
                await ctx.reply(f"Renamed deck '{old_name}' -> '{new_name}'.")
            except Exception:
                await ctx.reply("Failed to rename deck due to an error.")
        else:
            await ctx.reply("No such deck saved.")

    @commands.hybrid_command(name="fight")
    async def fight(self, ctx: commands.Context, opponent: discord.Member):
        """Challenge another player to a cat battle."""
        if opponent.bot:
            await ctx.reply("You can't fight bots.")
            return
        if ctx.author.id == opponent.id:
            await ctx.reply("You can't fight yourself.")
            return

        # create challenge message with accept/decline
        view = ChallengeView(self, ctx.author, opponent)
        await ctx.reply(f"{opponent.mention}, you have been challenged to a cat fight by {ctx.author.mention}!", view=view)


class ChallengeView(discord.ui.View):
    def __init__(self, manager: Fights, challenger: discord.Member, opponent: discord.Member):
        super().__init__(timeout=60)
        self.manager = manager
        self.challenger = challenger
        self.opponent = opponent

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("Only the challenged player can accept.", ephemeral=True)
            return
        await interaction.response.send_message("Challenge accepted. Pick your 3 cats.", ephemeral=True)
        # start selection for both players
        await self.start_selection(interaction)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("Only the challenged player can decline.", ephemeral=True)
            return
        await interaction.response.send_message("Challenge declined.")
        self.stop()

    async def start_selection(self, interaction: discord.Interaction):
        ctx = await self.manager.bot.get_context(interaction.message)
        session = FightSession(ctx, self.challenger, self.opponent)
        self.manager.sessions[interaction.message.id] = session

        # ask both players to select their 3 cats via select menus
        await self.prompt_select(self.challenger, session)
        await self.prompt_select(self.opponent, session)

    async def prompt_select(self, member: discord.Member, session: FightSession):
        mm = _get_main()
        if not mm:
            await session.channel.send("Internal error: cannot access cat database.")
            return
        cats = await mm.get_user_cats(session.guild.id, member.id)
        if not cats:
            await session.channel.send(f"{member.mention} has no cats to fight with.")
            return

        # build select options
        options = []
        for c in cats[:25]:
            label = f"{c.get('name')} ({c.get('type')})"
            value = c.get('id')
            display_stats = get_cat_display_stats(c)
            desc = f"HP:{display_stats.get('hp')} DMG:{display_stats.get('dmg')}"
            options.append(discord.SelectOption(label=label, value=value, description=desc))

        select = CatSelect(options=options, placeholder=f"Select 3 cats ({member.display_name})", member=member, session=session, manager=self.manager)
        view = discord.ui.View(timeout=60)
        view.add_item(select)
        try:
            await member.send(f"Select 3 cats for the fight in {session.channel.guild.name}", view=view)
        except Exception:
            # fallback to channel mention if DMs blocked
            await session.channel.send(f"{member.mention}, please open your DMs so you can select cats for the fight.")


class CatSelect(discord.ui.Select):
    def __init__(self, options, placeholder, member: discord.Member, session: FightSession, manager: Fights):
        super().__init__(placeholder=placeholder, min_values=3, max_values=3, options=options)
        self.member = member
        self.session = session
        self.manager = manager

    async def callback(self, interaction: discord.Interaction):
        # load full instances
        mm = _get_main()
        if not mm:
            await interaction.response.send_message("Internal error: cannot access cat database.", ephemeral=True)
            return
        cats_full = await mm.get_user_cats(self.session.guild.id, self.member.id)
        chosen = [next((x for x in cats_full if x.get('id') == val), None) for val in self.values]
        chosen = [c for c in chosen if c]
        # Store cats with their modifiers intact - get_cat_display_stats will apply them during battle
        self.session.teams[self.member.id] = chosen
        await interaction.response.send_message(f"Saved your deck of {len(chosen)} cats.", ephemeral=True)

        # check if both teams ready
        other_id = self.session.challenger.id if self.member.id == self.session.opponent.id else self.session.opponent.id
        if self.session.teams.get(other_id):
            # both ready, start fight
            await self.start_fight()

    async def start_fight(self):
        s = self.session
        # decide who goes first
        first = random.choice([s.challenger.id, s.opponent.id])
        s.turn = first
        # set active indices to 0
        s.active = {s.challenger.id: 0, s.opponent.id: 0}

        # Initialize each team's cats with modifier stats applied
        for team_cats in [s.teams.get(s.challenger.id, []), s.teams.get(s.opponent.id, [])]:
            for cat in team_cats:
                # Apply modifiers to initial HP/DMG
                stats = get_cat_display_stats(cat)
                cat['hp'] = stats['hp']
                cat['dmg'] = stats['dmg']

        # send fight embed (store message so we can edit it later)
        desc = f"Fight starting between {s.challenger.mention} and {s.opponent.mention}! {self._mention_by_id(s.turn)} goes first."
        emb = discord.Embed(title="Cat Battle", description=desc)
        view = BattleView(self.manager, s)
        sent = await s.channel.send(embed=emb, view=view)
        s.message = sent
        # now send initial state embed
        await self.send_state()


class DeckSelect(discord.ui.Select):
    def __init__(self, options, placeholder, owner: discord.Member, guild_id: int, deck_name: str):
        super().__init__(placeholder=placeholder, min_values=3, max_values=3, options=options)
        self.owner = owner
        self.guild_id = guild_id
        self.deck_name = deck_name

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("This selection isn't for you.", ephemeral=True)
            return
        # Save chosen ids
        data = _ensure_decks()
        g = str(self.guild_id)
        u = str(self.owner.id)
        data.setdefault(g, {})
        data[g].setdefault(u, {})
        data[g][u][self.deck_name] = list(self.values)
        try:
            _save_decks(data)
        except Exception:
            pass
        await interaction.response.send_message(f"Saved deck '{self.deck_name}' with {len(self.values)} cats.", ephemeral=True)

    def _mention_by_id(self, user_id):
        return f"<@{user_id}>"

    async def send_state(self):
        s = self.session
        a1 = s.active_cat(s.challenger.id)
        a2 = s.active_cat(s.opponent.id)
        # build embed showing both active cats and last action
        def _build_embed():
            desc = f"Round: 1 — Turn: {self._mention_by_id(s.turn)}"
            embed = discord.Embed(title="Cat Battle", description=desc)
            try:
                embed.add_field(name=f"{s.challenger.display_name} — {a1.get('name')}", value=f"HP: {a1.get('hp')}", inline=True)
                embed.add_field(name=f"{s.opponent.display_name} — {a2.get('name')}", value=f"HP: {a2.get('hp')}", inline=True)
                if getattr(s, 'last_action', None):
                    embed.add_field(name="Last action", value=s.last_action, inline=False)
                if getattr(s, 'last_hp_change', None):
                    tgt, old, new, dmg = s.last_hp_change
                    embed.set_footer(text=f"{old} → {new} (-{dmg})")
            except Exception:
                pass
            return embed

        view = BattleView(self.manager, s)
        if s.message:
            try:
                await s.message.edit(embed=_build_embed(), view=view)
            except Exception:
                # fallback: send new message
                sent = await s.channel.send(embed=_build_embed(), view=view)
                s.message = sent
        else:
            sent = await s.channel.send(embed=_build_embed(), view=view)
            s.message = sent


class BattleView(discord.ui.View):
    def __init__(self, manager: Fights, session: FightSession):
        super().__init__(timeout=None)
        self.manager = manager
        self.session = session

    @discord.ui.button(label="Attack", style=discord.ButtonStyle.primary)
    async def attack(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.turn:
            await interaction.response.send_message("It's not your turn.", ephemeral=True)
            return
        # show attack options
        active = self.session.active_cat(interaction.user.id)
        abilities = CAT_ABILITIES.get(active.get('type'), {}).get('attacks', [])
        if not abilities:
            await interaction.response.send_message("No attacks available.", ephemeral=True)
            return
        options = [discord.SelectOption(label=a['name'], value=str(i)) for i, a in enumerate(abilities)]
        sel = AbilitySelect(options=options, session=self.session, manager=self.manager)
        view = discord.ui.View()
        view.add_item(sel)
        await interaction.response.send_message("Choose an attack:", view=view, ephemeral=True)

    @discord.ui.button(label="Switch", style=discord.ButtonStyle.secondary)
    async def switch(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.turn:
            await interaction.response.send_message("It's not your turn.", ephemeral=True)
            return
        # allow switching to another cat in deck
        team = self.session.teams.get(interaction.user.id, [])
        options = []
        for idx, c in enumerate(team):
            options.append(discord.SelectOption(label=f"{c.get('name')} (idx {idx})", value=str(idx)))
        sel = SwitchSelect(options=options, session=self.session)
        view = discord.ui.View()
        view.add_item(sel)
        await interaction.response.send_message("Choose a cat to switch to:", view=view, ephemeral=True)

    @discord.ui.button(label="Surrender", style=discord.ButtonStyle.danger)
    async def surrender(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in [self.session.challenger.id, self.session.opponent.id]:
            await interaction.response.send_message("You're not part of this fight.", ephemeral=True)
            return
        confirm = ConfirmView(self.session, interaction.user.id)
        await interaction.response.send_message("Are you sure you want to surrender?", view=confirm, ephemeral=True)


class AbilitySelect(discord.ui.Select):
    def __init__(self, options, session: FightSession, manager: Fights):
        super().__init__(placeholder="Pick ability", min_values=1, max_values=1, options=options)
        self.session = session
        self.manager = manager

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        ability_idx = int(self.values[0])
        active = self.session.active_cat(user_id)
        abilities = CAT_ABILITIES.get(active.get('type'), {}).get('attacks', [])
        ability = abilities[ability_idx]

        # compute damage: base dmg (which already has modifiers applied from start_fight)
        base = int(active.get('dmg') or 1)
        damage = base + int(ability.get('power', 0))

        # apply weakness modifiers
        defender_id = self.session.opponent.id if user_id == self.session.challenger.id else self.session.challenger.id
        defender = self.session.active_cat(defender_id)
        attacker_type = active.get('type')
        defender_type = defender.get('type')
        if defender_type in TYPE_WEAKNESSES and attacker_type in TYPE_WEAKNESSES.get(defender_type, []):
            # defender weak to attacker
            damage = int(damage * 1.25)

        # apply damage
        old_hp = int(defender.get('hp', 0))
        new_hp = max(0, old_hp - damage)
        defender['hp'] = new_hp

        # record last action and HP change on session
        text = f"{interaction.user.display_name}'s {active.get('name')} used {ability.get('name')} for {damage} damage!"
        self.session.set_last_action(text, target_id=str(defender.get('id')), old_hp=old_hp, new_hp=new_hp, dmg=damage)

        # check if defender fainted
        if new_hp <= 0:
            # advance defender active index
            self.session.active[defender_id] += 1
            if self.session.active[defender_id] >= len(self.session.teams[defender_id]):
                # defender has no cats left -> attacker wins
                win_text = f"{interaction.user.display_name} wins the fight!"
                self.session.set_last_action(win_text)
                
                # Track battle win
                try:
                    mm = _get_main()
                    if mm:
                        Profile = getattr(mm, "Profile", None)
                        if Profile:
                            winner = await Profile.get_or_create(guild_id=self.session.guild.id, user_id=user_id)
                            winner.battles_won = (winner.battles_won or 0) + 1
                            await winner.save()
                except Exception as e:
                    print(f"[BATTLE] Failed to track win: {e}")
                
                # update embed and finish
                if self.session.message:
                    try:
                        emb = discord.Embed(title="Cat Battle", description=win_text)
                        await self.session.message.edit(embed=emb, view=None)
                    except Exception:
                        pass
                return

        # Determine whether this ability consumes the user's turn.
        consumes_turn = bool(ability.get('turn', True))
        if consumes_turn:
            # end turn: pass to defender
            self.session.turn = defender_id
        else:
            # user retains turn (no change)
            pass

        # update the fight embed to reflect changes
        try:
            # build an updated embed
            a1 = self.session.active_cat(self.session.challenger.id)
            a2 = self.session.active_cat(self.session.opponent.id)
            desc = f"Turn: <@{self.session.turn}>"
            embed = discord.Embed(title="Cat Battle", description=desc)
            embed.add_field(name=f"{self.session.challenger.display_name} — {a1.get('name')}", value=f"HP: {a1.get('hp')}", inline=True)
            embed.add_field(name=f"{self.session.opponent.display_name} — {a2.get('name')}", value=f"HP: {a2.get('hp')}", inline=True)
            if getattr(self.session, 'last_action', None):
                embed.add_field(name="Last action", value=self.session.last_action, inline=False)
            if getattr(self.session, 'last_hp_change', None):
                tgt, old, new, dmg = self.session.last_hp_change
                embed.set_footer(text=f"{old} → {new} (-{dmg})")
            if self.session.message:
                await self.session.message.edit(embed=embed, view=BattleView(self.manager, self.session))
        except Exception:
            pass

        # respond to the user privately with a short confirmation
        await interaction.response.send_message(text, ephemeral=True)


class SwitchSelect(discord.ui.Select):
    def __init__(self, options, session: FightSession):
        super().__init__(placeholder="Pick cat index", min_values=1, max_values=1, options=options)
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        idx = int(self.values[0])
        user_id = interaction.user.id
        self.session.active[user_id] = idx
        await interaction.response.send_message(f"Switched to cat index {idx}.", ephemeral=True)
        # end turn: switch to opponent
        opp = self.session.opponent.id if user_id == self.session.challenger.id else self.session.challenger.id
        self.session.turn = opp
        # update embed
        try:
            a1 = self.session.active_cat(self.session.challenger.id)
            a2 = self.session.active_cat(self.session.opponent.id)
            desc = f"Turn: <@{self.session.turn}>"
            embed = discord.Embed(title="Cat Battle", description=desc)
            embed.add_field(name=f"{self.session.challenger.display_name} — {a1.get('name')}", value=f"HP: {a1.get('hp')}", inline=True)
            embed.add_field(name=f"{self.session.opponent.display_name} — {a2.get('name')}", value=f"HP: {a2.get('hp')}", inline=True)
            if getattr(self.session, 'last_action', None):
                embed.add_field(name="Last action", value=self.session.last_action, inline=False)
            if getattr(self.session, 'last_hp_change', None):
                tgt, old, new, dmg = self.session.last_hp_change
                embed.set_footer(text=f"{old} → {new} (-{dmg})")
            if self.session.message:
                await self.session.message.edit(embed=embed, view=BattleView(None, self.session))
        except Exception:
            pass


class ConfirmView(discord.ui.View):
    def __init__(self, session: FightSession, surrendering_id: int):
        super().__init__(timeout=30)
        self.session = session
        self.surrendering_id = surrendering_id

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.danger)
    async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.surrendering_id:
            await interaction.response.send_message("Only the surrendering player can confirm.", ephemeral=True)
            return
        other = self.session.opponent if self.surrendering_id == self.session.challenger.id else self.session.challenger
        text = f"{interaction.user.display_name} surrendered. {other.display_name} wins!"
        self.session.set_last_action(text)
        
        # Track battle win for the other player
        try:
            mm = _get_main()
            if mm:
                Profile = getattr(mm, "Profile", None)
                if Profile:
                    winner = await Profile.get_or_create(guild_id=self.session.guild.id, user_id=other.id)
                    winner.battles_won = (winner.battles_won or 0) + 1
                    await winner.save()
        except Exception as e:
            print(f"[BATTLE] Failed to track win on surrender: {e}")
        
        if self.session.message:
            try:
                emb = discord.Embed(title="Cat Battle", description=text)
                await self.session.message.edit(embed=emb, view=None)
            except Exception:
                pass
        await interaction.response.send_message(text, ephemeral=True)

    @discord.ui.button(label="No", style=discord.ButtonStyle.secondary)
    async def no(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Surrender cancelled.", ephemeral=True)


async def setup(bot: commands.Bot):
    """Register the Fights cog with compatibility for sync/async add_cog implementations."""
    try:
        inst = Fights(bot)
        res = bot.add_cog(inst)
        # Some discord.py implementations return a coroutine from add_cog;
        # await it if so, otherwise continue.
        if asyncio.iscoroutine(res):
            await res
        try:
            print("Fights extension loaded", flush=True)
        except Exception:
            pass
    except Exception:
        import traceback

        print("Failed to setup Fights extension:")
        traceback.print_exc()
