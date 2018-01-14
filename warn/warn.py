"""Warning cog"""

# Credits go to Twentysix26 for modlog
# https://github.com/Twentysix26/Red-DiscordBot/blob/develop/cogs/mod.py
#bot.change_nickname(user, display_name + "ðŸ’©")
import discord
import os
import shutil
import aiohttp
import asyncio
from discord.ext import commands
from .utils import checks
from .utils.chat_formatting import pagify, box
import logging
import time
import re
import zlib, marshal, base64
import uuid
from .utils.chat_formatting import *
from .utils.dataIO import fileIO, dataIO
from .utils import checks
from discord.ext import commands
from enum import Enum
from __main__ import send_cmd_help

default_warn = ("user.mention, you have received your "
                "warning #warn.count! At warn.limit warnings you "
                "will be banned!")
default_max = 3
default_ban = ("After warn.limit warnings, user.name has been banned.")
try:
    from tabulate import tabulate
except Exception as e:
    raise RuntimeError("You must run `pip3 install tabulate`.") from e

log = logging.getLogger('red.punish')

UNIT_TABLE = {'s': 1, 'm': 60, 'h': 60 * 60, 'd': 60 * 60 * 24}
UNIT_SUF_TABLE = {'sec': (1, ''),
                  'min': (60, ''),
                  'hr': (60 * 60, 's'),
                  'day': (60 * 60 * 24, 's')
                  }
DEFAULT_TIMEOUT = '1m'
PURGE_MESSAGES = 1  # for cpunish
PATH = 'data/account/'
JSON = PATH + 'warnsettings.json'
DEFAULT_ROLE_NAME = 'Muted'


class BadTimeExpr(Exception):
    pass


def _parse_time(time):
    if any(u in time for u in UNIT_TABLE.keys()):
        delim = '([0-9.]*[{}])'.format(''.join(UNIT_TABLE.keys()))
        time = re.split(delim, time)
        time = sum([_timespec_sec(t) for t in time if t != ''])
    elif not time.isdigit():
        raise BadTimeExpr("invalid expression '%s'" % time)
    return int(time)


def _timespec_sec(t):
    timespec = t[-1]
    if timespec.lower() not in UNIT_TABLE:
        raise BadTimeExpr("unknown unit '%c'" % timespec)
    timeint = float(t[:-1])
    return timeint * UNIT_TABLE[timespec]


def _generate_timespec(sec):
    timespec = []

    def sort_key(kt):
        k, t = kt
        return t[0]
    for unit, kt in sorted(UNIT_SUF_TABLE.items(), key=sort_key, reverse=True):
        secs, suf = kt
        q = sec // secs
        if q:
            if q <= 1:
                suf = ''
            timespec.append('%02.d%s%s' % (q, unit, suf))
        sec = sec % secs
    return ', '.join(timespec)
        

class Warn:
    "Put misbehaving users in timeout"
    def __init__(self, bot):
        self.bot = bot
        self.json = compat_load(JSON)
        self.handles = {}
        #self.analytics = CogAnalytics(self)
        bot.loop.create_task(self.on_load())
        self.profile = "data/account/warnings.json"
        self.riceCog = dataIO.load_json(self.profile)
        self.warning_settings = "data/account/warning_settings.json"
        self.riceCog2 = dataIO.load_json(self.warning_settings)
        if not self.bot.get_cog("Mod"):
            print("You need the Mod cog to run this cog effectively!")

    def save(self):
        dataIO.save_json(JSON, self.json)


    @commands.group(no_pm=True, pass_context=True, name='warnset')
    async def _warnset(self, ctx):
        if ctx.message.server.id not in self.riceCog2:
            self.riceCog2[ctx.message.server.id] = {}
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)
            server = ctx.message.server
            try:
                msg = self.riceCog2[server.id]["warn_message"]
            except:
                msg = default_warn
            try:
                ban = self.riceCog2[server.id]["ban_message"]
            except:
                ban = default_ban
            try:
                _max = self.riceCog2[server.id]["max"]
            except:
                _max = default_max
            message = "```\n"
            message += "Warn Message - {}\n"
            message += "Ban Message - {}\n"
            message += "Warn Limit   - {}\n"
            message += "```"
            await self.bot.say(message.format(msg,
                                              ban,
                                              _max))

    @_warnset.command(no_pm=True, pass_context=True, manage_server=True)
    async def pm(self, ctx):
        """Enable/disable PM warn"""
        server = ctx.message.server
        if 'pm_warn' not in self.riceCog[server.id]:
            self.riceCog[server.id]['pm_warn'] = False

        p = self.riceCog[server.id]['pm_warn']
        if p:
            self.riceCog[server.id]['pm_warn'] = False
            await self.bot.say("Warnings are now in the channel.")
        elif not p:
            self.riceCog[server.id]['pm_warn'] = True
            await self.bot.say("Warnings are now in DM.")

    @_warnset.command(no_pm=True, pass_context=True, manage_server=True)
    async def poop(self, ctx):
        """Enable/disable poop emojis per warning."""
        server = ctx.message.server
        true_msg = "Poop emojis per warning enabled."
        false_msg = "Poop emojis per warning disabled."
        if 'poop' not in self.riceCog2[server.id]:
            self.riceCog2[server.id]['poop'] = True
            msg = true_msg
        elif self.riceCog2[server.id]['poop'] == True:
            self.riceCog2[server.id]['poop'] = False
            msg = false_msg
        elif self.riceCog2[server.id]['poop'] == False:
            self.riceCog2[server.id]['poop'] = True
            msg = true_msg
        else:
            msg = "Error."
        dataIO.save_json(self.warning_settings,
                         self.riceCog2)
        await self.bot.say(msg)

    @_warnset.command(no_pm=True, pass_context=True)
    @checks.admin_or_permissions(ban_members=True, manage_server=True)
    async def max(self, ctx, limit: int):
        server = ctx.message.server

        self.riceCog2[server.id]["max"] = limit
        dataIO.save_json(self.warning_settings,
                         self.riceCog2)
        await self.bot.say("Warn limit is now: \n{}".format(limit))

    @_warnset.command(no_pm=True, pass_context=True)
    @checks.admin_or_permissions(ban_members=True, manage_server=True)
    async def ban(self, ctx, *, msg=None):
        """Set the ban message.

        To get a full list of information, use **warnset message** without any parameters."""
        if not msg:
            await self.bot.say("```Set the ban message.\n\n"
                               "To get a full list of information, use "
                               "**warnset message** without any parameters.```")
            return
        server = ctx.message.server

        self.riceCog2[server.id]["ban_message"] = msg
        dataIO.save_json(self.warning_settings,
                         self.riceCog2)
        await self.bot.say("Ban message is now: \n{}".format(msg))

    @_warnset.command(no_pm=True, pass_context=True)
    @checks.admin_or_permissions(ban_members=True, manage_server=True)
    async def reset(self, ctx):
        server = ctx.message.server
        author = ctx.message.author
        channel = ctx.message.channel
        await self.bot.say("Are you sure you want to reset all warn settings"
                           "for this server?\n"
                           "Type **yes** within the next 15 seconds.")
        msg = await self.bot.wait_for_message(author=author,
                                              channel=channel,
                                              timeout=15.0)
        if msg.content.lower().strip() == "yes":
            self.riceCog2[server.id]["warn_message"] = default_warn
            self.riceCog2[server.id]["ban_message"] = default_ban
            self.riceCog2[server.id]["max"] = default_max
        else:
            await self.bot.say("Nevermind then.")
            return

    @_warnset.command(no_pm=True, pass_context=True)
    @checks.admin_or_permissions(ban_members=True, manage_server=True)
    async def message(self, ctx, *, msg=None):
        """Set the warning message

        user.mention - mentions the user
        user.name   - names the user
        user.id     - gets id of user
        warn.count  - gets the # of this warn
        warn.limit  - # of warns allowed

        Example:

        **You, user.mention, have received Warning warn.count. After warn.limit,
        you will be banned.**

        You can set it either for every server.
        To set the ban message, use *warnset ban*
        """
        if not msg:
            await self.bot.say("```Set the warning message\n\n"
                               "user.mention - mentions the user\n"
                               "user.name   - names the user\n"
                               "user.id     - gets id of user\n"
                               "warn.count  - gets the # of this warn\n"
                               "warn.limit  - # of warns allowed\n\n"

                               "Example:\n\n"

                               "**You, user.mention, have received Warning "
                               "warn.count. After warn.limit, you will be "
                               "banned.**\n\n"

                               "You can set it either for every server.\n"
                               "To set the ban message, use *warnset ban*\n```")
            return

        server = ctx.message.server

        self.riceCog2[server.id]["warn_message"] = msg
        dataIO.save_json(self.warning_settings,
                         self.riceCog2)
        await self.bot.say("Warn message is now: \n{}".format(msg))

    async def filter_message(self, msg, user, count, _max):
        msg = msg.replace("user.mention",
                          user.mention)
        msg = msg.replace("user.name",
                          user.name)
        msg = msg.replace("user.id",
                          user.id)
        msg = msg.replace("warn.count",
                          str(count))
        msg = msg.replace("warn.limit",
                          str(_max))
        return msg

    @commands.command(no_pm=True, pass_context=True)
    @checks.admin_or_permissions(ban_members=True)
    async def warn(self, ctx, user: discord.Member, *, reason: str=None):
        """Warns the user - At 3 warnings the user gets banned

        Thank you, 26, for the modlog"""
        server = ctx.message.server
        author = ctx.message.author
        channel = ctx.message.channel

        can_ban = channel.permissions_for(server.me).ban_members
        can_role = channel.permissions_for(server.me).manage_roles

        if reason is None:
            msg = await self.bot.say("Please enter a reason for the warning!")
            await asyncio.sleep(5)
            await self.bot.delete_message(msg)
            return

        if can_ban:
            pass
            await self.bot.delete_message(ctx.message)
        else:
            await self.bot.say("Sorry, I can't warn this user.\n"
                               "I am missing the `ban_members` permission")
            return

        if server.id not in self.riceCog2:
            msg = default_warn
            ban = default_ban
            _max = default_max

        if server.id not in self.riceCog:
            self.riceCog[server.id] = {}

        if 'pm_warn' not in self.riceCog[server.id]:
            self.riceCog[server.id]['pm_warn'] = False

        p = self.riceCog[server.id]['pm_warn']

        try:
            msg = self.riceCog2[server.id]["warn_message"]
        except:
            msg = default_warn
        try:
            ban = self.riceCog2[server.id]["ban_message"]
        except:
            ban = default_ban
        try:
            _max = self.riceCog2[server.id]["max"]
        except:
            _max = default_max

        colour = server.me.colour

        # checks if the user is in the file
        if server.id not in self.riceCog2:
            self.riceCog2[server.id] = {}
            dataIO.save_json(self.warning_settings,
                             self.riceCog2)
        if server.id not in self.riceCog:
            self.riceCog[server.id] = {}
            dataIO.save_json(self.profile,
                             self.riceCog)
            if user.id not in self.riceCog[server.id]:
                self.riceCog[server.id][user.id] = {}
                dataIO.save_json(self.profile,
                                 self.riceCog)
            else:
                pass
        else:
            if user.id not in self.riceCog[server.id]:
                self.riceCog[server.id][user.id] = {}
                dataIO.save_json(self.profile,
                                 self.riceCog)
            else:
                pass

        if "Count" in self.riceCog[server.id][user.id]:
            count = self.riceCog[server.id][user.id]["Count"]
        else:
            count = 0

        cog = self.bot.get_cog('Mod')

        # checks how many warnings the user has
        if count == 0:
            count += 1
            msg = await self.filter_message(msg=msg,
                                            user=user,
                                            count=count,
                                            _max=_max)
            data = discord.Embed(colour=colour)
            data.add_field(name="Warning",
                           value=msg)
            if reason:
                data.add_field(name="Reason",
                               value=reason,
                               inline=False)
            data.set_footer(text=server.name)
            if p:
                await self.bot.send_message(user, embed=data)
                await self.bot.send_message(user, "\n\n*In addition to this you have been muted for 10 minutes as a result of your actions.*")        
                await self._punish_cmd_common(ctx, user, reason=reason, duration=DEFAULT_TIMEOUT)
                mod=author
                user=user
                reason=reason
                ID = uuid.uuid4()
                channel = discord.utils.get(server.channels, name="warning_review")
                embed =  discord.Embed(title="User Warned:", description="**Case ID:** {}\n**Moderator:** {}\n**User:** {}\n**Reason:** {}\n**Warning Number:** {}/3".format(ID, mod, user, reason, count), colour=0xA00000)
                react = await self.bot.send_message(channel, embed=embed)
                await self.bot.add_reaction(react, "\U0001f44d")
                await self.bot.add_reaction(react, "\U0001f44e")
                await self.bot.add_reaction(react, "\U0001f937")
            elif not p:
                await self.bot.send_message(user, embed=data)
                await self.bot.send_message(user, "\n\n*In addition to this you have been muted for 10 minutes as a result of your actions.*")        
                await self._punish_cmd_common(ctx, user, reason=reason, duration=DEFAULT_TIMEOUT)
                mod=author
                user=user
                reason=reason
                ID = uuid.uuid4()
                channel = discord.utils.get(server.channels, name="warning_review")
                embed =  discord.Embed(title="User Warned:", description="**Case ID:** {}\n**Moderator:** {}\n**User:** {}\n**Reason:** {}\n**Warning Number:** {}/3".format(ID, mod, user, reason, count), colour=0xA00000)
                react = await self.bot.send_message(channel, embed=embed)
                await self.bot.add_reaction(react, "\U0001f44d")
                await self.bot.add_reaction(react, "\U0001f44e")
                await self.bot.add_reaction(react, "\U0001f937")

            self.riceCog[server.id][user.id].update({"Count": count})
            dataIO.save_json(self.profile,
                             self.riceCog)
            log = None
            
        elif count == 1:
            count += 1
            msg = await self.filter_message(msg=msg,
                                            user=user,
                                            count=count,
                                            _max=_max)
            data = discord.Embed(colour=colour)
            data.add_field(name="Warning",
                           value=msg)
            if reason:
                data.add_field(name="Reason",
                               value=reason,
                               inline=False)
            data.set_footer(text=server.name)
            if p:
                await self.bot.send_message(user, embed=data)
                mod=author
                user=user
                reason=reason
                ID = uuid.uuid4()
                channel = discord.utils.get(server.channels, name="warning_review")
                embed =  discord.Embed(title="User Warned:", description="**Case ID:** {}\n**Moderator:** {}\n**User:** {}\n**Reason:** {}\n**Warning Number:** {}/3".format(ID, mod, user, reason, count), colour=0xA00000)
                react = await self.bot.send_message(channel, embed=embed)
                await self.bot.add_reaction(react, "\U0001f44d")
                await self.bot.add_reaction(react, "\U0001f44e")
                await self.bot.add_reaction(react, "\U0001f937")
            elif not p:
                await self.bot.say(embed=data)
                mod=author
                user=user
                reason=reason
                ID = uuid.uuid4()
                channel = discord.utils.get(server.channels, name="warning_review")
                embed =  discord.Embed(title="User Warned:", description="**Case ID:** {}\n**Moderator:** {}\n**User:** {}\n**Reason:** {}\n**Warning Number:** {}/3".format(ID, mod, user, reason, count), colour=0xA00000)
                react = await self.bot.send_message(channel, embed=embed)
                await self.bot.add_reaction(react, "\U0001f44d")
                await self.bot.add_reaction(react, "\U0001f44e")
                await self.bot.add_reaction(react, "\U0001f937")
            self.riceCog[server.id][user.id].update({"Count": count})
            dataIO.save_json(self.profile,
                             self.riceCog)
            log = None


        else:
            msg = ban
            msg = await self.filter_message(msg=msg,
                                            user=user,
                                            count=count,
                                            _max=_max)
            data = discord.Embed(colour=colour)
            data.add_field(name="Warning",
                           value=msg)
            if reason:
                data.add_field(name="Reason",
                               value=reason,
                               inline=False)
            data.set_footer(text=server.name)
            if p:
                await self.bot.send_message(user, embed=data)
                mod=author
                user=user
                reason=reason
                channel = discord.utils.get(server.channels, name="warning_review")
                embed = discord.Embed(title="User Banned:", description="**Moderator:** {}\n**User:** {}\n**Reason:** {}\n*As the user has reached 3 warnings they have been banned from the server.*".format(mod, user, reason, count), colour=0xA00000)
                react = await self.bot.send_message(channel, embed=embed)
                await self.bot.add_reaction(react, "\U0001f44d")
                await self.bot.add_reaction(react, "\U0001f44e")
                await self.bot.add_reaction(react, "\U0001f937")
            elif not p:
                await self.bot.say(embed=data)
                mod=author
                user=user
                reason=reason
                channel = discord.utils.get(server.channels, name="warning_review")
                embed = discord.Embed(title="User Banned:", description="**Moderator:** {}\n**User:** {}\n**Reason:** {}\n*As the user has reached 3 warnings they have been banned from the server.*".format(mod, user, reason, count), colour=0xA00000)
                react = await self.bot.send_message(channel, embed=embed)
                await self.bot.add_reaction(react, "\U0001f44d")
                await self.bot.add_reaction(react, "\U0001f44e")
                await self.bot.add_reaction(react, "\U0001f937")
            count = 0
            self.riceCog[server.id][user.id].update({"Count": count})
            dataIO.save_json(self.profile,
                             self.riceCog)
            log = "BAN"

        if 'poop' in self.riceCog2[server.id] and can_role:
            if self.riceCog2[server.id]['poop'] == True:
                poops = count * "\U0001f528"
                role_name = "Warning {}".format(poops)
                is_there = False
                colour = 0xbc7642
                for role in server.roles:
                    if role.name == role_name:
                        poop_role = role
                        is_there = True
                if not is_there:
                    poop_role = await self.bot.create_role(server)
                    await self.bot.edit_role(role=poop_role,
                                             name=role_name,
                                             server=server)
                try:
                    await self.bot.add_roles(user,
                                             poop_role)
                except discord.errors.Forbidden:
                    await self.bot.say("No permission to add roles")

#        if warn:
#        action=warn,
#        mod=author,
#        user=user,
#        reason=reason)
#            await self.bot.message(channel, "{} has warned {} for the reason {}".format{mod, user, reason})

        if (reason and log):
            #await cog.new_case(server=server,
                               #action=log,
                               #mod=author,
                              # user=user,
                              # reason=reason)
            await self.bot.ban(user)
        elif log:
            #await cog.new_case(server=server,
                              # action=log,
                              # user=user,
                              # mod=author,
                              # reason="No reason provided yet.")
            await self.bot.ban(user)

    @commands.command(no_pm=True, pass_context=True)
    @checks.admin_or_permissions(ban_members=True)
    async def remove(self, ctx, user: discord.Member):
        author = ctx.message.author
        server = author.server
        colour = server.me.colour
        channel = ctx.message.channel
        can_role = channel.permissions_for(server.me).manage_roles
        count = self.riceCog[server.id][user.id]["Count"]

        if server.id not in self.riceCog:
            self.riceCog[server.id] = {}
            dataIO.save_json(self.profile,
                             self.riceCog)
            if user.id not in self.riceCog[server.id]:
                self.riceCog[server.id][user.id] = {}
                dataIO.save_json(self.profile,
                                 self.riceCog)
            else:
                pass
        else:
            if user.id not in self.riceCog[server.id]:
                self.riceCog[server.id][user.id] = {}
                dataIO.save_json(self.profile,
                                 self.riceCog)
            else:
                pass
        if 'poop' in self.riceCog2[server.id] and can_role:
            if self.riceCog2[server.id]['poop'] == True:
                try:
                    role = role = list(filter(lambda r: r.name.startswith('Warning \U0001f528'), server.roles))
                    await self.bot.remove_roles(user, *role)
                except discord.errors.Forbidden:
                    await self.bot.say("No permission to add roles")

        if "Count" in self.riceCog[server.id][user.id]:
            count = self.riceCog[server.id][user.id]["Count"]
        else:
            count = 0

        if count != 0:
            msg = await self.bot.say("A warning for {} has been removed!".format(user))
            await self.bot.send_message(user, "Howdy!\nThis is to let you know that your warning on the BNL Server has been reviewed and revoked!\n\n**The BNL Discord Staff**")
            count -= 1
            self.riceCog[server.id][user.id].update({"Count": count})
            dataIO.save_json(self.profile,
                             self.riceCog)
            await asyncio.sleep(15)
            await self.bot.delete_message(msg)
            await self.bot.delete_message(ctx.message)
        else:
            msg = await self.bot.say("You don't have any warnings to clear, "
                               + str(user.mention) + "!")
            await asyncio.sleep(15)
            await self.bot.delete_message(msg)
            await self.bot.delete_message(ctx.message)       

    @commands.command(no_pm=True, pass_context=True)
    @checks.admin_or_permissions(ban_members=True)
    async def clean(self, ctx, user: discord.Member):
        author = ctx.message.author
        server = author.server
        colour = server.me.colour
        channel = ctx.message.channel
        can_role = channel.permissions_for(server.me).manage_roles
        count = self.riceCog[server.id][user.id]["Count"]

        if server.id not in self.riceCog:
            self.riceCog[server.id] = {}
            dataIO.save_json(self.profile,
                             self.riceCog)
            if user.id not in self.riceCog[server.id]:
                self.riceCog[server.id][user.id] = {}
                dataIO.save_json(self.profile,
                                 self.riceCog)
            else:
                pass
        else:
            if user.id not in self.riceCog[server.id]:
                self.riceCog[server.id][user.id] = {}
                dataIO.save_json(self.profile,
                                 self.riceCog)
            else:
                pass
        if 'poop' in self.riceCog2[server.id] and can_role:
            if self.riceCog2[server.id]['poop'] == True:
                try:
                    role = role = list(filter(lambda r: r.name.startswith('Warning \U0001f528'), server.roles))
                    await self.bot.remove_roles(user, *role)
                except discord.errors.Forbidden:
                    await self.bot.say("No permission to add roles")

        if "Count" in self.riceCog[server.id][user.id]:
            count = self.riceCog[server.id][user.id]["Count"]
        else:
            count = 0

        if count != 0:
            msg = await self.bot.say("Warnings for {} have been cleared!".format(user))
            count = 0
            self.riceCog[server.id][user.id].update({"Count": count})
            dataIO.save_json(self.profile,
                             self.riceCog)
            await asyncio.sleep(15)
            await self.bot.delete_message(msg)
            await self.bot.delete_message(ctx.message)
        else:
            msg = await self.bot.say("You don't have any warnings to clear, "
                               + str(user.mention) + "!")
            await asyncio.sleep(15)
            await self.bot.delete_message(msg)
            await self.bot.delete_message(ctx.message)

# clear role
    async def get_role(self, server, quiet=False, create=False):
        default_name = "Muted"
        role_id = self.json.get(server.id, {}).get('ROLE_ID')

        if role_id:
            role = discord.utils.get(server.roles, id=role_id)
        else:
            role = discord.utils.get(server.roles, name=default_name)

        if create and not role:
            perms = server.me.server_permissions
            if not perms.manage_roles and perms.manage_channels:
                await self.bot.say("The Manage Roles and Manage Channels permissions are required to use this command.")
                return None

            else:
                msg = "The %s role doesn't exist; Creating it now..." % default_name

                if not quiet:
                    msgobj = await self.bot.reply(msg)

                log.debug('Creating punish role in %s' % server.name)
                perms = discord.Permissions.none()
                role = await self.bot.create_role(server, name=default_name, permissions=perms)
                await self.bot.move_role(server, role, server.me.top_role.position - 1)

                if not quiet:
                    msgobj = await self.bot.edit_message(msgobj, msgobj.content + 'configuring channels... ')

                for channel in server.channels:
                    await self.setup_channel(channel, role)

                if not quiet:
                    await self.bot.edit_message(msgobj, msgobj.content + 'done.')

        if role and role.id != role_id:
            if server.id not in self.json:
                self.json[server.id] = {}
            self.json[server.id]['ROLE_ID'] = role.id
            self.save()

        return role

    async def on_load(self):
        await self.bot.wait_until_ready()

        for serverid, members in self.json.copy().items():
            server = self.bot.get_server(serverid)
            me = server.me

            # Bot is no longer in the server
            if not server:
                del(self.json[serverid])
                continue

            role = await self.get_role(server, quiet=True, create=True)
            if not role:
                log.error("Needed to create punish role in %s, but couldn't."
                          % server.name)
                continue

            for member_id, data in members.copy().items():
                if not member_id.isdigit():
                    continue

                until = data['until']
                if until:
                    duration = until - time.time()

                member = server.get_member(member_id)
                if until and duration < 0:
                    if member:
                        reason = 'Punishment removal overdue, maybe bot was offline. '
                        if self.json[server.id][member_id]['reason']:
                            reason += self.json[server.id][member_id]['reason']
                        await self._unpunish(member, reason)
                    else:  # member disappeared
                        del(self.json[server.id][member.id])

                elif member and role not in member.roles:
                    if role >= me.top_role:
                        log.error("Needed to re-add punish role to %s in %s, "
                                  "but couldn't." % (member, server.name))
                        continue
                    await self.bot.add_roles(member, role)
                    if until:
                        self.schedule_unpunish(duration, member)

        self.save()

    async def _punish_cmd_common(self, ctx, member, reason, duration, quiet=True):
        server = ctx.message.server
        note = ''

        # if ctx.message.author.top_role <= member.top_role:
        #    await self.bot.say('Permission denied.')
        #    return

        if duration and duration.lower() in ['forever', 'inf', 'infinite']:
            duration = None
        else:
            if not duration:
                note += ' Using default duration of ' + DEFAULT_TIMEOUT
                duration = DEFAULT_TIMEOUT

            try:
                duration = _parse_time(duration)
                if duration < 1:
                    await self.bot.say("Duration must be 1 second or longer.")
                    return False
            except BadTimeExpr as e:
                await self.bot.say("Error parsing duration: %s." % e.args)
                return False

        role = await self.get_role(member.server)
        if role is None:
            return

        if role >= server.me.top_role:
            await self.bot.say('The %s role is too high for me to manage.' % role)
            return

        if server.id not in self.json:
            self.json[server.id] = {}

        if member.id in self.json[server.id]:
            msg = 'User was already punished; resetting their timer...'
        elif role in member.roles:
            msg = 'User was punished but had no timer, adding it now...'
        else:
            msg = 'Done.'

        if note:
            msg += ' ' + note

        if server.id not in self.json:
            self.json[server.id] = {}

        self.json[server.id][member.id] = {
            'until': (time.time() + duration) if duration else None,
            'by': ctx.message.author.id,
            'reason': reason
        }

        await self.bot.add_roles(member, role)
        self.save()

        # schedule callback for role removal
        if duration:
            self.schedule_unpunish(duration, member)

        if not quiet:
            await self.bot.say(msg)

        return True

    def schedule_unpunish(self, delay, member, reason=None):
        """Schedules role removal, canceling and removing existing tasks if present"""
        sid = member.server.id

        if sid not in self.handles:
            self.handles[sid] = {}

        if member.id in self.handles[sid]:
            self.handles[sid][member.id].cancel()

        coro = self._unpunish(member, reason)

        handle = self.bot.loop.call_later(delay, self.bot.loop.create_task, coro)
        self.handles[sid][member.id] = handle

    async def _unpunish(self, member, reason=None):
        """Remove punish role, delete record and task handle"""
        role = await self.get_role(member.server)
        if role:
            # Has to be done first to prevent triggering on_member_update listener
            self._unpunish_data(member)
            await self.bot.remove_roles(member, role)

            msg = 'Your punishment in %s has ended.' % member.server.name
            if reason:
                msg += "\nReason was: %s" % reason

            #await self.bot.send_message(member, msg)
    def _unpunish_data(self, member):
        """Removes punish data entry and cancels any present callback"""
        sid = member.server.id
        if sid in self.json and member.id in self.json[sid]:
            del(self.json[member.server.id][member.id])
            self.save()

        if sid in self.handles and member.id in self.handles[sid]:
            self.handles[sid][member.id].cancel()
            del(self.handles[member.server.id][member.id])

    # Functions related to unpunishing
    async def on_member_update(self, before, after):
        """Remove scheduled unpunish when manually removed"""
        sid = before.server.id

        if not (sid in self.json and before.id in self.json[sid]):
            return
        role = await self.get_role(before.server)
        if role and role in before.roles and role not in after.roles:
            msg = 'Your punishment in %s was ended early by a moderator/admin.' % before.server.name
            if self.json[sid][before.id]:
                msg += '\nReason was: ' + self.json[sid][before.id]

            #await self.bot.send_message(after, msg)
            self._unpunish_data(after)

    async def on_member_join(self, member):
        """Restore punishment if punished user leaves/rejoins"""
        sid = member.server.id
        role = await self.get_role(member.server)
        if not role or not (sid in self.json and member.id in self.json[sid]):
            return

        duration = self.json[sid][member.id]['until'] - time.time()
        if duration > 0:
            await self.bot.add_roles(member, role)

            reason = 'Punishment re-added on rejoin. '
            if self.json[sid][member.id]['reason']:
                reason += self.json[sid][member.id]['reason']

            if member.id not in self.handles[sid]:
                self.schedule_unpunish(duration, member, reason)
    async def WarnDeny
        if #role is mod role then check that the reaction is correct and run remove command.
                
    #async def on_command(self, command, ctx):
     #   if ctx.cog is self:
     #       self.analytics.command(ctx)
def compat_load(path):
    data = dataIO.load_json(path)
    for server, punishments in data.items():
        for user, pdata in punishments.items():
            if not user.isdigit():
                continue
            by = pdata.pop('givenby', None)  # able to read Kownlin json
            by = by if by else pdata.pop('by', None)
            pdata['by'] = by
            pdata['until'] = pdata.pop('until', None)
            pdata['reason'] = pdata.pop('reason', None)
    return data


def check_folder():
    if not os.path.exists("data/account"):
        print("Creating data/account/server.id folder")
        os.makedirs("data/account")
    if not os.path.exists(PATH):
        log.debug('Creating folder: data/account')
        os.makedirs(PATH)


def check_file():
    data = {}
    f = "data/account/warnings.json"
    g = "data/account/warning_settings.json"
    if not dataIO.is_valid_json(f):
        print("Creating data/account/warnings.json")
        dataIO.save_json(f,
                         data)
    if not dataIO.is_valid_json(g):
        print("Creating data/account/warning_settings.json")
        dataIO.save_json(g,
                         data)
    if not dataIO.is_valid_json(JSON):
        print('Creating empty %s' % JSON)
        dataIO.save_json(JSON, {})

def setup(bot):
    check_folder()
    check_file()
    bot.add_cog(Warn(bot))
    bot.add_listener(n.WarnDeny, 'on_reaction_add')
    
    
