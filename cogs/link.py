from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import utils.db as db

class Link(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    db.create_table()

  @discord.slash_command(name = "link", help = "Link your osrs account to your discord account.", guild_ids = [int(os.getenv("GUILD_ID"))])
  async def link(self, interaction, username: str):
    success = await db.add_user(str(interaction.author.id), username)
    if not success:
      await interaction.response.send_message("Failed to link the account. Please make sure you enter the username of an account you own.", ephemeral = True)
      return

    usernames = db.get_user(str(interaction.author.id))

    # if usernames is not empty
    if usernames:
      await interaction.response.send_message(f"Successfully linked {username} to your discord account. Your linked accounts are: {', '.join(usernames)}", ephemeral = True)
      return

    await interaction.response.send_message(f"Successfully linked {username} to your discord account. You now have no linked accounts.", ephemeral = True)
