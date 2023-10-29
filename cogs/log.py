from channelcheck import is_message_in_channels
from datetime import datetime
from discord.ext import commands

class LogMessages(commands.Cog):
  def __init__(self, bot):
    self.bot = bot

    # channel name
    self.channels = [ "bot-testing", "staff" ]

  @commands.Cog.listener()
  async def on_message(self, message):
    if is_message_in_channels(message, self.channels):
      print('{} => [{}] {} ({}): {}'.format(message.channel.name, datetime.now(), message.author, message.author.display_name, message.content), flush=True)
      