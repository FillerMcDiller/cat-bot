"""
DRAFT: Bot-side vote receiver
This is a draft implementation - DO NOT merge to main without testing!

This code integrates with the EXISTING reward_vote() function in main.py!
No need for pending rewards - everything happens instantly per-server.

Integration Steps:
1. Add internal_vote_handler() function to main.py
2. The start_internal_server() call is ALREADY in setup_hook!
3. Just make sure it calls reward_vote() with the user_id

The existing reward_vote() function already handles:
- Per-server battlepass XP (300, or 600 on Fri/Sat/Sun)
- Wooden pack rewards (via streak system)
- All streak bonuses
- Auto-claiming (no /claimvote needed!)
"""

import asyncio
import logging
from aiohttp import web

logger = logging.getLogger("bot.vote_receiver")


# ============================================================================
# NEW SIMPLIFIED APPROACH - Uses existing reward_vote() from main.py
# ============================================================================

async def internal_vote_handler(request):
    """
    Handle incoming vote notifications from vote_webhook_draft.py
    
    This simply calls the EXISTING reward_vote() function which:
    - Awards 300 BP XP per server (600 on Fri/Sat/Sun)
    - Gives wooden pack
    - Handles all streak logic
    - Instantly rewards across all servers!
    """
    try:
        data = await request.json()
        user_id = data.get("user_id")
        
        if not user_id:
            return web.json_response({"error": "Missing user_id"}, status=400)
        
        logger.info(f"Received vote notification for user {user_id}, calling reward_vote()")
        
        # Import and call the existing reward_vote function
        from main import reward_vote
        
        # Process reward asynchronously using existing system
        asyncio.create_task(reward_vote(user_id))
        
        return web.json_response({"status": "success", "user_id": user_id})
        
    except Exception as e:
        logger.error(f"Error handling vote: {e}")
        return web.json_response({"error": str(e)}, status=500)


# ============================================================================
# OLD COMPLEX APPROACH - NOT NEEDED ANYMORE!
# Keeping this for reference, but the above simple handler is all you need.
# ============================================================================

async def handle_vote_reward_OLD_COMPLEX_VERSION(user_id: int, is_weekend: bool):
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





async def start_internal_server(port: int = 3002):
    """
    Start internal HTTP server to receive vote notifications
    
    NOTE: This function is ALREADY in main.py!
    If you see it there, you don't need to copy this.
    Just add the internal_vote_handler function above.
    """
    app = web.Application()
    app.router.add_post('/vote', internal_vote_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', port)
    await site.start()
    
    logger.info(f"Internal vote receiver started on localhost:{port}")


# ============================================================================
# SIMPLIFIED INTEGRATION INSTRUCTIONS:
# ============================================================================
# 
# GOOD NEWS: The bot already has reward_vote() which does everything!
# 
# 1. Find the start_internal_server() function in main.py (around line 16300)
# 
# 2. Find the recieve_vote() handler function
# 
# 3. Replace it with this simple version:
#
#    async def recieve_vote(request):
#        """Handle Top.gg vote webhooks (internal receiver)"""
#        try:
#            request_json = await request.json()
#            user_id = int(request_json.get("user_id", 0))
#            
#            if not user_id:
#                return web.json_response({"error": "Missing user_id"}, status=400)
#            
#            # Call existing reward_vote function
#            asyncio.create_task(reward_vote(user_id))
#            
#            return web.json_response({"status": "success"})
#        except Exception as e:
#            logger.error(f"Error in recieve_vote: {e}")
#            return web.json_response({"error": str(e)}, status=500)
#
# That's it! No database changes, no new commands, no pending rewards!
