from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import utils.db as db

import random

PASSED_START_STAR_COUNT = 3
DEFAULT_ROLL_SIZE = 4
DEFAULT_ROLL_MODIFIER = 0

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
    roll_size = db.get_roll_size(team)
    roll_mod = db.get_roll_modifier(team)
    roll = random.randint(1, roll_size) + roll_mod

    # Move the team forward
    if db.move_team(team, roll, 20):
      # Add stars to the team
      db.add_stars(team, PASSED_START_STAR_COUNT)

      # Get star count
      stars = db.get_star_count(team)
      await interaction.response.send_message(f"{ team } rolled a { roll }. They have looped to the beginning, gained {PASSED_START_STAR_COUNT} stars, and are now on tile { db.get_team_tile(team) + 1 } with { stars } stars!!", ephemeral = False)
    else:
      await interaction.response.send_message(f"{ team } rolled a { roll }! { team } is now on tile { db.get_team_tile(team) + 1 }", ephemeral = False)    

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
    roll_size = db.get_roll_size(team_name)
    roll_mod = db.get_roll_modifier(team_name)
    roll = random.randint(1, roll_size) + roll_mod

    # Move the team forward
    if db.move_team(team_name, roll, 20):
      # Add stars to the team
      db.add_stars(team_name, PASSED_START_STAR_COUNT)

      # Get star count
      stars = db.get_star_count(team_name)
      await interaction.response.send_message(f"{ team_name } rolled a { roll }. They have looped to the beginning, gained {PASSED_START_STAR_COUNT} stars, and are now on tile { db.get_team_tile(team_name) + 1 } with { stars } stars!", ephemeral = False)
    else:
      await interaction.response.send_message(f"{ team_name } rolled a { roll }! { team_name } is now on tile { db.get_team_tile(team_name) + 1 }", ephemeral = False)  
