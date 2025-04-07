from discord.ext import commands
from discord import ui
import discord
import requests

from dotenv import load_dotenv
load_dotenv()
import os

class Apply(commands.Cog):
  def __init__(self, bot):
    self.bot = bot

  # Slash command to apply to join the clan
  @discord.slash_command(name = "apply", description = "Apply to join the clan", guild_ids = [int(os.getenv("GUILD_ID"))])
  async def apply(self, interaction):
    print(f"{interaction.author.nick if interaction.author.nick is not None else interaction.user.name}: /apply")
    # Check if the interaction is in a guild
    if not interaction.guild:
      await interaction.response.send_message("This command can only be used in a server", ephemeral = True)
      return
    
    # Check if the user has the "Applied" role
    role = discord.utils.get(interaction.guild.roles, name = "Applied")
    if role in interaction.user.roles:
      await interaction.response.send_message("You have already applied", ephemeral = True)
      return
    
    # Check if the user has the "Member" role
    role = discord.utils.get(interaction.guild.roles, name = "Member")
    if role in interaction.user.roles:
      await interaction.response.send_message("You are already a member", ephemeral = True)
      return
    
    await interaction.response.send_message("Please visit https://stabilityosrs.com to apply to the clan. If you have any questions, please ask a staff member.", ephemeral = True)
