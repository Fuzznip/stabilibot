from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import utils.db as db

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

    await interaction.response.send_message(f"Successfully completed the tile for team { team_name }!", ephemeral = True)
