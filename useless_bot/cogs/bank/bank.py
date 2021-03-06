import logging
from time import time
from typing import Union, Optional

import nextcord
from nextcord import Embed
from nextcord.ext import commands
from nextcord.ext.commands import Bot, group, Context, CommandError
from nextcord.utils import get

from useless_bot.core.bank_core import BankCore
from useless_bot.core.config import Config
from useless_bot.core.errors import *
from useless_bot.utils import on_global_command_error

schema = {"free_credits": 15}
logger = logging.getLogger("useless_bot.cog.bank")

__all__ = ["Bank"]


class Bank(commands.Cog, name="Bank"):
    """A discord-to-bank interface"""

    def __init__(self, bot: Bot, bank: BankCore):
        self.bot = bot

        self.config = Config(cog="Bank", schema=schema)

        # bank init
        self._bank = bank

    async def cog_command_error(self, ctx: Context, error: CommandError):
        if isinstance(error, BalanceUnderLimitError):
            await ctx.send("You don't have enough credits")
        elif isinstance(error, BalanceOverLimitError):
            await ctx.send("You have too much credits")
        elif isinstance(error, KeyError):
            await ctx.send("It doesn't seem you have a bank. Use `-bank` to create one")
        else:
            if not await on_global_command_error(ctx, error):
                logger.error(f"Exception occurred", exc_info=True)

    @staticmethod
    def gen_wait_str(seconds: int):
        seconds = 86400 - seconds
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)

        if hours > 0:
            return f"You need to wait {hours} hours"
        if minutes > 0:
            return f"You need to wait {minutes} minutes"

        return f"You need to wait {seconds} seconds"

    @group(invoke_without_command=True, usage="")
    async def bank(self, ctx: Context, user: Optional[Union[nextcord.User, nextcord.Member]] = None):
        """Get your bank page"""
        if user is not None and ctx.author.guild_permissions.administrator:
            pass
        else:
            user = ctx.author

        author_account = await self._bank.get_user(user)
        seconds = int(time()) - author_account.last_free_credits

        if seconds > 86400:
            free_cr_text = f"Use `{ctx.prefix}bank free` to reclaim your free daily credits"
        else:
            free_cr_text = self.gen_wait_str(seconds)

        embed = Embed()
        embed.title = "Bank Status"
        embed.description = f"Bank status of {user.mention}"
        embed.add_field(
            name="Credits", value=f"`{author_account.balance}`", inline=False
        )
        embed.add_field(name="Free credits", value=free_cr_text, inline=False)

        await ctx.send(embed=embed)

    @bank.command()
    async def free(self, ctx: Context):
        """Get your daily free credits"""
        user = ctx.author
        seconds = int(time()) - await self._bank.last_free_credits(user)

        free_credits = await self.config.get(["free_credits"])

        if seconds > 86400:
            await self._bank.deposit(user=user, value=free_credits)
            await self._bank.update_last_free_credits(user=user, new_time=int(time()))
            await ctx.send(
                f"Added {free_credits} credits to your account"
            )
        else:
            await ctx.send(self.gen_wait_str(seconds))

    @commands.is_owner()
    @bank.command()
    async def add(self, ctx: Context, user: Union[nextcord.User, nextcord.Member], value: int):
        """Add some bank to a user. WARNING: this will cause inflation"""
        await self._bank.deposit(user=user, value=value)
        await ctx.send(f"Added {value} credits to {user.mention}")

    @commands.is_owner()
    @bank.command()
    async def remove(self, ctx: Context, user: Union[nextcord.User, nextcord.Member], value: int):
        """Remove bank from a user. WARNING: this will cause inflation"""
        await self._bank.withdraw(user=user, value=value)
        await ctx.send(f"Removed {value} credits from {user.mention}")

    @commands.is_owner()
    @bank.command(hidden=True)
    async def cleanup(self, ctx: Context):
        members = list(self.bot.get_all_members())
        i = 0
        async for user_id in self._bank.users:
            if get(members, id=user_id) is None:
                await self._bank.del_user(user_id)
                i += 1

        await ctx.send(f"Bank database cleaned from {i} users")

    @commands.is_owner()
    @bank.command()
    async def reset(self, ctx: Context):
        await self._bank.clear()
        await ctx.send("Cleared database")

    @bank.command()
    async def move(self, ctx: Context, user: Union[nextcord.User, nextcord.Member], value: int):
        value = abs(value)  # prevent bank stealing
        await self._bank.move(from_user=ctx.author, to_user=user, value=value)
        await ctx.send(f"Moved {value} credits to {user.mention}")
