from discord.ext import commands
from discord import app_commands
import discord
from dotenv import load_dotenv
load_dotenv()
import os

class PublishButton(discord.ui.Button):
  def __init__(self, embed, destination):
    super().__init__(style = discord.ButtonStyle.green, label = "Publish")
    self.embed = embed
    self.channel = destination

  async def callback(self, interaction: discord.Interaction):
    destination = interaction.guild.get_channel(self.channel)
    await destination.send(embed = self.embed)
    await interaction.message.delete()

class CancelButton(discord.ui.Button):
  def __init__(self):
    super().__init__(style = discord.ButtonStyle.red, label = "Cancel")

  async def callback(self, interaction: discord.Interaction):
    await interaction.message.delete()

class Confirmation(discord.ui.View):
  def __init__(self, embed, destination):
    super().__init__(timeout = None)
    self.add_item(PublishButton(embed, destination))
    self.add_item(CancelButton())

class Announce(commands.Cog):
  def __init__(self, bot):
    self.bot = bot

    self.channel = int(os.environ.get("ANNOUNCEMENTS_CHANNEL")) # test-announcements channel id

  @app_commands.command(name = "announce", description = "Queues up an announcement to #announcements")
  async def announce(self, interaction: discord.Interaction, body: str, details: str = None, title: str = None) -> None:
    embed = discord.Embed()
    embed.title = title
    embed.description = body + f"\n\nIf you wish to learn more, check the full post here: {details}"
    await interaction.response.send_message(embed = embed, view = Confirmation(embed, self.channel), ephemeral = False)
  