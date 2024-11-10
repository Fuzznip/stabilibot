from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os
import random
import requests
import json

import utils.db as db

class Roll(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        # Ensure any databases that we need exist
        db.ensure_teams_table()
        db.ensure_tiles_db()
        self.total_distance = 0
        self.roll_message = ""

    async def move_team_forward(self, interaction, team, total_roll, next_tiles):
        # Get the current tile of the team
        current_tile = db.get_current_tile(team)
        # Get the current tile name
        current_tile_name = db.get_tile_name(current_tile)

        while total_roll > 0:
            # If the team is at a crossroads
            if len(next_tiles) > 1:
                # Get the remaining distance
                remaining_distance = total_roll
                # Get the tile1 and tile2
                tile1, tile2 = next_tiles
                # Create the crossroads view
                view = self.CrossroadsView(team, remaining_distance, tile1, tile2, self.move_team_forward)

                # Send the crossroads message
                message = f"You are at a crossroads on tile {current_tile_name}! Do you want to go to {db.get_tile_name(tile1)} or {db.get_tile_name(tile2)}?\n"
                message += f"You currently have **{db.get_coins(team)} coins** and **{db.get_stars(team)} stars**!\n"
                message += f"You have **{total_roll} tiles** left to move!"
                if self.roll_message != "":
                    message = self.roll_message + message
                    self.roll_message = ""

                await interaction.followup.send(message, ephemeral = False, view = view)
                return
            
            db.set_current_tile(team, next_tiles[0])
            current_tile = db.get_current_tile(team)

            # Move the team forward
            total_roll -= 1
            next_tiles = db.get_next_tiles(next_tiles[0])

            # If the team is at a star
            if db.has_star(current_tile):
                # Create the star view
                view = self.StarView(team, total_roll, self.move_team_forward)
                # Send the star message
                message = f"You are at a star on tile {current_tile_name}! Do you want to buy a star for 100 coins?\n"
                message += f"You currently have {db.get_coins(team)} coins and {db.get_stars(team)} stars!\n"
                message += f"You have {total_roll} tiles left to move!"
                if self.roll_message != "":
                    message = self.roll_message + message
                    self.roll_message = ""

                await interaction.followup.send(message, ephemeral = False, view = view)
                return

            # If the team is at an item shop
            if db.has_item_shop(current_tile):
                # Create the item shop view
                view = self.ItemShopView(team, total_roll, self.move_team_forward)
                # Send the item shop message
                message = f"You are at an item shop on tile {current_tile_name}! Do you want to buy an item?\n"
                message += f"You currently have {db.get_coins(team)} coins and {db.get_stars(team)} stars!\n"
                message += f"You have {total_roll} tiles left to move!"
                if self.roll_message != "":
                    message = self.roll_message + message
                    self.roll_message = ""

                await interaction.followup.send(message, ephemeral = False, view = view)
                return

        # Send the message
        message = self.roll_message
        message += f"\nYou moved forward {self.total_distance} tiles from {db.get_tile_name(db.get_previous_tile(team))} and are now at {db.get_tile_name(db.get_current_tile(team))}!"

        # If we landed on a random event tile
        if db.get_tile_challenge(current_tile) == -1:
            # Find a random challenge
            challenges = db.get_all_random_challenges()
            challenge = random.choice(challenges)
            
            # Set the challenge for the team
            db.set_team_random_challenge(team, challenge)
            db.set_team_is_doing_random_challenge(team)

            message += f"\nYou landed on a random event tile! Your challenge is: {db.get_challenge_name(challenge)}!\n"
        else:
            db.set_team_is_not_doing_random_challenge(team)

        await interaction.followup.send(message, ephemeral = False)
        db.set_team_not_rolling(team)

        
        # Send the final movement from the previous tile to the current tile to the event channel
        message = f"Team {db.get_team_name(team)} moved forward {self.total_distance} tiles from {db.get_tile_name(db.get_previous_tile(team))} and are now at {db.get_tile_name(db.get_current_tile(team))}!"
        thread_id = os.environ.get("THREAD_ID")

        embeds = {
            'embeds': [
                {
                    'author': {
                        'name': db.get_team_name(team),
                    },
                    'description': message,
                }
            ]
        }

        if thread_id == "":
            payload_link = os.environ.get("CHANNEL_WEBHOOK")
        else:
            payload_link = os.environ.get("FORUM_WEBHOOK") + f"?thread_id={thread_id}"
        result = requests.post(payload_link, data = {'payload_json': json.dumps(embeds)})
        try:
            result.raise_for_status()
        except requests.exceptions.HTTPError as err:
            print(err)

    # Crossroads view
    class CrossroadsView(discord.ui.View):
        def __init__(self, team, remaining_distance, tile1, tile2, move_team_forward):
            super().__init__(timeout = None)

            self.team = team
            self.remaining_distance = remaining_distance
            self.tile1 = tile1
            self.tile2 = tile2
            self.move_team_forward = move_team_forward
            print(f"Team {team} is at a crossroads with tiles {tile1} and {tile2}")
            self.add_buttons()

        def add_buttons(self):
            async def option_1(interaction: discord.Interaction):
                print(f"User {interaction.user.name} chose {self.tile1}!")
                # make sure the interaction author is in the team
                if db.get_team(str(interaction.user.id)) != self.team:
                    return

                # Remove the buttons
                self.clear_items()
                await interaction.response.defer()
                await interaction.edit_original_response(view = self)
                # Set the tile name to the tile1 name
                tile_name = db.get_tile_name(self.tile1)
                await interaction.followup.send(f"You chose {tile_name}!", ephemeral = False)
                # move the team forward
                await self.move_team_forward(interaction, self.team, self.remaining_distance, [self.tile1])

            async def option_2(interaction: discord.Interaction):
                print(f"User {interaction.user.name} chose {self.tile2}!")
                # make sure the interaction author is in the team
                if db.get_team(str(interaction.user.id)) != self.team:
                    return

                # Remove the buttons
                self.clear_items()
                await interaction.response.defer()
                await interaction.edit_original_response(view = self)
                # Set the tile name to the tile2 name
                tile_name = db.get_tile_name(self.tile2)
                await interaction.followup.send(f"You chose {tile_name}!", ephemeral = False)
                # move the team forward
                await self.move_team_forward(interaction, self.team, self.remaining_distance, [self.tile2])

            tile1Label = db.get_tile_name(self.tile1)
            button1 = discord.ui.Button(label = tile1Label, style = discord.ButtonStyle.primary)
            button1.callback = option_1

            tile2Label = db.get_tile_name(self.tile2)
            button2 = discord.ui.Button(label = tile2Label, style = discord.ButtonStyle.primary)
            button2.callback = option_2

            self.add_item(button1)
            self.add_item(button2)

    class StarView(discord.ui.View):
        def __init__(self, team, remaining_distance, move_team_forward):
            super().__init__(timeout = None)
            self.team = team
            self.remaining_distance = remaining_distance
            self.move_team_forward = move_team_forward
            self.add_buttons()

            print(f"Team {team} is at a star!")

        def add_buttons(self):
            if db.get_coins(self.team) < 100:
                async def yes(interaction: discord.Interaction):
                    print(f"User {interaction.user.name} does not have enough coins to buy a star!")
                    # make sure the interaction author is in the team
                    if db.get_team(str(interaction.user.id)) != self.team:
                        return

                    # Remove the buttons
                    self.clear_items()
                    await interaction.response.defer()
                    await interaction.edit_original_response(view = self)
                    await interaction.followup.send("You don't have enough coins to buy a star!", ephemeral = False)
                    await self.move_team_forward(interaction, self.team, self.remaining_distance, db.get_next_tiles(db.get_current_tile(self.team)))

                button1 = discord.ui.Button(label = "Not Enough Coins!", style = discord.ButtonStyle.green, disabled = True)
            else:
                async def yes(interaction: discord.Interaction):
                    print(f"User {interaction.user.name} bought a star!")
                    # make sure the interaction author is in the team
                    if db.get_team(str(interaction.user.id)) != self.team:
                        return

                    # Remove the buttons
                    self.clear_items()
                    await interaction.response.defer()
                    await interaction.edit_original_response(view = self)
                    db.set_coins(self.team, db.get_coins(self.team) - 100)
                    db.set_stars(self.team, db.get_stars(self.team) + 1)
                    # Move the star to a random tile on the board
                    allTilePositions = db.get_tile_positions()
                    tile = db.get_current_tile(self.team)
                    while tile == db.get_current_tile(self.team) or db.has_star(tile) or db.has_item_shop(tile) or db.count_teams_on_tile(tile) != 0:
                        tile = random.randint(1, len(allTilePositions) - 1)

                    db.set_star(tile)
                    db.unset_star(db.get_current_tile(self.team))
                    await interaction.followup.send(f"Congratulations! You bought a star for 100 coins! You now have {db.get_coins(self.team)} coins and {db.get_stars(self.team)} stars!\nThe Star has now moved to tile {tile}: {db.get_tile_name(tile)}!", ephemeral = False)
                    # call move_team_forward
                    await self.move_team_forward(interaction, self.team, self.remaining_distance, db.get_next_tiles(db.get_current_tile(self.team)))

                button1 = discord.ui.Button(label = "Yes", style = discord.ButtonStyle.green)

            async def no(interaction: discord.Interaction):
                print(f"User {interaction.user.name} did not buy a star!")
                # make sure the interaction author is in the team
                if db.get_team(str(interaction.user.id)) != self.team:
                    return

                # Remove the buttons
                self.clear_items()
                await interaction.response.defer()
                await interaction.edit_original_response(view = self)
                await interaction.followup.send("You did not buy a star.", ephemeral = False)
                # call move_team_forward
                await self.move_team_forward(interaction, self.team, self.remaining_distance, db.get_next_tiles(db.get_current_tile(self.team)))

            button1.callback = yes

            button2 = discord.ui.Button(label = "No", style = discord.ButtonStyle.red)
            button2.callback = no

            self.add_item(button1)
            self.add_item(button2)


    class ItemShopView(discord.ui.View):
        class ItemsPurchaseView(discord.ui.View):
            def __init__(self, team, total_roll, move_team_forward):
                super().__init__(timeout = None)
                self.team = team
                self.total_roll = total_roll
                self.move_team_forward = move_team_forward

                print(f"Team {team} is at an item shop!")

            def add_purchasable_item(self, price, itemName, id):
                async def purchase_item(interaction: discord.Interaction):
                    print(f"User {interaction.user.name} bought item {id}!")
                    # make sure the interaction author is in the team
                    if db.get_team(str(interaction.user.id)) != self.team:
                        return

                    # Remove the buttons
                    self.clear_items()
                    await interaction.response.defer()
                    await interaction.edit_original_response(view = self)

                    db.add_item_to_team(self.team, id)
                    db.set_coins(self.team, db.get_coins(self.team) - price)

                    # Move the item shop to a random tile on the board
                    allTilePositions = db.get_tile_positions()
                    tile = db.get_current_tile(self.team)
                    while tile == db.get_current_tile(self.team) or db.has_star(tile) or db.has_item_shop(tile) or db.count_teams_on_tile(tile) != 0:
                        tile = random.randint(1, len(allTilePositions) - 1)

                    db.set_item_shop(tile)
                    db.unset_item_shop(db.get_current_tile(self.team))

                    await interaction.followup.send(f"Congratulations! You bought an item for {price} coins! You now have {db.get_coins(self.team)} coins!\nThe Item Shop has now moved to tile {tile}: {db.get_tile_name(tile)}!", ephemeral = False)
                    # call move_team_forward
                    await self.move_team_forward(interaction, self.team, self.total_roll, db.get_next_tiles(db.get_current_tile(self.team)))

                if db.get_coins(self.team) < price:
                    button = discord.ui.Button(label = f"{price}: {itemName}", style = discord.ButtonStyle.green, disabled = True)
                else:
                    button = discord.ui.Button(label = f"{price}: {itemName}", style = discord.ButtonStyle.green)
                button.callback = purchase_item
                self.add_item(button)

            def add_close_shop_button(self):
                async def close_shop(interaction: discord.Interaction):
                    print(f"User {interaction.user.name} did not buy any items!")
                    # make sure the interaction author is in the team
                    if db.get_team(str(interaction.user.id)) != self.team:
                        return

                    # Remove the buttons
                    self.clear_items()
                    await interaction.response.defer()
                    await interaction.edit_original_response(view = self)
                    await interaction.followup.send("You did not buy any items.", ephemeral = False)
                    # call move_team_forward
                    await self.move_team_forward(interaction, self.team, self.total_roll, db.get_next_tiles(db.get_current_tile(self.team)))

                button = discord.ui.Button(label = "Close Shop", style = discord.ButtonStyle.red)
                button.callback = close_shop
                self.add_item(button)

        def __init__(self, team, total_roll, move_team_forward):
            super().__init__(timeout = None)
            self.team = team
            self.total_roll = total_roll
            self.move_team_forward = move_team_forward
            self.add_buttons()

        def get_random_shop_items(self):
            # Get all items
            items = db.get_all_items()

            # Get each item's rarity
            # item rarity is a number from 1 to 4, the lower the number, the more rare the item
            # Rarity is in item[7]
            rarities = [item[7] for item in items]

            # Get the total rarity
            total_rarity = sum(rarities)
            
            randomItems = []
            for x in range(0, 3):
                # Roll a random number between 1 and the total rarity
                roll = random.randint(1, total_rarity)

                # Get the item that corresponds to the roll
                for item in items:
                    roll -= item[7]
                    if roll <= 0:
                        randomItems.append(item)
                        break

            return [(item[6], item[1], item[0], item[2]) for item in randomItems]

        def add_buttons(self):
            async def view_shop(interaction: discord.Interaction):
                print(f"User {interaction.user.name} viewed the shop!")
                # make sure the interaction author is in the team
                if db.get_team(str(interaction.user.id)) != self.team:
                    return

                # Remove the buttons
                self.clear_items()
                await interaction.response.defer()
                await interaction.edit_original_response(view = self)
                itemsView = self.ItemsPurchaseView(self.team, self.total_roll, self.move_team_forward)
                shopItems = "The shop has the following items:\n"
                for price, itemName, id, description in self.get_random_shop_items():
                    shopItems += f"{itemName} for {price} coins: {description}\n"
                    itemsView.add_purchasable_item(price, itemName, id)
                itemsView.add_close_shop_button()
                await interaction.followup.send(shopItems, ephemeral = False, view = itemsView)

            async def pass_shop(interaction: discord.Interaction):
                print(f"User {interaction.user.name} did not view the shop's contents!")
                # make sure the interaction author is in the team
                if db.get_team(str(interaction.user.id)) != self.team:
                    return

                # Remove the buttons
                self.clear_items()
                await interaction.response.defer()
                await interaction.edit_original_response(view = self)
                await interaction.followup.send("You did not view the shop's contents.", ephemeral = False)
                # call move_team_forward
                await self.move_team_forward(interaction, self.team, self.total_roll, db.get_next_tiles(db.get_current_tile(self.team)))

            button1 = discord.ui.Button(label = "View", style = discord.ButtonStyle.green)
            button1.callback = view_shop
            button2 = discord.ui.Button(label = "Pass", style = discord.ButtonStyle.red)
            button2.callback = pass_shop

            self.add_item(button1)
            self.add_item(button2)

    @discord.slash_command(name = "roll", description = "Rolls your dice and moves your team forward on the board!", guild_ids = [int(os.getenv("GUILD_ID"))])
    async def command(self, interaction):
        # Log the command
        print(f"{interaction.author.nick if interaction.author.nick is not None else interaction.user.name}: /roll")
        # Defer the response
        await interaction.response.defer()
        
        # Get the team of the user
        team = db.get_team(str(interaction.author.id))
        if team is None:
            await interaction.followup.send("You are not in a team!", ephemeral = True)
            return

        # If the team is already rolling, return
        if db.is_team_rolling(team):
            await interaction.followup.send("Your team is already rolling! Follow that instead!", ephemeral = True)
            return

        # If the team is not ready to roll, return
        if not db.is_team_ready_to_roll(team):
            await interaction.followup.send("Your team is not ready to roll! Complete your tile first!", ephemeral = True)
            return

        db.set_team_not_ready_to_roll(team)
        db.set_team_rolling(team)
        db.set_previous_tile(team, db.get_current_tile(team))

        # Get the main die sides and the main die modifier
        main_die_sides = db.get_main_die_sides(team)
        main_die_modifier = db.get_main_die_modifier(team)
        
        # Get the extra die sides
        # extra_die_sides is an array of the sides of the extra dice ex. [4, 6, 8]
        extra_die_sides = db.get_extra_die_sides(team)

        # Roll the main die
        main_die_roll = random.randint(1, int(main_die_sides))
        # Roll the extra dice
        extra_die_rolls = [random.randint(1, sides) for sides in extra_die_sides]

        # Calculate the total roll
        total_roll = main_die_roll + main_die_modifier + sum(extra_die_rolls)
        
        roll_message = f"You rolled a 1d{main_die_sides} and got {main_die_roll}!\n"
        if main_die_modifier != 0:
            roll_message += f"You have a modifier of {main_die_modifier}, giving a total of {main_die_roll + main_die_modifier}!\n"
        if extra_die_rolls:
            roll_message += f"You rolled extra dice with sides {extra_die_sides} and got {extra_die_rolls}!\n"
            roll_message += f"Your total roll is {total_roll}!\n"
        self.roll_message = roll_message
        self.total_distance = total_roll
        
        await self.move_team_forward(interaction, team, total_roll, db.get_next_tiles(db.get_current_tile(team)))
