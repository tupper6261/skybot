import discord
from discord.ext import commands
import psycopg2
import os

load_dotenv()

DATABASE_TOKEN = os.getenv('DATABASE_TOKEN')
BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Set up the bot with the proper intents to read message content and reactions
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Adjust the reaction threshold here
REACTION_THRESHOLD = 5
REACTION_EMOJI = "🛰️"

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

bot.run(BOT_TOKEN)
