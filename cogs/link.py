from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import utils.db as db

import wom

class Link(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    db.create_table()

  @discord.slash_command(name = "link", help = "Link your osrs account to your discord account.", guild_ids = [int(os.getenv("GUILD_ID"))])
  async def link(self, interaction, username: str):
    print(f"{interaction.author.nick if interaction.author.nick is not None else interaction.user.name}: /link {username}")
    # check if the username is a valid RuneScape username
    try:
      # Get user data from WOM
      womClient = wom.Client(user_agent = "Stabilibot")
      await womClient.start()
      # get the first snapshot of the player
      result = await womClient.players.update_player(username = username)
      # Check if error is http response 429 (rate limited)
      if result.is_err:
        if result.unwrap_err().status != 429: # rate limiting is fine we just want to check if the username is valid
          print(result.unwrap_err().message)
      await womClient.close()
    except Exception as e:
      print(e)
      await womClient.close()
      await interaction.response.send_message("Failed to link the account. Unable to find account on Wise Old Man", ephemeral = True)
      return

    success = await db.add_user(str(interaction.author.id), username)
    if not success:
      await interaction.response.send_message("Failed to link the account. That account has already been linked.", ephemeral = True)
      return

    usernames = db.get_user(str(interaction.author.id))

    # if usernames is not empty
    if usernames:
      await interaction.response.send_message(f"Successfully linked {username} to your discord account. Your linked accounts are: {', '.join(usernames)}", ephemeral = True)
      return

    await interaction.response.send_message(f"Successfully linked {username} to your discord account. You now have no linked accounts.", ephemeral = True)
