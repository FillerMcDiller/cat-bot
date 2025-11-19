# Vote Webhook Setup Guide (DRAFT)

⚠️ **This is a DRAFT implementation - test thoroughly before deploying!**

## Overview

This system uses the EXISTING `reward_vote()` function to **instantly** reward users across all servers when they vote on Top.gg!

**Rewards (per server, instantly applied):**
- **300 Battlepass XP** (600 on Fri/Sat/Sun)
- **1 Wooden Pack** (from streak system - every 7 votes)
- **Streak Bonuses** at 25/50/75/100 votes (better packs!)
- **No claiming needed** - rewards appear immediately when they open `/battlepass`

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

### 3. Update Vote Handler (SIMPLE!)

Find the `recieve_vote()` function in `main.py` (around line 16299) and update it to:

```python
async def recieve_vote(request):
    """Handle Top.gg vote webhooks (internal receiver)"""
    try:
        request_json = await request.json()
        user_id = int(request_json.get("user_id", 0))
        
        if not user_id:
            return web.json_response({"error": "Missing user_id"}, status=400)
        
        # Call existing reward_vote function (does everything!)
        asyncio.create_task(reward_vote(user_id))
        
        return web.json_response({"status": "success"})
    except Exception as e:
        logger.error(f"Error in recieve_vote: {e}")
        return web.json_response({"error": str(e)}, status=500)
```

**That's all you need!** The existing `reward_vote()` function handles:
- Per-server XP (300 or 600 on Fri/Sat/Sun)
- Wooden pack from streak system
- All streak bonuses
- Instant application (no claiming needed)

### 4. Top.gg Configuration

1. Go to https://top.gg/bot/YOUR_BOT_ID/webhooks
2. Set webhook URL: `https://your-domain.com/webhook`
3. Copy the webhook secret to your `.env` file
4. Set authorization header type to "Custom"

### 5. Cloudflare Tunnel Configuration

Your tunnel should route:
- `https://your-domain.com/webhook` → `localhost:3001/webhook`

### 6. Integration with Bot

**You're already 99% done!** The bot has everything needed:
- ✅ `reward_vote()` function exists (line 17000+)
- ✅ `start_internal_server()` is in setup_hook
- ✅ Per-server instant rewards work
- ✅ No database changes needed
- ✅ No new commands needed

Just update the `recieve_vote()` handler as shown in step 3!

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
  -d '{"user_id":YOUR_DISCORD_ID}'
```

Then open `/battlepass` in any server to see your rewards!

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
2. Check main.py logs for errors in `reward_vote()`
3. Verify vote_cooldown is being set to 0 properly
4. Test with curl commands above

### Users not seeing rewards:
1. User should open `/battlepass` to see rewards
2. XP is added instantly to all servers
3. Check logs for "Rewarding vote for user" message
4. Verify `reward_vote()` function is being called

## Security Notes

⚠️ **Important:**
- Keep TOPGG_WEBHOOK_SECRET private
- The internal receiver (port 3002) should ONLY listen on localhost
- Never expose port 3002 to the internet
- Use HTTPS for the public webhook endpoint (handled by Cloudflare)

## What This System Does

✅ **Instant Rewards** - No claiming needed, rewards apply instantly  
✅ **Per-Server** - Get XP and packs in every server  
✅ **Weekend Bonus** - Automatic 2x XP on Fri/Sat/Sun  
✅ **Streak System** - Wooden pack every 7 votes, better packs at 25/50/75/100  
✅ **DM Notification** - Users get a DM when they vote  
✅ **Works with existing system** - Uses the vote quest that already exists!

## Future Improvements

- [ ] Add vote count to `/profile`
- [ ] Show current streak in vote DM
- [ ] Add vote reminders (12hr after last vote)
- [ ] Better streak visualization
