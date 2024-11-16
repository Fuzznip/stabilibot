from discord.ext import commands
import discord

from dotenv import load_dotenv
load_dotenv()
import os

import utils.db as db
import random

class UseItem(commands.Cog):
    async def use_extra_die_4(self, interaction: discord.Interaction, team, item): 
        print(f"Using extra die 4 for team {team}")
        # Check if team is ready to roll and is not currently rolling
        if not db.is_team_ready_to_roll(team) or db.is_team_rolling(team):
            await interaction.followup.send("This item may only be used when you are ready to roll and not currently rolling!", ephemeral = False)
            return

        db.give_team_die(team, 4)

        await interaction.followup.send(f"Your next roll will have an extra 4-sided die!", ephemeral = False)
        db.remove_item(team, item)

    async def use_extra_die_6(self, interaction: discord.Interaction, team, item):
        print(f"Using extra die 6 for team {team}")
        # Check if team is ready to roll and is not currently rolling
        if not db.is_team_ready_to_roll(team) or db.is_team_rolling(team):
            await interaction.followup.send("This item may only be used when you are ready to roll and not currently rolling!", ephemeral = False)
            return
        db.give_team_die(team, 6)

        await interaction.followup.send(f"Your next roll will have an extra 6-sided die!", ephemeral = False)
        db.remove_item(team, item)
        
    async def use_extra_die_8(self, interaction: discord.Interaction, team, item):
        print(f"Using extra die 8 for team {team}")
        # Check if team is ready to roll and is not currently rolling
        if not db.is_team_ready_to_roll(team) or db.is_team_rolling(team):
            await interaction.followup.send("This item may only be used when you are ready to roll and not currently rolling!", ephemeral = False)
            return
        db.give_team_die(team, 8)

        await interaction.followup.send(f"Your next roll will have an extra 8-sided die!", ephemeral = False)
        db.remove_item(team, item)

    async def use_add_modifier_1(self, interaction: discord.Interaction, team, item):
        print(f"Using add modifier 1 for team {team}")
        # Check if team is ready to roll and is not currently rolling
        if not db.is_team_ready_to_roll(team) or db.is_team_rolling(team):
            await interaction.followup.send("This item may only be used when you are ready to roll and not currently rolling!", ephemeral = False)
            return
        db.add_team_modifier(team, 1)

        await interaction.followup.send(f"Your next roll will have an extra 1 added to it!", ephemeral = False)
        db.remove_item(team, item)

    async def use_add_modifier_2(self, interaction: discord.Interaction, team, item):
        print(f"Using add modifier 2 for team {team}")
        # Check if team is ready to roll and is not currently rolling
        if not db.is_team_ready_to_roll(team) or db.is_team_rolling(team):
            await interaction.followup.send("This item may only be used when you are ready to roll and not currently rolling!", ephemeral = False)
            return
        db.add_team_modifier(team, 2)

        await interaction.followup.send(f"Your next roll will have an extra 2 added to it!", ephemeral = False)
        db.remove_item(team, item)

    async def use_add_modifier_4(self, interaction: discord.Interaction, team, item):
        print(f"Using add modifier 4 for team {team}")
        # Check if team is ready to roll and is not currently rolling
        if not db.is_team_ready_to_roll(team) or db.is_team_rolling(team):
            await interaction.followup.send("This item may only be used when you are ready to roll and not currently rolling!", ephemeral = False)
            return
        db.add_team_modifier(team, 4)

        await interaction.followup.send(f"Your next roll will have an extra 4 added to it!", ephemeral = False)
        db.remove_item(team, item)

    async def use_add_modifier_8(self, interaction: discord.Interaction, team, item):
        print(f"Using add modifier 8 for team {team}")
        # Check if team is ready to roll and is not currently rolling
        if not db.is_team_ready_to_roll(team) or db.is_team_rolling(team):
            await interaction.followup.send("This item may only be used when you are ready to roll and not currently rolling!", ephemeral = False)
            return
        db.add_team_modifier(team, 8)

        await interaction.followup.send(f"Your next roll will have an extra 8 added to it!", ephemeral = False)
        db.remove_item(team, item)

    async def use_swap_position(self, interaction: discord.Interaction, team, item):
        print(f"Using swap position for team {team}")
        # Ask the team which team they want to swap with
        # Create a view with a select menu of all the teams
        teams = db.get_team_names()
        myTeamName = db.get_team_name(team)

        # Remove the team from the list of teams
        teams.remove(myTeamName)

        selectOptions = [discord.SelectOption(label = teamName, value = teamName) for teamName in teams]

        async def select_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            await interaction.edit_original_response(view = discord.ui.View())

            # Get the team id of the team they selected
            selectedTeam = db.get_team_id(interaction.data["values"][0])
            # Swap the positions of the two teams
            position1 = db.get_team_tile(team)
            position2 = db.get_team_tile(selectedTeam)

            #TODO: Reset Tile progress for both teams first

            db.set_previous_tile(team, position1)
            db.set_previous_tile(selectedTeam, position2)

            db.set_current_tile(team, position2)
            db.set_current_tile(selectedTeam, position1)

            await interaction.followup.send(f"Swapped positions with team {db.get_team_name(selectedTeam)}!\n\nYou are now on tile {db.get_tile_name(position2)}.", ephemeral = False)

            # Inform the other team that they swapped positions
            # Get the text channel for the other team
            otherTeam = db.get_text_channel(selectedTeam)
            channel = (self.bot.get_channel(otherTeam) or await self.bot.fetch_channel(otherTeam))
            await channel.send(f"Team {db.get_team_name(team)} swapped positions with you!\n\nYou are now on tile {db.get_tile_name(position1)}.")

            db.remove_item(team, item)

        selectMenu = discord.ui.Select(placeholder = "Select a team to swap with", options = selectOptions)
        selectMenu.callback = select_callback

        await interaction.followup.send("Select a team to swap positions with:", view = discord.ui.View(selectMenu))

    async def use_teleport(self, interaction: discord.Interaction, team, item):
        print(f"Using teleport for team {team}")
        # Get all of the tiles
        tiles = db.get_tiles()
        selectedTile = db.get_current_tile(team)
        while selectedTile == db.get_current_tile(team):
            selectedTile = tiles[random.randint(0, len(tiles) - 1)]

        #TODO: Reset Tile progress for the team first

        db.set_previous_tile(team, db.get_current_tile(team))
        db.set_current_tile(team, selectedTile[0])

        await interaction.followup.send(f"Teleported to tile {selectedTile[1]}!", ephemeral = False)

        db.remove_item(team, item)

    async def use_double_coin(self, interaction: discord.Interaction, team, item):
        print(f"Using double coin for team {team}")
        # Doubles the coins, capped to 1000
        # db.set_coins(team, min(1000, db.get_team_coins(team) * 2))

        # await interaction.followup.send(f"Doubled your coins! You now have {db.get_team_coins(team)} coins!", ephemeral = False)
        await interaction.followup.send("This item is currently disabled. Also it exploded and disappeared.", ephemeral = False)
        db.remove_item(team, item)

    async def use_steal_star(self, interaction: discord.Interaction, team, item):
        print(f"Using steal star for team {team}")
        # Create a view with a select menu of all the teams
        teams = db.get_team_names()
        myTeamName = db.get_team_name(team)

        # Remove the team from the list of teams
        teams.remove(myTeamName)

        selectOptions = [discord.SelectOption(label = teamName, value = teamName) for teamName in teams]

        async def select_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            await interaction.edit_original_response(view = discord.ui.View())

            # Get the team id of the team they selected
            selectedTeam = db.get_team_id(interaction.data["values"][0])
            if db.get_team_stars(selectedTeam) == 0:
                await interaction.followup.send(f"Team {db.get_team_name(selectedTeam)} has no stars to steal!", ephemeral = False)
                return

            # Steal a star from the selected team
            db.set_stars(team, db.get_team_stars(team) + 1)
            db.set_stars(selectedTeam, db.get_team_stars(selectedTeam) - 1)

            await interaction.followup.send(f"Stole a star from team {db.get_team_name(selectedTeam)}!\n\nYou now have {db.get_team_stars(team)} stars.", ephemeral = False)

            # Inform the other team that they lost a star
            # Get the text channel for the other team
            otherTeam = db.get_text_channel(selectedTeam)
            channel = (self.bot.get_channel(otherTeam) or await self.bot.fetch_channel(otherTeam))
            await channel.send(f"Team {db.get_team_name(team)} stole a star from you!\n\nYou now have {db.get_team_stars(selectedTeam)} stars.")

            db.remove_item(team, item)

        selectMenu = discord.ui.Select(placeholder = "Select a team to steal a star from", options = selectOptions)
        selectMenu.callback = select_callback

        await interaction.followup.send("Select a team to steal a star from:", view = discord.ui.View(selectMenu))

    async def use_steal_coins(self, interaction: discord.Interaction, team, item):
        print(f"Using steal coins for team {team}")
        # Create a view with a select menu of all the teams
        teams = db.get_team_names()
        myTeamName = db.get_team_name(team)

        # Remove the team from the list of teams
        teams.remove(myTeamName)

        selectOptions = [discord.SelectOption(label = teamName, value = teamName) for teamName in teams]

        async def select_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            await interaction.edit_original_response(view = discord.ui.View())

            # Get the team id of the team they selected
            selectedTeam = db.get_team_id(interaction.data["values"][0])
            if db.get_team_coins(selectedTeam) == 0:
                await interaction.followup.send(f"Team {db.get_team_name(selectedTeam)} has no coins to steal!", ephemeral = False)
                return

            # Steal coins from the selected team
            enemyCoins = db.get_team_coins(selectedTeam)
            if enemyCoins >= 50:
                db.set_coins(team, db.get_team_coins(team) + 50)
                db.set_coins(selectedTeam, db.get_team_coins(selectedTeam) - 50)

                await interaction.followup.send(f"Stole 50 coins from team {db.get_team_name(selectedTeam)}!\n\nYou now have {db.get_team_coins(team)} coins.", ephemeral = False)

                # Inform the other team that they lost a star
                # Get the text channel for the other team
                otherTeam = db.get_text_channel(selectedTeam)
                channel = (self.bot.get_channel(otherTeam) or await self.bot.fetch_channel(otherTeam))
                await channel.send(f"Team {db.get_team_name(team)} stole 50 coins from you!\n\nYou now have {db.get_team_coins(selectedTeam)} coins.")
            else:
                db.set_coins(team, db.get_team_coins(team) + enemyCoins)
                db.set_coins(selectedTeam, 0)

                await interaction.followup.send(f"Stole {enemyCoins} coins from team {db.get_team_name(selectedTeam)}!", ephemeral = False)

                # Inform the other team that they lost a star
                # Get the text channel for the other team
                otherTeam = db.get_text_channel(selectedTeam)
                channel = (self.bot.get_channel(otherTeam) or await self.bot.fetch_channel(otherTeam))
                await channel.send(f"Team {db.get_team_name(team)} stole all of your coins!\n\nYou now have 0 coins.")
            
            db.remove_item(team, item)

        selectMenu = discord.ui.Select(placeholder = "Select a team to steal coins from", options = selectOptions)
        selectMenu.callback = select_callback

        await interaction.followup.send("Select a team to steal coins from:", view = discord.ui.View(selectMenu))

    async def use_deaths_coffer(self, interaction: discord.Interaction, team, item):
        print(f"Using deaths coffer for team {team}")

        # Check if team is not ready to roll or is currently rolling
        if db.is_team_ready_to_roll(team) or db.is_team_rolling(team):
            await interaction.followup.send("This item may only be used when you are progressing through a tile!", ephemeral = False)
            return

        # Ask the user if they wish to spend 100 coins
        # Create a view with two buttons, one for yes and one for no
        async def yes(interaction: discord.Interaction):
            await interaction.response.defer()
            if db.get_team_coins(team) >= 100:
                db.set_coins(team, db.get_team_coins(team) - 100 + 10)
                db.set_team_ready_to_roll(team)
                db.set_team_not_rolling(team)

                db.set_main_die_side(team, 4)
                db.set_main_die_modifier(team, 0)
                db.set_extra_die_sides(team, [])

                await interaction.followup.send("You spent 100 coins, gained 10 from completing the tile, and can now roll again!", ephemeral = False)
                db.remove_item(team, item)
            else:
                db.set_coins(team, 10)
                db.set_team_ready_to_roll(team)
                db.set_team_not_rolling(team)

                db.set_main_die_side(team, 4)
                db.set_main_die_modifier(team, 0)
                db.set_extra_die_sides(team, [])

                await interaction.followup.send("You spent all of your coins to complete the tile, gained 10 from completing the tile, and can now roll again!", ephemeral = False)
                db.remove_item(team, item)

        async def no(interaction: discord.Interaction):
            await interaction.response.defer()
            await interaction.followup.send("You decided to not use the item.", ephemeral = False)

        yesButton = discord.ui.Button(label = "Yes", style = discord.ButtonStyle.success)
        yesButton.callback = yes

        noButton = discord.ui.Button(label = "No", style = discord.ButtonStyle.danger)
        noButton.callback = no

        view = discord.ui.View()
        view.add_item(yesButton)
        view.add_item(noButton)

        await interaction.followup.send("Are you sure you want to spend up to 100 coins to complete the current tile?", view = view)

    async def use_reroll_global_challenge(self, interaction: discord.Interaction, team, item):
        print(f"Using reroll global challenge for team {team}")

        # Get all the global challenges from the database
        challenges = [98, 99, 100, 20, 60, 66, 72]
        print(challenges)

        # Get the current global challenge
        currentChallenge = db.get_global_challenge()

        while currentChallenge == db.get_global_challenge():
            currentChallenge = challenges[random.randint(0, len(challenges) - 1)]

        db.set_global_challenge(currentChallenge)
        await interaction.followup.send(f"Rerolled the global challenge! Your new challenge is: {db.get_challenge_name(currentChallenge)}", ephemeral = False)
        
        # Message all of the teams except the team that used the item
        for otherTeam in db.get_team_names():
            if otherTeam != db.get_team_name(team):
                # Get the text channel for the other team
                otherTeamId = db.get_team_id(otherTeam)
                otherTeamChannel = db.get_text_channel(otherTeamId)
                channel = (self.bot.get_channel(otherTeamChannel) or await self.bot.fetch_channel(otherTeamChannel))
                await channel.send(f"Team {db.get_team_name(team)} rerolled the global challenge! Your new challenge is: {db.get_challenge_name(currentChallenge)}.")

        db.remove_item(team, item)

    class StarView(discord.ui.View):
        def __init__(self, team, remaining_distance):
            super().__init__(timeout = None)
            self.team = team
            self.remaining_distance = remaining_distance
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

            button1.callback = yes

            button2 = discord.ui.Button(label = "No", style = discord.ButtonStyle.red)
            button2.callback = no

            self.add_item(button1)
            self.add_item(button2)

    async def use_golden_teleport_tablet(self, interaction: discord.Interaction, team, item):
        print(f"Using golden teleport tablet for team {team}")
        # Get all of the tiles
        tiles = db.get_star_tiles()
        selectedTile = db.get_current_tile(team)
        while selectedTile == db.get_current_tile(team):
            selectedTile = tiles[random.randint(0, len(tiles) - 1)]

        # Move the team to the selected tile
        db.set_previous_tile(team, db.get_current_tile(team))
        db.set_current_tile(team, selectedTile)

        view = self.StarView(team, 0)
        await interaction.followup.send(f"Teleported to tile {selectedTile}! Would you like to purchase a star for 100 coins?", view = view)

        db.remove_item(team, item)

    def __init__(self, bot: discord.Bot):
        self.bot = bot
        # Ensure any databases that we need exist
        db.ensure_items_db()
        db.ensure_global_challenges_list_db()

        self.styleDictionary = {
            "primary": discord.ButtonStyle.primary,
            "secondary": discord.ButtonStyle.secondary,
            "success": discord.ButtonStyle.success,
            "danger": discord.ButtonStyle.danger,
            "link": discord.ButtonStyle.link,
            "blurple": discord.ButtonStyle.blurple,
            "grey": discord.ButtonStyle.grey,
            "green": discord.ButtonStyle.green,
            "red": discord.ButtonStyle.red,
            "url": discord.ButtonStyle.url
        }

        self.itemDictionary = {
            "1": self.use_extra_die_4,
            "2": self.use_extra_die_6,
            "3": self.use_extra_die_8,
            "4": self.use_add_modifier_1,
            "5": self.use_add_modifier_2,
            "6": self.use_add_modifier_4,
            "7": self.use_add_modifier_8,
            "8": self.use_swap_position,
            "9": self.use_teleport,
            "10": self.use_double_coin,
            "11": self.use_steal_star,
            "12": self.use_deaths_coffer,
            "13": self.use_steal_coins,
            "14": self.use_reroll_global_challenge,
            "15": self.use_golden_teleport_tablet
        }

    class ItemBarView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout = None)
            self.value = None

        class ConfirmationView(discord.ui.View):
            def __init__(self, team, item, itemUseFunc):
                super().__init__(timeout = None)
                self.team = team
                self.item = item
                self.itemUseFunc = itemUseFunc
                self.add_buttons()

            def add_buttons(self):
                async def confirm(interaction: discord.Interaction):
                    self.clear_items()
                    await interaction.response.defer()
                    await interaction.edit_original_response(view = self)

                    await self.itemUseFunc(interaction, self.team, self.item)

                async def cancel(interaction: discord.Interaction):
                    self.clear_items()
                    await interaction.response.defer()
                    await interaction.edit_original_response(view = self)

                    await interaction.followup.send("You decided to not use the item.", ephemeral = False)

                confirmButton = discord.ui.Button(label = "Yes", style = discord.ButtonStyle.success)
                confirmButton.callback = confirm
                self.add_item(confirmButton)

                cancelButton = discord.ui.Button(label = "No", style = discord.ButtonStyle.danger)
                cancelButton.callback = cancel
                self.add_item(cancelButton)

        def add_button(self, team, item, itemUseFunc, style):
            async def button_callback(interaction: discord.Interaction):
                self.clear_items()
                await interaction.response.defer()
                await interaction.edit_original_response(view = self)

                confirmationView = self.ConfirmationView(team, item[0], itemUseFunc)
                await interaction.followup.send(f"Are you sure you want to use this item?\n\n{item[2]}", view = confirmationView)

            button = discord.ui.Button(label = item[1], style = style)
            button.callback = button_callback

            self.add_item(button)

        def add_cancel(self):
            async def cancel(interaction: discord.Interaction):
                self.clear_items()
                await interaction.response.defer()
                await interaction.edit_original_response(view = self)

                await interaction.followup.send("Item Menu Closed.", ephemeral = False)

            cancelButton = discord.ui.Button(label = "Cancel", style = discord.ButtonStyle.danger)
            cancelButton.callback = cancel
            # Add the button on a new action row
            cancelButton.row = 4 # 5th row is the last row
            
            self.add_item(cancelButton)

    @discord.slash_command(name = "use_item", description = "Opens up your team's item menu to use an item.", guild_ids = [int(os.getenv("GUILD_ID"))])
    async def use_item(self, interaction):
        # Log the command
        print(f"{interaction.author.nick if interaction.author.nick is not None else interaction.user.name}: /use_item")
        # Defer the response
        await interaction.response.defer()

        # Get the user's team
        team = db.get_team(str(interaction.author.id))
        if team is None:
            await interaction.followup.send("You are not on a team!", ephemeral = True)
            return

        # Get the team's items
        items = db.get_items(team)
        if len(items) > 0:
            # For each item, add a button to use it
            itemBarView = self.ItemBarView()
            for item in items:
                itemDetails = db.get_item(item)
                itemBarView.add_button(team, itemDetails, self.itemDictionary[str(itemDetails[0])], self.styleDictionary[itemDetails[8]])

            itemBarView.add_cancel()

            await interaction.followup.send("Select an item to use:", view = itemBarView)

        else:
            await interaction.followup.send("Your team has no items!")
            return

