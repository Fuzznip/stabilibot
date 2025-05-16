from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

from fastapi import FastAPI
from threading import Thread
import uvicorn
import asyncio

intents = discord.Intents.all()
intents.message_content = True
intents.members = True

client = discord.Client(intents = intents)

from cogs.api_server import Api
from cogs.apply import Apply
from cogs.check_avatar_update import CheckAvatarUpdate
from cogs.gear import Gear
from cogs.submit import Submit, SubmitKC
from cogs.rename import Rename
from cogs.cron_update_nicknames import UpdateNicknames
from cogs.event_mod import EventMod
from cogs.event_user import EventUser
from cogs.register_alt import RegisterAlt

class Stabilibot(commands.Bot):
  def __init__(self):
    super().__init__(intents = intents)
    self.app = FastAPI()

  async def on_ready(self):
    print(f"Logged in as {self.user}")
  
  async def on_message(self, message):
    if message.author == self.user:
      return
    await self.process_commands(message)

  async def on_application_command_error(self, context: commands.Context, exception: commands.CommandError) -> None:
    print("Error!:", exception)

    await super().on_application_command_error(context, exception)

bot = Stabilibot()
bot.add_cog(Api(bot))
bot.add_cog(Apply(bot))
bot.add_cog(CheckAvatarUpdate(bot))
bot.add_cog(Gear(bot))
bot.add_cog(Submit(bot))
bot.add_cog(SubmitKC(bot))
bot.add_cog(Rename(bot))
bot.add_cog(UpdateNicknames(bot))
bot.add_cog(EventMod(bot))
bot.add_cog(EventUser(bot))
bot.add_cog(RegisterAlt(bot))

bot.run(os.getenv("TOKEN"))
