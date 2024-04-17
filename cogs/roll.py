from discord.ext import commands
from discord import app_commands
import discord
import random

# This is a cog, a class that inherits from commands.Cog
# The class name is RollCommand, and it takes a single argument, bot
# The bot argument is the bot instance that the cog is being added to
# The bot instance is passed to the cog when it is added to the bot
# The bot instance is used to interact with the Discord API
class RollCommand(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    
  @app_commands.command(name = "roll", description = "roll dice!")
  async def roll(self, interaction: discord.Interaction, rollString: str = "1d20") -> None:
    try:
      num_dice, num_faces = map(int, rollString.split("d"))
    except:
      await interaction.channel.send("Invalid roll format. Use the format `1d20`")
      return
    
    if num_dice > 100:
      await interaction.channel.send("You can't roll more than 100 dice")
      return
    
    if num_faces > 10000:
      await interaction.channel.send("You can't roll a die with more than 10,000 faces")
      return
    
    if num_dice < 1:
      await interaction.channel.send("You can't roll less than 1 die")
      return
    
    if num_faces < 2:
      await interaction.channel.send("You can't roll a die with less than 2 faces")
      return
    
    rolls = [random.randint(1, num_faces) for _ in range(num_dice)]
    await interaction.channel.send(f"Rolling {num_dice}d{num_faces}: {', '.join(map(str, rolls))} = {sum(rolls)}")

