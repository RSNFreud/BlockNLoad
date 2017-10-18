import discord
from discord.ext import commands
from .utils.dataIO import dataIO 
from .utils import checks
import asyncio
import discord
import random
from discord.ext.commands.cooldowns import BucketType

class custom:
    """Custom game caller"""

    def __init__(self, bot):
        self.bot = bot
    @commands.cooldown(1,60,BucketType.user) 
# Limit how often a command can be used, (num per, seconds, Buckettype.default/user/disckserver/channel)
    @commands.command(aliases=["custom"], pass_context=True, no_pm=True)
    async def customs(self, ctx, password : str = None,  user : str = None, gamename : str = None):
        if password is None:
            embed = discord.Embed(colour=0x146b85, description="This command has several options.\n\n1. **!customs password** - This posts the custom as you hosting with the password you set in the command.\n2. **!customs password user** - This posts the custom with the password you set and the user you chose.\n3. **!customs password user customname**  - This posts the custom as the user you chose (has to be in the server) with the password and gamename you set.")
            msg = await self.bot.say(embed=embed)
            ctx.command.reset_cooldown(ctx)
            await asyncio.sleep(300)
            try:    
                await self.bot.delete_message(ctx.message)
                await self.bot.delete_message(msg)
            except discord.errors.NotFound:
                pass
            except UnboundLocalError:
                pass    
        else:
            server = ctx.message.server
            role = discord.utils.get(server.roles, name="Customs")
            if not user:
                user = ctx.message.author 
            if gamename is None:
                gamename = "a custom"
            embed = discord.Embed(colour=0x146b85, description="**%s** is hosting %s. The password is **%s**. To randomly pick a map use !map" % (user, gamename, password))  # Can use discord.Colour()
            embed.title = "New Custom Game!"
            embed.set_footer(text="To be notified or to not be notified for customs use ?rank Customs")
            try:
                await self.bot.edit_role(server, role)
            except AttributeError: 
                await self.bot.say("Make sure you have a role called Customs!")
            except discord.errors.Forbidden:
                await self.bot.say("Make sure I have **Manage Roles** permissions and my role is higher than the custom role!")
            else:
                await self.bot.delete_message(ctx.message)
                await self.bot.edit_role(server, role, mentionable=True)
                bmsg = await self.bot.say(role.mention, embed=embed)
                await self.bot.edit_role(server, role, mentionable=False)
                await asyncio.sleep(5)
            try:
                await self.bot.edit_role(server, role, mentionable=True)
                embed2 = discord.Embed(colour=0x146b85, description="This custom game is full! To get notified for when there are custom games use ?rank customs")
                await self.bot.edit_message(bmsg, role.mention, embed=embed2)
                await self.bot.edit_role(server, role, mentionable=False)
#                await self.bot.delete_message(bmsg)
            except discord.errors.NotFound:
                pass
            except UnboundLocalError:
                pass
        
    @commands.command(pass_context=True, no_pm=True)
    async def map(self, ctx):
        """Choose a random map"""
        maps = random.choice(["Mountain Express","Stone Temple","Block Docks","Beach Base","Blockageddon","Phaeton Complex","Sandy Shores","Shuko Style","Sky Bridge","Wilson's Bay","Cube Cove \nhttps://goo.gl/AiEZTb","Block Keep","Mount Olympus \n https://goo.gl/AiEZTb","Castle Ruins \nhttps://goo.gl/bR8ymQ"])
        msg = await self.bot.say("**" + maps + "**")
        await asyncio.sleep(300)
        try:
            await self.bot.delete_message(msg)
            await self.bot.delete_message(ctx.message)
        except discord.errors.NotFound:
            pass
        except UnboundLocalError:
            pass
    @commands.command(pass_context=True, no_pm=True)
    async def flip(self, ctx):
        """Choose a random team"""    
        team = random.choice(["**Team A**", "**Team 1**"])
        msg = await self.bot.say(team)
        await asyncio.sleep(300)
        try:
            await self.bot.delete_message(msg)
            await self.bot.delete_message(ctx.message)
        except discord.errors.NotFound:
            pass
        except UnboundLocalError:
            pass
    @commands.command(pass_context=True, no_pm=True)
    async def draw(self, ctx):
        """Choose a random team and map"""    
        team = random.choice(["**Team A**", "**Team 1**"])
        maps = random.choice(["Mountain Express","Stone Temple","Block Docks","Beach Base","Blockageddon","Phaeton Complex","Sandy Shores","Shuko Style","Sky Bridge","Wilson's Bay","Cube Cove \n https://goo.gl/AiEZTb","Block Keep","Mount Olympus \n https://goo.gl/AiEZTb","Castle Ruins \n https://goo.gl/bR8ymQ"])

        msg = await self.bot.say("**" + maps + "** - " + team)
        await asyncio.sleep(300)
        try:
            await self.bot.delete_message(msg)
            await self.bot.delete_message(ctx.message)
        except discord.errors.NotFound:
            pass
        except UnboundLocalError:
            pass
def setup(bot):
    bot.add_cog(custom(bot))
 
