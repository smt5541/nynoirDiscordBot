import asyncio
from typing import Callable

import discord.ui
from discord import ComponentType, SelectOption, ButtonStyle, Emoji, InputTextStyle, PermissionOverwrite, Permissions
from discord.embeds import EmptyEmbed
from discord.ui import Item

import config
import discord_bot
from discord_bot import bot
from discord_permissions import DP
from exceptions import PaginationError
from models import EarningSubmission, LocationAlignment, User, TransactionLog, SpendingSubmission, AdminTransaction

alignment_short_label = ["In Alignment", "In Contravention", "Not Applicable"]


async def generate_earning_embed(submission, title):
    embed = discord.Embed(title=f"{title} #{submission.id}")
    embed.add_field(name="Points Lodged", value=f"{submission.points_lodged} Points", inline=False)
    embed.add_field(name="Act Summary", value=submission.act_summary, inline=False)
    embed.add_field(name="Location Alignment", value=alignment_short_label[submission.location_alignment.value],
                    inline=False)
    if submission.approved is not None:
        embed.add_field(name="Approved", value="Yes" if submission.approved else "No", inline=False)
    if submission.denied_reason:
        embed.add_field(name="Denial Reason", value=submission.denied_reason, inline=False)
    user_discord_id = User.get_by_id(submission.user_id).discord_id
    discord_user = await bot.fetch_user(int(user_discord_id))
    embed.set_author(name=discord_user.name, url=discord_user.jump_url,
                     icon_url=discord_user.avatar.url if discord_user.avatar else EmptyEmbed)
    return embed


async def generate_spending_embed(submission, title):
    embed = discord.Embed(title=f"{title} #{submission.id}")
    embed.add_field(name="Ability Requested", value=submission.ability_requested, inline=False)
    embed.add_field(name="Description of Ability", value=submission.ability_description, inline=False)
    embed.add_field(name="Scope/Limitations of Ability", value=submission.ability_limitations, inline=False)
    embed.add_field(name="Cost or Balancing Weakness", value=submission.cost_weakness, inline=False)
    embed.add_field(name="Description of Cost or Balancing Weakness", value=submission.cost_weakness_description,
                    inline=False)
    embed.add_field(name="Is the ability Lore/Rule Compliant?", value="Yes" if submission.lore_rule_compliant else "No",
                    inline=False)
    if submission.approved is not None:
        embed.add_field(name="Approved", value="Yes" if submission.approved else "No", inline=False)
    if submission.denied_reason:
        embed.add_field(name="Denial Reason", value=submission.denied_reason, inline=False)
    user_discord_id = User.get_by_id(submission.user_id).discord_id
    discord_user = await bot.fetch_user(int(user_discord_id))
    embed.set_author(name=discord_user.name, url=discord_user.jump_url,
                     icon_url=discord_user.avatar.url if discord_user.avatar else EmptyEmbed)
    return embed


async def generate_leaderboard_embed(page):
    leaderboard_db_users = User.get_leaderboard(page)
    leaderboard_text = ""
    leaderboard = []
    max_place_len = 0
    max_points_len = 0
    for index, db_user in enumerate(leaderboard_db_users):
        user = await bot.fetch_user(db_user.discord_id)
        place = ((page - 1) * 10) + index + 1
        points = db_user.judgement_points
        leaderboard.append({"place": place, "points": points,
                            "name": f"{user.name}{'#' + user.discriminator if user.discriminator != '0' else ''}"})
        if len(str(place)) > max_place_len:
            max_place_len = len(str(place))
        if len(str(points)) > max_points_len:
            max_points_len = len(str(points))
    for leader in leaderboard:
        place = leader["place"]
        points = leader["points"]
        name = leader["name"]
        leaderboard_text += f"#{place}{' ' * (max_place_len - len(str(place)))} | {points}{' ' * (max_points_len - len(str(points)))} - {name}\n"
    embed = discord.Embed(title=f"Leaderboard - Page {page}")
    embed.add_field(name="", value=f"```{leaderboard_text}```")
    return embed


async def generate_transaction_log_embed(page, interaction: discord.Interaction = None, user: User = None):
    if interaction:
        user_discord_id = interaction.message.embeds[0].author.url.split("/")[-1]
        user = User.get_or_create(user_discord_id)
    db_transactions = TransactionLog.search_by_user(user.id, page=page)
    transactions = [{"id": "ID", "ts": "Timestamp", "amount": "Amount", "ref": "Reference"}]
    log_text = ""
    max_id_len = len(transactions[0]["id"])
    max_ts_len = len(transactions[0]["ts"])
    max_amount_len = len(transactions[0]["amount"])
    max_ref_len = len(transactions[0]["ref"])
    for index, db_txn in enumerate(db_transactions):
        ref = ""
        if db_txn.admin_transaction_id:
            ref = f"Admin Txn #{db_txn.admin_transaction_id}"
        elif db_txn.earning_submission_id:
            ref = f"Earn Sub #{db_txn.earning_submission_id}"
        elif db_txn.spending_submission_id:
            ref = f"Spend Sub #{db_txn.spending_submission_id}"
        transactions.append({"id": db_txn.id, "ts": db_txn.timestamp.isoformat(),
                             "amount": f"{'+' if db_txn.judgement_points > 0 else ''}{db_txn.judgement_points}",
                             "ref": ref})
        if len(str(transactions[-1]["id"])) > max_id_len:
            max_id_len = len(str(transactions[-1]["id"]))
        if len(str(transactions[-1]["ts"])) > max_ts_len:
            max_ts_len = len(str(transactions[-1]["ts"]))
        if len(str(transactions[-1]["amount"])) > max_amount_len:
            max_amount_len = len(str(transactions[-1]["amount"]))
        if len(str(transactions[-1]["ref"])) > max_ref_len:
            max_ref_len = len(str(transactions[-1]["ref"]))
    for txn in transactions:
        id = txn["id"]
        ts = txn["ts"]
        amount = txn["amount"]
        ref = txn["ref"]
        log_text += f"{id}{' ' * (max_id_len - len(str(id)))} | {ts}{' ' * (max_ts_len - len(str(ts)))} | {amount}{' ' * (max_amount_len - len(str(amount)))} | {ref}\n"
    embed = discord.Embed(title=f"Transaction Log - Page {page}")
    embed.add_field(name="", value=f"```{log_text}```")
    discord_user = await bot.fetch_user(int(user.discord_id))
    embed.set_author(name=discord_user.name, url=discord_user.jump_url,
                     icon_url=discord_user.avatar.url if discord_user.avatar else EmptyEmbed)
    return embed


async def generate_admin_transaction_embed(transaction, title):
    embed = discord.Embed(title=f"{title} #{transaction.id}")
    embed.add_field(name="Timestamp", value=transaction.timestamp.isoformat(), inline=False)
    target_user = User.get_by_id(transaction.user_id)
    embed.add_field(name="Target User", value=f"<@{target_user.discord_id}>", inline=False)
    embed.add_field(name="Balance Changes",
                    value=f"{'+' if transaction.net_points >= 0 else ''}{transaction.net_points}")
    admin_user = User.get_by_id(transaction.admin_user_id)
    embed.add_field(name="Performed by Admin", value=f"<@{admin_user.discord_id}>", inline=False)
    embed.add_field(name="Reason", value=transaction.reason, inline=False)
    return embed


async def generate_admin_transaction_log_embed(page, interaction: discord.Interaction = None, target: User = None,
                                               admin: User = None):
    embed = discord.Embed(title=f"Admin Transaction Log - Page {page}")
    target_discord = None
    if target:
        target_discord = await bot.fetch_user(target.discord_id)
        embed.add_field(name="Target User", value=target_discord.mention, inline=False)
    admin_discord = None
    if admin:
        admin_discord = await bot.fetch_user(admin.discord_id)
        embed.add_field(name="Admin User", value=admin_discord.mention, inline=False)
    if interaction:
        for field in interaction.message.embeds[0].fields:
            if field.name == "Target User":
                target_discord_id = field.value.strip("<@>")
                target_discord = await bot.fetch_user(int(target_discord_id))
                target = User.get_or_create(target_discord_id)
            elif field.name == "Admin User":
                admin_discord_id = field.value.strip("<@>")
                admin_discord = await bot.fetch_user(int(admin_discord_id))
                admin = User.get_or_create(admin_discord_id)
    db_transactions = AdminTransaction.search(target=target, admin=admin, page=page)
    transactions = [{"id": "ID", "ts": "Timestamp", "amount": "Amount", "by": "By", "on": "On"}]
    log_text = ""
    max_id_len = len(transactions[0]["id"])
    max_ts_len = len(transactions[0]["ts"])
    max_amount_len = len(transactions[0]["amount"])
    max_by_len = len(transactions[0]["by"])
    max_on_len = len(transactions[0]["on"])
    for index, db_txn in enumerate(db_transactions):
        on = ""
        if target:
            on = target_discord.name + (
                f"#{target_discord.discriminator}" if target_discord.discriminator != '0' else '')
        else:
            on_discord = await discord_bot.get_user(User.get_by_id(db_txn.user_id).discord_id)
            on = on_discord.name + (f"#{on_discord.discriminator}" if on_discord.discriminator != '0' else '')
        by = ""
        if admin:
            by = admin_discord.name + (f"#{admin_discord.discriminator}" if admin_discord.discriminator != '0' else '')
        else:
            by_discord = await discord_bot.get_user(User.get_by_id(db_txn.admin_user_id).discord_id)
            by = by_discord.name + (f"#{by_discord.discriminator}" if by_discord.discriminator != '0' else '')
        transactions.append({"id": db_txn.id, "ts": db_txn.timestamp.isoformat(),
                             "amount": f"{'+' if db_txn.net_points > 0 else ''}{db_txn.net_points}", "by": by,
                             "on": on})
        if len(str(transactions[-1]["id"])) > max_id_len:
            max_id_len = len(str(transactions[-1]["id"]))
        if len(str(transactions[-1]["ts"])) > max_ts_len:
            max_ts_len = len(str(transactions[-1]["ts"]))
        if len(str(transactions[-1]["amount"])) > max_amount_len:
            max_amount_len = len(str(transactions[-1]["amount"]))
        if len(str(transactions[-1]["on"])) > max_on_len:
            max_on_len = len(str(transactions[-1]["on"]))
        if len(str(transactions[-1]["by"])) > max_by_len:
            max_by_len = len(str(transactions[-1]["by"]))
    for txn in transactions:
        id = txn["id"]
        ts = txn["ts"]
        amount = txn["amount"]
        on = txn["on"]
        by = txn["by"]
        if admin and target:
            log_text += f"{id}{' ' * (max_id_len - len(str(id)))} | {ts}{' ' * (max_ts_len - len(str(ts)))} | {amount}{' ' * (max_amount_len - len(str(amount)))}\n"
        elif admin:
            log_text += f"{id}{' ' * (max_id_len - len(str(id)))} | {ts}{' ' * (max_ts_len - len(str(ts)))} | {amount}{' ' * (max_amount_len - len(str(amount)))} | {on}{' ' * (max_on_len - len(str(on)))}\n"
        elif target:
            log_text += f"{id}{' ' * (max_id_len - len(str(id)))} | {ts}{' ' * (max_ts_len - len(str(ts)))} | {amount}{' ' * (max_amount_len - len(str(amount)))} | {by}{' ' * (max_by_len - len(str(by)))}\n"
        else:
            log_text += f"{id}{' ' * (max_id_len - len(str(id)))} | {amount}{' ' * (max_amount_len - len(str(amount)))} | {on}{' ' * (max_on_len - len(str(on)))} | {by}{' ' * (max_by_len - len(str(by)))}\n"
    embed.add_field(name="", value=f"```{log_text}```")
    return embed


async def generate_users_embed(page, interaction: discord.Interaction = None, admin=None):
    if interaction:
        user_type = interaction.message.embeds[0].fields[0].value
        if user_type == "Bot Admins":
            admin = True
        elif user_type == "Standard Users":
            admin = True
    db_users = User.get_users(page, admin)
    users = [{"id": "ID", "vis": "Visible", "role": "Bot Role", "name": "Name"}]
    log_text = ""
    max_id_len = len(users[0]["id"])
    max_vis_len = len(users[0]["vis"])
    max_role_len = len(users[0]["role"])
    max_name_len = len(users[0]["name"])
    for index, db_user in enumerate(db_users):
        user = await bot.fetch_user(db_user.discord_id)
        users.append({"id": db_user.id, "vis": "Yes" if db_user.visible else "No",
                      "role": "Admin" if db_user.is_admin else "User",
                      "name": f"{user.name}{'#' + user.discriminator if user.discriminator != '0' else ''}"})
        if len(str(users[-1]["id"])) > max_id_len:
            max_id_len = len(str(users[-1]["id"]))
        if len(str(users[-1]["vis"])) > max_vis_len:
            max_vis_len = len(str(users[-1]["vis"]))
        if len(str(users[-1]["role"])) > max_role_len:
            max_role_len = len(str(users[-1]["role"]))
        if len(str(users[-1]["name"])) > max_name_len:
            max_name_len = len(str(users[-1]["name"]))
    for user in users:
        id = user["id"]
        vis = user["vis"]
        role = user["role"]
        name = user["name"]
        if admin is None:
            log_text += f"{id}{' ' * (max_id_len - len(str(id)))} | {vis}{' ' * (max_vis_len - len(str(vis)))} | {role}{' ' * (max_role_len - len(str(role)))} | {name}\n"
        else:
            log_text += f"{id}{' ' * (max_id_len - len(str(id)))} | {vis}{' ' * (max_vis_len - len(str(vis)))} | {name}\n"
    embed = discord.Embed(title=f"Users - Page {page}")
    role = ""
    if admin is None:
        role = "All Users"
    elif admin:
        role = "Bot Admins"
    else:
        role = "Standard Users"
    embed.add_field(name="User Type", value=role, inline=False)
    embed.add_field(name="", value=f"```{log_text}```")
    return embed


class EarningPointsLodged(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        custom_id="nyn:earning:points_select",
        min_values=1,
        max_values=1,
        options=[
            SelectOption(label="10 Points", value="10"),
            SelectOption(label="20 Points", value="20"),
            SelectOption(label="30 Points", value="30")
        ]
    )
    async def select_callback(self, select, interaction):
        await interaction.response.defer(ephemeral=True)
        current_submission = EarningSubmission.get_by_channel_id(interaction.channel.id)
        await interaction.followup.send(f"Set Lodged Points to {select.values[0]} for Submission")
        EarningSubmission.set_points_lodged(interaction.channel.id, select.values[0])
        await interaction.message.delete(reason="Hiding Select Field")
        if not current_submission.points_lodged:
            await interaction.channel.send("Click the button below to enter your Act Summary:",
                                           view=EarningActSummaryButton())


class EarningActSummaryButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        custom_id="nyn:earning:act_summary_button",
        label="Enter Act Summary",
        style=ButtonStyle.primary,
    )
    async def button_callback(self, button, interaction):
        await interaction.response.send_modal(EarningActSummary())


class EarningActSummary(discord.ui.Modal):
    def __init__(self, act_summary=None) -> None:
        super().__init__(title="Enter Act Summary")
        if act_summary:
            self.add_item(
                discord.ui.InputText(label="Summarize your act in one/two sentences", style=InputTextStyle.multiline,
                                     value=act_summary))
        else:
            self.add_item(
                discord.ui.InputText(label="Summarize your act in one/two sentences", style=InputTextStyle.multiline))

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        channel: discord.TextChannel = interaction.channel
        if channel.last_message.content.startswith("Click"):
            await channel.delete_messages([channel.last_message], reason="Hiding Input Button")
        current_submission = EarningSubmission.get_by_channel_id(interaction.channel.id)
        embed = discord.Embed()
        embed.add_field(name="Set Act Summary to:", value=self.children[0].value)
        await interaction.followup.send(embeds=[embed])
        EarningSubmission.set_act_summary(interaction.channel_id, self.children[0].value)
        if not current_submission.act_summary:
            await interaction.channel.send("Was your character acting...", view=EarningLocationAlignment())


class EarningLocationAlignment(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        custom_id="nyn:earning:alignment_select",
        min_values=1,
        max_values=1,
        options=[
            SelectOption(label="In Alignment with their location (good in good loc, evil in evil loc)", value="0"),
            SelectOption(label="In Contravention to their location(good in evil loc, evil in good loc)", value="1"),
            SelectOption(label="Not Applicable", value="2")
        ]
    )
    async def select_callback(self, select, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        current_submission = EarningSubmission.get_by_channel_id(interaction.channel.id)
        await interaction.followup.send(
            f"Set Location Alignment to {alignment_short_label[int(select.values[0])]} for Submission")
        EarningSubmission.set_location_alignment(interaction.channel.id, LocationAlignment(int(select.values[0])))
        if current_submission.location_alignment is None:
            current_submission = EarningSubmission.get_by_channel_id(interaction.channel.id)
            await interaction.channel.send(embed=await generate_earning_embed(current_submission, "Ready to Submit!"),
                                           view=EarningReviewEditSubmitButtons())
        await interaction.message.delete(reason="Hiding Input Field")


class EarningReviewEditSubmitButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        custom_id="nyn:earning:review_button",
        label="Review",
        style=ButtonStyle.secondary,
    )
    async def review_callback(self, button, interaction):
        await interaction.response.defer(ephemeral=True)
        submission = EarningSubmission.get_by_channel_id(interaction.channel.id)
        embed = await generate_earning_embed(submission, "Reviewing Submission")
        await interaction.followup.send(embeds=[embed])

    @discord.ui.button(
        custom_id="nyn:earning:edit_points_button",
        label="Edit Points Lodged",
        style=ButtonStyle.secondary
    )
    async def edit_points_callback(self, button, interaction):
        submission = EarningSubmission.get_by_channel_id(interaction.channel.id)
        await interaction.response.send_message(
            f"Editing Points Lodged, current value: {submission.points_lodged} Points", view=EarningPointsLodged())

    @discord.ui.button(
        custom_id="nyn:earning:edit_act_summary_button",
        label="Edit Act Summary",
        style=ButtonStyle.secondary
    )
    async def edit_act_summary_callback(self, button, interaction):
        submission = EarningSubmission.get_by_channel_id(interaction.channel.id)
        await interaction.response.send_modal(EarningActSummary(submission.act_summary))

    @discord.ui.button(
        custom_id="nyn:earning:edit_location_alignment_button",
        label="Edit Location Alignment",
        style=ButtonStyle.secondary
    )
    async def edit_location_alignment_callback(self, button, interaction):
        submission = EarningSubmission.get_by_channel_id(interaction.channel.id)
        await interaction.response.send_message(
            f"Editing Location Alignment, current value: {alignment_short_label[submission.location_alignment.value]}",
            view=EarningLocationAlignment())

    @discord.ui.button(
        custom_id="nyn:earning:submit_button",
        label="Submit",
        style=ButtonStyle.success
    )
    async def submit_callback(self, button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        submission = EarningSubmission.get_by_channel_id(interaction.channel.id)
        EarningSubmission.submit(interaction.channel.id)
        await interaction.user.send(
            embeds=[await generate_earning_embed(submission, f"Submitted! Earning Submission ID:")])
        channel = bot.get_channel(config.EARNING_SUBMISSIONS_REVIEW_CHANNEL_ID)
        await channel.send(embeds=[await generate_earning_embed(submission, f"New Earning Submission -")],
                           view=EarningApproveDenyButtons())
        await interaction.followup.send("Submitted!")
        await bot.get_channel(interaction.channel_id).delete(reason="Submission Completed")


class EarningApproveDenyButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        custom_id="nyn:earning:deny_button",
        label="Deny",
        style=ButtonStyle.danger,
    )
    async def deny_callback(self, button, interaction):
        calling_user = User.get_or_create(interaction.user.id)
        if not calling_user.is_admin:
            await interaction.response.send_message("You are not authorized to perform this action")
            return
        submission = EarningSubmission.get_by_id(interaction.message.embeds[0].title.split("#")[1])
        if submission.denied_reason:
            await interaction.response.send_message(f"Earning Submission #{submission.id} has already been denied!")
        elif submission.approved:
            await interaction.response.send_message(f"Earning Submission #{submission.id} has already been approved!")
        else:
            await interaction.response.send_modal(EarningDenyReason())

    @discord.ui.button(
        custom_id="nyn:earning:approve_button",
        label="Approve",
        style=ButtonStyle.success
    )
    async def approve_callback(self, button, interaction: discord.Interaction):
        calling_user = User.get_or_create(interaction.user.id)
        if not calling_user.is_admin:
            await interaction.response.send_message("You are not authorized to perform this action")
            return
        await interaction.response.defer(ephemeral=True)
        submission = EarningSubmission.get_by_id(interaction.message.embeds[0].title.split("#")[1])
        if submission.approved:
            await interaction.followup.send(f"Earning Submission #{submission.id} has already been approved!")
        else:
            EarningSubmission.approve(submission.id)
            TransactionLog.create_from_earning_submission(submission)
            submitter = await bot.fetch_user(User.get_by_id(submission.user_id).discord_id)
            await submitter.send(embeds=[await generate_earning_embed(submission, f"Approved! Earning Submission ID:")])
            await interaction.followup.send(f"Approved Earning Submission #{submission.id}")
            try:
                sub_channel = await bot.fetch_channel(int(submission.discord_channel_id))
                await sub_channel.delete(reason="Submission Approved")
            except discord.errors.NotFound:
                pass
            try:
                app_channel = await bot.fetch_channel(int(config.EARNING_SUBMISSIONS_APPROVED_CHANNEL_ID))
                await app_channel.send(embed=await generate_earning_embed(submission, "Canon Earning Submission - ID:"))
            except discord.errors.NotFound:
                await interaction.followup.send("Error: Unable to find Earning Submissions Approved Channel")


class EarningDenyReason(discord.ui.Modal):
    def __init__(self) -> None:
        super().__init__(title="Deny Submission")
        self.add_item(discord.ui.InputText(label="Denial Reason", style=InputTextStyle.multiline))

    async def callback(self, interaction: discord.Interaction):
        calling_user = User.get_or_create(interaction.user.id)
        if not calling_user.is_admin:
            await interaction.response.send_message("You are not authorized to perform this action")
            return
        await interaction.response.defer(ephemeral=True)
        submission = EarningSubmission.get_by_id(interaction.message.embeds[0].title.split("#")[1])
        EarningSubmission.deny(submission.id, self.children[0].value)
        submission = EarningSubmission.get_by_id(interaction.message.embeds[0].title.split("#")[1])
        submitter = await bot.fetch_user(User.get_by_id(submission.user_id).discord_id)
        await submitter.send(embeds=[await generate_earning_embed(submission, f"Denied! Earning Submission ID:")],
                             view=EarningMakeChangesButton())
        await interaction.followup.send(
            f"Denied Earning Submission #{submission.id}\n**Reason:**\n{self.children[0].value}")


class EarningMakeChangesButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Make Changes",
        style=ButtonStyle.primary,
        custom_id="nyn:earning:make_changes"
    )
    async def button_callback(self, button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        submission = EarningSubmission.get_by_id(interaction.message.embeds[0].title.split("#")[1])
        if submission.approved:
            await interaction.followup.send(
                f"Earning Submission #{submission.id} has been approved, no changes are necessary!")
        else:
            try:
                channel = await bot.fetch_channel(int(submission.discord_channel_id))
                await interaction.followup.send(f"Already Making Changes: {channel.mention}")
            except discord.errors.NotFound:
                submitter = await bot.fetch_user(User.get_by_id(user_id=submission.user_id).discord_id)
                guild = bot.get_guild(int(config.DISCORD_SERVER_ID))
                if guild:
                    role_everyone = await discord_bot.get_role_by_name("@everyone")
                    channel = await (
                        guild.create_text_channel(
                            f"earning-{submission.id}-edits",
                            overwrites={
                                role_everyone: PermissionOverwrite.from_pair(
                                    Permissions.none(),
                                    Permissions.all()
                                ),
                                submitter: PermissionOverwrite.from_pair(
                                    Permissions(DP.SEND_MESSAGES | DP.VIEW_CHANNEL),
                                    Permissions(~(DP.SEND_MESSAGES | DP.VIEW_CHANNEL))
                                )
                            },
                            category=await discord_bot.get_or_create_category("submissions")
                        )
                    )
                    EarningSubmission.make_edits(submission.id, channel.id)
                    await channel.send(
                        embed=await generate_earning_embed(submission, f"Making Changes to Earning Submission"),
                        view=EarningReviewEditSubmitButtons())
                    await interaction.followup.send(channel.mention)


class PaginationButtons(discord.ui.View):
    namespace = "pagination"

    def __init__(self, generate_embed: Callable, pagination_buttons):
        self.generate_embed = generate_embed
        self.pagination_buttons = pagination_buttons
        super().__init__(timeout=None)

    def permission_check(self, interaction):
        return True

    @discord.ui.button(
        custom_id=f"nyn:{namespace}:previous",
        label="Previous",
        style=ButtonStyle.secondary
    )
    async def previous_callback(self, button, interaction: discord.Interaction):
        if not self.permission_check(interaction):
            await interaction.response.send_message("You are not authorized to perform this action")
            return
        await interaction.response.defer(ephemeral=True)
        last_page = int(interaction.message.embeds[0].title.split()[-1])
        try:
            await interaction.followup.send(embed=await self.generate_embed(last_page - 1, interaction=interaction),
                                            view=self.pagination_buttons())
        except PaginationError as e:
            await interaction.followup.send(e.message)

    @discord.ui.button(
        custom_id=f"nyn:{namespace}:next",
        label="Next",
        style=ButtonStyle.secondary
    )
    async def next_callback(self, button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        last_page = int(interaction.message.embeds[0].title.split()[-1])
        try:
            await interaction.followup.send(embed=await self.generate_embed(last_page + 1, interaction=interaction),
                                            view=self.pagination_buttons())
        except PaginationError as e:
            await interaction.followup.send(e.message)


class LeaderboardPaginationButtons(PaginationButtons):
    namespace = "leaderboard"

    def __init__(self):
        super().__init__(lambda page, interaction=None: generate_leaderboard_embed(page), LeaderboardPaginationButtons)


class TransactionLogPaginationButtons(PaginationButtons):
    namespace = "transaction_log"

    def permission_check(self, interaction):
        return User.get_or_create(interaction.user.id).is_admin

    def __init__(self):
        super().__init__(lambda page, interaction=None: generate_transaction_log_embed(page, interaction=interaction),
                         TransactionLogPaginationButtons)


class AdminTransactionLogPaginationButtons(PaginationButtons):
    namespace = "admin_transaction_log"

    def permission_check(self, interaction):
        return User.get_or_create(interaction.user.id).is_admin

    def __init__(self):
        super().__init__(
            lambda page, interaction=None: generate_admin_transaction_log_embed(page, interaction=interaction),
            AdminTransactionLogPaginationButtons)


class UserPaginationButtons(PaginationButtons):
    namespace = "users"

    def permission_check(self, interaction):
        return User.get_or_create(interaction.user.id).is_admin

    def __init__(self):
        super().__init__(lambda page, interaction=None: generate_users_embed(page, interaction=interaction),
                         UserPaginationButtons)


class SpendingAbilityInfo(discord.ui.Modal):
    def __init__(self, submission=None) -> None:
        super().__init__(title=("Modify" if submission else "Enter") + " Ability Information")
        self.submission = None
        if submission:
            self.submission = submission
            self.add_item(discord.ui.InputText(label="Ability Requested", style=InputTextStyle.singleline,
                                               value=submission.ability_requested))
            self.add_item(discord.ui.InputText(label="Description of Ability", style=InputTextStyle.multiline,
                                               value=submission.ability_description))
            self.add_item(discord.ui.InputText(label="Scope/Limitations of Ability", style=InputTextStyle.multiline,
                                               value=submission.ability_limitations))
            self.add_item(discord.ui.InputText(label="Cost or Balancing Weakness", style=InputTextStyle.singleline,
                                               value=submission.cost_weakness))
            self.add_item(discord.ui.InputText(label="Description of Cost/Weakness", style=InputTextStyle.multiline,
                                               value=submission.cost_weakness_description))
        else:
            self.add_item(discord.ui.InputText(label="Ability Requested", style=InputTextStyle.singleline,
                                               placeholder="Leave blank to not change", required=False))
            self.add_item(discord.ui.InputText(label="Description of Ability", style=InputTextStyle.multiline,
                                               placeholder="Leave blank to not change", required=False))
            self.add_item(discord.ui.InputText(label="Scope/Limitations of Ability", style=InputTextStyle.multiline,
                                               placeholder="Leave blank to not change", required=False))
            self.add_item(discord.ui.InputText(label="Cost or Balancing Weakness", style=InputTextStyle.singleline,
                                               placeholder="Leave blank to not change", required=False))
            self.add_item(discord.ui.InputText(label="Description of Cost/Weakness", style=InputTextStyle.multiline,
                                               placeholder="Leave blank to not change", required=False))

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        channel_id = interaction.channel_id
        current_submission = SpendingSubmission.get_by_channel_id(interaction.channel.id)
        embed = discord.Embed()
        ability_requested = self.children[0].value
        if (self.submission and ability_requested != current_submission.ability_requested) or (
                self.submission is None and ability_requested):
            SpendingSubmission.set_ability_requested(channel_id, ability_requested)
            embed.add_field(name="Set Ability Requested to:", value=ability_requested, inline=False)
        else:
            embed.add_field(name="Left Ability Requested as:", value=current_submission.ability_requested, inline=False)
        ability_description = self.children[1].value
        if (self.submission and ability_description != current_submission.ability_description) or (
                self.submission is None and ability_description):
            SpendingSubmission.set_ability_description(channel_id, ability_description)
            embed.add_field(name="Set Ability Description to:", value=ability_description, inline=False)
        else:
            embed.add_field(name="Left Ability Requested as:", value=current_submission.ability_description,
                            inline=False)
        ability_scope_limits = self.children[2].value
        if (self.submission and ability_scope_limits != current_submission.ability_limitations) or (
                self.submission is None and ability_scope_limits):
            SpendingSubmission.set_ability_limitations(channel_id, ability_scope_limits)
            embed.add_field(name="Set Scope/Limitations of Ability to:", value=ability_scope_limits, inline=False)
        else:
            embed.add_field(name="Left Scope/Limitations of Ability as:", value=current_submission.ability_limitations,
                            inline=False)
        cost_weakness = self.children[3].value
        if (self.submission and cost_weakness != current_submission.cost_weakness) or (
                self.submission is None and cost_weakness):
            SpendingSubmission.set_cost_weakness(channel_id, cost_weakness)
            embed.add_field(name="Set Cost/Weakness to:", value=cost_weakness, inline=False)
        else:
            embed.add_field(name="Left Cost/Weakness as:", value=current_submission.cost_weakness, inline=False)
        cost_weakness_description = self.children[4].value
        if (self.submission and cost_weakness_description != current_submission.cost_weakness_description) or (
                self.submission is None and cost_weakness_description):
            SpendingSubmission.set_cost_weakness_description(channel_id, cost_weakness_description)
            embed.add_field(name="Set Cost/Weakness Description to:", value=cost_weakness_description, inline=False)
        else:
            embed.add_field(name="Left Cost/Weakness Description as:",
                            value=current_submission.cost_weakness_description, inline=False)

        await interaction.followup.send(embeds=[embed])

        sub = SpendingSubmission.get_by_channel_id(interaction.channel.id)
        if sub.ability_requested and sub.ability_description and sub.ability_limitations and sub.cost_weakness and sub.cost_weakness_description:
            await interaction.channel.send("Is your Ability Lore/Rule Compliant?",
                                           view=SpendingLoreRuleCompliantButtons())


class SpendingAbilityInfoButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        custom_id="nyn:spending:enter_ability_info_button",
        label="Enter Ability Information",
        style=ButtonStyle.primary,
    )
    async def button_callback(self, button, interaction):
        await interaction.response.send_modal(SpendingAbilityInfo())


class SpendingLoreRuleCompliantButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        custom_id="nyn:spending:compliance_no",
        label="No",
        style=ButtonStyle.danger,
    )
    async def no_callback(self, button, interaction):
        await interaction.response.defer(ephemeral=True)
        channel_id = interaction.channel_id
        embed = discord.Embed()
        SpendingSubmission.set_lore_rule_compliant(channel_id, False)
        embed.add_field(name="Set Lore/Rule Compliant to:", value="No", inline=False)
        current_submission = SpendingSubmission.get_by_channel_id(interaction.channel.id)
        await interaction.followup.send("Ready to Submit!",
                                        embed=await generate_spending_embed(current_submission, "Ready to Submit! "),
                                        view=SpendingReviewEditSubmitButtons())

    @discord.ui.button(
        custom_id="nyn:spending:compliance_yes",
        label="Yes",
        style=ButtonStyle.success,
    )
    async def yes_callback(self, button, interaction):
        await interaction.response.defer(ephemeral=True)
        channel_id = interaction.channel_id
        embed = discord.Embed()
        SpendingSubmission.set_lore_rule_compliant(channel_id, True)
        embed.add_field(name="Set Lore/Rule Compliant to:", value="Yes", inline=False)
        current_submission = SpendingSubmission.get_by_channel_id(interaction.channel.id)
        await interaction.followup.send("Ready to Submit!",
                                        embed=await generate_spending_embed(current_submission, "Ready to Submit! "),
                                        view=SpendingReviewEditSubmitButtons())


class SpendingReviewEditSubmitButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        custom_id="nyn:spending:review",
        label="Review",
        style=ButtonStyle.secondary
    )
    async def review_callback(self, button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        current_submission = SpendingSubmission.get_by_channel_id(interaction.channel.id)
        await interaction.followup.send(embed=await generate_spending_embed(current_submission, "Reviewing Submission"),
                                        view=SpendingReviewEditSubmitButtons())

    @discord.ui.button(
        custom_id="nyn:spending:edit",
        label="Edit",
        style=ButtonStyle.secondary
    )
    async def edit_callback(self, button, interaction: discord.Interaction):
        current_submission = SpendingSubmission.get_by_channel_id(interaction.channel.id)
        await interaction.response.send_modal(SpendingAbilityInfo(submission=current_submission))

    @discord.ui.button(
        custom_id="nyn:spending:submit",
        label="Submit",
        style=ButtonStyle.primary
    )
    async def submit_callback(self, button, interaction):
        await interaction.response.defer(ephemeral=True)
        submission = SpendingSubmission.get_by_channel_id(interaction.channel.id)
        SpendingSubmission.submit(interaction.channel_id)
        await interaction.user.send(
            embeds=[await generate_spending_embed(submission, f"Submitted! Spending Submission ID:")])
        channel = await bot.fetch_channel(config.SPENDING_SUBMISSIONS_REVIEW_CHANNEL_ID)
        await channel.send(embeds=[await generate_spending_embed(submission, f"New Spending Submission -")],
                           view=SpendingApproveDenyButtons())
        await interaction.followup.send("Submitted!")
        await bot.get_channel(interaction.channel_id).delete(reason="Submission Completed")


class SpendingApproveDenyButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        custom_id="nyn:spending:deny_button",
        label="Deny",
        style=ButtonStyle.danger,
    )
    async def deny_callback(self, button, interaction):
        submission = SpendingSubmission.get_by_id(interaction.message.embeds[0].title.split("#")[1])
        if submission.denied_reason:
            await interaction.response.send_message(f"Spending Submission #{submission.id} has already been denied!")
        elif submission.approved:
            await interaction.response.send_message(f"Spending Submission #{submission.id} has already been approved!")
        else:
            await interaction.response.send_modal(SpendingDenyReason())

    @discord.ui.button(
        custom_id="nyn:spending:approve_button",
        label="Approve",
        style=ButtonStyle.success
    )
    async def approve_callback(self, button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        submission = SpendingSubmission.get_by_id(interaction.message.embeds[0].title.split("#")[1])
        user = User.get_by_id(submission.user_id)
        if submission.approved:
            await interaction.followup.send(f"Spending Submission #{submission.id} has already been approved!")
        elif user.judgement_points < 200:
            await interaction.followup.send(
                f"User does not have enough Judgement Points! Current balance is: `{user.judgement_points}` Points")
        else:
            SpendingSubmission.approve(submission.id)
            TransactionLog.create_from_spending_submission(submission)
            submitter = await bot.fetch_user(User.get_by_id(submission.user_id).discord_id)
            await submitter.send(
                embeds=[await generate_spending_embed(submission, f"Approved! Spending Submission ID:")])
            await interaction.followup.send(f"Approved Spending Submission #{submission.id}")
            try:
                sub_channel = await bot.fetch_channel(int(submission.discord_channel_id))
                await sub_channel.delete(reason="Submission Approved")
            except discord.errors.NotFound:
                pass
            try:
                app_channel = await bot.fetch_channel(int(config.SPENDING_SUBMISSIONS_APPROVED_CHANNEL_ID))
                await app_channel.send(
                    embed=await generate_spending_embed(submission, "Canon Spending Submission - ID:"))
            except discord.errors.NotFound:
                await interaction.followup.send("Error: Unable to find Spending Submissions Approved Channel")


class SpendingDenyReason(discord.ui.Modal):
    def __init__(self) -> None:
        super().__init__(title="Deny Submission")
        self.add_item(discord.ui.InputText(label="Denial Reason", style=InputTextStyle.multiline))

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        submission = SpendingSubmission.get_by_id(interaction.message.embeds[0].title.split("#")[1])
        SpendingSubmission.deny(submission.id, self.children[0].value)
        submission = SpendingSubmission.get_by_id(interaction.message.embeds[0].title.split("#")[1])
        submitter = await bot.fetch_user(User.get_by_id(submission.user_id).discord_id)
        await submitter.send(embeds=[await generate_spending_embed(submission, f"Denied! Spending Submission ID:")],
                             view=SpendingMakeChangesButton())
        await interaction.followup.send(
            f"Denied Spending Submission #{submission.id}\n**Reason:**\n{self.children[0].value}")


class SpendingMakeChangesButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Make Changes",
        style=ButtonStyle.primary,
        custom_id="nyn:spending:make_changes"
    )
    async def button_callback(self, button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        submission = SpendingSubmission.get_by_id(interaction.message.embeds[0].title.split("#")[1])
        if submission.approved:
            await interaction.followup.send(
                f"Spending Submission #{submission.id} has been approved, no changes are necessary!")
        else:
            try:
                channel = await bot.fetch_channel(int(submission.discord_channel_id))
                await interaction.followup.send(f"Already Making Changes: {channel.mention}")
            except discord.errors.NotFound:
                submitter = await bot.fetch_user(User.get_by_id(user_id=submission.user_id).discord_id)
                guild = bot.get_guild(int(config.DISCORD_SERVER_ID))
                if guild:
                    role_everyone = await discord_bot.get_role_by_name("@everyone")
                    channel = await (
                        guild.create_text_channel(
                            f"spending-{submission.id}-edits",
                            overwrites={
                                role_everyone: PermissionOverwrite.from_pair(
                                    Permissions.none(),
                                    Permissions.all()
                                ),
                                submitter: PermissionOverwrite.from_pair(
                                    Permissions(DP.SEND_MESSAGES | DP.VIEW_CHANNEL),
                                    Permissions(~(DP.SEND_MESSAGES | DP.VIEW_CHANNEL))
                                )
                            },
                            category=await discord_bot.get_or_create_category("submissions")
                        )
                    )
                    SpendingSubmission.make_edits(submission.id, channel.id)
                    await channel.send(
                        embed=await generate_spending_embed(submission, f"Making Changes to Spending Submission"),
                        view=SpendingReviewEditSubmitButtons())
                    await interaction.followup.send(channel.mention)


def register_views(bot):
    bot.add_view(EarningActSummaryButton())
    bot.add_view(EarningPointsLodged())
    bot.add_view(EarningLocationAlignment())
    bot.add_view(EarningReviewEditSubmitButtons())
    bot.add_view(EarningApproveDenyButtons())
    bot.add_view(EarningMakeChangesButton())
    bot.add_view(LeaderboardPaginationButtons())
    bot.add_view(TransactionLogPaginationButtons())
    bot.add_view(AdminTransactionLogPaginationButtons())
    bot.add_view(UserPaginationButtons())
    bot.add_view(SpendingAbilityInfoButton())
    bot.add_view(SpendingLoreRuleCompliantButtons())
    bot.add_view(SpendingReviewEditSubmitButtons())
    bot.add_view(SpendingApproveDenyButtons())
    bot.add_view(SpendingMakeChangesButton())
