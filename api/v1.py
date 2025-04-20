from dotenv import load_dotenv
load_dotenv()
import discord
from discord.ext import commands
import os
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DiscordRoleAction(BaseModel):
    roles: list[str]
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
        
        @self.router.post("/application")
        async def application(request: Request, response: Response, token: str = None):
            if token != os.getenv("API_TOKEN"):
                logger.warning("Invalid token provided to application endpoint")
                response.status_code = 401
                return {"error": "Invalid token"}
            logger.info("Valid token provided to application endpoint")
            return {"message": "Application endpoint reached"}
        
        @self.router.post("/roles/{user_id}/add")
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
        
        @self.router.post("/roles/{user_id}/remove")
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
