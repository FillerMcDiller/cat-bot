"""
DRAFT: Bot-side vote receiver
This is a draft implementation - DO NOT merge to main without testing!

This code should be integrated into main.py to receive vote notifications
from the vote_webhook_draft.py server and reward users.

Add this to your main.py setup_hook or as a background task.
"""

import asyncio
import logging
from aiohttp import web
import json

logger = logging.getLogger("bot.vote_receiver")


async def handle_vote_reward(user_id: int, is_weekend: bool):
    """
    Process vote reward for a user
    
    Rewards:
    - 300 BP XP (600 on weekends)
    - 1 Wooden pack
    """
    try:
        # Import here to avoid circular imports when this is integrated
        from database import User, Profile
        from main import pack_data, add_cat_instances, cattypes, type_dict
        import random
        
        # Get user data
        user = await User.get_or_create(user_id=user_id)
        
        # Calculate BP XP reward
        bp_xp_reward = 600 if is_weekend else 300
        
        # Add BP XP
        current_xp = user.battlepass_xp or 0
        user.battlepass_xp = current_xp + bp_xp_reward
        await user.save()
        
        logger.info(f"Rewarded user {user_id} with {bp_xp_reward} BP XP (weekend: {is_weekend})")
        
        # Give wooden pack (index 0 in pack_data)
        # Pack opening logic from main.py
        wooden_pack = pack_data[0]  # Wooden pack
        pack_value = wooden_pack["totalvalue"]
        
        # Simulate pack opening
        cats_obtained = {}
        value = 0
        
        while value < pack_value:
            # Random cat selection weighted by rarity
            weights = [type_dict[t] for t in cattypes]
            total_weight = sum(weights)
            normalized_weights = [w / total_weight for w in weights]
            
            cat = random.choices(cattypes, weights=normalized_weights, k=1)[0]
            cat_value = type_dict[cat]
            
            if value + cat_value > pack_value:
                # Try to find a cat that fits
                fitting_cats = [c for c in cattypes if type_dict[c] <= (pack_value - value)]
                if fitting_cats:
                    weights_fitting = [type_dict[t] for t in fitting_cats]
                    total_weight_fitting = sum(weights_fitting)
                    normalized_weights_fitting = [w / total_weight_fitting for w in weights_fitting]
                    cat = random.choices(fitting_cats, weights=normalized_weights_fitting, k=1)[0]
                    cat_value = type_dict[cat]
                else:
                    break
            
            value += cat_value
            cats_obtained[cat] = cats_obtained.get(cat, 0) + 1
        
        logger.info(f"Pack contents for user {user_id}: {cats_obtained}")
        
        # We need to award these cats to the user across all their servers
        # Since cats are per-guild, we'll store this as a "pending reward"
        # that will be claimed when they use a command in any server
        
        # Store pending reward in user data (you may need to add this field to User model)
        pending = user.pending_vote_rewards or "[]"
        try:
            pending_list = json.loads(pending)
        except:
            pending_list = []
        
        pending_list.append({
            "timestamp": int(asyncio.get_event_loop().time()),
            "bp_xp": bp_xp_reward,
            "pack": "Wooden",
            "cats": cats_obtained,
            "is_weekend": is_weekend
        })
        
        user.pending_vote_rewards = json.dumps(pending_list)
        await user.save()
        
        logger.info(f"✅ Vote reward queued for user {user_id}")
        
        # Try to DM the user
        try:
            from main import bot
            discord_user = await bot.fetch_user(user_id)
            
            if discord_user:
                cats_text = ", ".join([f"{count}x {cat}" for cat, count in cats_obtained.items()])
                weekend_text = " (Weekend Bonus! 🎉)" if is_weekend else ""
                
                dm_message = (
                    f"🎉 **Thank you for voting!**{weekend_text}\n\n"
                    f"**Rewards:**\n"
                    f"✨ {bp_xp_reward} Battlepass XP\n"
                    f"📦 1 Wooden Pack containing: {cats_text}\n\n"
                    f"Your cats will be added to your inventory in all servers!"
                )
                
                await discord_user.send(dm_message)
                logger.info(f"Sent reward DM to user {user_id}")
        except Exception as dm_error:
            logger.warning(f"Could not DM user {user_id}: {dm_error}")
        
        return True
        
    except Exception as e:
        logger.exception(f"Error processing vote reward for user {user_id}: {e}")
        return False


async def internal_vote_handler(request):
    """Handle incoming vote notifications from vote_webhook_draft.py"""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        is_weekend = data.get("is_weekend", False)
        
        if not user_id:
            return web.json_response({"error": "Missing user_id"}, status=400)
        
        logger.info(f"Received vote notification for user {user_id}")
        
        # Process reward asynchronously
        asyncio.create_task(handle_vote_reward(user_id, is_weekend))
        
        return web.json_response({"status": "success", "user_id": user_id})
        
    except Exception as e:
        logger.error(f"Error handling vote: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def start_internal_server(port: int = 3002):
    """
    Start internal HTTP server to receive vote notifications
    
    This should be called in bot's setup_hook:
    bot.loop.create_task(start_internal_server(3002))
    """
    app = web.Application()
    app.router.add_post('/vote', internal_vote_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', port)
    await site.start()
    
    logger.info(f"Internal vote receiver started on localhost:{port}")


# ============================================================================
# INTEGRATION INSTRUCTIONS:
# ============================================================================
# 
# 1. Add to User model in database.py:
#    pending_vote_rewards = Column(Text, default="[]")
# 
# 2. Add to main.py setup_hook (already exists in your code):
#    - The start_internal_server() call is already there!
#    - Just copy the handle_vote_reward and internal_vote_handler functions
# 
# 3. Add command to claim rewards in any server:
#    @bot.tree.command(description="Claim your pending vote rewards")
#    async def claimvote(interaction: discord.Interaction):
#        user = await User.get_or_create(user_id=interaction.user.id)
#        pending = user.pending_vote_rewards or "[]"
#        pending_list = json.loads(pending)
#        
#        if not pending_list:
#            await interaction.response.send_message("No pending vote rewards!", ephemeral=True)
#            return
#        
#        # Process all pending rewards
#        for reward in pending_list:
#            cats = reward.get("cats", {})
#            profile = await Profile.get_or_create(
#                guild_id=interaction.guild.id,
#                user_id=interaction.user.id
#            )
#            
#            for cat_type, amount in cats.items():
#                await add_cat_instances(profile, cat_type, amount)
#        
#        # Clear pending rewards
#        user.pending_vote_rewards = "[]"
#        await user.save()
#        
#        total_cats = sum(r.get("cats", {}).values() for r in pending_list)
#        await interaction.response.send_message(
#            f"✅ Claimed {len(pending_list)} vote reward(s)! Added {total_cats} cats to your inventory!",
#            ephemeral=True
#        )
