from discord.ext import commands
import discord
from dotenv import load_dotenv
load_dotenv()
import os
import json
import aiohttp
import asyncio
from typing import Dict, Any, Optional
import logging
import traceback
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("event_rolls.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("event_user")

# Roll progression data class
class RollProgressionPayload:
    def __init__(self, data: dict):
        self.raw_data = data
        # Use action_required as the primary type indicator
        self.action_required = data.get("action_required")
        # The nested action_data contains specifics for the current action
        self.data = data.get("action_data", {}) 
        
        self.eventId = data.get("event_id")
        self.teamId = data.get("team_id")
        self.startingTileId = data.get("starting_tile_id")
        self.currentTileId = data.get("current_tile_id")
        
        # These are overall roll state values for the current turn/movement sequence
        self.roll_total_for_turn = data.get("roll_total_for_turn") 
        self.roll_remaining = data.get("roll_remaining")
        self.dice_results_for_roll = data.get("dice_results_for_roll", [])
        self.modifier_for_roll = data.get("modifier_for_roll", 0)
        self.path_taken_this_turn = data.get("path_taken_this_turn", [])

    # For convenience if 'rollType' was used before, map it to action_required
    @property
    def rollType(self):
        return self.action_required

    # Convenience accessors for data that might be at top level or in action_data
    # For "first_roll", dice results and roll total are in action_data
    def get_current_action_dice_results(self):
        if self.action_required == "first_roll":
            return self.data.get("dice_results_for_roll", [])
        return self.dice_results_for_roll

    def get_current_action_modifier(self):
        if self.action_required == "first_roll":
            return self.data.get("modifier_for_roll", 0)
        return self.modifier_for_roll

    def get_current_action_roll_total(self):
        if self.action_required == "first_roll":
            return self.data.get("roll_total_for_turn")
        return self.roll_total_for_turn

class EventUser(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = os.getenv("BACKEND_URL")
        # Dictionary to track active rolls and who initiated them
        self.active_rolls: Dict[str, str] = {}  # team_id -> discord_user_id
        self.active_item_views: Dict[str, discord.ui.View] = {}  # team_id -> discord.ui.View
        # Add a dictionary to store the original roll messages
        self.roll_messages: Dict[str, discord.Message] = {}  # team_id -> discord.Message
        logger.info(f"EventUser cog initialized with backend URL: {self.backend_url}")
    
    # Helper to get the first active stability party event
    async def get_active_event(self, interaction):
        logger.debug(f"Getting active event for user: {interaction.user.id}")
        # Fetch available events
        success, events = await self.call_backend_api(
            "/events",
            method="GET"
        )
        
        if not success:
            return None, f"Failed to retrieve events: {events}"
        
        if len(events) == 0:
            logger.warning("No active events found")
            return None, "No active events found."

        # Return the first active event with type "STABILITY_PARTY"
        for event in events:
            if event.get("type") == "STABILITY_PARTY":
                logger.info(f"Active event found: {event['id']}")
                return event, None
            
        logger.warning("No active stability party events found")
        return None, "No active stability party events found."
    
    # Helper method to get the user's team
    async def get_user_team(self, interaction, event_id):
        discord_id = str(interaction.user.id)
        logger.debug(f"Getting team for user {discord_id} in event {event_id}")
        
        # Call the API to get the user's team
        success, response_data = await self.call_backend_api(
            f"/events/{event_id}/users/{discord_id}/team",
            method="GET"
        )
        
        if not success:
            logger.error(f"Failed to retrieve team for user {discord_id}: {response_data}")
            return None, f"Failed to retrieve team."
        
        logger.debug(f"Team data received for user {discord_id}: {response_data}")
        
        # The API should return the team ID and team info
        team_id = response_data.get("id")
        
        if not team_id:
            logger.warning(f"User {discord_id} is not part of any team for event {event_id}")
            return None, "You are not part of any team for this event."
        
        logger.info(f"User {discord_id} belongs to team {team_id} in event {event_id}")
        return team_id, None
    
    # Helper method to make API calls to the backend
    async def call_backend_api(self, endpoint, payload=None, method="GET"):
        url = f"{self.backend_url}{endpoint}"
        logger.debug(f"API call: {method} {url} - Payload: {payload}")
        
        # Define common headers
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        try:
            start_time = datetime.now()
            async with aiohttp.ClientSession() as session:
                if method == "GET":
                    # For GET requests, we don't send a Content-Type header since there's no body
                    async with session.get(url, headers={"Accept": "application/json"}) as response:
                        elapsed = (datetime.now() - start_time).total_seconds() * 1000
                        if response.status in [200, 201]:
                            try:
                                data = await response.json()
                                logger.debug(f"API response ({elapsed:.2f}ms): {method} {url} - Status: {response.status} - Response size: {len(str(data))} chars")
                            except aiohttp.ContentTypeError:
                                # Handle non-JSON responses
                                data = await response.text()
                                logger.warning(f"Non-JSON response ({elapsed:.2f}ms): {method} {url} - Status: {response.status} - Data: {data[:100]}...")
                            
                            # Handle string data (possibly JSON)
                            if isinstance(data, str):
                                try:
                                    return True, json.loads(data)
                                except json.JSONDecodeError:
                                    logger.warning(f"Failed to decode JSON string: {data[:100]}...")
                                    return True, data
                            return True, data
                        else:
                            error_text = await response.text()
                            logger.error(f"API error ({elapsed:.2f}ms): {method} {url} - Status: {response.status} - Error: {error_text}")
                            return False, f"Error: {response.status} - {error_text}"
                
                elif method == "POST":
                    async with session.post(url, json=payload, headers=headers) as response:
                        elapsed = (datetime.now() - start_time).total_seconds() * 1000
                        if response.status in [200, 201]:
                            data = await response.json()
                            logger.debug(f"API response ({elapsed:.2f}ms): {method} {url} - Status: {response.status} - Response size: {len(str(data))} chars")
                        else:
                            error_text = await response.text()
                            logger.error(f"API error ({elapsed:.2f}ms): {method} {url} - Status: {response.status} - Error: {error_text}")
                            return False, f"Error: {response.status} - {error_text}"
                
                elif method == "PUT":
                    async with session.put(url, json=payload, headers=headers) as response:
                        if response.status in [200, 201]:
                            data = await response.json()
                        else:
                            error_text = await response.text()
                            print(f"Error calling {url}: {response.status} - {error_text}")
                            return False, f"Error: {response.status} - {error_text}"
                
                elif method == "DELETE":
                    # For DELETE with payload, include headers
                    if payload:
                        async with session.delete(url, json=payload, headers=headers) as response:
                            if response.status in [200, 201]:
                                try:
                                    data = await response.json()
                                except:
                                    # Some DELETE endpoints might not return JSON
                                    return True, {}
                            else:
                                error_text = await response.text()
                                print(f"Error calling {url}: {response.status} - {error_text}")
                                return False, f"Error: {response.status} - {error_text}"
                    else:
                        # For DELETE without payload, don't include Content-Type header
                        async with session.delete(url, headers={"Accept": "application/json"}) as response:
                            if response.status in [200, 201]:
                                try:
                                    data = await response.json()
                                except:
                                    # Some DELETE endpoints might not return JSON
                                    return True, {}
                            else:
                                error_text = await response.text()
                                print(f"Error calling {url}: {response.status} - {error_text}")
                                return False, f"Error: {response.status} - {error_text}"
            
            # Handle the case where it's a list
            if isinstance(data, list):
                return True, {"items": data}
            return True, data
                
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Connection error to {url}: {str(e)}", exc_info=True)
            return False, f"Connection error: Failed to connect to the backend service. (Start aggressively screenshotting your progress for proof!)"
        except Exception as e:
            logger.error(f"Unexpected error calling {url}: {str(e)}", exc_info=True)
            logger.error(traceback.format_exc())
            return False, f"Unexpected error: {str(e)}"
    
    
    @discord.slash_command(name="stats", description="View your team's current stats and location, as well as event news and info", guild_ids=[int(os.getenv("GUILD_ID"))])
    async def get_stats(self, interaction):
        logger.info(f"{interaction.user.display_name} ({interaction.user.id}): /event_stats")
        
        await interaction.response.defer(ephemeral=False)
        
        # Get the first active event
        event, error = await self.get_active_event(interaction)
        if error:
            await interaction.followup.send(error)
            return
            
        event_id = event.get('id')
        
        # Get the user's team
        team_id, error = await self.get_user_team(interaction, event_id)
        if error:
            await interaction.followup.send(error)
            return
        
        # Get team stats
        success, response_data = await self.call_backend_api(
            f"/events/{event_id}/teams/{team_id}/stats",
            method="GET"
        )
        
        if not success:
            await interaction.followup.send(f"Failed to get team stats: {response_data}")
            return
        
        # Extract essential information
        team_name = response_data.get("team_name", "Unknown Team")
        stars = response_data.get("stars", 0)
        coins = response_data.get("coins", 0)
        
        # Get location info
        current_location = response_data.get("current_location", {})
        tile_info = current_location.get("tile_info", {})
        region_info = current_location.get("region", {})
        current_region_name = region_info.get("name", "Unknown Region")
        tile_completed = response_data.get("tile_completed", False)
        is_rolling = response_data.get("is_rolling", False)
        
        # Get event star locations
        event_star_locations = response_data.get("event_star_locations", [])
        
        # Build the embed
        embed = discord.Embed(
            title=f"{team_name}",
            description=f"**Current Status:** {'✅ Completed' if tile_completed else '🔄 In Progress'}{' (Rolling)' if is_rolling else ''}",
            color=discord.Color.gold() if stars > 0 else discord.Color.blue()
        )
        
        # Add basic stats
        embed.add_field(name="⭐ Stars", value=str(stars), inline=True)
        embed.add_field(name="💰 Coins", value=str(coins), inline=True)
        
        # Add current location info
        location_value = f"{tile_info.get('name', 'Unknown Tile')}"
        if region_info:
            location_value += f"\nRegion: **{current_region_name}**"
        
        embed.add_field(name="📍 Current Location", value=location_value, inline=False)
        
        # Add event star locations, highlighting those in the team's current region
        if event_star_locations:
            star_locations_text = ""
            for location in event_star_locations:
                star_region = location.get("region", "Unknown")
                star_name = location.get("name", "Unknown")
                star_description = location.get("description", "")
                
                # Highlight stars in the current region
                if star_region == current_region_name:
                    star_locations_text += f"**▶️ {star_name}** - {star_region} 🔍\n"
                    if star_description:
                        star_locations_text += f"   *{star_description}*\n"
                else:
                    star_locations_text += f"• {star_name} - {star_region}\n"
            
            embed.add_field(name="⭐ Event Star Locations", value=star_locations_text or "None available", inline=False)
        
        await interaction.followup.send(embed=embed)
    
    # Get Tile Progress Command
    @discord.slash_command(name="progress", description="View your team's current tile progress", guild_ids=[int(os.getenv("GUILD_ID"))])
    async def get_tile_progress(self, interaction):
        logger.info(f"{interaction.user.display_name} ({interaction.user.id}): /event_progress")
        
        await interaction.response.defer(ephemeral=False)
        
        # Get the first active event
        event, error = await self.get_active_event(interaction)
        if error:
            await interaction.followup.send(error)
            return
            
        event_id = event.get('id')
        
        # Get the user's team
        team_id, error = await self.get_user_team(interaction, event_id)
        if error:
            await interaction.followup.send(error)
            return
        
        # Get tile progress
        success, response_data = await self.call_backend_api(
            f"/events/{event_id}/teams/{team_id}/tile-progress",
            method="GET"
        )

        if not success:
            await interaction.followup.send(f"Failed to get tile progress: {response_data}")
            return
        
        # Extract tile information
        team_name = response_data.get("team_name", "Unknown Team")
        tile_name = response_data.get("current_tile", "Unknown")
        region_name = response_data.get("current_region", "Unknown")
        tile_description = response_data.get("tile_description", "No description available")
        is_completed = response_data.get("is_tile_completed", False)
        tile_progress = response_data.get("tile_progress", [])
        region_progress = response_data.get("region_progress", [])
        is_rolling = response_data.get("is_rolling", False)
        
        # Create a detailed embed with tile information
        embed = discord.Embed(
            title=f"{region_name} - {tile_name}",
            description=tile_description,
            color=discord.Color.green() if is_completed else discord.Color.blue()
        )
        
        # Add tile type
        embed.add_field(name="Region", value=region_name, inline=True)
        embed.add_field(name="Status", value="✅ Completed" if is_completed else "🔄 In Progress", inline=True)
        
        if not is_completed:
            # Add progress information if there's any
            progress_text = ""
            for progress_string in region_progress:
                progress_text += f"• {progress_string}\n"

            if progress_text:
                # if it's over the size limit, truncate it
                if len(progress_text) > 1024:
                    progress_text = progress_text[:1021] + "..."
                embed.add_field(name="Region Progress", value=progress_text, inline=False)

            progress_text = ""
            for progress_string in tile_progress:
                progress_text += f"• {progress_string}\n"

            if progress_text:
                # if it's over the size limit, truncate it
                if len(progress_text) > 1024:
                    progress_text = progress_text[:1021] + "..."
                embed.add_field(name="Tile Progress", value=progress_text, inline=False)
        
        # Add action hint
        if not is_rolling and is_completed:
            embed.add_field(name="Available Action", value="You can roll! Use `/roll`", inline=False)
        elif is_completed:
            embed.add_field(name="Next Steps", value="Waiting for your team to roll", inline=False)
        else:
            embed.add_field(name="Next Steps", value="Complete the current tile's challenges", inline=False)
        
        await interaction.followup.send(embed=embed)

    @discord.slash_command(name="items", description="View and use items in your inventory", guild_ids=[int(os.getenv("GUILD_ID"))])
    async def view_items(self, interaction):
        logger.info(f"{interaction.user.display_name} ({interaction.user.id}): /items")
        
        await interaction.response.defer(ephemeral=False)
        
        # Get the first active event
        event, error = await self.get_active_event(interaction)
        if error:
            await interaction.followup.send(error)
            return
            
        event_id = event.get('id')
        
        # Get the user's team
        team_id, error = await self.get_user_team(interaction, event_id)
        if error:
            await interaction.followup.send(error)
            return
        
        # Get items
        success, response_data = await self.call_backend_api(
            f"/events/{event_id}/teams/{team_id}/items/inventory",
            method="GET"
        )
        
        if not success:
            await interaction.followup.send(f"Failed to get items: {response_data}")
            return
        
        # Create a detailed embed with the items
        items = response_data.get("items", [])
        
        logging.info(response_data)

        if not items:
            await interaction.followup.send("You have no items in your inventory.")
            return
        
        embed = discord.Embed(
            title="Your Inventory",
            color=discord.Color.blue()
        )
        
        view = InventoryView(self, interaction, str(event_id), str(team_id), items)
        
        await interaction.followup.send(embed=embed, view=view)

    # Roll Dice Command
    @discord.slash_command(name="roll", description="Roll dice to move forward on the board", guild_ids=[int(os.getenv("GUILD_ID"))])
    async def roll_dice(self, interaction):
        logger.info(f"{interaction.user.display_name} ({interaction.user.id}): /event_roll")
        
        await interaction.response.defer(ephemeral=False)
        
        # Get the first active event
        event, error = await self.get_active_event(interaction)
        if error:
            logger.error(f"Failed to get active event: {error}")
            await interaction.followup.send(error)
            return
            
        event_id = event.get('id')
        logger.debug(f"Active event found: {event_id}")
        
        # Get the user's team
        team_id, error = await self.get_user_team(interaction, event_id)
        if error:
            logger.error(f"Failed to get team for user {interaction.user.id}: {error}")
            await interaction.followup.send(error)
            return
        
        logger.debug(f"User {interaction.user.id} team found: {team_id}")
        
        # # Check if there's already an active roll for this team
        # if team_id in self.active_rolls:
        #     active_roller_id = self.active_rolls[team_id]
        #     logger.debug(f"Team {team_id} has an active roll by user {active_roller_id}")
            
        #     if active_roller_id != str(interaction.user.id):
        #         # Someone else from the team already has an active roll
        #         active_roller = await self.bot.fetch_user(int(active_roller_id))
        #         if active_roller:
        #             roller_name = active_roller.display_name
        #             logger.info(f"Roll blocked: {interaction.user.display_name} attempted to roll while {roller_name} already has an active roll")
        #         else:
        #             roller_name = "Another player"
        #             logger.info(f"Roll blocked: {interaction.user.display_name} attempted to roll while another user already has an active roll")
                
        #         await interaction.followup.send(f"⚠️ {roller_name} already started a roll for your team. Please wait until their roll sequence is complete.")
        #         return
        #     else:
        #         logger.debug(f"User {interaction.user.id} is continuing their existing roll for team {team_id}")
        
        # Start the roll
        logger.info(f"Starting roll for team {team_id} by user {interaction.user.id}")
        success, response_data = await self.call_backend_api(
            f"/events/{event_id}/teams/{team_id}/roll",
            method="POST"
        )
        
        if not success:
            logger.error(f"Failed to roll dice for team {team_id}: {response_data}")
            await interaction.followup.send(f"Failed to roll dice: Your team is not able to roll right now.")
            return
        
        logger.debug(f"Roll API response: {json.dumps(response_data)[:200]}...")
        
        # Record that this user started a roll for this team
        self.active_rolls[team_id] = str(interaction.user.id)
        logger.info(f"Recorded active roll for team {team_id} by user {interaction.user.id}")
        
        # Process the roll progression
        try:
            # Send the initial message and store it for future updates
            roll_message = await interaction.followup.send("🎲 Processing your roll...", wait=True)
            self.roll_messages[team_id] = roll_message
            logger.debug(f"Roll message created and stored for team {team_id}: {roll_message.id}")
            
            await self.process_roll_progression(interaction, response_data)
        except Exception as e:
            logger.error(f"Error processing roll progression: {str(e)}", exc_info=True)
            logger.error(traceback.format_exc())
            await interaction.followup.send(f"An error occurred while processing your roll: {str(e)}")
            # Clean up the active roll on error
            if team_id in self.active_rolls:
                del self.active_rolls[team_id]
                logger.info(f"Cleaned up active roll for team {team_id} due to error")
            if team_id in self.roll_messages:
                del self.roll_messages[team_id]
                logger.info(f"Cleaned up roll message for team {team_id} due to error")

    # Process roll progression
    async def process_roll_progression(self, interaction: discord.Interaction, response_data: dict, existing_message: discord.Message = None):
        """Process the roll progression response and update the existing UI"""
        
        # --- Define ACTION_TYPES locally if RollState class is not available ---
        ACTION_TYPES = {
            "CONTINUE": "continue",
            "SHOP": "shop",
            "STAR": "star",
            "DOCK": "dock",
            "CROSSROAD": "crossroad",
            "COMPLETE": "complete",
            "FIRST_ROLL": "first_roll",
            "ISLAND_SELECTION": "island_selection"
        }
        # --- End local ACTION_TYPES definition ---

        logger.info("Processing roll progression response:")
        logger.info(f"{json.dumps(response_data, indent=2)}") 
        
        try:
            roll_data = RollProgressionPayload(response_data)
            action_type = roll_data.action_required 
            team_id = roll_data.teamId
            event_id = roll_data.eventId 
            
            logger.info(f"Roll progression - Type: {action_type}, Team: {team_id}, Event: {event_id}")
            logger.debug(f"Roll details - From: {roll_data.startingTileId}, To: {roll_data.currentTileId}, " +
                        f"TotalForTurn: {roll_data.roll_total_for_turn}, Remaining: {roll_data.roll_remaining}")
            
            roll_message_ref = existing_message
            if not roll_message_ref:
                if interaction.message and interaction.message.author == self.bot.user:
                    roll_message_ref = interaction.message
                else: 
                    logger.warning(f"No existing message to edit for team {team_id}, sending new followup.")
                    if interaction.response.is_done():
                        roll_message_ref = await interaction.followup.send("🎲 Roll in progress...", wait=True)
                    else: 
                        # This path should ideally not be taken if interaction is from a component callback that deferred.
                        # If it's the initial command, interaction.response.send_message should be used first.
                        try:
                            await interaction.response.send_message("🎲 Roll in progress...", ephemeral=True) 
                            roll_message_ref = await interaction.original_response()
                        except discord.errors.InteractionResponded: # If already responded (e.g. by a quick defer)
                            roll_message_ref = await interaction.followup.send("🎲 Roll in progress...", wait=True)

                if team_id: 
                    self.roll_messages[team_id] = roll_message_ref 

            embed = discord.Embed(title="🎲 Roll in Progress...") 
            
            dice_rolled_display = roll_data.get_current_action_dice_results()
            modifier_display = roll_data.get_current_action_modifier()
            roll_total_display = roll_data.get_current_action_roll_total()

            if roll_total_display is not None:
                embed.description = f"Rolled: {dice_rolled_display} + Mod: {modifier_display} = **{roll_total_display}** total!"
            else:
                embed.description = "Processing your action..."

            embed.color = discord.Color.blue()
            
            if roll_data.roll_remaining is not None and roll_data.roll_remaining > 0 and action_type != ACTION_TYPES["FIRST_ROLL"]:
                embed.add_field(
                    name="Movement",
                    value=f"Moves remaining: {roll_data.roll_remaining}/{roll_data.roll_total_for_turn}",
                    inline=False
                )
            
            view = None 

            logger.info(f"Action type: {action_type}")
            if action_type == ACTION_TYPES["COMPLETE"]: # Use local ACTION_TYPES
                logger.info(f"Roll ended - Team {team_id} completed roll sequence.")
                embed.title = f"🎲 Roll Complete! Total Roll: {roll_data.roll_total_for_turn}"
                embed.color = discord.Color.green()
                
                current_tile_info = roll_data.data.get("current_tile", {})
                landed_tile_name = current_tile_info.get("name", "an unnamed tile")
                landed_tile_desc = current_tile_info.get("description", "No further details.")
                completion_message = roll_data.data.get("message", f"You've landed on **{landed_tile_name}**!")
                
                path_taken = roll_data.data.get("path_taken_this_turn")
                distance_moved = roll_data.roll_total_for_turn

                embed.description = completion_message
                embed.add_field(name=f"Landed on: {landed_tile_name}", value=landed_tile_desc, inline=False)
                
                embed.add_field(
                    name="Total Distance Moved",
                    value=f"Moved {distance_moved} spaces: {' -> '.join(path_taken)}",
                    inline=False
                )

                if team_id and team_id in self.active_rolls: 
                    del self.active_rolls[team_id]

            elif action_type == ACTION_TYPES["FIRST_ROLL"]: # Use local ACTION_TYPES
                logger.info(f"First roll for team {team_id}. Prompting for island selection.")
                embed.title = "🎉 Welcome - First Roll!"
                embed.description = roll_data.data.get("message", "Roll your dice and choose your starting island!")
                embed.add_field(name="Your Roll", value=f"Dice: {roll_data.data.get('dice_results_for_roll')} + Mod: {roll_data.data.get('modifier_for_roll')} = **{roll_data.data.get('roll_total_for_turn')}**", inline=False)
                
                available_islands = roll_data.data.get("available_islands", [])
                if available_islands:
                    view = FirstRollIslandSelectView(
                        self, 
                        str(event_id), 
                        str(team_id),  
                        available_islands,
                        roll_data.data.get("roll_total_for_turn", 0), 
                        str(interaction.user.id), 
                        roll_message_ref
                    )
                    if team_id: 
                        if team_id not in self.active_rolls: self.active_rolls[team_id] = {}
                        self.active_rolls[team_id]['first_roll_total'] = roll_data.data.get("roll_total_for_turn", 0)
                        self.active_rolls[team_id]['roll_remaining'] = 0 
                else:
                    embed.add_field(name="Error", value=roll_data.data.get("error", "No starting islands configured!"), inline=False)
                    if team_id and team_id in self.active_rolls: del self.active_rolls[team_id] 

            elif action_type == ACTION_TYPES["CROSSROAD"]: # Use local ACTION_TYPES
                logger.info(f"Crossroad for team {team_id}")
                embed.title = "🛤️ Crossroad Ahead!"
                embed.description = roll_data.data.get("message", "You've reached a crossroad. Choose your path!")
                options = roll_data.data.get("options", [])
                current_tile_info = roll_data.data.get("current_tile", {})
                embed.add_field(name=f"Currently at: {current_tile_info.get('name', 'Crossroad')}", value="Select your next tile from the options below.", inline=False)

                if options:
                    view = RollCrossroadView( 
                        self, 
                        str(event_id), 
                        str(team_id), 
                        options,
                        str(interaction.user.id), 
                        roll_message_ref
                    )
                else:
                    embed.add_field(name="No Options", value="Strangely, no paths lead from here...", inline=False)
                    if team_id and team_id in self.active_rolls: del self.active_rolls[team_id]


            elif action_type == ACTION_TYPES["SHOP"]: # Use local ACTION_TYPES
                logger.info(f"Shop interaction for team {team_id}")
                embed.title = "🛒 Item Shop!"
                embed.description = roll_data.data.get("message", "Welcome to the shop!")
                available_items = roll_data.data.get("items", [])
                team_coins = roll_data.data.get("coins", 0)
                moves_remaining_at_shop = roll_data.data.get("moves_remaining", roll_data.roll_remaining) 

                embed.add_field(name="Your Wallet", value=f"💰 {team_coins} Coins", inline=True)

                active_roll_context = {"roll_remaining": moves_remaining_at_shop}
                if team_id and team_id in self.active_rolls: 
                    active_roll_context = self.active_rolls[team_id]
                    active_roll_context["roll_remaining"] = moves_remaining_at_shop 

                view = RollShopInitialView(
                    self,
                    str(event_id),
                    str(team_id),
                    available_items,
                    team_coins,
                    str(interaction.user.id), 
                    roll_message_ref,
                    active_roll_context 
                )

            elif action_type == ACTION_TYPES["DOCK"]: # Use local ACTION_TYPES
                logger.info(f"Dock interaction for team {team_id}")
                embed.title = "⚓ Ship Charter"
                embed.description = roll_data.data.get("message", "You've reached a dock. Care to travel?")
                destinations = roll_data.data.get("destinations", [])
                team_coins = roll_data.data.get("coins", 0)
                moves_remaining_at_dock = roll_data.data.get("moves_remaining", roll_data.roll_remaining)

                embed.add_field(name="Your Wallet", value=f"💰 {team_coins} Coins", inline=True)

                active_roll_context_dock = {"roll_remaining": moves_remaining_at_dock}
                if team_id and team_id in self.active_rolls:
                    active_roll_context_dock = self.active_rolls[team_id]
                    active_roll_context_dock["roll_remaining"] = moves_remaining_at_dock

                view = RollDockInitialView(
                    self,
                    str(event_id),
                    str(team_id),
                    destinations,
                    team_coins,
                    str(interaction.user.id),
                    roll_message_ref,
                    active_roll_context_dock
                )
            
            # Add more elif blocks for STAR, CONTINUE etc. as needed using ACTION_TYPES["STAR"]
            elif action_type == ACTION_TYPES["STAR"]: # Use local ACTION_TYPES
                logger.info(f"Star interaction for team {team_id}")
                embed.title = "⭐ Star Encounter"
                embed.description = roll_data.data.get("message", "You've encountered a star! Choose wisely.")
                star_price = roll_data.data.get("price", 0)
                current_tile_info = roll_data.data.get("current_tile", {})
                embed.add_field(name=f"Currently at: {current_tile_info.get('name', 'Star')}", value="Select your star option from the choices below.", inline=False)

                view = RollStarView(
                    self,
                    str(event_id),
                    str(team_id),
                    star_price,
                    str(interaction.user.id),
                    roll_message_ref
                )

            try:
                if roll_message_ref: 
                    await roll_message_ref.edit(content=None, embed=embed, view=view)
                    logger.info(f"Roll progression UI updated for team {team_id} on message {roll_message_ref.id}")
                else: 
                    logger.error(f"Critical: roll_message_ref is None for team {team_id}, cannot update UI.")
                    if interaction and not interaction.response.is_done():
                        await interaction.response.send_message(embed=embed, view=view, ephemeral=True) 
                    elif interaction:
                        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

            except discord.errors.HTTPException as http_error:
                if http_error.status == 404: 
                    logger.warning(f"Original roll message for team {team_id} not found. Sending a new one.")
                    target_channel = interaction.channel
                    if not target_channel and roll_message_ref: 
                        target_channel = roll_message_ref.channel
                    if target_channel:
                        new_message = await target_channel.send(embed=embed, view=view) 
                        if team_id: self.roll_messages[team_id] = new_message 
                    else:
                        logger.error(f"Cannot send new message for team {team_id}, channel context lost.")
                else:
                    logger.error(f"HTTPException editing roll message for team {team_id}: {http_error}", exc_info=True)
                    if interaction: await interaction.followup.send("Error updating roll display.", ephemeral=True)
            except Exception as e:
                logger.error(f"Generic error updating roll message for team {team_id}: {e}", exc_info=True)
                if interaction: await interaction.followup.send("An error occurred while updating the roll display.", ephemeral=True)

        except Exception as e:
            logger.error(f"Error in process_roll_progression for team {team_id if 'team_id' in locals() else 'UNKNOWN'}: {str(e)}", exc_info=True)
            if interaction and not interaction.response.is_done():
                await interaction.response.send_message(f"An error occurred processing the roll: {str(e)}", ephemeral=True)
            elif interaction:
                try:
                    await interaction.followup.send(f"An error occurred processing the roll: {str(e)}", ephemeral=True)
                except Exception as followup_e:
                    logger.error(f"Failed to send followup error message: {followup_e}")

class RollBaseView(discord.ui.View):
    def __init__(self, cog, event_id: str, team_id: str, initiator_id: str, roll_message: discord.Message):
        super().__init__(timeout=0)  # Keep the view active indefinitely
        self.cog = cog
        self.event_id = event_id
        self.team_id = team_id
        self.initiator_id = initiator_id
        self.roll_message = roll_message
        logger.debug(f"RollBaseView initialized: event={event_id}, team={team_id}, initiator={initiator_id}, message={roll_message.id}")
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if the user who clicks the button is the same one who initiated the roll"""
        if str(interaction.user.id) != self.initiator_id:
            logger.warning(f"Interaction blocked: User {interaction.user.id} attempted to interact with a roll started by {self.initiator_id}")
            await interaction.response.send_message("Only the player who started the roll can make decisions during the roll.", ephemeral=True)
            return False
        logger.debug(f"Interaction permitted: User {interaction.user.id} is the roll initiator")
        return True

class RollCrossroadView(RollBaseView):
    def __init__(self, cog, event_id: str, team_id: str, directions: list, initiator_id: str, roll_message: discord.Message):
        super().__init__(cog, event_id, team_id, initiator_id, roll_message)
        
        logger.debug(f"Creating CrossroadView with {len(directions)} directions")
        
        # Add a button for each direction
        for i, dir_data in enumerate(directions):
            dir_name = dir_data.get("name", f"Direction {i+1}")
            dir_id = dir_data.get("id", "")
            
            button = discord.ui.Button(
                label=dir_name,
                style=discord.ButtonStyle.primary,
                custom_id=f"direction_{dir_id}"
            )
            
            # Set the callback for this button
            button.callback = self.create_callback(dir_id)
            logger.debug(f"Added direction button: {dir_name} (ID: {dir_id})")
            
            self.add_item(button)
    
    def create_callback(self, direction_id: str):
        """Create a callback function for a direction button"""
        async def callback(interaction: discord.Interaction):
            logger.info(f"Direction selected: {direction_id} by user {interaction.user.id} for team {self.team_id}")
            await interaction.response.defer(ephemeral=True)  # Use ephemeral response to avoid cluttering the channel
            
            # Call API to choose direction
            logger.debug(f"Calling API to choose direction {direction_id}")
            success, response_data = await self.cog.call_backend_api(
                f"/events/{self.event_id}/teams/{self.team_id}/roll/crossroad",
                payload={"directionId": direction_id},
                method="POST"
            )
            
            if not success:
                logger.error(f"Failed to choose direction {direction_id}: {response_data}")
                await interaction.followup.send(f"Failed to choose direction: {response_data}", ephemeral=True)
                return
            
            logger.debug(f"Direction API response: {json.dumps(response_data)[:200]}...")
            
            # Process the next step of the roll
            logger.info(f"Processing next roll step after choosing direction {direction_id}")
            await self.cog.process_roll_progression(interaction, response_data)
            
            # Disable all buttons after selection to prevent double-clicks
            for item in self.children:
                item.disabled = True
            
            # We don't need to edit the message here as process_roll_progression will update it
            
        return callback

class RollShopView(RollBaseView):
    def __init__(self, cog, event_id: str, team_id: str, available_items: list, team_coins: int, initiator_id: str, roll_message: discord.Message):
        super().__init__(cog, event_id, team_id, initiator_id, roll_message)
        self.available_items = available_items
        self.team_coins = team_coins
        
        logger.debug(f"Creating ShopView with {len(available_items)} items and {team_coins} coins")
        
        # Add buttons for each item to view its details
        for i, item in enumerate(available_items):
            item_name = item.get("name", f"Item {i+1}")
            item_price = item.get("price", 0)
            
            # Style based on affordability
            affordable = team_coins >= item_price
            style = discord.ButtonStyle.primary if affordable else discord.ButtonStyle.secondary
            
            # Create a button for viewing item details
            button = discord.ui.Button(
                label=f"View {item_name}",
                style=style,
                custom_id=f"view_item_{i}"
            )
            
            # Set the callback for this button with the item index
            button.callback = self.create_view_item_callback(i)
            self.add_item(button)
            logger.debug(f"Added view button for {item_name} (Price: {item_price}, Affordable: {affordable})")
        
        # Add back button to return to initial shop view
        back_button = discord.ui.Button(
            label="Back to Shop Menu",
            style=discord.ButtonStyle.secondary,
            custom_id="back_to_shop_menu"
        )
        back_button.callback = self.back_to_shop_menu
        self.add_item(back_button)
        
        # Add continue journey button
        continue_button = discord.ui.Button(
            label="Continue Journey",
            style=discord.ButtonStyle.danger,
            custom_id="shop_continue"
        )
        continue_button.callback = self.continue_journey
        self.add_item(continue_button)
    
    def create_view_item_callback(self, item_index: int):
        """Create a callback function for viewing an item's details"""
        async def view_item_callback(interaction: discord.Interaction):
            if item_index >= len(self.available_items):
                logger.error(f"Invalid item index: {item_index}, max: {len(self.available_items)-1}")
                await interaction.response.send_message("This item is no longer available.", ephemeral=True)
                return
                
            item = self.available_items[item_index]
            item_name = item.get("name", "Unknown Item")
            item_price = item.get("price", 0)
            item_description = item.get("description", "No description available.")
            item_rarity = item.get("rarity", "common").capitalize()
            item_id = item.get("id", "")
            
            logger.info(f"User {interaction.user.id} is viewing details for item {item_name} (ID: {item_id})")
            await interaction.response.defer(ephemeral=True)
            
            # Create a detailed embed for this item
            embed = discord.Embed(
                title=f"🛒 {item_name}",
                description=item_description,
                color=discord.Color.purple()
            )
            
            # Add item details
            embed.add_field(name="Price", value=f"{item_price} coins", inline=True)
            embed.add_field(name="Rarity", value=item_rarity, inline=True)
            
            # Add team coins info
            affordable = self.team_coins >= item_price
            status = "✅ You can afford this item" if affordable else "❌ Not enough coins"
            embed.add_field(
                name="Your Funds",
                value=f"{self.team_coins} coins available\n{status}",
                inline=False
            )
            
            # Create a detailed view for this item
            item_view = RollShopItemView(
                self.cog,
                self.event_id,
                self.team_id,
                item,
                self.team_coins,
                self.available_items,
                self.initiator_id,
                self.roll_message
            )
            
            # Update the message with item details
            await self.roll_message.edit(embed=embed, view=item_view)
            
            # Let the user know the item details are displayed
            #await interaction.followup.send(f"Viewing details for {item_name}.", ephemeral=True)
        
        return view_item_callback
    
    async def back_to_shop_menu(self, interaction: discord.Interaction):
        """Go back to the initial shop menu"""
        logger.info(f"User {interaction.user.id} is returning to shop menu")
        await interaction.response.defer(ephemeral=True)
        
        # Create a new embed for the initial shop view
        embed = discord.Embed(
            title="🛒 Item Shop",
            description="Would you like to browse the items in this shop?",
            color=discord.Color.purple()
        )
        
        embed.add_field(
            name="Your Team",
            value=f"💰 **{self.team_coins} coins** available",
            inline=False
        )
        
        embed.add_field(
            name="Available Items",
            value=f"There are **{len(self.available_items)}** items available in this shop.",
            inline=False
        )
        
        # Create a new initial shop view
        initial_view = RollShopInitialView(
            self.cog,
            self.event_id,
            self.team_id,
            self.available_items,
            self.team_coins,
            self.initiator_id,
            self.roll_message
        )
        
        # Update the message
        await self.roll_message.edit(embed=embed, view=initial_view)
        
        # Let the user know they've returned to the initial shop menu
        await interaction.followup.send("Returning to shop menu.", ephemeral=True)
    
    async def continue_journey(self, interaction: discord.Interaction):
        """Continue the journey without buying anything"""
        logger.info(f"User {interaction.user.id} chose to continue journey from shop list view")
        await interaction.response.defer(ephemeral=True)
        
        # Call API to continue the journey
        success, response_data = await self.cog.call_backend_api(
            f"/events/{self.event_id}/teams/{self.team_id}/roll/continue",
            method="POST"
        )
        
        if not success:
            logger.error(f"Failed to continue journey: {response_data}")
            await interaction.followup.send(f"Failed to continue journey: {response_data}", ephemeral=True)
            return
        
        logger.debug(f"Continue journey API response: {json.dumps(response_data)[:200]}...")
        
        # Process the next step of the roll
        await self.cog.process_roll_progression(interaction, response_data)
        
        # Let the user know their selection was received
        #await interaction.followup.send("Continuing journey without buying anything! Check the updated message.", ephemeral=True)

class RollStarView(RollBaseView):
    def __init__(self, cog, event_id: str, team_id: str, cost: int, initiator_id: str, roll_message: discord.Message):
        super().__init__(cog, event_id, team_id, initiator_id, roll_message)
        self.cost = cost
        
        # Add buttons: Buy Star or Skip
        self.add_item(discord.ui.Button(
            label=f"Buy Star ({cost} coins)",
            style=discord.ButtonStyle.primary,
            custom_id="star_buy"
        ))
        
        self.add_item(discord.ui.Button(
            label="Continue Journey",
            style=discord.ButtonStyle.secondary,
            custom_id="star_skip"
        ))
        
        # Set callbacks
        self.children[0].callback = self.buy_star
        self.children[1].callback = self.skip_star
    
    async def buy_star(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Call API to buy the star
        success, response_data = await self.cog.call_backend_api(
            f"/events/{self.event_id}/teams/{self.team_id}/roll/star",
            payload={"action": "buy", "cost": self.cost},
            method="POST"
        )
        
        if not success:
            await interaction.followup.send(f"Failed to buy star: {response_data}", ephemeral=True)
            return
        
        # Show star purchase confirmation in the original message
        team_stars = response_data.get("teamStars", 0)
        team_coins = response_data.get("teamCoins", 0)
        
        # Update the embed to show the star purchase
        current_embed = self.roll_message.embeds[0] if self.roll_message.embeds else discord.Embed(title="⭐ Star Purchase")
        current_embed.description = f"You purchased a star!\n\nYour team now has {team_stars} stars and {team_coins} coins remaining."
        current_embed.color = discord.Color.gold()
        
        # Disable the buttons
        for item in self.children:
            item.disabled = True
            
        await self.roll_message.edit(embed=current_embed, view=self)
        
        # Process next step of roll if there is one
        next_response = response_data.get("nextStep", {})
        if next_response:
            await self.cog.process_roll_progression(interaction, next_response)

        # Continue the journey
        await self.cog.process_roll_progression(interaction, response_data)
        
        # Let the user know their purchase was successful
        #await interaction.followup.send("Star purchased! Check the updated message.", ephemeral=True)
    
    async def skip_star(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Call API to skip buying the star
        success, response_data = await self.cog.call_backend_api(
            f"/events/{self.event_id}/teams/{self.team_id}/roll/star",
            payload={"action": "skip"},
            method="POST"
        )
        
        if not success:
            await interaction.followup.send(f"Failed to skip star: {response_data}", ephemeral=True)
            return
        
        # Process the next step of the roll
        await self.cog.process_roll_progression(interaction, response_data)
        
        # Let the user know their selection was received
        #await interaction.followup.send("Continuing journey! Check the updated message.", ephemeral=True)

class RollDockInitialView(RollBaseView):
    def __init__(self, cog, event_id: str, team_id: str, destinations: list, team_coins: int, 
                 initiator_id: str, roll_message: discord.Message, active_roll_context: dict = None):
        super().__init__(cog, event_id, team_id, initiator_id, roll_message)
        self.destinations = destinations
        self.team_coins = team_coins
        self.active_roll_context = active_roll_context or {}
        
        logger.debug(f"Creating DockInitialView with {len(destinations)} destinations, available coins: {team_coins}")
        
        # Add "View Destinations" button
        view_destinations_button = discord.ui.Button(
            label=f"View Available Islands ({len(destinations)})",
            style=discord.ButtonStyle.primary,
            custom_id="view_destinations",
            disabled=len(destinations) == 0
        )
        view_destinations_button.callback = self.show_destinations
        self.add_item(view_destinations_button)
        
        # Add "Continue Journey" button
        continue_button = discord.ui.Button(
            label="Continue Journey",
            style=discord.ButtonStyle.secondary,
            custom_id="dock_continue"
        )
        continue_button.callback = self.continue_journey
        self.add_item(continue_button)
        
    async def show_destinations(self, interaction: discord.Interaction):
        """Show the available destinations for the player to select from"""
        logger.info(f"User {interaction.user.id} is viewing destinations for team {self.team_id}")
        await interaction.response.defer(ephemeral=True)
        
        # Create a detailed embed showing all destinations
        embed = discord.Embed(
            title="⚓ Available Islands",
            description=f"Choose an island to charter a ship to",
            color=discord.Color.blue()
        )
        
        # Add detailed info for each destination
        for dest in self.destinations:
            name = dest.get("name", "Unknown Location")
            description = dest.get("description", "No description available.")
            dest_id = dest.get("id", "")
            charter_price = dest.get("cost", 0)
            
            # Check if the team can afford this destination
            affordable = self.team_coins >= charter_price
            status = "✅ Available" if affordable else "❌ Not enough coins"
            
            embed.add_field(
                name=f"{name}",
                value=f"{description}\n**Status:** {status}\n**Cost:** {charter_price} coins",
                inline=False
            )
        
        # Create a selector view with all destinations
        destination_view = RollDockSelectorView(
            self.cog,
            self.event_id,
            self.team_id,
            self.destinations,
            self.team_coins,
            self.initiator_id,
            self.roll_message
        )
        
        # Update the message with destination details
        await self.roll_message.edit(embed=embed, view=destination_view)
        
        # Let the user know the destinations are displayed
        #await interaction.followup.send("Viewing available islands! Check the updated message.", ephemeral=True)
    
    async def continue_journey(self, interaction: discord.Interaction):
        """Continue the journey without chartering a ship"""
        logger.info(f"User {interaction.user.id} chose to continue journey without viewing destinations")
        await interaction.response.defer(ephemeral=True)
        
        # Call API to continue the journey
        success, response_data = await self.cog.call_backend_api(
            f"/events/{self.event_id}/teams/{self.team_id}/roll/continue",
            method="POST"
        )
        
        if not success:
            logger.error(f"Failed to continue journey: {response_data}")
            await interaction.followup.send(f"Failed to continue journey: {response_data}", ephemeral=True)
            return
        
        logger.debug(f"Continue journey API response: {json.dumps(response_data)[:200]}...")
        
        # Process the next step of the roll
        await self.cog.process_roll_progression(interaction, response_data)
        
        # Let the user know their selection was received
        #await interaction.followup.send("Continuing journey without chartering a ship! Check the updated message.", ephemeral=True)

class RollDockSelectorView(RollBaseView):
    def __init__(self, cog, event_id: str, team_id: str, destinations: list, team_coins: int, initiator_id: str, roll_message: discord.Message):
        super().__init__(cog, event_id, team_id, initiator_id, roll_message)
        self.destinations = destinations
        self.team_coins = team_coins
        
        logger.debug(f"Creating DockSelectorView with {len(destinations)} destinations, available coins: {team_coins}")
        
        # Add a Select menu for destinations
        options = []
        self.destination_map = {}  # To map select values to destination IDs
        
        for i, dest in enumerate(destinations):
            dest_name = dest.get("name", "Unknown Location")
            dest_id = dest.get("id", "")
            dest_desc = dest.get("description", "")
            charter_price = dest.get("cost", 0)
            affordable = team_coins >= charter_price
            
            # Truncate description if too long for the select option
            short_desc = dest_desc[:50] + ("..." if len(dest_desc) > 50 else "")
            
            # Store the mapping of select value to destination ID
            select_value = f"dest_{i}"
            self.destination_map[select_value] = {
                "id": dest_id,
                "name": dest_name,
                "description": dest_desc,
                "cost": charter_price,
                "affordable": affordable
            }
            
            # Create the option
            options.append(
                discord.SelectOption(
                    label=dest_name,
                    description=short_desc,
                    value=select_value,
                    default=False,
                    emoji="✅" if affordable else "❌"
                )
            )
        
        if options:
            # Create the select menu for destinations
            self.destination_select = discord.ui.Select(
                placeholder="Select an island to travel to...",
                min_values=1,
                max_values=1,
                options=options,
                custom_id="destination_select"
            )
            self.destination_select.callback = self.on_destination_select
            self.add_item(self.destination_select)
            
            # Add confirm and cancel buttons
            self.confirm_button = discord.ui.Button(
                label="Charter Ship",
                style=discord.ButtonStyle.success,
                custom_id="confirm_charter",
                disabled=True  # Disabled until a selection is made
            )
            self.confirm_button.callback = self.on_confirm
            self.add_item(self.confirm_button)
        
        # Add a cancel button to go back
        self.cancel_button = discord.ui.Button(
            label="Cancel",
            style=discord.ButtonStyle.secondary,
            custom_id="cancel_charter"
        )
        self.cancel_button.callback = self.on_cancel
        self.add_item(self.cancel_button)
        
        # Track the selected destination
        self.selected_destination = None
    
    async def on_destination_select(self, interaction: discord.Interaction):
        """Handle destination selection"""
        logger.info(f"User {interaction.user.id} selected a destination from the dropdown")
        await interaction.response.defer(ephemeral=True)
        
        # Get the selected value
        selected_value = self.destination_select.values[0]
        dest_info = self.destination_map.get(selected_value, {})
        
        if not dest_info:
            logger.error(f"Invalid destination selection: {selected_value}")
            await interaction.followup.send("Invalid destination selected.", ephemeral=True)
            return
        
        dest_name = dest_info.get("name", "Unknown")
        dest_id = dest_info.get("id", "")
        dest_price = dest_info.get("cost", 0)
        affordable = dest_info.get("affordable", False)
        
        logger.debug(f"Selected destination: {dest_name} (ID: {dest_id}, Affordable: {affordable})")
        
        if not affordable:
            logger.warning(f"User selected unaffordable destination: {dest_name}")
            await interaction.followup.send(f"You don't have enough coins to charter a ship to {dest_name}. You need {dest_price} coins.", ephemeral=True)
            
            # Reset the selection
            self.destination_select.placeholder = "Select an island to travel to..."
            self.confirm_button.disabled = True
            await self.roll_message.edit(view=self)
            return
        
        # Store the selected destination
        self.selected_destination = dest_info
        
        # Enable the confirm button
        self.confirm_button.disabled = False
        self.destination_select.placeholder = f"Selected: {dest_name}"
        
        # Update the message
        await self.roll_message.edit(view=self)
        
        # Let the user know their selection was recorded
        #await interaction.followup.send(f"You selected {dest_name}. Click 'Charter Ship' to confirm your travel.", ephemeral=True)
    
    async def on_confirm(self, interaction: discord.Interaction):
        """Handle confirmation of travel to selected destination"""
        logger.info(f"User {interaction.user.id} confirmed charter to destination")
        await interaction.response.defer(ephemeral=True)
        
        if not self.selected_destination:
            logger.error("User tried to confirm with no destination selected")
            await interaction.followup.send("You need to select a destination first.", ephemeral=True)
            return
        
        dest_id = self.selected_destination.get("id", "")
        dest_name = self.selected_destination.get("name", "Unknown")
        dest_cost = self.selected_destination.get("cost", 0)
        
        logger.info(f"Chartering ship to {dest_name} (ID: {dest_id}) for {dest_cost} coins")
        
        # Call API to travel to the destination
        success, response_data = await self.cog.call_backend_api(
            f"/events/{self.event_id}/teams/{self.team_id}/roll/dock",
            payload={"action": "charter", "destinationId": dest_id, "cost": dest_cost},
            method="POST"
        )
        
        if not success:
            logger.error(f"Failed to charter ship to {dest_id}: {response_data}")
            await interaction.followup.send(f"Failed to charter ship: {response_data}", ephemeral=True)
            return
        
        logger.info(f"Successfully chartered ship to {dest_name} for {dest_cost} coins")
        
        # Show travel confirmation in the existing message
        travel_cost = response_data.get("travelCost", dest_cost)
        team_coins = response_data.get("teamCoins", self.team_coins - travel_cost)
        new_tile_id = response_data.get("newTileId", "Unknown")
        
        # Update the embed
        travel_embed = discord.Embed(
            title="⚓ Ship Chartered!",
            description=f"You traveled to **{dest_name}** for {travel_cost} coins. Your team now has {team_coins} coins remaining.",
            color=discord.Color.blue()
        )
        
        travel_embed.add_field(
            name="New Location",
            value=f"You are now on tile {new_tile_id} ({dest_name})",
            inline=False
        )
        
        # Disable all components
        for item in self.children:
            item.disabled = True
        
        # Update the message
        await self.roll_message.edit(embed=travel_embed, view=self)
        
        # Process next step or end roll
        next_response = response_data.get("nextStep", {})
        if next_response:
            await self.cog.process_roll_progression(interaction, next_response)
        else:
            # If no next step, then we're done with the roll
            if self.team_id in self.cog.active_rolls:
                del self.cog.active_rolls[self.team_id]
                logger.info(f"Cleaned up active roll for team {self.team_id} after traveling to {dest_name}")
        
        # Process the next step of the roll
        await self.cog.process_roll_progression(interaction, response_data)
        
        # Let the user know their selection was registered
        #await interaction.followup.send(f"Ship chartered to {dest_name}! Check the updated message.", ephemeral=True)
    
    async def on_cancel(self, interaction: discord.Interaction):
        """Cancel selection and go back to initial dock view"""
        logger.info(f"User {interaction.user.id} canceled destination selection")
        await interaction.response.defer(ephemeral=True)
        
        # Go back to the initial dock view
        embed = discord.Embed(
            title="⚓ Ship Charter",
            description="Would you like to charter a ship to another island?",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Your Team",
            value=f"💰 **{self.team_coins} coins** available",
            inline=False
        )
        
        # Create a new initial view
        initial_view = RollDockInitialView(
            self.cog,
            self.event_id,
            self.team_id,
            self.destinations,
            self.team_coins,
            self.initiator_id,
            self.roll_message
        )
        
        # Update the message
        await self.roll_message.edit(embed=embed, view=initial_view)
        
        # Let the user know they've returned to the initial view
        #await interaction.followup.send("Returning to ship charter options.", ephemeral=True)

class RollShopInitialView(RollBaseView):
    def __init__(self, cog, event_id: str, team_id: str, available_items: list, team_coins: int, initiator_id: str, roll_message: discord.Message, active_roll_context: dict = None):
        super().__init__(cog, event_id, team_id, initiator_id, roll_message)
        self.available_items = available_items
        self.team_coins = team_coins
        self.active_roll_context = active_roll_context or {}
        
        logger.debug(f"Creating ShopInitialView with {len(available_items)} items and {team_coins} coins")
        
        # Add "View Shop" button
        view_shop_button = discord.ui.Button(
            label=f"View Shop ({len(available_items)} items)",
            style=discord.ButtonStyle.primary,
            custom_id="view_shop",
            disabled=len(available_items) == 0
        )
        view_shop_button.callback = self.show_shop
        self.add_item(view_shop_button)
        
        # Add "Continue Journey" button
        continue_button = discord.ui.Button(
            label="Continue Journey",
            style=discord.ButtonStyle.secondary,
            custom_id="shop_continue"
        )
        continue_button.callback = self.continue_journey
        self.add_item(continue_button)
        
    async def show_shop(self, interaction: discord.Interaction):
        """Show the available items in the shop"""
        logger.info(f"User {interaction.user.id} is viewing shop items for team {self.team_id}")
        await interaction.response.defer(ephemeral=True)
        
        # Create a detailed embed showing all items
        embed = discord.Embed(
            title="🛒 Available Items",
            description="Choose an item to buy",
            color=discord.Color.purple()
        )
        
        # Add detailed info for each item
        for item in self.available_items:
            name = item.get("name", "Unknown Item")
            description = item.get("description", "No description available.")
            price = item.get("price", 0)
            item_id = item.get("id", "")
            rarity = item.get("rarity", "common").capitalize()
            image = item.get("image", "")
            item_type = item.get("item_type", "Unknown")
            
            # Check if the team can afford this item
            affordable = self.team_coins >= price
            status = "✅ Available" if affordable else "❌ Not enough coins"
            
            embed.add_field(
                name=f"{name}",
                value=f"{description}\n**Price:** {price} coins\n**Status:** {status}",
                inline=False
            )
          # Create a selector view with all items
        shop_view = RollShopView(
            self.cog,
            self.event_id,
            self.team_id,
            self.available_items,
            self.team_coins,
            self.initiator_id,
            self.roll_message
        )
        
        # Update the message with item details
        await self.roll_message.edit(embed=embed, view=shop_view)
        
        # Let the user know the items are displayed
        #await interaction.followup.send("Viewing available items! Check the updated message.", ephemeral=True)
    
    async def continue_journey(self, interaction: discord.Interaction):
        """Continue the journey without buying anything"""
        logger.info(f"User {interaction.user.id} chose to continue journey without viewing shop items")
        await interaction.response.defer(ephemeral=True)
        
        # Call API to continue the journey
        success, response_data = await self.cog.call_backend_api(
            f"/events/{self.event_id}/teams/{self.team_id}/roll/continue",
            method="POST"
        )
        
        if not success:
            logger.error(f"Failed to continue journey: {response_data}")
            await interaction.followup.send(f"Failed to continue journey: {response_data}", ephemeral=True)
            return
        
        logger.debug(f"Continue journey API response: {json.dumps(response_data)[:200]}...")
        
        # Process the next step of the roll
        await self.cog.process_roll_progression(interaction, response_data)
        
        # Let the user know their selection was received
        #await interaction.followup.send("Continuing journey without buying anything! Check the updated message.", ephemeral=True)

class RollShopItemView(RollBaseView):
    def __init__(self, cog, event_id: str, team_id: str, item: dict, team_coins: int, all_items: list, initiator_id: str, roll_message: discord.Message):
        super().__init__(cog, event_id, team_id, initiator_id, roll_message)
        self.item = item
        self.team_coins = team_coins
        self.all_items = all_items
        
        item_name = item.get("name", "Unknown Item")
        item_price = item.get("price", 0)
        self.item_id = item.get("id", "")
        
        logger.debug(f"Creating ShopItemView for {item_name} (ID: {self.item_id}, Price: {item_price})")
        
        # Check if the team can afford this item
        affordable = team_coins >= item_price
        
        # Add Buy button (disabled if not affordable)
        buy_button = discord.ui.Button(
            label=f"Buy {item_name} ({item_price} coins)",
            style=discord.ButtonStyle.success,
            custom_id=f"buy_{self.item_id}",
            disabled=not affordable
        )
        buy_button.callback = self.buy_item
        self.add_item(buy_button)
        
        # Add back button to return to shop list
        back_button = discord.ui.Button(
            label="Back to Items",
            style=discord.ButtonStyle.secondary,
            custom_id="back_to_items"
        )
        back_button.callback = self.back_to_items
        self.add_item(back_button)
        
        # Add continue journey button
        continue_button = discord.ui.Button(
            label="Continue Journey",
            style=discord.ButtonStyle.danger,
            custom_id="shop_continue"
        )
        continue_button.callback = self.continue_journey
        self.add_item(continue_button)
    
    async def buy_item(self, interaction: discord.Interaction):
        """Buy the selected item and continue the journey"""
        item_name = self.item.get("name", "Unknown Item")
        item_price = self.item.get("price", 0)
        
        logger.info(f"User {interaction.user.id} is buying item {item_name} (ID: {self.item_id}) for {item_price} coins")
        await interaction.response.defer(ephemeral=True)
        
        # Call API to buy the item
        success, response_data = await self.cog.call_backend_api(
            f"/events/{self.event_id}/teams/{self.team_id}/roll/shop",
            payload={"action": "buy", "itemId": self.item_id, "price": item_price},
            method="POST"
        )
        
        if not success:
            logger.error(f"Failed to buy item {self.item_id}: {response_data}")
            await interaction.followup.send(f"Failed to buy item: {response_data}", ephemeral=True)
            return
        
        logger.info(f"Successfully purchased {item_name} for {item_price} coins")
        
        # Show purchase confirmation in the original message
        team_coins = response_data.get("teamCoins", self.team_coins - item_price)
        
        # Update the embed to show the purchase
        purchase_embed = discord.Embed(
            title="🛒 Purchase Complete!",
            description=f"You purchased **{item_name}** for {item_price} coins. Your team now has {team_coins} coins remaining.\n\nRoll is now continuing...",
            color=discord.Color.green()
        )
        
        # Show information about the purchased item
        purchase_embed.add_field(
            name="Item Acquired",
            value=self.item.get("description", "No description available."),
            inline=False
        )
        
        # Disable all buttons after purchase
        for item in self.children:
            item.disabled = True
        
        # Update the message
        await self.roll_message.edit(embed=purchase_embed, view=self)

        logger.info(f"Waiting 3 seconds before continuing roll progression after purchase of {item_name}")
        await asyncio.sleep(3)
        
        # Process next step of roll as shops only allow one purchase
        next_response = response_data.get("nextStep", {})
        if next_response:
            logger.debug(f"Processing next roll step after purchase: {next_response}")
            await self.cog.process_roll_progression(interaction, next_response)
        else:
            # If there's no next step provided, clean up the active roll
            if self.team_id in self.cog.active_rolls:
                del self.cog.active_rolls[self.team_id]
                logger.info(f"Cleaned up active roll for team {self.team_id} after item purchase")
        
        # Process the next step of the roll
        await self.cog.process_roll_progression(interaction, response_data)
        # Let the user know their purchase was successful
        #await interaction.followup.send(f"You purchased {item_name}! Check the updated message.", ephemeral=True)
    
    async def back_to_items(self, interaction: discord.Interaction):
        """Go back to the shop items list"""
        logger.info(f"User {interaction.user.id} is returning to shop item list")
        await interaction.response.defer(ephemeral=True)
        
        # Create a detailed embed showing all items
        embed = discord.Embed(
            title="🛒 Available Items",
            description="Choose an item to buy",
            color=discord.Color.purple()
        )
        
        # Create a shop view with all items
        shop_view = RollShopView(
            self.cog,
            self.event_id,
            self.team_id,
            self.all_items,
            self.team_coins,
            self.initiator_id,
            self.roll_message
        )
        
        # Update the message with item list
        await self.roll_message.edit(embed=embed, view=shop_view)
        
        # Let the user know they've returned to the item list
        #await interaction.followup.send("Returning to item list.", ephemeral=True)
    
    async def continue_journey(self, interaction: discord.Interaction):
        """Continue the journey without buying anything"""
        logger.info(f"User {interaction.user.id} chose to continue journey from item detail view")
        await interaction.response.defer(ephemeral=True)
        
        # Call API to continue the journey
        success, response_data = await self.cog.call_backend_api(
            f"/events/{self.event_id}/teams/{self.team_id}/roll/continue",
            method="POST"
        )
        
        if not success:
            logger.error(f"Failed to continue journey: {response_data}")
            await interaction.followup.send(f"Failed to continue journey: {response_data}", ephemeral=True)
            return
        
        logger.debug(f"Continue journey API response: {json.dumps(response_data)[:200]}...")
        
        # Process the next step of the roll
        await self.cog.process_roll_progression(interaction, response_data)
        
        # Let the user know their selection was received
        #await interaction.followup.send("Continuing journey without buying anything! Check the updated message.", ephemeral=True)

class FirstRollIslandSelectView(RollBaseView): # Inherit from RollBaseView
    def __init__(self, cog, event_id: str, team_id: str, 
                 available_islands: list, first_roll_total: int, 
                 initiator_id: str, 
                 roll_message: discord.Message): 
        super().__init__(cog, event_id, team_id, initiator_id, roll_message)
        
        self.first_roll_total = first_roll_total

        if not available_islands:
            logger.warning(f"FirstRollIslandSelectView initialized for team {team_id} with no available islands.")
            # Optionally add a disabled item or label to the view
            # self.add_item(discord.ui.Button(label="No islands available", disabled=True))
            return

        select_options = []
        for island in available_islands:
            select_options.append(discord.SelectOption(
                label=island.get("name", "Unknown Island")[:100], 
                value=str(island.get("id")), 
                description=(island.get("description", "") or "Select this island.")[:100] 
            ))
        
        if len(select_options) > 25:
            logging.warning(f"Too many islands ({len(select_options)}) for select menu for team {team_id}. Truncating to 25.")
            select_options = select_options[:25]
        
        if not select_options: 
             logging.error(f"No valid island options to display for team {team_id} after processing.")
             return

        island_select = discord.ui.Select(
            placeholder="Choose your starting island...",
            options=select_options,
            custom_id=f"sp3_island_select:{team_id}" 
        )
        island_select.callback = self.island_select_callback
        self.add_item(island_select)
        logger.debug(f"FirstRollIslandSelectView populated with {len(select_options)} islands for team {team_id}.")

    async def island_select_callback(self, interaction: discord.Interaction):
        chosen_island_id = interaction.data["values"][0]
        # --- CORRECTED DEFER CALL ---
        await interaction.response.defer(ephemeral=True) 
        # --- END CORRECTION ---

        logger.info(f"Team {self.team_id} (Initiator: {self.initiator_id}) selected island {chosen_island_id}. First roll total was {self.first_roll_total}.")

        try:
            action_type_island_selection = "island_selection" # Use string directly
            # Fallback logic if ACTION_TYPES is defined in cog or globally (less likely for this view)
            # if hasattr(self.cog, 'ACTION_TYPES') and "ISLAND_SELECTION" in self.cog.ACTION_TYPES:
            #      action_type_island_selection = self.cog.ACTION_TYPES["ISLAND_SELECTION"]
            # elif 'ACTION_TYPES' in globals() and "ISLAND_SELECTION" in globals()['ACTION_TYPES']:
            #      action_type_island_selection = globals()['ACTION_TYPES']["ISLAND_SELECTION"]


            success, response_data = await self.cog.call_backend_api( 
                f"/events/{self.event_id}/teams/{self.team_id}/roll/first_island", 
                method="POST",
                payload={ 
                    "chosen_island_id": chosen_island_id,
                    "first_roll_total": self.first_roll_total 
                }
            )

            if success and response_data:
                await self.cog.process_roll_progression(
                    interaction=interaction, 
                    response_data=response_data,
                    existing_message=self.roll_message 
                )
                await interaction.followup.send(f"You selected island {chosen_island_id}. The game is updating...", ephemeral=True)
            else:
                error_message = response_data.get("error", "Failed to process island selection.") if isinstance(response_data, dict) else "Unknown error from API."
                logger.error(f"API call for island selection failed for team {self.team_id}: {error_message}")
                await interaction.followup.send(f"Error processing island selection: {error_message}", ephemeral=True)
        except Exception as e:
            logger.error(f"Exception during island selection callback for team {self.team_id}: {e}", exc_info=True)
            await interaction.followup.send(f"An unexpected error occurred: {str(e)[:1000]}", ephemeral=True)

class ItemBaseView(discord.ui.View):
    def __init__(self, cog, interaction: discord.Interaction, event_id: str, team_id: str, original_message: discord.Message = None):
        super().__init__(timeout=180)  # 3 minutes timeout
        self.cog = cog
        self.original_interaction = interaction
        self.event_id = event_id
        self.team_id = team_id
        self.original_message = original_message

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.original_interaction.user.id:
            await interaction.response.send_message("You cannot interact with this inventory display.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if self.original_message:
            try:
                timeout_embed = discord.Embed(
                    title="Inventory Closed",
                    description="This inventory view has timed out.",
                    color=discord.Color.orange()
                )
                await self.original_message.edit(embed=timeout_embed, view=None)
            except discord.NotFound:
                logger.warning(f"Original message {self.original_message.id} not found on timeout for inventory view.")
            except Exception as e:
                logger.error(f"Error editing message on inventory view timeout: {e}")
        for item in self.children:
            item.disabled = True
        self.stop()

    async def handle_cancel(self, interaction: discord.Interaction):
        # Defer should be done by the calling method with appropriate ephemeral status
        try:
            if self.original_message:
                await self.original_message.delete()
                logger.info(f"Inventory message {self.original_message.id} deleted by user {interaction.user.id}.")
            else: # Fallback
                await interaction.delete_original_response()
                logger.info(f"Original interaction response for inventory deleted by user {interaction.user.id}.")
        except discord.NotFound:
            logger.warning(f"Attempted to delete inventory message for user {interaction.user.id}, but it was already deleted.")
        except Exception as e:
            logger.error(f"Error deleting inventory message for user {interaction.user.id}: {e}")
        self.stop()

class ItemDetailView(ItemBaseView):
    def __init__(self, cog, interaction: discord.Interaction, event_id: str, team_id: str, item_data: dict, all_items: list, original_message: discord.Message):
        super().__init__(cog, interaction, event_id, team_id, original_message)
        self.item_data = item_data
        self.all_items = all_items

        item_name = self.item_data.get("name", "Unknown Item")
        item_id = self.item_data.get("id", "unknown") # Ensure custom_id is valid

        use_button = discord.ui.Button(label=f"Use {item_name}", style=discord.ButtonStyle.green, custom_id=f"item_use_{item_id}")
        use_button.callback = self.use_item_callback
        self.add_item(use_button)

        back_button = discord.ui.Button(label="Back to Inventory", style=discord.ButtonStyle.grey, custom_id="item_back")
        back_button.callback = self.back_to_inventory_callback
        self.add_item(back_button)

        cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.red, custom_id="item_detail_cancel")
        cancel_button.callback = self.cancel_button_callback
        self.add_item(cancel_button)

    async def use_item_callback(self, interaction: discord.Interaction):
        await interaction.response.defer() # Edits original message, so not ephemeral
        item_id = self.item_data.get("id")
        item_name = self.item_data.get("name", "Unknown Item")

        if not item_id:
            await self.original_message.edit(content="Error: Item ID is missing. Cannot use this item.", embed=None, view=None)
            logger.error(f"User {interaction.user.id} tried to use item without ID: {self.item_data}")
            return

        success, response_data = await self.cog.call_backend_api(
            f"/events/{self.event_id}/teams/{self.team_id}/items/use",
            method="POST",
            payload={"itemId": item_id}
        )

        result_embed = discord.Embed(title=f"Using {item_name}")
        if success:
            message = response_data.get("message", f"Successfully used {item_name}.")
            result_embed.description = f"✅ {message}"
            result_embed.color = discord.Color.green()
            logger.info(f"User {interaction.user.id} used item {item_id} for team {self.team_id}. Response: {message}")

            refreshed_items, error_msg = await self.cog._fetch_inventory_items(self.event_id, self.team_id)
            if error_msg:
                result_embed.description += f"\n\n⚠️ Failed to refresh inventory: {error_msg}"
                await self.original_message.edit(embed=result_embed, view=None) # Show use result, then error
                return

            if not refreshed_items:
                result_embed.description += "\n\nYour inventory is now empty."
                await self.original_message.edit(embed=result_embed, view=None)
            else:
                inventory_embed, inventory_view = self.cog._build_inventory_display(
                    self.original_interaction, self.event_id, self.team_id, refreshed_items, self.original_message
                )
                # Prepend use message to the new inventory display
                if inventory_embed.description:
                    inventory_embed.description = f"✅ {message}\n\n{inventory_embed.description}"
                else:
                    inventory_embed.description = f"✅ {message}"
                await self.original_message.edit(embed=inventory_embed, view=inventory_view)
        else:
            error_message = response_data if isinstance(response_data, str) else response_data.get("detail", "Failed to use item.")
            result_embed.description = f"❌ {error_message}"
            result_embed.color = discord.Color.red()
            logger.error(f"User {interaction.user.id} failed to use item {item_id} for team {self.team_id}. Error: {error_message}")
            await self.original_message.edit(embed=result_embed, view=self) # Re-show current view with error

    async def back_to_inventory_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        inventory_embed, inventory_view = self.cog._build_inventory_display(
            self.original_interaction, self.event_id, self.team_id, self.all_items, self.original_message
        )
        await self.original_message.edit(embed=inventory_embed, view=inventory_view)

    async def cancel_button_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.handle_cancel(interaction)

class InventoryView(ItemBaseView):
    def __init__(self, cog, interaction: discord.Interaction, event_id: str, team_id: str, items: list):
        super().__init__(cog, interaction, event_id, team_id)
        self.items = items

        for item_data in self.items:
            item_name = item_data.get("name", "Unknown Item")
            item_id = item_data.get("id", item_name.replace(" ", "_").lower()) # Fallback custom_id
            button = discord.ui.Button(label=item_name, style=discord.ButtonStyle.secondary, custom_id=f"inventory_view_item_{item_id}")
            button.callback = self.create_show_item_detail_callback(item_data)
            self.add_item(button)

        cancel_button = discord.ui.Button(label="Close Inventory", style=discord.ButtonStyle.red, custom_id="inventory_cancel_main")
        cancel_button.callback = self.cancel_button_callback
        self.add_item(cancel_button)

    def create_show_item_detail_callback(self, item_data: dict):
        async def callback(interaction: discord.Interaction):
            await interaction.response.defer()
            detailed_view = ItemDetailView(
                self.cog,
                interaction,
                self.event_id,
                self.team_id,
                item_data,
                self.items,
                self.original_message
            )
            await self.original_message.edit(view=detailed_view)
        return callback

    async def cancel_button_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.handle_cancel(interaction)
