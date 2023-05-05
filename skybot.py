import discord
from discord.ext import commands
import psycopg2
import os
from dotenv import load_dotenv
import asyncio
from datetime import datetime, timedelta
import pytz

load_dotenv()

DATABASE_TOKEN = os.getenv('DATABASE_TOKEN')
BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Set up the bot with the proper intents to read message content and reactions
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
client = discord.Client(intents=intents)
bot = commands.Bot(command_prefix="!", intents=intents)

# Adjust the reaction threshold here
REACTION_THRESHOLD = 5
REACTION_EMOJI = "🛰️"

# Start the anniversary checker loop
@client.event
async def on_ready():
    client.loop.create_task(check_anniversaries())

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

#Checks the anniversaries in the user list and sends a happy anniversary message
async def check_anniversaries():
    now = datetime.now(pytz.timezone('US/Eastern'))
    # Check if the current time is between 10 AM and 6 PM EST
    if time(10, 0) <= now.time() <= time(18, 0):
        #Get the Skylab guild
        guild = bot.get_guild(972905096230891540)
        #Get the general channel
        postChannel = discord.utils.get(guild.channels, id = 972905096230891543)

        #Check each member to see if it's their anniversary
        for member in guild.members:
            join_date = member.joined_at
            time_since_join = now - join_date
            years = time_since_join.days // 365
            #We'll use this later
            posted = False

            #If the user has been here at least a year and today is his anniversary
            if years > 0 and time_since_join.days % 365 == 0:
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
    # Calculate the time until 10 AM EST and sleep until then
    next_start = now.replace(hour=10, minute=0, second=0, microsecond=0)
    if now.hour >= 18:
        next_start += timedelta(days=1)  # Next day if the current time is past 6 PM
    sleep_duration = (next_start - now).total_seconds()
    await asyncio.sleep(sleep_duration)


bot.run(BOT_TOKEN)
