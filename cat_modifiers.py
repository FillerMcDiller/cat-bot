# Cat Modifiers System
# Modifiers are special properties that can be applied to cats to boost their stats and value
# This system is designed to be extensible - new modifiers can be easily added

import random
import json

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
        "rarity_divisor": 3.0,  # Spawn rate is 1/3 of the cat's base rarity
        "stat_multiplier": 2.0,  # Double all stats (hp, dmg)
        "kibble_multiplier": 3.0,  # 3x kibble value
        "adventure_multiplier": 3.0,  # 3x adventure rewards
        "steal_resistance": 0.8,  # 80% harder to steal (20% steal chance instead of normal)
        "pack_rarity": ["Platinum", "Diamond"],  # Can spawn from these pack types only
        "emoji": "✨",
        "display_name": "Enchanted",
    },
    "snowy": {
        "name": "❄️ Snowy",
        "description": "A festive cat covered in snow (December only)",
        "rarity_divisor": 2.0,  # Spawn rate is 1/2 of the cat's base rarity (higher chance in December)
        "stat_multiplier": 1.1,  # 10% stat boost
        "kibble_multiplier": 1.5,  # 50% more kibble
        "adventure_multiplier": 1.3,  # 30% more adventure rewards
        "steal_resistance": 0.3,  # 30% harder to steal
        "emoji": "❄️",
        "display_name": "Snowy",
    }
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
    
    # Check for snowy modifier first (December exclusive)
    if "snowy" in modifiers:
        return f"{base_path}/{cat_type}_snowy.png"
    
    # Check for enchanted modifier
    if "enchanted" in modifiers:
        return f"{base_path}/{cat_type}_cat_enchanted.png"
    
    return f"{base_path}/{cat_type}_cat.png"


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


# =============================================================================
# INTEGRATION POINTS
# =============================================================================

"""
INTEGRATION GUIDE:

1. SPAWNING CATS (add_cat_instances and create_instance_if_missing):
   
   At the TOP of main.py, import and initialize type_dict:
   ```python
   from cat_modifiers import should_apply_random_modifier, add_modifier
   ```
   
   Then in add_cat_instances() and repair_cat_instances(), after creating instance dict:
   ```python
   # Check for random modifiers (enchanted, etc)
   # Enchanted spawn rate: cat_rarity / (3.0 * 1000)
   # Example: Fine cat (1000) -> 1000/(3*1000) = 0.333 = 1 in 3 Fine cats
   should_apply, modifier_name = should_apply_random_modifier(cat_type, type_dict)
   if should_apply:
       add_modifier(instance, modifier_name)
   ```

2. DISPLAYING CAT STATS (in battle, team, etc):
   ```python
   # When showing cat stats, apply multipliers
   base_stats = get_cat_display_name(cat)  # For display name
   stats = apply_stat_multipliers(cat)     # For battle
   img_path = get_image_path(cat)          # For image
   ```

3. ADVENTURE REWARDS (kibble calculation):
   ```python
   # When calculating adventure rewards
   kibble_base = 100  # or whatever base is
   multiplier = get_kibble_multiplier(cat)
   kibble_amount = int(kibble_base * multiplier)
   ```

4. ADVENTURE EXPLORATION (adventure rewards):
   ```python
   # When calculating adventure rewards
   adventure_mult = get_adventure_multiplier(cat)
   rewards = apply_adventure_multiplier(base_rewards, adventure_mult)
   ```

5. PACK OPENING (when generating cat from pack):
   ```python
   # After determining cat_type from pack
   # Check if pack can spawn modifiers (Platinum/Diamond only)
   if pack_type in ["Platinum", "Diamond"]:
       should_apply, modifier_name = should_apply_random_modifier(cat_type, type_dict)
       if should_apply and can_open_from_pack(cat_type, modifier_name, pack_type):
           add_modifier(instance, modifier_name)
   ```

6. STEALING CATS (preventcatch or steal logic):
   ```python
   # When player tries to steal a cat
   resistance = get_steal_resistance(cat)
   steal_chance = 0.5  # Base 50% chance
   steal_chance *= (1 - resistance)  # Apply resistance
   if random.random() < steal_chance:
       # Successfully stole
   ```

7. DISPLAYING CAT INFO (profile, inventory, etc):
   ```python
   # Show full modifier info
   modifier_info = get_modifier_info(modifier_name)
   formatted = format_modifier_stats(modifier_name)
   ```

8. BREEDING (if implemented):
   ```python
   # Modifiers could be inherited from parents
   # Or small chance to create new modifier
   ```
"""

