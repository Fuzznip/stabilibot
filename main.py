import asyncio
import discord
from typing import Literal, Optional
from discord.ext import commands
from discord.ext.commands import Greedy
from dotenv import load_dotenv
load_dotenv()
import nest_asyncio
nest_asyncio.apply()
import os

from cogs.log import LogMessages
from cogs.gear import GearCommand
from cogs.nick import NicknameCommand
from cogs.announce import Announce

class Stabilibot(commands.Bot):
  def __init__(self, command_prefix):
    intents = discord.Intents.all()
    intents.message_content = True
    super().__init__(command_prefix = command_prefix, intents = intents)

async def main():
  bot = Stabilibot(command_prefix = "!")

  # from https://gist.github.com/AbstractUmbra/a9c188797ae194e592efe05fa129c57f
  @bot.command()
  @commands.guild_only()
  @commands.is_owner()
  async def sync(ctx, guilds: Greedy[discord.Object], spec: Optional[Literal["~", "*", "^"]] = None) -> None:
    if not guilds:
      if spec == "~":
        synced = await ctx.bot.tree.sync(guild=ctx.guild)
      elif spec == "*":
        ctx.bot.tree.copy_global_to(guild=ctx.guild)
        synced = await ctx.bot.tree.sync(guild=ctx.guild)
      elif spec == "^":
        ctx.bot.tree.clear_commands(guild=ctx.guild)
        await ctx.bot.tree.sync(guild=ctx.guild)
        synced = []
      else:
        synced = await ctx.bot.tree.sync()

      await ctx.send(
        f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
      )
      return

    ret = 0
    for guild in guilds:
      try:
        await ctx.bot.tree.sync(guild=guild)
      except discord.HTTPException:
        pass
      else:
        ret += 1

    await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

  await bot.add_cog(LogMessages(bot))
  await bot.add_cog(GearCommand(bot))
  await bot.add_cog(NicknameCommand(bot))
  await bot.add_cog(Announce(bot))
  bot.run(os.environ.get("TOKEN"))

if __name__ == "__main__":
  asyncio.run(main())
