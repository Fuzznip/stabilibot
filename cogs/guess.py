from discord.ext import commands
from discord import ui
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import aiohttp
import io

class GuessModal(ui.DesignerModal):
    def __init__(self, bot: commands.Bot, interaction: discord.Interaction):
        super().__init__(title = "Guess", custom_id = "guess_form")
        self.bot = bot
        self.interaction = interaction
        
        # Add Item Name field
        item_name_label = ui.Label(label = "Item Name")
        item_name_label.set_input_text(placeholder = "Enter the item name", required = True)
        self.add_item(item_name_label)
        
        # Add Location field
        location_label = ui.Label(label = "Location")
        location_label.set_input_text(placeholder = "Enter the location", required = True)
        self.add_item(location_label)
        
        # Add Screenshot field
        screenshot_label = ui.Label(label = "Screenshot")
        screenshot_label.set_file_upload(required = False, min_values = 0, max_values = 1)
        self.add_item(screenshot_label)

    async def callback(self, interaction) -> None:
        await interaction.response.defer(ephemeral = True)
        
        # Extract values from modal
        item_name = None
        location = None
        screenshot = None
        
        for item in self.children:
            if isinstance(item, ui.Label):
                if item.label == "Item Name":
                    item_name = item.item.value if hasattr(item.item, 'value') else None
                elif item.label == "Location":
                    location = item.item.value if hasattr(item.item, 'value') else None
                elif item.label == "Screenshot":
                    screenshot = item.item.values[0] if hasattr(item.item, 'values') and item.item.values else None
        
        # Get the current user from interaction
        user = interaction.user
        
        # Create json payload
        payload = {
            "discord_id": str(user.id),
            "item_name": item_name,
            "location": location,
            "has_image": screenshot is not None
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
                    
                    # If a puzzle was solved without an image, tell them to submit proof
                    if puzzle_solved and not screenshot:
                        proof_message = "**Correct!** You got the right answer! Please submit the location with a screenshot as proof to confirm the answer."
                        await interaction.followup.send(proof_message)
                        return
                    
                    # If a puzzle was solved with an image, notify the designated user
                    if puzzle_solved and screenshot:
                        try:
                            # Get the user to notify
                            notify_user = await self.bot.fetch_user(88087113626587136)
                            
                            # Download the attachment from the screenshot
                            file_data = await screenshot.read()
                            file = discord.File(fp = io.BytesIO(file_data), filename = screenshot.filename)
                            
                            # Create notification message
                            notification_message = (
                                f"**Puzzle Solved!**\n"
                                f"User: {user.display_name} ({user.id})\n"
                                f"Item Name: {item_name}\n"
                                f"Location: {location}"
                            )
                            
                            # Send DM with the file
                            await notify_user.send(content = notification_message, file = file)
                            print(f"Notified user 88087113626587136 about puzzle solve by {user.display_name}")
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

class Guess(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(name = "guess", description = "Submit a guess for an item and location", guild_ids = [int(os.getenv("GUILD_ID"))])
    async def guess(self, interaction):
        print(f"{interaction.user.name}: /guess")
        
        # Send a modal to the user for input
        await interaction.response.send_modal(GuessModal(self.bot, interaction))

def setup(bot):
    bot.add_cog(Guess(bot))
