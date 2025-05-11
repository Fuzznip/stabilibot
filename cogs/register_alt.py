from discord.ext import commands
import discord
from dotenv import load_dotenv
load_dotenv()
import os
import requests

class RegisterAlt(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = os.getenv("BACKEND_URL")

    @discord.slash_command(name="register_account", description="Register an alternate account", guild_ids=[int(os.getenv("GUILD_ID"))])
    async def register_alt(self, interaction, alt_name: str):
        print(f"{interaction.user.display_name}: /register_account {alt_name}")
        
        await interaction.response.defer(ephemeral=True)
        
        # Make API call to register alternate account
        discord_id = str(interaction.user.id)
        response = requests.post(
            f"{self.backend_url}/users/{discord_id}/add_alt",
            json={"rsn": alt_name}
        )
        
        if response.status_code in [200, 201]:
            await interaction.followup.send(f"Successfully registered '{alt_name}' as an alternate account.", ephemeral=True)
        else:
            await interaction.followup.send(f"Failed to register alternate account: {response.text}", ephemeral=True)
    
    @discord.slash_command(name="remove_account", description="Remove an alternate account", guild_ids=[int(os.getenv("GUILD_ID"))])
    async def remove_alt(self, interaction, alt_name: str):
        print(f"{interaction.user.display_name}: /remove_account {alt_name}")
        
        await interaction.response.defer(ephemeral=True)
        
        # Make API call to remove alternate account
        discord_id = str(interaction.user.id)
        response = requests.delete(
            f"{self.backend_url}/users/{discord_id}/remove_alt",
            json={"rsn": alt_name}
        )
        
        if response.status_code in [200, 201]:
            await interaction.followup.send(f"Successfully removed '{alt_name}' from your alternate accounts.", ephemeral=True)
        else:
            await interaction.followup.send(f"Failed to remove alternate account: {response.text}", ephemeral=True)

    @discord.slash_command(name="list_accounts", description="List your registered accounts", guild_ids=[int(os.getenv("GUILD_ID"))])
    async def list_accounts(self, interaction):
        print(f"{interaction.user.display_name}: /list_accounts")
        
        await interaction.response.defer(ephemeral=True)
        
        # Make API call to list registered accounts
        discord_id = str(interaction.user.id)
        response = requests.get(
            f"{self.backend_url}/users/{discord_id}/accounts"
        )
        
        if response.status_code == 200:
            alts = response.json()
            if alts:
                alt_list = "\n".join(alts)
                await interaction.followup.send(f"Your registered accounts:\n{alt_list}", ephemeral=True)
            else:
                await interaction.followup.send("You have no registered accounts.", ephemeral=True)
        else:
            await interaction.followup.send(f"Failed to retrieve accounts: {response.text}", ephemeral=True)
                           
def setup(bot):
    bot.add_cog(RegisterAlt(bot))
