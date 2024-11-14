from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import utils.db as db

def reset_progress(team_id, challenge_id):
    progress = db.get_progress(team_id)
    if progress is None:
        progress = {}

    for task in db.get_challenge_tasks(challenge_id):
        if str(challenge_id) not in progress:
            progress[str(challenge_id)] = {}
        progress[str(challenge_id)][str(task)] = 0

class CompleteCoin(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        # Ensure any databases that we need exist

    @commands.has_role("Staff") # Double check roles
    @discord.slash_command(name = "complete_coin", description = "Completes the coin challenge for the given team and resets progress", guild_ids = [int(os.getenv("GUILD_ID"))])
    async def complete_coin(self, interaction, team_name: str):
        # Log the command
        print(f"{interaction.author.nick if interaction.author.nick is not None else interaction.user.name}: /complete_coin {team_name}")
        # Defer the response
        await interaction.response.defer()

        # Get the team ID
        team_id = db.get_team_id(team_name)
        if team_id is None:
            await interaction.followup.send("Team name doesn't exist. Double check spelling", ephemeral = True)
            return

        # Get the team's current tile
        tile = db.get_team_tile(team_id)
        # Get the tile's coin challenge
        coin_challenge = db.get_coin_challenge(tile)
        # Get the team's current coins
        coins = db.get_team_coins(team_id)
        # Get the team's coins gained this tile
        coins_gained = db.get_coins_gained_this_tile(team_id)

        # Check if the coins gained this tile is less than 10
        if coins_gained >= 10:
            await interaction.followup.send("Coin challenge has already been completed twice this tile", ephemeral = True)
            return

        # Add 5 coins to the team's total coins
        db.set_coins(team_id, coins + 5)
        # Add 5 coins to the team's coins gained this tile
        db.set_coins_gained_this_tile(team_id, coins_gained + 5)

        # Reset the team's progress for the coin challenge
        reset_progress(team_id, coin_challenge)

        await interaction.followup.send(f"Coin challenge completed for {team_name}", ephemeral = True)

class CompleteTile(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        # Ensure any databases that we need exist

    @commands.has_role("Staff") # Double check roles
    @discord.slash_command(name = "complete_tile", description = "Completes the tile challenge for the given team and resets progress", guild_ids = [int(os.getenv("GUILD_ID"))])
    async def complete_tile(self, interaction, team_name: str):
        # Log the command
        print(f"{interaction.author.nick if interaction.author.nick is not None else interaction.user.name}: /complete_tile {team_name}")
        # Defer the response
        await interaction.response.defer()

        # Get the team ID
        team_id = db.get_team_id(team_name)
        if team_id is None:
            await interaction.followup.send("Team name doesn't exist. Double check spelling", ephemeral = True)
            return

        # Get the team's current tile
        tile = db.get_team_tile(team_id)
        # Get the tile's Tile challenge
        tile_challenge = db.get_tile_challenge(tile)
        # Get the team's current coins
        coins = db.get_team_coins(team_id)

        # Add 10 coins to the team's total coins
        db.set_coins(team_id, coins + 10)
        # Sets the team's main die to 4
        db.set_main_die_side(team_id, 4)
        # Resets the team's main modifier to 0
        db.set_main_die_modifier(team_id, 0)
        # Resets the team's extra dice to []
        db.set_extra_die_sides(team_id, [])

        # Reset the team's progress for the tile challenge
        reset_progress(team_id, tile_challenge)

        # Set the team able to roll
        db.set_team_ready_to_roll(team_id)
        db.set_team_not_rolling(team_id)

        await interaction.followup.send(f"Tile challenge completed for {team_name}. They are ready to roll with a 4-sided die", ephemeral = True)

class CompleteRegion(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        # Ensure any databases that we need exist

    @commands.has_role("Staff") # Double check roles
    @discord.slash_command(name = "complete_region", description = "Completes the region challenge for the given team and resets progress", guild_ids = [int(os.getenv("GUILD_ID"))])
    async def complete_region(self, interaction, team_name: str):
        # Log the command
        print(f"{interaction.author.nick if interaction.author.nick is not None else interaction.user.name}: /complete_region {team_name}")
        # Defer the response
        await interaction.response.defer()

        # Get the team ID
        team_id = db.get_team_id(team_name)
        if team_id is None:
            await interaction.followup.send("Team name doesn't exist. Double check spelling", ephemeral = True)
            return

        # Get the team's current tile
        tile = db.get_team_tile(team_id)
        # Get the tile's Region challenge
        region_challenge = db.get_region_challenge(tile)
        # Get the team's current coins
        coins = db.get_team_coins(team_id)

        # Add 10 coins to the team's total coins
        db.set_coins(team_id, coins + 40)
        # Sets the team's main die to 8
        db.set_main_die_side(team_id, 8)
        # Resets the team's main modifier to 0
        db.set_main_die_modifier(team_id, 0)
        # Resets the team's extra dice to []
        db.set_extra_die_sides(team_id, [])

        # Reset the team's progress for the region challenge
        reset_progress(team_id, region_challenge)

        # Set the team able to roll
        db.set_team_ready_to_roll(team_id)
        db.set_team_not_rolling(team_id)

        await interaction.followup.send(f"Region challenge completed for {team_name}. They are ready to roll with an 8-sided die", ephemeral = True)

class CompleteGlobal(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        # Ensure any databases that we need exist

    @commands.has_role("Staff") # Double check roles
    @discord.slash_command(name = "complete_global", description = "Completes the global challenge for the given team and resets progress", guild_ids = [int(os.getenv("GUILD_ID"))])
    async def complete_global(self, interaction, team_name: str):
        # Log the command
        print(f"{interaction.author.nick if interaction.author.nick is not None else interaction.user.name}: /complete_global {team_name}")
        # Defer the response
        await interaction.response.defer()

        # Get the team ID
        team_id = db.get_team_id(team_name)
        if team_id is None:
            await interaction.followup.send("Team name doesn't exist. Double check spelling", ephemeral = True)
            return

        # Get the tile's Global challenge
        global_challenge = db.get_global_challenge()
        # Get the team's current coins
        coins = db.get_team_coins(team_id)

        # Add 10 coins to the team's total coins
        db.set_coins(team_id, coins + 80)
        # Sets the team's main die to 12
        db.set_main_die_side(team_id, 12)
        # Resets the team's main modifier to 0
        db.set_main_die_modifier(team_id, 0)
        # Resets the team's extra dice to []
        db.set_extra_die_sides(team_id, [])

        # Reset the team's progress for the global challenge
        reset_progress(team_id, global_challenge)

        # Set the team able to roll
        db.set_team_ready_to_roll(team_id)
        db.set_team_not_rolling(team_id)

        # Choose a new global challenge
        # Give the team an enchanted crystal ball
        db.add_item_to_team(team_id, 14)

        await interaction.followup.send(f"Global challenge completed for {team_name}. They are ready to roll with a 12-sided die.\n\nAn enchanted crystal ball has been added to their inventory as well. YOU MUST IMMEDIATELY USE THIS ITEM TO ROLL A NEW GLOBAL CHALLENGE BECAUSE IM TOO LAZY TO CODE IT UP ON MY END THANKS", ephemeral = True)

class ForceResetRolling(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        # Ensure any databases that we need exist

    @commands.has_role("Staff") # Double check roles
    @discord.slash_command(name = "force_reset_rolling", description = "Forces a team to be able to roll again", guild_ids = [int(os.getenv("GUILD_ID"))])
    async def force_reset_rolling(self, interaction, team_name: str):
        # Log the command
        print(f"{interaction.author.nick if interaction.author.nick is not None else interaction.user.name}: /force_reset_rolling {team_name}")
        # Defer the response
        await interaction.response.defer()

        # Get the team ID
        team_id = db.get_team_id(team_name)
        if team_id is None:
            await interaction.followup.send("Team name doesn't exist. Double check spelling", ephemeral = True)
            return

        db.set_team_ready_to_roll(team_id)
        db.set_team_not_rolling(team_id)

        await interaction.followup.send(f"{team_name} is now able to roll again", ephemeral = True)

class ForceResetNotRolling(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        # Ensure any databases that we need exist

    @commands.has_role("Staff") # Double check roles
    @discord.slash_command(name = "force_reset_not_rolling", description = "Forces a team to not be able to roll again", guild_ids = [int(os.getenv("GUILD_ID"))])
    async def force_reset_not_rolling(self, interaction, team_name: str):
        # Log the command
        print(f"{interaction.author.nick if interaction.author.nick is not None else interaction.user.name}: /force_reset_not_rolling {team_name}")
        # Defer the response
        await interaction.response.defer()

        # Get the team ID
        team_id = db.get_team_id(team_name)
        if team_id is None:
            await interaction.followup.send("Team name doesn't exist. Double check spelling", ephemeral = True)
            return

        db.set_team_not_ready_to_roll(team_id)
        db.set_team_not_rolling(team_id)

        await interaction.followup.send(f"{team_name} is now progressing their tile", ephemeral = True)
