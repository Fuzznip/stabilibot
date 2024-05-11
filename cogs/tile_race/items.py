from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import random

import utils.db as db

DEFAULT_ROLL_SIZE = 4
DEFAULT_ROLL_MODIFIER = 0

class TeamTargeter(discord.ui.Select):
  def __init__(self, my_team, my_item_id, callback):
    options = []
    teams = db.get_team_names()
    for team in teams:
      if team == my_team:
        continue
      options.append(discord.SelectOption(label = team, value = team))
    super().__init__(placeholder = "Select a team", options = options)
    self.cb = callback
    self.team = my_team
    self.item_id = my_item_id

  async def callback(self, interaction):
    team = interaction.data["values"][0]
    db.remove_item(self.team, self.item_id)
    await self.cb(interaction, team)

class SucksToSuck(discord.ui.Button):
  def __init__(self, my_team, item_id):
    self.team = my_team
    self.item_id = item_id
    super().__init__(style = discord.ButtonStyle.red, label = "Sucks to Suck!")

  async def callback(self, interaction):
    view = discord.ui.View()
    async def cb(interaction: discord.Interaction, team):
      tile = db.get_team_tile(team)
      tile = max(0, tile - 2)
      db.complete_tile(team)
      db.set_team_tile(team, tile)

      await interaction.edit(content = f"Sucks to Suck on { team }! They moved back to tile { tile + 1 }", view = None)

    view.add_item(TeamTargeter(self.team, self.item_id, cb))
    # Send response and delete the original message
    await interaction.response.defer()
    await interaction.followup.send("Select a team to use Sucks to Suck on:", view = view, ephemeral = True)
    await interaction.delete_original_response()

class SwitchItUp(discord.ui.Button):
  def __init__(self, my_team, item_id):
    self.team = my_team
    self.item_id = item_id
    super().__init__(style = discord.ButtonStyle.red, label = "Switch It Up!")

  async def callback(self, interaction):
    view = discord.ui.View()
    async def cb(interaction: discord.Interaction, team):
      their_tile = db.get_team_tile(team)
      my_tile = db.get_team_tile(self.team)
      
      db.complete_tile(team)
      db.set_team_tile(team, my_tile)

      db.complete_tile(self.team)
      db.set_team_tile(self.team, their_tile)

      await interaction.edit(content = f"Switched it up with { team }! You are now on tile { their_tile + 1 } while they are on { my_tile + 1 }!", view = None)
      
    view.add_item(TeamTargeter(self.team, self.item_id, cb))
    # Send response and delete the original message
    await interaction.response.defer()
    await interaction.followup.send("Select a team to use Switch it Up on:", view = view, ephemeral = True)
    await interaction.delete_original_response()

class StealAStar(discord.ui.Button):
  def __init__(self, my_team, item_id):
    self.team = my_team
    self.item_id = item_id
    super().__init__(style = discord.ButtonStyle.red, label = "Steal a star!")

  async def callback(self, interaction):
    view = discord.ui.View()
    async def cb(interaction: discord.Interaction, team):
      their_stars = db.get_star_count(team)
      my_stars = db.get_star_count(self.team)

      if their_stars == 0:
        db.add_star(self.team)
        await interaction.edit(content = f"There is nothing to steal! You've gained a star instead and now have { my_stars + 1 } stars!", view = None)
      else:
        db.set_stars(team, their_stars - 1)
        db.add_star(self.team)
        await interaction.edit(content = f"Stole a star from { team }! You are at { my_stars + 1 } stars while they dropped to { their_stars - 1 } stars!", view = None)
      
    view.add_item(TeamTargeter(self.team, self.item_id, cb))
    # Send response and delete the original message
    await interaction.response.defer()
    await interaction.followup.send("Select a team to Steal a Star from:", view = view, ephemeral = True)
    await interaction.delete_original_response()

class TimeToSkill(discord.ui.Button):
  def __init__(self, my_team, item_id):
    self.team = my_team
    self.item_id = item_id
    super().__init__(style = discord.ButtonStyle.red, label = "Time to Skill!")

  async def callback(self, interaction):
    view = discord.ui.View()
    async def cb(interaction: discord.Interaction, team):
      skilling_tile = {
        "name": "Time to Skill!",
        "main_triggers": [
          {
            "type": "CHAT",
            "trigger": ["werewolf agility lap"],
            "count": 250,
            "points": 1,
          },
        ],
      }

      db.add_tile_blocker(team, skilling_tile)
      
      await interaction.edit(content = f"{team} is now forced to skill before they can complete their tile! Oh the humanity!", view = None)
      
    view.add_item(TeamTargeter(self.team, self.item_id, cb))
    # Send response and delete the original message
    await interaction.response.defer()
    await interaction.followup.send("Select a team to force to skill:", view = view, ephemeral = True)
    await interaction.delete_original_response()

class Deny(discord.ui.Button):
  def __init__(self, my_team, item_id):
    self.team = my_team
    self.item_id = item_id
    super().__init__(style = discord.ButtonStyle.red, label = "Deny!")

  async def callback(self, interaction):
    view = discord.ui.View()
    async def cb(interaction: discord.Interaction, team):
      skilling_tile = {
        "repeat": db.get_team_tile(team)
      }

      db.add_tile_blocker(team, skilling_tile)

      await interaction.edit(content = f"{team} is now forced to skill before they can complete their tile! Oh the humanity!", view = None)
      
    view.add_item(TeamTargeter(self.team, self.item_id, cb))
    # Send response and delete the original message
    await interaction.response.defer()
    await interaction.followup.send("Select a team to force them to complete a tile twice:", view = view, ephemeral = True)
    await interaction.delete_original_response()

class Reroll(discord.ui.Button):
  def __init__(self, my_team, item_id):
    self.team = my_team
    self.item_id = item_id
    super().__init__(style = discord.ButtonStyle.blurple, label = "Reroll!")

  async def callback(self, interaction):
    old_tile = db.get_team_tile(self.team)
    prev_tile = db.get_previous_tile(self.team)
    # TODO: real logic
    if old_tile < prev_tile:
      old_roll = old_tile + 20 - prev_tile
    else:
      old_roll = old_tile - prev_tile
    
    roll_size = db.get_roll_size(self.team)
    roll_modifier = db.get_roll_modifier(self.team)

    new_roll = old_roll
    while new_roll == old_roll:
      new_roll = random.randint(1, roll_size) + roll_modifier
      if(new_roll == old_roll):
        print("Rerolling...")


    db.complete_tile(self.team)
    db.set_team_tile(self.team, prev_tile)
    db.move_team(self.team, new_roll)
    new_tile = db.get_team_tile(self.team)
    if new_tile > prev_tile and old_tile < prev_tile:
      print(f"{self.team} rerolled from {old_tile} and went back to {new_tile}. This is just before they looped so they lose 3 stars.")
      db.set_stars(self.team, db.get_star_count(self.team) - 3)

    db.remove_item(self.team, self.item_id)

    await interaction.edit(content = f"You have rerolled from tile { old_tile + 1 }. You have rolled a { new_roll } instead and are now on tile { new_tile + 1 }!", view = None)

class FourPlusFour(discord.ui.Button):
  def __init__(self, my_team, item_id):
    self.team = my_team
    self.item_id = item_id
    super().__init__(style = discord.ButtonStyle.blurple, label = "4 + 4!")

  async def callback(self, interaction):
    db.set_roll_modifier(self.team, 4)
    db.remove_item(self.team, self.item_id)

    await interaction.edit(content = f"Your next roll will have +4 added to it!", view = None)

class Teleport(discord.ui.Button):
  def __init__(self, my_team, item_id):
    self.team = my_team
    self.item_id = item_id
    super().__init__(style = discord.ButtonStyle.blurple, label = "Teleport!")

  async def callback(self, interaction):
    # get a random tile
    current_tile = db.get_team_tile(self.team)
    tile = current_tile
    while tile == current_tile:
      tile = random.randint(0, 20)
    db.complete_tile(self.team)
    db.set_team_tile(self.team, tile)

    db.remove_item(self.team, self.item_id)

    await interaction.edit(content = f"You have teleported to tile { tile + 1 }!", view = None)

class ThankYouNext(discord.ui.Button):
  def __init__(self, my_team, item_id):
    self.team = my_team
    self.item_id = item_id
    super().__init__(style = discord.ButtonStyle.blurple, label = "Thank you, Next!")

  async def callback(self, interaction):
    # make sure team is not ready
    if db.is_team_ready(self.team):
      await interaction.edit(content = "Your team is ready to roll. Please roll first!", view = None)
      return

    db.complete_tile(self.team)
    db.set_roll_size(self.team, DEFAULT_ROLL_SIZE)
    db.set_roll_modifier(self.team, DEFAULT_ROLL_MODIFIER)
    # add 1 star to the team
    db.add_star(self.team)
    db.remove_item(self.team, self.item_id)

    await interaction.edit(content = f"Your tile has been completed!", view = None)

class CustomDie(discord.ui.Button):
  def __init__(self, my_team, item_id):
    self.team = my_team
    self.item_id = item_id
    super().__init__(style = discord.ButtonStyle.blurple, label = "Custom Die!")

  async def callback(self, interaction):
    if not db.is_team_ready(self.team):
      await interaction.edit(content = "Your team is not ready to roll. Please complete your current tile!", view = None)
      return
    
    async def cb(interaction):
      number = int(interaction.data["values"][0])
      db.complete_tile(self.team)
      db.move_team(self.team, number)
      db.remove_item(self.team, self.item_id)
      tile = db.get_team_tile(self.team)
      await interaction.edit(content = f"You have moved forward {number} tiles and are now on tile { tile + 1 }", view = None)

    view = discord.ui.View()
    selector = discord.ui.Select(placeholder = "Select a number", options = [discord.SelectOption(label = str(i), value = str(i)) for i in range(1, 4)])
    selector.callback = cb
    view.add_item(selector)
    await interaction.response.defer()
    await interaction.followup.send("How far would you like to move:", view = view, ephemeral = True)
    await interaction.delete_original_response()

item_classes = [
  SucksToSuck, # 0
  SwitchItUp, # 1
  StealAStar, # 2
  TimeToSkill,  # 3
  Deny, # 4
  Reroll, # 5
  FourPlusFour, # 6
  Teleport,   # 7
  ThankYouNext, # 8
  CustomDie # 9
]

class Items(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    db.ensure_teams_table()

  @discord.slash_command(name = "use_item", description = "View your team's items", guild_ids = [int(os.getenv("GUILD_ID"))])
  async def items(self, interaction):
    team = db.get_team(str(interaction.author.id))
    items = db.get_items(team)

    if not items:
      await interaction.response.send_message("You have no items.", ephemeral = True)
      return

    view = discord.ui.View()
    for item in items:
      i = item_classes[int(item)](team, item)
      view.add_item(i)

    await interaction.response.send_message("Select an item to use:", view = view, ephemeral = True)

class AddItem(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    db.ensure_teams_table()

  @commands.has_role("Staff")
  @discord.slash_command(name = "add_item", description = "Add an item to a team", guild_ids = [int(os.getenv("GUILD_ID"))])
  async def add_item(self, interaction, team_name: str, item: str):
    if item not in [item.__name__.lower() for item in item_classes]:
      await interaction.response.send_message("Invalid item.", ephemeral = True)
      return

    item_id = [item.__name__.lower() for item in item_classes].index(item)
    db.add_item(team_name, item_id)
    await interaction.response.send_message(f"Successfully added {item} to {team_name}!", ephemeral = True)
