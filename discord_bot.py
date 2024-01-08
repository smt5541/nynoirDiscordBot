from typing import Optional

import discord.utils
from discord import NotFound, HTTPException
from discord.ext import commands

import config

bot = commands.Bot()


async def get_role_by_name(name):
    guild = bot.get_guild(int(config.DISCORD_SERVER_ID))
    roles = await guild.fetch_roles()
    for role in roles:
        if role.name == name:
            return role
    return None


async def get_or_create_category(name):
    guild = bot.get_guild(int(config.DISCORD_SERVER_ID))
    for category in guild.categories:
        if category.name == name:
            return category
    category = await guild.create_category(name)
    return category


async def get_user(id) -> Optional[discord.User]:
    user = bot.get_user(id)
    if not user:
        try:
            user = await bot.fetch_user(id)
            return user
        except (NotFound, HTTPException):
            return None
    return user
