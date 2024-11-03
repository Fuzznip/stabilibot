from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import utils.db as db

class RenameTeam(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        # Ensure any databases that we need exist
        db.ensure_teams_table()

    @commands.has_role("Staff")
    @discord.slash_command(name = "rename_team", description = "Renames a team and their channels", guild_ids = [int(os.getenv("GUILD_ID"))])
    async def command(self, interaction, team: str, new_name: str):
        # Log the command
        print(f"{interaction.author.nick if interaction.author.nick is not None else interaction.user.name}: /command {team} {new_name}")

        # Defer the response
        await interaction.response.defer()

        # Check if the team exists
        if not db.team_exists(team):
            # Send deferred response
            await interaction.followup.send("Team doesn't exist", ephemeral = True)
            return

        # Check if the new name is already in use
        if db.team_exists(new_name):
            await interaction.followup.send("New team name already in use", ephemeral = True)
            return

        # Get the role for the team
        role_id = db.get_role_id(team)
        role = discord.utils.get(interaction.guild.roles, id = role_id)
        # Rename the role
        try:
            await role.edit(name = new_name)
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral = True)
            return

        # Get the text channel for the team
        channel_id = db.get_text_channel_id(team)
        channel = discord.utils.get(interaction.guild.text_channels, id = channel_id)
        # Rename the text channel
        try:
            await channel.edit(name = new_name)
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral = True)
            return

        # Get the voice channel for the team
        voice_channel_id = db.get_voice_channel_id(team)
        voice_channel = discord.utils.get(interaction.guild.voice_channels, id = voice_channel_id)
        # Rename the voice channel
        try:
            await voice_channel.edit(name = new_name)
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral = True)
            return

        # Rename the team
        try:
            db.rename_team(team, new_name)
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral = True)
            return

        await interaction.followup.send(f"Successfully renamed team {team} to {new_name}", ephemeral = True)

