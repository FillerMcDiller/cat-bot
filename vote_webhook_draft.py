"""
DRAFT: Top.gg Vote Webhook System
This is a draft implementation - DO NOT merge to main without testing!

This system receives Top.gg vote webhooks via Cloudflare tunnel on port 3001
and instantly rewards users across all servers with:
- 300 battlepass XP (600 on Fri/Sat/Sun)
- 1 Wooden pack (opens automatically)
- Streak bonuses (every 7th vote, special rewards at 25/50/75/100)

Uses the existing reward_vote() system from main.py for instant per-server rewards!

Requirements:
    pip install fastapi uvicorn

Setup:
1. Configure your Top.gg webhook URL to: https://your-domain.com/webhook
2. Set TOPGG_WEBHOOK_SECRET in your .env file
3. Run this alongside your bot: python vote_webhook_draft.py
"""

import os
import asyncio
import hmac
import hashlib
import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, Header
from dotenv import load_dotenv
import uvicorn

# Load environment variables
load_dotenv()

# Configuration
TOPGG_WEBHOOK_SECRET = os.getenv("TOPGG_WEBHOOK_SECRET", "")
WEBHOOK_PORT = int(os.getenv("VOTE_WEBHOOK_PORT", "3001"))
BOT_INTERNAL_PORT = int(os.getenv("BOT_INTERNAL_PORT", "3002"))

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s %(name)s: %(message)s'
)
logger = logging.getLogger("vote_webhook")

app = FastAPI(title="KITTAYYYYYYY Vote Webhook")


def verify_topgg_signature(body: bytes, authorization: str) -> bool:
    """Verify Top.gg webhook signature"""
    if not TOPGG_WEBHOOK_SECRET:
        logger.warning("TOPGG_WEBHOOK_SECRET not set - skipping verification (INSECURE!)")
        return True
    
    try:
        # Top.gg uses HMAC-SHA256 for webhook verification
        expected_signature = hmac.new(
            TOPGG_WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(authorization, expected_signature)
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False


def is_weekend() -> bool:
    """Check if today is Saturday (5) or Sunday (6)"""
    return datetime.now().weekday() in [5, 6]


async def notify_bot(user_id: int):
    """
    Send vote notification to the bot's internal webhook receiver
    
    The bot's reward_vote() function handles:
    - Weekend detection (Fri/Sat/Sun = 2x XP)
    - Streak bonuses
    - Per-server rewards instantly
    """
    import aiohttp
    
    try:
        vote_data = {
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        bot_url = f"http://127.0.0.1:{BOT_INTERNAL_PORT}/vote"
        logger.info(f"[NOTIFY_BOT] Attempting to forward vote to bot at {bot_url}")
        logger.info(f"[NOTIFY_BOT] Payload: {vote_data}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                bot_url,
                json=vote_data,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                resp_text = await resp.text()
                logger.info(f"[NOTIFY_BOT] Bot response status: {resp.status}, body: {resp_text}")
                
                if resp.status == 200:
                    logger.info(f"✅ Successfully notified bot about vote from user {user_id}")
                    return True
                else:
                    logger.error(f"❌ Bot returned non-200 status: {resp.status}")
                    return False
    except aiohttp.ClientConnectorError as e:
        logger.error(f"❌ CONNECTION FAILED: Cannot connect to bot at localhost:{BOT_INTERNAL_PORT} - Is the bot running? Error: {e}")
        return False
    except asyncio.TimeoutError:
        logger.error(f"❌ TIMEOUT: Bot at localhost:{BOT_INTERNAL_PORT} did not respond within 5 seconds")
        return False
    except Exception as e:
        logger.error(f"❌ Failed to notify bot: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "KITTAYYYYYYY Vote Webhook",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/webhook")
async def topgg_webhook(
    request: Request,
    authorization: Optional[str] = Header(None)
):
    """
    Handle Top.gg vote webhooks
    
    Expected payload from Top.gg:
    {
        "bot": "bot_id",
        "user": "user_id",
        "type": "upvote",
        "isWeekend": false,
        "query": ""
    }
    """
    try:
        # Get raw body for signature verification
        body = await request.body()
        
        # Verify signature if secret is configured
        # TEMPORARY: Disable signature verification for testing
        # TODO: Re-enable this after getting correct secret from Top.gg
        if False and TOPGG_WEBHOOK_SECRET:
            if not authorization:
                logger.warning("Missing Authorization header")
                raise HTTPException(status_code=401, detail="Missing Authorization header")
            
            if not verify_topgg_signature(body, authorization):
                logger.warning("Invalid signature from Top.gg webhook")
                raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse JSON payload
        payload = await request.json()
        
        # Extract data
        user_id = int(payload.get("user", 0))
        vote_type = payload.get("type", "")
        
        if not user_id:
            logger.error(f"Invalid user_id in payload: {payload}")
            raise HTTPException(status_code=400, detail="Invalid user_id")
        
        if vote_type != "upvote":
            logger.info(f"Received non-upvote type: {vote_type}")
            return {"status": "ignored", "reason": "not an upvote"}
        
        logger.info(f"Received vote from user {user_id}")
        
        # Forward to bot (bot handles weekend detection, streaks, etc.)
        success = await notify_bot(user_id)
        
        if success:
            return {
                "status": "success",
                "user_id": user_id,
                "message": "Vote recorded and rewards applied instantly to all servers!"
            }
        else:
            # Still return 200 to Top.gg so they don't retry
            logger.error(f"Bot notification failed but returning 200 to Top.gg")
            return {
                "status": "accepted",
                "message": "Vote received but bot notification pending"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/health")
async def health_check():
    """Health check for monitoring"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "secret_configured": bool(TOPGG_WEBHOOK_SECRET)
    }


if __name__ == "__main__":
    logger.info("="*60)
    logger.info(f"Starting vote webhook server on port {WEBHOOK_PORT}")
    logger.info(f"Bot internal port: {BOT_INTERNAL_PORT}")
    logger.info(f"Bot internal URL: http://127.0.0.1:{BOT_INTERNAL_PORT}/vote")
    logger.info(f"Webhook secret configured: {bool(TOPGG_WEBHOOK_SECRET)}")
    logger.info("="*60)
    
    if not TOPGG_WEBHOOK_SECRET:
        logger.warning("⚠️  TOPGG_WEBHOOK_SECRET not set - webhook verification disabled!")
        logger.warning("⚠️  Set this in your .env file for security!")
    
    logger.info("⚠️  MAKE SURE THE BOT IS RUNNING FIRST! The webhook needs to forward to the bot's internal server.")
    
    uvicorn.run(
        app,
        host="0.0.0.0",  # Listen on all interfaces for Cloudflare tunnel
        port=WEBHOOK_PORT,
        log_level="info"
    )
