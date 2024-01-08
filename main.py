import asyncio

from discord import Intents, PermissionOverwrite, Permissions, option

import config
from config import *
import discord
from discord.ext import commands
import discord_bot

from discord_permissions import DP
from models import EarningSubmission, User, AdminTransaction, TransactionLog
from ui import EarningPointsLodged, register_views


def run_bot():
    bot = discord_bot.bot

    @bot.event
    async def on_ready():
        register_views(bot)
        print("Bot Ready")

    import commands

    bot.run(config.DISCORD_TOKEN)



if __name__ == '__main__':
    run_bot()
