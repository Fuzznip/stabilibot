from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

class GearButton(discord.ui.Button):
  def __init__(self, style, label, image):
    super().__init__(style = style, label = label)
    self.image = image
    self.label = label

  async def callback(self, interaction: discord.Interaction):
    embed = discord.Embed()
    embed.set_image(url = self.image)
    embed.title = self.label
    await interaction.response.defer()
    await interaction.channel.send(embed = embed)

class GearButtons(discord.ui.View):
  def __init__(self):
    super().__init__(timeout = None)
    self.add_item(GearButton(label = "Nex", style = discord.ButtonStyle.blurple, image = "https://i.imgur.com/HjOdnq5.png"))
    self.add_item(GearButton(label = "CoX", style = discord.ButtonStyle.green, image = "https://i.imgur.com/yQoqVaH.png"))
    self.add_item(GearButton(label = "ToB", style = discord.ButtonStyle.red, image = "https://i.imgur.com/CLkzg2T.png"))
    self.add_item(GearButton(label = "ToA", style = discord.ButtonStyle.grey, image = "https://i.imgur.com/2xIc7sO.png"))

class Gear(commands.Cog):
  def __init__(self, bot):
    self.bot = bot

  @discord.slash_command(name = "gear", description = "minimum gear setup selector", guild_ids = [int(os.getenv("GUILD_ID"))])
  async def gear(self, interaction) -> None:
    print(f"{interaction.author.nick if interaction.author.nick is not None else interaction.user.name}: /gear")
    embed = discord.Embed(title = "Select Content")
    await interaction.response.send_message(embed = embed, view = GearButtons(), ephemeral = True)
