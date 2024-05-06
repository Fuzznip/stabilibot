import psycopg
from psycopg_pool import ConnectionPool

from dotenv import load_dotenv
load_dotenv()
import os

import wom

dbpool = ConnectionPool(conninfo = os.getenv("DATABASE_URL"))

def create_table():
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      cur.execute("CREATE TABLE IF NOT EXISTS users (discord_id text PRIMARY KEY, username text[])")
      conn.commit()

async def add_user(discordId, username):
  success = False

  # check if the username is a valid RuneScape username
  try:
    # Get user data from WOM
    womClient = wom.Client(user_agent = "Stabilibot")
    await womClient.start()
    # get the first snapshot of the player
    result = await womClient.players.update_player(username = username)
    if not result.is_ok:
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
        cur.execute("INSERT INTO users (discord_id, username) VALUES (%s, %s)", (discordId, username))
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
      # Create the table with team, tile, array of discord ids, and ready boolean
      cur.execute("CREATE TABLE IF NOT EXISTS teams (team text PRIMARY KEY, tile int, discord_ids text[], ready boolean, stars int DEFAULT 0, coins int DEFAULT 0, last_roll_time timestamp DEFAULT now())")
      conn.commit()

def get_teams():
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Get all the teams from the table
      cur.execute("SELECT * FROM teams")
      values = cur.fetchall()
      return values

def create_team(team):
  success = False
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Check if the team already exists
      cur.execute("SELECT * FROM teams WHERE team = %s", (team, ))
      if cur.fetchone() is not None:
        return success

      # If the team doesn't exist, add it to the table
      cur.execute("INSERT INTO teams (team, tile, discord_ids, ready, stars, coins, last_roll_time) VALUES (%s, 0, '{}', true, 0, 0, now())", (team, ))
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
    
def move_team(team, roll):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Get tile count
      tile_count = 21

      # Check if the team has reached the end
      cur.execute("SELECT tile FROM teams WHERE team = %s", (team, ))
      value = cur.fetchone()
      
      if value[0] + roll >= tile_count:
        # Loop back to the beginning
        cur.execute("UPDATE teams SET tile = %s WHERE team = %s", (value[0] + roll - tile_count, team))
      else:
        # Move the team forward
        cur.execute("UPDATE teams SET tile = tile + %s WHERE team = %s", (roll, team))

      # Set the team to not ready and last roll time to now
      cur.execute("UPDATE teams SET ready = false, last_roll_time = now() WHERE team = %s", (team, ))
      conn.commit()
        
def get_team_tile(team):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Get the team from the table
      cur.execute("SELECT tile FROM teams WHERE team = %s", (team, ))
      value = cur.fetchone()
      return value[0] if value is not None else None

def complete_tile(team):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Check if the team is ready to complete the tile
      cur.execute("SELECT ready FROM teams WHERE team = %s", (team, ))
      value = cur.fetchone()
      if value[0]:
        return

      # Set the team to ready
      cur.execute("UPDATE teams SET ready = true WHERE team = %s", (team, ))
      conn.commit()

def add_star(team):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Add a star to the team
      cur.execute("UPDATE teams SET stars = stars + 1 WHERE team = %s", (team, ))
      conn.commit()

def set_stars(team, stars):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Set the stars for the team
      cur.execute("UPDATE teams SET stars = %s WHERE team = %s", (stars, team))
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
