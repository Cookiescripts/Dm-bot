import discord
from discord import app_commands
from discord.ext import commands
import os

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


# ── Shared logic ─────────────────────────────────────────────────────────────

async def logic_dm(send, member: discord.Member, message: str):
    try:
        await member.send(message)
        await send(f"Message sent to {member.mention}.")
    except discord.Forbidden:
        await send(f"Could not send a DM to {member.mention}. They may have DMs disabled.")
    except discord.HTTPException as e:
        await send(f"Failed to send DM: {e}")


async def logic_broadcast(send, edit, guild: discord.Guild, message: str):
    members = [m for m in guild.members if not m.bot]
    await send(f"Broadcasting to {len(members)} members...")
    success, failed = 0, 0
    for member in members:
        try:
            await member.send(message)
            success += 1
        except (discord.Forbidden, discord.HTTPException):
            failed += 1
    await edit(f"Broadcast complete. Sent: {success} | Failed: {failed}")


async def logic_announce(channel: discord.TextChannel, title: str, message: str, author: discord.Member):
    embed = discord.Embed(title=title, description=message, color=discord.Color.blurple())
    embed.set_footer(text=f"Announced by {author.display_name}", icon_url=author.display_avatar.url)
    await channel.send(embed=embed)


HELP_TEXT = (
    "**Available Commands**\n\n"
    "**Prefix Commands**\n"
    "`!dm @user <message>` — Send a DM to a specific user\n"
    "`!broadcast <message>` — Send a DM to all members *(Admin only)*\n"
    "`!announce #channel <title> | <message>` — Post an embed to a channel *(Admin only)*\n"
    "`!help` — Show this help message\n\n"
    "**Slash Commands**\n"
    "`/dm` — Send a DM to a specific user\n"
    "`/broadcast` — Send a DM to all members *(Admin only)*\n"
    "`/announce` — Post an embed to a channel *(Admin only)*\n"
    "`/help` — Show this help message"
)


# ── Bot events ────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")


async def setup_hook():
    await bot.tree.sync()
    print("Slash commands synced.")

bot.setup_hook = setup_hook


# ── Prefix commands ───────────────────────────────────────────────────────────

@bot.command(name="dm")
async def prefix_dm(ctx, member: discord.Member, *, message: str):
    await logic_dm(ctx.send, member, message)

@prefix_dm.error
async def prefix_dm_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Usage: `!dm @user <message>`")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("Could not find that member. Make sure you @mention a valid server member.")
    else:
        await ctx.send(f"An error occurred: {error}")


@bot.command(name="broadcast")
@commands.has_permissions(administrator=True)
async def prefix_broadcast(ctx, *, message: str):
    sent_msg = None

    async def send(text):
        nonlocal sent_msg
        sent_msg = await ctx.send(text)

    async def edit(text):
        await sent_msg.edit(content=text)

    await logic_broadcast(send, edit, ctx.guild, message)

@prefix_broadcast.error
async def prefix_broadcast_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Usage: `!broadcast <message>`")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You need Administrator permission to use this command.")
    else:
        await ctx.send(f"An error occurred: {error}")


@bot.command(name="announce")
@commands.has_permissions(administrator=True)
async def prefix_announce(ctx, channel: discord.TextChannel, *, content: str):
    if "|" not in content:
        await ctx.send("Usage: `!announce #channel <title> | <message>`")
        return
    title, _, message = content.partition("|")
    await logic_announce(channel, title.strip(), message.strip(), ctx.author)
    await ctx.send(f"Announcement posted in {channel.mention}.", delete_after=5)

@prefix_announce.error
async def prefix_announce_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Usage: `!announce #channel <title> | <message>`")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You need Administrator permission to use this command.")
    elif isinstance(error, commands.ChannelNotFound):
        await ctx.send("Could not find that channel. Make sure you #mention a valid channel.")
    else:
        await ctx.send(f"An error occurred: {error}")


@bot.command(name="help")
async def prefix_help(ctx):
    await ctx.send(HELP_TEXT)


# ── Slash commands ────────────────────────────────────────────────────────────

@bot.tree.command(name="dm", description="Send a DM to a specific user")
@app_commands.describe(member="The user to DM", message="The message to send")
async def slash_dm(interaction: discord.Interaction, member: discord.Member, message: str):
    await interaction.response.defer(ephemeral=True)
    await logic_dm(lambda text: interaction.followup.send(text, ephemeral=True), member, message)


@bot.tree.command(name="broadcast", description="Send a DM to all non-bot members (Admin only)")
@app_commands.describe(message="The message to broadcast")
@app_commands.default_permissions(administrator=True)
async def slash_broadcast(interaction: discord.Interaction, message: str):
    await interaction.response.defer(ephemeral=True)
    followup_msg = None

    async def send(text):
        nonlocal followup_msg
        followup_msg = await interaction.followup.send(text, ephemeral=True)

    async def edit(text):
        await followup_msg.edit(content=text)

    await logic_broadcast(send, edit, interaction.guild, message)


@bot.tree.command(name="announce", description="Post a formatted embed announcement to a channel (Admin only)")
@app_commands.describe(channel="The channel to post in", title="Announcement title", message="Announcement body")
@app_commands.default_permissions(administrator=True)
async def slash_announce(interaction: discord.Interaction, channel: discord.TextChannel, title: str, message: str):
    await logic_announce(channel, title, message, interaction.user)
    await interaction.response.send_message(f"Announcement posted in {channel.mention}.", ephemeral=True)


@bot.tree.command(name="help", description="Show all available commands")
async def slash_help(interaction: discord.Interaction):
    await interaction.response.send_message(HELP_TEXT, ephemeral=True)


# ── Run ───────────────────────────────────────────────────────────────────────

token = os.environ.get("TOKEN")
if not token:
    raise ValueError("TOKEN environment variable is not set.")

bot.run(token)
