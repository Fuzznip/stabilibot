import psycopg
from psycopg_pool import ConnectionPool
from psycopg.types.json import Jsonb

from dotenv import load_dotenv
load_dotenv()
import os

import wom

import json
import uuid

dbpool = ConnectionPool(conninfo = os.getenv("DATABASE_URL"))

async def add_user(discordId, username):
  # first, lowercase the username
  username = username.lower()

  success = False

  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # First confirm that the username is not already linked to another discord account
      cur.execute("SELECT * FROM users WHERE runescape_name = %s", (username, ))
      if cur.fetchone() is not None:
        return success
      
      # Get the user from the table
      cur.execute("SELECT * FROM users WHERE discord_id = %s", (discordId, ))
      # Check if the user exists
      val = cur.fetchone()
      if val is None:
        # If the user doesn't exist, add them to the table
        # Generate a default UUID4 for the user as well
        id = str(uuid.uuid4())

        cur.execute("INSERT INTO users (discord_id, runescape_name, id) VALUES (%s, %s, %s)", (discordId, username, id))
      else:
        # If the user exists, update their username
        cur.execute("UPDATE users SET runescape_name = %s WHERE discord_id = %s", (username, discordId))
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
      cur.execute("SELECT * FROM users WHERE discord_id = %s AND runescape_name = %s", (discordId, username))
      if cur.fetchone() is None:
        return success

      # Remove the username from the user's discord account
      cur.execute("UPDATE users SET runescape_name = NULL WHERE discord_id = %s", (discordId, ))
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
      cur.execute("SELECT runescape_name FROM users WHERE discord_id = %s", (discordId, ))
      value = cur.fetchone()
      return value[0] if value is not None else None

def get_user_from_username(username):
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      # Get the user from the table
      cur.execute("SELECT discord_id FROM users WHERE runescape_name = %s", (username, ))
      value = cur.fetchone()
      return value[0] if value is not None else None

def get_users_from_id(discordId):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the user from the table
            cur.execute("SELECT runescape_name FROM users WHERE discord_id = %s", (discordId, ))
            value = cur.fetchone()
            return value[0] if value is not None else None

