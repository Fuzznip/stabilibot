from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import utils.db as db

class ViewTeams(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    db.ensure_teams_table()

  @discord.slash_command(name = "view_teams", description = "View all teams", guild_ids = [int(os.getenv("GUILD_ID"))])
  async def view_teams(self, interaction):
    teams = db.get_teams()

    if not teams:
      await interaction.response.send_message("No teams found.", ephemeral = True)
      return

    await interaction.response.send_message(teams, ephemeral = True)

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

class DeleteTeam(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    db.ensure_teams_table()

  # Only allow users to delete a team if they have the "Staff" role
  @commands.has_role("Staff")
  @discord.slash_command(name = "delete_team", description = "Deletes a team", guild_ids = [int(os.getenv("GUILD_ID"))])
  async def delete_team(self, interaction, team_name: str):
    # Attempt to delete a team
    success = db.delete_team(team_name)

    if not success:
      await interaction.response.send_message("Failed to delete team. Team does not exist.", ephemeral = True)
      return
    
    # Delete the role of the team
    guild = self.bot.get_guild(int(os.getenv("GUILD_ID")))
    role = discord.utils.get(guild.roles, name = team_name)
    await role.delete()

    await interaction.response.send_message(f"Successfully deleted team { team_name }!", ephemeral = True)

