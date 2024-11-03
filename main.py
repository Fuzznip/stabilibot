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
# from cogs.tile_race.roll import Roll, RollTeam, MoveToTile
# from cogs.tile_race.create_team import ViewTeams, ViewTeam, MyTeam, CreateTeam, DeleteTeam
# from cogs.tile_race.add_player import AddPlayer, RemovePlayer
# from cogs.tile_race.complete_tile import CompleteTile, AddCoins, SetStars
# from cogs.tile_race.items import Items, AddItem

from cogs.sp2.create_team import CreateTeam
from cogs.sp2.delete_team import DeleteTeam
from cogs.sp2.rename_team import RenameTeam
from cogs.sp2.add_user import AddUser

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
# bot.add_cog(Roll(bot))
# bot.add_cog(RollTeam(bot))
# bot.add_cog(MoveToTile(bot))
# bot.add_cog(ViewTeams(bot))
# bot.add_cog(ViewTeam(bot))
# bot.add_cog(MyTeam(bot))
# bot.add_cog(CreateTeam(bot))
# bot.add_cog(DeleteTeam(bot))
# bot.add_cog(AddPlayer(bot))
# bot.add_cog(RemovePlayer(bot))
# bot.add_cog(CompleteTile(bot))
# bot.add_cog(AddCoins(bot))
# bot.add_cog(SetStars(bot))
# bot.add_cog(Items(bot))
# bot.add_cog(AddItem(bot))
bot.add_cog(CreateTeam(bot))
bot.add_cog(DeleteTeam(bot))
bot.add_cog(RenameTeam(bot))
bot.add_cog(AddUser(bot))
bot.run(os.getenv("TOKEN"))
