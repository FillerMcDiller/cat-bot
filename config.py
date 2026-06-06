
import dotenv
from dotenv import load_dotenv
import os

load_dotenv(override=True)


def _normalize_public_base_url(value: str | None) -> str | None:
    if not value:
        return None
    url = str(value).strip().rstrip("/")
    if not url:
        return None
    if "://" not in url:
        url = f"http://{url}"
    return url

TOKEN = os.getenv("TOKEN")
if TOKEN:
    TOKEN = TOKEN.strip().replace('\ufeff', '')  # remove BOM and whitespace
else:
    raise RuntimeError("TOKEN not found in .env!")
# db password for postgres
# user - cat_bot, database - cat_bot, ip - localhost, port - default
DB_PASS = os.environ["DBPASS"] = "cat"

#
# all the following are optional (setting them to None will disable the feature)
#

# channel id for db backups, private extremely recommended
BACKUP_ID = 1436486865489236299

# top.gg vote webhook verification key, setting this to None disables all voting stuff
WEBHOOK_VERIFY = os.getenv("WEBHOOK_VERIFY")  

# Optional alias for external webhook integrations
TOPGG_WEBHOOK_SECRET = os.getenv("TOPGG_WEBHOOK_SECRET")

# Public webhook port (Top.gg/Cloudflare tunnel target)
WEBHOOK_PORT = int(os.getenv("VOTE_WEBHOOK_PORT", "3001"))

# Internal receiver port (local forwarding target)
INTERNAL_WEBHOOK_PORT = int(os.getenv("BOT_INTERNAL_PORT", "3002"))

# Signed web session secret for inventory links created by /inventory
INVENTORY_WEB_TOKEN_SECRET = os.getenv("INVENTORY_WEB_TOKEN_SECRET")

# Public GitHub Pages URL for the inventory web UI
INVENTORY_WEB_UI_URL = os.getenv("INVENTORY_WEB_UI_URL")

# Public API base URL that the GitHub Pages UI should call
INVENTORY_API_BASE_URL = _normalize_public_base_url(os.getenv("INVENTORY_API_BASE_URL"))

# Public API base URL for the Cat Competition submission form.
# Falls back to the inventory API base when both features share the same backend.
CATCOMP_API_BASE_URL = _normalize_public_base_url(os.getenv("CATCOMP_API_BASE_URL")) or INVENTORY_API_BASE_URL

# Allowed CORS origin for web UI (set to your GitHub Pages URL in production)
WEB_UI_ORIGIN = os.getenv("WEB_UI_ORIGIN", "fillermcdiller.github.io/cat-bot")

# top.gg api token to occasionally post stats
TOP_GG_TOKEN = os.getenv("TOP_GG_TOKEN")

# only post stats if server count is above this, to prevent wrong stats
MIN_SERVER_SEND = 0  # Changed from 100_000 to 0 to allow stats posting for all server counts

# wordnik api key for /define command
WORDNIK_API_KEY = None

# channel to store supporter images, can also be used for moderation purposes
DONOR_CHANNEL_ID = 1249343008890028144

# cat bot will also log all rain uses/movements here
# cat!rain commands here can be used without author check and will dm reciever a thanks message
RAIN_CHANNEL_ID = 1436486865489236299

# OpenRouter API key for chatbot 
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")

# Gemini settings for periodic chat reader responses
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# Azure OpenAI settings for periodic chat reader responses
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

# Chat reader behavior tuning
CHAT_INTERVAL_SECONDS = int(os.getenv("CHAT_INTERVAL_SECONDS", "600"))
CHAT_BUFFER_SIZE = int(os.getenv("CHAT_BUFFER_SIZE", "120"))
CHAT_CONTEXT_MESSAGES = int(os.getenv("CHAT_CONTEXT_MESSAGES", "40"))
CHAT_MIN_NEW_MESSAGES = int(os.getenv("CHAT_MIN_NEW_MESSAGES", "4"))
CHAT_MAX_MESSAGE_CHARS = int(os.getenv("CHAT_MAX_MESSAGE_CHARS", "220"))
