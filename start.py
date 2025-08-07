import discord
from discord.ext import commands
from pymongo import MongoClient
import asyncio
from .act1_1 import Act1_1  # ✅ Import the class instead
from .dialog import call_cog_method

class Start(commands.Cog):
    def __init__(self, bot):
        self._last_member = None
        self.bot = bot
        self.client = MongoClient("mongodb+srv://billymcdugal:Passport86@economy.iaynb.mongodb.net/")
        self.db = self.client['Player']  # Replace with your database name
        self.collection = self.db['Start']  # Replace with your collection name
        self.choices_collection = self.db['Start.Choices']
        self.stats_collection = self.db["Player.Stats"]

    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.content == "ping start-cog":
            await msg.channel.send("Start-cog is connected..")

    @commands.command()
    async def start(self, ctx):
        # Check if user has already started
        user_choices = self.choices_collection.find_one({"user_id": ctx.author.id})
        if user_choices:
            await ctx.send(f"{ctx.author.mention}, you have already created your character!")
            return

        await ctx.send(f"{ctx.author.name}, you have begun your long journey. Continue creating your character!")
        await self.choosesex(ctx)
        user_id = ctx.author.id
        self.stats_collection.update_one(
            {"user_id": user_id},
            {"$set": {"xp": 0}},  # Set experience and credits to 0
            upsert=True
            
        )
        user_id = ctx.author.id
        self.stats_collection.update_one(
            {"user_id": user_id},
            {"$set": {"level": 1}},  # Set experience and credits to 0
            upsert=True
            
        )
        economy_db = self.client['Economy']  # Access the Economy database
        currency_collection = economy_db['Currency']  # Access the Currency collection
        currency_collection.update_one(
        {"user_id": user_id},
        {"$set": {"credits": 0}},  # Set credits to 0 in the Currency collection
        upsert=True
    )
    @commands.command()
    async def choosesex(self, ctx):
        await asyncio.sleep(1)
        options = ["Male", "Female"] 
                   #"Ambiguous", "Asexual"]
        embed = discord.Embed(title="Choose your character's sex!", description="React with the correct emoji to make your choice.")
        option_emoji = ["1️⃣", "2️⃣",] #"3️⃣", "4️⃣"]
        description = "\n".join([f"{emoji} {option}" for emoji, option in zip(option_emoji, options)])
        embed.add_field(name="Options", value=description, inline=False)

        message = await ctx.send(embed=embed)

        for emoji in option_emoji:
            await message.add_reaction(emoji)

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in option_emoji and reaction.message.id == message.id

        try:
            reaction, _ = await self.bot.wait_for('reaction_add', timeout=120.0, check=check)
            choice_index = option_emoji.index(str(reaction.emoji))
            choice = options[choice_index]

            await self.save_hair_choice(ctx.author.id, choice)
            await ctx.send(f"{ctx.author.mention}, you have chosen: {choice}")
        except asyncio.TimeoutError:
            await ctx.send(f"{ctx.author.mention}, you took too long to choose!")
        
        # Proceed to race selection after hair selection
        await self.choosehair(ctx)

    async def save_hair_choice(self, user_id, choice):
        self.choices_collection.update_one(
            {"user_id": user_id},
            {"$set": {"hair.choice": choice}},
            upsert=True
        )
    @commands.command()
    async def choosehair(self, ctx):
        await asyncio.sleep(1)
        options = ["Black", "Blonde", "Green"] 
                   #"Blue", "White", "Brown", "Purple", "Red"]
        embed = discord.Embed(title="Choose your character's hair color!", description="React with the correct emoji to make your choice.")
        option_emoji = ["⚫", "🟡", "🟢"] 
                        #"🔵", "⚪", "🟤", "🟣", "🔴"] 
        description = "\n".join([f"{emoji} {option}" for emoji, option in zip(option_emoji, options)])
        embed.add_field(name="Options", value=description, inline=False)

        message = await ctx.send(embed=embed)

        for emoji in option_emoji:
            await message.add_reaction(emoji)

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in option_emoji and reaction.message.id == message.id

        try:
            reaction, _ = await self.bot.wait_for('reaction_add', timeout=120.0, check=check)
            choice_index = option_emoji.index(str(reaction.emoji))
            choice = options[choice_index]

            await self.save_hair_choice(ctx.author.id, choice)
            await ctx.send(f"{ctx.author.mention}, you have chosen: {choice}")
        except asyncio.TimeoutError:
            await ctx.send(f"{ctx.author.mention}, you took too long to choose!")
        
        # Proceed to race selection after hair selection
        await self.chooserace(ctx)

    async def save_hair_choice(self, user_id, choice):
        self.choices_collection.update_one(
            {"user_id": user_id},
            {"$set": {"hair.choice": choice}},
            upsert=True
        )

    @commands.command()
    async def chooserace(self, ctx):
        await asyncio.sleep(1)
        options = ["terrans", "feralin", "scarvous"] #"Pharquels", "Bar'Phons", "Robartons"]
        embed = discord.Embed(title="Choose your character's race!", description="React with the correct emoji to make your choice.")
        option_emoji = ["1️⃣", "2️⃣", "3️⃣"] #"4️⃣", "5️⃣", "6️⃣"]  # Adjusted for the six race options
        description = "\n".join([f"{emoji} {option}" for emoji, option in zip(option_emoji, options)])
        embed.add_field(name="Options", value=description, inline=False)

        message = await ctx.send(embed=embed)

        for emoji in option_emoji:
            await message.add_reaction(emoji)

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in option_emoji and reaction.message.id == message.id

        try:
            reaction, _ = await self.bot.wait_for('reaction_add', timeout=120.0, check=check)
            choice_index = option_emoji.index(str(reaction.emoji))
            choice = options[choice_index]

            await self.save_race_choice(ctx.author.id, choice)
            await ctx.send(f"{ctx.author.mention}, you have chosen: {choice}")
        except asyncio.TimeoutError:
            await ctx.send(f"{ctx.author.mention}, you took too long to choose!")

        # Proceed to planet selection after race selection
        await self.chooseplanet(ctx)

    async def save_race_choice(self, user_id, choice):
        self.choices_collection.update_one(
            {"user_id": user_id},
            {"$set": {"race.choice": choice.lower()}},  # Save in lowercase for consistency
            upsert=True
        )

    @commands.command()
    async def chooseplanet(self, ctx):
        await asyncio.sleep(1)
        options = ["Terranus", "Feraneous", "Drakon"] 
                   #"Harzen", "Phonzar", "Mechanius"]
        embed = discord.Embed(title="Choose your character's home planet!", description="React with the correct emoji to make your choice.")
        option_emoji = ["1️⃣", "2️⃣", "3️⃣",] 
                        #"4️⃣", "5️⃣", "6️⃣"]
        description = "\n".join([f"{emoji} {option}" for emoji, option in zip(option_emoji, options)])
        embed.add_field(name="Options", value=description, inline=False)

        message = await ctx.send(embed=embed)

        for emoji in option_emoji:
            await message.add_reaction(emoji)

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in option_emoji and reaction.message.id == message.id

        try:
            reaction, _ = await self.bot.wait_for('reaction_add', timeout=120.0, check=check)
            choice_index = option_emoji.index(str(reaction.emoji))
            choice = options[choice_index]
           
            await self.save_planet_choice(ctx.author.id, choice)
            await ctx.send(f"{ctx.author.mention}, you have chosen: {choice}")
            
        except asyncio.TimeoutError:
            await ctx.send(f"{ctx.author.mention}, you took too long to choose!")
            
        await self.send_intro_message(ctx)    
    
    async def save_planet_choice(self, user_id, choice):
        self.choices_collection.update_one(
            {"user_id": user_id},
            {"$set": {"planet.choice": choice}},  # Save planet choice to the correct field
            upsert=True
        )
        
    @commands.command()
    async def choosestartingWeapon(self, ctx):
        
        options = ["Sword", "Energy Pistol", "Knife", "Beam Bow"]
        embed = discord.Embed(title="Choose your character's starting weapon!", description="React with the correct emoji to make your choice.")
        option_emoji = "🗡️", "🔫", "🔪", "🏹"
        description = "\n".join([f"{emoji} {option}" for emoji, option in zip(option_emoji, options)])
        embed.add_field(name="Options", value=description, inline=False)

        message = await ctx.send(embed=embed)

        for emoji in option_emoji:
            await message.add_reaction(emoji)

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in option_emoji and reaction.message.id == message.id

        try:
            reaction, _ = await self.bot.wait_for('reaction_add', timeout=120.0, check=check)
            choice_index = option_emoji.index(str(reaction.emoji))
            choice = options[choice_index]

            await self.save_startingWeapon_choice(ctx.author.id, choice)
            await ctx.send(f"{ctx.author.mention}, you have chosen: {choice}")
        except asyncio.TimeoutError:
            await ctx.send(f"{ctx.author.mention}, you took too long to choose!")
            
        await self.resetmessage(ctx)
        await self.charstats(ctx)
        
    async def save_startingWeapon_choice(self, user_id, choice):
        self.choices_collection.update_one(
            {"user_id": user_id},
            {"$set": {"startingWeapon.choice": choice}},  # Save planet choice to the correct field
            upsert=True
        )
      
    @commands.command()
    async def assignStats(self, ctx):
        """Assign stats based on race choice."""
        user_id = ctx.author.id

        # Fetch the user's race choice from `choices_collection`
        user_choice = self.choices_collection.find_one({"user_id": user_id})

        if not user_choice or "race" not in user_choice:
            await ctx.send(f"{ctx.author.mention}, you haven't created a character yet. Use the `!start` command.")
            return

        # Define race stats (make sure this is defined before using it)
        race_stats = {
            "terrans": {"health": 100, "max_health": 100, "attack": 20, "accuracy": 85, "defense": 2, "abilities": []},
            "feralous": {"health": 150, "max_health": 150, "attack": 10, "accuracy": 100, "defense": 5,"abilities": []},
            "scarvous": {"health": 75, "max_health": 75, "attack": 20, "accuracy": 85, "defense": 4,"abilities": []},
            "pharquels": {"health": 75,"max_health": 75, "attack": 20, "accuracy": 85, "defense": 3,"abilities": []},
            "bar'phons": {"health": 125,"max_health": 125, "attack": 15, "accuracy": 70, "defense": 3,"abilities": []},
            "robartons": {"health": 125, "max_health": 125, "attack": 20, "accuracy": 80, "defense": 3,"abilities": []},
        }

        # Get the race choice (normalized to lowercase)
        race_choice = user_choice["race"]["choice"].lower()

        if race_choice not in race_stats:
            await ctx.send(f"{ctx.author.mention}, invalid race choice detected. Please reset your character.")
            return

        # Get stats for the chosen race
        stats = race_stats[race_choice]

        # Save stats to `player_stats` collection
        self.stats_collection.update_one(
            {"user_id": user_id},  # Find by user_id
            {
                "$set": {
                    "user_id": user_id,
                    "health": stats["health"],
                    "max_health": stats["max_health"],
                    "attack": stats["attack"],
                    "accuracy": stats["accuracy"],
                    "defense": stats["defense"],
                    "abilities": stats["abilities"]  # Save abilities as well
                }
            },
            upsert=True  # Insert a new document if one doesn't already exist
        )

        # Confirmation message
        await ctx.send(
            f"Stats for your character have been assigned and saved:\n"
            f"**Health:** {stats['health']}\n"
            f"**Attack:** {stats['attack']}\n"
            f"**Accuracy:** {stats['accuracy']}\n"
            f"**Defense:** {stats['defense']}"
        )

        await asyncio.sleep(1)
        await ctx.send("Type `!charstats` anytime to view your stats!")
        await self.send_intro_message(ctx)
    @commands.command()
    async def assign_stats(self, ctx):
        """Assign stats to the character and trigger the intro message automatically."""
        # Your existing logic for assigning stats goes here, like:
        stats = await self.get_stats_from_user(ctx)
        # Assume the stats are now assigned, and you have the information you need.

        # After stats are assigned, automatically trigger the intro message.
        await self.send_intro_message(ctx)

    async def send_intro_message(self, ctx):
        """Send the introductory message in parts, allowing navigation with forward and back arrows."""
        user_data = self.choices_collection.find_one({"user_id": ctx.author.id})
        planet_choice = user_data.get("planet", {}).get("choice", "Unknown Planet")

        intro_parts = [
            {
                "title": f"🌟 Your Journey Begins, {ctx.author.name}! 🌟",
                "description": ("The stars above could be yours, but the question is, what path will you take? "
                                "Will you create chaos out of order or order out of chaos? Will you be a beacon of light or summon the darkness? "
                                "Your path lays before you!"),
                "image": "https://i.imgur.com/TphqgoX.png"
            },
            {
                "title": "The Crash",
                "description": (f"You open your eyes, your nose filling with unknown horrible smells, melting Aetherium. "
                                "You leap to your feet in your pajamas and poke your head into the hallway, seeing the ship on fire.\n\n"
                                "You run to the cockpit to see your parents trying to pilot the ship, remembering how life used to be."),
                "image": "https://i.imgur.com/FM47PGG.png"
            },
            {
                "title": "The Decision to Flee",
                "description": (f"You've overheard the story many times, but at the time, didn't know what it meant. "
                                "You still don't really, but you recite it to yourself daily.\n\n"
                                f"**{ctx.author.name}'s parents** grew up in **{planet_choice}**, the children of prominent merchants, "
                                "taking over the family businesses across the Solar System when they came of age.\n\n"
                                "Unwilling to deal with the shady corporations operating in the shadows, your family's profits dragged, but this was not enough.\n\n"
                                f"To escape corruption, both families made secret plans to relocate their businesses back to their home planet, **{planet_choice}**."),
                "image": "https://i.imgur.com/fimUIGU.png"
            },
            {
                "title": "The Daring Escape",
                "description": (f"Your parents, pregnant with **{ctx.author.name}**, could not deal with the stresses of Hyper Space Travel, "
                                f"so they waited for their new baby, **{ctx.author.name}**, to be born.\n\n"
                                f"**{ctx.author.name}'s parents** waited and waited for a message from **{ctx.author.name}'s grandparents**, "
                                "trying to make their saved credits last.\n\n"
                                "But the day came when their savings would not last any longer, and they needed to make a difficult decision. "
                                "Stay and wait, in constant terror of being attacked by their enemies, or go and risk having no one to receive them.\n\n"
                                "With no good decisions in sight, your parents decided to pack their things onto their family ship, the **Chrono Scout**."),
                "image": "https://i.imgur.com/kWhSKZ5.png"
            },
            {
                "title": "Disaster Strikes",
                "description": (f"They felt nervous, startled every time their proximity alarm went off, but the alarms were picking up on large space debris, "
                                "likely the **Solar Syndicate**, as they have become more ruthless lately, disrupting trade throughout the **Solar System**.\n\n"
                                f"But your parents sigh in relief each time sensors show that there are no foes in sight. They gained confidence as **{planet_choice}** came closer and closer.\n\n"
                                f"Over the intercom, your parents hear the familiar accent of the citizens of **{planet_choice}**. They smile, hug, and cheer as they align their approach with **{planet_choice}**'s Planetary Travel Service.\n\n"
                                "They feel a sense of relief and joy, but suddenly, the Chrono Scout begins to shake erratically, and the screens go black. \n\n"
                                "The traffic correspondent's voice fades to static, and they hear a demonic laugh over the intercom."),
                "image": "https://i.imgur.com/3Sun2ye.png"
            },
            {
                "title": "Time to Flee",
                "description": (f"The **Chrono Scout** starts flying uncontrollably, catching fire as the heating shield melts away. \n\n"
                                f"Your parents scream, saying, 'We need to save **{ctx.author.name}**!'\n\n"
                                f"They grab **{ctx.author.name}**, carrying you through the chaos as the **Chrono Scout** dangerously approaches the planet.\n\n"
                                f"They hurry to the 3 single-occupant escape pods, only to find that the other two were launched into the atmosphere.\n\n"
                                f"**{ctx.author.name}'s Parents** look at each other, and then back at their precious **{ctx.author.name}**.\n\n"
                                f"Covered in tears, they thrust a crying **{ctx.author.name}** into the escape pod, close the hatch, place a hand on the window, and slam down the eject lever, sealing their fate.\n\n"
                                f"**{ctx.author.name}** looks out the window, watching the fiery ball that was the **Chrono Scout**, quickly going out of sight."),
                "image": "https://i.imgur.com/6f3ZXwF.png"
            },
            {
                "title": "Barely Escaped Death",
                "description":  ("You wake up, the pod opened, looking up at a group of strangers, some scary, some kind, scared.\n\n Unsure of your surroundings, where you are, who these people may be, wanting to run away, anywhere away from here. \n\nThe sky goes dark as a rough hood slides quickly over your furrowed brow. The last thing you hear is the sawing and clanging of the escape pod being torn apart, looking for anything of value. \n\n You hear a grizzled voice, 'What do we do with the kid?'"
                                "'Its just a kid!', another yells. A soft voice slowly rises up among the chorus of competing voices, causing them to quickly fade away.\n\n "
                                "There's an orphanage not too far away, drop him off and kick the door after dark, if he's lucky they'll make sure he gets some food tonight. He will die if you leave him here."
                                "Just then you feel the rope tighten around your wrists, forcing them together\n\n"
                                "You feel being picked up and carried over a shoulder, the rhythm slowly rocking you to sleep\n\n"),

                "image": "https://i.imgur.com/XDwChl7.png"
            },
            {
                "title": "New Home",
                "description": "You wake up feeling pain striking up and down your side, realizing you are now laying on hard sandstone steps. You hear adult feet scurrying away, and someone approaching on the other side of a door.\n\n" 
                "The door whines as it opens and you hear a voice you almost mistake to be your Mother's. \n\n ‘**Someone**, get help quick! We have another mouth to feed.’\n\n" 
                "The light coming from the doorway slowly getting brighter as the hood is pulled quickly over your head, adjusting to it seeing a dark but kind face with the moon shining brightly behind them. \n\nYou feel a man's hands on your wrists as he cuts the rope away. You hear 'Come in dear.' as they gesture into a house with a sand floor, simple wood chair, and nearly bare cupboards.\n\n You immediately think about dessert last night with your parents. You begin to cry.",
                
                "image": "https://i.imgur.com/MWky87F.png"
            },
            {
                "title": "Second Childhood",
                "description":  "The years pass, you become stronger, as strong as you can with the limited food the orphanage may provide.\n\n"
            "You become tough, almost too tough, hardened by your surroundings."
            "You become confident, feeling like you can take on any challenge."
            "You huddle around the table, ready to celebrate your 15th birthday, feeling eager for adulthood.",

                "image": "https://i.imgur.com/N6BDfrG.png"
            },
            {
                "title": "Adulthood Begins",
                "description": "There was a knock on the door, once opened, entering comes a group of scary looking men, that *all* orphans have grown to fear. \n\nIt is the **Quartermaster** and his minions, well known for his cruelty in taking on indentured servants, praying on the abandoned for free labor. \n\nHe says with a menacing grin, 'Point him out to me, you **owe** me another'.\n\n"
            "The kind woman you have known all your life, face pale as white sand slowly lifts her finger and traces it on you. You get up to flee but feel a hand on your shoulder stopping you, another hand on your throat and a fist strongly hitting you in your stomach. \n\nYour eyes slowly closing, the last thing you remember is the sound of your heels dragging on sand as you are pulled away from the place you have called home for over a decade.",

                "image": "https://i.imgur.com/WgVgzXM.jpeg"
            },
            {
                "title": "Adulthood Begins",
                "description": "You wake with a shoulder gently waking you, 'Get up, if they find you sleeping, it won't go well for you'. \n\nYou feel yourself being pulled up to your feet. 'It's time to work'\n\n"
            "You have barely turned 15, but it seems that Adulthood has come early. \n\nThe next challenge has begun, you are filled with rage. Both at what has happened to you, but also the unending desire to find out what happened to your parents.\n\n"
            "Go forward adventurer, your quest to find your own path has just barely begun!",
                "image": "https://i.imgur.com/DSxgXv6.png"
            },
        ]

        # Create the initial embed
        embed = discord.Embed(title=intro_parts[0]["title"], description=intro_parts[0]["description"], color=discord.Color.blue())
        embed.set_image(url=intro_parts[0]["image"])
        message = await ctx.send(embed=embed)

        # Add initial reactions
        await message.add_reaction("➡️")
        
        current_index = 0  # Start at the first message

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["➡️", "⬅️", "✅"] and reaction.message.id == message.id

        while True:
            try:
                reaction, _ = await self.bot.wait_for('reaction_add', timeout=120.0, check=check)

                if str(reaction.emoji) == "➡️" and current_index < len(intro_parts) - 1:
                    current_index += 1
                elif str(reaction.emoji) == "⬅️" and current_index > 0:
                    current_index -= 1
                elif str(reaction.emoji) == "✅" and current_index == len(intro_parts) - 1:
                    await ctx.send(f"🌟 **Your journey begins now, press !info for more information, {ctx.author.name}!** 🌟")
                    break  # Exit the function

                # Update the embed instead of sending a new message
                embed = discord.Embed(title=intro_parts[current_index]["title"], 
                                    description=intro_parts[current_index]["description"], 
                                    color=discord.Color.blue())
                embed.set_image(url=intro_parts[current_index]["image"])
                await message.edit(embed=embed)

                # Remove only the user's reaction so they can click again
                await message.remove_reaction(reaction.emoji, ctx.author)

                # Clear all reactions and add the correct ones based on position
                await message.clear_reactions()
                if current_index > 0:
                    await message.add_reaction("⬅️")  # Back arrow only if not on first message
                if current_index < len(intro_parts) - 1:
                    await message.add_reaction("➡️")  # Forward arrow only if not on last message
                if current_index == len(intro_parts) - 1:
                    await message.add_reaction("✅")  # End function on last message
                    await self.charstats(ctx)
                    return
            except asyncio.TimeoutError:
                await ctx.send(f"{ctx.author.mention}, you took too long to respond. Please start over with `!start`.")
                
                return
            

    @commands.command()
    async def charstats(self, ctx):
        await asyncio.sleep(2)
        """Display the stats of the character."""
        user_choice = self.choices_collection.find_one({"user_id": ctx.author.id})

        if not user_choice or "race" not in user_choice:
            await ctx.send(f"{ctx.author.mention}, no character found! Please use the `!start` command to begin.")
            return

        race_choice = user_choice["race"]["choice"].lower()
        
        # Define race stats
        race_stats = {
            "terrans": {"health": 100, "max_health": 100, "attack": 20, "accuracy": 85, "defense": 2, "level": 1},
            "mammal alien": {"health": 150, "max_health": 150, "attack": 10, "accuracy": 100, "defense": 5, "level": 1},
            "reptile alien": {"health": 75, "max_health": 75, "attack": 20, "accuracy": 85, "defense": 4, "level": 1},
            "blue humanoid wizard": {"health": 75,"max_health": 75, "attack": 20, "accuracy": 85, "defense": 3, "level": 1},
            "shapeshifter": {"health": 125,"max_health": 125, "attack": 15, "accuracy": 70, "defense": 3, "level": 1},
            "robot race": {"health": 125, "max_health": 125, "attack": 20, "accuracy": 80, "defense": 3, "level": 1},
            }
        
        user_choice = self.choices_collection.find_one({"user_id": ctx.author.id})
        race_choice = user_choice["race"]["choice"].lower()
        if race_choice not in race_stats:
            await ctx.send(f"{ctx.author.mention}, invalid race choice detected. Please reset your character.")
            return
        stats = race_stats[race_choice]

    # Save stats to the Player.Stats collection
        user_id = ctx.author.id
        self.stats_collection.update_one(
            {"user_id": user_id},  # Filter by user ID
            {
                "$set": {
                    "user_id": user_id,
                    "race": race_choice,
                    "health": stats["health"],
                    "max_health": stats["max_health"],
                    "attack": stats["attack"],
                    "accuracy": stats["accuracy"],
                    "defense": stats["defense"],
                    "level": stats["level"]
               }
            },
        upsert=True,  # Insert if no document exists for this user
    )

        # Send stats to the user
        stats = race_stats[race_choice]
        await ctx.send(
            f"Stats for your character (**{race_choice.title()}**):\n"
            f"**Health:** {stats['health']}\n"
            f"**Attack:** {stats['attack']}\n"
            f"**Accuracy:** {stats['accuracy']}\n"
            f"**Defense:** {stats['defense']}"
        )
            # Correct way to call start_act1 from Act1 cog
        await call_cog_method(self.bot, "Act1_1", "start_act1_1", ctx)
        
    @commands.command()
    async def reset(self, ctx):
        """Reset the character creation."""
        print("Reset command invoked")
        user_id = ctx.author.id

        # Remove the user's data from all relevant collections
        self.collection.delete_one({"user_id": user_id})  # Delete from 'Start' collection
        self.choices_collection.delete_one({"user_id": user_id})  # Delete from 'Start.Choices' collection
        self.stats_collection.delete_one({"user_id": user_id})  # Delete from 'Player.Stats' collection

        await ctx.send(f"{ctx.author.mention}, your character has been successfully reset. You can now start over using the `!start` command.")
        await self.resetmessage(ctx)

    @commands.command()
    async def resetmessage(self, ctx):
        """Inform users about resetting their character."""
        await asyncio.sleep(4)
        await ctx.send(
            "If you would like to reset your choices, enter `!reset` to restart the character creation process. Good luck as you battle your way to the top!"
        )
        

        
        
