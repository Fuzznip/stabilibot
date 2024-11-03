from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import utils.db as db

class CommandTemplate(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        # Ensure any databases that we need exist

    @commands.has_role("Staff") # Double check roles
    @discord.slash_command(name = "command name", description = "command description", guild_ids = [int(os.getenv("GUILD_ID"))])
    async def command(self, interaction, opts: str):
        # Log the command
        print(f"{interaction.author.nick if interaction.author.nick is not None else interaction.user.name}: /command {opts}")
        # Defer the response
        await interaction.response.defer()

        await interaction.followup.send("Command not implemented", ephemeral = True)
