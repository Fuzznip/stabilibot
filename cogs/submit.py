import discord
from discord.ext import commands
from discord import ui # Pycord uses discord.ui
import os
import aiohttp
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

GUILD_ID = int(os.getenv("GUILD_ID"))
DROP_SERVER_URL = os.getenv("DROP_SERVER_URL")
KC_SERVER_URL = os.getenv("KC_SERVER_URL", DROP_SERVER_URL) # Defaults to DROP_SERVER_URL if not set

# --- Modal Definitions (Using InputText and InputTextStyle) ---

class DropSubmissionModal(ui.Modal):
    def __init__(self, bot: commands.Bot, original_message: discord.Message):
        super().__init__(title="Submit Item Drop", timeout=None, custom_id="drop_submit_form_modal")
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

    async def on_submit(self, modal_interaction: discord.Interaction):
        await modal_interaction.response.defer(ephemeral=True, thinking=True)

        payload = {
            "submission_type": "drop",
            "timestamp": self.original_message.created_at.isoformat(),
            "user": self.original_message.author.nick if self.original_message.author.nick is not None else self.original_message.author.name,
            "discord_id": str(self.original_message.author.id),
            "item_name": self.questionItemName.value,
            "source": self.questionItemSource.value,
            "attachment_url": self.original_message.attachments[0].url if self.original_message.attachments else None
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(DROP_SERVER_URL, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        await modal_interaction.followup.send(data.get("message", "Drop submission processed successfully!"), ephemeral=True)
                    else:
                        error_text = await response.text()
                        print(f"Error from drop server: {response.status} - {error_text}")
                        await modal_interaction.followup.send(f"Error submitting drop: Server responded with {response.status}. Please try again later.", ephemeral=True)
        except aiohttp.ClientConnectorError as e:
            print(f"Drop Submission - ClientConnectorError: {str(e)}")
            await modal_interaction.followup.send(f"Error connecting to submission server: {str(e)}", ephemeral=True)
        except Exception as e:
            print(f"Drop Submission - Unknown Error: {str(e)}")
            await modal_interaction.followup.send(f"An unknown error occurred during submission: {str(e)}", ephemeral=True)

    async def on_error(self, error: Exception, interaction: discord.Interaction) -> None:
        print(f"Error in DropSubmissionModal: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message("Oops! Something went wrong with the drop submission form.", ephemeral=True)
        else:
            await interaction.followup.send("Oops! Something went wrong with the drop submission form.", ephemeral=True)


class KCSubmissionModal(ui.Modal):
    def __init__(self, bot: commands.Bot, original_message: discord.Message):
        super().__init__(title="Submit Kill Count (KC)", timeout=None, custom_id="kc_submit_form_modal")
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

    async def on_submit(self, modal_interaction: discord.Interaction):
        await modal_interaction.response.defer(ephemeral=True, thinking=True)

        try:
            kc_value = int(self.questionKillCount.value)
        except ValueError:
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

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(KC_SERVER_URL, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        await modal_interaction.followup.send(data.get("message", "KC submission processed successfully!"), ephemeral=True)
                    else:
                        error_text = await response.text()
                        print(f"Error from KC server: {response.status} - {error_text}")
                        await modal_interaction.followup.send(f"Error submitting KC: Server responded with {response.status}. Please try again later.", ephemeral=True)
        except aiohttp.ClientConnectorError as e:
            print(f"KC Submission - ClientConnectorError: {str(e)}")
            await modal_interaction.followup.send(f"Error connecting to submission server: {str(e)}", ephemeral=True)
        except Exception as e:
            print(f"KC Submission - Unknown Error: {str(e)}")
            await modal_interaction.followup.send(f"An unknown error occurred during submission: {str(e)}", ephemeral=True)

    async def on_error(self, error: Exception, interaction: discord.Interaction) -> None:
        print(f"Error in KCSubmissionModal: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message("Oops! Something went wrong with the KC submission form.", ephemeral=True)
        else:
            await interaction.followup.send("Oops! Something went wrong with the KC submission form.", ephemeral=True)


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
            return False
        return interaction.user.id == self.message_command_interaction.user.id # Check against user from ApplicationContext

    async def _disable_buttons_and_edit_original(self):
        """Helper to disable buttons and attempt to edit the original response."""
        for item_in_view in self.children:
            if isinstance(item_in_view, ui.Button):
                item_in_view.disabled = True
        
        if self.message_command_interaction and hasattr(self.message_command_interaction, 'interaction'):
            try:
                # THE FIX: Access original_response() via the .interaction attribute of ApplicationContext
                base_interaction = self.message_command_interaction.interaction
                if base_interaction: # Ensure the base interaction exists
                    original_response_message = await base_interaction.original_response()
                    await original_response_message.edit(view=self)
                else:
                    print("Base interaction not found on ApplicationContext, cannot edit original response.")
            except discord.NotFound:
                print("Original interaction message not found for SubmissionTypeView, skipping edit.")
            except discord.HTTPException as e:
                print(f"Failed to edit original interaction message: {e} (Status: {e.status if hasattr(e, 'status') else 'N/A'})")
            except AttributeError as e: 
                print(f"AttributeError when trying to edit original response: {e}. This might happen if 'base_interaction.original_response()' is not available.")
            except Exception as e:
                print(f"An unexpected error occurred while editing original response: {e}")
        elif not self.message_command_interaction:
             print("message_command_interaction was not set in SubmissionTypeView.")
        else:
            print(f"message_command_interaction (type: {type(self.message_command_interaction)}) does not have 'interaction' attribute.")

        self.stop()


    @ui.button(label="Log Item Drop", style=discord.ButtonStyle.success, custom_id="submit_view_drop_button")
    async def drop_button_callback(self, button_object: ui.Button, interaction_from_button_click: discord.Interaction):
        await interaction_from_button_click.response.send_modal(DropSubmissionModal(self.bot, self.original_message))
        await self._disable_buttons_and_edit_original()


    @ui.button(label="Log Kill Count", style=discord.ButtonStyle.primary, custom_id="submit_view_kc_button")
    async def kc_button_callback(self, button_object: ui.Button, interaction_from_button_click: discord.Interaction):
        await interaction_from_button_click.response.send_modal(KCSubmissionModal(self.bot, self.original_message))
        await self._disable_buttons_and_edit_original()

# --- Cog Definition ---

class SubmitCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # For Pycord, ensure this decorator is correct for your version.
    # It might be discord.app_commands.message_command or just discord.message_command
    @discord.message_command(name="Submit Image for Event", guild_ids=[GUILD_ID]) 
    async def submit_image_entry(self, app_context: discord.ApplicationContext, message: discord.Message):
        # app_context is the ApplicationContext from the message command
        if not message.attachments or len(message.attachments) == 0:
            await app_context.response.send_message("The selected message must have an image attachment.", ephemeral=True)
            return
        if len(message.attachments) > 1:
            await app_context.response.send_message("This submission handles only the first image if multiple are attached.", ephemeral=True)

        view = SubmissionTypeView(self.bot, message)
        view.message_command_interaction = app_context # Store the ApplicationContext
        await app_context.response.send_message("What type of submission is this for the attached image?", view=view, ephemeral=True)
