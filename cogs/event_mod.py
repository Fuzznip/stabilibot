from discord.ext import commands
import discord
from dotenv import load_dotenv
load_dotenv()
import os
import json
import aiohttp
import logging

class AddToTeamSelectView(discord.ui.View):
    def __init__(self, target_member, teams, cog, event_id):
        super().__init__(timeout=300)
        self.target_member = target_member
        self.cog = cog
        self.event_id = event_id

        self.team_select = discord.ui.Select(
            placeholder="Select a team",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=f"{team.get('name', 'Unknown')}",
                    description=f"ID: {team.get('id', 'Unknown')}",
                    value=json.dumps({"id": team.get('id', 'Unknown'), "name": team.get('name', 'Unknown')})
                ) for team in teams
            ]
        )

        self.team_select.callback = self.team_selected
        self.add_item(self.team_select)

    async def team_selected(self, interaction):
        if not await self.cog.check_mod_permissions(interaction):
            return

        selected = json.loads(self.team_select.values[0])
        team_id = selected["id"]
        team_name = selected["name"]

        await interaction.response.defer(ephemeral=True)

        # Call API to add player to team
        payload = {
            "discord_id": str(self.target_member.id),
        }

        success, response_data = await self.cog.call_backend_api(
            f"/v2/teams/{team_id}/members",
            payload,
            interaction
        )

        if not success:
            await interaction.followup.send(f"Failed to add player to team: {response_data}", ephemeral=True)
            return

        # Create or find the Discord role with the team name and assign it
        guild = interaction.guild
        role = discord.utils.get(guild.roles, name=team_name)

        if not role:
            try:
                role = await guild.create_role(name=team_name, mentionable=True)
            except discord.Forbidden:
                await interaction.followup.send(
                    f"Added {self.target_member.display_name} to team '{team_name}' via API, but I don't have permission to create the Discord role.",
                    ephemeral=True
                )
                return

        try:
            await self.target_member.add_roles(role)
        except discord.Forbidden:
            await interaction.followup.send(
                f"Added {self.target_member.display_name} to team '{team_name}' via API, but I don't have permission to assign the role.",
                ephemeral=True
            )
            return

        await interaction.message.edit(
            content=f"Added {self.target_member.display_name} to team **{team_name}** and assigned the **{team_name}** role.",
            view=None
        )
        await interaction.followup.send("Done!", ephemeral=True)


class TeamSelectView(discord.ui.View):
    def __init__(self, user, teams, cog, event_id):
        super().__init__(timeout=300)  # 5 minute timeout
        self.user = user
        self.cog = cog
        self.event_id = event_id
        
        # Create team select dropdown
        self.team_select = discord.ui.Select(
            placeholder="Select a team",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=f"{team.get('name', 'Unknown')}",
                    description=f"ID: {team.get('id', 'Unknown')}",
                    value=team.get('id', 'Unknown')
                ) for team in teams
            ]
        )
        
        self.team_select.callback = self.team_selected
        self.add_item(self.team_select)
    
    async def team_selected(self, interaction):
        if not await self.cog.check_mod_permissions(interaction):
            return
            
        team_id = self.team_select.values[0]
        
        # Instead of opening a modal, directly add the user to the team
        await interaction.response.defer(ephemeral=True)
        
        # Call API to add user's Discord ID to the team
        payload = {
            "discord_id": str(self.user.id),
            "username": self.user.display_name,
        }
        
        success, response_data = await self.cog.call_backend_api(
            f"/events/{self.event_id}/moderation/teams/{team_id}/members",
            payload,
            interaction
        )
        
        if success:
            member_id = response_data.get('member_id')
            usernames = response_data.get('usernames', [])
            
            # Create a success message with the registered usernames
            message = f"✅ Added {self.user.display_name} (Discord ID: {self.user.id}) to team successfully!\nMember ID: {member_id}"
            
            if usernames:
                message += "\n\nRegistered usernames added:"
                for username in usernames:
                    message += f"\n• {username}"
        
            # Update the existing message instead of creating a new one and deleting the old one
            await interaction.message.edit(content=message, view=None)
            await interaction.followup.send("User added to team successfully!", ephemeral=True)
        else:
            await interaction.followup.send(f"Failed to add user to team: {response_data}", ephemeral=True)

class TeamSelectionView(discord.ui.View):
    def __init__(self, cog, teams, interaction, action_type, timeout=180):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.teams = teams
        self.original_interaction = interaction
        self.action_type = action_type  # rename, set_stars, set_coins, complete_tile, undo_turn
        
        # Create team select dropdown
        options = []
        for team in teams:
            team_id = team.get('id', 'Unknown')
            team_name = team.get('name', 'Unknown')
            
            # Get stars and coins if available
            team_data = team.get('data', {})
            stars = team_data.get('stars', 0) if team_data else 0
            coins = team_data.get('coins', 0) if team_data else 0
            current_tile = team_data.get('currentTile', 0) if team_data else 0
            
            description = f"Stars: {stars} | Coins: {coins} | Tile: {current_tile}"
            
            options.append(discord.SelectOption(
                label=team_name[:25],  # Discord limits option label length
                description=f"ID: {team_id}",
                value=team_id
            ))
        
        self.team_select = discord.ui.Select(
            placeholder="Select a team",
            min_values=1,
            max_values=1,
            options=options
        )
        
        self.team_select.callback = self.team_selected
        self.add_item(self.team_select)
    
    async def team_selected(self, interaction):
        team_id = self.team_select.values[0]
        selected_team = next((team for team in self.teams if team.get('id') == team_id), None)
        
        if not selected_team:
            await interaction.response.send_message("Team not found. Please try again.", ephemeral=True)
            return
        
        team_name = selected_team.get('name', 'Unknown')
        
        # Handle different actions based on action_type
        if self.action_type == "rename":
            # Show rename modal
            modal = TeamRenameModal(self.cog, team_id, team_name)
            await interaction.response.send_modal(modal)
            
        elif self.action_type == "set_stars":
            # Show set stars modal
            team_data = selected_team.get('data', {})
            current_stars = team_data.get('stars', 0) if team_data else 0
            modal = TeamStarsModal(self.cog, team_id, team_name, current_stars)
            await interaction.response.send_modal(modal)
            
        elif self.action_type == "set_coins":
            # Show set coins modal
            team_data = selected_team.get('data', {})
            current_coins = team_data.get('coins', 0) if team_data else 0
            modal = TeamCoinsModal(self.cog, team_id, team_name, current_coins)
            await interaction.response.send_modal(modal)
            
        elif self.action_type == "complete_tile":
            # Directly complete the tile
            await interaction.response.defer(ephemeral=True)
            
            event, error = await self.cog.get_active_event(interaction)
            if error:
                await interaction.followup.send(error, ephemeral=True)
                return
                
            event_id = event.get('id')
            
            payload = {
                "moderator_id": str(interaction.user.id)
            }
            
            success, response_data = await self.cog.call_backend_api(
                f"/events/{event_id}/moderation/teams/{team_id}/complete-tile",
                payload,
                interaction
            )
            
            if success:
                await interaction.followup.send(f"Tile completed successfully for team '{team_name}'.", ephemeral=True)
            else:
                await interaction.followup.send(f"Failed to complete tile: {response_data}", ephemeral=True)
                

        elif self.action_type == "move_team_to_tile":
            # Show set stars modal
            team_data = selected_team.get('data', {})
            current_tile = team_data.get('currentTile', "") if team_data else ""
            modal = TeamMoveToTileModal(self.cog, team_id, team_name, current_tile)
            await interaction.response.send_modal(modal)
            
        elif self.action_type == "undo_turn":
            # Directly undo the turn
            await interaction.response.defer(ephemeral=True)
            
            event, error = await self.cog.get_active_event(interaction)
            if error:
                await interaction.followup.send(error, ephemeral=True)
                return
                
            event_id = event.get('id')
            
            payload = {
                "moderator_id": str(interaction.user.id)
            }
            
            success, response_data = await self.cog.call_backend_api(
                f"/events/{event_id}/moderation/teams/{team_id}/undo-roll",
                payload,
                interaction
            )
            
            if success:
                await interaction.followup.send(f"Last turn undone successfully for team '{team_name}'.", ephemeral=True)
            else:
                await interaction.followup.send(f"Failed to undo last turn: {response_data}", ephemeral=True)
                
        elif self.action_type == "team_details":
            # Show team details
            await interaction.response.defer(ephemeral=True)
            
            event, error = await self.cog.get_active_event(interaction)
            if error:
                await interaction.followup.send(error, ephemeral=True)
                return
                
            event_id = event.get('id')
            
            success, response_data = await self.cog.call_backend_api(
                f"/events/{event_id}/teams/{team_id}/stats",
                None,
                interaction,
                method="GET"
            )
            
            if success:
                team = response_data
                if not team:
                    await interaction.followup.send(f"Team with ID {team_id} not found.", ephemeral=True)
                    return
                
                team_name = team.get('name', 'Unknown')
                captain_id = team.get('captain', 'Unknown')
                members = team.get('members', [])
                
                # Get stars and coins from team data if available
                team_data = team.get('data', {})
                stars = team_data.get('stars', 0) if team_data else 0
                coins = team_data.get('coins', 0) if team_data else 0
                current_tile = team_data.get('currentTile', 0) if team_data else 0
                
                embed = discord.Embed(title=f"Team: {team_name}", color=discord.Color.gold())
                embed.add_field(name="Team ID", value=team_id, inline=True)
                embed.add_field(name="Captain ID", value=captain_id, inline=True)
                embed.add_field(name="Stars", value=stars, inline=True)
                embed.add_field(name="Coins", value=coins, inline=True)
                embed.add_field(name="Current Tile", value=current_tile, inline=True)
                
                # List members
                if members:
                    member_list = []
                    for member in members:
                        member_list.append(f"{member}")
                    
                    embed.add_field(
                        name="Members", 
                        value="\n".join(member_list), 
                        inline=False
                    )
                else:
                    embed.add_field(name="Members", value="No members", inline=False)
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(f"Failed to get team details: {response_data}", ephemeral=True)

# Modal for team rename
class TeamRenameModal(discord.ui.Modal):
    def __init__(self, cog, team_id, current_name):
        super().__init__(title=f"Rename Team: {current_name}")
        self.cog = cog
        self.team_id = team_id
        
        self.new_name = discord.ui.InputText(
            label="New Team Name",
            placeholder="Enter the new name for the team",
            style=discord.InputTextStyle.short,
            max_length=100,
            required=True
        )
        self.add_item(self.new_name)
    
    async def callback(self, interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Get the first active STABILITY_PARTY event
        event, error = await self.cog.get_active_event(interaction)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return
            
        event_id = event.get('id')
        
        payload = {
            "name": self.new_name.value,
            "moderator_id": str(interaction.user.id)
        }
        
        success, response_data = await self.cog.call_backend_api(
            f"/events/{event_id}/moderation/teams/{self.team_id}/rename",
            payload,
            interaction
        )
        
        if success:
            await interaction.followup.send(f"Team renamed to '{self.new_name.value}' successfully.", ephemeral=True)
        else:
            await interaction.followup.send(f"Failed to rename team: {response_data}", ephemeral=True)

# Modal for setting team stars
class TeamStarsModal(discord.ui.Modal):
    def __init__(self, cog, team_id, team_name, current_stars=0):
        super().__init__(title=f"Set Stars for: {team_name}")
        self.cog = cog
        self.team_id = team_id
        
        self.stars = discord.ui.InputText(
            label="Stars",
            placeholder="Enter the number of stars",
            style=discord.InputTextStyle.short,
            value=str(current_stars),
            required=True
        )
        self.add_item(self.stars)
    
    async def callback(self, interaction):
        try:
            stars = int(self.stars.value)
        except ValueError:
            await interaction.response.send_message("Please enter a valid number for stars.", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        
        # Get the first active STABILITY_PARTY event
        event, error = await self.cog.get_active_event(interaction)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return
            
        event_id = event.get('id')
        
        payload = {
            "stars": stars,
            "moderator_id": str(interaction.user.id)
        }
        
        success, response_data = await self.cog.call_backend_api(
            f"/events/{event_id}/moderation/teams/{self.team_id}/stars",
            payload,
            interaction,
            method="PUT"
        )
        
        if success:
            await interaction.followup.send(f"Team stars set to {stars} successfully.", ephemeral=True)
        else:
            await interaction.followup.send(f"Failed to set team stars: {response_data}", ephemeral=True)

# Modal for setting team coins
class TeamCoinsModal(discord.ui.Modal):
    def __init__(self, cog, team_id, team_name, current_coins=0):
        super().__init__(title=f"Set Coins for: {team_name}")
        self.cog = cog
        self.team_id = team_id
        
        self.coins = discord.ui.InputText(
            label="Coins",
            placeholder="Enter the number of coins",
            style=discord.InputTextStyle.short,
            value=str(current_coins),
            required=True
        )
        self.add_item(self.coins)
    
    async def callback(self, interaction):
        try:
            coins = int(self.coins.value)
        except ValueError:
            await interaction.response.send_message("Please enter a valid number for coins.", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        
        # Get the first active STABILITY_PARTY event
        event, error = await self.cog.get_active_event(interaction)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return
            
        event_id = event.get('id')
        
        payload = {
            "coins": coins,
            "moderator_id": str(interaction.user.id)
        }
        
        success, response_data = await self.cog.call_backend_api(
            f"/events/{event_id}/moderation/teams/{self.team_id}/coins",
            payload,
            interaction,
            method="PUT"
        )
        
        if success:
            await interaction.followup.send(f"Team coins set to {coins} successfully.", ephemeral=True)
        else:
            await interaction.followup.send(f"Failed to set team coins: {response_data}", ephemeral=True)

class TeamMoveToTileModal(discord.ui.Modal):
    def __init__(self, cog, team_id, team_name, tile_id):
        super().__init__(title=f"Move Team to Tile: {team_name}")
        self.cog = cog
        self.team_id = team_id
        self.tile_id = tile_id
        
        self.tile = discord.ui.InputText(
            label="Tile Number",
            placeholder="Enter the tile id to move the team to",
            style=discord.InputTextStyle.long,
            required=True
        )
        self.add_item(self.tile)
    
    async def callback(self, interaction):
        await interaction.response.defer(ephemeral=True)
        
        tile = self.tile.value

        # Get the first active STABILITY_PARTY event
        event, error = await self.cog.get_active_event(interaction)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return
            
        event_id = event.get('id')
        
        payload = {
            "tile_id": tile,
            "moderator_id": str(interaction.user.id)
        }
        
        success, response_data = await self.cog.call_backend_api(
            f"/events/{event_id}/moderation/teams/{self.team_id}/move-to-tile",
            payload,
            interaction,
            method="PUT"
        )

        logging.info(f"Move team to tile response: {response_data}")
        
        if success:
            await interaction.followup.send(f"{response_data['message']}", ephemeral=True)
        else:
            await interaction.followup.send(f"Failed to move team: {response_data}", ephemeral=True)

class EventMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = os.getenv("BACKEND_URL")
    
    # Helper to get the first active stability party event
    async def get_active_event(self, interaction):
        # Fetch available events
        success, response_data = await self.call_backend_api(
            "/v2/events/active",
            None,
            interaction,
            method="GET"
        )
        
        if not success:
            return None, f"Failed to retrieve events: {response_data}"
        
        # # Get available events with type="STABILITY_PARTY"
        # stability_party_events = [event for event in response_data if event.get('type') == "STABILITY_PARTY"]
        
        # if not stability_party_events:
        #     return None, "No active STABILITY_PARTY events found"
        
        # # Return the first active event
        # event = stability_party_events[0]
        return response_data, None
    
    # Helper to check if user has event moderator permissions
    async def check_mod_permissions(self, interaction):
        # Check if user has the Event Moderator role or is an administrator
        if interaction.user.guild_permissions.administrator:
            return True
        
        event_mod_role = discord.utils.get(interaction.guild.roles, name="Staff")
        if event_mod_role and event_mod_role in interaction.user.roles:
            return True
        
        await interaction.response.send_message("You don't have permission to use event moderation commands.", ephemeral=True)
        return False
    
    # Helper method to make API calls to the backend
    async def call_backend_api(self, endpoint, payload=None, interaction=None, method="POST"):
        url = f"{self.backend_url}{endpoint}"
        
        try:
            async with aiohttp.ClientSession() as session:
                if method == "GET":
                    async with session.get(url) as response:
                        if response.status in [200, 201]:
                            try:
                                data = await response.json()
                                return True, data
                            except aiohttp.ContentTypeError:
                                # Handle non-JSON responses
                                data = await response.text()
                                return True, json.loads(data)
                        else:
                            error_text = await response.text()
                            print(f"Error calling {url}: {response.status} - {error_text}")
                            return False, f"Error: {response.status} - {error_text}"
                
                elif method == "POST":
                    async with session.post(url, json=payload) as response:
                        if response.status in [200, 201]:
                            try:
                                data = await response.json()
                            except aiohttp.ContentTypeError:
                                data = await response.text()
                                return True, json.loads(data)
                        else:
                            error_text = await response.text()
                            print(f"Error calling {url}: {response.status} - {error_text}")
                            return False, f"Error: {response.status} - {error_text}"

                elif method == "PUT":
                    async with session.put(url, json=payload) as response:
                        if response.status in [200, 201]:
                            try:
                                data = await response.json()
                            except aiohttp.ContentTypeError:
                                data = await response.text()
                                return True, json.loads(data)
                        else:
                            error_text = await response.text()
                            print(f"Error calling {url}: {response.status} - {error_text}")
                            return False, f"Error: {response.status} - {error_text}"
                
                elif method == "DELETE":
                    async with session.delete(url, json=payload if payload else {}) as response:
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
            print(f"Connection error to {url}: {str(e)}")
            return False, f"Connection error: {str(e)}\nMake sure your backend server is running at {self.backend_url}"
        except Exception as e:
            print(f"Unexpected error calling {url}: {str(e)}")
            return False, f"Unexpected error: {str(e)}"

    # Add Player to Team Command
    @discord.slash_command(name="add_to_team", description="Add a player to an event team", guild_ids=[int(os.getenv("GUILD_ID"))])
    async def add_to_team(self, interaction, player: discord.Member):
        print(f"{interaction.user.display_name}: /add_to_team {player.display_name}")

        if not await self.check_mod_permissions(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        # Get the first active STABILITY_PARTY event
        event, error = await self.get_active_event(interaction)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        event_id = event.get('id')
        event_name = event.get('name')

        teams = event.get('teams', [])
        if not teams:
            await interaction.followup.send("No teams found for this event.", ephemeral=True)
            return

        # Show team selection dropdown
        view = AddToTeamSelectView(player, teams, self, event_id)
        await interaction.followup.send(
            f"Select a team to add **{player.display_name}** to for event '{event_name}':",
            view=view,
            ephemeral=True
        )

    # Create Team Command
    @discord.slash_command(name="event_create_team", description="Create a new event team", guild_ids=[int(os.getenv("GUILD_ID"))])
    async def create_team(self, interaction, team_name: str, captain_id: str):
        print(f"{interaction.user.display_name}: /event_create_team {team_name} {captain_id}")
        
        if not await self.check_mod_permissions(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Get the first active STABILITY_PARTY event
        event, error = await self.get_active_event(interaction)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return
            
        event_id = event.get('id')
        
        payload = {
            "name": team_name,
            "discord_id": captain_id,
            "moderator_id": str(interaction.user.id)
        }
        
        success, response_data = await self.call_backend_api(
            f"/events/{event_id}/moderation/teams",
            payload,
            interaction
        )
        
        if success:
            message = f"Team '{team_name}' created successfully for event {event.get('name')}.\nTeam ID: {response_data.get('team_id')}"
            discord_info = response_data.get('discord', {})
            if discord_info:
                message += f"\nDiscord Role ID: {discord_info.get('role_id')}"
                message += f"\nText Channel ID: {discord_info.get('text_channel_id')}"
                message += f"\nVoice Channel ID: {discord_info.get('voice_channel_id')}"
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.followup.send(f"Failed to create team: {response_data}", ephemeral=True)
    
    # Rename Team Command
    @discord.slash_command(name="event_rename_team", description="Rename an event team", guild_ids=[int(os.getenv("GUILD_ID"))])
    async def rename_team(self, interaction):
        print(f"{interaction.user.display_name}: /event_rename_team")
        
        if not await self.check_mod_permissions(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Get the first active STABILITY_PARTY event
        event, error = await self.get_active_event(interaction)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return
            
        event_id = event.get('id')
        
        # Get teams for this event
        success, teams = await self.call_backend_api(
            f"/events/{event_id}/teams",
            None,
            interaction,
            method="GET"
        )
        
        if not success:
            await interaction.followup.send(f"Failed to get teams: {teams}", ephemeral=True)
            return
            
        if not teams:
            await interaction.followup.send("No teams found for this event.", ephemeral=True)
            return
        
        # Show team selection view
        view = TeamSelectionView(self, teams, interaction, "rename")
        await interaction.followup.send("Select a team to rename:", view=view, ephemeral=True)
    
    # Complete Tile Command
    @discord.slash_command(name="event_complete_tile", description="Force completion of a tile for a team (Without rewards, you need to manually do that)", guild_ids=[int(os.getenv("GUILD_ID"))])
    async def complete_tile(self, interaction):
        print(f"{interaction.user.display_name}: /event_complete_tile")
        
        if not await self.check_mod_permissions(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Get the first active STABILITY_PARTY event
        event, error = await self.get_active_event(interaction)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return
            
        event_id = event.get('id')
        
        # Get teams for this event
        success, teams = await self.call_backend_api(
            f"/events/{event_id}/teams",
            None,
            interaction,
            method="GET"
        )
        
        if not success:
            await interaction.followup.send(f"Failed to get teams: {teams}", ephemeral=True)
            return
            
        if not teams:
            await interaction.followup.send("No teams found for this event.", ephemeral=True)
            return
        
        # Show team selection view
        view = TeamSelectionView(self, teams, interaction, "complete_tile")
        await interaction.followup.send("Select a team to complete the current tile for:", view=view, ephemeral=True)
    
    # Set Stars Command
    @discord.slash_command(name="event_set_stars", description="Set the amount of stars a team has", guild_ids=[int(os.getenv("GUILD_ID"))])
    async def set_stars(self, interaction):
        print(f"{interaction.user.display_name}: /event_set_stars")
        
        if not await self.check_mod_permissions(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Get the first active STABILITY_PARTY event
        event, error = await self.get_active_event(interaction)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return
            
        event_id = event.get('id')
        
        # Get teams for this event
        success, teams = await self.call_backend_api(
            f"/events/{event_id}/teams",
            None,
            interaction,
            method="GET"
        )
        
        if not success:
            await interaction.followup.send(f"Failed to get teams: {teams}", ephemeral=True)
            return
            
        if not teams:
            await interaction.followup.send("No teams found for this event.", ephemeral=True)
            return
        
        # Show team selection view
        view = TeamSelectionView(self, teams, interaction, "set_stars")
        await interaction.followup.send("Select a team to set stars for:", view=view, ephemeral=True)
    
    # Set Coins Command
    @discord.slash_command(name="event_set_coins", description="Set the amount of coins a team has", guild_ids=[int(os.getenv("GUILD_ID"))])
    async def set_coins(self, interaction):
        print(f"{interaction.user.display_name}: /event_set_coins")
        
        if not await self.check_mod_permissions(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Get the first active STABILITY_PARTY event
        event, error = await self.get_active_event(interaction)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return
            
        event_id = event.get('id')
        
        # Get teams for this event
        success, teams = await self.call_backend_api(
            f"/events/{event_id}/teams",
            None,
            interaction,
            method="GET"
        )
        
        if not success:
            await interaction.followup.send(f"Failed to get teams: {teams}", ephemeral=True)
            return
            
        if not teams:
            await interaction.followup.send("No teams found for this event.", ephemeral=True)
            return
        
        # Show team selection view
        view = TeamSelectionView(self, teams, interaction, "set_coins")
        await interaction.followup.send("Select a team to set coins for:", view=view, ephemeral=True)
    
    @discord.slash_command(name="event_move_team_to_tile", description="Move a team to a specific tile", guild_ids=[int(os.getenv("GUILD_ID"))])
    async def move_team_to_tile(self, interaction):
        print(f"{interaction.user.display_name}: /event_move_team_to_tile")
        
        if not await self.check_mod_permissions(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Get the first active STABILITY_PARTY event
        event, error = await self.get_active_event(interaction)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return
            
        event_id = event.get('id')
        
        # Get teams for this event
        success, teams = await self.call_backend_api(
            f"/events/{event_id}/teams",
            None,
            interaction,
            method="GET"
        )
        
        if not success:
            await interaction.followup.send(f"Failed to get teams: {teams}", ephemeral=True)
            return
            
        if not teams:
            await interaction.followup.send("No teams found for this event.", ephemeral=True)
            return
        
        # Show team selection view
        view = TeamSelectionView(self, teams, interaction, "move_team_to_tile")
        await interaction.followup.send("Select a team to move to a specific tile:", view=view, ephemeral=True)

    # Undo Last Turn Command
    @discord.slash_command(name="event_undo_turn", description="Undo a team's last turn they rolled for", guild_ids=[int(os.getenv("GUILD_ID"))])
    async def undo_turn(self, interaction):
        print(f"{interaction.user.display_name}: /event_undo_turn")
        
        if not await self.check_mod_permissions(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Get the first active STABILITY_PARTY event
        event, error = await self.get_active_event(interaction)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return
            
        event_id = event.get('id')
        
        # Get teams for this event
        success, teams = await self.call_backend_api(
            f"/events/{event_id}/teams",
            None,
            interaction,
            method="GET"
        )
        
        if not success:
            await interaction.followup.send(f"Failed to get teams: {teams}", ephemeral=True)
            return
            
        if not teams:
            await interaction.followup.send("No teams found for this event.", ephemeral=True)
            return
        
        # Show team selection view
        view = TeamSelectionView(self, teams, interaction, "undo_turn")
        await interaction.followup.send("Select a team to undo the last turn for:", view=view, ephemeral=True)
    
    # Get Teams List Command
    @discord.slash_command(name="event_list_teams", description="List all teams for an event", guild_ids=[int(os.getenv("GUILD_ID"))])
    async def list_teams(self, interaction):
        print(f"{interaction.user.display_name}: /event_list_teams")
        
        if not await self.check_mod_permissions(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Get the first active STABILITY_PARTY event
        event, error = await self.get_active_event(interaction)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return
            
        event_id = event.get('id')
        event_name = event.get('name')
        
        success, response_data = await self.call_backend_api(
            f"/events/{event_id}/teams",
            None,
            interaction,
            method="GET"
        )
        
        if success:
            teams = response_data
            
            if not teams:
                await interaction.followup.send("No teams found for this event.", ephemeral=True)
                return
            
            embed = discord.Embed(title=f"Event Teams - {event_name}", color=discord.Color.blue())
            
            for team in teams:
                team_id = team.get('id', 'Unknown')
                success, response = await self.call_backend_api(
                    f"/events/{event_id}/moderation/teams/{team_id}/members",
                    method="GET"
                )
                team_name = team.get('name', 'Unknown')
                members = response
                
                member_list = "\n".join([f"• {member.get('username', 'Unknown')}" for member in members]) or "No members"
                
                # Get stars and coins from team data if available
                team_data = team.get('data', {})
                stars = team_data.get('stars', 0) if team_data else 0
                coins = team_data.get('coins', 0) if team_data else 0
                
                embed.add_field(
                    name=f"{team_name} (ID: {team_id}) - Stars: {stars} | Coins: {coins}", 
                    value=member_list, 
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(f"Failed to get teams list: {response_data}", ephemeral=True)
    
    # Get Team Details Command
    @discord.slash_command(name="event_team_details", description="Get detailed information about a team", guild_ids=[int(os.getenv("GUILD_ID"))])
    async def team_details(self, interaction):
        print(f"{interaction.user.display_name}: /event_team_details")
        
        if not await self.check_mod_permissions(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Get the first active STABILITY_PARTY event
        event, error = await self.get_active_event(interaction)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return
            
        event_id = event.get('id')
        
        # Get teams for this event
        success, teams = await self.call_backend_api(
            f"/events/{event_id}/teams",
            None,
            interaction,
            method="GET"
        )
        
        if not success:
            await interaction.followup.send(f"Failed to get teams: {teams}", ephemeral=True)
            return
            
        if not teams:
            await interaction.followup.send("No teams found for this event.", ephemeral=True)
            return
        
        # Show team selection view
        view = TeamSelectionView(self, teams, interaction, "team_details")
        await interaction.followup.send("Select a team to view details:", view=view, ephemeral=True)
    
    # Add To Team Context Menu Command
    @discord.user_command(name="Add to Event Team", guild_ids=[int(os.getenv("GUILD_ID"))])
    async def add_to_team_context_menu(self, interaction: discord.Interaction, member: discord.Member):
        print(f"{interaction.user.display_name}: Used context menu to add {member.display_name} to a team")
        
        if not await self.check_mod_permissions(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # First, fetch available events and teams
        event, error = await self.get_active_event(interaction)
        
        if error:
            await interaction.followup.send(f"Failed to retrieve events: {event}", ephemeral=True)
            return
        
        # For simplicity, we'll take the first active event
        event_id = event.get('id')
        event_name = event.get('name')
        
        # Now get teams for this event
        success, teams = await self.call_backend_api(
            f"/events/{event_id}/teams",
            None,
            interaction,
            method="GET"
        )
        
        if not success:
            await interaction.followup.send(f"Failed to retrieve teams: {teams}", ephemeral=True)
            return
        
        if not teams:
            await interaction.followup.send("No teams found for the event.", ephemeral=True)
            return
        
        # Show team selection view
        view = TeamSelectView(member, teams, self, event_id)
        await interaction.followup.send(
            f"Select a team to add {member.display_name} to for event '{event_name}':", 
            view=view,
            ephemeral=True
        )
    
    # Remove From Team Context Menu Command
    @discord.user_command(name="Remove from Event Team", guild_ids=[int(os.getenv("GUILD_ID"))])
    async def remove_from_team_context_menu(self, interaction: discord.Interaction, member: discord.Member):
        print(f"{interaction.user.display_name}: Used context menu to remove {member.display_name} from a team")
        
        if not await self.check_mod_permissions(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Get the first active STABILITY_PARTY event
        event, error = await self.get_active_event(interaction)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return
            
        event_id = event.get('id')
        
        # Now get teams for this event
        success, teams = await self.call_backend_api(
            f"/events/{event_id}/teams",
            None,
            interaction,
            method="GET"
        )
        
        if not success:
            await interaction.followup.send(f"Failed to retrieve teams: {teams}", ephemeral=True)
            return
        
        # Find which team(s) this user is on
        discord_id = str(member.id)
        user_teams = []
        
        for team in teams:
            team_id = team.get('id')
            team_name = team.get('name')
            
            success, _ = await self.call_backend_api(
                f"/events/{event_id}/moderation/teams/{team_id}/members/{discord_id}",
                None,
                None,
                "DELETE"
            )

            if success:
                user_teams.append(team_name)
        
        if not user_teams:
            await interaction.followup.send(f"{member.display_name} is not on any teams for the current event.", ephemeral=True)
            return
        
        # If user is only on one team, remove them directly
        if len(user_teams) == 1:
            if success:
                await interaction.followup.send(f"Successfully removed {member.display_name} from team {team['team_name']}.", ephemeral=True)
            else:
                await interaction.followup.send(f"Failed to remove player from team {user_teams[0]}", ephemeral=True)
        else:
            if success:
                await interaction.followup.send(f"Successfully removed {member.display_name} from teams {', '.join(user_teams)}.", ephemeral=True)
            else:
                await interaction.followup.send(f"Failed to remove player from teams: {', '.join(user_teams)}", ephemeral=True)
