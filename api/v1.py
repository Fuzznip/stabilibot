from dotenv import load_dotenv
load_dotenv()
import discord
from discord.ext import commands
import os
from fastapi import APIRouter, Request, Response

class V1(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.router = APIRouter()

        @self.router.get("/")
        def root(request: Request, token: str = None):
            if token != os.getenv("API_TOKEN"):
                return {"error": "Invalid token"}
            return {"message": "Welcome to the API!"}
        
        @self.router.post("/roles/{user_id}/add")
        async def add_role(request: Request, response: Response, user_id: int, role: str = None, token: str = None):
            if token != os.getenv("API_TOKEN"):
                response.status_code = 401
                return {"error": "Invalid token"}
            guild = self.bot.get_guild(int(os.getenv("GUILD_ID")))
            if not guild:
                response.status_code = 404
                return {"error": "Guild not found"}
            
            member = guild.get_member(user_id)
            if not member:
                response.status_code = 404
                return {"error": "Member not found"}
            
            role = discord.utils.get(guild.roles, name=role)
            if not role:
                response.status_code = 404
                return {"error": "Role not found"}
            
            await member.add_roles(role)
            return {"message": f"Role {role.name} added to {member.name}"}
        
        @self.router.post("/roles/{user_id}/remove")
        async def remove_role(request: Request, response: Response, user_id: int, role: str = None, token: str = None):
            if token != os.getenv("API_TOKEN"):
                response.status_code = 401
                return {"error": "Invalid token"}
            guild = self.bot.get_guild(int(os.getenv("GUILD_ID")))
            if not guild:
                response.status_code = 404
                return {"error": "Guild not found"}
            
            member = guild.get_member(user_id)
            if not member:
                response.status_code = 404
                return {"error": "Member not found"}
            
            role = discord.utils.get(guild.roles, name=role)
            if not role:
                response.status_code = 404
                return {"error": "Role not found"}
            
            await member.remove_roles(role)
            return {"message": f"Role {role.name} removed from {member.name}"}
    