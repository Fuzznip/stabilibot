from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import utils.db as db

class UseItem(discord.Button):
  def __init__(self, item: str, callback):
    super().__init__(style = discord.ButtonStyle.green, label = item)
    self.item = item
    self.callback = callback

  async def callback(self, interaction):
    db.use_item(self.callback, self.item)
    await interaction.response.send_message(f"Used item { self.item }.", ephemeral = True)

class Items(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    db.ensure_teams_table()

  @discord.slash_command(name = "use_item", description = "View your team's items", guild_ids = [int(os.getenv("GUILD_ID"))])
  async def items(self, interaction):
    items = db.get_items(str(interaction.author.id))

    if not items:
      await interaction.response.send_message("You have no items.", ephemeral = True)
      return

    buttons = []
    for item in items:
      buttons.append(UseItem(item, str(interaction.author.id)))

    await interaction.response.send_message("Select an item to use.", components = [buttons], ephemeral = True)
    