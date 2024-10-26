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
    async def COMMAND(self, interaction, options: str, to: str, be: str, passed: str):
        await interaction.response.send_message("", ephemeral = False)
        pass
