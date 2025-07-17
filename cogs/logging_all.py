import discord
import logging
import aiosqlite

from discord.ext import commands
from discord import app_commands
from discord.ui import Select, View

from core.utils import check_permissions, log_command_usage, DB_PATH

# ---------------------------------------------------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------------------------------------------------
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------------------------------------------------
# Log Class
# ---------------------------------------------------------------------------------------------------------------------
class LoggingView(View):
    def __init__(self, cog_instance: commands.Cog, action):
        super().__init__(timeout=180)
        self.cog_instance = cog_instance
        self.action = action
        placeholder = f"Select events to {action}"
        update_value = 1 if action == "enable" else 0

        options = [
            discord.SelectOption(label="ALL", value="all"),
            discord.SelectOption(label="Member Join", value="member_join"),
            discord.SelectOption(label="Member Remove", value="member_remove"),
            discord.SelectOption(label="Message Edit", value="message_edit"),
            discord.SelectOption(label="Message Delete", value="message_delete"),
            discord.SelectOption(label="Voice State Update", value="voice_state_update"),
            discord.SelectOption(label="Channel Create", value="guild_channel_create"),
            discord.SelectOption(label="Channel Delete", value="guild_channel_delete"),
            discord.SelectOption(label="Channel Update", value="guild_channel_update"),
        ]

        select = Select(placeholder=placeholder, options=options)
        self.add_item(select)

        async def select_callback(interaction):
            try:
                if "all" in select.values:
                    await self.cog_instance.conn.execute(
                        f'''UPDATE logging_config SET member_join = ?, member_remove = ?, message_edit = ?, 
                            message_delete = ?, voice_state_update = ?, guild_channel_create = ?, 
                            guild_channel_delete = ?, guild_channel_update = ? WHERE guild_id = ?''',
                        (update_value,) * 8 + (interaction.guild_id,)
                    )
                else:
                    for value in select.values:
                        await self.cog_instance.conn.execute(
                            f'UPDATE logging_config SET {value} = ? WHERE guild_id = ?',
                            (update_value, interaction.guild_id)
                        )

                await self.cog_instance.conn.commit()
                await interaction.response.send_message(
                    f"{self.action.capitalize()}d logging for {', '.join(select.values)} events.",
                    ephemeral=True
                )
                logger.info(f"Updated logging configuration for guild_id: {interaction.guild_id}")

            except Exception as e:
                logger.error(f"Error updating logging configuration: {e}")

        select.callback = select_callback

    async def on_timeout(self):
        logger.info("LoggingView selection timed out.")


class LogsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = None

    async def cog_load(self):
        self.conn = await aiosqlite.connect(DB_PATH)

    async def cog_unload(self):
        if self.conn:
            await self.conn.close()

    async def is_logging_enabled(self, guild_id, event_type):
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(f'SELECT {event_type} FROM logging_config WHERE guild_id = ?', (guild_id,)) as cursor:
                result = await cursor.fetchone()
        return result and result[0] == 1

# ---------------------------------------------------------------------------------------------------------------------
# Logging Functions
# ---------------------------------------------------------------------------------------------------------------------
    @commands.Cog.listener()
    async def on_member_join(self, member):
        if not await self.is_logging_enabled(member.guild.id, 'member_join'):
            return

        try:
            async with aiosqlite.connect(DB_PATH) as conn:
                async with conn.execute('SELECT log_channel_id FROM config WHERE guild_id = ?',
                                        (member.guild.id,)) as cursor:
                    result = await cursor.fetchone()

            if result:
                log_channel_id = result[0]
                logger.debug(
                    f"Attempting to retrieve log channel with ID: {log_channel_id} for guild: {member.guild.id}")

                try:
                    log_channel = await self.bot.fetch_channel(log_channel_id)
                except discord.NotFound:
                    logger.error(f"Log channel with ID {log_channel_id} not found in guild: {member.guild.id}")
                    return
                except discord.Forbidden:
                    logger.error(f"Permission denied to access channel ID {log_channel_id} in guild: {member.guild.id}")
                    return
                except Exception as e:
                    logger.error(f"Unexpected error fetching channel: {e}")
                    return

                if log_channel:
                    embed = discord.Embed(
                        description="Action: `Member Joined`",
                        color=discord.Color.green()
                    )
                    embed.add_field(name="User", value=member.mention, inline=True)
                    embed.add_field(name="Guild ID", value=str(member.guild.id), inline=True)
                    embed.set_footer(text=f"User ID: {member.id}")
                    embed.set_author(name=str(member), icon_url=member.display_avatar.url)
                    embed.timestamp = discord.utils.utcnow()

                    await log_channel.send(embed=embed)
                    logger.info(f"Logged member join event for user: {member}")

        except Exception as e:
            logger.error(f"Error in on_member_join event: {e}")


    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if not await self.is_logging_enabled(member.guild.id, 'member_remove'):
            return

        try:
            async with aiosqlite.connect(DB_PATH) as conn:
                async with conn.execute('SELECT log_channel_id FROM config WHERE guild_id = ?',
                                        (member.guild.id,)) as cursor:
                    result = await cursor.fetchone()

            if result:
                log_channel_id = result[0]
                logger.debug(
                    f"Attempting to retrieve log channel with ID: {log_channel_id} for guild: {member.guild.id}")

                try:
                    log_channel = await self.bot.fetch_channel(log_channel_id)
                except discord.NotFound:
                    logger.error(f"Log channel with ID {log_channel_id} not found in guild: {member.guild.id}")
                    return
                except discord.Forbidden:
                    logger.error(f"Permission denied to access channel ID {log_channel_id} in guild: {member.guild.id}")
                    return
                except Exception as e:
                    logger.error(f"Unexpected error fetching channel: {e}")
                    return

                if log_channel:
                    embed = discord.Embed(
                        description="Action: `Member Left`",
                        color=discord.Color.red()
                    )
                    embed.add_field(name="User", value=member.mention, inline=True)
                    embed.add_field(name="Guild ID", value=str(member.guild.id), inline=True)
                    embed.set_footer(text=f"User ID: {member.id}")
                    embed.set_author(name=str(member), icon_url=member.display_avatar.url)
                    embed.timestamp = discord.utils.utcnow()

                    await log_channel.send(embed=embed)
                    logger.info(f"Logged member leave event for user: {member}")

        except Exception as e:
            logger.error(f"Error in on_member_remove event: {e}")

# ---------------------------------------------------------------------------------------------------------------------
# ---------------------------------------------------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if not await self.is_logging_enabled(message.guild.id, 'message_delete'):
            return

        try:
            async with aiosqlite.connect(DB_PATH) as conn:
                async with conn.execute('SELECT log_channel_id FROM config WHERE guild_id = ?',
                                        (message.guild.id,)) as cursor:
                    result = await cursor.fetchone()

            if result:
                log_channel_id = result[0]
                logger.debug(
                    f"Attempting to retrieve log channel with ID: {log_channel_id} for guild: {message.guild.id}")

                try:
                    log_channel = await self.bot.fetch_channel(log_channel_id)
                except discord.NotFound:
                    logger.error(f"Log channel with ID {log_channel_id} not found in guild: {message.guild.id}")
                    return
                except discord.Forbidden:
                    logger.error(
                        f"Permission denied to access channel ID {log_channel_id} in guild: {message.guild.id}")
                    return
                except Exception as e:
                    logger.error(f"Unexpected error fetching channel: {e}")
                    return

                if log_channel:
                    embed = discord.Embed(
                        description="Action: `Message Deleted`",
                        color=discord.Color.red()
                    )
                    embed.add_field(name="User", value=message.author.mention, inline=True)
                    embed.add_field(name="Channel", value=message.channel.mention, inline=True)

                    if message.content:
                        embed.add_field(name="Content", value=f"*{message.content}*", inline=False)
                    else:
                        embed.add_field(name="Content", value="*Content not available*", inline=False)

                    embed.set_footer(text=f"User ID: {message.author.id}")
                    embed.timestamp = discord.utils.utcnow()

                    await log_channel.send(embed=embed)
                    logger.info(
                        f"Logged message deletion event for user: {message.author} in channel: {message.channel.name}")

        except Exception as e:
            logger.error(f"Error in on_message_delete event: {e}")


    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if not await self.is_logging_enabled(before.guild.id, 'message_edit'):
            return

        try:
            if before.content == after.content:
                return  # No changes in content

            async with aiosqlite.connect(DB_PATH) as conn:
                async with conn.execute('SELECT log_channel_id FROM config WHERE guild_id = ?',
                                        (before.guild.id,)) as cursor:
                    result = await cursor.fetchone()

            if result:
                log_channel_id = result[0]
                logger.debug(
                    f"Attempting to retrieve log channel with ID: {log_channel_id} for guild: {before.guild.id}")

                try:
                    log_channel = await self.bot.fetch_channel(log_channel_id)
                except discord.NotFound:
                    logger.error(f"Log channel with ID {log_channel_id} not found in guild: {before.guild.id}")
                    return
                except discord.Forbidden:
                    logger.error(f"Permission denied to access channel ID {log_channel_id} in guild: {before.guild.id}")
                    return
                except Exception as e:
                    logger.error(f"Unexpected error fetching channel: {e}")
                    return

                if log_channel:
                    embed = discord.Embed(
                        description="Action: `Message Edited`",
                        color=discord.Color.blue()
                    )
                    embed.add_field(name="User", value=before.author.mention, inline=True)
                    embed.add_field(name="Channel", value=before.channel.mention, inline=True)
                    embed.add_field(name="Before", value=f"*{before.content}*", inline=False)
                    embed.add_field(name="After", value=f"*{after.content}*", inline=False)

                    embed.set_footer(text=f"User ID: {before.author.id}")
                    embed.timestamp = discord.utils.utcnow()

                    await log_channel.send(embed=embed)
                    logger.info(
                        f"Logged message edit event for user: {before.author} in channel: {before.channel.name}")

        except Exception as e:
            logger.error(f"Error in on_message_edit event: {e}")

# ---------------------------------------------------------------------------------------------------------------------
# ---------------------------------------------------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not await self.is_logging_enabled(member.guild.id, 'voice_state_update'):
            return

        try:
            async with aiosqlite.connect(DB_PATH) as conn:
                async with conn.execute('SELECT log_channel_id FROM config WHERE guild_id = ?', (member.guild.id,)) as cursor:
                    result = await cursor.fetchone()

            if result:
                log_channel_id = result[0]
                logger.debug(f"Attempting to retrieve log channel with ID: {log_channel_id} for guild: {member.guild.id}")

                try:
                    log_channel = await self.bot.fetch_channel(log_channel_id)
                except discord.NotFound:
                    logger.error(f"Log channel with ID {log_channel_id} not found in guild: {member.guild.id}")
                    return
                except discord.Forbidden:
                    logger.error(f"Permission denied to access channel ID {log_channel_id} in guild: {member.guild.id}")
                    return
                except Exception as e:
                    logger.error(f"Unexpected error fetching channel: {e}")
                    return

                if log_channel:
                    action_description = "Action: `Voice State Updated`"
                    if before.channel is None and after.channel is not None:
                        action_description = "Action: `Joined Voice Channel`"
                    elif before.channel is not None and after.channel is None:
                        action_description = "Action: `Left Voice Channel`"
                    elif before.channel != after.channel:
                        action_description = "Action: `Moved Voice Channels`"

                    embed = discord.Embed(
                        description=action_description,
                        color=discord.Color.green() if after.channel else discord.Color.red()
                    )
                    embed.add_field(name="User", value=member.mention, inline=False)
                    if before.channel:
                        embed.add_field(name="From", value=before.channel.mention, inline=True)
                    if after.channel:
                        embed.add_field(name="To", value=after.channel.mention, inline=True)

                    embed.set_footer(text=f"User ID: {member.id}")
                    embed.timestamp = discord.utils.utcnow()

                    await log_channel.send(embed=embed)
                    logger.info(f"Logged voice state update for user: {member}")

        except Exception as e:
            logger.error(f"Error in on_voice_state_update event: {e}")

# ---------------------------------------------------------------------------------------------------------------------
# ---------------------------------------------------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        if not await self.is_logging_enabled(channel.guild.id, 'guild_channel_create'):
            return

        try:
            async with aiosqlite.connect(DB_PATH) as conn:
                async with conn.execute('SELECT log_channel_id FROM config WHERE guild_id = ?', (channel.guild.id,)) as cursor:
                    result = await cursor.fetchone()

            if result:
                log_channel_id = result[0]
                logger.debug(f"Attempting to retrieve log channel with ID: {log_channel_id} for guild: {channel.guild.id}")

                try:
                    log_channel = await self.bot.fetch_channel(log_channel_id)
                except discord.NotFound:
                    logger.error(f"Log channel with ID {log_channel_id} not found in guild: {channel.guild.id}")
                    return
                except discord.Forbidden:
                    logger.error(f"Permission denied to access channel ID {log_channel_id} in guild: {channel.guild.id}")
                    return
                except Exception as e:
                    logger.error(f"Unexpected error fetching channel: {e}")
                    return

                if log_channel:
                    embed = discord.Embed(
                        description="Action: `Channel Created`",
                        color=discord.Color.green()
                    )
                    embed.add_field(name="Channel", value=channel.mention, inline=True)
                    embed.add_field(name="Channel Type", value=str(channel.type), inline=True)
                    embed.set_footer(text=f"Channel ID: {channel.id}")
                    embed.timestamp = discord.utils.utcnow()

                    await log_channel.send(embed=embed)
                    logger.info(f"Logged channel creation event for channel: {channel.name}")

        except Exception as e:
            logger.error(f"Error in on_guild_channel_create event: {e}")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if not await self.is_logging_enabled(channel.guild.id, 'guild_channel_delete'):
            return

        try:
            async with aiosqlite.connect(DB_PATH) as conn:
                async with conn.execute('SELECT log_channel_id FROM config WHERE guild_id = ?', (channel.guild.id,)) as cursor:
                    result = await cursor.fetchone()

            if result:
                log_channel_id = result[0]
                logger.debug(f"Attempting to retrieve log channel with ID: {log_channel_id} for guild: {channel.guild.id}")

                try:
                    log_channel = await self.bot.fetch_channel(log_channel_id)
                except discord.NotFound:
                    logger.error(f"Log channel with ID {log_channel_id} not found in guild: {channel.guild.id}")
                    return
                except discord.Forbidden:
                    logger.error(f"Permission denied to access channel ID {log_channel_id} in guild: {channel.guild.id}")
                    return
                except Exception as e:
                    logger.error(f"Unexpected error fetching channel: {e}")
                    return

                if log_channel:
                    embed = discord.Embed(
                        description="Action: `Channel Deleted`",
                        color=discord.Color.red()
                    )
                    embed.add_field(name="Channel Name", value=channel.name, inline=True)
                    embed.add_field(name="Channel Type", value=str(channel.type), inline=True)
                    embed.set_footer(text=f"Channel ID: {channel.id}")
                    embed.timestamp = discord.utils.utcnow()

                    await log_channel.send(embed=embed)
                    logger.info(f"Logged channel deletion event for channel: {channel.name}")

        except Exception as e:
            logger.error(f"Error in on_guild_channel_delete event: {e}")

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        if not await self.is_logging_enabled(before.guild.id, 'guild_channel_update'):
            return

        try:
            async with aiosqlite.connect(DB_PATH) as conn:
                async with conn.execute('SELECT log_channel_id FROM config WHERE guild_id = ?', (before.guild.id,)) as cursor:
                    result = await cursor.fetchone()

            if result:
                log_channel_id = result[0]
                logger.debug(f"Attempting to retrieve log channel with ID: {log_channel_id} for guild: {before.guild.id}")

                try:
                    log_channel = await self.bot.fetch_channel(log_channel_id)
                except discord.NotFound:
                    logger.error(f"Log channel with ID {log_channel_id} not found in guild: {before.guild.id}")
                    return
                except discord.Forbidden:
                    logger.error(f"Permission denied to access channel ID {log_channel_id} in guild: {before.guild.id}")
                    return
                except Exception as e:
                    logger.error(f"Unexpected error fetching channel: {e}")
                    return

                if log_channel:
                    embed = discord.Embed(
                        description="Action: `Channel Updated`",
                        color=discord.Color.blue()
                    )
                    embed.add_field(name="Channel", value=after.mention, inline=True)

                    changes = []
                    if before.name != after.name:
                        changes.append(f"Name: `{before.name}` → `{after.name}`")
                    if before.category != after.category:
                        before_category = before.category.name if before.category else "None"
                        after_category = after.category.name if after.category else "None"
                        changes.append(f"Category: `{before_category}` → `{after_category}`")
                    if before.position != after.position:
                        changes.append(f"Position: `{before.position}` → `{after.position}`")

                    if changes:
                        embed.add_field(name="Changes", value="\n".join(changes), inline=False)

                    embed.set_footer(text=f"Channel ID: {after.id}")
                    embed.timestamp = discord.utils.utcnow()

                    await log_channel.send(embed=embed)
                    logger.info(f"Logged channel update event for channel: {before.name}")

        except Exception as e:
            logger.error(f"Error in on_guild_channel_update event: {e}")

# ---------------------------------------------------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------------------------------------------------
    async def enable_disable_logging(self, interaction: discord.Interaction, action: str):
        assert action in ["enable", "disable"]

        async with self.conn.execute('SELECT * FROM logging_config WHERE guild_id = ?', (interaction.guild_id,)) as cursor:  # Use the class variable conn
            row = await cursor.fetchone()
        if not row:
            await self.conn.execute('INSERT INTO logging_config (guild_id) VALUES (?)', (interaction.guild_id,))  # Use the class variable conn
            await self.conn.commit()

        view = LoggingView(self, action)
        await interaction.response.send_message(f"Select events to {action} logging:", view=view, ephemeral=True)
        await log_command_usage(self.bot, interaction)

    @app_commands.command(description="Admin: Enable logging for specific events")
    @app_commands.guild_only()
    async def logging_enable(self, interaction: discord.Interaction):
        if not await check_permissions(interaction):
            await interaction.response.send_message("You do not have permission to use this command. "
                                                    "An Admin needs to `/authorise` you!",
                                                    ephemeral=True)
            return

        await self.enable_disable_logging(interaction, "enable")


    @app_commands.command(description="Admin: Disable logging for specific events")
    @app_commands.guild_only()
    async def logging_disable(self, interaction: discord.Interaction):
        if not await check_permissions(interaction):
            await interaction.response.send_message("You do not have permission to use this command. "
                                                    "An Admin needs to `/authorise` you!",
                                                    ephemeral=True)
            return
        await self.enable_disable_logging(interaction, "disable")

    @app_commands.command(description="Admin: Display current logging settings")
    @app_commands.guild_only()
    async def logging_settings(self, interaction: discord.Interaction):
        if not await check_permissions(interaction):
            await interaction.response.send_message("You do not have permission to use this command. "
                                                    "An Admin needs to `/authorise` you!",
                                                    ephemeral=True)
            await log_command_usage(self.bot, interaction)
            return

        try:
            async with self.conn.execute('SELECT * FROM logging_config WHERE guild_id = ?',
                                         (interaction.guild_id,)) as cursor:
                row = await cursor.fetchone()

            if not row:
                await interaction.response.send_message("No logging settings configured for this guild.",
                                                        ephemeral=True)
                await log_command_usage(self.bot, interaction)
                return

            # Access row by index since it's a tuple
            settings = {
                "member_join": "enabled" if row[1] else "disabled",
                "member_remove": "enabled" if row[2] else "disabled",
                "message_edit": "enabled" if row[3] else "disabled",
                "message_delete": "enabled" if row[4] else "disabled",
                "voice_state_update": "enabled" if row[5] else "disabled",
                "guild_channel_create": "enabled" if row[6] else "disabled",
                "guild_channel_delete": "enabled" if row[7] else "disabled",
                "guild_channel_update": "enabled" if row[8] else "disabled"
            }

            embed = discord.Embed(title="Logging Settings", color=discord.Color.blue())

            for key, value in settings.items():
                embed.add_field(name=key, value=f"```\n{value}\n```", inline=False)

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in logging_settings command: {e}")
            await interaction.response.send_message("An unexpected error occurred while retrieving logging settings.",
                                                    ephemeral=True)
        finally:
            await log_command_usage(self.bot, interaction)

# ---------------------------------------------------------------------------------------------------------------------
# Setup Function
# ---------------------------------------------------------------------------------------------------------------------

async def setup(bot):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute('''
        CREATE TABLE IF NOT EXISTS logging_config (
            guild_id INTEGER PRIMARY KEY,
            member_join INTEGER DEFAULT 0,
            member_remove INTEGER DEFAULT 0,
            message_edit INTEGER DEFAULT 0,
            message_delete INTEGER DEFAULT 0,
            voice_state_update INTEGER DEFAULT 0,
            guild_channel_create INTEGER DEFAULT 0,
            guild_channel_delete INTEGER DEFAULT 0,
            guild_channel_update INTEGER DEFAULT 0
        )
        ''')
        await conn.commit()
    await bot.add_cog(LogsCog(bot))

