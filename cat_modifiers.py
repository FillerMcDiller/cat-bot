# Cat Modifiers System
# Modifiers are special properties that can be applied to cats to boost their stats and value
# This system is designed to be extensible - new modifiers can be easily added

import random
import json
import os

# Import type_dict to calculate spawn rates dynamically
# NOTE: This should be updated when imported from main.py
type_dict = None

# =============================================================================
# MODIFIER DEFINITIONS
# =============================================================================

CAT_MODIFIERS = {
    "enchanted": {
        "name": "✨ Enchanted",
        "description": "A magical cat with doubled stats and value",
        "rarity_divisor": 3.0,
        "stat_multiplier": 2.0,  
        "kibble_multiplier": 3.0, 
        "adventure_multiplier": 3.0,  
        "steal_resistance": 0.8,  
        "pack_rarity": ["Platinum", "Diamond"],  
        "emoji": "✨",
        "display_name": "Enchanted",
    },
    "snowy": {
        "name": "❄️ Snowy",
        "description": "A festive cat covered in snow (December only)",
        "rarity_divisor": 2.0,  
        "stat_multiplier": 1.1,  
        "kibble_multiplier": 1.5,  
        "adventure_multiplier": 1.3,  
        "steal_resistance": 0.3,  
        "emoji": "❄️",
        "display_name": "Snowy",
    },
    "pumpkin": {
        "name": "🎃 Pumpkin",
        "description": "A festive cat with a pumpkin theme (October only)",
        "rarity_divisor": 2.0,
        "stat_multiplier": 1.1,
        "kibble_multiplier": 1.5,
        "adventure_multiplier": 1.3,
        "steal_resistance": 0.3,
        "pack_rarity": [],
        "emoji": "🎃",
        "display_name": "Pumpkin",
    },
}

# =============================================================================
# MODIFIER UTILITY FUNCTIONS
# =============================================================================

def has_modifier(cat: dict, modifier_name: str) -> bool:
    """Check if a cat has a specific modifier"""
    modifiers = cat.get("modifiers", [])
    return modifier_name in modifiers


def add_modifier(cat: dict, modifier_name: str) -> bool:
    """Add a modifier to a cat. Returns True if added, False if already has it"""
    if modifier_name not in CAT_MODIFIERS:
        return False
    
    modifiers = cat.get("modifiers", [])
    if modifier_name in modifiers:
        return False
    
    modifiers.append(modifier_name)
    cat["modifiers"] = modifiers
    return True


def get_cat_display_name(cat: dict) -> str:
    """Get the display name for a cat including modifiers"""
    modifiers = cat.get("modifiers", [])
    name = cat.get("name", "Unknown")
    
    if modifiers:
        modifier_emojis = " ".join([CAT_MODIFIERS[m]["emoji"] for m in modifiers if m in CAT_MODIFIERS])
        return f"{modifier_emojis} {name}"
    
    return name


def get_image_path(cat: dict, base_path: str = "images/spawn") -> str:
    """Get the correct image path for a cat, accounting for modifiers"""
    cat_type = cat.get("type", "Fine").lower()
    modifiers = cat.get("modifiers", [])

    # Use the first available variant so a new modifier can be enabled before
    # its complete set of image assets has been deployed.
    for modifier_name in ("pumpkin", "snowy", "enchanted"):
        if modifier_name in modifiers:
            variant_path = os.path.join(base_path, f"{cat_type}_cat_{modifier_name}.png")
            if os.path.exists(variant_path):
                return variant_path

    return os.path.join(base_path, f"{cat_type}_cat.png")


def apply_stat_multipliers(cat: dict) -> dict:
    """Apply all active modifier multipliers to cat stats. Returns modified stats dict"""
    modifiers = cat.get("modifiers", [])
    
    hp = cat.get("hp", 1)
    dmg = cat.get("dmg", 1)
    
    # Apply each modifier's stat multiplier
    for modifier_name in modifiers:
        if modifier_name in CAT_MODIFIERS:
            multiplier = CAT_MODIFIERS[modifier_name].get("stat_multiplier", 1.0)
            hp = int(hp * multiplier)
            dmg = int(dmg * multiplier)
    
    return {"hp": hp, "dmg": dmg}


def get_kibble_multiplier(cat: dict) -> float:
    """Get the combined kibble multiplier for a cat from all modifiers"""
    modifiers = cat.get("modifiers", [])
    multiplier = 1.0
    
    for modifier_name in modifiers:
        if modifier_name in CAT_MODIFIERS:
            mult = CAT_MODIFIERS[modifier_name].get("kibble_multiplier", 1.0)
            multiplier *= mult
    
    return multiplier


def get_adventure_multiplier(cat: dict) -> float:
    """Get the combined adventure reward multiplier for a cat from all modifiers"""
    modifiers = cat.get("modifiers", [])
    multiplier = 1.0
    
    for modifier_name in modifiers:
        if modifier_name in CAT_MODIFIERS:
            mult = CAT_MODIFIERS[modifier_name].get("adventure_multiplier", 1.0)
            multiplier *= mult
    
    return multiplier


def should_apply_random_modifier(cat_type: str = None, type_dict_ref: dict = None) -> tuple[bool, str]:
    """Randomly determine if a modifier should be applied to a new cat.
    
    Spawn chance is calculated as: cat_rarity / (rarity_divisor * 1000)
    For example, Fine cat (1000) -> enchanted chance = 1000 / (3.0 * 1000) = 0.333... = 1 in 3 Fine cats
    
    Args:
        cat_type: The type of cat being spawned (e.g., "Fine", "Legendary")
        type_dict_ref: Reference to type_dict from main.py with rarity values
    
    Returns: (should_apply: bool, modifier_name: str)
    """
    if not cat_type or not type_dict_ref:
        return False, None
    
    cat_rarity = type_dict_ref.get(cat_type, 1.0)
    
    for modifier_name, modifier_data in CAT_MODIFIERS.items():
        # Calculate spawn chance based on cat rarity
        rarity_divisor = modifier_data.get("rarity_divisor", 3.0)
        spawn_chance = cat_rarity / (rarity_divisor * 1000.0)
        
        if random.random() < spawn_chance:
            return True, modifier_name
    
    return False, None


def get_steal_resistance(cat: dict) -> float:
    """Get the steal resistance for a cat (0.0 = normal steal chance, 1.0 = unstealable)"""
    modifiers = cat.get("modifiers", [])
    resistance = 0.0
    
    for modifier_name in modifiers:
        if modifier_name in CAT_MODIFIERS:
            resist = CAT_MODIFIERS[modifier_name].get("steal_resistance", 0.0)
            resistance += resist
    
    return min(resistance, 1.0)  # Cap at 100%


def can_open_from_pack(cat_type: str, modifier_name: str, pack_type: str) -> bool:
    """Check if a modifier can be found in a specific pack type"""
    if modifier_name not in CAT_MODIFIERS:
        return False
    
    allowed_packs = CAT_MODIFIERS[modifier_name].get("pack_rarity", [])
    return pack_type in allowed_packs


def get_modifier_info(modifier_name: str) -> dict:
    """Get detailed info about a modifier"""
    if modifier_name not in CAT_MODIFIERS:
        return None
    
    return CAT_MODIFIERS[modifier_name].copy()


def format_modifier_stats(modifier_name: str) -> str:
    """Format modifier stats for display"""
    if modifier_name not in CAT_MODIFIERS:
        return ""
    
    mod = CAT_MODIFIERS[modifier_name]
    lines = [
        f"**{mod['name']}**",
        f"{mod['description']}",
        "",
        "**Bonuses:**",
        f"• Stats: {(mod['stat_multiplier'] - 1) * 100:.0f}% boost",
        f"• Kibble: {(mod['kibble_multiplier'] - 1) * 100:.0f}% boost",
        f"• Adventures: {(mod['adventure_multiplier'] - 1) * 100:.0f}% boost",
        f"• Steal Resistance: {mod['steal_resistance'] * 100:.0f}%",
    ]
    
    if mod['pack_rarity']:
        lines.append(f"• Can appear in: {', '.join(mod['pack_rarity'])} packs")
    
    return "\n".join(lines)



