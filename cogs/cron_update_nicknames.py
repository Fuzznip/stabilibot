import discord
from discord.ext import commands, tasks
import requests
import os

class UpdateNicknames(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_usernames.start()

    @tasks.loop(hours=24)
    async def check_usernames(self):
        guild = self.bot.get_guild(int(os.getenv("GUILD_ID")))
        if not guild:
            print("Guild not found")
            return

        # Fetch user data from the backend
        try:
            url = os.getenv("BACKEND_URL") + "/users"
            response = requests.get(url)
            if response.status_code != 200:
                print(f"Error fetching user data: {response.status_code} - {response.text}")
                return
            user_data = response.json()
        except Exception as e:
            print(f"Error fetching user data: {e}")
            return

        # Map user IDs to their OSRS usernames and previous names
        user_map = {
            str(user["discord_id"]): {
                "current_name": user["runescape_name"],
                "previous_names": user.get("previous_names", [])
            }
            for user in user_data
        }

        # Loop through members with the "Member" role
        role = discord.utils.get(guild.roles, name="Member")
        if not role:
            print("Member role not found")
            return

        for member in role.members:
            user_info = user_map.get(str(member.id))
            if not user_info:
                continue

            current_name = user_info["current_name"]
            previous_names = user_info["previous_names"]
            current_nick = member.nick or member.name

            # Check if any previous name is in the current nickname
            matched_previous_name = next((name for name in previous_names if name in current_nick), None)

            if matched_previous_name:
                # Replace the matched previous name with the current name
                new_nick = current_nick.replace(matched_previous_name, current_name)
            elif current_name not in current_nick:
                # If no match, prepend the current name to the nickname
                new_nick = f"{current_name}"
            else:
                # No changes needed
                continue

            try:
                old_nick = member.nick if member.nick else member.name
                await member.edit(nick=new_nick)
                print(f"Updated nickname for {old_nick} to {new_nick}")
            except discord.errors.Forbidden:
                print(f"Bot does not have permission to change nickname for {member.display_name}")

    @check_usernames.before_loop
    async def before_check_usernames(self):
        await self.bot.wait_until_ready()
