from discord.ext import commands
from utils.ultimate_lines import ultimate_lines  # Import the ultimate_lines dictionary
from utils.character_images import character_images  # Import the character_images dictionary
import random  # Import random for selecting a random line
import re  # Import regex for cleaning words
import discord  # Import discord for creating embeds

class MessageListener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore messages from the bot itself
        if message.author == self.bot.user:
            return

        # List of common words to ignore
        common_words = {"the", "i", "o", "a", "an", "and", "or", "is", "it", "to", "of", "in", "on", "for", "with", "at", "by", "you", "get", "your"}

        # Clean the message and ultimate lines by keeping only alphanumeric characters
        def clean_text(text):
            return re.sub(r"[^a-zA-Z0-9\s]", "", text.lower())

        # Remove common words from the message
        message_words = set(word for word in clean_text(message.content).split() if word not in common_words)
        matching_lines = [
            line for line in ultimate_lines 
            if any(word in message_words for word in clean_text(line).split())
        ]
        
        # If there are matches, pick one at random and send it with an embed
        if matching_lines:
            selected_line = random.choice(matching_lines)
            character = ultimate_lines[selected_line]
            embed = discord.Embed(title=selected_line,color=discord.Color.blue())
            if character in character_images:
                embed.set_thumbnail(url=character_images[character])
            await message.channel.send(embed=embed)
