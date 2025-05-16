import discord
from discord.ext import commands
from discord import ui # Pycord uses discord.ui
import os
import aiohttp
import traceback
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

GUILD_ID = int(os.getenv("GUILD_ID"))
DROP_SERVER_URL = os.getenv("DROP_SERVER_URL")
KC_SERVER_URL = os.getenv("KC_SERVER_URL", DROP_SERVER_URL) # Defaults to DROP_SERVER_URL if not set

# --- Modal Definitions (Using InputText and InputTextStyle) ---

class DropSubmissionModal(ui.Modal):
    def __init__(self, bot: commands.Bot, original_message: discord.Message):
        # Remove custom_id to let Pycord auto-generate it
        super().__init__(title="Submit Item Drop", timeout=None)
        self.bot = bot
        self.original_message = original_message # The message with the attachment

        self.questionItemName = ui.InputText( 
            label="What is the name of the drop? (EXACT NAME)",
            style=discord.InputTextStyle.short, 
            placeholder="Scythe of vitur (uncharged)",
            required=True
        )
        self.questionItemSource = ui.InputText( 
            label="Where did you get the drop?",
            style=discord.InputTextStyle.short, 
            placeholder="Theatre of Blood",
            required=True
        )
        self.add_item(self.questionItemName)
        self.add_item(self.questionItemSource)

    async def callback(self, modal_interaction: discord.Interaction):
        """This is the method that gets called when the modal is submitted.
        In Pycord modals, callback is the standard method for handling submissions."""
        print(f"===== DropSubmissionModal callback CALLED for user {modal_interaction.user.id} =====")
        print(f"Modal values - Item name: '{self.questionItemName.value}', Source: '{self.questionItemSource.value}'")
        
        try:
            await modal_interaction.response.defer(ephemeral=True, thinking=True)
            print("Modal interaction deferred successfully")

            payload = {
                "submission_type": "drop",
                "timestamp": self.original_message.created_at.isoformat(),
                "user": self.original_message.author.nick if self.original_message.author.nick is not None else self.original_message.author.name,
                "discord_id": str(self.original_message.author.id),
                "item_name": self.questionItemName.value,
                "source": self.questionItemSource.value,
                "attachment_url": self.original_message.attachments[0].url if self.original_message.attachments else None
            }
            print(f"Drop submission payload prepared: {payload}")

            # Handle API call with proper error handling
            try:
                async with aiohttp.ClientSession() as session:
                    print(f"Sending request to: {DROP_SERVER_URL}/bot")
                    async with session.post(DROP_SERVER_URL + "/bot", json=payload) as response:
                        print(f"Response status: {response.status}")
                        if response.status == 200:
                            data = await response.json()
                            print(f"Success response: {data}")
                            await modal_interaction.followup.send(data.get("message", "Drop submission processed successfully!"), ephemeral=True)
                        else:
                            error_text = await response.text()
                            print(f"Error from server: {response.status} - {error_text}")
                            await modal_interaction.followup.send(f"Error submitting: Server responded with {response.status}. Please try again later.", ephemeral=True)
            except aiohttp.ClientConnectorError as e:
                print(f"ClientConnectorError: {str(e)}")
                await modal_interaction.followup.send(f"Error connecting to submission server: {str(e)}", ephemeral=True)
            except Exception as e:
                print(f"API Error: {str(e)}")
                print(traceback.format_exc())
                await modal_interaction.followup.send(f"An unknown error occurred: {str(e)}", ephemeral=True)
        except Exception as outer_e:
            print(f"Outer Exception: {str(outer_e)}")
            print(traceback.format_exc())
            if not modal_interaction.response.is_done():
                await modal_interaction.response.send_message("Something went wrong with the submission form.", ephemeral=True)
            else:
                await modal_interaction.followup.send("Something went wrong with the submission form.", ephemeral=True)


class KCSubmissionModal(ui.Modal):
    def __init__(self, bot: commands.Bot, original_message: discord.Message):
        # Remove custom_id to let Pycord auto-generate it
        super().__init__(title="Submit Kill Count (KC)", timeout=None)
        self.bot = bot
        self.original_message = original_message

        self.questionBossName = ui.InputText( 
            label="What is the Boss/Monster name?",
            style=discord.InputTextStyle.short, 
            placeholder="General Graardor",
            required=True
        )
        self.questionKillCount = ui.InputText( 
            label="How many KC are you submitting?",
            style=discord.InputTextStyle.short, 
            placeholder="1234",
            required=True
        )
        self.add_item(self.questionBossName)
        self.add_item(self.questionKillCount)

    async def callback(self, modal_interaction: discord.Interaction):
        """This is the method that gets called when the modal is submitted.
        In Pycord modals, callback is the standard method for handling submissions."""
        print(f"===== KCSubmissionModal callback CALLED for user {modal_interaction.user.id} =====")
        print(f"Modal values - Boss: '{self.questionBossName.value}', KC: '{self.questionKillCount.value}'")
        
        try:
            await modal_interaction.response.defer(ephemeral=True, thinking=True)
            print("Modal interaction deferred successfully")

            try:
                kc_value = int(self.questionKillCount.value)
            except ValueError:
                print(f"Invalid KC value: {self.questionKillCount.value}")
                await modal_interaction.followup.send("Kill Count must be a valid number.", ephemeral=True)
                return

            payload = {
                "submission_type": "kc",
                "timestamp": self.original_message.created_at.isoformat(),
                "user": self.original_message.author.nick if self.original_message.author.nick is not None else self.original_message.author.name,
                "discord_id": str(self.original_message.author.id),
                "boss_name": self.questionBossName.value,
                "kill_count": kc_value,
                "attachment_url": self.original_message.attachments[0].url if self.original_message.attachments else None
            }
            print(f"KC submission payload prepared: {payload}")

            # Handle API call with proper error handling
            try:
                async with aiohttp.ClientSession() as session:
                    print(f"Sending request to: {KC_SERVER_URL}/bot")
                    async with session.post(KC_SERVER_URL + "/bot", json=payload) as response:
                        print(f"Response status: {response.status}")
                        if response.status == 200:
                            data = await response.json()
                            print(f"Success response: {data}")
                            await modal_interaction.followup.send(data.get("message", "KC submission processed successfully!"), ephemeral=True)
                        else:
                            error_text = await response.text()
                            print(f"Error from server: {response.status} - {error_text}")
                            await modal_interaction.followup.send(f"Error submitting: Server responded with {response.status}. Please try again later.", ephemeral=True)
            except aiohttp.ClientConnectorError as e:
                print(f"ClientConnectorError: {str(e)}")
                await modal_interaction.followup.send(f"Error connecting to submission server: {str(e)}", ephemeral=True)
            except Exception as e:
                print(f"API Error: {str(e)}")
                print(traceback.format_exc())
                await modal_interaction.followup.send(f"An unknown error occurred: {str(e)}", ephemeral=True)
        except Exception as outer_e:
            print(f"Outer Exception: {str(outer_e)}")
            print(traceback.format_exc())
            if not modal_interaction.response.is_done():
                await modal_interaction.response.send_message("Something went wrong with the submission form.", ephemeral=True)
            else:
                await modal_interaction.followup.send("Something went wrong with the submission form.", ephemeral=True)


# --- View with Ephemeral Buttons (Corrected Edit Logic) ---

class SubmissionTypeView(ui.View):
    def __init__(self, bot: commands.Bot, original_message: discord.Message):
        super().__init__(timeout=180)
        self.bot = bot
        self.original_message = original_message
        # self.message_command_interaction stores the ApplicationContext from the message command
        self.message_command_interaction: discord.ApplicationContext = None 

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not self.message_command_interaction: 
            print(f"Interaction check failed: message_command_interaction is None")
            return False
        
        is_authorized = interaction.user.id == self.message_command_interaction.user.id
        if not is_authorized:
            print(f"Interaction check failed: user {interaction.user.id} != initiator {self.message_command_interaction.user.id}")
        return is_authorized # Check against user from ApplicationContext

    async def _disable_buttons_and_edit_original(self):
        """Helper to disable buttons and attempt to edit the original response."""
        print("Disabling buttons and editing original message")
        for item_in_view in self.children:
            if isinstance(item_in_view, ui.Button):
                item_in_view.disabled = True
        
        if self.message_command_interaction and hasattr(self.message_command_interaction, 'interaction'):
            try:
                # THE FIX: Access original_response() via the .interaction attribute of ApplicationContext
                print("Trying to access message_command_interaction.interaction")
                base_interaction = self.message_command_interaction.interaction
                if base_interaction: # Ensure the base interaction exists
                    print("Found base_interaction, retrieving original response")
                    original_response_message = await base_interaction.original_response()
                    print(f"Got original_response_message, editing with disabled buttons: {original_response_message.id}")
                    await original_response_message.edit(view=self)
                    print("Successfully edited original message")
                else:
                    print("Base interaction not found on ApplicationContext, cannot edit original response.")
            except discord.NotFound:
                print("Original interaction message not found for SubmissionTypeView, skipping edit.")
            except discord.HTTPException as e:
                print(f"Failed to edit original interaction message: {e} (Status: {e.status if hasattr(e, 'status') else 'N/A'})")
            except AttributeError as e: 
                print(f"AttributeError when trying to edit original response: {e}. This might happen if 'base_interaction.original_response()' is not available.")
                print(f"Type of message_command_interaction: {type(self.message_command_interaction)}")
                print(f"Available attributes: {dir(self.message_command_interaction)}")
            except Exception as e:
                print(f"An unexpected error occurred while editing original response: {e}")
                print(traceback.format_exc())
        elif not self.message_command_interaction:
             print("message_command_interaction was not set in SubmissionTypeView.")
        else:
            print(f"message_command_interaction (type: {type(self.message_command_interaction)}) does not have 'interaction' attribute.")
            print(f"Available attributes: {dir(self.message_command_interaction)}")

        self.stop()


    @ui.button(label="Log Item Drop", style=discord.ButtonStyle.success, custom_id="submit_view_drop_button")
    async def drop_button_callback(self, button_object: ui.Button, interaction_from_button_click: discord.Interaction):
        print(f"Drop button clicked by user {interaction_from_button_click.user.id}")
        try:
            # Create a modal instance
            modal = DropSubmissionModal(self.bot, self.original_message)
            # Send the modal
            await interaction_from_button_click.response.send_modal(modal)
            print(f"Drop modal sent successfully with type: {type(modal)}")
            # Disable buttons after modal is sent
            await self._disable_buttons_and_edit_original()
        except Exception as e:
            print(f"Error in drop_button_callback: {str(e)}")
            print(traceback.format_exc())
            await interaction_from_button_click.followup.send("An error occurred while showing the drop submission form.", ephemeral=True)


    @ui.button(label="Log Kill Count", style=discord.ButtonStyle.primary, custom_id="submit_view_kc_button")
    async def kc_button_callback(self, button_object: ui.Button, interaction_from_button_click: discord.Interaction):
        print(f"KC button clicked by user {interaction_from_button_click.user.id}")
        try:
            # Create a modal instance
            modal = KCSubmissionModal(self.bot, self.original_message)
            # Send the modal
            await interaction_from_button_click.response.send_modal(modal)
            print(f"KC modal sent successfully with type: {type(modal)}")
            # Disable buttons after modal is sent
            await self._disable_buttons_and_edit_original()
        except Exception as e:
            print(f"Error in kc_button_callback: {str(e)}")
            print(traceback.format_exc())
            await interaction_from_button_click.followup.send("An error occurred while showing the KC submission form.", ephemeral=True)

# --- Cog Definition ---

class SubmitCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # For Pycord, ensure this decorator is correct for your version.
    # It might be discord.app_commands.message_command or just discord.message_command
    @discord.message_command(name="Submit Image for Event", guild_ids=[GUILD_ID]) 
    async def submit_image_entry(self, app_context: discord.ApplicationContext, message: discord.Message):
        print(f"Submit Image for Event command invoked by {app_context.user.id}")
        # app_context is the ApplicationContext from the message command
        if not message.attachments or len(message.attachments) == 0:
            print("No image attachments found in the selected message")
            await app_context.response.send_message("The selected message must have an image attachment.", ephemeral=True)
            return
        if len(message.attachments) > 1:
            print(f"Multiple attachments found: {len(message.attachments)}")
            await app_context.response.send_message("This submission handles only the first image if multiple are attached.", ephemeral=True)

        view = SubmissionTypeView(self.bot, message)
        view.message_command_interaction = app_context # Store the ApplicationContext
        print(f"Created SubmissionTypeView and assigned message_command_interaction")
        
        try:
            await app_context.response.send_message("What type of submission is this for the attached image?", view=view, ephemeral=True)
            print("Initial view sent successfully")
        except Exception as e:
            print(f"Error sending initial view: {str(e)}")
            print(traceback.format_exc())
            await app_context.response.send_message("An error occurred while creating the submission dialog.", ephemeral=True)

def setup(bot: commands.Bot):
    bot.add_cog(SubmitCog(bot))
    print("SubmitCog loaded successfully")
