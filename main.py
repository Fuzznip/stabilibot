from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

intents = discord.Intents.all()
intents.message_content = True
intents.members = True

client = discord.Client(intents = intents)

from cogs.apply import Apply
from cogs.gear import Gear
from cogs.submit import Submit
from cogs.accounts import Accounts
from cogs.link import Link
from cogs.unlink import Unlink
from cogs.add_link import AddLink
from cogs.message_listener import MessageListener

class Stabilibot(commands.Bot):
  def __init__(self):
    super().__init__(intents = intents)

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
bot.add_cog(Apply(bot))
bot.add_cog(Gear(bot))
bot.add_cog(Submit(bot))
bot.add_cog(Accounts(bot))
bot.add_cog(Link(bot))
bot.add_cog(Unlink(bot))
bot.add_cog(AddLink(bot))
bot.add_cog(MessageListener(bot))

bot.run(os.getenv("TOKEN"))

