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
bot = commands.Bot(command_prefix="+", intents=intents)

class OptInView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Opt-In", style=discord.ButtonStyle.green)
    async def opt_in_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild
        #See if the user is in the matchmaking list
        conn = psycopg2.connect(DATABASE_TOKEN, sslmode='require')
        cur = conn.cursor()
        cur.execute("select * from skylab_matchmaking where discord_user_id = {0} and guild_id = {1}".format(user.id, guild.id))
        result = cur.fetchall()
        #If (s)he isn't in the list, add them and opt them in
        if result == []:
            cur.execute("insert into skylab_matchmaking (discord_user_id, opted_in, discord_username, guild_id) values ({0}, true, '{1}')".format(user.id, user.name, guild.id))
            await interaction.response.send_message(content=f"{user.mention}, you have been added to the matching service. Matchmaking takes place on Mondays.", ephemeral=True)
        else:
            #If the user is already opted in
            if result[0][1]:
                await interaction.response.send_message(content=f"{user.mention}, you are already opted-in.", ephemeral=True)
            else:
                cur.execute("update skylab_matchmaking set opted_in = true where discord_user_id = {}".format(user.id))
                await interaction.response.send_message(content=f"{user.mention}, you have been added to the matching service. Matchmaking takes place on Mondays.", ephemeral=True)
        cur.close()
        conn.commit()
        conn.close()

    @discord.ui.button(label="Opt-Out", style=discord.ButtonStyle.red)
    async def opt_out_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild
        #See if the user is in the matchmaking list
        conn = psycopg2.connect(DATABASE_TOKEN, sslmode='require')
        cur = conn.cursor()
        cur.execute("select * from skylab_matchmaking where discord_user_id = {0} and guild_id = {1}".format(user.id, guild.id))
        result = cur.fetchall()
        #If (s)he isn't in the list, nothing needs to be done
        if result == []:
            await interaction.response.send_message(content=f"{user.mention}, you are already opted-out.", ephemeral=True)
        else:
            #If the user is currently opted in
            if result[0][1]:
                cur.execute("update skylab_matchmaking set opted_in = false where discord_user_id = {}".format(user.id))
                await interaction.response.send_message(content=f"{user.mention}, you have opted-out from the matching service.", ephemeral=True)
            else:
                await interaction.response.send_message(content=f"{user.mention}, you are already opted-out.", ephemeral=True)
        cur.close()
        conn.commit()
        conn.close()
            
@bot.event
async def on_ready():
    #We need to make the opt-in/out buttons live within each server
    for guild in bot.guilds:
        conn = psycopg2.connect(DATABASE_TOKEN, sslmode='require')
        cur = conn.cursor()
        cur.execute("select * from skylab_matchmaking_guilds where guild_id = {}".format(guild.id))
        result = cur.fetchall()
        cur.close()
        conn.close()

        if result != []:
            opt_channel_id = result[0][1]

            channel = guild.get_channel(opt_channel_id)

            message = discord.utils.get(await channel.history(limit=10).flatten(), author=bot.user)
            if not message:
                message = await channel.send("Hello! Welcome to the Skylab Meetups channel.\n\nEach Monday, you'll be paired with another server member so you can connect, network, plan a Halo gaming session; whatever! It's an opportunity to meet other community members.\n\nAnd on each Monday, if the bot notices you didn't post in your meetup channel during the previous week, you'll be automatically opted-out from the service. You can opt back in at any point, but we want to discourage regular ghosting! \n\nClick the buttons below to opt-in or opt-out:")
            else:
                await message.edit(content="Hello! Welcome to the Skylab Meetups channel.\n\nEach Monday, you'll be paired with another server member so you can connect, network, plan a Halo gaming session; whatever! It's an opportunity to meet other community members.\n\nAnd on each Monday, if the bot notices you didn't post in your meetup channel during the previous week, you'll be automatically opted-out from the service. You can opt back in at any point, but we want to discourage regular ghosting! \n\nClick the buttons below to opt-in or opt-out:")

            view = OptInView()
            await message.edit(view=view)

    #Loop through the guilds the bot is in and make matches when necessary! 
    while True:
        for guild in bot.guilds:
            await make_matches(guild)
        #Wait 6 hours before checking again
        await asyncio.sleep(3600)

#When the bot joins the guild, we're gonna see if it's joined before and it's already set up or if we need to set it up 
@bot.event
async def on_guild_join(guild):
    #See if the guild is already in the database
    conn = psycopg2.connect(DATABASE_TOKEN, sslmode='require')
    cur = conn.cursor()
    cur.execute("select * from skylab_matchmaking_guilds where guild_id = {}".format(guild.id))
    result = cur.fetchall()
    cur.close()
    conn.close()
    #If it isn't in the list, we need to set up the guild
    if result == []:
        await setup_guild(guild)
    #If it is in the list, we need to see if the channels we set up previously still exist
    else:
        refresh = False
        opt_channel_id = result[0][1]
        stats_channel_id = result[0][2]
        category_id = result[0][3]

        opt_channel = guild.get_channel(opt_channel_id)
        stats_channel = guild.get_channel(stats_channel_id)
        category = guild.get_channel(category_id)

        if category == None:
            refresh = True
            category = await guild.create_category("Meetups")
        if opt_channel == None:
            refresh = True
            opt_channel = await guild.create_text_channel("skylab-meetups", category = category)
            message = await opt_channel.send("Hello! Welcome to the Skylab Meetups channel.\n\nEach Monday, you'll be paired with another server member so you can connect, network, plan a Halo gaming session; whatever! It's an opportunity to meet other community members.\n\nAnd on each Monday, if the bot notices you didn't post in your meetup channel during the previous week, you'll be automatically opted-out from the service. You can opt back in at any point, but we want to discourage regular ghosting! \n\nClick the buttons below to opt-in or opt-out:")
            view = OptInView()
            await message.edit(view=view)
        else:
            await opt_channel.edit(category = category)
        if stats_channel == None:
            refresh = True
            stats_channel = await guild.create_text_channel("meetups-stats", category = category)
        else:
            await stats_channel.edit(category = category)

        #If anything had to be updated, we're just gonna reload everything just to be safe. Otherwise, we'll assume we can pick up where we left off
        if refresh:
            #The next meetup will be recalculated
            next_meetup = calculate_next_meetup()

            #Update the database 
            conn = psycopg2.connect(DATABASE_TOKEN, sslmode='require')
            cur = conn.cursor()
            cur.execute("UPDATE skylab_matchmaking_guilds SET opt_in_channel_id = {0}, stats_channel_id = {1}, category_id = {2}, next_meetup = {3} WHERE guild_id = {4}".format(opt_channel.id, stats_channel.id, category.id, next_meetup, guild.id))
            conn.commit()

            #Then we're also going to clear out any existing matchmaking channels to make sure there's no confusion
            cur.execute("DELETE FROM skylab_matchmaking_channels WHERE guild_id = {0}".format(guild.id))
            conn.commit()
            await clear_existing_channels(guild)

            #We're also going to opt-out all users in this guild to create a fresh start
            cur.execute("UPDATE skylab_matchmaking SET opted_in = FALSE WHERE guild_id = {0}".format(guild.id))
            conn.commit()

            cur.close()
            conn.commit()
            conn.close()
    return
    
#this function calculates the next meetup time
async def calculate_next_meetup():
    current_time = int(time.time())
    next_meetup = 1694440800
    #we find the timestamp of the next meetup by starting with September 11, 2023 and adding 7 days until we get to the first monday at 10am that is in the future as of the time the bot is added to the server
    #Why september 11, 2023? Cuz that's the current next meetup as of the time of this writing :)
    while next_meetup < current_time:
        next_meetup += 604800
    return next_meetup

#this function sets up the channels that the bot will use
async def setup_guild(guild):
    category = await guild.create_category("Meetups")
    opt_channel = await guild.create_text_channel("skylab-meetups", category = category)
    stats_channel = await guild.create_text_channel("meetups-stats", category = category)

    message = await opt_channel.send("Hello! Welcome to the Skylab Meetups channel.\n\nEach Monday, you'll be paired with another server member so you can connect, network, plan a Halo gaming session; whatever! It's an opportunity to meet other community members.\n\nAnd on each Monday, if the bot notices you didn't post in your meetup channel during the previous week, you'll be automatically opted-out from the service. You can opt back in at any point, but we want to discourage regular ghosting! \n\nClick the buttons below to opt-in or opt-out:")
    view = OptInView()
    await message.edit(view=view)

    next_meetup = calculate_next_meetup()
    #add all the channels and meetup time to the database
    conn = psycopg2.connect(DATABASE_TOKEN, sslmode='require')
    cur = conn.cursor()
    cur.execute("insert into skylab_matchmaking_guilds (guild_id, opt_in_channel_id, stats_channel_id, category_id, next_meetup) values ({0}, {1}, {2}, {3}, {4})".format(guild.id, opt_channel.id, stats_channel.id, category.id, next_meetup))
    cur.close()
    conn.commit()
    conn.close()
    return

# Clear all existing channels from the specified category except for the opt-in/opt-out and stats channels
async def clear_existing_channels(guild):
    conn = psycopg2.connect(DATABASE_TOKEN, sslmode='require')
    cur = conn.cursor()
    cur.execute("select * from skylab_matchmaking_guilds where guild_id = {}".format(guild.id))
    result = cur.fetchall()
    cur.close()
    conn.close()

    opt_channel_id = result[0][1]
    stats_channel_id = result[0][2]
    category_id = result[0][3]

    category = guild.get_channel(category_id)

    for channel in category.channels:
        if channel.id != opt_channel_id and channel.id != stats_channel_id:
            await channel.delete()

# Make matches
async def make_matches(guild):
    guild_id = guild.id

    conn = psycopg2.connect(DATABASE_TOKEN, sslmode='require')
    cur = conn.cursor()
    cur.execute("select * from skylab_matchmaking_guilds where guild_id = {}".format(guild.id))
    result = cur.fetchall()

    opt_channel_id = result[0][1]
    stat_channel_id = result[0][2]
    category_id = result[0][3]

    category = guild.get_channel(category_id)
    opt_channel = guild.get_channel(opt_channel_id)
    stat_channel = guild.get_channel(stat_channel_id)

    #We're gonna make sure that the channels/category still exist like we think they do, and if not, we'll recreate/adjust them
    if category == None:
        category = await guild.create_category("Meetups")
    if opt_channel == None:
        opt_channel = await guild.create_text_channel("skylab-meetups", category = category)
        message = await opt_channel.send("Hello! Welcome to the Skylab Meetups channel.\n\nEach Monday, you'll be paired with another server member so you can connect, network, plan a Halo gaming session; whatever! It's an opportunity to meet other community members.\n\nAnd on each Monday, if the bot notices you didn't post in your meetup channel during the previous week, you'll be automatically opted-out from the service. You can opt back in at any point, but we want to discourage regular ghosting! \n\nClick the buttons below to opt-in or opt-out:")
        view = OptInView()
        await message.edit(view=view)
    else:
        await opt_channel.edit(category = category)
    if stats_channel == None:
        stats_channel = await guild.create_text_channel("meetups-stats", category = category)
    else:
        await stats_channel.edit(category = category)

    #Check when the next scheduled meetup is
    cur.execute("select next_meetup from skylab_matchmaking_guilds where guild_id = {0}}".format(guild_id))
    next_meetup = int(cur.fetchall()[0][0])
    #If we're past that time:
    if int(time.time()) >= next_meetup:

        #Go through the channels in the category and find out who ghosted
        cur.execute("SELECT * FROM skylab_matchmaking_channels where guild_id = {0}".format(guild_id))
        results = cur.fetchall()

        successfulMeetups = []

        for row in results:
            if row[1] not in successfulMeetups:
                successfulMeetups.append(row[1])

        numTotalMeetups = len(successfulMeetups)

        for row in results:
            #we go through all the channels in the 
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

            cur.execute("select * from skylab_matchmaking where discord_user_id = {0} and guild_id = {1}".format(discord_user_id, guild_id))
            result = cur.fetchall()[0]
            if ghosted:
                cur.execute("update matchmaking set num_ghosts = {0}, opted_in = false where discord_user_id = {1} and guild_id = {2}".format(result[3]+1, discord_user_id, guild_id))
                conn.commit()
                if channel_id in successfulMeetups:
                    successfulMeetups.remove(channel_id)
                user = guild.get_member(discord_user_id)
                if user:
                    # Notify the user about being opted out
                    opt_out_message = f"{user.mention}, it seems like you didn't post a message in your meetup channel during this last session. I've gone ahead and opted you out from meetups for now. Feel free to head to <#{opt_channel_id}> and opt back in if you'd like!"
                    await stat_channel.send(opt_out_message)
            else:
                cur.execute("update skylab_matchmaking set num_chats = {0} where discord_user_id = {1} and guild_id = {2}".format(result[4]+1, discord_user_id, guild_id))
                conn.commit()
        
        numSuccessfulMeetups = len(successfulMeetups)
        # Notify the stats channel about the successful matches count
        match_summary_message = f"Looks like {numSuccessfulMeetups} successful meetups were made out of {numTotalMeetups} total matches during this past session. Keep it up!"
        await stat_channel.send(match_summary_message)

        #Clear the matchmaking channels from this past round
        cur.execute("DELETE FROM skylab_matchmaking_channels WHERE guild_id = {0}".format(guild.id))
        conn.commit()

        # Clear existing channels from the category except for the opt-in/opt-out channel
        await clear_existing_channels(guild)
        
        cur.execute("SELECT discord_user_id FROM skylab_matchmaking WHERE opted_in = true and guild_id = {0}".format(guild_id))
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
            newChannel = await create_private_channel(matchUsers, category_id, guild)
            for user in matchUsers:
                cur.execute("insert into skylab_matchmaking_channels (discord_user_id, channel_id, guild_id) values ({0}, {1})".format(user, newChannel.id, guild_id))
                conn.commit()

        #Update the next meetup time (add a week)
        next_meetup = next_meetup + 604800
        command = "update skylab_matchmaking_guilds set value = {0} where name = 'skylab_next_meetup'".format(next_meetup)
        cur.execute(command)
        conn.commit()

    cur.close()
    conn.commit()
    conn.close()

async def create_private_channel(user_ids, category_id, guild):

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

    #Returns the created channel if needed
    return channel

bot.run(BOT_TOKEN)
