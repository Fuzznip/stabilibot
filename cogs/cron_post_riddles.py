import discord
from discord.ext import commands, tasks
import aiohttp
import os
from datetime import datetime, time, timezone, timedelta

class PostRiddles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.post_daily_riddle.start()

    @tasks.loop(time=time(hour=20, minute=5))  # 12:05 PM PST = 20:05 UTC
    async def post_daily_riddle(self):
        # Define PST timezone (UTC-8)
        pst = timezone(timedelta(hours=-8))
        now = datetime.now(pst)
        
        # Only run between 2/20/2026 and 2/28/2026
        start_date = datetime(2026, 2, 20, tzinfo=pst).date()
        end_date = datetime(2026, 2, 28, tzinfo=pst).date()
        
        if not (start_date <= now.date() <= end_date):
            print(f"Skipping riddle post - outside date range. Current date: {now.date()}")
            return
        
        # Fetch riddles from backend
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(os.getenv("BACKEND_URL") + "/riddles") as response:
                    if response.status != 200:
                        print(f"Error fetching riddles: {response.status} - {await response.text()}")
                        return
                    
                    riddles_data = await response.json()
                    riddles = riddles_data.get("riddles", [])
                    
                    if not riddles:
                        print("No riddles found")
                        return
                    
                    # Get the latest riddle based on release_timestamp
                    latest_riddle = max(riddles, key=lambda r: r.get("release_timestamp", ""))
                    
                    # Get the channel to post to
                    channel = self.bot.get_channel(1472741684801441802)
                    if not channel:
                        print("Channel not found")
                        return
                    
                    # Format and post the riddle as an embed
                    riddle_text = latest_riddle.get("riddle", "No riddle text available")
                    riddle_name = latest_riddle.get("name", "Unknown")
                    riddle_id = latest_riddle.get("id", "Unknown")
                    riddle_number = len(riddles)
                    
                    embed = discord.Embed(
                        title=riddle_text,
                        color=discord.Color.gold()
                    )
                    embed.set_author(name=riddle_name)
                    embed.timestamp = datetime.now(pst)
                    
                    await channel.send(embed=embed)
                    print(f"Posted riddle {riddle_id} to channel {channel.id}")
                    
        except aiohttp.ClientConnectorError as e:
            print(f"Error connecting to backend: {str(e)}")
        except Exception as e:
            print(f"Error posting daily riddle: {str(e)}")

    @post_daily_riddle.before_loop
    async def before_post_daily_riddle(self):
        await self.bot.wait_until_ready()

def setup(bot):
    bot.add_cog(PostRiddles(bot))
