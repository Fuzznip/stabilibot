from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import utils.db as db

class AddUser(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        # Ensure any databases that we need exist
        db.ensure_teams_table()
        db.ensure_user_db()

    @commands.has_role("Staff") # Double check roles
    @discord.slash_command(name = "add_user", description = "Adds a user to a team", guild_ids = [int(os.getenv("GUILD_ID"))])
    async def command(self, interaction, team_name: str, username: str):
        # Log the command
        print(f"{interaction.author.nick if interaction.author.nick is not None else interaction.user.name}: /add_user {team_name} {username}")
        # Defer the response
        await interaction.response.defer()

        # Check if the team exists
        if not db.team_exists(team_name):
            # Send deferred response
            await interaction.followup.send("Team doesn't exist", ephemeral = True)
            return

        # Check if the user is linked
        id = db.get_user_from_username(username.lower())
        if id is None:
            await interaction.followup.send("User not linked", ephemeral = True)
            return

        # Check if the user is already in a team
        if db.user_in_team(id):
            await interaction.followup.send(f"User {username} already in a team", ephemeral = True) 
            return

        # Get the list of users linked to the player
        users = db.get_users_from_id(id)

        # Get the role for the team
        role_id = db.get_role_id(team_name)
        role = discord.utils.get(interaction.guild.roles, id = role_id)

        # Give the user the role
        try:
            member = interaction.guild.get_member(int(id))

            await member.add_roles(role)
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral = True)
            return

        # Add the user to the team
        teamId = db.get_team_id(team_name)
        db.add_user_to_team(id, users, teamId)

        await interaction.followup.send(f"Added {username} to {team_name}", ephemeral = True)
