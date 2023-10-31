from channelcheck import is_channel
from discord.ext import commands
from discord import app_commands
import discord

class GearButton(discord.ui.Button):
  def __init__(self, style, label, image):
    super().__init__(style = style, label = label)
    self.image = image
    self.label = label

  async def callback(self, interaction: discord.Interaction):
    embed = discord.Embed()
    embed.set_image(url = self.image)
    embed.title = self.label
    await interaction.response.send_message(embed = embed, ephemeral = False)

class GearButtons(discord.ui.View):
  def __init__(self):
    super().__init__(timeout = None)
    self.add_item(GearButton(label = "Nex", style = discord.ButtonStyle.blurple, image = "https://i.imgur.com/HjOdnq5.png"))
    self.add_item(GearButton(label = "CoX", style = discord.ButtonStyle.green, image = "https://i.imgur.com/yQoqVaH.png"))
    self.add_item(GearButton(label = "ToB", style = discord.ButtonStyle.red, image = "https://i.imgur.com/CLkzg2T.png"))
    self.add_item(GearButton(label = "ToA", style = discord.ButtonStyle.grey, image = "https://i.imgur.com/2xIc7sO.png"))

class GearCommand(commands.Cog):
  def __init__(self, bot):
    self.bot = bot

  @app_commands.command(name="gear", description="minimum gear setup selector")
  async def gear(self, interaction: discord.Interaction) -> None:
    embed = discord.Embed(title = "Select Content")
    await interaction.response.send_message(embed = embed, view = GearButtons(), ephemeral = True)
