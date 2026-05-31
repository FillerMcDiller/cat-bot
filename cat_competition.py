import os
from urllib.parse import urlencode
import discord
from discord.ext import commands
from discord import app_commands


class CatCompLink(commands.Cog):
    """Provides a single command linking to the website submission form."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name='catcomp', description='Open the Cat Competition submission page (website)')
    async def catcomp(self, interaction: discord.Interaction):
        api_base = None
        try:
            from config import CATCOMP_API_BASE_URL
            api_base = CATCOMP_API_BASE_URL
        except Exception:
            api_base = None

        url = os.getenv('CATCOMP_URL', 'https://fillermcdiller.github.io/cat-bot/catcomp/')
        if api_base:
            separator = '&' if '?' in url else '?'
            url = f"{url}{separator}{urlencode({'api': api_base})}"

        await interaction.response.send_message(f'Submit your entry on the website: {url}', ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(CatCompLink(bot))
