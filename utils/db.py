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
