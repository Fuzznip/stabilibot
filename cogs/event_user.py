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
    def __init__(self, data: Dict[str, Any]):
        self.eventId = data.get("event_id", "")
        self.teamId = data.get("team_id", "")
        self.startingTileId = data.get("starting_tile_id", "")
        self.currentTileId = data.get("current_tile_id", "")
        self.rollDistanceTotal = data.get("roll_total", 0)
        self.rollDistanceRemaining = data.get("roll_remaining", 0)
        self.rollType = data.get("action_required", "end")
        self.data = data.get("action_data", {})
        
        logger.debug(f"Roll payload initialized: type={self.rollType}, event={self.eventId}, team={self.teamId}, " +
                    f"distance={self.rollDistanceTotal}, remaining={self.rollDistanceRemaining}")

class EventUser(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = os.getenv("BACKEND_URL")
        # Dictionary to track active rolls and who initiated them
        self.active_rolls: Dict[str, str] = {}  # team_id -> discord_user_id
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

        # Return the first active event
        return events[0], None
    
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
    
    # Get Team Stats Command
    @discord.slash_command(name="event_stats", description="View your team's current stats and location", guild_ids=[int(os.getenv("GUILD_ID"))])
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
        
        # Create a detailed embed with the team stats
        team_name = response_data.get("team_name", "Unknown Team")
        members = response_data.get("members", [])
        stars = response_data.get("stars", 0)
        coins = response_data.get("coins", 0)
        
        current_location = response_data.get("current_location", {})
        tile_num = current_location.get("tile", 0)
        tile_info = current_location.get("tile_info", {})
        region_info = current_location.get("region", {})
        tile_completed = response_data.get("tile_completed", False)
        
        buffs = response_data.get("buffs", [])
        debuffs = response_data.get("debuffs", [])
        items = response_data.get("items", [])
        is_rolling = response_data.get("is_rolling", False)
        
        # Build the embed
        embed = discord.Embed(
            title=f"{team_name} Stats",
            color=discord.Color.gold() if stars > 0 else discord.Color.blue()
        )
        
        # Add basic stats
        embed.add_field(name="⭐ Stars", value=str(stars), inline=True)
        embed.add_field(name="💰 Coins", value=str(coins), inline=True)
        
        # Add location info
        location_value = f"Tile #{tile_num}"
        if tile_info:
            location_value += f" - {tile_info.get('name', 'Unknown')}"
        if region_info:
            location_value += f"\nRegion: {region_info.get('name', 'Unknown')}"
        location_value += f"\nStatus: {'✅ Completed' if tile_completed else '🔄 In Progress'}"
        if is_rolling:
            location_value += " (Rolling)"
        
        embed.add_field(name="📍 Current Location", value=location_value, inline=False)
        
        # Add members list
        if members:
            embed.add_field(name="👥 Team Members", value="\n".join([f"• {member}" for member in members]), inline=False)
        
        # Add buffs, debuffs, and items if there are any
        if buffs:
            embed.add_field(name="✨ Active Buffs", value="\n".join([f"• {buff}" for buff in buffs]) or "None", inline=True)
        
        if debuffs:
            embed.add_field(name="☠️ Active Debuffs", value="\n".join([f"• {debuff}" for debuff in debuffs]) or "None", inline=True)
        
        if items:
            item_names = []
            for item in items:
                if isinstance(item, dict):
                    item_names.append(f"• {item.get('name', 'Unknown Item')}")
                else:
                    item_names.append(f"• {item}")
            
            if item_names:
                embed.add_field(name="🎒 Inventory", value="\n".join(item_names), inline=False)
        
        await interaction.followup.send(embed=embed)
    
    # Get Tile Progress Command
    @discord.slash_command(name="event_progress", description="View your team's current tile progress", guild_ids=[int(os.getenv("GUILD_ID"))])
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
        tile_number = response_data.get("tile_number", 0)
        tile_type = response_data.get("tile_type", "Unknown")
        tile_name = response_data.get("tile_name", "Unknown")
        tile_description = response_data.get("tile_description", "No description available")
        is_completed = response_data.get("is_completed", False)
        progress = response_data.get("progress", {})
        can_roll = response_data.get("can_roll", False)
        
        # Create a detailed embed with tile information
        embed = discord.Embed(
            title=f"Tile #{tile_number}: {tile_name}",
            description=tile_description,
            color=discord.Color.green() if is_completed else discord.Color.blue()
        )
        
        # Add tile type
        embed.add_field(name="Type", value=tile_type, inline=True)
        embed.add_field(name="Status", value="✅ Completed" if is_completed else "🔄 In Progress", inline=True)
        
        # Add progress information if there's any
        if progress:
            progress_text = ""
            for challenge_key, challenge_data in progress.items():
                if isinstance(challenge_data, dict):
                    for task, status in challenge_data.items():
                        progress_text += f"• {task}: {'✅' if status else '❌'}\n"
                else:
                    progress_text += f"• {challenge_key}: {challenge_data}\n"
            
            if progress_text:
                embed.add_field(name="Challenge Progress", value=progress_text, inline=False)
        
        # Add action hint
        if can_roll:
            embed.add_field(name="Available Action", value="You can roll the dice! Use `/event_roll`", inline=False)
        elif is_completed:
            embed.add_field(name="Next Steps", value="Waiting for your team to roll", inline=False)
        else:
            embed.add_field(name="Next Steps", value="Complete the current tile's challenges", inline=False)
        
        await interaction.followup.send(embed=embed)

    # Roll Dice Command
    @discord.slash_command(name="event_roll", description="Roll dice to move forward on the board", guild_ids=[int(os.getenv("GUILD_ID"))])
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
        
        # Check if there's already an active roll for this team
        if team_id in self.active_rolls:
            active_roller_id = self.active_rolls[team_id]
            logger.debug(f"Team {team_id} has an active roll by user {active_roller_id}")
            
            if active_roller_id != str(interaction.user.id):
                # Someone else from the team already has an active roll
                active_roller = await self.bot.fetch_user(int(active_roller_id))
                if active_roller:
                    roller_name = active_roller.display_name
                    logger.info(f"Roll blocked: {interaction.user.display_name} attempted to roll while {roller_name} already has an active roll")
                else:
                    roller_name = "Another player"
                    logger.info(f"Roll blocked: {interaction.user.display_name} attempted to roll while another user already has an active roll")
                
                await interaction.followup.send(f"⚠️ {roller_name} already started a roll for your team. Please wait until their roll sequence is complete.")
                return
            else:
                logger.debug(f"User {interaction.user.id} is continuing their existing roll for team {team_id}")
        
        # Start the roll
        logger.info(f"Starting roll for team {team_id} by user {interaction.user.id}")
        success, response_data = await self.call_backend_api(
            f"/events/{event_id}/teams/{team_id}/roll",
            method="POST"
        )
        
        if not success:
            logger.error(f"Failed to roll dice for team {team_id}: {response_data}")
            await interaction.followup.send(f"Failed to roll dice: {response_data}")
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
    async def process_roll_progression(self, interaction, response_data):
        """Process the roll progression response and update the existing UI"""
        logger.info(f"{json.dumps(response_data, indent=2)}")
        
        try:
            roll_data = RollProgressionPayload(response_data)
            roll_type = roll_data.rollType
            team_id = roll_data.teamId
            
            logger.info(f"Roll progression - Type: {roll_type}, Team: {team_id}, Event: {roll_data.eventId}")
            logger.debug(f"Roll details - From: {roll_data.startingTileId}, To: {roll_data.currentTileId}, " +
                        f"Total: {roll_data.rollDistanceTotal}, Remaining: {roll_data.rollDistanceRemaining}")
            
            # Log all fields in data
            # logger.info(f"{json.dumps(roll_data.data, indent=2)}")

            # Get the stored message for this roll
            roll_message = self.roll_messages.get(team_id)
            if not roll_message:
                logger.warning(f"No stored roll message found for team {team_id}, creating new message")
                roll_message = await interaction.followup.send("🎲 Roll in progress...", wait=True)
                self.roll_messages[team_id] = roll_message
            
            # Create the base embed for the roll
            embed = discord.Embed(
                title="🎲 Roll Progress",
                description=f"Team rolled a total of {roll_data.rollDistanceTotal}. Moving from tile {roll_data.startingTileId} to {roll_data.currentTileId}.",
                color=discord.Color.blue()
            )
            
            if roll_data.rollDistanceRemaining > 0:
                embed.add_field(
                    name="Progress",
                    value=f"Distance remaining: {roll_data.rollDistanceRemaining}/{roll_data.rollDistanceTotal}",
                    inline=False
                )
            
            # Create a view for buttons if needed
            view = None

            # Handle different roll types
            if roll_type == "complete":
                logger.info(f"Roll ended - Team {team_id} completed roll")
                # Roll has ended, show final position
                embed.title = "🎲 Roll Complete!"
                embed.color = discord.Color.green()
                
                current_tile = roll_data.data.get("current_tile", {})
                new_tile_name = current_tile.get("name", "Unknown")
                new_tile_description = current_tile.get("description", "No description available")
                message = roll_data.data.get("message", f"You've landed on {new_tile_name}!")
                
                logger.debug(f"Final tile - Name: {new_tile_name}, Description: {new_tile_description}")
                
                embed.description = message
                
                embed.add_field(
                    name=f"Landed on Tile: {new_tile_name}",
                    value=new_tile_description if new_tile_description else "No description available",
                    inline=False
                )
                
                # Clean up the active roll for this team
                if team_id in self.active_rolls:
                    del self.active_rolls[team_id]
                    logger.info(f"Cleaned up active roll for team {team_id} - Roll completed")
                
                # We don't delete from roll_messages to keep the reference to the final message
                    
            elif roll_type == "crossroad":
                # ...existing crossroad handling code...
                pass
                
            elif roll_type == "shop":
                logger.info(f"Roll at item shop - Team {team_id} is at a shop")
                
                # Get shop data from the payload
                available_items = roll_data.data.get("available_items", [])
                team_coins = roll_data.data.get("coins", 0)
                current_tile = roll_data.data.get("current_tile", {})
                message = roll_data.data.get("message", "You've found a shop!")
                moves_remaining = roll_data.data.get("moves_remaining", 0)
                
                tile_name = current_tile.get("name", "Shop")
                
                logger.debug(f"Shop data: {len(available_items)} items, {team_coins} coins, at tile {tile_name}")
                
                # Create an embed for the shop
                embed.title = "🛒 Item Shop"
                embed.description = message
                embed.color = discord.Color.purple()
                
                embed.add_field(
                    name="Your Team",
                    value=f"💰 **{team_coins} coins** available\n🎲 **{moves_remaining}** moves remaining",
                    inline=False
                )
                
                # Show item count but don't list them all initially
                if not available_items:
                    embed.add_field(
                        name="No Items Available",
                        value="This shop has no items in stock.",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="Available Items",
                        value=f"There are **{len(available_items)}** items available in this shop.",
                        inline=False
                    )
                
                # Create a view for the initial shop choice
                view = RollShopInitialView(
                    self, 
                    roll_data.eventId,
                    team_id, 
                    available_items,
                    team_coins,
                    self.active_rolls[team_id],
                    roll_message
                )
                logger.debug(f"Created initial shop view with {len(available_items)} items")
                
            elif roll_type == "star":
                # ...existing star handling code...
                pass
                
            elif roll_type == "dock":
                logger.info(f"Roll at dock - Team {team_id} is at a ship charter point")
                
                # Get dock data from the payload
                charter_price = roll_data.data.get("charter_price", 10)
                team_coins = roll_data.data.get("coins", 0)
                destinations = roll_data.data.get("destinations", [])
                current_tile = roll_data.data.get("current_tile", {})
                message = roll_data.data.get("message", "You've found a dock!")
                moves_remaining = roll_data.data.get("moves_remaining", 0)
                
                tile_name = current_tile.get("name", "Dock")
                
                logger.debug(f"Dock data: {len(destinations)} destinations, {team_coins} coins, at tile {tile_name}")
                
                # Create an embed for the dock
                embed.title = "⚓ Ship Charter"
                embed.description = message
                embed.color = discord.Color.blue()
                
                embed.add_field(
                    name="Your Team",
                    value=f"💰 **{team_coins} coins** available\n🎲 **{moves_remaining}** moves remaining",
                    inline=False
                )
                
                # Show destination count but don't list them all initially
                if not destinations:
                    embed.add_field(
                        name="No Destinations Available",
                        value="There are no destinations you can charter a ship to.",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="Available Destinations",
                        value=f"There are **{len(destinations)}** islands you can charter a ship to for **{charter_price}** coins each.",
                        inline=False
                    )
                
                # Create a view for the dock initial choice
                view = RollDockInitialView(
                    self, 
                    roll_data.eventId,
                    team_id, 
                    destinations,
                    charter_price,
                    team_coins,
                    self.active_rolls[team_id],
                    roll_message
                )
                logger.debug(f"Created initial dock view with {len(destinations)} destinations")

            try:
                logger.debug(f"Updating roll message {roll_message.id} for team {team_id}")
                await roll_message.edit(content=None, embed=embed, view=view)
                logger.info(f"Roll progression UI updated for team {team_id}")
            except discord.errors.HTTPException as http_error:
                if "Invalid Webhook Token" in str(http_error) or http_error.status == 401:
                    logger.warning(f"Webhook token expired for team {team_id}. Creating a new message.")
                    # The webhook token has expired, create a new message instead
                    new_message = await interaction.followup.send(embed=embed, view=view, wait=True)
                    
                    # Update our tracking to use the new message
                    self.roll_messages[team_id] = new_message
                    logger.info(f"Created new roll message {new_message.id} for team {team_id} due to expired webhook")
                else:
                    # Re-raise other HTTP exceptions
                    raise
        
        except Exception as e:
            logger.error(f"Error in process_roll_progression: {str(e)}", exc_info=True)
            logger.error(traceback.format_exc())
            raise  # Re-raise to be handled by the calling function

# Views for different roll scenarios
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
                f"/events/{self.event_id}/teams/{self.team_id}/roll/direction",
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

# Update other view classes similarly
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
            await interaction.followup.send(f"Viewing details for {item_name}.", ephemeral=True)
        
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
        await interaction.followup.send("Continuing journey without buying anything! Check the updated message.", ephemeral=True)

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
        
        # Let the user know their purchase was successful
        await interaction.followup.send("Star purchased! Check the updated message.", ephemeral=True)
    
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
        await interaction.followup.send("Continuing journey! Check the updated message.", ephemeral=True)

class RollDockView(RollBaseView):
    def __init__(self, cog, event_id: str, team_id: str, destinations: list, charter_price: int, team_coins: int, initiator_id: str, roll_message: discord.Message):
        super().__init__(cog, event_id, team_id, initiator_id, roll_message)
        self.destinations = destinations
        self.charter_price = charter_price
        self.team_coins = team_coins
        
        logger.debug(f"Creating DockView with {len(destinations)} destinations, price: {charter_price}, available coins: {team_coins}")
        
        # Only add destinations that the team can afford
        affordable_destinations = []
        for dest in destinations:
            dest_name = dest.get("name", "Unknown")
            dest_id = dest.get("id", "")
            affordable = team_coins >= charter_price
            
            if affordable:
                affordable_destinations.append((dest_name, dest_id))
                logger.debug(f"Adding affordable destination: {dest_name} (ID: {dest_id})")
            else:
                logger.debug(f"Skipping unaffordable destination: {dest_name} (ID: {dest_id})")
        
        # Add buttons for each destination the team can afford
        for dest_name, dest_id in affordable_destinations:
            button = discord.ui.Button(
                label=f"Travel to {dest_name} ({charter_price} coins)",
                style=discord.ButtonStyle.primary,
                custom_id=f"dock_dest_{dest_id}"
            )
            
            button.callback = self.create_travel_callback(dest_id, dest_name)
            self.add_item(button)
        
        # Add a "Continue Journey" button 
        continue_button = discord.ui.Button(
            label="Continue Journey",
            style=discord.ButtonStyle.secondary,
            custom_id="dock_continue"
        )
        continue_button.callback = self.continue_journey
        self.add_item(continue_button)
        logger.debug("Added continue journey button to dock view")
    
    def create_travel_callback(self, destination_id: str, destination_name: str):
        """Create a callback function for traveling to a destination"""
        async def travel_callback(interaction: discord.Interaction):
            logger.info(f"User {interaction.user.id} is attempting to travel to {destination_name} ({destination_id}) for {self.charter_price} coins")
            await interaction.response.defer(ephemeral=True)
            
            # Call API to travel to the destination
            success, response_data = await self.cog.call_backend_api(
                f"/events/{self.event_id}/teams/{self.team_id}/roll/dock",
                payload={"action": "charter", "destination_island_id": destination_id},
                method="POST"
            )
            
            if not success:
                logger.error(f"Failed to travel to destination {destination_id}: {response_data}")
                await interaction.followup.send(f"Failed to charter ship: {response_data}", ephemeral=True)
                return
            
            logger.info(f"Successfully chartered ship to {destination_name} for {self.charter_price} coins")
            
            # Show travel confirmation in the existing message
            travel_cost = response_data.get("travelCost", self.charter_price)
            team_coins = response_data.get("teamCoins", self.team_coins - travel_cost)
            new_tile_id = response_data.get("newTileId", "Unknown")
            
            # Update the embed
            travel_embed = discord.Embed(
                title="⚓ Ship Chartered!",
                description=f"You traveled to **{destination_name}** for {travel_cost} coins. Your team now has {team_coins} coins remaining.",
                color=discord.Color.blue()
            )
            
            travel_embed.add_field(
                name="New Location",
                value=f"You are now on tile {new_tile_id} ({destination_name})",
                inline=False
            )
            
            # Disable all buttons after selection
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
                    logger.info(f"Cleaned up active roll for team {self.team_id} after traveling to {destination_name}")
            
            # Let the user know their selection was registered
            await interaction.followup.send(f"Ship chartered to {destination_name}! Check the updated message.", ephemeral=True)
            
        return travel_callback
    
    async def continue_journey(self, interaction: discord.Interaction):
        """Continue the journey without chartering a ship"""
        logger.info(f"User {interaction.user.id} chose to continue journey without chartering a ship")
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
        await interaction.followup.send("Continuing journey without chartering a ship! Check the updated message.", ephemeral=True)

class RollDockInitialView(RollBaseView):
    def __init__(self, cog, event_id: str, team_id: str, destinations: list, charter_price: int, team_coins: int, initiator_id: str, roll_message: discord.Message):
        super().__init__(cog, event_id, team_id, initiator_id, roll_message)
        self.destinations = destinations
        self.charter_price = charter_price
        self.team_coins = team_coins
        
        logger.debug(f"Creating DockInitialView with {len(destinations)} destinations, price: {charter_price}, available coins: {team_coins}")
        
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
            description=f"Choose an island to charter a ship to (Cost: {self.charter_price} coins each)",
            color=discord.Color.blue()
        )
        
        # Add detailed info for each destination
        for dest in self.destinations:
            name = dest.get("name", "Unknown Location")
            description = dest.get("description", "No description available.")
            dest_id = dest.get("id", "")
            
            # Check if the team can afford this destination
            affordable = self.team_coins >= self.charter_price
            status = "✅ Available" if affordable else "❌ Not enough coins"
            
            embed.add_field(
                name=f"{name}",
                value=f"{description}\n**Status:** {status}",
                inline=False
            )
        
        # Create a selector view with all destinations
        destination_view = RollDockSelectorView(
            self.cog,
            self.event_id,
            self.team_id,
            self.destinations,
            self.charter_price,
            self.team_coins,
            self.initiator_id,
            self.roll_message
        )
        
        # Update the message with destination details
        await self.roll_message.edit(embed=embed, view=destination_view)
        
        # Let the user know the destinations are displayed
        await interaction.followup.send("Viewing available islands! Check the updated message.", ephemeral=True)
    
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
        await interaction.followup.send("Continuing journey without chartering a ship! Check the updated message.", ephemeral=True)

class RollDockSelectorView(RollBaseView):
    def __init__(self, cog, event_id: str, team_id: str, destinations: list, charter_price: int, team_coins: int, initiator_id: str, roll_message: discord.Message):
        super().__init__(cog, event_id, team_id, initiator_id, roll_message)
        self.destinations = destinations
        self.charter_price = charter_price
        self.team_coins = team_coins
        
        logger.debug(f"Creating DockSelectorView with {len(destinations)} destinations, price: {charter_price}, available coins: {team_coins}")
        
        # Add a Select menu for destinations
        options = []
        self.destination_map = {}  # To map select values to destination IDs
        
        for i, dest in enumerate(destinations):
            dest_name = dest.get("name", "Unknown Location")
            dest_id = dest.get("id", "")
            dest_desc = dest.get("description", "")
            affordable = team_coins >= charter_price
            
            # Truncate description if too long for the select option
            short_desc = dest_desc[:50] + ("..." if len(dest_desc) > 50 else "")
            
            # Store the mapping of select value to destination ID
            select_value = f"dest_{i}"
            self.destination_map[select_value] = {
                "id": dest_id,
                "name": dest_name,
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
        affordable = dest_info.get("affordable", False)
        
        logger.debug(f"Selected destination: {dest_name} (ID: {dest_id}, Affordable: {affordable})")
        
        if not affordable:
            logger.warning(f"User selected unaffordable destination: {dest_name}")
            await interaction.followup.send(f"You don't have enough coins to charter a ship to {dest_name}. You need {self.charter_price} coins.", ephemeral=True)
            
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
        await interaction.followup.send(f"You selected {dest_name}. Click 'Charter Ship' to confirm your travel.", ephemeral=True)
    
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
        
        logger.info(f"Chartering ship to {dest_name} (ID: {dest_id}) for {self.charter_price} coins")
        
        # Call API to travel to the destination
        success, response_data = await self.cog.call_backend_api(
            f"/events/{self.event_id}/teams/{self.team_id}/roll/dock",
            payload={"action": "charter", "destinationId": dest_id},
            method="POST"
        )
        
        if not success:
            logger.error(f"Failed to charter ship to {dest_id}: {response_data}")
            await interaction.followup.send(f"Failed to charter ship: {response_data}", ephemeral=True)
            return
        
        logger.info(f"Successfully chartered ship to {dest_name} for {self.charter_price} coins")
        
        # Show travel confirmation in the existing message
        travel_cost = response_data.get("travelCost", self.charter_price)
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
        
        # Let the user know their selection was registered
        await interaction.followup.send(f"Ship chartered to {dest_name}! Check the updated message.", ephemeral=True)
    
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
        
        embed.add_field(
            name="Available Destinations",
            value=f"There are **{len(self.destinations)}** islands you can charter a ship to for **{self.charter_price}** coins each.",
            inline=False
        )
        
        # Create a new initial view
        initial_view = RollDockInitialView(
            self.cog,
            self.event_id,
            self.team_id,
            self.destinations,
            self.charter_price,
            self.team_coins,
            self.initiator_id,
            self.roll_message
        )
        
        # Update the message
        await self.roll_message.edit(embed=embed, view=initial_view)
        
        # Let the user know they've returned to the initial view
        await interaction.followup.send("Returning to ship charter options.", ephemeral=True)

class RollShopInitialView(RollBaseView):
    def __init__(self, cog, event_id: str, team_id: str, available_items: list, team_coins: int, initiator_id: str, roll_message: discord.Message):
        super().__init__(cog, event_id, team_id, initiator_id, roll_message)
        self.available_items = available_items
        self.team_coins = team_coins
        
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
        await interaction.followup.send("Viewing available items! Check the updated message.", ephemeral=True)
    
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
        await interaction.followup.send("Continuing journey without buying anything! Check the updated message.", ephemeral=True)

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
            payload={"action": "buy", "itemId": self.item_id},
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
            description=f"You purchased **{item_name}** for {item_price} coins. Your team now has {team_coins} coins remaining.",
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
        
        # Let the user know their purchase was successful
        await interaction.followup.send(f"You purchased {item_name}! Check the updated message.", ephemeral=True)
    
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
        await interaction.followup.send("Returning to item list.", ephemeral=True)
    
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
        await interaction.followup.send("Continuing journey without buying anything! Check the updated message.", ephemeral=True)

def setup(bot):
    logger.info("Adding EventUser cog to bot")
    bot.add_cog(EventUser(bot))
    logger.info("EventUser cog successfully added")
