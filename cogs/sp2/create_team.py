from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import utils.db as db

class CreateTeam(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        db.ensure_teams_table()

    @commands.has_role("Staff")
    @discord.slash_command(name = "create_team", description = "creates a team", guild_ids = [int(os.getenv("GUILD_ID"))])
    async def create_team(self, interaction, team_name: str):
        # Log the command
        print(f"{interaction.author.nick if interaction.author.nick is not None else interaction.user.name}: /create_team {team_name}")

        # Defer the response
        await interaction.response.defer()

        # Check if the team name is already in use
        if db.team_exists(team_name):
            await interaction.followup.send("Team name already in use", ephemeral = True)
            return

        # Create a role for the team
        try:
            role = await interaction.guild.create_role(name = team_name)
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral = True)
            return

        # Create a text channel for the team under the "events" category
        category = discord.utils.get(interaction.guild.categories, name = "Events")
        try:
            channel = await interaction.guild.create_text_channel(team_name, category = category)
            # Only allow the team role to see the channel
            await channel.set_permissions(role, read_messages = True, send_messages = True)

            # Do not allow @everyone to see the channel
            await channel.set_permissions(interaction.guild.default_role, read_messages = False)
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral = True)
            return

        # Create a voice channel for the team under the "events" category
        try:
            voice_channel = await interaction.guild.create_voice_channel(team_name, category = category)
            # Only allow the team role to see the channel
            await voice_channel.set_permissions(role, connect = True, speak = True)

            # Do not allow @everyone to see the channel
            await voice_channel.set_permissions(interaction.guild.default_role, connect = False)
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral = True)
            return

        # Create the team
        try:
            db.create_team(team_name, role.id, channel.id, voice_channel.id)
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral = True)
            return

        await interaction.followup.send(f"Succesfully created team {team_name}", ephemeral = True)
