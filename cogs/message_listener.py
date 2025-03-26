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

        # Define colors for specific characters
        character_colors = {
            "Adam Warlock": discord.Color.gold(),
            "Black Panther": discord.Color.dark_gray(),
            "Black Widow": discord.Color.red(),
            "Captain America": discord.Color.blue(),
            "Doctor Strange": discord.Color.purple(),
            "Groot": discord.Color.green(),
            "Hawkeye": discord.Color.orange(),
            "Hela": discord.Color.dark_red(),
            "Hero Hulk": discord.Color.dark_green(),
            "Iron Man": discord.Color.dark_orange(),
            "Loki": discord.Color.dark_purple(),
            "Psylocke": discord.Color.purple(),
            "Storm": discord.Color.blue(),
            "Scarlet Witch": discord.Color.magenta(),
            "Spider-Man": discord.Color.red(),
            "Thor": discord.Color.light_gray(),
            "The Punisher": discord.Color.dark_gray(),
            "The Thing": discord.Color.orange(),
            "Wolverine": discord.Color.gold(),
            # ...add more characters and colors as needed...
        }

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
            color = character_colors.get(character, discord.Color.default())  # Default color if character not found
            embed = discord.Embed(title=selected_line, color=color)
            if character in character_images:
                embed.set_thumbnail(url=character_images[character])
            await message.channel.send(embed=embed)
