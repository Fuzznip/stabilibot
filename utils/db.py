import psycopg
from psycopg_pool import ConnectionPool
from psycopg.types.json import Jsonb

from dotenv import load_dotenv
load_dotenv()
import os

import wom

import json

dbpool = ConnectionPool(conninfo = os.getenv("DATABASE_URL"))

def create_table():
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      cur.execute("CREATE TABLE IF NOT EXISTS users (discord_id text PRIMARY KEY, username text[])")
      conn.commit()

async def add_user(discordId, username):
  # first, lowercase the username
  username = username.lower()

  success = False

  # check if the username is a valid RuneScape username
  try:
    # Get user data from WOM
    womClient = wom.Client(user_agent = "Stabilibot")
    await womClient.start()
    # get the first snapshot of the player
    result = await womClient.players.update_player(username = username)
    # Check if error is http response 429 (rate limited)
    if not result.is_ok:
      if result.status != 429: # rate limiting is fine we just want to check if the username is valid
        await womClient.close()
        return success
    await womClient.close()
  except:
    await womClient.close()
    return success

  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # First confirm that the username is not already linked to another discord account
      cur.execute("SELECT * FROM users WHERE username @> %s", ([username], ))
      if cur.fetchone() is not None:
        return success

      # Get the user from the table
      cur.execute("SELECT * FROM users WHERE discord_id = %s", (discordId, ))
      # Check if the user exists
      val = cur.fetchone()
      if val is None:
        # If the user doesn't exist, add them to the table
        cur.execute("INSERT INTO users (discord_id, username) VALUES (%s, %s)", (discordId, [username]))
      else:
        # Check if the username is already in the array
        if username in val[1]:
          return
        # If the username isn't in the array, add it
        cur.execute("UPDATE users SET username = array_append(users.username, %s) WHERE discord_id = %s", (username, discordId))
      conn.commit()
      success = True

  return success

async def remove_user(discordId, username):
  # first, lowercase the username
  username = username.lower()

  success = False
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Check if the user has the username linked to their discord account
      cur.execute("SELECT * FROM users WHERE discord_id = %s AND username @> %s", (discordId, [username]))
      if cur.fetchone() is None:
        return success

      # Remove the username from the array
      cur.execute("UPDATE users SET username = array_remove(users.username, %s) WHERE discord_id = %s", (username, discordId))
      conn.commit()
      success = True

  return success

def get_users():
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Get all the users from the table
      cur.execute("SELECT * FROM users")
      values = cur.fetchall()
      return values

def get_user(discordId):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Get the user from the table
      cur.execute("SELECT username FROM users WHERE discord_id = %s", (discordId, ))
      value = cur.fetchone()
      return value[0] if value is not None else None

def get_user_from_username(username):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Get the user from the table
      cur.execute("SELECT discord_id FROM users WHERE username @> %s", ([username], ))
      value = cur.fetchone()
      return value[0] if value is not None else None

def ensure_teams_table():
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Create the teams table
      # team: the name of the team
      # tile: the current tile the team is on
      # discord_ids: the discord ids of the users on the team
      # items: the items the team has
      # ready: whether the team is ready to roll
      # stars: the number of stars the team has
      # coins: the number of coins the team has
      # tile_progress: the progress the team has made on various tiles
      # last_roll_time: the time the team last rolled
      cur.execute("""CREATE TABLE IF NOT EXISTS teams (
                  team text PRIMARY KEY, 
                  tile int, 
                  tile_blockers jsonb[] DEFAULT '{}'::jsonb[],
                  last_tile int,
                  roll_size int DEFAULT 4,
                  roll_modifier int DEFAULT 0,
                  discord_ids text[], 
                  items text[], 
                  ready boolean, 
                  stars int DEFAULT 0, 
                  coins int DEFAULT 0, 
                  tile_progress jsonb DEFAULT '{}'::jsonb,
                  side_progress jsonb DEFAULT '{}'::jsonb,
                  last_roll_time timestamp DEFAULT now())""")
      conn.commit()

def get_teams():
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Get all the teams from the table
      cur.execute("SELECT * FROM teams")
      values = cur.fetchall()
      return values

def get_team_names():
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Get all the team names from the table
      cur.execute("SELECT team FROM teams")
      values = cur.fetchall()
      return [value[0] for value in values]

def create_team(team):
  success = False
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Check if the team already exists
      cur.execute("SELECT * FROM teams WHERE team = %s", (team, ))
      if cur.fetchone() is not None:
        return success

      # If the team doesn't exist, add it to the table
      cur.execute("""INSERT INTO teams (
                  team, 
                  tile, 
                  tile_blockers,
                  last_tile,
                  roll_size,
                  roll_modifier,
                  discord_ids, 
                  items, 
                  ready, 
                  stars, 
                  coins, 
                  tile_progress,
                  side_progress,
                  last_roll_time
                  ) VALUES (
                  %s, 
                  -1,
                  '{}'::jsonb[], 
                  -1,
                  4,
                  0,
                  '{}', 
                  '{}', 
                  true, 
                  0, 
                  0, 
                  '{}'::jsonb,
                  '{}'::jsonb,
                  now()
                  )""", (team, ))
      conn.commit()
      success = True

  return success

def delete_team(team):
  success = False
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Check if the team exists
      cur.execute("SELECT * FROM teams WHERE team = %s", (team, ))
      if cur.fetchone() is None:
        return success

      # If the team exists, remove it from the table
      cur.execute("DELETE FROM teams WHERE team = %s", (team, ))
      conn.commit()
      success = True

  return success

def team_exists(team): 
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Check if the team exists
      cur.execute("SELECT * FROM teams WHERE team = %s", (team, ))
      return cur.fetchone() is not None

def get_team(discordId):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Get the team from the table
      cur.execute("SELECT team FROM teams WHERE discord_ids @> %s", ([discordId], ))
      value = cur.fetchone()
      return value[0] if value is not None else None

def add_player(team, user):
  success = False
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Get the discord id from the username
      cur.execute("SELECT discord_id FROM users WHERE username @> %s", ([user], ))
      value = cur.fetchone()
      if value is None:
        return success
      
      # Check if the user is already on a team
      cur.execute("SELECT * FROM teams WHERE discord_ids @> %s", ([value[0]], ))
      if cur.fetchone() is not None:
        return success
      
      # Add the user to the team
      cur.execute("UPDATE teams SET discord_ids = array_append(teams.discord_ids, %s) WHERE team = %s", (value[0], team))
      conn.commit()
      success = True

  return success

def remove_player(team, user):
  success = False
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Get the discord id from the username
      cur.execute("SELECT discord_id FROM users WHERE username @> %s", ([user], ))
      value = cur.fetchone()
      if value is None:
        return success
      
      # Check if the user is on the team
      cur.execute("SELECT * FROM teams WHERE discord_ids @> %s", ([value[0]], ))
      if cur.fetchone() is None:
        return success
      
      # Remove the user from the team
      cur.execute("UPDATE teams SET discord_ids = array_remove(teams.discord_ids, %s) WHERE team = %s", ('88087113626587136', team))
      conn.commit()
      success = True

  return success

def is_team_ready(team):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Get the team from the table
      cur.execute("SELECT ready FROM teams WHERE team = %s", (team, ))
      value = cur.fetchone()
      return value[0] if value is not None else None
    
def move_team(team, roll, max_tile = 20):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      looped = False

      # Check if the team has reached the end
      cur.execute("SELECT tile FROM teams WHERE team = %s", (team, ))
      value = cur.fetchone()
      
      if value[0] + roll > max_tile:
        # Loop back to the beginning
        cur.execute("UPDATE teams SET tile = %s WHERE team = %s", (value[0] + roll - max_tile - 1, team))
        looped = True
      else:
        # Move the team forward
        cur.execute("UPDATE teams SET tile = tile + %s WHERE team = %s", (roll, team))

      # Set the previous tile
      cur.execute("UPDATE teams SET last_tile = %s WHERE team = %s", (value[0], team))

      # Set the team to not ready and last roll time to now
      cur.execute("UPDATE teams SET ready = false, last_roll_time = now() WHERE team = %s", (team, ))
      conn.commit()

      return looped

def get_team_tile(team):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Get the team from the table
      cur.execute("SELECT tile FROM teams WHERE team = %s", (team, ))
      value = cur.fetchone()
      return value[0] if value is not None else None
    
def get_previous_tile(team):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Get the team from the table
      cur.execute("SELECT last_tile FROM teams WHERE team = %s", (team, ))
      value = cur.fetchone()
      return value[0] if value is not None else None

def set_team_tile(team, tile):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Set the tile for the team
      cur.execute("UPDATE teams SET tile = %s WHERE team = %s", (tile, team))
      conn.commit()

def complete_tile(team):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Complete the tile
      cur.execute("UPDATE teams SET ready = true WHERE team = %s", (team, ))

      # Get the tile from the table
      cur.execute("SELECT tile FROM teams WHERE team = %s", (team, ))
      value = cur.fetchone()
      tile = value[0]

      # Reset the "gained" field in the side progress
      # Get the side progress from the table as a json
      cur.execute("SELECT side_progress FROM teams WHERE team = %s", (team, ))
      value = json.dumps(cur.fetchall())
      value_dict = json.loads(value)[0][0]
      if value_dict and str(tile) in value_dict:
        for key in value_dict[str(tile)]:
          value_dict[str(tile)][key]["gained"] = 0
        cur.execute("UPDATE teams SET side_progress = jsonb_set(side_progress, %s, %s) WHERE team = %s", ([str(tile)], json.dumps(value_dict[str(tile)]), team))

      # Reset the "value" field in the main progress
      # Get the main progress from the table as a json
      cur.execute("SELECT tile_progress FROM teams WHERE team = %s", (team, ))
      value = json.dumps(cur.fetchall())
      value_dict = json.loads(value)[0][0]
      if value_dict and str(tile) in value_dict:
        for key in value_dict[str(tile)]:
          value_dict[str(tile)][key]["value"] = 0
        cur.execute("UPDATE teams SET tile_progress = jsonb_set(tile_progress, %s, %s) WHERE team = %s", ([str(tile)], json.dumps(value_dict[str(tile)]), team))

      conn.commit()

def get_star_count(team):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Get the team from the table
      cur.execute("SELECT stars FROM teams WHERE team = %s", (team, ))
      value = cur.fetchone()
      return value[0] if value is not None else None

def add_star(team):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Add a star to the team
      cur.execute("UPDATE teams SET stars = stars + 1 WHERE team = %s", (team, ))
      conn.commit()

def add_stars(team, count):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Add stars to the team
      cur.execute("UPDATE teams SET stars = stars + %s WHERE team = %s", (count, team))
      conn.commit()

def set_stars(team, stars):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Set the stars for the team
      cur.execute("UPDATE teams SET stars = %s WHERE team = %s", (stars, team))
      conn.commit()

def add_coins(team, coins):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Add coins to the team
      cur.execute("UPDATE teams SET coins = coins + %s WHERE team = %s", (coins, team))
      conn.commit()

def set_coins(team, coins):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Add coins to the team
      cur.execute("UPDATE teams SET coins = coins + %s WHERE team = %s", (coins, team))
      conn.commit()

def get_coin_count(team):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Get the team from the table
      cur.execute("SELECT coins FROM teams WHERE team = %s", (team, ))
      value = cur.fetchone()
      return value[0] if value is not None else None

def get_items(team):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Get the team from the table
      cur.execute("SELECT items FROM teams WHERE team = %s", (team, ))
      value = cur.fetchone()
      return value[0] if value is not None else None

def add_item(team, item):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Add an item to the team
      cur.execute("UPDATE teams SET items = array_append(teams.items, %s) WHERE team = %s", (str(item), team))
      conn.commit()

def remove_item(team, item):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # get the items from the team
      cur.execute("SELECT items FROM teams WHERE team = %s", (team, ))
      value = cur.fetchone()
      if value is None:
        return
      
      # Remove the first instance of the item from the array
      if item in value[0]:
        items = value[0]
        items.remove(item)

      cur.execute("UPDATE teams SET items = %s WHERE team = %s", (items, team))
      conn.commit()

def add_tile_blocker(team, tile_blocker):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Get the array of tile blockers from the team
      cur.execute("SELECT tile_blockers FROM teams WHERE team = %s", (team, ))

      # If the team doesn't have any tile blockers, set the array to an empty array
      value = cur.fetchone()
      if value is None:
        cur.execute("UPDATE teams SET tile_blockers = %s WHERE team = %s", ([tile_blocker], team))
        conn.commit()
        return
      
      # Otherwise add the tile blocker to the array
      cur.execute("UPDATE teams SET tile_blockers = array_append(teams.tile_blockers, %s) WHERE team = %s", (Jsonb(tile_blocker), team))
      conn.commit()

def get_roll_size(team):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Get the team from the table
      cur.execute("SELECT roll_size FROM teams WHERE team = %s", (team, ))
      value = cur.fetchone()
      return value[0] if value is not None else None
    
def get_roll_modifier(team):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Get the team from the table
      cur.execute("SELECT roll_modifier FROM teams WHERE team = %s", (team, ))
      value = cur.fetchone()
      return value[0] if value is not None else None

def set_roll_modifier(team, modifier):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Set the roll modifier for the team
      cur.execute("UPDATE teams SET roll_modifier = %s WHERE team = %s", (modifier, team))
      conn.commit()

def set_roll_size(team, size):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Set the roll size for the team
      cur.execute("UPDATE teams SET roll_size = %s WHERE team = %s", (size, team))
      conn.commit()

def get_tile(tile_id):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Get the tile from the table
      cur.execute("SELECT * FROM tiles WHERE tile_id = %s", (tile_id, ))
      value = cur.fetchone()
      return value if value is not None else None

def get_item_name(item_id):
  item_classes = [
    "SucksToSuck", # 0
    "SwitchItUp", # 1
    "StealAStar", # 2
    "TimeToSkill",  # 3
    "Deny", # 4
    "Reroll", # 5
    "FourPlusFour", # 6
    "Teleport",   # 7
    "ThankYouNext", # 8
    "CustomDie" # 9
  ]

  return item_classes[item_id]

def get_main_progress(team, tile):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Get the main progress from the table as a json
      cur.execute("SELECT tile_progress FROM teams WHERE team = %s", (team, ))
      value = json.dumps(cur.fetchall())
      value_dict = json.loads(value)[0][0]
      if value_dict is None:
        return None
      
      # loop through value tuple
      if str(tile) not in value_dict:
        return {}
      
      return value_dict[str(tile)]

def get_side_progress(team, tile):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Get the side progress from the table as a json
      cur.execute("SELECT side_progress FROM teams WHERE team = %s", (team, ))
      value = json.dumps(cur.fetchall())
      value_dict = json.loads(value)[0][0]
      if value_dict is None:
        return None
      
      # loop through value tuple
      if str(tile) not in value_dict:
        return {}
      
      return value_dict[str(tile)]
