import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
load_dotenv()
import nest_asyncio
nest_asyncio.apply()
import os

from cogs.log import LogMessages

class Stabilibot(commands.Bot):
  def __init__(self, command_prefix):
    intents = discord.Intents.all()
    intents.message_content = True
    super().__init__(command_prefix=command_prefix, intents=intents)

async def main():
  bot = Stabilibot(command_prefix="!")

  await bot.add_cog(LogMessages(bot))
  await bot.run(os.environ.get("TOKEN"))

if __name__ == "__main__":
  asyncio.run(main())