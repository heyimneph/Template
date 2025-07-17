import os
import discord
import logging

from datetime import datetime
from discord.ext import commands
from dotenv import load_dotenv
from discord.ext.commands import Context, is_owner

# Load environment variables
load_dotenv(".env")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", 0))
TEST_GUILD_ID = int(os.getenv("TEST_GUILD_ID", 0)) or None


DISCORD_PREFIX = "!"
LAUNCH_TIME = datetime.utcnow()

# ---------------------------------------------------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------------------------------------------------
os.makedirs("data/logs", exist_ok=True)
os.makedirs("data/databases", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("data/logs/discord.log", encoding="utf-8", mode="w"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------------------------------------------------
# Bot Setup
# ---------------------------------------------------------------------------------------------------------------------
intents = discord.Intents.default()
intents.guilds = True
intents.message_content = True

client = commands.Bot(
    command_prefix=DISCORD_PREFIX,
    intents=intents,
    help_command=None,
    activity=discord.Activity(type=discord.ActivityType.playing, name="games -- /help")
)


# ---------------------------------------------------------------------------------------------------------------------
# Sync Function
# ---------------------------------------------------------------------------------------------------------------------
async def perform_sync(guild: discord.abc.Snowflake):
    try:
        client.tree.clear_commands(guild=guild)
        client.tree.copy_global_to(guild=guild)
        synced = await client.tree.sync(guild=guild)

        logger.info(f"Synced {len(synced)} command(s) to guild: {getattr(guild, 'name', 'Unknown')} ({guild.id})")
        return len(synced)

    except Exception as e:
        logger.exception(f"Failed to sync commands: {e}")
        return 0



# ---------------------------------------------------------------------------------------------------------------------
# Sync All Guilds Command (Owner-only)
# ---------------------------------------------------------------------------------------------------------------------
@client.command(name="sync_all")
@is_owner()
async def sync_all(ctx: Context):
    total_commands = 0
    total_guilds = len(client.guilds)

    for guild in client.guilds:
        count = await perform_sync(guild=guild)
        total_commands += count

    await ctx.reply(f"Synced commands to {total_guilds} guild(s). Total commands synced: {total_commands}")


