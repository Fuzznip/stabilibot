from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import utils.db as db

from PIL import Image

class Board(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        # Ensure any databases that we need exist
        self.iconSize = 160
        self.iconPadding = 140
        self.tileModifierPadding = 30

    def get_offset(self, numOfTeamsOnTile, i, x, y):
        # If there is only one team on the tile, return the original position
        if numOfTeamsOnTile == 1:
            return (int(x - self.iconSize / 2), int(y - self.iconSize / 2))
        # If there are two teams on the tile, return the original position with a horizontal padding of 30
        if numOfTeamsOnTile == 2:
            if i == 0:
                return (int(x - self.iconSize / 2 - self.iconPadding / 2), int(y - self.iconSize / 2))
            if i == 1:
                return (int(x - self.iconSize / 2 + self.iconPadding / 2), int(y - self.iconSize / 2))
        # If there are three teams on the tile, give a circular pattern with a radius of 20
        if numOfTeamsOnTile == 3:
            if i == 0:
                return (int(x - self.iconSize / 2), int(y - self.iconSize / 2 - self.iconPadding / 2))
            if i == 1:
                return (int(x - self.iconSize / 2 - self.iconPadding / 2), int(y - self.iconSize / 2 + self.iconPadding / 2))
            if i == 2:
                return (int(x - self.iconSize / 2 + self.iconPadding / 2), int(y - self.iconSize / 2 + self.iconPadding / 2))

    def paste_with_drop_shadow(self, base, image, position, shadow_offset=(4, 4), shadow_color=(0, 0, 0, 128)):
        # Create a new image with the shadow
        shadow = Image.new("RGBA", image.size)
        shadow.paste(shadow_color, (0, 0, shadow.size[0], shadow.size[1]), image)
        # Paste the shadow onto the base
        base.paste(shadow, (position[0] + shadow_offset[0], position[1] + shadow_offset[1]), shadow)
        # Paste the image onto the base
        base.paste(image, position, image)

    @discord.slash_command(name = "board", description = "Views the current board", guild_ids = [int(os.getenv("GUILD_ID"))])
    async def board(self, interaction):
        # Log the command
        print(f"{interaction.author.nick if interaction.author.nick is not None else interaction.user.name}: /board")
        # Defer the response
        await interaction.response.defer()
        path = os.path.join(os.path.dirname(__file__), "../../images")

        board_image = "board.png"

        teams = db.get_teams()
        # Load the board image
        board_path = os.path.join(path, board_image)
        board = Image.open(board_path).convert("RGBA")
        # Create a dictionary where the key is a tile and the value is the array of teams on that tile
        tiles = {}
        for team in teams:
            tile = team[4]
            if tile in tiles:
                # Insert sorted by team number
                i = 0
                while i < len(tiles[tile]) and tiles[tile][i][0] < team[0]:
                    i += 1
                tiles[tile].insert(i, team)
            else:
                tiles[tile] = [team]
        
        for tile, teams in tiles.items():
            numOfTeamsOnTile = len(teams)
            for i, team in enumerate(teams):
                # Get the team's image name
                team_image = team[2]
                position = db.get_tile_position(tile)
                x = int(position[1:position.index(",")])
                y = int(position[position.index(",") + 1:-1])
                
                finalPosition = self.get_offset(numOfTeamsOnTile, i, x, y)
                
                # Add the team's image to the board at the tile's position
                # load the team image
                final_image_path = os.path.join(path, team_image)
                icon = Image.open(final_image_path).convert("RGBA")
                # resize the image to 48x48
                icon = icon.resize((self.iconSize, self.iconSize))
                # paste the image onto the board
                self.paste_with_drop_shadow(board, icon, finalPosition)

        star_image = "star.png"
        # Get the star positions
        stars = db.get_star_tiles()
        # Load the star image
        star_icon = Image.open(os.path.join(path, star_image)).convert("RGBA")
        star_icon = star_icon.resize((self.iconSize, self.iconSize))
        for star in stars:
            # Get the star's position
            star_position = db.get_tile_position(star)
            x = int(star_position[1:star_position.index(",")])
            y = int(star_position[star_position.index(",") + 1:-1])

            # Add the star to the board
            self.paste_with_drop_shadow(board, star_icon, (int(x - self.iconSize / 2), int(y - self.iconSize / 2 - self.iconPadding - self.tileModifierPadding)))

        item_shop_image = "item_shop.png"
        # Get the item shop positions
        item_shops = db.get_item_shop_tiles()
        # Load the item shop image
        item_shop_icon = Image.open(os.path.join(path, item_shop_image)).convert("RGBA")
        item_shop_icon = item_shop_icon.resize((self.iconSize, self.iconSize))
        for item_shop in item_shops:
            # Get the item shop's position
            item_shop_position = db.get_tile_position(item_shop)
            x = int(item_shop_position[1:item_shop_position.index(",")])
            y = int(item_shop_position[item_shop_position.index(",") + 1:-1])

            # Add the item shop to the board
            self.paste_with_drop_shadow(board, item_shop_icon, (int(x - self.iconSize / 2), int(y - self.iconSize / 2 - self.iconPadding - self.tileModifierPadding)))

        # Send the board image
        # Save the board image
        board.save(os.path.join(path, "board_send.png"))
        await interaction.followup.send(file=discord.File(os.path.join(path, "board_send.png")))
