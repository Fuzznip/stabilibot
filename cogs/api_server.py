import asyncio
from discord.ext import commands
import discord
from fastapi import FastAPI
from uvicorn import Config, Server
from api.v1 import V1

from dotenv import load_dotenv
load_dotenv()

class Api(discord.Cog):
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.server_task = None  # Reference to the server task

    @discord.Cog.listener(name="on_ready")
    async def on_ready(self):
        self.app = FastAPI()
        v1 = V1(self.bot)
        self.app.include_router(v1.router)

        config = Config(
            app=self.app,
            host="0.0.0.0",
            port=8080
        )
        server = Server(config=config)

        # Start the server in the background and store the task reference
        self.server_task = asyncio.create_task(server.serve())

    @discord.Cog.listener(name="on_close")
    async def on_close(self):
        # Cancel the server task if it is running
        if self.server_task:
            self.server_task.cancel()
            try:
                await self.server_task
            except asyncio.CancelledError:
                pass

        # Additional cleanup if necessary
        print("FastAPI server has been shut down.")

    def setup(self):
        self.bot.add_cog(self)

        # Register a shutdown hook to call on_close
        original_close = self.bot.close

        async def close_with_on_close():
            await self.on_close()  # Call the on_close method
            await original_close()  # Proceed with the original close logic

        self.bot.close = close_with_on_close

