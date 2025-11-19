# Vote Webhook Setup Guide (DRAFT)

⚠️ **This is a DRAFT implementation - test thoroughly before deploying!**

## Overview

This system rewards users for voting on Top.gg with:
- **300 Battlepass XP** (600 on weekends)
- **1 Wooden Pack** (automatically opened)

## Architecture

```
Top.gg → Cloudflare Tunnel → vote_webhook_draft.py (port 3001)
                                        ↓
                              bot (port 3002) → Discord Bot
```

## Setup Steps

### 1. Install Dependencies

```bash
pip install fastapi uvicorn
```

### 2. Configure Environment Variables

Add to your `.env` file:

```env
# Top.gg webhook secret (get from https://top.gg/bot/YOUR_BOT_ID/webhooks)
TOPGG_WEBHOOK_SECRET=your_secret_here

# Webhook server port (for Cloudflare tunnel)
VOTE_WEBHOOK_PORT=3001

# Bot internal receiver port
BOT_INTERNAL_PORT=3002
```

### 3. Database Migration

Add to `database.py` User model:

```python
pending_vote_rewards = Column(Text, default="[]")
```

Then run migration:

```sql
ALTER TABLE users ADD COLUMN pending_vote_rewards TEXT DEFAULT '[]';
```

### 4. Top.gg Configuration

1. Go to https://top.gg/bot/YOUR_BOT_ID/webhooks
2. Set webhook URL: `https://your-domain.com/webhook`
3. Copy the webhook secret to your `.env` file
4. Set authorization header type to "Custom"

### 5. Cloudflare Tunnel Configuration

Your tunnel should route:
- `https://your-domain.com/webhook` → `localhost:3001/webhook`

### 6. Integration with Bot

#### Option A: Copy functions to main.py

Copy these functions from `bot_vote_receiver_draft.py` to `main.py`:
- `handle_vote_reward()`
- `internal_vote_handler()`

The `start_internal_server()` call is already in your setup_hook!

#### Option B: Import as module

```python
# In main.py
from bot_vote_receiver_draft import handle_vote_reward, internal_vote_handler, start_internal_server
```

### 7. Add Claim Command

Add this command to `main.py`:

```python
@bot.tree.command(description="Claim your pending vote rewards")
async def claimvote(interaction: discord.Interaction):
    """Claim vote rewards from voting on Top.gg"""
    await interaction.response.defer()
    
    user = await User.get_or_create(user_id=interaction.user.id)
    pending = user.pending_vote_rewards or "[]"
    
    try:
        pending_list = json.loads(pending)
    except:
        pending_list = []
    
    if not pending_list:
        await interaction.followup.send("❌ No pending vote rewards!", ephemeral=True)
        return
    
    # Process all pending rewards
    total_cats = {}
    total_bp_xp = 0
    
    for reward in pending_list:
        cats = reward.get("cats", {})
        bp_xp = reward.get("bp_xp", 0)
        total_bp_xp += bp_xp
        
        profile = await Profile.get_or_create(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id
        )
        
        for cat_type, amount in cats.items():
            await add_cat_instances(profile, cat_type, amount)
            total_cats[cat_type] = total_cats.get(cat_type, 0) + amount
    
    # Clear pending rewards
    user.pending_vote_rewards = "[]"
    await user.save()
    
    # Format response
    cats_text = ", ".join([f"{amount}x {cat}" for cat, amount in total_cats.items()])
    
    embed = discord.Embed(
        title="🎉 Vote Rewards Claimed!",
        description=f"Thank you for supporting KITTAYYYYYYY!",
        color=Colors.brown
    )
    embed.add_field(name="Battlepass XP", value=f"✨ {total_bp_xp} XP", inline=False)
    embed.add_field(name="Cats Added", value=f"🐱 {cats_text}", inline=False)
    embed.set_footer(text="Vote again at https://top.gg/bot/YOUR_BOT_ID/vote")
    
    await interaction.followup.send(embed=embed)
```

## Running

### Development/Testing

Terminal 1 (Bot):
```bash
python main.py
```

Terminal 2 (Webhook Server):
```bash
python vote_webhook_draft.py
```

### Production

Use a process manager like `supervisord` or `systemd` to run both processes.

Example `supervisord` config:

```ini
[program:catbot]
command=python main.py
directory=/path/to/cat-bot
autostart=true
autorestart=true

[program:catbot_webhook]
command=python vote_webhook_draft.py
directory=/path/to/cat-bot
autostart=true
autorestart=true
```

## Testing

### Test webhook locally:

```bash
curl -X POST http://localhost:3001/webhook \
  -H "Content-Type: application/json" \
  -H "Authorization: YOUR_SECRET_HERE" \
  -d '{"bot":"123","user":"YOUR_DISCORD_ID","type":"upvote","isWeekend":false}'
```

### Test bot receiver:

```bash
curl -X POST http://localhost:3002/vote \
  -H "Content-Type: application/json" \
  -d '{"user_id":YOUR_DISCORD_ID,"is_weekend":false}'
```

## Monitoring

Check logs:
- Webhook server logs vote receipts
- Bot logs reward processing
- Users should receive DMs when rewards are ready

Check health endpoints:
- `http://localhost:3001/health` - Webhook server
- `http://localhost:3001/` - Status page

## Troubleshooting

### Votes not being received:
1. Check Cloudflare tunnel is running and routing correctly
2. Verify webhook URL on Top.gg matches your domain
3. Check `vote_webhook_draft.py` logs for errors
4. Verify TOPGG_WEBHOOK_SECRET is correct

### Rewards not being given:
1. Check bot internal receiver is running (port 3002)
2. Check main.py logs for errors in `handle_vote_reward`
3. Verify database has `pending_vote_rewards` column
4. Test with curl commands above

### Users not getting cats:
1. User must run `/claimvote` in a server
2. Check user.pending_vote_rewards is not empty
3. Verify add_cat_instances() function is working

## Security Notes

⚠️ **Important:**
- Keep TOPGG_WEBHOOK_SECRET private
- The internal receiver (port 3002) should ONLY listen on localhost
- Never expose port 3002 to the internet
- Use HTTPS for the public webhook endpoint (handled by Cloudflare)

## Future Improvements

- [ ] Add vote streak bonuses
- [ ] Show vote history in `/profile`
- [ ] Auto-claim rewards when user uses any command
- [ ] Add vote reminders (12hr after last vote)
- [ ] Better pack opening UI in DMs
