from discord.ext import commands
from discord import app_commands
import discord

class NicknameCommand(commands.Cog):
  def __init__(self, bot):
    self.bot = bot

  @app_commands.command(name="ign", description="sets your osrs name and any alts")
  async def ign(self, interaction: discord.Interaction, main: str, alt: str = None) -> None:
    s = f"{main}"
    if alt != None:
      s += f" | {alt}"
    await interaction.user.edit(nick = s)
    await interaction.response.send_message(f"Your name is now {s}", ephemeral = True)
