from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import utils.db as db

class Accounts(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        # Ensure any databases that we need exist

    @discord.slash_command(name = "accounts", description = "Lists the osrs accounts linked to your discord account", guild_ids = [int(os.getenv("GUILD_ID"))])
    async def accounts(self, interaction):
        # Log the command
        print(f"{interaction.author.nick if interaction.author.nick is not None else interaction.user.name}: /accounts")
        # Defer the response
        accounts = db.get_user(str(interaction.author.id))
        if accounts:
            await interaction.response.send_message(f"Linked accounts: {', '.join(accounts)}", ephemeral = True)
            return
        else:
            await interaction.response.send_message("No accounts linked", ephemeral = True)
            return

        await interaction.response.send_message("Command not implemented", ephemeral = True)

