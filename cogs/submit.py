from discord.ext import commands
from discord import ui
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import aiohttp

class SubmissionModal(ui.Modal):
  def __init__(self, bot: commands.Bot, interaction: discord.Interaction, message: discord.Message):
    super().__init__(title = "Submit", timeout = None, custom_id = "submit_form")
    self.bot = bot
    self.interaction = interaction
    self.message = message
    self.add_item(self.questionItemName)
    self.add_item(self.questionItemSource)

  async def callback(self, interaction) -> None:
    message = await interaction.response.defer(ephemeral = True, invisible = False)  # Acknowledge the interaction

    # Create json payload
    payload = {
      "timestamp": self.message.created_at.isoformat(),
      "user": self.message.author.nick,
      "discordId": self.message.author.id,
      "item": self.questionItemName.value,
      "source": self.questionItemSource.value,
      "attachment": self.message.attachments[0].url # Should be guaranteed to have exactly one attachment
    }

    # Send the json payload to the SUBMISSION_ENDPOINT
    try:
      async with aiohttp.ClientSession() as session:
        async with session.post(os.getenv("SUBMISSION_ENDPOINT"), json = payload) as response:
          if response.status != 200:
            await interaction.followup.send("Error submitting file.")
            return
          
          # get response data
          data = await response.json()
          await interaction.followup.send(data["message"])
          return
    except aiohttp.ClientConnectorError as e:
      print(str(e))
      await interaction.followup.send(f"Error connecting to server: {str(e)}")
      return
    except e:
      print(str(e))
      await interaction.followup.send(f"Unknown Error: {str(e)}")
      return

  questionItemName = discord.ui.InputText(label = "What is the name of the drop? (EXACT NAME)", style = discord.InputTextStyle.short, placeholder = "Scythe of vitur (uncharged)", required = True)
  questionItemSource = discord.ui.InputText(label = "Where did you get the drop?", style = discord.InputTextStyle.short, placeholder = "Theatre of Blood", required = True)

class Submit(commands.Cog):
  def __init__(self, bot):
    self.bot = bot

  @discord.message_command(name = "Submit", guild_ids = [int(os.getenv("GUILD_ID"))])
  async def submit(self, interaction: discord.Interaction, message: discord.Message):
    print(f"{interaction.author.nick if interaction.author.nick is not None else interaction.user.name}: /submit {message.author.nick}")
    # Check that the message contains exactly one attachment
    if len(message.attachments) != 1:
      await interaction.response.send_message("Please only submit on a message with exactly one file.", ephemeral = True)
      return
    
    # TODO: Check if the message has already been submitted

    # Send a modal to the user for additional information
    await interaction.response.send_modal(SubmissionModal(self.bot, interaction, message))
