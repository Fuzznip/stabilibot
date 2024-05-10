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

class MyTeam(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    db.ensure_teams_table()

  @discord.slash_command(name = "my_team", description = "View your team", guild_ids = [int(os.getenv("GUILD_ID"))])
  async def my_team(self, interaction):
    team = db.get_team(str(interaction.author.id))

    if team is None:
      await interaction.response.send_message("You are not on a team. Please join a team.", ephemeral = True)
      return

    tile_id = db.get_team_tile(team)
    tile_data = db.get_tile(tile_id)
    tile_name = tile_data[1]

    stars = db.get_star_count(team)
    coins = db.get_coin_count(team)

    await interaction.response.send_message(f"""You are on team { team }.
Your team currently has { stars } stars and { coins } coins.
You are on tile number {tile_id + 1}: {tile_name}.

Want more information? Ask what you want to see out of the bot at https://discord.com/channels/519627285503148032/1238326277191241728""", ephemeral = True)

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

