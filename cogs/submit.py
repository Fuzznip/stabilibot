from discord.ext import commands
from discord import ui
import discord

from dotenv import load_dotenv
load_dotenv()
import os
import json

import aiohttp

class DropSubmissionModal(ui.Modal):
    def __init__(self, bot: commands.Bot, interaction: discord.Interaction, message: discord.Message):
        super().__init__(title = "Submit", timeout = None, custom_id = "submit_form")
        self.bot = bot
        self.interaction = interaction
        self.message = message
        self.add_item(self.questionItemName)
        self.add_item(self.questionItemSource)
        self.add_item(self.questionItemQuantity)
        self.questionItemQuantity.value = "1"

    async def callback(self, interaction) -> None:
        await interaction.response.defer(ephemeral = True)
        # Create json payload
        payload = {
            "submission_type": "drop",
            "timestamp": self.message.created_at.isoformat(),
            "user": self.message.author.name,
            "discord_id": str(self.message.author.id),
            "item_name": self.questionItemName.value,
            "source": self.questionItemSource.value,
            "quantity": self.questionItemQuantity.value,
            "attachment_url": self.message.attachments[0].url # Should be guaranteed to have exactly one attachment
        }

        # Send the json payload to the SUBMISSION_ENDPOINT
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(os.getenv("DROP_SERVER_URL") + "/bot", json = payload) as response:
                    if response.status != 200:
                        print(response.status)
                        print(json.dumps(payload, indent = 4))
                        print(os.getenv("DROP_SERVER_URL") + "/bot")
                        await interaction.followup.send("Error submitting file.")
                        return
                    else: 
                        print(f"Submission successful: {response.status}")
                        print(await response.text())
                
                # get response data
                data = await response.json()
                await interaction.followup.send(data["message"])
                return
        except aiohttp.ClientConnectorError as e:
            print(str(e))
            await interaction.followup.send(f"Error connecting to server: {str(e)}")
            return
        except:
            await interaction.followup.send(f"Unknown Error")
            return

    questionItemName = discord.ui.InputText(label = "What is the name of the drop? (EXACT NAME)", style = discord.InputTextStyle.short, placeholder = "Scythe of vitur (uncharged)", required = True)
    questionItemSource = discord.ui.InputText(label = "Where did you get the drop?", style = discord.InputTextStyle.short, placeholder = "Theatre of Blood", required = True)
    questionItemQuantity = discord.ui.InputText(label = "How many of this item are you submitting?", style = discord.InputTextStyle.short, placeholder = "1", required = False)

class Submit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.message_command(name = "Submit Drop", guild_ids = [int(os.getenv("GUILD_ID"))])
    async def submit(self, interaction: discord.Interaction, message: discord.Message):
        print(f"{interaction.author.display_name}: /submit {message.author.display_name}")
        # Check that the message contains exactly one attachment
        if len(message.attachments) != 1:
            await interaction.response.send_message("Please only submit on a message with exactly one file.", ephemeral = True)
            return
        
        # TODO: Check if the message has already been submitted

        # Send a modal to the user for additional information
        await interaction.response.send_modal(DropSubmissionModal(self.bot, interaction, message))

class KCSubmissionModal(ui.Modal):
    def __init__(self, bot: commands.Bot, interaction: discord.Interaction, message: discord.Message):
        super().__init__(title = "Submit", timeout = None, custom_id = "submit_form")
        self.bot = bot
        self.interaction = interaction
        self.message = message
        self.add_item(self.questionBossName)
        self.add_item(self.questionKCCount)
        self.questionKCCount.value = "1" # Default value for KC count

    async def callback(self, interaction) -> None:
        await interaction.response.defer(ephemeral = True)
        # Create json payload
        payload = {
            "submission_type": "kc",
            "timestamp": self.message.created_at.isoformat(),
            "user": self.message.author.nick if self.message.author.nick is not None else self.message.author.name,
            "discord_id": str(self.message.author.id),
            "boss_name": self.questionBossName.value,
            "kill_count": self.questionKCCount.value,
            "attachment_url": self.message.attachments[0].url # Should be guaranteed to have exactly one attachment
        }

        # Send the json payload to the SUBMISSION_ENDPOINT
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(os.getenv("DROP_SERVER_URL") + "/bot", json = payload) as response:
                    if response.status != 200:
                        print(response.status)
                        print(json.dumps(payload, indent = 4))
                        print(os.getenv("DROP_SERVER_URL") + "/bot")
                        await interaction.followup.send("Error submitting file.")
                        return
                    else: 
                        print(f"Submission successful: {response.status}")
                        print(await response.text())
                
                # get response data
                data = await response.json()
                await interaction.followup.send(data["message"])
                return
        except aiohttp.ClientConnectorError as e:
            print(str(e))
            await interaction.followup.send(f"Error connecting to server: {str(e)}")
            return
        except:
            await interaction.followup.send(f"Unknown Error")
            return

    questionBossName = discord.ui.InputText(label = "What is the name of the boss?", style = discord.InputTextStyle.short, placeholder = "Theatre of Blood", required = True)
    questionKCCount = discord.ui.InputText(label = "How many kills are you submitting?", style = discord.InputTextStyle.short, placeholder = "1", required = False)

class SubmitKC(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.message_command(name = "Submit KC", guild_ids = [int(os.getenv("GUILD_ID"))])
    async def submit(self, interaction: discord.Interaction, message: discord.Message):
        print(f"{interaction.author.nick if interaction.author.nick is not None else interaction.user.name}: /submit {message.author.nick}")
        # Check that the message contains exactly one attachment
        if len(message.attachments) != 1:
            await interaction.response.send_message("Please only submit on a message with exactly one file.", ephemeral = True)
            return
        
        # TODO: Check if the message has already been submitted

        # Send a modal to the user for additional information
        await interaction.response.send_modal(KCSubmissionModal(self.bot, interaction, message))

