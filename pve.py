import discord
import asyncio
import random
import time
from discord.ext import commands
from pymongo import MongoClient
#from discord import Embed
from .GetPlayerLevel import get_player_level
from .levelthresh import LEVEL_THRESHOLDS
from .npcs import npcs
from .abilityRequirements import add_reactions
import copy 
from .abilityRequirements import handle_player_action
from .statusEffects import (apply_player_status_effects, apply_npc_status_effects, activate_summon_drone, 
                            process_deploy_needles, apply_harden_scales, apply_harpoonify_effect, 
                            apply_barrier_shield, apply_poison_dart, apply_slime_attack, apply_lunge, apply_energy_ball, 
                            #apply_healing_aura, 
                             get_player_stats
                            
                            )
from .getPlayerStats import DatabaseManager 
from .quests import QuestTracker        


class BattleCog(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.active_battles = {}
        self.major_pain_cooldowns = {}  # Dictionary to track the cooldowns for "Major Pain"
        self.summon_drone_status = {}
        self.summon_drone_cooldowns = {}
        self.barrier_shield_cooldowns = {}
        self.call_allies_cooldowns = {}
        self.poison_dart_cooldowns = {}
        self.slime_attack_cooldowns = {}
        self.harden_scales_cooldowns = {}
        self.lunge_cooldowns = {}
        self.harpoonify_cooldowns = {}
        self.energy_ball_cooldowns = {}
      #  self.healing_aura_cooldowns = {}
        self.stoneify_cooldowns = {}
        self.twinify_cooldowns = {}
        self.cooldown_time = 12 * 60 * 60  # Cooldown time in seconds (12 hours)
        
        # MongoDB setup
        self.client = MongoClient(
       
        )
        self.db = self.client["Player"]
        self.collection = self.db["Player.Stats"]
        self.npc = self.db["Player.NPC"]
    
    def has_ability(self, player_stats, ability_name):
        """Check if a player has unlocked a specific ability based on their race and level."""
        # Iterate over the player's abilities
        for ability in player_stats["abilities"]:
            if ability["name"] == ability_name:
                if player_stats["level"] >= ability["level_required"]:
                    return True
        return False
    
    async def unlock_abilities(self, player_level: int, race_name: str = "Human"):
        """Unlock abilities for the given player level and race."""
        # Use RaceAbilityManager to get unlocked abilities
        unlocked_abilities = self.race_ability_manager.unlock_abilities(race_name, player_level)
        
        # Format the abilities into a response message
        if unlocked_abilities:
            abilities_list = "\n".join([f"{ability['name']}: {ability['description']}" for ability in unlocked_abilities])
            return f"Unlocked Abilities for {race_name} at level {player_level}:\n{abilities_list}"
        else:
            return f"No abilities unlocked for {race_name} at level {player_level}."
            
    def update_player_health(self, player_id, health):
        """Update the player's health in the database."""
        player_stats = self.collection.find_one({"user_id": player_id})
        if not player_stats:
            return

        max_health = player_stats.get("max_health", 100)
        updated_health = min(health, max_health)

        self.collection.update_one(
            {"user_id": player_id},
            {"$set": {"health": updated_health}}
        )
        
    def get_xp_threshold_for_level(level):
        print(f"Getting XP threshold for level: {level}")

        # Special case for level 1
        if level == 1:
            print("Level 1 found, returning 0 XP threshold.")
            return 0  # Level 1 has 0 XP threshold

        # Search for the level in LEVEL_THRESHOLDS
        for threshold in LEVEL_THRESHOLDS:
            if threshold["level"] == level:
                print(f"XP threshold for level {level}: {threshold['xp_threshold']}")
                return threshold["xp_threshold"]  # Return the xp_threshold for the matching level
        
        # If no threshold found for the given level
            print(f"No threshold found for level {level}")
            return None
        # Check for level 1
    
    def add_experience(self, player_id, xp_gain):
        """Add experience and ensure NPC kills are recorded"""
        player_stats = self.collection.find_one({"user_id": player_id})

        if player_stats:
            current_level = player_stats.get("level", 1)  # Default to 1 if missing
            current_xp = player_stats.get("experience", 0)

            new_xp = current_xp + xp_gain
            new_level = current_level
            level_up_occurred = False

            print(f"DEBUG: XP Gained: {xp_gain}, Old XP: {current_xp}, New XP: {new_xp}")

            # Only check thresholds at or above current level
            for threshold in LEVEL_THRESHOLDS:
                if threshold["level"] > current_level and new_xp >= threshold["xp_threshold"]:
                    new_level = threshold["level"]
                    level_up_occurred = True
                    print(f"DEBUG: Leveled up to {new_level} (Threshold: {threshold['xp_threshold']})")
                else:
                    break  

            level_up_message = ""
            if level_up_occurred:
                level_diff = new_level - current_level
                player_stats["attack"] += 2 * level_diff
                player_stats["defense"] += 2 * level_diff
                player_stats["max_health"] += 10 * level_diff
                player_stats["health"] = player_stats["max_health"]

                level_up_message = f"🎉 Congratulations! You leveled up to **Level {new_level}**! Your stats have improved: Attack {player_stats['attack']}, Defense {player_stats['defense']}, Max Health {player_stats['max_health']}."

            # Update experience and level in the database
            self.collection.update_one(
                {"user_id": player_id},
                {"$set": {
                    "experience": new_xp,
                    "level": new_level,
                    "attack": player_stats["attack"],
                    "defense": player_stats["defense"],
                    "max_health": player_stats["max_health"],
                    "health": player_stats["health"]
                }}
            )

            # **Ensure the player exists in the 'player.npc' collection**
            self.npc.update_one({"user_id": player_id}, {"$inc": {"npc_kills": 1}}, upsert=True)

            # ✅ Call the quest tracking function from QuestTracker
            quest_tracker = self.bot.get_cog("QuestTracker")  # Get the QuestTracker cog
            if quest_tracker:
                loop = self.bot.loop
                loop.create_task(quest_tracker.check_hired_gun_quest(player_id))  # Run the async function

            # Fetch the updated stats before sending the response
            updated_player_stats = self.collection.find_one({"user_id": player_id})

            print(f"DEBUG: Final Level: {updated_player_stats['level']}, Updated in DB")

            return {
                "stats": updated_player_stats,  # Return the latest player stats
                "level_up_occurred": level_up_occurred,  
                "level_up_message": level_up_message  
            }

        return {"error": "Player not found in the database"}
    @commands.command()
    async def fight(self, ctx, npc_override=None):
        await self.start_battle(ctx.channel, ctx.author, npc_override=npc_override)
    # Corrected call: only pass player_id, not ctx
        player_id = ctx.author.id
        db_manager = self.bot.get_cog("DatabaseManager")
        
        # Call get_player_stats correctly
        player_stats = await db_manager.get_player_stats(player_id)  # Corrected call
        
        if player_stats:
            # Use the fetched player stats here
            print(f"Player Stats: {player_stats}")
        else:
            print("No player stats found.")
        
        # Check if player stats are available
        if not player_stats:
            await ctx.send("Player stats not found!")
            return
        
        # Prevent multiple active battles
        if ctx.author.id in self.active_battles:
            await ctx.send("You are already in a battle!")
            return
        
        # Simulate race abilities or get them from another cog
        raceability_cog = self.bot.get_cog("RACEABILITY")
        if not raceability_cog:
            await ctx.send("The RACEABILITY cog is not loaded properly!")
            return
        
        # Unlock race abilities for the player
        player_stats = raceability_cog.unlock_abilities(player_stats)
    
        if npc_override:  
            npc = npc_override  # Use the provided NPC instead of a random one
        else:
            npc = random.choice
        npc = copy.deepcopy(random.choice(npcs))
        # Set up active battle
        self.active_battles[ctx.author.id] = {"player": player_stats, "npc": npc, "turn": "player"}

        # Debugging line to check if the embed was sent
        print(f"NPC Embed Sent: {npc['name']}")  # This should print the NPC name to the console
            # Start the player's turn
        await self.send_npc_embed(ctx, npc)

    async def start_battle(self, channel, user, npc_override=None, on_victory=None):
        print("testing start battle code debug")
        player_id = user.id
        db_manager = self.bot.get_cog("DatabaseManager")

        # Check if player is already in a battle
        if user.id in self.active_battles:
            await channel.send("You are already in a battle!")
            return

        player_stats = await db_manager.get_player_stats(player_id)
        if not player_stats:
            await channel.send("Player stats not found!")
            return

        raceability_cog = self.bot.get_cog("RACEABILITY")
        if not raceability_cog:
            await channel.send("The RACEABILITY cog is not loaded properly!")
            return

        player_stats = raceability_cog.unlock_abilities(player_stats)

        npc = npc_override if npc_override else copy.deepcopy(random.choice(npcs))

        # ✅ Add the on_victory callback here
        self.active_battles[user.id] = {
            "player": player_stats,
            "npc": npc,
            "turn": "player",
            "on_victory": on_victory  # ✅ <--- THIS is the important new line
        }

        battle = self.active_battles[user.id]  # ✅ now it's safe

        print(f"NPC Embed Sent: {npc['name']}")

        # Only call send_npc_embed once
        await self.send_npc_embed(channel, npc, user, battle)
    async def send_npc_embed(self, channel, npc, author=None, battle=None):
        embed = discord.Embed(
            title=f"A wild {npc['name']} appears!",
            description=npc['description'],
            color=discord.Color.red()
        )
        
        embed.set_thumbnail(url=npc['image'])  # Optional

        message = await channel.send(embed=embed)

        if author:
            print(f"Embed sent for player ID: {author.id}")

        # Store the embed message inside the battle dict so player_turn can use it
        if battle is not None:
            battle["embed_message"] = message
            await self.player_turn(channel, author, battle)
           
    async def player_turn(self, channel, author, battle):
        """Handle the player's turn in battle."""
        
        player = await get_player_stats(author.id)
        battle["player"] = player  
        npc = battle["npc"]

        if not player or not npc:
            await channel.send("Error: Missing player or NPC data.")
            return

        embed_message = battle.get("embed_message")

        # 🎨 Get existing embed without clearing fields
        embed = embed_message.embeds[0]  

        # ✅ Keep attack logs, only update health values in the description
        embed.title = "⚔️ Your Turn!"
        embed.description = (
            f"🧑 {author.mention} ❤️ {player['health']}  |  👹 {npc['name']} ❤️ {npc['health']}\n\n"
            "React with ⚔️ for a **normal attack** or 💥 for a **power attack**!"
        )

        await embed_message.edit(embed=embed)  

        # Refresh reactions
        await embed_message.clear_reactions()
        await embed_message.add_reaction("⚔️")
        await embed_message.add_reaction("💥")

        # Wait for player's reaction
        await self.wait_for_reaction(channel, embed_message, author.id)
        
    async def wait_for_reaction(self, channel, message, player_id):
        """Wait for the player to react."""
        player_stats = self.collection.find_one({"user_id": player_id})
        player_level = player_stats.get("level", 1)
        player_race = player_stats.get("race")

        user = message.guild.get_member(player_id) or await self.bot.fetch_user(player_id)
        print(f"wait_for_reaction called by {user.name}")
        battle = self.active_battles.get(player_id)
        if not battle:
            await channel.send("Error: No active battle found.")
            return
        embed_message = self.active_battles.get(player_id, {}).get("embed_message")
        if not embed_message:
            print(f"No embed message found for player {player_id}.")
            await channel.send(f"No embed message found for player {player_id}.")
            return

        print(f"Found embed message for player {player_id}: {embed_message.id}")

        valid_emojis = ["⚔️", "💥", "💣", "🛡️", "🚁", "💉", "🦔", "🤮", "💨", "🐲", "🐉",
                        "🌀", "🌟", "😵", "🗿", "👨🏻‍🤝‍👨🏼", "🔱", "☄️"]
        #battle = self.active_battles.get(user.id)
        #if battle:
            #await self.process_attack(channel, user, battle, "normal")
        def check(reaction, reacting_user):
            return (
                reacting_user.id == player_id and
                reaction.message.id == message.id and
                str(reaction.emoji) in valid_emojis
            )

        try:
            # Wait for a reaction
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=120.0, check=check)
            print(f"Detected reaction: {reaction.emoji}")  # Debug message

            # Check which emoji was reacted to and handle accordingly
            if str(reaction.emoji) == "⚔️":
                await self.process_attack(channel, user, battle, "normal")
            elif str(reaction.emoji) == "💥":
                await self.process_attack(channel, user, battle, "power")
            elif str(reaction.emoji) == "💣":
                if player_level >= 2 and player_race == "terrans":  # Check if player is level 2 or higher for Major Pain
                    await self.process_major_pain(channel, user)
                else:
                    await channel.send("You need to be at least Level 2 to use Major Pain!")
                    await self.send_npc_embed(channel, battle["npc"])  # Re-send the embed after showing the error
            elif str(reaction.emoji) == "🛡️":
                if player_level >= 5 and player_race == "terrans":  # Check if player is level 5 or higher for Barrier Shield
                    await self.process_barrier_shield(channel, user)
                else:
                    await channel.send("You need to be at least Level 5 to use Barrier Shield!")
                    await self.send_npc_embed(channel, battle["npc"])  # Re-send the embed after showing the error
            elif str(reaction.emoji) == "🚁":
                if player_level >= 10 and player_race == "terrans":  # Check if player is level 10 or higher for Summon Drone
                    await self.summon_drone(channel, user)
                    await self.npc_turn(channel, battle)
                else:
                    await channel.send("You need to be at least Level 10 to use Summon Drone!")
                    await self.send_npc_embed(channel, battle["npc"])  # Re-send the embed after showing the error
            elif str(reaction.emoji) == "💉":
                if player_level >= 2 and player_race == "mammal alien":
                    await self.process_poison_dart(channel, user, "poison dart")
                    await self.npc_turn(channel, battle)
                else:
                    await channel.send("You need to be at least Level 2 and Mammal Alien to use Poison Dart!")
                    await self.send_npc_embed(channel, battle["npc"])
            elif str(reaction.emoji) == "🦔":
                if player_level >= 5 and player_race == "mammal alien":
                    await self.process_call_allies(channel, user, battle)
                    await self.npc_turn(channel, battle)
                else:    
                    await channel.send("You need to be at least Level 5 and Mammal Alien to use Call Allies!")
                    await self.send_npc_embed(channel, user, battle["npc"])
            elif str(reaction.emoji) == "🤮":
                if player_level >= 10 and player_race == "mammal alien":
                    await self.process_slime_attack (channel, user, battle)
                    await self.npc_turn(channel, battle)
                else:    
                    await channel.send("You need to be at least Level 10 and Mammal Alien to use Slime Attack!")    
            elif str(reaction.emoji) == "💨":
                if player_level >= 2 and player_race == "reptile alien":
                    await self.process_lunge(channel, user, battle)
                    #await self.npc_turn(ctx, self.active_battles[ctx.author.id])
                else:
                    await channel.send("You need to be at least Level 2 and Reptile Alien to use Lunge!")
                    await self.send_npc_embed(channel, battle["npc"]) 
            elif str(reaction.emoji) == "🐲":
                if player_level >= 5 and player_race == "reptile alien":
                    await self.process_harden_scales(channel, user, battle)
                    await self.npc_turn(channel, battle)
                else:
                    await channel.send("You need to be at least Level 5 and Reptile Alien to use Harden Scales!")
                    await self.send_npc_embed(channel, battle["npc"])
            elif str(reaction.emoji) == "🐉":
                if player_level >= 10 and player_race == "reptile alien":
                    await self.process_deploy_needles(channel, user, battle)
                    await self.npc_turn(channel, battle)
                else:
                    await channel.send("You need to be at least Level 10 and Reptile Alien to use Deploy Spikes!")
                    await self.send_npc_embed(channel, user, battle["npc"])
            elif str(reaction.emoji) == "🌀":
                if player_level >= 2 and player_race == "blue humanoid wizard":
                    await self.process_energy_ball(channel, battle)
                    #await self.npc_turn(ctx, self.active_battles[ctx.author.id])
                else:
                    await channel.send("You need to be at least Level 2 and Blue Humanoid Wizard to use Energy Ball!")
                    await self.send_npc_embed(channel, user, battle["npc"])
            elif str(reaction.emoji) == "🌟":
                if player_level >= 5 and player_race == "blue humanoid wizard":
                    await self.process_healing_aura(channel, battle)
                    #await self.npc_turn(ctx, self.active_battles[ctx.author.id])
                else:
                    await channel.send("You need to be at least Level 5 and Blue Humanoid Wizard to use Energy Ball!")
                    await self.send_npc_embed(channel, user, battle["npc"])    
            elif str(reaction.emoji) == "😵":
                if player_level >= 10 and player_race == "blue humanoid wizard":
                    await self.process_tremors(channel, user, battle)
                    await self.npc_turn(channel, battle)
                else:
                    await channel.send("You need to be at least Level 10 and Blue Humanoid Wizard to use Tremors!")
                    await self.send_npc_embed(channel, battle["npc"])   
            elif str(reaction.emoji) == "🗿":
                if player_level >= 2 and player_race == "shapeshifter":
                    await self.process_stoneify(channel, user, battle)
                    #await self.npc_turn(ctx, self.active_battles[ctx.author.id])
                else:
                    await channel.send("You need to be at least Level 2 and Shapeshifter to use Stoneify!")
                    await self.send_npc_embed(channel, battle["npc"])        
            elif str(reaction.emoji) == "👨🏻‍🤝‍👨🏼":
                if player_level >= 5 and player_race == "shapeshifter":
                    await self.process_twinify_effect(channel, user, battle)
                    #await self.npc_turn(ctx, self.active_battles[ctx.author.id])
                else:
                    await channel.send("You need to be at least Level 2 and Shapeshifter to use Twinify!")
                    await self.send_npc_embed(channel, battle["npc"])         
            elif str(reaction.emoji) == "🔱":
                if player_level >= 10 and player_race == "shapeshifter":
                    await self.process_harpoonify(channel, user, battle)
                    #await self.npc_turn(ctx, self.active_battles[ctx.author.id])
                else:
                    await channel.send("You need to be at least Level 2 and Shapeshifter to use Twinify!")
                    await self.send_npc_embed(channel, battle["npc"])                     
            elif str(reaction.emoji) == "☄️":
                if player_level >= 2 and player_race == "robot race":
                    await self.deploy_laser_fists(channel, user, battle)
                    #await self.npc_turn(ctx, self.active_battles[ctx.author.id])
                else:
                    await channel.send("You need to be at least Level 2 and Robot Race to use Deploy Laser Fist!")
                    await self.send_npc_embed(channel, battle["npc"])                        
                                 
                                     
        except asyncio.TimeoutError:
            await channel.send("Battle timed out! Defaulting to a normal attack.")
            await self.process_attack(channel, user, battle, "normal")
        
    async def process_major_pain(self, ctx, battle):
        """Handle the player's Major Pain attack with cooldown check."""
        current_time = time.time()  # Get the current time in seconds since the epoch

        # Check if the player is on cooldown
        if ctx.author.id in self.major_pain_cooldowns:
            last_used = self.major_pain_cooldowns[ctx.author.id]
            time_diff = current_time - last_used

            if time_diff < self.cooldown_time:
                # If the cooldown hasn't passed yet, inform the player and allow them to choose another action
                time_remaining = self.cooldown_time - time_diff
                cooldown_message = await ctx.send(f"⚠️ Major Pain is on cooldown! You can use it again in {int(time_remaining // 60)} minutes.")
                
                # Update the message with new options for the player's turn
                embed = discord.Embed(
                    title="Your turn",
                    description="Major Pain is on cooldown. Choose another action.",
                    color=discord.Color.blue()
                )
                
                action_message = await ctx.send(embed=embed)

               

                return  # Exit after the player selects a new action

        # If no cooldown, proceed with Major Pain logic
        if ctx.author.id not in self.active_battles:
            await ctx.send("You are not in a battle! Use `!fight` to start one.")
            return
        battle = self.active_battles[ctx.author.id]
        player = battle["player"]
        npc = battle["npc"]

        # Major Pain logic
        if random.random() <= 0.2:  # 20% chance for backfire
            backfire_damage = max(0, int(player["attack"] * 3) - player["defense"])
            player["health"] -= backfire_damage
            await ctx.send(f"💣 Your **Major Pain** ability backfired! You took {backfire_damage} damage!")
            self.update_player_health(ctx.author.id, player["health"])
        else:
            # 80% chance for massive damage on the NPC
            damage = max(0, int(player["attack"] * 3) - npc["defense"])  # 3x attack damage
            npc["health"] -= damage
            if npc["health"] <=0: 
                await ctx.send(f"💣 You unleashed **Major Pain** and defeated **{npc['name']}**!")
            else:
                await ctx.send(f"💣 You unleashed **Major Pain** on the **{npc['name']}** for {damage} damage!")
            self.major_pain_cooldowns[ctx.author.id] = current_time  # Set the cooldown
        
        if npc["health"] <= 0:
            xp_gain = npc["xp"]
            print(f"XP Gain: {xp_gain}")  # Debugging line
            result = self.add_experience(ctx.author.id, xp_gain)
            print(f"add_experience result: {result}")  # Debug log

            if "error" in result:
                await ctx.send("An error occurred while updating your experience.")
                del self.active_battles[ctx.author.id]
                return
            
            # Update the player level based on the new experience
            get_player_level(ctx.author.id)

            updated_stats = result["stats"]
            level_up_occurred = result["level_up_occurred"]

            if level_up_occurred:
                old_level = player.get("level")
                new_level = updated_stats["level"]
                attack_increase = updated_stats["attack"] - player["attack"]
                defense_increase = updated_stats["defense"] - player["defense"]
                health_increase = updated_stats["max_health"] - player["max_health"]

                level_up_message = (
                    f"🎉 You leveled up to **Level {new_level}**!\n"
                    f"🆙 **+{attack_increase} Attack, +{defense_increase} Defense, "
                    f"+{health_increase} Max_Health**\n"
                    f"📊 Your current stats: "
                    f"Attack: {updated_stats['attack']}, Defense: {updated_stats['defense']}, "
                    f"Health: {updated_stats['health']}/{updated_stats['max_health']}."
                )
            else:
                level_up_message = ""

            await ctx.send(
                f"🎉 You defeated the **{npc['name']}** and gained **{xp_gain} XP**!\n"
                f"{level_up_message}"
            )

            del self.active_battles[ctx.author.id]
            return

        # If the NPC is still alive, continue to NPC's turn
        await self.npc_turn(ctx, battle)
        
    async def process_lunge(self, ctx, battle):
       
        await apply_lunge(
            ctx=ctx,
            battle=battle,
            active_battles=self.active_battles,
            lunge_cooldowns=self.lunge_cooldowns,
            player_turn=self.player_turn,
            handle_npc_defeat=self.handle_npc_defeat,
            npc_turn=self.npc_turn
    )
        await self.npc_turn(ctx, battle)    
    async def summon_drone(self, ctx):
        """Summon Drone ability that multiplies damage by 3 for 4 turns."""
        if ctx.author.id not in self.active_battles:
            await ctx.send("You are not in a battle! Use `!fight` to start one.")
            return

        # Get the active battle
        battle = self.active_battles[ctx.author.id]
        player = battle['player']

        # Activate Summon Drone status effect
        message = activate_summon_drone(player)
        await ctx.send(message)    
    async def process_stoneify(self, ctx, battle):
        """Handle the player's Stoneify ability."""
        if ctx.author.id not in self.active_battles:
            await ctx.send("You are not in a battle! Use `!fight` to start one.")
            return
        
        battle = self.active_battles[ctx.author.id]
        player = battle["player"]
        current_time = time.time()  # Get the current time in seconds since the epoch
        cooldown_time = 8 * 60 * 60  # 8 hours cooldown for "Stoneify"

        # Check if the player has used Stoneify recently
        if ctx.author.id in self.stoneify_cooldowns:
            last_used = self.stoneify_cooldowns[ctx.author.id]
            time_diff = current_time - last_used

            if time_diff < cooldown_time:
                # If the cooldown hasn't passed yet, inform the player and allow them to choose another action
                time_remaining = cooldown_time - time_diff
                await ctx.send(
                    f"⚠️ **Stoneify** is on cooldown! You can use it again in {int(time_remaining // 60)} minutes."
                )

                # Create an embed message
                embed = discord.Embed(
                    title="Your turn",
                    description="Stoneify is on cooldown. Choose another action.",
                    color=discord.Color.blue()
                )
                await ctx.send(embed=embed)
                await self.player_turn(ctx, battle)
                return

        # Apply the Stoneify effect to the player
        if "status_effects" not in player:
            player["status_effects"] = {}
        
        player["status_effects"]["stoneify"] = {
            "damage_reduction": 0.75,  # Reduce damage taken by 75%
            "turns_remaining": 3,  # Effect lasts for 3 turns
        }
        
        await ctx.send(
            f"🛡️ You activated **Stoneify**! You will take 75% less damage for the next 3 turns."
        )
        
        # Record the ability use and start cooldown
        self.stoneify_cooldowns[ctx.author.id] = current_time

        # Proceed to NPC's turn
        await self.npc_turn(ctx, battle)   
    async def process_energy_ball(self, ctx, battle):
 
        await apply_energy_ball(self,ctx,battle)
        await self.player_turn(ctx, battle)    
    
   # async def process_healing_aura(self, ctx, battle):
     #   """
      #  Wrapper for the Healing Aura ability, calling the function from statusEffects.py.
       # """
      #  await apply_healing_aura(self, ctx, battle)
      #  print("DEBUG, Healing Aura activated by reaction")
      #  await self.npc_turn(ctx, battle)
                
    async def process_barrier_shield(self, ctx):
        """Handle the player's Barrier Shield ability."""
        
        # Check if the player is in an active battle
        if ctx.author.id not in self.active_battles:
            await ctx.send("You are not in a battle! Use `!fight` to start one.")
            return

        # Get the active battle and the player object
        battle = self.active_battles[ctx.author.id]
        player = battle['player']

        # Apply the Barrier Shield ability and get the response message and success status
        result = await apply_barrier_shield(player, ctx, self.barrier_shield_cooldowns)
        if result is None:
            await ctx.send("An error occurred while processing the Barrier Shield.")
            return

        message, success = result

        # Send the message to the player, informing them about the result
        await ctx.send(message)

        # Update the player's shield activation status if successful
        if success:
            player["shield_activated"] = True

            # Proceed with the NPC's turn or the next step in the battle
            await self.npc_turn(ctx, battle)
            
    async def process_tremors(self, ctx, battle):
        """Handle the player's Tremors ability."""
        player = battle["player"]
        npc = battle["npc"]
        current_time = time.time()
        cooldown_time = 3 * 60 * 60  # 3-hour cooldown for "Tremors"

        # Initialize cooldown tracking if not present
        if not hasattr(self, "tremors_cooldowns"):
            self.tremors_cooldowns = {}

        # Check if the ability is on cooldown
        if ctx.author.id in self.tremors_cooldowns:
            last_used = self.tremors_cooldowns[ctx.author.id]
            time_diff = current_time - last_used

            if time_diff < cooldown_time:
                time_remaining = cooldown_time - time_diff
                await ctx.send(
                    f"⚠️ **Tremors** is on cooldown! You can use it again in {int(time_remaining // 60)} minutes."
                )
                await self.player_turn(ctx, battle)
                return

        if npc["health"] <= 0:
            await ctx.send("The NPC is already defeated!")
            return

        # Calculate Tremors damage
        tremors_damage = player["attack"] * 4
        npc["health"] -= tremors_damage

        # Apply the prone status effect
        if "status_effects" not in npc:
            npc["status_effects"] = {}

        # 50% chance to knock NPC prone
        is_prone = random.random() < .5

        if is_prone:
            prone_effect = {
                "turns_remaining": 2,  # 1 turn to skip + 1 turn to stand up
                "bonus_damage": 0.5,  # Takes +50% damage
            }
            npc["status_effects"]["prone"] = prone_effect
            await ctx.send(
                f"🌋 **Tremors!** You dealt **{tremors_damage} damage** to **{npc['name']}**, knocking them **prone**!"
            )
        else:
            await ctx.send(
                f"🌋 **Tremors!** You dealt **{tremors_damage} damage** to **{npc['name']}**, but they resisted being knocked prone!"
            )

        # Update cooldown
        self.tremors_cooldowns[ctx.author.id] = current_time

        # Check if the NPC is defeated
        if npc["health"] <= 0:
            await ctx.send(f"💀 You defeated the **{npc['name']}**!")
            del self.active_battles[ctx.author.id]
            return

        # Proceed to player's next turn
        await self.player_turn(ctx, battle)   
        
    async def process_harden_scales(self, ctx, battle):
        """Apply the Harden Scales ability."""
        player = battle["player"]
        cooldowns = self.harden_scales_cooldowns

        # Call the centralized function in statusEffects.py
        result = await apply_harden_scales(player, ctx, cooldowns)

        # Handle the result message
        await ctx.send(result)
        await self.npc_turn (ctx, battle)
        # If the ability couldn't be applied, prompt the player for another action
        if "Harden Scales active" not in result:
            await self.npc_turn(ctx, battle)
            
        async def process_deploy_needles(self, ctx, battle):
            """Activate the Deploy Needles ability."""
            player = battle["player"]

            # Call the function from statusEffects.py
            activation_message = await process_deploy_needles(ctx, self.active_battles[ctx.author.id])

            # Send the activation message to the user
            await ctx.send(activation_message)
            
            # Proceed to the NPC's turn
            await self.npc_turn(ctx, battle)
    
    async def process_slime_attack(self, ctx, battle):
        """Handle the player's Slime Attack with cooldown."""
        player = battle["player"]
        npc = battle["npc"]
        
        result = await apply_slime_attack(ctx, battle, self.slime_attack_cooldowns)

        if result == "cooldown":
            # If Slime Attack is on cooldown, return to the player's turn
            await self.player_turn(ctx, battle)

        if result == "immobilized":
            await ctx.send(
                f"🟢 **{ctx.author.display_name}** used **Slime Attack**, immobilizing **{npc['name']}** for 3 turns! "
                f"They will take double damage during those turns!"
            )
            # Proceed to the next turn
            await self.player_turn(ctx, battle)

        # Normal NPC turn logic
        npc = battle["npc"]
        player = battle["player"]

        damage = max(0, int(npc["attack"]) - player["defense"])
        player["health"] -= damage
        await ctx.send(f"⚔️ The **{npc['name']}** attacked you for **{damage} damage**!")

        if player["health"] <= 0:
            await ctx.send("💀 You were defeated in battle!")
            del self.active_battles[ctx.author.id]
            return

        await self.player_turn(ctx, battle)  
          
    async def process_twinify_effect(self, ctx, battle):
        """Handle the Twinify effect, applying and managing its behavior."""
        player = battle["player"]

        # Ensure the player's status_effects dictionary exists
        if "status_effects" not in player:
            player["status_effects"] = {}

        # Check if the Twinify effect is already active
        if "twinify" not in player["status_effects"]:
            # Activate the Twinify effect
            player["status_effects"]["twinify"] = {
                "turns_remaining": 4,  # Lasts for 3 turns
                "damage_multiplier": 2.0,  # Double damage
                "miss_chance": 0.5,       # 50% chance to miss
            }
            await ctx.send(
                f"✨ **Twinify activated!** Your attack power is doubled, and enemies have a 50% chance of missing their attacks for 3 turns!"
            )
            await self.npc_turn(ctx, battle)
            return

        # Process the Twinify effect if already active
        twinify_effect = player["status_effects"]["twinify"]

        # Apply miss chance to NPC attacks (example effect)
        if random.random() < twinify_effect["miss_chance"]:
            await ctx.send("🌀 The enemy's attack missed due to the Twinify effect!")
        else:
            await ctx.send("✨ Twinify effect active, but the attack hits!")

        # Decrement turns remaining
        twinify_effect["turns_remaining"] -= 1

        # Remove the effect if expired
        if twinify_effect["turns_remaining"] <= 0:
            del player["status_effects"]["twinify"]
            await ctx.send("🔄 The Twinify effect has worn off!")

            # Clean up status_effects dictionary if empty
            if not player["status_effects"]:
                del player["status_effects"]
        
    async def apply_twinify_damage(self, ctx, battle, damage):
        """Apply Twinify damage multiplier during the player's turn."""
        player = battle["player"]
        npc = battle["npc"]

        if "status_effects" in player and "twinify" in player["status_effects"]:
            twinify_effect = player["status_effects"]["twinify"]
            damage *= twinify_effect["damage_multiplier"]
            await ctx.send(f"⚡ Your Twinify effect is active, dealing **{int(damage)} damage**!")

            twinify_effect["turns_remaining"] -= 1
            if twinify_effect["turns_remaining"] <= 0:
                del player["status_effects"]["twinify"]
                if not player["status_effects"]:
                    del player["status_effects"]
                await ctx.send("🔄 The Twinify effect has worn off!")
        
        npc["health"] -= int(damage)
        
    async def process_harpoonify(self, ctx, battle):
        """Handle the player's Harpoonify attack."""
        if ctx.author.id not in self.active_battles:
            await ctx.send("You are not in a battle! Use `!fight` to start one.")
            return

        # Get player and NPC
        battle = self.active_battles[ctx.author.id]
        player = battle["player"]
        npc = battle["npc"]

        try:
            # Call the external function
            message, defeated, cooldown_applied = await apply_harpoonify_effect(
                player, npc, self.harpoonify_cooldowns, ctx.author.id
            )

            # Send messages to the user
            await ctx.send(message)

            if defeated:
                await self.handle_npc_defeat(ctx, npc, battle['player'])
                return

            if not cooldown_applied:
                # If cooldown wasn't applied, prompt the user to take another action
                await self.player_turn(ctx, battle)
                return

            # Proceed to NPC's turn
            await self.npc_turn(ctx, battle)

        except Exception as e:
            print(f"Error in process_harpoonify: {e}")
            await ctx.send(f"An error occurred during your action: {e}")
        
    async def process_deploy_needles(self, ctx, battle):
        """Activate the Deploy Needles ability."""
        player = battle["player"]

        # Call the function from statusEffects.py
        activation_message = await process_deploy_needles(ctx, self.active_battles[ctx.author.id])

        # Send the activation message to the user
        await ctx.send(activation_message)

        # Proceed to the NPC's turn
        await self.npc_turn(ctx, battle)
        
    async def process_attack(self, channel, user, battle, attack_type):
        """Handles attack logic, keeping damage and updated health in the embed."""
        
        battle = self.active_battles.get(user.id)
        if not battle:
            await channel.send("Error: No active battle found.")
            return

        player = battle.get('player')
        npc = battle.get('npc')
        if not player or not npc:
            await channel.send("Error: Missing player or NPC data.")
            return

        embed_message = battle.get("embed_message")

        try:
            # Apply status effects and calculate damage multiplier
            result = await apply_player_status_effects(player, npc, channel, user)
            if result is None:
                print("[ERROR] apply_player_status_effects returned None!")
                attack_multiplier, expired_effects = 1, []  
            else:
                defense_multiplier, attack_multiplier, expired_effects = result

            # Determine type multiplier based on attack_type
            if attack_type == "normal":
                type_multiplier = 1.0
            elif attack_type == "power":
                type_multiplier = 1.5
            else:
                type_multiplier = 1.0  # default fallback

            # Calculate damage with both multipliers
            player_damage = max((player['attack'] * attack_multiplier * type_multiplier) - npc['defense'], 0)
            npc['health'] -= player_damage

            # NPC counterattacks if still alive
            if npc["health"] > 0:
                npc_damage = max(npc["attack"] - player["defense"], 0)
                player["health"] -= npc_damage
            else:
                npc_damage = 0  # NPC dies, no counterattack

            # 🎨 Update the existing embed **WITHOUT CLEARING FIELDS**
            embed = embed_message.embeds[0]

            # ✅ Keep the updated health in the embed description
            embed.description = (
                f"🧑 {user.mention} ❤️ {player['health']}  |  👹 {npc['name']} ❤️ {npc['health']}\n\n"
                "React with ⚔️ for a **normal attack** or 💥 for a **power attack**!"
            )

            # ✅ **Check if damage fields already exist**  
            found_player_field = False
            found_npc_field = False

            for field in embed.fields:
                if "Your Attack" in field.name:
                    field.value = f"⚔️ You dealt **{player_damage}** damage to {npc['name']}."
                    found_player_field = True
                if "Enemy Attack" in field.name:
                    field.value = f"👹 {npc['name']} dealt **{npc_damage}** damage to you."
                    found_npc_field = True

            # ✅ **Only add fields if they don't already exist**
            if not found_player_field:
                embed.add_field(name="🗡️ Your Attack", value=f"⚔️ You dealt **{player_damage}** damage to {npc['name']}.", inline=False)
            if not found_npc_field:
                embed.add_field(name="💥 Enemy Attack", value=f"👹 {npc['name']} dealt **{npc_damage}** damage to you.", inline=False)

            # **Check for battle outcome**
            if npc["health"] <= 0:
                embed.title = "🏆 Victory!"
                embed.description = f"⚔️ **You defeated {npc['name']}!**"
                await embed_message.edit(embed=embed)
                del self.active_battles[user.id]  
                return

            if player["health"] <= 0:
                embed.title = "☠️ Defeat!"
                embed.description = f"💀 {user.mention} was defeated by {npc['name']}!"
                await embed_message.edit(embed=embed)
                del self.active_battles[user.id]  
                return

            # Update embed with new health and **PERSISTING DAMAGE FIELDS**
            await embed_message.edit(embed=embed)  

            # Pass expired effects to player_turn for processing
            battle["expired_effects"] = expired_effects

            # NPC's turn next
            await self.npc_turn(channel, user, battle)

        except Exception as e:
            print(f"Error in process_attack: {e}")
            await channel.send("An error occurred during your attack.")

    async def npc_turn(self, channel, user, battle):
        """NPC's turn to attack the player."""
        player = battle["player"]
        npc = battle["npc"]
        defense_multiplier = await apply_player_status_effects(player, npc, channel, user)
        if isinstance(defense_multiplier, tuple):
            defense_multiplier = defense_multiplier[0]  # Unpack the first value if needed
        # Validate NPC data
        if npc is None or "name" not in npc:
            await channel.send("⚠️ Error: NPC data is incomplete or missing.")
            print(f"Error: NPC object is invalid. NPC: {npc}")  # Log the invalid NPC
            return

        npc_name = npc.get("name", "Unnamed NPC")
        print(f"Entering npc_turn. NPC: {npc_name} | Player: {player.get('name', 'Unknown Player')}")
        
        npc_defense_multiplier = await apply_npc_status_effects(npc, channel, user)  # Apply effects and get defense multiplier
        
        if "health_loss" in npc.get("status_effects", {}):
            effect = npc["status_effects"]["health_loss"]
            bleeding_damage = npc["max_health"] * effect["value"]
            npc["health"] -= bleeding_damage
            
        if "status_effects" in npc and "slime" in npc["status_effects"]:
            await self.player_turn(channel, user, battle)
            await channel.send("NPC Turn skilled due to being immobilized!") 
            return   
        # Apply NPC status effects
       # await apply_healing_aura(player, ctx, self.collection)
        

        # Retrieve adjusted defense or default to base defense
        base_defense = player.get("defense", 0) * defense_multiplier
        adjusted_defense = base_defense  # Start with base defense

        # Check for any status effects that modify defense
        defense_found = False
        for effect_name, effect_data in player.get("status_effects", {}).items():
            if "adjusted_defense" in effect_data:
                adjusted_defense = max(adjusted_defense, effect_data["adjusted_defense"])
                print(f"[DEBUG] Using adjusted defense from {effect_name}: {effect_data['adjusted_defense']}")
                defense_found = True

        # If no defense-modifying effects are found, use base defense with a multiplier of 1
        if not defense_found:
            npc_defense_multiplier = 1
            print(f"[DEBUG] No defense-modifying effects found. Defaulting to base defense: {base_defense}")

        print(f"[DEBUG] Final adjusted defense: {adjusted_defense}, Defense Multiplier: {npc_defense_multiplier}")

        # Check for poison dart status effect
        if "poison dart" in npc.get("status_effects", {}):
            poison_effect = npc["status_effects"]["poison dart"]
            poison_damage = poison_effect["damage"]

            # Apply poison damage to the NPC
            npc["health"] -= poison_damage
            await channel.send(f"☠️ **{npc_name}** lost **{poison_damage}** **health** due to poison!")
        if "shield_barrier" in player.get("status_effects", {}):
            await self.player_turn(channel, user, battle)
            return
        # Calculate and apply damage
        npc_damage = max(0, npc["attack"] - adjusted_defense * npc_defense_multiplier)
        player["health"] -= npc_damage
        #await ctx.send(f"⚔️ The **{npc_name}** attacked you, dealing {npc_damage} damage!")
        
        self.collection.update_one(
            {"user_id": user.id},  # Match the correct player
            {"$set": {"health": player["health"]}}  # Update health
        )
        # Check if NPC is defeated after attack
        if npc["health"] <= 0:
            await self.handle_npc_defeat(channel, user, npc, battle["player"])
            return

        # Check if player is defeated
        if player["health"] <= 0:
            await channel.send("💀 You were defeated in battle!")
            del self.active_battles[user.id]
            embed = discord.Embed(
                title="💀 You Have Been Defeated 💀",
                description=f"The **{npc_name}** has vanquished you!",
            )
            embed.add_field(name="NPC Name", value=npc_name, inline=True)
            embed.add_field(name="NPC Remaining Health", value="0 (Defeated)", inline=True)
            embed.add_field(name="Your Remaining Health", value="0 (Defeated)", inline=True)
            embed.set_thumbnail(url="https://i.imgur.com/hNKBn3F.jpeg")
            embed.set_footer(text="Better luck next time! Use `!heal` to recover and try again.")
            await channel.send(embed=embed)
            return

        # Proceed to the player's turn
        await self.player_turn(channel, user, battle)
        print(f"Debug: Entering player_turn.")
        
    async def handle_npc_defeat(self, user, channel, npc, player):
        """
        Handle NPC defeat: award experience, notify the player, and clean up the battle.

        :param ctx: The context of the game.
        :param npc: The defeated NPC object.
        :param player: The player's data.
        """
        # Award experience to the player
        xp_gain = npc.get("xp", 0)  # Ensure XP value exists
        result = self.add_experience(user.id, xp_gain)
        print(f"add_experience result: {result}")  # Debug log

        # Format the message based on the result
        if "error" in result:
            await channel.send(result["error"])
        else:
            stats = result["stats"]
            level_up_message = ""
            if result.get("level_up_occurred", False):
                level_up_message = (
                    f"🎉 Congratulations! You leveled up to **Level {stats['level']}**! "
                    f"Your stats have improved: Attack {stats['attack']}, Defense {stats['defense']}, Max_Health {stats['max_health']}."
                )
            
            # Send XP and level-up notifications
            await channel.send(
                f"🎉 You defeated the **{npc['name']}** and gained **{xp_gain} XP**!\n{level_up_message}"
            )

        # Send final victory message
        embed = discord.Embed(
            title="🎉 Victory! 🎉",
            description=f"You have defeated the **{npc['name']}**!",
        )
        embed.add_field(name="Your Remaining Health", value=player.get("health", "Unknown"), inline=True)
        embed.set_footer(text="Congratulations!")
        await channel.send(embed=embed)

        # Clean up the battle
        battle_data = self.active_battles.get(user.id)
        on_victory = battle_data.get("on_victory") if battle_data else None

        if on_victory is None:
            print(f"⚠️ No on_victory callback set for user {user.name} ({user.id})")
        elif not callable(on_victory):
            print(f"❌ on_victory exists but is not callable: {on_victory}")
        else:
            print(f"✅ Calling on_victory callback for user {user.name} ({user.id})")
            await on_victory(channel, user)

        # ✅ Clean up the battle
        del self.active_battles[user.id]

    async def process_poison_dart(self, ctx, action):
        print("[DEBUG] process_poison_dart called from pve.py")
        """Handle the player's poison dart action."""
        # Retrieve the battle data from active battles
        if ctx.author.id not in self.active_battles:
            await ctx.send("You are not in a battle! Use `!fight` to start one.")
            return

        battle = self.active_battles[ctx.author.id]  # Fetch the battle dictionary

        # Call the apply_poison_dart function
        message, success = await apply_poison_dart(ctx, battle, self.poison_dart_cooldowns)

        # Send the result of the poison dart action
        await ctx.send(message)

        # If the action was successful, continue to NPC's turn
        if success:
            try:
                await self.npc_turn(ctx, battle)  # Proceed to NPC's turn
            except Exception as e:
                print(f"Error during NPC turn: {e}")
                
async def process_call_allies(self, ctx, battle):
    """Handle the player's Call Allies ability."""
    result = await process_call_allies(ctx, battle, self.call_allies_cooldowns)

    # Handle results from process_call_allies
    if result == "cooldown":
        # Cooldown case: Player's turn continues
        await self.player_turn(ctx, battle)
        return

    if result == "npc_defeated":
        npc = battle["npc"]
        xp_gain = npc["xp"]
        result = self.add_experience(ctx.author.id, xp_gain)

        if "error" in result:
            await ctx.send("An error occurred while updating your experience.")
            del self.active_battles[ctx.author.id]
            return

        level_up_message = ""
        if result["level_up_occurred"]:
            updated_stats = result["stats"]
            level_up_message = (
                f"🎉 You leveled up to **Level {updated_stats['level']}**!\n"
                f"📊 Current stats: Attack: {updated_stats['attack']}, "
                f"Defense: {updated_stats['defense']}, Health: {updated_stats['max_health']}."
            )

        await ctx.send(
            f"🎉 You defeated the **{npc['name']}** and gained **{xp_gain} XP**!\n"
            f"{level_up_message}"
        )
        del self.active_battles[ctx.author.id]
        return

    # If successful, continue to the player's next turn
    await self.player_turn(ctx, battle)
    

        


