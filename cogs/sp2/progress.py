from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import utils.db as db

class Progress(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        # Ensure any databases that we need exist
        db.ensure_teams_table()
        db.ensure_tiles_db()

    def get_progress(self, team, challenge, task):
        progress = db.get_progress(team)
        print(progress)
        if progress is None:
            return 0

        return progress[str(challenge)][str(task)] if str(challenge) in progress and str(task) in progress[str(challenge)] else 0

    def add_progress_embed(self, challenge_type, embeds, team, challenge):
        # Get the challenge name and description
        challenge_name = db.get_challenge_name(challenge)
        challenge_description = db.get_challenge_description(challenge)
        # Create the embed
        challenge_embed = discord.Embed(title = f"{ challenge_type } Challenge: { challenge_name }", description = challenge_description)
        # Get the tasks for the challenge
        tasks = db.get_challenge_tasks(challenge)
        # Add the tasks to the embed
        for task in tasks:
            # Get the triggers for the task
            triggers = db.get_task_triggers(task)
            triggerList = []
            for trigger in triggers:
                # Get the trigger and the source
                trigger, source = db.get_trigger_and_source(trigger)
                # If the source is empty, this is a general trigger
                if source is None:
                    triggerList.append(trigger)
                # If the trigger and source are the same, this is a KC trigger
                elif trigger == source:
                    triggerList.append(trigger + " KC")
                # If the trigger and source are different, this is a specific source trigger
                else:
                    triggerList.append(f"{trigger} from {source}")

            # Add the task to the embed
            challenge_embed.add_field(name = "Get " + " OR ".join(triggerList), value = f"{self.get_progress(team, challenge, task)} / {db.get_task_quantity(task)}", inline = False)
        # Add the embed to the list of embeds
        embeds.append(challenge_embed)

    @discord.slash_command(name = "progress", description = "Shows your team's progress through your current tile!", guild_ids = [int(os.getenv("GUILD_ID"))])
    async def progress(self, interaction):
        # Log the command
        print(f"{interaction.author.nick if interaction.author.nick is not None else interaction.user.name}: /progress")
        # Defer the response
        await interaction.response.defer()

        # Get the team ID
        team_id = db.get_team(str(interaction.author.id))
        if team_id is None:
            await interaction.followup.send("You are not on a team!", ephemeral = True)
            return

        # Get the team's current tile
        tile = db.get_team_tile(team_id)

        # Get the team's current stars
        stars = db.get_team_stars(team_id)
        # Get the team's current coins
        coins = db.get_team_coins(team_id)
        # Get the team's current items
        items = db.get_team_items(team_id)

        ready = db.is_team_ready_to_roll(team_id) or db.is_team_rolling(team_id)

        if ready:
            message = f"{db.get_team_name(team_id)}'s progress:\n"
        else:
            message = f"{db.get_team_name(team_id)}'s progress through {db.get_tile_name(tile)}:\n"
        message += f":star: Stars: {stars}\n"
        message += f":coin: Coins: {coins}\n"
        if len(items) > 0:
            itemNames = []
            for item in items:
                itemNames.append(str(db.get_item_name(item)))
            message += f":shopping_bags: Items: { ', '.join(itemNames) }\n"

        # Check if the team is ready to roll or not
        if ready:
            message += "Your team is done with your tile and is ready to roll!"
            await interaction.followup.send(message, ephemeral = True)
            return

        # Get the coin task for the tile
        coin_challenge = db.get_coin_challenge(tile)
        # Get the tile task for the tile
        tile_challenge = db.get_tile_challenge(tile)
        # Get the region task for the tile
        region_challenge = db.get_region_challenge(tile)
        # Get the global task
        global_challenge = db.get_global_challenge()

        embeds = []
        if coin_challenge != -1:
            self.add_progress_embed("Coin", embeds, team_id, coin_challenge)
        if tile_challenge != -1:
            self.add_progress_embed("Tile", embeds, team_id, tile_challenge)
        if region_challenge != -1:
            self.add_progress_embed("Region", embeds, team_id, region_challenge)
        if global_challenge != -1:
            self.add_progress_embed("Global", embeds, team_id, global_challenge)

        # Send the message
        await interaction.followup.send(message, embeds = embeds)

