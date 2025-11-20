
import dotenv
from dotenv import load_dotenv
import os

load_dotenv()

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

# top.gg api token to occasionally post stats
TOP_GG_TOKEN = os.getenv("TOP_GG_TOKEN")

# only post stats if server count is above this, to prevent wrong stats
MIN_SERVER_SEND = 100_000

# wordnik api key for /define command
WORDNIK_API_KEY = None

# channel to store supporter images, can also be used for moderation purposes
DONOR_CHANNEL_ID = 1249343008890028144

# cat bot will also log all rain uses/movements here
# cat!rain commands here can be used without author check and will dm reciever a thanks message
RAIN_CHANNEL_ID = 1436486865489236299

# OpenRouter API key for chatbot 
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
