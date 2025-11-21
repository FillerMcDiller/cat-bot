<<<<<<< HEAD
<<<<<<< HEAD
# ![Cat Bot PFP](https://wsrv.nl/?url=raw.githubusercontent.com/milenakos/cat-bot/main/images/cat.png&h=25) Cat Bot [![Discord Bots](https://top.gg/api/widget/1387305159264309399.svg) [![Discord Bots](https://top.gg/api/v1/widgets/large/724055681490399232)(https://top.gg//discord/servers/724055681490399232) [![Wiki](https://img.shields.io/badge/Wiki-blue?label=Cat%20Bot&logo=wiki.js)](https://wiki.minkos.lol)

Discord Cat Bot Source Code

# Development

Please note that self-hosting is hacky and isn't supported; instructions below are for testing/development/messing around. I won't stop you, but you WILL have to mess around with the code a bunch for it to work good, so be warned.

## Prerequisites

- Python 3 (around 3.8 or so, newer is better ofc)
- PostgreSQL
- Git (optional)

## Instructions

1. Clone the repository. You can use the green "Code" button at the top or a git command:

   ```shell
   git clone https://github.com/milenakos/cat-bot.git
   ```

3. Install requirements:

   ```shell
   pip install -r requirements.txt
   ```

   If you are running a Gateway Proxy, do `pip install -r requirements-gw.txt` instead. This uses a custom fork which contacts `localhost:7878` instead and removes ratelimits and heartbeats.

4. You will need to add all emojis you want to Discord's App Emoji in the Dev Portal.

   If they aren't found there, they will be replaced with a placeholder.

   All emojis can be downloaded [here](https://github.com/staring-cat/emojis/releases/latest/download/emojis.zip).

5. Go inside of the `config.py` file and configure everything to your liking.

6. Run the bot with `python bot.py`.

7. Done!

=======
# cat-botmcdiller

Discord Cat Bot by milenakos, edited by fillermcdiller

not public as of rn, don't plan on doing that. Used in my discord server.

Hosted on 10 year old pc with Debian 13

