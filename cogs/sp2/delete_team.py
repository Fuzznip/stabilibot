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
            # 1	Kevin's Kittens	-1	-1	8	45	{}	{}	{}	{"2": {"1": 0}, "3": {"2": 0}, "4": {"3": 0}, "5": {"4": 1}, "6": {"5": 0}, "7": {"6": 0}, "8": {"7": 0}, "9": {"8": 1}, "10": {"9": 0}, "11": {"10": 2}, "14": {"16": 890}, "15": {"17": 0, "83": 1}, "18": {"22": 0}, "20": {"24": 0}, "21": {"25": 0, "26": 0}, "27": {"33": 0}, "29": {"36": 0}, "30": {"37": 0, "38": 0}, "31": {"39": 0, "40": 0, "41": 0}, "32": {"42": 0}, "36": {"47": 0, "48": 0}, "37": {"41": 0, "49": 0}, "39": {"21": 0, "41": 0, "44": 0}, "40": {"51": 0}, "41": {"52": 0}, "44": {"54": 0}, "45": {"55": 0}, "47": {"58": 0, "61": 0}, "48": {"59": 0}, "52": {"64": 0, "83": 0}, "55": {"68": 0}, "57": {"69": 1}, "58": {"70": 0}, "59": {"71": 193}, "62": {"73": 0, "74": 0}, "63": {"75": 0, "76": 0}, "64": {"78": 0, "90": 0}, "66": {"77": 0}, "69": {"80": 4}, "70": {"84": 0}, "78": {"108": 0}, "81": {"105": 0}, "87": {"98": 0}, "90": {"95": 0}, "92": {"93": 7}}	false	8	0	{}	1302701969076523048	1302701970154455091	1302701973661024467	lunch.png	0	false	false	
            
            # Go through all users on the team and remove them from the team
            team_id = db.get_team_id(team_name)
            all_users = db.get_all_users()
            print(all_users)
            for user in all_users:
                if user[2] == team_id:
                    print(f"Removing {user[0]}: {','.join(user[1])} from team {team_name}")
                    db.remove_user_from_team(user[0])

            db.delete_team(team_name)

        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral = True)
            return

        await interaction.followup.send(f"Succesfully deleted team {team_name}", ephemeral = True)
        pass
