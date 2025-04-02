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
                # Set the user's name in discord
                guild = interaction.guild
                member = guild.get_member(interaction.user.id)
                if member:
                    current_nick = member.nick or member.name
                    previous_names = response.json().get("previous_names", [])

                    # Check if any previous name is in the current nickname
                    matched_previous_name = next((name for name in previous_names if name.lower() in current_nick.lower()), None)

                    if matched_previous_name:
                        # Replace the matched previous name with the new name
                        new_nick = current_nick.replace(matched_previous_name, new_name)
                    elif new_name.lower() not in current_nick.lower():
                        # If no match, prepend the new name to the nickname
                        new_nick = f"{new_name}"
                    else:
                        # No changes needed
                        new_nick = current_nick

                    try:
                        old_nick = member.nick if member.nick else member.name
                        await member.edit(nick=new_nick)
                        print(f"Updated nickname for {old_nick} to {new_nick}")
                    except discord.errors.Forbidden:
                        print(f"Bot does not have permission to change nickname for {member.display_name}")
                else:
                    print(f"Member not found in guild: {interaction.user.id}")
            else:
                await interaction.response.send_message(f"Error updating username: {response.status_code} - {response.text}", ephemeral=True)
                print(f"Error updating username: {response.status_code} - {response.text}")
        except Exception as e:
            await interaction.response.send_message(f"Error updating username: {e}", ephemeral=True)
            print(f"Error updating username: {e}")

def setup(bot):
    bot.add_cog(Rename(bot))
