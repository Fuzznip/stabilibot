from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import utils.db as db

class AddPlayer(commands.Cog):
  def __init__(self, bot: discord.Bot):
    self.bot = bot
    db.ensure_teams_table()

  @commands.has_role("Staff")
  @discord.slash_command(name = "add_player", description = "Adds a player to a team", guild_ids = [int(os.getenv("GUILD_ID"))])
  async def add_player(self, interaction, team_name: str, user: str):
    # Attempt to add a player to a team
    success = db.add_player(team_name, user)

    if not success:
      await interaction.response.send_message("Failed to add player to team. Team does not exist or player is already on a team.", ephemeral = True)
      return
    
    # Give the player the role of the team
    discordId = db.get_user_from_username(user)
    guild = self.bot.get_guild(int(os.getenv("GUILD_ID")))
    role = discord.utils.get(guild.roles, name = team_name)
    member = await guild.fetch_member(int(discordId))
    await member.add_roles(role)
    await interaction.response.send_message(f"Successfully added { user } to team { team_name }!", ephemeral = True)

class RemovePlayer(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    db.ensure_teams_table()

  @commands.has_role("Staff")
  @discord.slash_command(name = "remove_player", description = "Removes a player from a team", guild_ids = [int(os.getenv("GUILD_ID"))])
  async def remove_player(self, interaction, user: str):
    # Check which team the user is on
    team_name = db.get_team(db.get_user_from_username(user))

    # Attempt to remove a player from a team
    success = db.remove_player(team_name, user)

    if not success:
      await interaction.response.send_message("Failed to remove player from team. Team does not exist or player is not on the team.", ephemeral = True)
      return
    
    # Remove the role of the team from the player
    discordId = db.get_user_from_username(user)
    guild = self.bot.get_guild(int(os.getenv("GUILD_ID")))
    role = discord.utils.get(guild.roles, name = team_name)
    member = await guild.fetch_member(int(discordId))
    await member.remove_roles(role)
    await interaction.response.send_message(f"Successfully removed { user } from team { team_name }!", ephemeral = True)
