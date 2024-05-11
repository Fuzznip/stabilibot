from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import utils.db as db

DEFAULT_ROLL_SIZE = 4
DEFAULT_ROLL_MODIFIER = 0

class CompleteTile(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    db.ensure_teams_table()

  @commands.has_role("Staff")
  @discord.slash_command(name = "complete_tile", description = "Completes the current tile for a team", guild_ids = [int(os.getenv("GUILD_ID"))])
  async def complete_tile(self, interaction, team_name: str):
    # Check if the team is ready to complete the tile
    if db.is_team_ready(team_name):
      await interaction.response.send_message("Your team is not ready to complete the tile. Please roll the die first!", ephemeral = True)
      return
    
    # Complete the tile
    db.complete_tile(team_name)
    db.set_roll_size(team_name, DEFAULT_ROLL_SIZE)
    db.set_roll_modifier(team_name, DEFAULT_ROLL_MODIFIER)
    # add 1 star to the team
    db.add_star(team_name)

    await interaction.response.send_message(f"Successfully completed the tile for team { team_name }!", ephemeral = True)

class AddCoins(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    db.ensure_teams_table()

  @commands.has_role("Staff")
  @discord.slash_command(name = "add_coins", description = "Adds coins to a team", guild_ids = [int(os.getenv("GUILD_ID"))])
  async def add_coins(self, interaction, team_name: str, coins: int):
    # Ensure that the coins are positive
    if coins <= 0:
      await interaction.response.send_message("Failed to add coins to team. Please enter a positive number of coins.", ephemeral = True)
      return
    
    # Check if the team exists
    if not db.team_exists(team_name):
      await interaction.response.send_message("Failed to add coins to team. Team does not exist.", ephemeral = True)
      return

    # Get the current coin count of the team
    current_coins = db.get_coin_count(team_name)
    # If the addition of coins would reach the cap of 10 coins, convert 10 coins to 1 star
    if current_coins + coins >= 10:      
      # Add coins to the team
      db.set_coins(team_name, coins + current_coins - 10)
      db.add_star(team_name)
      await interaction.response.send_message(f"Successfully added { coins } coins to { team_name }. They have gained a star and now have { coins + current_coins - 10 } coins!", ephemeral = True)
    else:
      await interaction.response.send_message(f"Successfully added { coins } coins to { team_name }. They now have { current_coins + coins } coins!", ephemeral = True)

class SetStars(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    db.ensure_teams_table()

  @commands.has_role("Staff")
  @discord.slash_command(name = "set_stars", description = "Sets the number of stars for a team", guild_ids = [int(os.getenv("GUILD_ID"))])
  async def set_stars(self, interaction, team_name: str, stars: int):
    # Ensure that the stars are positive
    if stars < 0:
      await interaction.response.send_message("Failed to set stars for team. Please enter a non-negative number of stars.", ephemeral = True)
      return

    # Check if the team exists
    if not db.team_exists(team_name):
      await interaction.response.send_message("Failed to set stars for team. Team does not exist.", ephemeral = True)
      return

    # Set the stars for the team
    db.set_stars(team_name, stars)

    await interaction.response.send_message(f"Successfully set { team_name }'s stars to { stars }!", ephemeral = True)
