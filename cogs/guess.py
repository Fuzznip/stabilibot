from discord.ext import commands
from discord import ui
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import aiohttp
import io

class GuessModal(ui.Modal):
    def __init__(self, bot: commands.Bot, interaction: discord.Interaction, message: discord.Message):
        super().__init__(title = "Guess", timeout = None, custom_id = "guess_form")
        self.bot = bot
        self.interaction = interaction
        self.message = message
        self.add_item(self.questionItemName)
        self.add_item(self.questionLocation)

    async def callback(self, interaction) -> None:
        await interaction.response.defer(ephemeral = True)
        
        # Create json payload
        payload = {
            "discord_id": str(self.message.author.id),
            "item_name": self.questionItemName.value,
            "location": self.questionLocation.value
        }

        # Send the json payload to the /guess endpoint
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(os.getenv("BACKEND_URL") + "/guess", json = payload) as response:
                    if response.status != 200:
                        print(response.status)
                        print(f"Error response: {await response.text()}")
                        await interaction.followup.send("Error submitting guess.")
                        return
                    else:
                        print(f"Guess submission successful: {response.status}")
                
                # Get response data
                data = await response.json()
                
                # Extract the response fields
                item_name_matches = data.get("item_name_matches", False)
                location_matches = data.get("location_matches", False)
                puzzle_solved = data.get("puzzle_solved", False)
                response_message = data.get("message", "Guess submitted successfully")
                
                # Log the results
                print(f"Item match: {item_name_matches}, Location match: {location_matches}, Puzzle solved: {puzzle_solved}")
                
                # If a puzzle was solved, notify the designated user
                if puzzle_solved:
                    try:
                        # Get the user to notify
                        notify_user = await self.bot.fetch_user(88087113626587136)
                        
                        # Download the attachment from the message
                        attachment = self.message.attachments[0]
                        file_data = await attachment.read()
                        file = discord.File(fp = io.BytesIO(file_data), filename = attachment.filename)
                        
                        # Create notification message
                        notification_message = (
                            f"**Puzzle Solved!**\n"
                            f"User: {self.message.author.display_name} ({self.message.author.id})\n"
                            f"Item Name: {self.questionItemName.value}\n"
                            f"Location: {self.questionLocation.value}"
                        )
                        
                        # Send DM with the file
                        await notify_user.send(content = notification_message, file = file)
                        print(f"Notified user 88087113626587136 about puzzle solve by {self.message.author.display_name}")
                    except Exception as e:
                        print(f"Error notifying user about puzzle solve: {str(e)}")
                
                # Send the response message to the user
                await interaction.followup.send(response_message)
                return
        except aiohttp.ClientConnectorError as e:
            print(str(e))
            await interaction.followup.send(f"Error connecting to server: {str(e)}")
            return
        except Exception as e:
            print(f"Unknown error: {str(e)}")
            await interaction.followup.send(f"Unknown Error")
            return

    questionItemName = discord.ui.InputText(label = "Item Name", style = discord.InputTextStyle.short, placeholder = "Enter the item name", required = True)
    questionLocation = discord.ui.InputText(label = "Location", style = discord.InputTextStyle.short, placeholder = "Enter the location", required = True)

class Guess(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.message_command(name = "Submit Guess", guild_ids = [int(os.getenv("GUILD_ID"))])
    async def guess(self, interaction: discord.Interaction, message: discord.Message):
        print(f"{interaction.author.display_name}: Submit Guess on {message.author.display_name}'s message")
        
        # Check that the message contains exactly one attachment
        if len(message.attachments) != 1:
            await interaction.response.send_message("Please only submit on a message with exactly one file.", ephemeral = True)
            return
        
        # Send a modal to the user for input
        await interaction.response.send_modal(GuessModal(self.bot, interaction, message))

def setup(bot):
    bot.add_cog(Guess(bot))
