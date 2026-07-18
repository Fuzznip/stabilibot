from discord.ext import commands
from discord import ui
import discord

from dotenv import load_dotenv
load_dotenv()
import os
import json

import aiohttp

# Discord StringSelect menus have a hard cap of 25 options, so the search
# results shown at once are limited to this. Users narrow further via "Search again".
MAX_SELECT_OPTIONS = 25


async def fetch_drop_triggers():
    """Fetch the current DROP-trigger whitelist from the backend.

    Returns a list of "Item:Source" (or bare "Item") strings. Returns None when
    the whitelist can't be loaded (no active event -> 404, or the server is down).
    """
    url = os.getenv("BACKEND_URL") + "/events/whitelist"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={"Accept": "application/json"}) as response:
                if response.status != 200:
                    print(f"Whitelist fetch failed: {response.status}")
                    return None
                data = await response.json()
                return data.get("triggers", [])
    except Exception as e:
        print(f"Error fetching whitelist: {e}")
        return None


def split_trigger(trigger: str):
    """"Tanzanite fang:Zulrah" -> ("Tanzanite fang", "Zulrah"); "Dom" -> ("Dom", "")."""
    if ":" in trigger:
        item_name, source = trigger.split(":", 1)
        return item_name, source
    return trigger, ""


async def submit_drop_payload(interaction, payload):
    """POST a completed drop submission to the drop server and report the result."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(os.getenv("DROP_SERVER_URL") + "/bot", json=payload) as response:
                if response.status != 200:
                    print(response.status)
                    print(json.dumps(payload, indent=4))
                    print(os.getenv("DROP_SERVER_URL") + "/bot")
                    await interaction.followup.send("Error submitting file.", ephemeral=True)
                    return
                print(f"Submission successful: {response.status}")
                print(await response.text())
                data = await response.json()
                await interaction.followup.send(data["message"], ephemeral=True)
                return
    except aiohttp.ClientConnectorError as e:
        print(str(e))
        await interaction.followup.send(f"Error connecting to server: {str(e)}", ephemeral=True)
        return
    except Exception:
        await interaction.followup.send("Unknown Error", ephemeral=True)
        return


class SearchAgainButton(ui.Button):
    """Re-opens the search modal, keeping the same screenshot and quantity."""
    def __init__(self, bot, message, quantity):
        super().__init__(label="Search again", style=discord.ButtonStyle.secondary)
        self.bot = bot
        self.message = message
        self.quantity = quantity

    async def callback(self, interaction):
        await interaction.response.send_modal(DropSearchModal(self.bot, self.message, self.quantity))


class TriggerSelectView(ui.View):
    """Ephemeral dropdown of the triggers that matched the user's search."""
    def __init__(self, bot, message, triggers, quantity):
        super().__init__(timeout=300)
        self.bot = bot
        self.message = message
        self.quantity = quantity

        options = []
        for trigger in triggers:
            item_name, source = split_trigger(trigger)
            options.append(discord.SelectOption(
                label=item_name[:100],
                description=(f"Source: {source}" if source else "No source")[:100],
                value=trigger[:100],
            ))

        self.trigger_select = discord.ui.Select(
            placeholder="Choose the drop...",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.trigger_select.callback = self.trigger_selected
        self.add_item(self.trigger_select)
        self.add_item(SearchAgainButton(bot, message, quantity))

    async def trigger_selected(self, interaction):
        await interaction.response.defer(ephemeral=True)
        trigger = self.trigger_select.values[0]
        item_name, source = split_trigger(trigger)
        payload = {
            "submission_type": "drop",
            "timestamp": self.message.created_at.isoformat(),
            "user": self.message.author.display_name,
            "discord_id": str(self.message.author.id),
            "item_name": item_name,
            "source": source,
            "quantity": self.quantity,
            "attachment_url": self.message.attachments[0].url,  # guaranteed exactly one attachment
        }
        await submit_drop_payload(interaction, payload)


class DropSearchModal(ui.Modal):
    """Step 1: capture a search term + quantity. A modal (not autocomplete) so the
    flow stays bound to the right-clicked screenshot message."""
    def __init__(self, bot: commands.Bot, message: discord.Message, quantity_default: str = "1"):
        super().__init__(title="Submit Drop", timeout=None)
        self.bot = bot
        self.message = message

        self.search_input = discord.ui.InputText(
            label="Search for the drop",
            style=discord.InputTextStyle.short,
            placeholder="e.g. vestige, tassets, fang",
            required=True,
        )
        self.quantity_input = discord.ui.InputText(
            label="How many of this item are you submitting?",
            style=discord.InputTextStyle.short,
            placeholder="1",
            required=False,
            value=quantity_default,
        )
        self.add_item(self.search_input)
        self.add_item(self.quantity_input)

    async def callback(self, interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        query = (self.search_input.value or "").strip()
        quantity = (self.quantity_input.value or "1").strip() or "1"

        triggers = await fetch_drop_triggers()
        if triggers is None:
            await interaction.followup.send(
                "Couldn't load the drop whitelist (no active event, or the server is unavailable). Try again shortly.",
                ephemeral=True,
            )
            return
        if not triggers:
            await interaction.followup.send(
                "There are no drop triggers configured for the current event.",
                ephemeral=True,
            )
            return

        matches = sorted((t for t in triggers if query.lower() in t.lower()), key=str.lower)
        if not matches:
            await interaction.followup.send(
                f"No triggers matched \"{query}\". Try a different search term.",
                view=SearchAgainView(self.bot, self.message, quantity),
                ephemeral=True,
            )
            return

        total = len(matches)
        shown = matches[:MAX_SELECT_OPTIONS]
        content = f"Select the drop you're submitting for **{self.message.author.display_name}**:"
        if total > MAX_SELECT_OPTIONS:
            content += (
                f"\n_Showing {MAX_SELECT_OPTIONS} of {total} matches "
                "— hit **Search again** with a narrower term if you don't see it._"
            )

        await interaction.followup.send(
            content,
            view=TriggerSelectView(self.bot, self.message, shown, quantity),
            ephemeral=True,
        )


class SearchAgainView(ui.View):
    """Shown when a search returns no matches — just a button to try again."""
    def __init__(self, bot, message, quantity):
        super().__init__(timeout=300)
        self.add_item(SearchAgainButton(bot, message, quantity))


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

        # Send the search modal; the whole flow stays tied to this screenshot message
        await interaction.response.send_modal(DropSearchModal(self.bot, message))

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
            "user": self.message.author.display_name,
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
