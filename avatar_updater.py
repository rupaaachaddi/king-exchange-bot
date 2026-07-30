import discord

intents = discord.Intents.default()
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    with open("logo.gif", "rb") as f:
        await client.user.edit(avatar=f.read())
    print("GIF logo updated!")
    await client.close()   # stop the script once done, don't leave it running

client.run(None)