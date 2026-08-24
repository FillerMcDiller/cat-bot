import os
from urllib.parse import urlencode
import discord
from discord.ext import commands
from discord import app_commands


class CatCompLink(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name='catcomp', description='Open the Cat Competition submission page (website)')
    async def catcomp(self, interaction: discord.Interaction):
        api_base = None
        api_backups = []
        try:
            from config import CATCOMP_API_BASE_URL, CATCOMP_API_BACKUPS
            api_base = CATCOMP_API_BASE_URL
            api_backups = list(CATCOMP_API_BACKUPS or [])
        except Exception:
            api_base = None
            api_backups = []

        url = os.getenv('CATCOMP_URL', 'https://fillermcdiller.github.io/cat-bot/catcomp/')
        params = {}
        if api_base:
            params['api'] = api_base
        if api_backups:
            clean_backups = [b for b in api_backups if b and b.rstrip('/') != (api_base or '').rstrip('/')]
            if clean_backups:
                params['api_backups'] = ','.join(clean_backups)

        if params:
            separator = '&' if '?' in url else '?'
            url = f"{url}{separator}{urlencode(params)}"

        await interaction.response.send_message(f'Submit your entry on the website: {url}', ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(CatCompLink(bot))
