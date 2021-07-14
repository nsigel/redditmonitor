import discord, asyncio  # imports the base discord package
from discord.ext import (
    commands,
)  # imports discord.ext and it's commands wrapper, "commands"!
import aiohttp  # this is what we're going to use to make http requests to reddit!
import json  # this is how we will manupulate the json response of the reddit API
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()  # load environment variables from the .env file
TOKEN = os.getenv("BOT_TOKEN")
prefix = "r!"
client = commands.Bot(
    command_prefix=prefix
)  # this defines the discord bot's object - "client". we are also passing in the bot's prefix, which in this case is "r!"


@client.event
async def on_ready():  # this bot event is called when the discord API returns a "ready" status.
    print(f"Alive and well as {client.user}!")
    # Sets the json object content of "subreddits.json" as a client variable - accessable and mutable everywhere
    client.subreddits = json.load(open("subreddits.json"))

    # Changes the bot's discord precense status!
    await client.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"over {len(client.subreddits)} subreddits!",
        )
    )
    await start_monitor()


async def start_monitor():
    client.connector = aiohttp.TCPConnector(ssl=False, limit=None)
    client.session = await aiohttp.ClientSession(
        connector=client.connector
    ).__aenter__()  # this creates a session within aiohttp and converts it into an awaitable using "__aenter__" so we can use it throughout the script!
    while True:
        await asyncio.wait(
            [monitor(subreddit) for subreddit in [*client.subreddits]]
        )  # calls the monitor function for each subreddit in the subreddits


@client.command()
async def add_subreddit(ctx, subreddit):
    client.subreddits[subreddit.replace("r/", "").replace("/", "")] = {
        "last_post": 0,
        "channel": int(os.getenv("DEFAULT_CHANNEL")),
    }

    json.dump(client.subreddits, open("subreddits.json", "w"), indent=4)
    await ctx.send(
        embed=discord.Embed(
            title=f"Succesfully added subreddit {subreddit}!",
            description=f"Change this subreddit's posting channel with `r!channel {subreddit}`",
            color=0x0066CC,
        )
    )


@client.command()
async def channel(ctx, subreddit, channel):
    if subreddit in [*client.subreddits]:
        client.subreddits[subreddit]["channel"] = channel
    await ctx.send(
        embed=discord.Embed(
            title=f"Succesfully changed channel!",
            description=f"Channel changed to `{channel}`",
            color=0x0066CC,
        )
    )


@client.command()
async def remove_subreddit(ctx, subreddit):
    if subreddit in [*client.subreddits]:
        del client.subreddits[subreddit]

        await ctx.send(
            embed=discord.Embed(title="Succesfully removed item!", color=0x0066CC)
        )


@client.command()
async def subreddits(ctx):
    embed = discord.Embed(title="Monitored subreddits:", color=0x0066CC)
    subs = [*client.subreddits]
    for i in subs:
        embed.add_field(name=i, value=client.subreddits[i]["channel"])
    await ctx.send(embed=embed)


async def request(subreddit):
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36",
        "referer": f"https://www.reddit.com/r/{subreddit}",
    }

    url = f"https://www.reddit.com/r/{subreddit}/new.json"
    return await client.session.get(url, headers=headers)


async def monitor(subreddit):
    try:
        res = await request(subreddit)

        if res.status != 200:
            raise Exception(f"Bad status code - {res.status}")

        else:
            try:
                data = (
                    await res.json()
                )  # attempt to get the json response of the request
                last_post = data["data"]["children"][0]["data"]

            except:
                raise Exception("Unable to retrieve JSON response!")

            if client.subreddits[subreddit]["last_post"] != last_post["created_utc"]:
                print("New post found!")
                await send_new_post(last_post)

    except Exception as e:
        print(f"Error raised during montioring!\n{str(e)}")
        return


async def send_new_post(post):
    title = post["title"]
    link = post["url"]
    posted = post["created_utc"]
    post_link = "https://www.reddit.com" + post["permalink"]
    post_author = post["author"]
    selftext = post["selftext"]
    subreddit = post["subreddit"]

    embed = discord.Embed(title=title, url=post_link, color=0x0066CC)

    if selftext:
        embed.add_field(name="Post selftext:", value=selftext)

    if "i.redd.it" in link:
        embed.set_thumbnail(url=link)
    else:
        embed.add_field(name="Linked URL:", value=post_link)

    embed.set_author(
        icon_url="https://images-ext-2.discordapp.net/external/ZJezPe-pD7CzDpku0o5R2zTdEcksXkU3cCAulnhGjwQ/https/www.iconfinder.com/data/icons/social-media-2092/100/social-36-512.png",
        name=f"New post found in r/{subreddit}!",
    )
    embed.add_field(name="Author:", value=post_author, inline=True)
    embed.timestamp = datetime.now()

    posting_channel = client.get_channel(client.subreddits[subreddit]["channel"])

    await posting_channel.send(embed=embed)

    client.subreddits[subreddit]["last_post"] = posted
    json.dump(client.subreddits, open("subreddits.json", "w"), indent=4)


# Error handling


@client.event
async def on_command_error(ctx, error):
    if hasattr(ctx.command, "on_error"):
        return

    if isinstance(error, commands.CheckFailure):
        await ctx.send(
            embed=discord.Embed(
                color=0xE1306C,
                description="Not allowed. If you believe this is a mistake, please contact a developer!",
            )
        )

    elif isinstance(error, commands.CommandNotFound):
        return

    elif isinstance(error, commands.MissingRequiredArgument):
        try:
            await ctx.send(
                content=ctx.author.mention,
                embed=discord.Embed(
                    color=0xE1306C,
                    description=f"**Bad syntax!** Use {prefix}`help <command>` to get syntax.",
                ),
            )

        except discord.Forbidden:
            pass

    else:
        print(error)


client.run(TOKEN)
