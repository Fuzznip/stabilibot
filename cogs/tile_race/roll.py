from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import utils.db as db

import random

class Roll(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    db.ensure_teams_table()

  @discord.slash_command(name = "roll", description = "Rolls on the board and moves your team forward", guild_ids = [int(os.getenv("GUILD_ID"))])
  async def roll(self, interaction):
    # Check which team the user is on
    team = db.get_team(str(interaction.author.id))

    if team is None:
      await interaction.response.send_message("You are not on a team. Please join a team before rolling.", ephemeral = True)
      return
    
    # Check if the team is ready to roll
    if not db.is_team_ready(team):
      await interaction.response.send_message("Your team is not ready to roll. Please complete your current tile!", ephemeral = True)
      return
    
    # Roll the die
    roll = random.randint(1, 4)

    # Move the team forward
    db.move_team(team, roll)

    await interaction.response.send_message(f"{ team } rolled a { roll }! { team } is now on tile { db.get_team_tile(team) }", ephemeral = False)
    
class RollTeam(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    db.ensure_teams_table()

  @commands.has_role("Staff")
  @discord.slash_command(name="roll_team", description="Rolls on the board and moves a team forward", guild_ids=[int(os.getenv("GUILD_ID"))])
  async def roll_team(self, interaction, team_name: str):
    # Check if the team is ready to roll
    if not db.is_team_ready(team_name):
      await interaction.response.send_message(f"{team_name} is not ready to roll. Please complete the current tile!", ephemeral=True)
      return

    # Roll the die
    roll = random.randint(1, 4)

    # Move the team forward
    db.move_team(team_name, roll)

    await interaction.response.send_message(f"{team_name} rolled a {roll}! {team_name} is now on tile {db.get_team_tile(team_name)}", ephemeral=False)

