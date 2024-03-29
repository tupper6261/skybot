import discord
from discord.ext import commands
from discord.ui import Button, View, Select
import psycopg2
import os
from dotenv import load_dotenv
import asyncio
from datetime import datetime, time as datetimetime
import pytz
import random
import time

load_dotenv()

DATABASE_TOKEN = os.getenv('DATABASE_TOKEN')
BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Set up the bot with the proper intents to read message content and reactions
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Adjust the reaction threshold here
REACTION_THRESHOLD = 5
REACTION_EMOJI = "🛰️"

class OptInView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Opt-In", style=discord.ButtonStyle.green)
    async def opt_in_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        user = interaction.user
        #See if the user is in the anniversary list
        conn = psycopg2.connect(DATABASE_TOKEN, sslmode='require')
        cur = conn.cursor()
        cur.execute("select * from matchmaking where discord_user_id = {}".format(user.id))
        result = cur.fetchall()
        #If (s)he isn't in the list, add them and opt them in
        if result == []:
            cur.execute("insert into matchmaking (discord_user_id, opted_in, discord_username) values ({0}, true, '{1}')".format(user.id, user.name))
            await interaction.response.send_message(content=f"{user.mention}, you have been added to the matching service. Matchmaking takes place on Mondays.", ephemeral=True)
        else:
            #If the user is already opted in
            if result[0][1]:
                await interaction.response.send_message(content=f"{user.mention}, you are already opted-in.", ephemeral=True)
            else:
                cur.execute("update matchmaking set opted_in = true where discord_user_id = {}".format(user.id))
                await interaction.response.send_message(content=f"{user.mention}, you have been added to the matching service. Matchmaking takes place on Mondays.", ephemeral=True)
        cur.close()
        conn.commit()
        conn.close()

    @discord.ui.button(label="Opt-Out", style=discord.ButtonStyle.red)
    async def opt_out_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        user = interaction.user
        #See if the user is in the anniversary list
        conn = psycopg2.connect(DATABASE_TOKEN, sslmode='require')
        cur = conn.cursor()
        cur.execute("select * from matchmaking where discord_user_id = {}".format(user.id))
        result = cur.fetchall()
        #If (s)he isn't in the list, nothing needs to be done
        if result == []:
            await interaction.response.send_message(content=f"{user.mention}, you are already opted-out.", ephemeral=True)
        else:
            #If the user is currently opted in
            if result[0][1]:
                cur.execute("update matchmaking set opted_in = false where discord_user_id = {}".format(user.id))
                await interaction.response.send_message(content=f"{user.mention}, you have opted-out from the matching service.", ephemeral=True)
            else:
                await interaction.response.send_message(content=f"{user.mention}, you are already opted-out.", ephemeral=True)
        cur.close()
        conn.commit()
        conn.close()
            

@bot.event
async def on_ready():
    guild_id = 972905096230891540  # Replace with your guild ID
    channel_id = 1121094795792756847  # Replace with your channel ID where the opt-in message will be sent

    guild = bot.get_guild(guild_id)
    channel = guild.get_channel(channel_id)

    message = discord.utils.get(await channel.history(limit=10).flatten(), author=bot.user)
    if not message:
        message = await channel.send("Hello! Welcome to the Skylab Meetups channel.\n\nEach Monday, you'll be paired with another Skylabber so you can connect, network, plan a Halo gaming session; whatever! It's an opportunity to meet other Web3 founders.\n\nAnd on each Monday, if the bot notices you didn't post in your meetup channel during the previous week, you'll be automatically opted-out from the service. You can opt back in at any point, but we want to discourage regular ghosting! \n\nClick the buttons below to opt-in or opt-out:")
    else:
        await message.edit(content="Hello! Welcome to the Skylab Meetups channel.\n\nEach Monday, you'll be paired with another Skylabber so you can connect, network, plan a Halo gaming session; whatever! It's an opportunity to meet other Web3 founders.\n\nAnd on each Monday, if the bot notices you didn't post in your meetup channel during the previous week, you'll be automatically opted-out from the service. You can opt back in at any point, but we want to discourage regular ghosting! \n\nClick the buttons below to opt-in or opt-out:")

    view = OptInView()
    await message.edit(view=view)
    while True:
        await check_anniversaries()
        await make_matches()
        #sleep for 6 hours
        await asyncio.sleep(21600)

@bot.event
async def on_raw_reaction_add(ctx):
    # Check if the reaction is the 🛰️ emoji and if the count is equal to or greater than the threshold
    if ctx.emoji.name == REACTION_EMOJI and ctx.member != bot.user:
        channel = bot.get_channel(ctx.channel_id)
        message = await channel.fetch_message(ctx.message_id)
        # Find the #highlights channel
        highlights_channel = discord.utils.get(message.guild.channels, id=974732712411807754)

        #we don't want to highlight a highlight
        if ctx.channel_id == highlights_channel.id:
            return

        if message.reactions:
            for reaction in message.reactions:
                if reaction.emoji == REACTION_EMOJI and reaction.count >= REACTION_THRESHOLD:
                    #See if the message has already been highlighted. 
                    conn = psycopg2.connect(DATABASE_TOKEN, sslmode='require')
                    cur = conn.cursor()
                    cur.execute("select * from highlightmessages where message_id = {}".format(ctx.message_id))
                    results = cur.fetchall()

                    if results == []:
                        #add the message to the hightlighted messages list
                        cur.execute("insert into highlightmessages (message_id) values ({})".format(ctx.message_id))

                        # Post the message content, author, and link to the original message in the #highlights channel
                        embed = discord.Embed(
                            description=message.content,
                            color=discord.Color.blue()
                        )
                        embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar)
                        embed.add_field(name="Original Post", value=f"[Jump to message]({message.jump_url})")
                        await highlights_channel.send(embed=embed)

                    cur.close()
                    conn.commit()
                    conn.close()

    # Check if the reaction is the ✅ emoji and if the count is equal to or greater than the threshold
    if ctx.emoji.name == "✅" and ctx.member != bot.user and ctx.message_id == 1122894424070959144:
        guild = await bot.fetch_guild(ctx.guild_id)
        tester_role = guild.get_role(1122894492282912829)
        user = ctx.member
        await user.add_roles(tester_role)
        #See if the user is in the matchmaking list
        conn = psycopg2.connect(DATABASE_TOKEN, sslmode='require')
        cur = conn.cursor()
        cur.execute("select * from matchmaking where discord_user_id = {}".format(user.id))
        result = cur.fetchall()
        #If (s)he isn't in the list, add them and opt them in
        if result == []:
            cur.execute("insert into matchmaking (discord_user_id, opted_in) values ({}, true)".format(user.id))
        else:
            #If the user isn't already opted in
            if result[0][1] == False:
                cur.execute("update matchmaking set opted_in = true where discord_user_id = {}".format(user.id))
        cur.close()
        conn.commit()
        conn.close()


#Checks the anniversaries in the user list and sends a happy anniversary message
async def check_anniversaries():
    now = datetime.now(pytz.timezone('US/Eastern'))
    #Get the Skylab guild
    guild = bot.get_guild(972905096230891540)
    #Get the general channel
    postChannel = discord.utils.get(guild.channels, id = 972905096230891543)

    #Check each member to see if it's their anniversary
    async for member in guild.fetch_members():
        join_date = member.joined_at                                                                            
        years = now.year - join_date.year
        #We'll use this later
        posted = False

        #If the user has been here at least a year and today is his anniversary
        if years > 0 and ((join_date.day == now.day and join_date.month == now.month) or (join_date.day == 29 and join_date.month == 2 and now.month == 3 and now.month == 1)) and not member.bot:
            #See if the user is in the anniversary list
            conn = psycopg2.connect(DATABASE_TOKEN, sslmode='require')
            cur = conn.cursor()
            cur.execute("select * from skylabanniversaries where discord_user_id = {}".format(member.id))
            result = cur.fetchall()
            #If (s)he isn't in the list, add them and post a message
            if result == []:
                cur.execute("insert into skylabanniversaries (discord_user_id, anniversary) values ({0}, {1})".format(member.id, years))
                conn.commit()
                await postChannel.send(f"🎉 Happy {years} year(s) Skylab anniversary, {member.mention}! 🎉")
                posted = True
            #If (s)he is in the list, see if they've already gotten a message this year, and send a message if not
            else:
                if result[0][1] != years:
                    cur.execute("update skylabanniversaries set anniversary = {0}where discord_user_id = {1}".format(years, member.id))
                    conn.commit()
                    await postChannel.send(f"🎉 Happy {years} year(s) Skylab anniversary, {member.mention}! 🎉")
                    posted = True
            cur.close()
            conn.commit()
            conn.close()
            #Pauses for a bit so that the bot doesn't flood the channel :)
            if posted == True:
                await asyncio.sleep(600)  # Sleep for 10 minutes (600 seconds)

# Clear all existing channels from the specified category except for the opt-in/opt-out and stats channels
async def clear_existing_channels(category_id):
    guild_id = 972905096230891540  # Replace with your guild ID
    guild = bot.get_guild(guild_id)

    category = guild.get_channel(category_id)
    opt_channel_id = 1121094795792756847  #ID of the opt-in/opt-out channel
    stat_channel_id = 1124068878369181806 #ID of the stats channel

    for channel in category.channels:
        if channel.id != opt_channel_id and channel.id != stat_channel_id:
            await channel.delete()

# Make matches
async def make_matches():
    guild_id = 972905096230891540  # Replace with your guild ID
    guild = bot.get_guild(guild_id)
    category_id = 1121094611436314634  # Replace with the ID of the Meetups category
    category = guild.get_channel(category_id)
    opt_channel_id = 1121094795792756847
    stat_channel_id = 1124068878369181806 #ID of the stats channel

    conn = psycopg2.connect(DATABASE_TOKEN, sslmode='require')
    cur = conn.cursor()

    #Check when the next scheduled meetup is
    command = "select value from globalvariables where name = 'skylab_next_meetup'"
    cur.execute(command)
    next_meetup = int(cur.fetchall()[0][0])
    #If we're past that time:
    if int(time.time()) >= next_meetup:

        #Go through the channels in the category and find out who ghosted
        cur.execute("SELECT * FROM matchmaking_channels")
        results = cur.fetchall()

        successfulMeetups = []

        for row in results:
            if row[1] not in successfulMeetups:
                successfulMeetups.append(row[1])

        numTotalMeetups = len(successfulMeetups)

        for row in results:
            ghosted = True
            discord_user_id = row[0]
            channel_id = row[1]

            # Get the channel object
            channel = guild.get_channel(channel_id)

            # Retrieve the message history of the channel
            messages = await channel.history().flatten()

            # Iterate through the messages and check the author
            for message in messages:
                if message.author.id == discord_user_id:
                    ghosted = False
                    break  # No need to continue iterating if the user's message is found

            cur.execute("select * from matchmaking where discord_user_id = {0}".format(discord_user_id))
            result = cur.fetchall()[0]
            if ghosted:
                cur.execute("update matchmaking set num_ghosts = {0} where discord_user_id = {1}".format(result[3]+1, discord_user_id))
                cur.execute("update matchmaking set opted_in = false where discord_user_id = {0}".format(discord_user_id))
                if channel_id in successfulMeetups:
                    successfulMeetups.remove(channel_id)
                user = guild.get_member(discord_user_id)
                if user:
                    # Notify the user about being opted out
                    opt_out_message = f"{user.mention}, it seems like you didn't post a message in your meetup channel during this last session. I've gone ahead and opted you out from meetups for now. Feel free to head to <#{opt_channel_id}> and opt back in if you'd like!"
                    await guild.get_channel(stat_channel_id).send(opt_out_message)
            else:
                cur.execute("update matchmaking set num_chats = {0} where discord_user_id = {1}".format(result[4]+1, discord_user_id))
            conn.commit()
        
        numSuccessfulMeetups = len(successfulMeetups)
        # Notify the stats channel about the successful matches count
        match_summary_message = f"Looks like {numSuccessfulMeetups} successful meetups were made out of {numTotalMeetups} total matches during this past session. Keep it up!"
        await guild.get_channel(stat_channel_id).send(match_summary_message)

        #Clear the matchmaking_channels table
        cur.execute("truncate matchmaking_channels")
        conn.commit()

        # Clear existing channels from the category except for the opt-in/opt-out channel
        await clear_existing_channels(category_id)
        
        cur.execute("SELECT discord_user_id FROM matchmaking WHERE opted_in = true")
        result = cur.fetchall()

        # Collect discord_user_id from the result directly
        users = [i[0] for i in result]  

        while len(users) >= 2:
            # If there are an odd number of opted-in users, we'll make a threesome
            if len(users) % 2 == 1:
                matchUsers = random.sample(users, 3)
            else:
                matchUsers = random.sample(users, 2)
            users = [user for user in users if user not in matchUsers]
            newChannel = await create_private_channel(matchUsers, category_id)
            for user in matchUsers:
                cur.execute("insert into matchmaking_channels (discord_user_id, channel_id) values ({0}, {1})".format(user, newChannel.id))
                conn.commit()

        #Update the next meetup time (add a week)
        next_meetup = str(next_meetup + 604800)
        command = "update globalvariables set value = '{0}' where name = 'skylab_next_meetup'".format(next_meetup)
        cur.execute(command)
        conn.commit()

    cur.close()
    conn.commit()
    conn.close()

async def create_private_channel(user_ids, category_id):
    guild_id = 972905096230891540
    guild = bot.get_guild(guild_id)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        guild.me: discord.PermissionOverwrite(read_messages=True)
    }

    usernames = []
    userMentions = []
    for user_id in user_ids:
        user = guild.get_member(user_id)
        if user:
            overwrites[user] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            usernames.append(user.name)
            userMentions.append(user.mention)

    channel_name = "-".join(usernames)  # Concatenate usernames with hyphens
    channel = await guild.create_text_channel(
        name=channel_name,
        category=guild.get_channel(category_id),
        overwrites=overwrites
    )

    # Delay before setting permissions
    await asyncio.sleep(1)

    notification_message = f"Hello {' and '.join(userMentions)}! This private channel has been created for your meetup. Enjoy your chat!\n\nPlease note that this channel will be deleted when matches are made again next week."
    await channel.send(content=notification_message)

    # You can also return the created channel if needed
    return channel

# Slash command for testing make_matches
@bot.slash_command(guild_ids=[972905096230891540], description = "Make matches")
async def test_make_matches(ctx):
    await ctx.respond("making matches", ephemeral = True)

    await make_matches()

bot.run(BOT_TOKEN)
