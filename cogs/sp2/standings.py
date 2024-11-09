from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import utils.db as db

class Standings(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        # Ensure any databases that we need exist

    @discord.slash_command(name = "standings", description = "Shows the current standings of the event", guild_ids = [int(os.getenv("GUILD_ID"))])
    async def standings(self, interaction):
        # Log the command
        print(f"{interaction.author.nick if interaction.author.nick is not None else interaction.user.name}: /standings")
        # Defer the response
        await interaction.response.defer()
        # Get each team
        teams = db.get_teams()
        # Sort the teams by stars (tuple index 4), tiebreak by coins (tuple index 5)
        teams.sort(key = lambda x: (x[4], x[5]), reverse = True)
        # Create the embed
        standings_embed = discord.Embed(title = "Standings")
        # Add each team to the embed
        for i, team in enumerate(teams):
            team_name = team[1]
            stars = team[4]
            coins = team[5]
            current_tile_name = db.get_tile_name(team[3])

            if i == 0:
                standings_embed.add_field(name = f":first_place: {team_name}", value = f":star: Stars: {stars}\n:coin: Coins: {coins}\nCurrent Tile: {current_tile_name}", inline = False)
            elif i == 1:
                standings_embed.add_field(name = f":second_place: {team_name}", value = f":star: Stars: {stars}\n:coin: Coins: {coins}\nCurrent Tile: {current_tile_name}", inline = False)
            elif i == 2:
                standings_embed.add_field(name = f":third_place: {team_name}", value = f":star: Stars: {stars}\n:coin: Coins: {coins}\nCurrent Tile: {current_tile_name}", inline = False)
            else:
                standings_embed.add_field(name = f"{i + 1}. {team_name}", value = f":star: Stars: {stars}\n:coin: Coins: {coins}\nCurrent Tile: {current_tile_name}", inline = False)

        # Send the embed
        await interaction.followup.send(embed = standings_embed)
