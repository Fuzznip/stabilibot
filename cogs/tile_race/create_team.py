from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import utils.db as db

import time

class ViewTeams(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    db.ensure_teams_table()

  @discord.slash_command(name = "view_teams", description = "View all teams standings", guild_ids = [int(os.getenv("GUILD_ID"))])
  async def view_teams(self, interaction):
    teams = db.get_teams()

    if not teams:
      await interaction.response.send_message("No teams found.", ephemeral = True)
      return
    
    team_strings = []

    for team in teams:
      name = team[0]
      tile = team[1]
      ready = team[8]
      items = team[7]
      main_progress = team[11]
      side_progress = team[12]
      stars = team[9]
      coins = team[10]

      tile_data = db.get_tile(tile)
      tile_name = tile_data[1]

      item_list = []
      for item in items:
        item_name = db.get_item_name(int(item))
        item_list.append(item_name)

      ready_string = 'ready' if ready else 'not ready'

      team_strings.append(f"{ name }: tile { tile + 1 } ({tile_name}) with { stars } stars and { coins } coins. They are {ready_string} to roll. Their available items are: [ { ', '.join(item_list) } ]")

    await interaction.response.send_message("\n".join(team_strings), ephemeral = True)

class MyTeam(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    db.ensure_teams_table()

  @discord.slash_command(name = "my_team", description = "View your team", guild_ids = [int(os.getenv("GUILD_ID"))])
  async def my_team(self, interaction):
    await interaction.response.defer()
    team = db.get_team(str(interaction.author.id))

    if team is None:
      await interaction.response.send_message("You are not on a team. Please join a team.", ephemeral = True)
      return

    tile_id = db.get_team_tile(team)
    tile_data = db.get_tile(tile_id)
    tile_name = tile_data[1]

    stars = db.get_star_count(team)
    coins = db.get_coin_count(team)
    tile_main_progress = tile_data[2]
    tile_side_progress = tile_data[3]
    
    team_main_progress = db.get_main_progress(team, tile_id)
    team_side_progress = db.get_side_progress(team, tile_id)

    progress = []
    # Enumerate through the triggers of the main and side progress
    progress.append(f"{tile_name} Quest Progress:")
    # check if the team has main progress
    if len(team_main_progress) > 0:
      for trigger in tile_main_progress:
        if "count" in trigger:
          max_count = trigger["count"]
        else:
          max_count = 1

        if "points" in trigger:
          points = trigger["points"]
        else:
          points = 1

        if "type" in trigger:
          type = trigger["type"]
        else:
          type = "UNKNOWN"

        if "name" in trigger:
          name = trigger["name"]
        else:
          name = "unknown"

        for t in trigger["trigger"]:
          # remove everything in t after a :
          t = t.split(":")[0]
          t_lower = t.lower()
          if t_lower in team_main_progress:
            count = team_main_progress[t_lower]["value"]
            if count > 0:
              if type == "CHAT":
                progress.append(f"\t{name} [{type}]: {count}/{max_count} ({points} stars)")
              else:
                progress.append(f"\t{t} [{type}]: {count}/{max_count} ({points} stars)")
    else:
      progress.append("\tNo main quest progress")
    
    # Enumerate through the triggers of the main and side progress
    progress.append(f"{tile_name} Side Quest Progress:")
    if len(team_side_progress) > 0:
      for trigger in tile_side_progress:
        if "count" in trigger:
          max_count = trigger["count"]
        else:
          max_count = 1

        if "points" in trigger:
          points = trigger["points"]
        else:
          points = 1

        if "type" in trigger:
          type = trigger["type"]
        else:
          type = "UNKNOWN"

        if "name" in trigger:
          name = trigger["name"]
        else:
          name = "unknown"

        for t in trigger["trigger"]:
          # remove everything in t after a :
          t = t.split(":")[0]
          t_lower = t.lower()
          if t_lower in team_side_progress:
            count = team_side_progress[t_lower]["value"]
            if count > 0:
              if type == "CHAT":
                progress.append(f"\t{name} [{type}]: {count}/{max_count} ({points} coins)")
              else:
                progress.append(f"\t{t} [{type}]: {count}/{max_count} ({points} coins)")
    else:
      progress.append("\tNo side quest progress")

    coins_gained = 0
    for object in team_side_progress:
      coins_gained += team_side_progress[object]["gained"] if "gained" in team_side_progress[object] else 0

    progress_string = "\n".join(progress)
    await interaction.followup.send(f"""You are on team { team }.
Your team currently has { stars } stars and { coins } coins.
You are on tile number {tile_id + 1}: {tile_name}.

{progress_string}

Coins earned so far: {coins_gained}/8

Want more information? Ask what you want to see out of the bot at https://discord.com/channels/519627285503148032/1238326277191241728""", ephemeral = True)

class ViewTeam(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    db.ensure_teams_table()

  @discord.slash_command(name = "view_team", description = "View a team", guild_ids = [int(os.getenv("GUILD_ID"))])
  async def view_team(self, interaction, team_name: str):
    await interaction.response.defer()
    team = team_name

    if db.team_exists(team) == False:
      await interaction.response.send_message("Team does not exist.", ephemeral = True)
      return

    tile_id = db.get_team_tile(team)
    tile_data = db.get_tile(tile_id)
    tile_name = tile_data[1]

    stars = db.get_star_count(team)
    coins = db.get_coin_count(team)
    tile_main_progress = tile_data[2]
    tile_side_progress = tile_data[3]
    
    team_main_progress = db.get_main_progress(team, tile_id)
    team_side_progress = db.get_side_progress(team, tile_id)

    progress = []
    # Enumerate through the triggers of the main and side progress
    progress.append(f"{tile_name} Quest Progress:")
    # check if the team has main progress
    if len(team_main_progress) > 0:
      for trigger in tile_main_progress:
        if "count" in trigger:
          max_count = trigger["count"]
        else:
          max_count = 1

        if "points" in trigger:
          points = trigger["points"]
        else:
          points = 1

        if "type" in trigger:
          type = trigger["type"]
        else:
          type = "UNKNOWN"

        if "name" in trigger:
          name = trigger["name"]
        else:
          name = "unknown"

        for t in trigger["trigger"]:
          # remove everything in t after a :
          t = t.split(":")[0]
          t_lower = t.lower()
          if t_lower in team_main_progress:
            count = team_main_progress[t_lower]["value"]
            if count > 0:
              if type == "CHAT":
                progress.append(f"\t{name} [{type}]: {count}/{max_count} ({points} stars)")
              else:
                progress.append(f"\t{t} [{type}]: {count}/{max_count} ({points} stars)")
    else:
      progress.append("\tNo main quest progress")
    
    # Enumerate through the triggers of the main and side progress
    progress.append(f"{tile_name} Side Quest Progress:")
    if len(team_side_progress) > 0:
      for trigger in tile_side_progress:
        if "count" in trigger:
          max_count = trigger["count"]
        else:
          max_count = 1

        if "points" in trigger:
          points = trigger["points"]
        else:
          points = 1

        if "type" in trigger:
          type = trigger["type"]
        else:
          type = "UNKNOWN"

        if "name" in trigger:
          name = trigger["name"]
        else:
          name = "unknown"

        for t in trigger["trigger"]:
          # remove everything in t after a :
          t = t.split(":")[0]
          t_lower = t.lower()
          if t_lower in team_side_progress:
            count = team_side_progress[t_lower]["value"]
            if count > 0:
              if type == "CHAT":
                progress.append(f"\t{name} [{type}]: {count}/{max_count} ({points} coins)")
              else:
                progress.append(f"\t{t} [{type}]: {count}/{max_count} ({points} coins)")
    else:
      progress.append("\tNo side quest progress")

    coins_gained = 0
    for object in team_side_progress:
      coins_gained += team_side_progress[object]["gained"] if "gained" in team_side_progress[object] else 0

    progress_string = "\n".join(progress)
    await interaction.followup.send(f"""Team { team }:
The team currently has { stars } stars and { coins } coins.
They are on tile number {tile_id + 1}: {tile_name}.

{progress_string}

Coins earned so far: {coins_gained}/8

Want more information? Ask what you want to see out of the bot at https://discord.com/channels/519627285503148032/1238326277191241728""", ephemeral = True)

class CreateTeam(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    db.ensure_teams_table()

  # Only allow users to create a team if they have the "Staff" role
  @commands.has_role("Staff")
  @discord.slash_command(name = "create_team", description = "Creates a team", guild_ids = [int(os.getenv("GUILD_ID"))])
  async def create_team(self, interaction, team_name: str):
    # Attempt to create a team
    success = db.create_team(team_name)

    if not success:
      await interaction.response.send_message("Failed to create team. Team name already exists.", ephemeral = True)
      return
    
    # Create a role named after the team
    guild = self.bot.get_guild(int(os.getenv("GUILD_ID")))
    await guild.create_role(name = team_name, reason = "Creating a team")

    await interaction.response.send_message(f"Successfully created team { team_name }!", ephemeral = True)

class DeleteTeam(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    db.ensure_teams_table()

  # Only allow users to delete a team if they have the "Staff" role
  @commands.has_role("Staff")
  @discord.slash_command(name = "delete_team", description = "Deletes a team", guild_ids = [int(os.getenv("GUILD_ID"))])
  async def delete_team(self, interaction, team_name: str):
    # Attempt to delete a team
    success = db.delete_team(team_name)

    if not success:
      await interaction.response.send_message("Failed to delete team. Team does not exist.", ephemeral = True)
      return
    
    # Delete the role of the team
    guild = self.bot.get_guild(int(os.getenv("GUILD_ID")))
    role = discord.utils.get(guild.roles, name = team_name)
    await role.delete()

    await interaction.response.send_message(f"Successfully deleted team { team_name }!", ephemeral = True)

