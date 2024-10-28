from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import utils.db as db

class CommandClass(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        db.ensure_teams_table()

    @commands.has_role("Staff")
    @discord.slash_command(name = "", description = "", guild_ids = [int(os.getenv("GUILD_ID"))])
    async def COMMAND(self, interaction, team_name: str):
        # Log the command
        print(f"{interaction.author.nick if interaction.author.nick is not None else interaction.user.name}: /{interaction.data['name']} {team_name}")

        # Check if the team name is already in use
        if db.team_exists(team_name):
            await interaction.response.send_message("Team name already in use", ephemeral = True)
            return

        # Create the team
        try:
            db.create_team(team_name)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral = True)
            return

        await interaction.response.send_message(f"Succesfully created team {team_name}", ephemeral = True)
        pass
