from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import utils.db as db

class Unlink(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    db.create_table()

  @discord.slash_command(name = "unlink", help = "Unlinks an osrs account from your discord account.", guild_ids = [int(os.getenv("GUILD_ID"))])
  async def unlink(self, interaction, username: str):
    success = await db.remove_user(str(interaction.author.id), username)
    
    usernames = db.get_user(str(interaction.author.id))

    if not success:
      if usernames:
        await interaction.response.send_message(f"Failed to unlink the account. {username} was not linked to your discord account. Your linked accounts are: {', '.join(usernames)}", ephemeral = True)
        return
      else:
        await interaction.response.send_message(f"Failed to unlink the account. {username} was not linked to your discord account. You have no linked accounts.", ephemeral = True)
        return

    # if usernames is not empty
    if usernames:
      await interaction.response.send_message(f"Successfully removed {username} from your discord account. Your linked accounts are: {', '.join(usernames)}", ephemeral = True)
      return

    await interaction.response.send_message(f"Successfully removed {username} from your discord account.", ephemeral = True)
    