from discord.ext import commands
import discord
import requests
import os

class Rename(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(name="namechange", description="Update your OSRS username", guild_ids=[int(os.getenv("GUILD_ID"))])
    async def namechange(self, interaction, new_name: str):
        print(f"{interaction.user.display_name}: /namechange {new_name}")

        # Update the name in the backend
        try:
            url = f"{os.getenv('BACKEND_URL')}/users/{interaction.user.id}/rename"
            payload = {"runescape_name": new_name}
            headers = {"Content-Type": "application/json"}
            response = requests.put(url, json=payload, headers=headers)

            if response.status_code == 200:
                await interaction.response.send_message(f"Username updated to {new_name}", ephemeral=True)
            else:
                await interaction.response.send_message(f"Error updating username: {response.status_code} - {response.text}", ephemeral=True)
                print(f"Error updating username: {response.status_code} - {response.text}")
        except Exception as e:
            await interaction.response.send_message(f"Error updating username: {e}", ephemeral=True)
            print(f"Error updating username: {e}")

def setup(bot):
    bot.add_cog(Rename(bot))
