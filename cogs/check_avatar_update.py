import discord
from discord.ext import commands
import os
import requests
from backend import BACKEND_HEADERS

class CheckAvatarUpdate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        # Check if the avatar has changed
        if before.avatar != after.avatar:
            requests.put(
                os.getenv("BACKEND_URL") + f"/users/{after.id}",
                headers=BACKEND_HEADERS,
                json={
                    "discord_avatar_url": after.avatar.url,
                }
            )

async def setup(bot):
    await bot.add_cog(CheckAvatarUpdate(bot))
