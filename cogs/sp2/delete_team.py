from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import utils.db as db

class DeleteTeam(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        db.ensure_teams_table()

    @commands.has_role("Staff")
    @discord.slash_command(name = "delete_team", description = "deletes a team", guild_ids = [int(os.getenv("GUILD_ID"))])
    async def delete_team(self, interaction, team_name: str):
        # Log the command
        print(f"{interaction.author.nick if interaction.author.nick is not None else interaction.user.name}: /delete_team {team_name}")
        
        # Defer the response
        await interaction.response.defer()

        # Check if the team name is already in use
        if not db.team_exists(team_name):
            await interaction.followup.send("Team name doesn't exist", ephemeral = True)
            return

        # delete the role for the team
        role_id = db.get_role_id(team_name)
        print(role_id)
        role = discord.utils.get(interaction.guild.roles, id = role_id)
        try:
            await role.delete()
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral = True)
            return

        # delete the text channel for the team under the "events" category
        channel_id = db.get_text_channel_id(team_name)
        print(channel_id)
        channel = discord.utils.get(interaction.guild.text_channels, id = channel_id)
        try:
            await channel.delete()
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral = True)
            return

        # delete the voice channel for the team under the "events" category
        voice_channel_id = db.get_voice_channel_id(team_name)
        print(voice_channel_id)
        voice_channel = discord.utils.get(interaction.guild.voice_channels, id = voice_channel_id)
        try:
            await voice_channel.delete()
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral = True)

        # delete the team
        try:
            #TODO: Backup team data through a message or log before deleting the team in case someone accidentally does this and wants it reverted
            #TODO: OR we can just mark the team as "deleted" and keep in database anyways
            db.delete_team(team_name)
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral = True)
            return

        await interaction.followup.send(f"Succesfully deleted team {team_name}", ephemeral = True)
        pass
