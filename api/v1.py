from dotenv import load_dotenv
load_dotenv()
import discord
from discord.ext import commands
import os
from fastapi import APIRouter, Request, Response
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class V1(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.router = APIRouter()

        @self.router.get("/")
        def root(request: Request, token: str = None):
            logger.info("Received request to root endpoint with token: %s", token)
            if token != os.getenv("API_TOKEN"):
                logger.warning("Invalid token provided to root endpoint")
                return {"error": "Invalid token"}
            logger.info("Valid token provided to root endpoint")
            return {"message": "Welcome to the API!"}
        
        @self.router.post("/roles/{user_id}/add")
        async def add_role(request: Request, response: Response, user_id: int, role: str = None, token: str = None):
            logger.info("Received request to add role '%s' to user ID %d with token: %s", role, user_id, token)
            if token != os.getenv("API_TOKEN"):
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
            
            role = discord.utils.get(guild.roles, name=role)
            if not role:
                logger.error("Role '%s' not found", role)
                response.status_code = 404
                return {"error": "Role not found"}
            
            await member.add_roles(role)
            logger.info("Role '%s' added to user '%s'", role.name, member.name)
            return {"message": f"Role {role.name} added to {member.name}"}
        
        @self.router.post("/roles/{user_id}/remove")
        async def remove_role(request: Request, response: Response, user_id: int, role: str = None, token: str = None):
            logger.info("Received request to remove role '%s' from user ID %d with token: %s", role, user_id, token)
            if token != os.getenv("API_TOKEN"):
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
            
            role = discord.utils.get(guild.roles, name=role)
            if not role:
                logger.error("Role '%s' not found", role)
                response.status_code = 404
                return {"error": "Role not found"}
            
            await member.remove_roles(role)
            logger.info("Role '%s' removed from user '%s'", role.name, member.name)
            return {"message": f"Role {role.name} removed from {member.name}"}
