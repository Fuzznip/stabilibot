from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import utils.db as db

class CreateTeam(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    db.ensure_teams_table()

  # Only allow users to create a team if they have the "Staff" role
  @commands.has_role("Staff")
  @discord.slash_command(name = "create_team", description = "Creates a team", guild_ids = [int(os.getenv("GUILD_ID"))])
  async def create_team(self, interaction, team_name: str):
    # Attempt to create a team
    success = db.create_team(team_name)

    if not success:
      await interaction.response.send_message("Failed to create team. Team name already exists.", ephemeral = True)
      return
    
    # Create a role named after the team
    guild = self.bot.get_guild(int(os.getenv("GUILD_ID")))
    await guild.create_role(name = team_name, reason = "Creating a team")

    await interaction.response.send_message(f"Successfully created team { team_name }!", ephemeral = True)
