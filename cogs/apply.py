from discord.ext import commands
from discord import ui, app_commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import wom
from wom import Skills

class ApplicationForm(ui.Modal, title = "Application Form"):
  def __init__(self, bot: commands.Bot, interaction: discord.Interaction):
    super().__init__(title = "Application Form", timeout = None, custom_id = "application_form")
    self.bot = bot
    self.interaction = interaction
  
  async def on_submit(self, interaction: discord.Interaction) -> None:
    try:
      # Get user data from WOM
      womClient = wom.Client(user_agent = "Stabilibot")
      await womClient.start()
      # get the first snapshot of the player
      result = await womClient.players.update_player(username = self.osrsName.value)
      if result.is_ok:
        playerDetail = result.unwrap()
        snapshot = playerDetail.latest_snapshot
        if playerDetail.latest_snapshot is None:
          errorMessage = "Cannot find latest snapshot for player. Please try again later."
          await interaction.response.send_message(errorMessage, ephemeral = True)
          print(errorMessage)
          await womClient.close()
          return
        totalLevel = snapshot.data.skills[Skills("overall")].level
        ehb = playerDetail.player.ehb

        # Create an embed with the title as the username
        embed = discord.Embed(title = self.osrsName.value)
        # Add the user's discord username and avatar to the embed
        embed.set_author(name = interaction.user.display_name, icon_url = interaction.user.display_avatar)

        # Add the user's application responses to the embed
        embed.add_field(name = "Recruitment Method", value = self.recruitmentMethod.value)
        embed.add_field(name = "Reason for Joining", value = self.reasonForJoining.value)
        embed.add_field(name = "In-Game Goals", value = self.inGameGoals.value)
        embed.add_field(name = "Total Level", value = totalLevel)
        embed.add_field(name = "EHB", value = ehb)

        # Get the env APPLICATION_OUTPUT_CHANNEL
        channel = self.bot.get_channel(int(os.getenv("APPLICATION_OUTPUT_CHANNEL_ID")))

        # submit the embed to the APPLICATION_OUTPUT_CHANNEL
        await channel.send(embed = embed)

        # Remove the "Applicant" role from the user if they have it
        role = discord.utils.get(interaction.guild.roles, name = "Applicant")
        if role in interaction.user.roles:
          await interaction.user.remove_roles(role)
        
        # Remove the "Guest" role from the user if they have it
        role = discord.utils.get(interaction.guild.roles, name = "Guest")
        if role in interaction.user.roles:
          await interaction.user.remove_roles(role)

        # Add the "Applied" role to the user
        role = discord.utils.get(interaction.guild.roles, name = "Applied")
        await interaction.user.add_roles(role)

        # Rename the user to their OSRS username
        try:
          await interaction.user.edit(nick = self.osrsName.value)
        except discord.errors.Forbidden:
          print("Bot does not have permission to change nickname for user: {}".format(interaction.user.display_name))

        await interaction.response.send_message("Application submitted!", ephemeral = True)
      else:
        await interaction.response.send_message("Error fetching player data - double check the spelling of your OSRS username and then contact Staff if issue persists.", ephemeral = True)
      await womClient.close()
    except Exception as e:
      await interaction.response.send_message(f"An error occurred: {e}", ephemeral = True)
      print(e)
      await womClient.close()

  osrsName = ui.TextInput(label = "What is your OSRS username?", placeholder = "Zezima", required = True)
  recruitmentMethod = ui.TextInput(label = "How did you hear about us?", style = discord.TextStyle.paragraph, placeholder = "Reddit/OSRS discord/Word of Mouth", required = True, max_length = 100)
  reasonForJoining = ui.TextInput(label = "Why do you want to join?", style = discord.TextStyle.paragraph, placeholder = "I want to learn to PvM", required = True, max_length = 1000)
  inGameGoals = ui.TextInput(label = "What are your in-game goals?", style = discord.TextStyle.paragraph, placeholder = "Maxing my account/Making 10b gp", required = True, max_length = 1000)

class ApplyCommand(commands.Cog):
  def __init__(self, bot: commands.Bot):
    self.bot = bot

  @app_commands.command(name = "apply", description = "apply to join the clan")
  async def apply(self, interaction: discord.Interaction) -> None:
    # Check if the interaction is in a guild
    if not interaction.guild:
      await interaction.response.send_message("This command can only be used in a server", ephemeral = True)
      return
    
    # Check if the user has the "Applied" role
    role = discord.utils.get(interaction.guild.roles, name = "Applied")
    if role in interaction.user.roles:
      await interaction.response.send_message("You have already applied", ephemeral = True)
      return
    
    # Check if the user has the "Member" role
    role = discord.utils.get(interaction.guild.roles, name = "Member")
    if role in interaction.user.roles:
      await interaction.response.send_message("You are already a member", ephemeral = True)
      return

    await interaction.response.send_modal(ApplicationForm(self.bot, interaction))
