import os
import discord
from discord.ext import commands
from discord import app_commands


class CatCompLink(commands.Cog):
    """Provides a single command linking to the website submission form."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name='catcomp', description='Open the Cat Competition submission page (website)')
    async def catcomp(self, interaction: discord.Interaction):
        # Use an environment variable or config override for the submission URL
        url = None
        try:
            from config import CATCOMP_URL
            url = CATCOMP_URL
        except Exception:
            url = None

        if not url:
            url = os.getenv('CATCOMP_URL', 'https://example.com/catcomp-submit')

        await interaction.response.send_message(f'Submit your entry on the website: {url}', ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(CatCompLink(bot))
