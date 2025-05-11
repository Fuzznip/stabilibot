from dotenv import load_dotenv
load_dotenv()
import discord
from discord.ext import commands
import os
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel
import logging
from typing import Optional, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DiscordRoleAction(BaseModel):
    roles: list[str]
    token: str

class CreateChannelRequest(BaseModel):
    category_name: str
    channel_name: str
    view_roles: List[int]  # Changed from list[str] to List[int]
    access_roles: List[int]  # Changed from list[str] to List[int]
    token: str

class CreateRoleRequest(BaseModel):
    role_name: str
    color: Optional[str] = None  # Hex color code, e.g., "FF0000" for red
    hoist: Optional[bool] = False  # Whether the role should be displayed separately
    mentionable: Optional[bool] = False  # Whether the role can be mentioned
    permissions: Optional[int] = None  # Permission integer
    token: str

class DeleteRoleRequest(BaseModel):
    role_name: str
    token: str

class SetNicknameRequest(BaseModel):
    user_id: int
    nickname: str
    token: str

class V1(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.router = APIRouter()

        @self.router.get("/")
        def root(request: Request, token: str = None):
            if token != os.getenv("API_TOKEN"):
                logger.warning("Invalid token provided to root endpoint")
                return {"error": "Invalid token"}
            logger.info("Valid token provided to root endpoint")
            return {"message": "Welcome to the API!"}
        
        @self.router.post("/{user_id}/roles/add")
        async def add_role(request: Request, response: Response, user_id: int, action: DiscordRoleAction):
            logger.info("Received request to add roles '%s' to user ID %d", ', '.join(action.roles), user_id)
            if action.token != os.getenv("API_TOKEN"):
                logger.warning("Invalid token provided to add_role endpoint")
                response.status_code = 401
                return {"error": "Invalid token"}
            guild = self.bot.get_guild(int(os.getenv("GUILD_ID")))
            if not guild:
                logger.error("Guild not found")
                response.status_code = 404
                return {"error": "Guild not found"}
            
            member = guild.get_member(user_id)
            if not member:
                logger.error("Member with ID %d not found", user_id)
                response.status_code = 404
                return {"error": "Member not found"}
            
            for role_name in action.roles:
                role = discord.utils.get(guild.roles, name=role_name)
                if not role:
                    logger.error("Role '%s' not found", role_name)
                    response.status_code = 404
                    return {"error": "Role not found"}
                
                await member.add_roles(role)
                logger.info("Role '%s' added to user '%s'", role.name, member.name)

            return {"message": f"Roles {', '.join(action.roles)} added to {member.name}"}
        
        @self.router.post("/{user_id}/roles/remove")
        async def remove_role(request: Request, response: Response, user_id: int, action: DiscordRoleAction):
            logger.info("Received request to remove roles '%s' from user ID %d", ', '.join(action.roles), user_id)
            if action.token != os.getenv("API_TOKEN"):
                logger.warning("Invalid token provided to remove_role endpoint")
                response.status_code = 401
                return {"error": "Invalid token"}
            guild = self.bot.get_guild(int(os.getenv("GUILD_ID")))
            if not guild:
                logger.error("Guild not found")
                response.status_code = 404
                return {"error": "Guild not found"}
            
            member = guild.get_member(user_id)
            if not member:
                logger.error("Member with ID %d not found", user_id)
                response.status_code = 404
                return {"error": "Member not found"}
            
            for role_name in action.roles:
                role = discord.utils.get(guild.roles, name=role_name)
                if not role:
                    logger.error("Role '%s' not found", role_name)
                    response.status_code = 404
                    return {"error": "Role not found"}
                
                await member.remove_roles(role)
                logger.info("Role '%s' removed from user '%s'", role.name, member.name)

            return {"message": f"Roles {', '.join(action.roles)} removed from {member.name}"}
        
        @self.router.post("/channels/create-text")
        async def create_text_channel(request: Request, response: Response, channel_request: CreateChannelRequest):
            logger.info(f"Received request to create text channel: {channel_request.channel_name} in category: {channel_request.category_name}")
            
            if channel_request.token != os.getenv("API_TOKEN"):
                logger.warning("Invalid token provided to create_text_channel endpoint")
                response.status_code = 401
                return {"error": "Invalid token"}
            
            guild = self.bot.get_guild(int(os.getenv("GUILD_ID")))
            if not guild:
                logger.error("Guild not found")
                response.status_code = 404
                return {"error": "Guild not found"}
            
            # Find the category
            category = discord.utils.get(guild.categories, name=channel_request.category_name)
            if not category:
                logger.error(f"Category '{channel_request.category_name}' not found")
                response.status_code = 404
                return {"error": f"Category '{channel_request.category_name}' not found"}
            
            # Setup permissions
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
            }
            
            # Add view roles
            for role_id in channel_request.view_roles:
                role = discord.utils.get(guild.roles, id=role_id)
                if not role:
                    logger.error(f"View role '{role_id}' not found")
                    response.status_code = 404
                    return {"error": f"View role '{role_id}' not found"}
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=False)
            
            # Add access roles
            for role_id in channel_request.access_roles:
                role = discord.utils.get(guild.roles, id=role_id)
                if not role:
                    logger.error(f"Access role '{role_id}' not found")
                    response.status_code = 404
                    return {"error": f"Access role '{role_id}' not found"}
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
            try:
                # Create the text channel
                channel = await guild.create_text_channel(
                    name=channel_request.channel_name,
                    category=category,
                    overwrites=overwrites
                )
                logger.info(f"Created text channel '{channel.name}' with ID {channel.id}")
                return {"message": f"Text channel '{channel.name}' created successfully", "channel_id": str(channel.id)}
            except discord.errors.Forbidden:
                logger.error("Bot doesn't have permission to create channels")
                response.status_code = 403
                return {"error": "Bot doesn't have permission to create channels"}
            except Exception as e:
                logger.error(f"Error creating text channel: {str(e)}")
                response.status_code = 500
                return {"error": f"Error creating text channel: {str(e)}"}
        
        @self.router.post("/channels/create-voice")
        async def create_voice_channel(request: Request, response: Response, channel_request: CreateChannelRequest):
            logger.info(f"Received request to create voice channel: {channel_request.channel_name} in category: {channel_request.category_name}")
            
            if channel_request.token != os.getenv("API_TOKEN"):
                logger.warning("Invalid token provided to create_voice_channel endpoint")
                response.status_code = 401
                return {"error": "Invalid token"}
            
            guild = self.bot.get_guild(int(os.getenv("GUILD_ID")))
            if not guild:
                logger.error("Guild not found")
                response.status_code = 404
                return {"error": "Guild not found"}
            
            # Find the category
            category = discord.utils.get(guild.categories, name=channel_request.category_name)
            if not category:
                logger.error(f"Category '{channel_request.category_name}' not found")
                response.status_code = 404
                return {"error": f"Category '{channel_request.category_name}' not found"}
            
            # Setup permissions
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
            }
            
            # Add view roles
            for role_id in channel_request.view_roles:
                role = discord.utils.get(guild.roles, id=role_id)
                if not role:
                    logger.error(f"View role '{role_id}' not found")
                    response.status_code = 404
                    return {"error": f"View role '{role_id}' not found"}
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, connect=False)
            
            # Add access roles
            for role_id in channel_request.access_roles:
                role = discord.utils.get(guild.roles, id=role_id)
                if not role:
                    logger.error(f"Access role '{role_id}' not found")
                    response.status_code = 404
                    return {"error": f"Access role '{role_id}' not found"}
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, connect=True, speak=True)
            
            try:
                # Create the voice channel
                channel = await guild.create_voice_channel(
                    name=channel_request.channel_name,
                    category=category,
                    overwrites=overwrites
                )
                logger.info(f"Created voice channel '{channel.name}' with ID {channel.id}")
                return {"message": f"Voice channel '{channel.name}' created successfully", "channel_id": str(channel.id)}
            except discord.errors.Forbidden:
                logger.error("Bot doesn't have permission to create channels")
                response.status_code = 403
                return {"error": "Bot doesn't have permission to create channels"}
            except Exception as e:
                logger.error(f"Error creating voice channel: {str(e)}")
                response.status_code = 500
                return {"error": f"Error creating voice channel: {str(e)}"}
            
        @self.router.post("/roles/create")
        async def create_role(request: Request, response: Response, role_request: CreateRoleRequest):
            logger.info(f"Received request to create role: {role_request.role_name}")
            
            if role_request.token != os.getenv("API_TOKEN"):
                logger.warning("Invalid token provided to create_role endpoint")
                response.status_code = 401
                return {"error": "Invalid token"}
            
            guild = self.bot.get_guild(int(os.getenv("GUILD_ID")))
            if not guild:
                logger.error("Guild not found")
                response.status_code = 404
                return {"error": "Guild not found"}
            
            # Check if role already exists
            existing_role = discord.utils.get(guild.roles, name=role_request.role_name)
            if existing_role:
                logger.warning(f"Role '{role_request.role_name}' already exists")
                response.status_code = 409
                return {"error": f"Role '{role_request.role_name}' already exists", "role_id": str(existing_role.id)}
            
            try:
                # Set up role parameters
                role_params = {
                    "name": role_request.role_name,
                    "hoist": role_request.hoist,
                    "mentionable": role_request.mentionable,
                }
                
                # Add color if provided
                if role_request.color:
                    try:
                        # Convert hex color to discord.Color
                        color_int = int(role_request.color.strip('#'), 16)
                        role_params["color"] = discord.Color(color_int)
                    except ValueError:
                        logger.warning(f"Invalid color format: {role_request.color}")
                
                # Add permissions if provided
                if role_request.permissions is not None:
                    role_params["permissions"] = discord.Permissions(role_request.permissions)
                
                # Create the role
                new_role = await guild.create_role(**role_params)
                
                logger.info(f"Created role '{new_role.name}' with ID {new_role.id}")
                return {
                    "message": f"Role '{new_role.name}' created successfully",
                    "role_id": str(new_role.id)
                }
            except discord.errors.Forbidden:
                logger.error("Bot doesn't have permission to create roles")
                response.status_code = 403
                return {"error": "Bot doesn't have permission to create roles"}
            except Exception as e:
                logger.error(f"Error creating role: {str(e)}")
                response.status_code = 500
                return {"error": f"Error creating role: {str(e)}"}
        
        @self.router.delete("/roles/delete")
        async def delete_role(request: Request, response: Response, role_request: DeleteRoleRequest):
            logger.info(f"Received request to delete role: {role_request.role_name}")
            
            if role_request.token != os.getenv("API_TOKEN"):
                logger.warning("Invalid token provided to delete_role endpoint")
                response.status_code = 401
                return {"error": "Invalid token"}
            
            guild = self.bot.get_guild(int(os.getenv("GUILD_ID")))
            if not guild:
                logger.error("Guild not found")
                response.status_code = 404
                return {"error": "Guild not found"}
            
            # Find the role to delete
            role = discord.utils.get(guild.roles, name=role_request.role_name)
            if not role:
                logger.error(f"Role '{role_request.role_name}' not found")
                response.status_code = 404
                return {"error": f"Role '{role_request.role_name}' not found"}
            
            try:
                # Store role ID for response
                role_id = str(role.id)
                role_name = role.name
                
                # Delete the role
                await role.delete()
                
                logger.info(f"Deleted role '{role_name}' with ID {role_id}")
                return {
                    "message": f"Role '{role_name}' deleted successfully",
                    "role_id": role_id
                }
            except discord.errors.Forbidden:
                logger.error("Bot doesn't have permission to delete roles")
                response.status_code = 403
                return {"error": "Bot doesn't have permission to delete roles"}
            except Exception as e:
                logger.error(f"Error deleting role: {str(e)}")
                response.status_code = 500
                return {"error": f"Error deleting role: {str(e)}"}

        @self.router.post("/{user_id}/set-nickname")
        async def set_nickname(request: Request, response: Response, user_id: int, nickname_request: SetNicknameRequest):
            logger.info(f"Received request to set nickname for user ID {user_id} to '{nickname_request.nickname}'")
            
            if nickname_request.token != os.getenv("API_TOKEN"):
                logger.warning("Invalid token provided to set_nickname endpoint")
                response.status_code = 401
                return {"error": "Invalid token"}
            
            guild = self.bot.get_guild(int(os.getenv("GUILD_ID")))
            if not guild:
                logger.error("Guild not found")
                response.status_code = 404
                return {"error": "Guild not found"}
            
            member = guild.get_member(user_id)
            if not member:
                logger.error(f"Member with ID {user_id} not found")
                response.status_code = 404
                return {"error": "Member not found"}
            
            try:
                # Set the nickname
                await member.edit(nick=nickname_request.nickname)
                
                logger.info(f"Set nickname for user '{member.name}' to '{nickname_request.nickname}'")
                return {
                    "message": f"Nickname for user '{member.name}' set to '{nickname_request.nickname}'",
                    "user_id": str(member.id)
                }
            except discord.errors.Forbidden:
                logger.error("Bot doesn't have permission to change nicknames")
                response.status_code = 403
                return {"error": "Bot doesn't have permission to change nicknames"}
            except Exception as e:
                logger.error(f"Error setting nickname: {str(e)}")
                response.status_code = 500
                return {"error": f"Error setting nickname: {str(e)}"}
            return {"message": f"Nickname for user '{member.name}' set to '{nickname_request.nickname}'"}

