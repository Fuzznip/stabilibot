import psycopg
from psycopg_pool import ConnectionPool
from psycopg.types.json import Jsonb

from dotenv import load_dotenv
load_dotenv()
import os

import wom

import json

dbpool = ConnectionPool(conninfo = os.getenv("DATABASE_URL"))

def ensure_user_db():
  with dbpool.connection() as conn:
    with conn.cursor() as cur:
      cur.execute("CREATE TABLE IF NOT EXISTS users (discord_id text PRIMARY KEY, username text[])")
      conn.commit()

async def add_user(discordId, username):
  # first, lowercase the username
  username = username.lower()

  success = False

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

def get_users_from_id(discordId):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the user from the table
            cur.execute("SELECT username FROM users WHERE discord_id = %s", (discordId, ))
            value = cur.fetchone()
            return value[0] if value is not None else None

def ensure_teams_table():
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Create teams table
            cur.execute("CREATE TABLE IF NOT EXISTS sp2teams (team SERIAL PRIMARY KEY, team_name TEXT, team_image TEXT, previous_tile INT, current_tile INT, stars INT, coins INT, coins_gained_this_tile INT, items INT[], buffs INT[], debuffs INT[], progress jsonb, ready BOOLEAN, rolling BOOLEAN, main_die_sides INT, main_die_modifier INT, extra_dice_sides INT[], role_id TEXT, text_channel_id TEXT, voice_channel_id TEXT, is_on_random_tile BOOLEAN, random_challenge INT)")
            conn.commit()

def ensure_tiles_db():
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Create tiles table
            cur.execute("CREATE TABLE IF NOT EXISTS sp2tiles (tile_id SERIAL PRIMARY KEY, tile_name TEXT, description TEXT, region_name TEXT, coin_challenge SERIAL references sp2challenges(id), task_challenge SERIAL references sp2challenges(id), region_challenge SERIAL references sp2challenges(id), has_star BOOLEAN, has_item_shop BOOLEAN, next_tiles INT[], position POINT)")
            conn.commit()

def ensure_task_db():
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Create tasks table
            cur.execute("CREATE TABLE IF NOT EXISTS sp2tasks (id SERIAL PRIMARY KEY, triggers INT[], quantity INT)")
            conn.commit()

def ensure_challenge_db():
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Create challenges table
            cur.execute("CREATE TABLE IF NOT EXISTS sp2challenges (id SERIAL PRIMARY KEY, name TEXT, description TEXT, tasks INT[])")
            conn.commit()

def ensure_trigger_db():
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Create triggers table
            cur.execute("CREATE TABLE IF NOT EXISTS sp2triggers (trigger_id SERIAL PRIMARY KEY, trigger TEXT, source TEXT)")
            conn.commit()

def ensure_global_challenges_list_db():
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Create global challenges list table
            cur.execute("CREATE TABLE IF NOT EXISTS sp2globalchallenges (id SERIAL PRIMARY KEY, challenges INT)")
            conn.commit()

def ensure_items_db():
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Create items table
            cur.execute("CREATE TABLE IF NOT EXISTS sp2items (id SERIAL PRIMARY KEY, name TEXT, description TEXT, selects_anyone BOOLEAN, selects_opponent BOOLEAN, has_quantity BOOLEAN, price INT, rarity INT, style TEXT)")
            conn.commit()
            
def get_tiles():
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get all the tiles from the table
            cur.execute("SELECT * FROM sp2tiles")
            values = cur.fetchall()
            return values

def get_teams():
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get all the teams from the table
            cur.execute("SELECT * FROM sp2teams")
            values = cur.fetchall()
            return values

def get_team_names():
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get all the team names from the table
            cur.execute("SELECT team_name FROM sp2teams")
            values = cur.fetchall()
            return [value[0] for value in values]

def get_team_id(team_name):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the team from the table
            cur.execute("SELECT team FROM sp2teams WHERE team_name = %s", (team_name, ))
            value = cur.fetchone()
            return value[0] if value is not None else None

def get_team_name(team_id):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the team from the table
            cur.execute("SELECT team_name FROM sp2teams WHERE team = %s", (team_id, ))
            value = cur.fetchone()
            return value[0] if value is not None else None

def create_team(team_name, roleId, textChannelId, voiceChannelId):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # If the team doesn't exist, add it to the table
            cur.execute("INSERT INTO sp2teams (team_name, previous_tile, current_tile, stars, coins, items, buffs, debuffs, progress, ready, main_die_sides, main_die_modifier, extra_dice_sides, role_id, text_channel_id, voice_channel_id) VALUES (%s, -1, -1, 0, 0, '{}', '{}', '{}', '{}'::jsonb, true, 4, 0, '{}', %s, %s, %s)", (team_name, roleId, textChannelId, voiceChannelId))
            conn.commit()

def delete_team(team_name):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # If the team exists, remove it from the table
            cur.execute("DELETE FROM sp2teams WHERE team_name = %s", (team_name, ))
            conn.commit()

def rename_team(team_name, new_name):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Rename the team
            cur.execute("UPDATE sp2teams SET team_name = %s WHERE team_name = %s", (new_name, team_name))
            conn.commit()

def team_exists(team_name):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Check if the team exists
            cur.execute("SELECT * FROM sp2teams WHERE team_name = %s", (team_name, ))
            return cur.fetchone() is not None

def get_role_id(team_name):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the team from the table
            cur.execute("SELECT role_id FROM sp2teams WHERE team_name = %s", (team_name, ))
            value = cur.fetchone()
            return int(value[0]) if value is not None else None

def get_text_channel_id(team_name):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the team from the table
            cur.execute("SELECT text_channel_id FROM sp2teams WHERE team_name = %s", (team_name, ))
            value = cur.fetchone()
            return int(value[0]) if value is not None else None

def get_voice_channel_id(team_name):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the team from the table
            cur.execute("SELECT voice_channel_id FROM sp2teams WHERE team_name = %s", (team_name, ))
            value = cur.fetchone()
            return int(value[0]) if value is not None else None

def ensure_sp2_users_db():
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Create users table
            cur.execute("CREATE TABLE IF NOT EXISTS sp2users (discord_id TEXT PRIMARY KEY, usernames TEXT[], team SERIAL REFERENCES sp2teams(team))")
            conn.commit()

def add_user_to_team(discordId, usernames, teamId):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # If the user doesn't exist, add them to the table
            cur.execute("INSERT INTO sp2users (discord_id, usernames, team) VALUES (%s, %s, %s)", (discordId, usernames, teamId))
            conn.commit()

def remove_user_from_team(discordId):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # If the user exists, remove them from the table
            cur.execute("DELETE FROM sp2users WHERE discord_id = %s", (discordId, ))
            conn.commit()

def user_in_team(discordId):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Check if the user is in a team
            cur.execute("SELECT * FROM sp2users WHERE discord_id = %s", (discordId, ))
            return cur.fetchone() is not None

def get_team(discordId):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the team from the table
            cur.execute("SELECT team FROM sp2users WHERE discord_id = %s", (discordId, ))
            value = cur.fetchone()
            return value[0] if value is not None else None

def is_team_ready_to_roll(team):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the team from the table
            cur.execute("SELECT ready FROM sp2teams WHERE team = %s", (team, ))
            value = cur.fetchone()
            return value[0] if value is not None else None

def is_team_rolling(team):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the team from the table
            cur.execute("SELECT rolling FROM sp2teams WHERE team = %s", (team, ))
            value = cur.fetchone()
            return value[0] if value is not None else None

def get_current_tile(team):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the team from the table
            cur.execute("SELECT current_tile FROM sp2teams WHERE team = %s", (team, ))
            value = cur.fetchone()
            return value[0] if value is not None else None

def get_tile_name(team):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the team from the table
            cur.execute("SELECT tile_name FROM sp2tiles WHERE tile_id = %s", (team, ))
            value = cur.fetchone()
            return value[0] if value is not None else None

def get_next_tiles(tile):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the team from the table
            cur.execute("SELECT next_tiles FROM sp2tiles WHERE tile_id = %s", (tile, ))
            value = cur.fetchone()
            return value[0] if value is not None else []

def get_main_die_sides(team):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the team from the table
            cur.execute("SELECT main_die_sides FROM sp2teams WHERE team = %s", (team, ))
            value = cur.fetchone()
            return value[0] if value is not None else 0

def get_main_die_modifier(team):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the team from the table
            cur.execute("SELECT main_die_modifier FROM sp2teams WHERE team = %s", (team, ))
            value = cur.fetchone()
            return value[0] if value is not None else 0

def get_extra_die_sides(team):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the team from the table
            cur.execute("SELECT extra_dice_sides FROM sp2teams WHERE team = %s", (team, ))
            value = cur.fetchone()
            return value[0] if value is not None else []

def set_team_ready_to_roll(team):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Set the team to ready to roll
            cur.execute("UPDATE sp2teams SET ready = true WHERE team = %s", (team, ))
            conn.commit()

def set_team_not_ready_to_roll(team):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Set the team to not ready to roll
            cur.execute("UPDATE sp2teams SET ready = false WHERE team = %s", (team, ))
            conn.commit()

def set_team_rolling(team):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Set the team to rolling
            cur.execute("UPDATE sp2teams SET rolling = true WHERE team = %s", (team, ))
            conn.commit()

def set_team_not_rolling(team):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Set the team to not rolling
            cur.execute("UPDATE sp2teams SET rolling = false WHERE team = %s", (team, ))
            conn.commit()

def set_current_tile(team, tile):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Set the tile for the team
            cur.execute("UPDATE sp2teams SET current_tile = %s WHERE team = %s", (tile, team))
            conn.commit()

def set_previous_tile(team, tile):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Set the previous tile for the team
            cur.execute("UPDATE sp2teams SET previous_tile = %s WHERE team = %s", (tile, team))
            conn.commit()

def get_previous_tile(team):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the team from the table
            cur.execute("SELECT previous_tile FROM sp2teams WHERE team = %s", (team, ))
            value = cur.fetchone()
            return value[0] if value is not None else None

def get_coins(team):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the team from the table
            cur.execute("SELECT coins FROM sp2teams WHERE team = %s", (team, ))
            value = cur.fetchone()
            return value[0] if value is not None else 0

def set_coins(team, coins):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Set the coins for the team
            cur.execute("UPDATE sp2teams SET coins = %s WHERE team = %s", (coins, team))
            conn.commit()

def get_stars(team):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the team from the table
            cur.execute("SELECT stars FROM sp2teams WHERE team = %s", (team, ))
            value = cur.fetchone()
            return value[0] if value is not None else 0

def set_stars(team, stars):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Set the stars for the team
            cur.execute("UPDATE sp2teams SET stars = %s WHERE team = %s", (stars, team))
            conn.commit()

def get_challenge_name(challenge):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the challenge from the table
            cur.execute("SELECT name FROM sp2challenges WHERE id = %s", (challenge, ))
            value = cur.fetchone()
            return value[0] if value is not None else None

def get_challenge_description(challenge):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the challenge from the table
            cur.execute("SELECT description FROM sp2challenges WHERE id = %s", (challenge, ))
            value = cur.fetchone()
            return value[0] if value is not None else None

def get_challenge_tasks(challenge):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the challenge from the table
            cur.execute("SELECT tasks FROM sp2challenges WHERE id = %s", (challenge, ))
            value = cur.fetchone()
            return value[0] if value is not None else None

def get_task_triggers(task):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the task from the table
            cur.execute("SELECT triggers FROM sp2tasks WHERE id = %s", (task, ))
            value = cur.fetchone()
            return value[0] if value is not None else None

def get_trigger_and_source(trigger):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the trigger from the table
            cur.execute("SELECT trigger, source FROM sp2triggers WHERE trigger_id = %s", (trigger, ))
            value = cur.fetchone()
            return value[0], value[1] if value is not None else None

def get_task_quantity(task):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the task from the table
            cur.execute("SELECT quantity FROM sp2tasks WHERE id = %s", (task, ))
            value = cur.fetchone()
            return value[0] if value is not None else None

def get_team_tile(team):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the team from the table
            cur.execute("SELECT current_tile FROM sp2teams WHERE team = %s", (team, ))
            value = cur.fetchone()
            return value[0] if value is not None else None

def get_team_stars(team):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the team from the table
            cur.execute("SELECT stars FROM sp2teams WHERE team = %s", (team, ))
            value = cur.fetchone()
            return value[0] if value is not None else None

def get_team_coins(team):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the team from the table
            cur.execute("SELECT coins FROM sp2teams WHERE team = %s", (team, ))
            value = cur.fetchone()
            return value[0] if value is not None else None

def get_team_items(team):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the team from the table
            cur.execute("SELECT items FROM sp2teams WHERE team = %s", (team, ))
            value = cur.fetchone()
            return value[0] if value is not None else None

def get_coin_challenge(tile):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the tile from the table
            cur.execute("SELECT coin_challenge FROM sp2tiles WHERE tile_id = %s", (tile, ))
            value = cur.fetchone()
            return value[0] if value is not None else None

def get_tile_challenge(tile):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the tile from the table
            cur.execute("SELECT task_challenge FROM sp2tiles WHERE tile_id = %s", (tile, ))
            value = cur.fetchone()
            return value[0] if value is not None else None

def get_region_challenge(tile):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the tile from the table
            cur.execute("SELECT region_challenge FROM sp2tiles WHERE tile_id = %s", (tile, ))
            value = cur.fetchone()
            return value[0] if value is not None else None

def get_global_challenge():
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the global challenge from the table
            cur.execute("SELECT global_challenge FROM sp2game WHERE game_id = 1")
            value = cur.fetchone()
            return value[0] if value is not None else None

def set_global_challenge(challenge):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Set the global challenge
            cur.execute("UPDATE sp2game SET global_challenge = %s WHERE game_id = 1", (challenge, ))
            conn.commit()

def set_main_die_side(team, sides):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Set the main die sides for the team
            cur.execute("UPDATE sp2teams SET main_die_sides = %s WHERE team = %s", (sides, team))
            conn.commit()

def set_main_die_modifier(team, modifier):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Set the main die modifier for the team
            cur.execute("UPDATE sp2teams SET main_die_modifier = %s WHERE team = %s", (modifier, team))
            conn.commit()

def set_extra_die_sides(team, sides):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Set the extra die sides for the team
            cur.execute("UPDATE sp2teams SET extra_dice_sides = %s WHERE team = %s", (sides, team))
            conn.commit()

def get_tile_positions():
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the tile positions from the table
            cur.execute("SELECT tile_id FROM sp2tiles")
            values = cur.fetchall()
            return [value[0] for value in values]


def has_star(tile):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Check if the tile has a star
            cur.execute("SELECT has_star FROM sp2tiles WHERE tile_id = %s", (tile, ))
            value = cur.fetchone()
            return value[0] if value is not None else False

def has_item_shop(tile):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Check if the tile has an item shop
            cur.execute("SELECT has_item_shop FROM sp2tiles WHERE tile_id = %s", (tile, ))
            value = cur.fetchone()
            return value[0] if value is not None else False

def count_teams_on_tile(tile):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the tile from the table
            cur.execute("SELECT COUNT(*) FROM sp2teams WHERE current_tile = %s", (tile, ))
            value = cur.fetchone()
            return value[0] if value is not None else 0

def set_star(tile):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Set the tile to have a star
            cur.execute("UPDATE sp2tiles SET has_star = true WHERE tile_id = %s", (tile, ))
            conn.commit()

def set_item_shop(tile):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Set the tile to have an item shop
            cur.execute("UPDATE sp2tiles SET has_item_shop = true WHERE tile_id = %s", (tile, ))
            conn.commit()

def unset_star(tile):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Set the tile to not have a star
            cur.execute("UPDATE sp2tiles SET has_star = false WHERE tile_id = %s", (tile, ))
            conn.commit()

def unset_item_shop(tile):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Set the tile to not have an item shop
            cur.execute("UPDATE sp2tiles SET has_item_shop = false WHERE tile_id = %s", (tile, ))
            conn.commit()

def get_all_items():
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get all the items from the table
            cur.execute("SELECT * FROM sp2items")
            values = cur.fetchall()
            return values

def add_item_to_team(team, item):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the team from the table
            cur.execute("SELECT items FROM sp2teams WHERE team = %s", (team, ))
            value = cur.fetchone()
            items = value[0] if value is not None else []
            items.append(item)
            # Add the item to the team
            cur.execute("UPDATE sp2teams SET items = %s WHERE team = %s", (items, team))
            conn.commit()

def get_progress(team):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the team from the table
            cur.execute("SELECT progress FROM sp2teams WHERE team = %s", (team, ))
            value = cur.fetchone()
            return value[0] if value is not None else None

def get_team_image(team):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the team from the table
            cur.execute("SELECT team_image FROM sp2teams WHERE team = %s", (team, ))
            value = cur.fetchone()
            return value[0] if value is not None else ""

def get_tile_position(tile):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the tile from the table
            cur.execute("SELECT position FROM sp2tiles WHERE tile_id = %s", (tile, ))
            value = cur.fetchone()
            return value[0] if value is not None else None

def get_star_tiles():
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the star tiles from the table
            cur.execute("SELECT tile_id FROM sp2tiles WHERE has_star = true")
            values = cur.fetchall()
            return [value[0] for value in values]

def get_item_shop_tiles():
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the item shop tiles from the table
            cur.execute("SELECT tile_id FROM sp2tiles WHERE has_item_shop = true")
            values = cur.fetchall()
            return [value[0] for value in values]

def get_items(team):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the team from the table
            cur.execute("SELECT items FROM sp2teams WHERE team = %s", (team, ))
            value = cur.fetchone()
            return value[0] if value is not None else []

def get_item(item):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the item from the table
            cur.execute("SELECT * FROM sp2items WHERE id = %s", (item, ))
            value = cur.fetchone()
            return value if value is not None else None

def get_item_name(item):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the item from the table
            cur.execute("SELECT name FROM sp2items WHERE id = %s", (item, ))
            value = cur.fetchone()
            return value[0] if value is not None else None

def give_team_die(team, die_sides):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the team from the table
            cur.execute("SELECT extra_dice_sides FROM sp2teams WHERE team = %s", (team, ))
            value = cur.fetchone()
            extra_dice_sides = value[0] if value is not None else []
            extra_dice_sides.append(die_sides)
            # Give the team the die
            cur.execute("UPDATE sp2teams SET extra_dice_sides = %s WHERE team = %s", (extra_dice_sides, team))
            conn.commit()

def remove_item(team, item):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the team from the table
            cur.execute("SELECT items FROM sp2teams WHERE team = %s", (team, ))
            value = cur.fetchone()
            items = value[0] if value is not None else []
            items.remove(item)
            # Remove the item from the team
            cur.execute("UPDATE sp2teams SET items = %s WHERE team = %s", (items, team))
            conn.commit()

def add_team_modifier(team, modifier):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the team from the table
            cur.execute("UPDATE sp2teams SET main_die_modifier = main_die_modifier + %s WHERE team = %s", (modifier, team))
            conn.commit()

def get_global_challenges():
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the global challenges from the table
            # Return challenges from all rows
            cur.execute("SELECT challenges FROM sp2globalchallenges")
            value = cur.fetchone()
            return value[0] if value is not None else []

def ensure_random_challenges_db():
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Create random challenges table
            cur.execute("CREATE TABLE IF NOT EXISTS sp2randomchallenges (id SERIAL PRIMARY KEY, challenge INT)")
            conn.commit()

def get_all_random_challenges():
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Get the global challenges from the table
            cur.execute("SELECT * FROM sp2randomchallenges")
            value = cur.fetchone()
            return value if value is not None else None

def set_team_random_challenge(team, challenge):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Set the team random challenge
            cur.execute("UPDATE sp2teams SET random_challenge = %s WHERE team = %s", (challenge, team))
            conn.commit()

def set_team_is_doing_random_challenge(team):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Set the team to be doing a random challenge
            cur.execute("UPDATE sp2teams SET is_on_random_tile = true WHERE team = %s", (team, ))
            conn.commit()

def set_team_is_not_doing_random_challenge(team):
    with dbpool.connection() as conn:
        with conn.cursor() as cur:
            # Set the team to not be doing a random challenge
            cur.execute("UPDATE sp2teams SET is_on_random_tile = false WHERE team = %s", (team, ))
            conn.commit()

# def ensure_teams_table():
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Create the teams table
#       # team: the name of the team
#       # tile: the current tile the team is on
#       # discord_ids: the discord ids of the users on the team
#       # items: the items the team has
#       # ready: whether the team is ready to roll
#       # stars: the number of stars the team has
#       # coins: the number of coins the team has
#       # tile_progress: the progress the team has made on various tiles
#       # last_roll_time: the time the team last rolled
#       cur.execute("""CREATE TABLE IF NOT EXISTS teams (
#                   team text PRIMARY KEY, 
#                   tile int, 
#                   tile_blockers jsonb[] DEFAULT '{}'::jsonb[],
#                   last_tile int,
#                   roll_size int DEFAULT 4,
#                   roll_modifier int DEFAULT 0,
#                   discord_ids text[], 
#                   items text[], 
#                   ready boolean, 
#                   stars int DEFAULT 0, 
#                   coins int DEFAULT 0, 
#                   tile_progress jsonb DEFAULT '{}'::jsonb,
#                   side_progress jsonb DEFAULT '{}'::jsonb,
#                   last_roll_time timestamp DEFAULT now())""")
#       conn.commit()
#
# def get_teams():
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Get all the teams from the table
#       cur.execute("SELECT * FROM teams")
#       values = cur.fetchall()
#       return values
#
# def get_team_names():
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Get all the team names from the table
#       cur.execute("SELECT team FROM teams")
#       values = cur.fetchall()
#       return [value[0] for value in values]
#
# def create_team(team):
#   success = False
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Check if the team already exists
#       cur.execute("SELECT * FROM teams WHERE team = %s", (team, ))
#       if cur.fetchone() is not None:
#         return success
#
#       # If the team doesn't exist, add it to the table
#       cur.execute("""INSERT INTO teams (
#                   team, 
#                   tile, 
#                   tile_blockers,
#                   last_tile,
#                   roll_size,
#                   roll_modifier,
#                   discord_ids, 
#                   items, 
#                   ready, 
#                   stars, 
#                   coins, 
#                   tile_progress,
#                   side_progress,
#                   last_roll_time
#                   ) VALUES (
#                   %s, 
#                   -1,
#                   '{}'::jsonb[], 
#                   -1,
#                   4,
#                   0,
#                   '{}', 
#                   '{}', 
#                   true, 
#                   0, 
#                   0, 
#                   '{}'::jsonb,
#                   '{}'::jsonb,
#                   now()
#                   )""", (team, ))
#       conn.commit()
#       success = True
#
#   return success
#
# def delete_team(team):
#   success = False
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Check if the team exists
#       cur.execute("SELECT * FROM teams WHERE team = %s", (team, ))
#       if cur.fetchone() is None:
#         return success
#
#       # If the team exists, remove it from the table
#       cur.execute("DELETE FROM teams WHERE team = %s", (team, ))
#       conn.commit()
#       success = True
#
#   return success
#
# def team_exists(team): 
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Check if the team exists
#       cur.execute("SELECT * FROM teams WHERE team = %s", (team, ))
#       return cur.fetchone() is not None
#
# def get_team(discordId):
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Get the team from the table
#       cur.execute("SELECT team FROM teams WHERE discord_ids @> %s", ([discordId], ))
#       value = cur.fetchone()
#       return value[0] if value is not None else None
#
# def add_player(team, user):
#   success = False
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Get the discord id from the username
#       cur.execute("SELECT discord_id FROM users WHERE username @> %s", ([user], ))
#       value = cur.fetchone()
#       if value is None:
#         return success
#       
#       # Check if the user is already on a team
#       cur.execute("SELECT * FROM teams WHERE discord_ids @> %s", ([value[0]], ))
#       if cur.fetchone() is not None:
#         return success
#       
#       # Add the user to the team
#       cur.execute("UPDATE teams SET discord_ids = array_append(teams.discord_ids, %s) WHERE team = %s", (value[0], team))
#       conn.commit()
#       success = True
#
#   return success
#
# def remove_player(team, user):
#   success = False
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Get the discord id from the username
#       cur.execute("SELECT discord_id FROM users WHERE username @> %s", ([user], ))
#       value = cur.fetchone()
#       if value is None:
#         return success
#       
#       # Check if the user is on the team
#       cur.execute("SELECT * FROM teams WHERE discord_ids @> %s", ([value[0]], ))
#       if cur.fetchone() is None:
#         return success
#       
#       # Remove the user from the team
#       cur.execute("UPDATE teams SET discord_ids = array_remove(teams.discord_ids, %s) WHERE team = %s", ('88087113626587136', team))
#       conn.commit()
#       success = True
#
#   return success
#
# def is_team_ready(team):
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Get the team from the table
#       cur.execute("SELECT ready FROM teams WHERE team = %s", (team, ))
#       value = cur.fetchone()
#       return value[0] if value is not None else None
#     
# def move_team(team, roll, max_tile = 20):
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       looped = False
#
#       # Check if the team has reached the end
#       cur.execute("SELECT tile FROM teams WHERE team = %s", (team, ))
#       value = cur.fetchone()
#       
#       if value[0] + roll > max_tile:
#         # Loop back to the beginning
#         cur.execute("UPDATE teams SET tile = %s WHERE team = %s", (value[0] + roll - max_tile - 1, team))
#         looped = True
#       else:
#         # Move the team forward
#         cur.execute("UPDATE teams SET tile = tile + %s WHERE team = %s", (roll, team))
#
#       # Set the previous tile
#       cur.execute("UPDATE teams SET last_tile = %s WHERE team = %s", (value[0], team))
#
#       # Set the team to not ready and last roll time to now
#       cur.execute("UPDATE teams SET ready = false, last_roll_time = now() WHERE team = %s", (team, ))
#       conn.commit()
#
#       return looped
#
# def get_team_tile(team):
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Get the team from the table
#       cur.execute("SELECT tile FROM teams WHERE team = %s", (team, ))
#       value = cur.fetchone()
#       return value[0] if value is not None else None
#     
# def get_previous_tile(team):
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Get the team from the table
#       cur.execute("SELECT last_tile FROM teams WHERE team = %s", (team, ))
#       value = cur.fetchone()
#       return value[0] if value is not None else None
#
# def set_team_tile(team, tile):
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Set the tile for the team
#       cur.execute("UPDATE teams SET tile = %s WHERE team = %s", (tile, team))
#       conn.commit()
#
# def complete_tile(team):
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Complete the tile
#       cur.execute("UPDATE teams SET ready = true WHERE team = %s", (team, ))
#
#       # Get the tile from the table
#       cur.execute("SELECT tile FROM teams WHERE team = %s", (team, ))
#       value = cur.fetchone()
#       tile = value[0]
#
#       # Reset the "gained" field in the side progress
#       # Get the side progress from the table as a json
#       cur.execute("SELECT side_progress FROM teams WHERE team = %s", (team, ))
#       value = json.dumps(cur.fetchall())
#       value_dict = json.loads(value)[0][0]
#       if value_dict and str(tile) in value_dict:
#         for key in value_dict[str(tile)]:
#           value_dict[str(tile)][key]["gained"] = 0
#         cur.execute("UPDATE teams SET side_progress = jsonb_set(side_progress, %s, %s) WHERE team = %s", ([str(tile)], json.dumps(value_dict[str(tile)]), team))
#
#       # Reset the "value" field in the main progress
#       # Get the main progress from the table as a json
#       cur.execute("SELECT tile_progress FROM teams WHERE team = %s", (team, ))
#       value = json.dumps(cur.fetchall())
#       value_dict = json.loads(value)[0][0]
#       if value_dict and str(tile) in value_dict:
#         for key in value_dict[str(tile)]:
#           value_dict[str(tile)][key]["value"] = 0
#         cur.execute("UPDATE teams SET tile_progress = jsonb_set(tile_progress, %s, %s) WHERE team = %s", ([str(tile)], json.dumps(value_dict[str(tile)]), team))
#
#       conn.commit()
#
# def get_star_count(team):
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Get the team from the table
#       cur.execute("SELECT stars FROM teams WHERE team = %s", (team, ))
#       value = cur.fetchone()
#       return value[0] if value is not None else None
#
# def add_star(team):
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Add a star to the team
#       cur.execute("UPDATE teams SET stars = stars + 1 WHERE team = %s", (team, ))
#       conn.commit()
#
# def add_stars(team, count):
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Add stars to the team
#       cur.execute("UPDATE teams SET stars = stars + %s WHERE team = %s", (count, team))
#       conn.commit()
#
# def set_stars(team, stars):
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Set the stars for the team
#       cur.execute("UPDATE teams SET stars = %s WHERE team = %s", (stars, team))
#       conn.commit()
#
# def add_coins(team, coins):
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Add coins to the team
#       cur.execute("UPDATE teams SET coins = coins + %s WHERE team = %s", (coins, team))
#       conn.commit()
#
# def set_coins(team, coins):
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Add coins to the team
#       cur.execute("UPDATE teams SET coins = coins + %s WHERE team = %s", (coins, team))
#       conn.commit()
#
# def get_coin_count(team):
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Get the team from the table
#       cur.execute("SELECT coins FROM teams WHERE team = %s", (team, ))
#       value = cur.fetchone()
#       return value[0] if value is not None else None
#
# def get_items(team):
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Get the team from the table
#       cur.execute("SELECT items FROM teams WHERE team = %s", (team, ))
#       value = cur.fetchone()
#       return value[0] if value is not None else None
#
# def add_item(team, item):
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Add an item to the team
#       cur.execute("UPDATE teams SET items = array_append(teams.items, %s) WHERE team = %s", (str(item), team))
#       conn.commit()
#
# def remove_item(team, item):
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # get the items from the team
#       cur.execute("SELECT items FROM teams WHERE team = %s", (team, ))
#       value = cur.fetchone()
#       if value is None:
#         return
#       
#       # Remove the first instance of the item from the array
#       if item in value[0]:
#         items = value[0]
#         items.remove(item)
#
#       cur.execute("UPDATE teams SET items = %s WHERE team = %s", (items, team))
#       conn.commit()
#
# def add_tile_blocker(team, tile_blocker):
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Get the array of tile blockers from the team
#       cur.execute("SELECT tile_blockers FROM teams WHERE team = %s", (team, ))
#
#       # If the team doesn't have any tile blockers, set the array to an empty array
#       value = cur.fetchone()
#       if value is None:
#         cur.execute("UPDATE teams SET tile_blockers = %s WHERE team = %s", ([tile_blocker], team))
#         conn.commit()
#         return
#       
#       # Otherwise add the tile blocker to the array
#       cur.execute("UPDATE teams SET tile_blockers = array_append(teams.tile_blockers, %s) WHERE team = %s", (Jsonb(tile_blocker), team))
#       conn.commit()
#
# def get_roll_size(team):
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Get the team from the table
#       cur.execute("SELECT roll_size FROM teams WHERE team = %s", (team, ))
#       value = cur.fetchone()
#       return value[0] if value is not None else None
#     
# def get_roll_modifier(team):
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Get the team from the table
#       cur.execute("SELECT roll_modifier FROM teams WHERE team = %s", (team, ))
#       value = cur.fetchone()
#       return value[0] if value is not None else None
#
# def set_roll_modifier(team, modifier):
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Set the roll modifier for the team
#       cur.execute("UPDATE teams SET roll_modifier = %s WHERE team = %s", (modifier, team))
#       conn.commit()
#
# def set_roll_size(team, size):
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Set the roll size for the team
#       cur.execute("UPDATE teams SET roll_size = %s WHERE team = %s", (size, team))
#       conn.commit()
#
# def get_tile(tile_id):
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Get the tile from the table
#       cur.execute("SELECT * FROM tiles WHERE tile_id = %s", (tile_id, ))
#       value = cur.fetchone()
#       return value if value is not None else None
#
# def get_item_name(item_id):
#   item_classes = [
#     "SucksToSuck", # 0
#     "SwitchItUp", # 1
#     "StealAStar", # 2
#     "TimeToSkill",  # 3
#     "Deny", # 4
#     "Reroll", # 5
#     "FourPlusFour", # 6
#     "Teleport",   # 7
#     "ThankYouNext", # 8
#     "CustomDie" # 9
#   ]
#
#   return item_classes[item_id]
#
# def get_main_progress(team, tile):
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Get the main progress from the table as a json
#       cur.execute("SELECT tile_progress FROM teams WHERE team = %s", (team, ))
#       value = json.dumps(cur.fetchall())
#       value_dict = json.loads(value)[0][0]
#       if value_dict is None:
#         return None
#       
#       # loop through value tuple
#       if str(tile) not in value_dict:
#         return {}
#       
#       return value_dict[str(tile)]
#
# def get_side_progress(team, tile):
#   with dbpool.connection() as conn:
#     with conn.cursor() as cur:
#       # Get the side progress from the table as a json
#       cur.execute("SELECT side_progress FROM teams WHERE team = %s", (team, ))
#       value = json.dumps(cur.fetchall())
#       value_dict = json.loads(value)[0][0]
#       if value_dict is None:
#         return None
#       
#       # loop through value tuple
#       if str(tile) not in value_dict:
#         return {}
#       
#       return value_dict[str(tile)]
