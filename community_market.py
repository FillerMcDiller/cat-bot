import asyncio
import json
import os
import time
from typing import Any, Callable, Dict, List, Literal, Optional

import discord
from discord import app_commands


class CommunityMarketStorage:
    def __init__(self, path: str):
        self.path = path
        self.lock = asyncio.Lock()

    def _ensure(self) -> Dict[str, Any]:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            data = {"next_id": 1, "listings": []}
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return data
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "next_id" not in data:
                data["next_id"] = 1
            if "listings" not in data:
                data["listings"] = []
            return data
        except Exception:
            data = {"next_id": 1, "listings": []}
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return data

    def _save(self, data: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def _owned_cosmetics(profile) -> set[str]:
    raw = profile.owned_cosmetics or ""
    if not raw:
        return set()
    return {x for x in raw.split(",") if x}


def _set_owned_cosmetics(profile, owned: set[str]) -> None:
    profile.owned_cosmetics = ",".join(sorted(owned))


def _find_cosmetic(cosmetics_data: Dict[str, Dict[str, Dict[str, Any]]], query: str) -> Optional[tuple[str, str, str]]:
    q = query.strip().lower()
    for category, items in cosmetics_data.items():
        for cosmetic_id, meta in items.items():
            name = str(meta.get("name", cosmetic_id))
            if cosmetic_id.lower() == q or name.lower() == q:
                return category, cosmetic_id, name
    for category, items in cosmetics_data.items():
        for cosmetic_id, meta in items.items():
            name = str(meta.get("name", cosmetic_id))
            if q in cosmetic_id.lower() or q in name.lower():
                return category, cosmetic_id, name
    return None


def _resolve_pack_name(pack_data: List[Dict[str, Any]], query: str) -> Optional[str]:
    q = query.strip().lower()
    exact = {p["name"].lower(): p["name"] for p in pack_data}
    if q in exact:
        return exact[q]
    for p in pack_data:
        name = p["name"]
        if q in name.lower():
            return name
    return None


def _find_item_key(items: Dict[str, int], query: str) -> Optional[str]:
    q = query.strip().lower()
    for k in items.keys():
        if k.lower() == q:
            return k
    for k in items.keys():
        if q == k.split("_")[0].lower():
            return k
    for k in items.keys():
        if q in k.lower():
            return k
    return None


def _humanize_item_key(item_key: str) -> str:
    parts = str(item_key).rsplit("_", 1)
    item_code = parts[0] if parts else str(item_key)
    tier = parts[1] if len(parts) > 1 else ""
    base = " ".join(p.capitalize() for p in item_code.split("_") if p)
    return f"{base} {tier}".strip()


def register_community_market(
    *,
    bot,
    profile_model,
    get_user_cats: Callable,
    save_user_cats: Callable,
    get_user_items: Callable,
    save_user_items: Callable,
    pack_data: List[Dict[str, Any]],
    cosmetics_data: Dict[str, Dict[str, Dict[str, Any]]],
    check_global_cooldown: Callable,
    get_emoji: Callable,
    data_path: Optional[str] = None,
) -> None:
    if getattr(bot, "_community_market_registered", False):
        return

    market_path = data_path or os.path.join(os.path.dirname(__file__), "data", "community_market.json")
    storage = CommunityMarketStorage(market_path)

    async def _cooldown(interaction: discord.Interaction, seconds: int = 3) -> bool:
        ok = await check_global_cooldown(interaction.user.id, cooldown_seconds=seconds)
        if not ok:
            await interaction.response.send_message("slow down! you're using commands too fast", ephemeral=True)
            return False
        return True

    async def _take_asset_for_listing(
        guild_id: int,
        seller_id: int,
        kind: str,
        name: str,
        quantity: int,
        cat_id: Optional[str],
    ) -> tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
        kind = kind.lower()

        if kind == "cat":
            cats = await get_user_cats(guild_id, seller_id)
            if not cats:
                return None, None, "You have no cats to list."

            selected: List[dict] = []
            if cat_id:
                for c in cats:
                    if str(c.get("id")) == str(cat_id):
                        if c.get("on_adventure"):
                            return None, None, "You cannot list a cat that is on adventure."
                        selected = [c]
                        break
                if not selected:
                    return None, None, "Cat id not found in your collection."
            else:
                q = name.strip().lower()
                pool = [
                    c
                    for c in cats
                    if not c.get("on_adventure")
                    and (
                        str(c.get("type", "")).lower() == q
                        or str(c.get("name", "")).lower() == q
                        or q in str(c.get("type", "")).lower()
                        or q in str(c.get("name", "")).lower()
                    )
                ]
                if len(pool) < quantity:
                    return None, None, f"Not enough matching cats to list (need {quantity}, found {len(pool)})."
                selected = pool[:quantity]

            selected_ids = {str(c.get("id")) for c in selected}
            remaining = [c for c in cats if str(c.get("id")) not in selected_ids]
            await save_user_cats(guild_id, seller_id, remaining)

            display = f"{selected[0].get('type', 'Cat')} x{len(selected)}"
            if len(selected) == 1:
                display = f"{selected[0].get('name', selected[0].get('type', 'Cat'))}"
            payload = {"cats": selected}
            return payload, display, None

        if kind == "pack":
            pack_name = _resolve_pack_name(pack_data, name)
            if not pack_name:
                return None, None, "Unknown pack name."

            profile = await profile_model.get_or_create(guild_id=guild_id, user_id=seller_id)
            field = f"pack_{pack_name.lower()}"
            have = int(getattr(profile, field, 0) or 0)
            if have < quantity:
                return None, None, f"You only have {have} {pack_name} packs."

            setattr(profile, field, have - quantity)
            await profile.save()
            payload = {"pack_name": pack_name}
            return payload, f"{pack_name} Pack", None

        if kind == "item":
            items = await get_user_items(guild_id, seller_id)
            if not items:
                return None, None, "You have no items to list."
            item_key = _find_item_key(items, name)
            if not item_key:
                return None, None, "Item not found in your inventory."
            have = int(items.get(item_key, 0) or 0)
            if have < quantity:
                return None, None, f"You only have {have} of {item_key}."

            items[item_key] = have - quantity
            await save_user_items(guild_id, seller_id, items)
            payload = {"item_key": item_key}
            return payload, _humanize_item_key(item_key), None

        if kind == "cosmetic":
            profile = await profile_model.get_or_create(guild_id=guild_id, user_id=seller_id)
            found = _find_cosmetic(cosmetics_data, name)
            if not found:
                return None, None, "Cosmetic not found."
            category, cosmetic_id, cosmetic_name = found
            owned = _owned_cosmetics(profile)
            if cosmetic_id not in owned:
                return None, None, "You do not own that cosmetic."

            owned.remove(cosmetic_id)
            _set_owned_cosmetics(profile, owned)

            if category == "badges" and profile.equipped_badge == cosmetic_id:
                profile.equipped_badge = ""
            elif category == "titles" and profile.equipped_title == cosmetic_id:
                profile.equipped_title = ""
            elif category == "effects" and profile.equipped_effect == cosmetic_id:
                profile.equipped_effect = "none"
            elif category == "colors" and profile.equipped_color == cosmetic_id:
                profile.equipped_color = "default"

            await profile.save()
            payload = {"category": category, "cosmetic_id": cosmetic_id, "cosmetic_name": cosmetic_name}
            return payload, cosmetic_name, None

        if kind == "other":
            payload = {"label": name}
            return payload, name, None

        return None, None, "Unsupported listing type."

    async def _deliver_asset_to_buyer(guild_id: int, buyer_id: int, listing: Dict[str, Any], quantity: int) -> Optional[str]:
        kind = listing["kind"]
        payload = listing.get("payload", {})

        if kind == "cat":
            cats = payload.get("cats", [])
            if len(cats) < quantity:
                return "Listing no longer has enough cat instances."
            take = cats[:quantity]
            payload["cats"] = cats[quantity:]
            buyer_cats = await get_user_cats(guild_id, buyer_id)
            buyer_cats.extend(take)
            await save_user_cats(guild_id, buyer_id, buyer_cats)
            listing["payload"] = payload
            return None

        if kind == "pack":
            pack_name = payload.get("pack_name")
            if not pack_name:
                return "Invalid pack payload."
            buyer = await profile_model.get_or_create(guild_id=guild_id, user_id=buyer_id)
            field = f"pack_{pack_name.lower()}"
            cur = int(getattr(buyer, field, 0) or 0)
            setattr(buyer, field, cur + quantity)
            await buyer.save()
            return None

        if kind == "item":
            item_key = payload.get("item_key")
            if not item_key:
                return "Invalid item payload."
            items = await get_user_items(guild_id, buyer_id)
            items[item_key] = int(items.get(item_key, 0) or 0) + quantity
            await save_user_items(guild_id, buyer_id, items)
            return None

        if kind == "cosmetic":
            cosmetic_id = payload.get("cosmetic_id")
            if not cosmetic_id:
                return "Invalid cosmetic payload."
            buyer = await profile_model.get_or_create(guild_id=guild_id, user_id=buyer_id)
            owned = _owned_cosmetics(buyer)
            owned.add(cosmetic_id)
            _set_owned_cosmetics(buyer, owned)
            await buyer.save()
            return None

        if kind == "other":
            return None

        return "Unsupported listing type."

    async def _query_browse_listings(
        guild_id: int,
        *,
        kind: Optional[str] = None,
        name: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        seller_id: Optional[int] = None,
        sort_by: str = "newest",
    ) -> List[Dict[str, Any]]:
        async with storage.lock:
            data = storage._ensure()
            listings = [
                l for l in data["listings"] if l.get("status") == "active" and int(l.get("guild_id", 0)) == guild_id
            ]

        if kind:
            listings = [l for l in listings if l.get("kind") == kind]
        if name:
            q = name.lower().strip()
            listings = [l for l in listings if q in str(l.get("name", "")).lower()]
        if min_price is not None:
            listings = [l for l in listings if int(l.get("unit_price", 0)) >= min_price]
        if max_price is not None:
            listings = [l for l in listings if int(l.get("unit_price", 0)) <= max_price]
        if seller_id is not None:
            listings = [l for l in listings if int(l.get("seller_id", 0)) == seller_id]

        if sort_by == "newest":
            listings.sort(key=lambda x: int(x.get("created_at", 0)), reverse=True)
        elif sort_by == "oldest":
            listings.sort(key=lambda x: int(x.get("created_at", 0)))
        elif sort_by == "price_low":
            listings.sort(key=lambda x: int(x.get("unit_price", 0)))
        elif sort_by == "price_high":
            listings.sort(key=lambda x: int(x.get("unit_price", 0)), reverse=True)
        elif sort_by == "name":
            listings.sort(key=lambda x: str(x.get("name", "")).lower())

        return listings

    async def _build_browse_embed(
        guild_id: int,
        *,
        kind: Optional[str] = None,
        name: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        seller_id: Optional[int] = None,
        sort_by: str = "newest",
        page: int = 1,
        per_page: int = 3,
    ) -> tuple[discord.Embed, List[Dict[str, Any]], int, int, int]:
        listings = await _query_browse_listings(
            guild_id,
            kind=kind,
            name=name,
            min_price=min_price,
            max_price=max_price,
            seller_id=seller_id,
            sort_by=sort_by,
        )

        total = len(listings)
        pages = max(1, (total + per_page - 1) // per_page)
        page = max(1, min(page, pages))
        start = (page - 1) * per_page
        chunk = listings[start : start + per_page]

        embed = discord.Embed(
            title="Community Market",
            description=(
                f"Listings: **{total}**\n"
                f"Filters: kind={kind or 'any'}, name={name or 'any'}, "
                f"price={min_price if min_price is not None else 0}-{max_price if max_price is not None else 'max'}"
            ),
            color=discord.Color.from_rgb(110, 89, 60),
        )

        if not chunk:
            embed.add_field(name="No listings", value="No active listings match these filters.", inline=False)
            return embed, chunk, page, pages, total

        lines = []
        for l in chunk:
            lid = l["id"]
            l_kind = l.get("kind", "other")
            l_name = l.get("name", "Unknown")
            qty = int(l.get("quantity", 1))
            unit_price = int(l.get("unit_price", 0))
            sid = int(l.get("seller_id", 0))
            details = (l.get("details") or "").strip()
            extra = f" | {details}" if details else ""
            lines.append(f"`#{lid}` {l_name} ({l_kind}) x{qty} - {unit_price:,} kibble each - seller <@{sid}>{extra}")

        embed.add_field(name=f"Page {page}/{pages}", value="\n".join(lines), inline=False)
        embed.set_footer(text="Click a Buy button below to purchase one unit.")
        return embed, chunk, page, pages, total

    async def _build_my_embed(guild_id: int, user_id: int, page: int = 1) -> discord.Embed:
        async with storage.lock:
            data = storage._ensure()
            listings = [
                l
                for l in data["listings"]
                if l.get("status") == "active"
                and int(l.get("guild_id", 0)) == guild_id
                and int(l.get("seller_id", 0)) == user_id
            ]

        listings.sort(key=lambda x: int(x.get("created_at", 0)), reverse=True)
        per_page = 10
        total = len(listings)
        pages = max(1, (total + per_page - 1) // per_page)
        page = max(1, min(page, pages))
        start = (page - 1) * per_page
        chunk = listings[start : start + per_page]

        embed = discord.Embed(
            title="Your Market Listings",
            description=f"Active listings: {total}",
            color=discord.Color.from_rgb(110, 89, 60),
        )
        if not chunk:
            embed.add_field(name="None", value="You have no active listings.", inline=False)
            return embed

        lines = [
            f"`#{l['id']}` {l.get('name')} ({l.get('kind')}) x{l.get('quantity')} - {int(l.get('unit_price', 0)):,} kibble"
            for l in chunk
        ]
        embed.add_field(name=f"Page {page}/{pages}", value="\n".join(lines), inline=False)
        return embed

    async def _purchase_listing(it: discord.Interaction, listing_id: int, quantity: int = 1) -> tuple[bool, str]:
        if quantity <= 0:
            return False, "Quantity must be positive."

        async with storage.lock:
            data = storage._ensure()
            listing = next((l for l in data["listings"] if int(l.get("id", 0)) == listing_id), None)
            if not listing or listing.get("status") != "active":
                return False, "That listing is not active."
            if int(listing.get("guild_id", 0)) != it.guild.id:
                return False, "That listing belongs to another server."
            if int(listing.get("seller_id", 0)) == it.user.id:
                return False, "You cannot buy your own listing."

            available = int(listing.get("quantity", 0))
            if quantity > available:
                return False, f"Only {available} unit(s) available."

            buyer = await profile_model.get_or_create(guild_id=it.guild.id, user_id=it.user.id)
            seller = await profile_model.get_or_create(guild_id=it.guild.id, user_id=int(listing["seller_id"]))
            total_cost = int(listing.get("unit_price", 0)) * quantity
            buyer_kibble = int(getattr(buyer, "kibble", 0) or 0)
            if buyer_kibble < total_cost:
                return False, f"Not enough kibble. Need {total_cost:,}, you have {buyer_kibble:,}."

            transfer_error = await _deliver_asset_to_buyer(it.guild.id, it.user.id, listing, quantity)
            if transfer_error:
                return False, f"Purchase failed: {transfer_error}"

            buyer.kibble = buyer_kibble - total_cost
            seller.kibble = int(getattr(seller, "kibble", 0) or 0) + total_cost
            await buyer.save()
            await seller.save()

            listing["quantity"] = available - quantity
            if int(listing["quantity"]) <= 0:
                listing["status"] = "sold"
                listing["sold_at"] = int(time.time())
                listing["buyer_id"] = it.user.id
            storage._save(data)

        if listing.get("kind") == "other":
            return True, (
                f"Bought {quantity}x from listing #{listing_id} for {total_cost:,} kibble. "
                "This 'other' listing is manual delivery."
            )

        return True, f"Bought {quantity}x **{listing.get('name', 'item')}** for **{total_cost:,}** kibble."

    def _listing_emoji_and_cat_name(listing: Dict[str, Any]) -> tuple[str, str]:
        kind = str(listing.get("kind", "other"))
        name = str(listing.get("name", "item"))

        emoji = "📦"
        cat_name = ""
        try:
            if kind == "cat":
                payload_cats = listing.get("payload", {}).get("cats", [])
                cat_type = (payload_cats[0].get("type") if payload_cats else name) or "cat"
                emoji = get_emoji(f"{str(cat_type).lower()}cat")
                if payload_cats:
                    cat_name = str(payload_cats[0].get("name", "") or "")
            elif kind == "pack":
                base_pack = name.split()[0].lower()
                emoji = get_emoji(f"{base_pack}pack")
            elif kind == "item":
                base_item = name.split("_")[0].lower()
                emoji = get_emoji(base_item)
            elif kind == "cosmetic":
                emoji = get_emoji("ach")
        except Exception:
            emoji = "📦"
            cat_name = ""

        return emoji, cat_name

    def _listing_second_line(listing: Dict[str, Any]) -> str:
        kind = str(listing.get("kind", "other"))
        qty = int(listing.get("quantity", 1))
        unit_price = int(listing.get("unit_price", 0))
        price_segment = f"{unit_price:,} kibble each"
        _, cat_name = _listing_emoji_and_cat_name(listing)

        if cat_name:
            return f"{kind} x{qty} - {cat_name} - {price_segment}"
        return f"{kind} x{qty} - {price_segment}"

    async def _cancel_listing(it: discord.Interaction, listing_id: int) -> tuple[bool, str]:
        async with storage.lock:
            data = storage._ensure()
            listing = next((l for l in data["listings"] if int(l.get("id", 0)) == listing_id), None)
            if not listing or listing.get("status") != "active":
                return False, "That listing is not active."
            if int(listing.get("guild_id", 0)) != it.guild.id:
                return False, "That listing belongs to another server."
            if int(listing.get("seller_id", 0)) != it.user.id:
                return False, "You can only cancel your own listings."

            qty = int(listing.get("quantity", 0))
            payload = listing.get("payload", {})
            kind = listing.get("kind")

            if kind == "cat":
                cats = payload.get("cats", [])
                my_cats = await get_user_cats(it.guild.id, it.user.id)
                my_cats.extend(cats)
                await save_user_cats(it.guild.id, it.user.id, my_cats)
            elif kind == "pack":
                pack_name = payload.get("pack_name")
                if pack_name:
                    profile = await profile_model.get_or_create(guild_id=it.guild.id, user_id=it.user.id)
                    field = f"pack_{pack_name.lower()}"
                    setattr(profile, field, int(getattr(profile, field, 0) or 0) + qty)
                    await profile.save()
            elif kind == "item":
                item_key = payload.get("item_key")
                if item_key:
                    items = await get_user_items(it.guild.id, it.user.id)
                    items[item_key] = int(items.get(item_key, 0) or 0) + qty
                    await save_user_items(it.guild.id, it.user.id, items)
            elif kind == "cosmetic":
                cosmetic_id = payload.get("cosmetic_id")
                if cosmetic_id:
                    profile = await profile_model.get_or_create(guild_id=it.guild.id, user_id=it.user.id)
                    owned = _owned_cosmetics(profile)
                    owned.add(cosmetic_id)
                    _set_owned_cosmetics(profile, owned)
                    await profile.save()

            listing["status"] = "cancelled"
            listing["cancelled_at"] = int(time.time())
            storage._save(data)

        return True, f"Cancelled listing #{listing_id} and returned unsold assets."

    @bot.tree.command(name="market", description="Open the community market GUI")
    async def market(interaction: discord.Interaction):
        if not await _cooldown(interaction):
            return

        class BrowseListingsView(discord.ui.LayoutView):
            def __init__(
                self,
                author_id: int,
                guild_id: int,
                *,
                kind: Optional[str] = None,
                name: Optional[str] = None,
                min_price: Optional[int] = None,
                max_price: Optional[int] = None,
                sort_by: str = "newest",
                page: int = 1,
            ):
                super().__init__(timeout=300)
                self.author_id = author_id
                self.guild_id = guild_id
                self.kind = kind
                self.name = name
                self.min_price = min_price
                self.max_price = max_price
                self.sort_by = sort_by
                self.page = page

            async def _auth(self, it: discord.Interaction) -> bool:
                if it.user.id != self.author_id:
                    await it.response.send_message("This browse panel isn't yours.", ephemeral=True)
                    return False
                return True

            async def _render(self) -> tuple[List[Dict[str, Any]], int, int, int]:
                listings = await _query_browse_listings(
                    self.guild_id,
                    kind=self.kind,
                    name=self.name,
                    min_price=self.min_price,
                    max_price=self.max_price,
                    sort_by=self.sort_by,
                )

                per_page = 3
                total = len(listings)
                pages = max(1, (total + per_page - 1) // per_page)
                page = max(1, min(self.page, pages))
                self.page = page
                start = (page - 1) * per_page
                chunk = listings[start : start + per_page]

                self._rebuild_items(chunk, page, pages, total)
                return chunk, page, pages, total

            def _rebuild_items(self, chunk: List[Dict[str, Any]], page: int, pages: int, total: int) -> None:
                self.clear_items()

                filter_text = (
                    f"kind={self.kind or 'any'}, name={self.name or 'any'}, "
                    f"price={self.min_price if self.min_price is not None else 0}-{self.max_price if self.max_price is not None else 'max'}, "
                    f"sort={self.sort_by}"
                )

                header = discord.ui.Container(
                    discord.ui.TextDisplay("## Community Market"),
                    discord.ui.TextDisplay(f"Listings: **{total}**"),
                    discord.ui.TextDisplay(f"Filters: {filter_text}"),
                    discord.ui.TextDisplay(f"-# Page {page}/{pages}"),
                )
                self.add_item(header)

                if not chunk:
                    self.add_item(discord.ui.Container(discord.ui.TextDisplay("No active listings match these filters.")))

                refresh_btn = discord.ui.Button(label="Refresh", style=discord.ButtonStyle.secondary, row=0)

                async def refresh_cb(btn_it: discord.Interaction):
                    if not await self._auth(btn_it):
                        return
                    await self._render()
                    await btn_it.response.edit_message(content=None, embed=None, view=self)

                refresh_btn.callback = refresh_cb

                prev_btn = discord.ui.Button(label="Prev", style=discord.ButtonStyle.secondary, row=1, disabled=page <= 1)
                next_btn = discord.ui.Button(label="Next", style=discord.ButtonStyle.secondary, row=1, disabled=page >= pages)
                info_btn = discord.ui.Button(
                    label=f"Page {page}/{pages} ({total} listings)",
                    style=discord.ButtonStyle.secondary,
                    row=1,
                    disabled=True,
                )

                async def prev_cb(btn_it: discord.Interaction):
                    if not await self._auth(btn_it):
                        return
                    self.page = max(1, self.page - 1)
                    await self._render()
                    await btn_it.response.edit_message(content=None, embed=None, view=self)

                async def next_cb(btn_it: discord.Interaction):
                    if not await self._auth(btn_it):
                        return
                    self.page = self.page + 1
                    await self._render()
                    await btn_it.response.edit_message(content=None, embed=None, view=self)

                refresh_btn.callback = refresh_cb
                prev_btn.callback = prev_cb
                next_btn.callback = next_cb
                self.add_item(discord.ui.ActionRow(refresh_btn, prev_btn, next_btn, info_btn))

                for listing in chunk:
                    lid = int(listing.get("id", 0))
                    name = str(listing.get("name", "item"))
                    kind = str(listing.get("kind", "other"))
                    unit_price = int(listing.get("unit_price", 0))
                    seller = int(listing.get("seller_id", 0))
                    details = (listing.get("details") or "").strip()
                    buy_btn = discord.ui.Button(label=f"Buy ({unit_price:,})"[:80], style=discord.ButtonStyle.success)

                    async def buy_cb(btn_it: discord.Interaction, listing_id: int = lid):
                        if not await self._auth(btn_it):
                            return
                        await btn_it.response.defer()
                        ok, msg = await _purchase_listing(btn_it, listing_id, quantity=1)
                        await self._render()
                        await btn_it.edit_original_response(content=None, embed=None, view=self)
                        await btn_it.followup.send(msg, ephemeral=True)

                    buy_btn.callback = buy_cb
                    emoji, _ = _listing_emoji_and_cat_name(listing)
                    second_line = _listing_second_line(listing)

                    listing_lines = [
                        discord.ui.TextDisplay(f"### #{lid} {name}"),
                        discord.ui.TextDisplay(f"{emoji} - {name}"),
                        discord.ui.TextDisplay(second_line),
                        discord.ui.TextDisplay(f"seller <@{seller}>"),
                    ]
                    if details:
                        listing_lines.append(discord.ui.TextDisplay(f"-# {details}"))
                    listing_card = discord.ui.Container(*listing_lines, discord.ui.ActionRow(buy_btn))
                    self.add_item(listing_card)

        class MyListingsView(discord.ui.LayoutView):
            def __init__(self, author_id: int, guild_id: int, page: int = 1):
                super().__init__(timeout=300)
                self.author_id = author_id
                self.guild_id = guild_id
                self.page = page

            async def _auth(self, it: discord.Interaction) -> bool:
                if it.user.id != self.author_id:
                    await it.response.send_message("This listings panel isn't yours.", ephemeral=True)
                    return False
                return True

            async def _render(self) -> tuple[List[Dict[str, Any]], int, int, int]:
                async with storage.lock:
                    data = storage._ensure()
                    listings = [
                        l
                        for l in data["listings"]
                        if l.get("status") == "active"
                        and int(l.get("guild_id", 0)) == self.guild_id
                        and int(l.get("seller_id", 0)) == self.author_id
                    ]

                listings.sort(key=lambda x: int(x.get("created_at", 0)), reverse=True)
                per_page = 3
                total = len(listings)
                pages = max(1, (total + per_page - 1) // per_page)
                page = max(1, min(self.page, pages))
                self.page = page
                start = (page - 1) * per_page
                chunk = listings[start : start + per_page]

                self._rebuild_items(chunk, page, pages, total)
                return chunk, page, pages, total

            def _rebuild_items(self, chunk: List[Dict[str, Any]], page: int, pages: int, total: int) -> None:
                self.clear_items()

                header = discord.ui.Container(
                    discord.ui.TextDisplay("## Your Market Listings"),
                    discord.ui.TextDisplay(f"Active listings: **{total}**"),
                    discord.ui.TextDisplay(f"-# Page {page}/{pages}"),
                )
                self.add_item(header)

                if not chunk:
                    self.add_item(discord.ui.Container(discord.ui.TextDisplay("You have no active listings.")))

                refresh_btn = discord.ui.Button(label="Refresh", style=discord.ButtonStyle.secondary)
                prev_btn = discord.ui.Button(label="Prev", style=discord.ButtonStyle.secondary, disabled=page <= 1)
                next_btn = discord.ui.Button(label="Next", style=discord.ButtonStyle.secondary, disabled=page >= pages)
                cancel_tab_btn = discord.ui.Button(label="Cancel by ID", style=discord.ButtonStyle.danger)

                async def refresh_cb(btn_it: discord.Interaction):
                    if not await self._auth(btn_it):
                        return
                    await self._render()
                    await btn_it.response.edit_message(content=None, embed=None, view=self)

                async def prev_cb(btn_it: discord.Interaction):
                    if not await self._auth(btn_it):
                        return
                    self.page = max(1, self.page - 1)
                    await self._render()
                    await btn_it.response.edit_message(content=None, embed=None, view=self)

                async def next_cb(btn_it: discord.Interaction):
                    if not await self._auth(btn_it):
                        return
                    self.page = self.page + 1
                    await self._render()
                    await btn_it.response.edit_message(content=None, embed=None, view=self)

                async def cancel_tab_cb(btn_it: discord.Interaction):
                    if not await self._auth(btn_it):
                        return

                    class CancelModal(discord.ui.Modal, title="Cancel Listing"):
                        listing_id = discord.ui.TextInput(label="Listing ID", required=True, max_length=20)

                        async def on_submit(self2, mit: discord.Interaction):
                            try:
                                listing_id = int(self2.listing_id.value.strip())
                            except Exception:
                                await mit.response.send_message("Listing ID must be a number.", ephemeral=True)
                                return

                            await mit.response.defer(ephemeral=True)
                            ok, msg = await _cancel_listing(mit, listing_id)
                            await self._render()
                            await mit.edit_original_response(content=None, embed=None, view=self)
                            await mit.followup.send(msg, ephemeral=True)

                    await btn_it.response.send_modal(CancelModal())

                refresh_btn.callback = refresh_cb
                prev_btn.callback = prev_cb
                next_btn.callback = next_cb
                cancel_tab_btn.callback = cancel_tab_cb
                self.add_item(discord.ui.ActionRow(refresh_btn, prev_btn, next_btn, cancel_tab_btn))

                for listing in chunk:
                    lid = int(listing.get("id", 0))
                    name = str(listing.get("name", "item"))
                    seller = int(listing.get("seller_id", 0))
                    details = (listing.get("details") or "").strip()
                    emoji, _ = _listing_emoji_and_cat_name(listing)
                    second_line = _listing_second_line(listing)
                    cancel_btn = discord.ui.Button(label=f"Cancel #{lid}"[:80], style=discord.ButtonStyle.danger)

                    async def cancel_cb(btn_it: discord.Interaction, listing_id: int = lid):
                        if not await self._auth(btn_it):
                            return
                        await btn_it.response.defer()
                        ok, msg = await _cancel_listing(btn_it, listing_id)
                        await self._render()
                        await btn_it.edit_original_response(content=None, embed=None, view=self)
                        await btn_it.followup.send(msg, ephemeral=True)

                    cancel_btn.callback = cancel_cb

                    listing_lines = [
                        discord.ui.TextDisplay(f"### #{lid} {name}"),
                        discord.ui.TextDisplay(f"{emoji} - {name}"),
                        discord.ui.TextDisplay(second_line),
                        discord.ui.TextDisplay(f"seller <@{seller}>"),
                    ]
                    if details:
                        listing_lines.append(discord.ui.TextDisplay(f"-# {details}"))

                    listing_card = discord.ui.Container(*listing_lines, discord.ui.ActionRow(cancel_btn))
                    self.add_item(listing_card)

        class MarketView(discord.ui.View):
            def __init__(self, author_id: int):
                super().__init__(timeout=300)
                self.author_id = author_id

            async def _auth(self, it: discord.Interaction) -> bool:
                if it.user.id != self.author_id:
                    await it.response.send_message("This market panel isn't yours.", ephemeral=True)
                    return False
                return True

            @discord.ui.button(label="Browse", style=discord.ButtonStyle.primary)
            async def browse_btn(self, it: discord.Interaction, _: discord.ui.Button):
                if not await self._auth(it):
                    return

                class BrowseModal(discord.ui.Modal, title="Browse Market"):
                    kind = discord.ui.TextInput(label="Kind (cat/pack/item/cosmetic/other)", required=False, max_length=20)
                    name = discord.ui.TextInput(label="Name contains (optional)", required=False, max_length=80)
                    price = discord.ui.TextInput(label="Price range min-max (e.g. 100-5000)", required=False, max_length=40)
                    sort = discord.ui.TextInput(label="Sort (newest/oldest/price/name)", required=False, max_length=20)
                    page = discord.ui.TextInput(label="Page number", required=False, default="1", max_length=8)

                    async def on_submit(self2, mit: discord.Interaction):
                        k = self2.kind.value.strip().lower() or None
                        n = self2.name.value.strip() or None
                        s = self2.sort.value.strip().lower() or "newest"
                        p = int(self2.page.value.strip() or "1")
                        p = max(1, p)

                        min_price = None
                        max_price = None
                        raw_price = self2.price.value.strip()
                        if raw_price:
                            try:
                                a, b = raw_price.split("-", 1)
                                min_price = int(a.strip()) if a.strip() else None
                                max_price = int(b.strip()) if b.strip() else None
                            except Exception:
                                await mit.response.send_message("Invalid price range. Use format like 100-5000", ephemeral=True)
                                return

                        view = BrowseListingsView(
                            author_id=mit.user.id,
                            guild_id=mit.guild.id,
                            kind=k,
                            name=n,
                            min_price=min_price,
                            max_price=max_price,
                            sort_by=s,
                            page=p,
                        )
                        await view._render()
                        await mit.response.send_message(view=view, ephemeral=True)

                await it.response.send_modal(BrowseModal())

            @discord.ui.button(label="Sell", style=discord.ButtonStyle.success)
            async def sell_btn(self, it: discord.Interaction, _: discord.ui.Button):
                if not await self._auth(it):
                    return
                profile = await profile_model.get_or_create(guild_id=it.guild.id, user_id=it.user.id)
                cats = await get_user_cats(it.guild.id, it.user.id)
                items = await get_user_items(it.guild.id, it.user.id)

                cat_counts: Dict[str, int] = {}
                for c in cats:
                    if c.get("on_adventure"):
                        continue
                    ctype = str(c.get("type", "")).strip()
                    if not ctype:
                        continue
                    cat_counts[ctype] = cat_counts.get(ctype, 0) + 1

                pack_entries: List[Dict[str, Any]] = []
                for p in pack_data:
                    pack_name = str(p.get("name", "")).strip()
                    if not pack_name:
                        continue
                    have = int(getattr(profile, f"pack_{pack_name.lower()}", 0) or 0)
                    if have > 0:
                        pack_entries.append({"value": pack_name, "label": f"{pack_name} Pack x{have}", "qty": have})

                item_entries: List[Dict[str, Any]] = []
                for item_key, count in items.items():
                    qty = int(count or 0)
                    if qty <= 0:
                        continue
                    item_entries.append({
                        "value": str(item_key),
                        "label": f"{_humanize_item_key(str(item_key))} x{qty}",
                        "qty": qty,
                    })

                owned = _owned_cosmetics(profile)
                cosmetic_entries: List[Dict[str, Any]] = []
                for category, entries in cosmetics_data.items():
                    for cosmetic_id, meta in entries.items():
                        if cosmetic_id not in owned:
                            continue
                        cosmetic_name = str(meta.get("name", cosmetic_id))
                        cosmetic_entries.append({
                            "value": cosmetic_id,
                            "label": f"{cosmetic_name} ({category})"[:100],
                            "qty": 1,
                        })

                sellable: Dict[str, List[Dict[str, Any]]] = {
                    "cat": [{"value": k, "label": f"{k} x{v}"[:100], "qty": v} for k, v in sorted(cat_counts.items())],
                    "pack": pack_entries,
                    "item": sorted(item_entries, key=lambda x: x["label"].lower()),
                    "cosmetic": sorted(cosmetic_entries, key=lambda x: x["label"].lower()),
                }

                available_kinds = [k for k in ("cat", "pack", "item", "cosmetic") if sellable.get(k)]
                if not available_kinds:
                    await it.response.send_message(
                        "You don't have sellable assets right now (cats not on adventure, packs, items, or cosmetics).",
                        ephemeral=True,
                    )
                    return

                class SellWizardView(discord.ui.View):
                    def __init__(self, author_id: int, guild_id: int):
                        super().__init__(timeout=300)
                        self.author_id = author_id
                        self.guild_id = guild_id
                        self.selected_kind: Optional[str] = available_kinds[0] if available_kinds else None
                        self.selected_asset: Optional[str] = None
                        self._rebuild()

                    async def _auth(self, mit: discord.Interaction) -> bool:
                        if mit.user.id != self.author_id:
                            await mit.response.send_message("This sell panel isn't yours.", ephemeral=True)
                            return False
                        return True

                    def _rebuild(self):
                        self.clear_items()

                        kind_options = []
                        kind_emoji = {"cat": "🐱", "pack": "📦", "item": "🧪", "cosmetic": "🏷️"}
                        for k in available_kinds:
                            kind_options.append(
                                discord.SelectOption(
                                    label=k.title(),
                                    value=k,
                                    emoji=kind_emoji.get(k),
                                    description=f"{len(sellable.get(k, []))} available",
                                    default=(k == self.selected_kind),
                                )
                            )

                        kind_select = discord.ui.Select(
                            placeholder="Select type to sell...",
                            options=kind_options,
                            min_values=1,
                            max_values=1,
                            row=0,
                        )

                        async def kind_cb(mit: discord.Interaction):
                            if not await self._auth(mit):
                                return
                            self.selected_kind = kind_select.values[0]
                            self.selected_asset = None
                            self._rebuild()
                            await mit.response.edit_message(view=self)

                        kind_select.callback = kind_cb
                        self.add_item(kind_select)

                        assets = sellable.get(self.selected_kind or "", [])
                        asset_options = []
                        for asset in assets[:25]:
                            asset_options.append(discord.SelectOption(label=asset["label"][:100], value=asset["value"][:100]))

                        if asset_options:
                            asset_select = discord.ui.Select(
                                placeholder="Select exact asset...",
                                options=asset_options,
                                min_values=1,
                                max_values=1,
                                row=1,
                            )

                            async def asset_cb(mit: discord.Interaction):
                                if not await self._auth(mit):
                                    return
                                self.selected_asset = asset_select.values[0]
                                self._rebuild()
                                await mit.response.edit_message(view=self)

                            asset_select.callback = asset_cb
                            self.add_item(asset_select)

                        continue_btn = discord.ui.Button(
                            label="Continue",
                            style=discord.ButtonStyle.success,
                            row=2,
                            disabled=not (self.selected_kind and self.selected_asset),
                        )
                        cancel_btn = discord.ui.Button(label="Close", style=discord.ButtonStyle.secondary, row=2)

                        async def continue_cb(mit: discord.Interaction):
                            if not await self._auth(mit):
                                return
                            if not self.selected_kind or not self.selected_asset:
                                await mit.response.send_message("Choose a type and asset first.", ephemeral=True)
                                return

                            selected_kind = self.selected_kind
                            selected_asset = self.selected_asset
                            selected_qty = 1
                            for asset in sellable.get(selected_kind, []):
                                if asset["value"] == selected_asset:
                                    selected_qty = int(asset.get("qty", 1) or 1)
                                    break

                            class SellDetailsModal(discord.ui.Modal, title="Create Listing"):
                                price = discord.ui.TextInput(label="Price per unit (kibble)", required=True, max_length=20)
                                quantity = discord.ui.TextInput(
                                    label=f"Quantity (max {selected_qty})",
                                    required=False,
                                    default="1",
                                    max_length=10,
                                )
                                details = discord.ui.TextInput(label="Optional details", required=False, max_length=120)

                                async def on_submit(self2, submit_it: discord.Interaction):
                                    try:
                                        price = int(self2.price.value.strip())
                                        quantity = int(self2.quantity.value.strip() or "1")
                                    except Exception:
                                        await submit_it.response.send_message("Price and quantity must be numbers.", ephemeral=True)
                                        return

                                    if price <= 0 or quantity <= 0:
                                        await submit_it.response.send_message("Price and quantity must be positive.", ephemeral=True)
                                        return

                                    if quantity > selected_qty:
                                        await submit_it.response.send_message(
                                            f"You only have {selected_qty} available for that asset.",
                                            ephemeral=True,
                                        )
                                        return

                                    if selected_kind == "cosmetic":
                                        quantity = 1

                                    await submit_it.response.defer(ephemeral=True)
                                    payload, display_name, error = await _take_asset_for_listing(
                                        guild_id=submit_it.guild.id,
                                        seller_id=submit_it.user.id,
                                        kind=selected_kind,
                                        name=selected_asset,
                                        quantity=quantity,
                                        cat_id=None,
                                    )
                                    if error:
                                        await submit_it.followup.send(error, ephemeral=True)
                                        return

                                    async with storage.lock:
                                        data = storage._ensure()
                                        listing_id = int(data["next_id"])
                                        data["next_id"] = listing_id + 1
                                        listing = {
                                            "id": listing_id,
                                            "guild_id": submit_it.guild.id,
                                            "seller_id": submit_it.user.id,
                                            "kind": selected_kind,
                                            "name": display_name or selected_asset,
                                            "unit_price": int(price),
                                            "quantity": int(quantity),
                                            "details": self2.details.value.strip(),
                                            "payload": payload or {},
                                            "status": "active",
                                            "created_at": int(time.time()),
                                        }
                                        data["listings"].append(listing)
                                        storage._save(data)

                                    await submit_it.followup.send(
                                        f"Listed #{listing_id}: **{listing['name']}** ({selected_kind}) x{listing['quantity']} for **{listing['unit_price']:,}** kibble each.",
                                        ephemeral=True,
                                    )

                            await mit.response.send_modal(SellDetailsModal())

                        async def cancel_cb(mit: discord.Interaction):
                            if not await self._auth(mit):
                                return
                            await mit.response.edit_message(content="Closed sell panel.", view=None)

                        continue_btn.callback = continue_cb
                        cancel_btn.callback = cancel_cb
                        self.add_item(continue_btn)
                        self.add_item(cancel_btn)

                wizard = SellWizardView(author_id=it.user.id, guild_id=it.guild.id)
                await it.response.send_message(
                    "Select what you want to sell:",
                    view=wizard,
                    ephemeral=True,
                )

            @discord.ui.button(label="My Listings", style=discord.ButtonStyle.secondary)
            async def my_btn(self, it: discord.Interaction, _: discord.ui.Button):
                if not await self._auth(it):
                    return
                view = MyListingsView(author_id=it.user.id, guild_id=it.guild.id, page=1)
                await view._render()
                await it.response.send_message(view=view, ephemeral=True)

            @discord.ui.button(label="Cancel Listing", style=discord.ButtonStyle.danger)
            async def cancel_btn(self, it: discord.Interaction, _: discord.ui.Button):
                if not await self._auth(it):
                    return

                class CancelModal(discord.ui.Modal, title="Cancel Listing"):
                    listing_id = discord.ui.TextInput(label="Listing ID", required=True, max_length=20)

                    async def on_submit(self2, mit: discord.Interaction):
                        try:
                            listing_id = int(self2.listing_id.value.strip())
                        except Exception:
                            await mit.response.send_message("Listing ID must be a number.", ephemeral=True)
                            return

                        await mit.response.defer(ephemeral=True)
                        ok, msg = await _cancel_listing(mit, listing_id)
                        await mit.followup.send(msg, ephemeral=True)

                await it.response.send_modal(CancelModal())

        embed = discord.Embed(
            title="Community Market",
            description=(
                "Buy and sell cats, packs, items, cosmetics, and more with kibble.\n"
                "Use the buttons below to browse listings, create sales, and manage your listings."
            ),
            color=discord.Color.from_rgb(110, 89, 60),
        )
        embed.set_footer(text="Tip: Browse includes one-click Buy buttons per listing.")
        await interaction.response.send_message(embed=embed, view=MarketView(interaction.user.id), ephemeral=True)

    try:
        existing = bot.tree.get_command("market")
        if existing is not None:
            bot.tree.remove_command("market")
    except Exception:
        pass

    bot.tree.add_command(market)
    setattr(bot, "_community_market_registered", True)
