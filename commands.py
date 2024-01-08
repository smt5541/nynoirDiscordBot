from typing import Optional

import discord
from discord import PermissionOverwrite, Permissions, option

import config
import discord_bot
from discord_bot import bot
from discord_permissions import DP
from exceptions import PaginationError
from models import User, EarningSubmission, AdminTransaction, TransactionLog, SpendingSubmission
from ui import register_views, EarningPointsLodged, generate_leaderboard_embed, LeaderboardPaginationButtons, \
    SpendingAbilityInfoButton, generate_transaction_log_embed, TransactionLogPaginationButtons, generate_earning_embed, \
    generate_spending_embed, generate_admin_transaction_embed, generate_admin_transaction_log_embed, \
    AdminTransactionLogPaginationButtons, generate_users_embed, UserPaginationButtons


@bot.slash_command(name="earning_submission", guild_ids=[config.DISCORD_SERVER_ID])
async def earning_submission(ctx):
    await ctx.response.defer(ephemeral=True)
    user = User.get_or_create(ctx.author.id)
    next_submission_id = EarningSubmission.get_next_id()
    guild = bot.get_guild(int(config.DISCORD_SERVER_ID))
    if guild:
        role_everyone = await discord_bot.get_role_by_name("@everyone")
        channel = await (
            guild.create_text_channel(
            f"earning-{next_submission_id}",
                overwrites={
                    role_everyone: PermissionOverwrite.from_pair(
                        Permissions.none(),
                        Permissions.all()
                    ),
                    ctx.author: PermissionOverwrite.from_pair(
                        Permissions(DP.SEND_MESSAGES | DP.VIEW_CHANNEL),
                        Permissions(~(DP.SEND_MESSAGES | DP.VIEW_CHANNEL))
                    )
                },
                category=await discord_bot.get_or_create_category("submissions")
            )
        )
        EarningSubmission.create(channel.id, user.id)
        await ctx.followup.send(channel.mention)
        await channel.send("How many points would you like to lodge?", view=EarningPointsLodged())
    else:
        await ctx.followup.send("Failed to get Guild")


@bot.slash_command(name="balance", guild_ids=[config.DISCORD_SERVER_ID])
@option("user",
        discord.User,
        required=False,
        description="User to get balance of")
async def balance(ctx, user: discord.User):
    if user:
        db_user = User.get_or_create(user.id)
        await ctx.respond(f"{user.name}'s Judgement Point balance is: `{db_user.judgement_points}`")
    else:
        db_user = User.get_or_create(ctx.author.id)
        await ctx.respond(f"Your Judgement Point balance is: `{db_user.judgement_points}`")


@bot.slash_command(name="admin_transaction", guild_ids=[config.DISCORD_SERVER_ID])
@option("user",
        discord.User,
        description="User to modify balance of")
@option("action",
        choices=["+", "-", "="],
        description="Whether to add, remove, or set balance")
@option("amount",
        type=int,
        min_value=0,
        description="The amount of points to use in this transaction")
@option("reason",
        description="The reason this transaction is being performed")
async def admin_transaction(ctx, user: discord.User, action, amount, reason):
    await ctx.response.defer(ephemeral=True)
    calling_user = User.get_or_create(ctx.author.id)
    if not calling_user.is_admin:
        await ctx.followup.send("You are not authorized to perform this action")
        return
    db_user = User.get_or_create(user.id)
    db_admin_user = User.get_or_create(ctx.author.id)
    result_points = db_user.judgement_points
    description = f", user {user.name}'s balance has "
    if action == "+":
        result_points += amount
        description += f"been increased by {amount} points"
    elif action == "-":
        result_points -= amount
        description += f"been decreased by {amount} points"
    else:
        result_points = amount
        description += f"been set to {amount} points"
    description += f", balance is now {result_points} points."
    net_points = result_points - db_user.judgement_points
    admin_transaction_id = AdminTransaction.create(db_user.id, db_admin_user.id, net_points, reason)
    TransactionLog.create_from_admin_transaction(AdminTransaction.get_by_id(admin_transaction_id))
    await ctx.followup.send("Admin Transaction Performed" + description)

@bot.slash_command(name="admin_transaction_log", guild_ids=[config.DISCORD_SERVER_ID])
@option("target_user",
        type=discord.User,
        description="The targeted user to query admin transactions for",
        required=False)
@option("admin_user",
        type=discord.User,
        description="The admin user to query admin transactions for",
        required=False)
@option("page",
        type=int,
        min_value=1,
        description="The page of the Admin Transaction Log to view",
        required=False)
async def admin_transaction_log(ctx, target_user: discord.User=None, admin_user:discord.User=None, page=1):
    calling_user = User.get_or_create(ctx.author.id)
    if not calling_user.is_admin:
        await ctx.response.send_message("You are not authorized to perform this action")
        return
    db_target_user = None
    if target_user:
        db_target_user = User.get_or_create(target_user.id)
    db_admin_user = None
    if admin_user:
        db_admin_user = User.get_or_create(admin_user.id)
    try:
        await ctx.response.defer(ephemeral=True)
        await ctx.followup.send(embed=await generate_admin_transaction_log_embed(page, target=db_target_user, admin=db_admin_user), view=AdminTransactionLogPaginationButtons())
    except PaginationError as e:
        await ctx.followup.send(e.message)

@bot.slash_command(name="leaderboard", guild_ids=[config.DISCORD_SERVER_ID])
@option("page",
        type=int,
        min_value=1,
        description="The page of the Leaderboard to view",
        required=False
)
async def leaderboard(ctx, page):
    if page is None:
        page = 1
    try:
        await ctx.respond(embeds=[await generate_leaderboard_embed(page)], view=LeaderboardPaginationButtons())
    except PaginationError as e:
        await ctx.respond(e.message)


@bot.slash_command(name="transaction_log", guild_ids=[config.DISCORD_SERVER_ID])
@option("user", discord.User, description="The user to retrieve the Transaction Log for")
@option("page",
        type=int,
        min_value=1,
        description="The page of the Transaction Log to view",
        required=False
)
async def transaction_log(ctx, user: discord.User, page=1):
    calling_user = User.get_or_create(ctx.author.id)
    if not calling_user.is_admin:
        await ctx.response.send_message("You are not authorized to perform this action")
        return
    db_user = User.get_or_create(user.id)
    try:
        await ctx.response.defer(ephemeral=True)
        await ctx.followup.send(embed=await generate_transaction_log_embed(page, user=db_user), view=TransactionLogPaginationButtons())
    except PaginationError as e:
        await ctx.followup.send(e.message)


@bot.slash_command(name="inspect", guild_ids=[config.DISCORD_SERVER_ID])
@option("record_type",
        choices=["Earning Submission", "Spending Submission", "Admin Transaction"],
        description="The type of record to inspect")
@option("record_id",
        type=int,
        min_value=0,
        description="The ID of the record to inspect")
async def inspect(ctx, record_type, record_id):
    await ctx.response.defer(ephemeral=True)
    calling_user = User.get_or_create(ctx.author.id)
    if not calling_user.is_admin:
        await ctx.followup.send("You are not authorized to perform this action")
        return
    if record_type == "Earning Submission":
        submission = EarningSubmission.get_by_id(record_id)
        if submission:
            await ctx.followup.send(embed=await generate_earning_embed(submission, "Inspecting Earning Submission"))
        else:
            await ctx.followup.send(f"Earning Submission #{record_id} does not exist!")
    elif record_type == "Spending Submission":
        submission = SpendingSubmission.get_by_id(record_id)
        if submission:
            await ctx.followup.send(embed=await generate_spending_embed(submission, "Inspecting Spending Submission"))
        else:
            await ctx.followup.send(f"Spending Submission #{record_id} does not exist!")
    else:
        transaction = AdminTransaction.get_by_id(record_id)
        if transaction:
            await ctx.followup.send(embed=await generate_admin_transaction_embed(transaction, "Inspecting Admin Transaction"))
        else:
            await ctx.followup.send(f"Admin Transaction #{record_id} does not exist!")


@bot.slash_command(name="spending_submission", guild_ids=[config.DISCORD_SERVER_ID])
async def spending_submission(ctx):
    await ctx.response.defer(ephemeral=True)
    user = User.get_or_create(ctx.author.id)
    if user.judgement_points >= 200:
        next_submission_id = SpendingSubmission.get_next_id()
        guild = bot.get_guild(int(config.DISCORD_SERVER_ID))
        if guild:
            role_everyone = await discord_bot.get_role_by_name("@everyone")
            channel = await (
                guild.create_text_channel(
                f"spending-{next_submission_id}",
                    overwrites={
                        role_everyone: PermissionOverwrite.from_pair(
                            Permissions.none(),
                            Permissions.all()
                        ),
                        ctx.author: PermissionOverwrite.from_pair(
                            Permissions(DP.SEND_MESSAGES | DP.VIEW_CHANNEL),
                            Permissions(~(DP.SEND_MESSAGES | DP.VIEW_CHANNEL))
                        )
                    },
                    category=await discord_bot.get_or_create_category("submissions")
                )
            )
            SpendingSubmission.create(channel.id, user.id)
            await ctx.followup.send(channel.mention)
            await channel.send("Click the button below to enter your Ability information", view=SpendingAbilityInfoButton())
        else:
            await ctx.followup.send("Failed to get Guild")
    else:
        await ctx.followup.send(f"You don't have enough Judgement Points to create a Spending Submission. Your current balance is `{user.judgement_points}` Points")

@bot.slash_command(name="set_visibility", guild_ids=[config.DISCORD_SERVER_ID])
@option("visibility", choices=["visible", "invisible"], description="The visibility the user should have on the Leaderboard")
@option("user", discord.User, description="The user to set the visibility of, if they are a member of the server", required=False)
@option("user_id", type=int, min_value=0, description="The NY Noir ID of the user (from /users) to set the visibility of", required=False)
async def set_visibility(ctx, visibility, user: Optional[discord.User], user_id: Optional[int]):
    await ctx.response.defer(ephemeral=True)
    calling_user = User.get_or_create(ctx.author.id)
    if not calling_user.is_admin:
        await ctx.followup.send("You are not authorized to perform this action")
        return
    if user:
        db_user = User.get_or_create(user.id)
        User.set_visible_by_discord_id(user.id, True if visibility == "visible" else False)
        await ctx.followup.send(f"Visibility updated! NY Noir user #{db_user.id} ({user.name}) has been set to {visibility}")
    elif user_id:
        db_user = User.get_by_id(user_id)
        if db_user:
            User.set_visible(user_id, True if visibility == "visible" else False)
            user = await bot.fetch_user(db_user.discord_id)
            await ctx.followup.send(f"Visibility updated! NY Noir user #{db_user.id} ({user.name}) has been set to {visibility}")
        else:
            await ctx.followup.send(f"No NY Noir user exists with User ID #{user_id}")
    else:
        await ctx.followup.send("Either `user` or `user_id` must be provided")


@bot.slash_command(name="set_user_privs", guild_ids=[config.DISCORD_SERVER_ID])
@option("user_privs", choices=["user", "bot admin"], description="The privileges this user has to this Bot")
@option("user", discord.User, description="The user to set the admin status of, if they are a member of the server", required=False)
@option("user_id", type=int, min_value=0, description="The NY Noir ID of the user (from /users) to set the admin status of", required=False)
async def set_user_privs(ctx, user_privs, user: Optional[discord.User], user_id: Optional[int]):
    await ctx.response.defer(ephemeral=True)
    calling_user = User.get_or_create(ctx.author.id)
    if not calling_user.is_admin:
        await ctx.followup.send("You are not authorized to perform this action")
        return
    if user:
        db_user = User.get_or_create(user.id)
        User.set_admin_by_discord_id(user.id, True if user_privs == "bot admin" else False)
        await ctx.followup.send(f"Privileges updated! NY Noir user #{db_user.id} ({user.name}) has been set to {user_privs}")
    elif user_id:
        db_user = User.get_by_id(user_id)
        if db_user:
            User.set_admin(user_id, True if user_privs == "bot admin" else False)
            user = await bot.fetch_user(db_user.discord_id)
            await ctx.followup.send(f"Privileges updated! NY Noir user #{db_user.id} ({user.name}) has been set to {user_privs}")
        else:
            await ctx.followup.send(f"No NY Noir user exists with User ID #{user_id}")
    else:
        await ctx.followup.send("Either `user` or `user_id` must be provided")

@bot.slash_command(name="users", guild_ids=[config.DISCORD_SERVER_ID])
@option("user_type", choices=["all", "user", "bot admin"], description="The type of users to show")
@option("page",
        type=int,
        min_value=1,
        description="The page of the Users List to view",
        required=False
)
async def users(ctx, user_type, page=1):
    await ctx.response.defer(ephemeral=True)
    calling_user = User.get_or_create(ctx.author.id)
    if not calling_user.is_admin:
        await ctx.followup.send("You are not authorized to perform this action")
        return
    admin = None
    if user_type == "user":
        admin = False
    elif user_type == "bot admin":
        admin = True
    try:
        await ctx.followup.send(embed=await generate_users_embed(page, admin=admin), view=UserPaginationButtons())
    except PaginationError as e:
        await ctx.followup.send(e.message)
