import datetime
import math
from enum import Enum
from typing import Optional

from sqlalchemy import Text, DateTime, ForeignKey, select, func, Connection, insert, BigInteger, update, desc
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import expression

from db import get_engine
from exceptions import PaginationError


class utcnow(expression.FunctionElement):
    type = DateTime()
    inherit_cache = True

@compiles(utcnow, 'mysql')
def pg_utcnow(element, compiler, **kw):
    return "UTC_TIMESTAMP()"


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(primary_key=True)
    discord_id: Mapped[str] = mapped_column(Text)
    judgement_points: Mapped[int] = mapped_column()
    visible: Mapped[bool] = mapped_column(server_default='1')
    is_admin: Mapped[bool] = mapped_column(server_default='0')

    @classmethod
    def get_or_create(cls, discord_id):
        engine = get_engine()
        discord_id = str(discord_id)
        stmt = select(User).where(User.discord_id == discord_id).limit(1)
        with engine.connect() as conn:
            result = conn.execute(stmt).first()
            if result:
                return result
            stmt = insert(User).values(discord_id=discord_id, judgement_points=0)
            conn.execute(stmt)
            conn.commit()
            stmt = select(User).where(User.discord_id == discord_id).limit(1)
            result = conn.execute(stmt).first()
            if result:
                return result
        raise ValueError("Unable to Create User")

    @classmethod
    def get_by_id(cls, user_id):
        engine = get_engine()
        stmt = select(User).where(User.id == user_id).limit(1)
        with engine.connect() as conn:
            result = conn.execute(stmt).first()
            if result:
                return result
        return None

    @classmethod
    def get_leaderboard(cls, page=1):
        count = cls.count()
        if page < 1 or math.ceil(count/10) < page:
            raise PaginationError((page, math.ceil(count/10)))
        engine = get_engine()
        stmt = select(User).where(User.visible == True).order_by(desc(User.judgement_points)).limit(10).offset((page - 1) * 10)
        with engine.connect() as conn:
            result = conn.execute(stmt)
            if result:
                return result
            return []

    @classmethod
    def count(cls, only_visible=True, admin=None):
        engine = get_engine()
        stmt = select(func.count())
        if only_visible:
            stmt = stmt.where(User.visible == True)
        if admin is None:
            pass
        elif not admin:
            stmt = stmt.where(User.is_admin == False)
        elif admin:
            stmt = stmt.where(User.is_admin == True)
        stmt = stmt.select_from(User)
        with engine.connect() as conn:
            result = conn.execute(stmt).first()
            return result[0]


    @classmethod
    def get_users(cls, page=1, admin=None):
        count = cls.count(only_visible=False, admin=admin)
        if page < 1 or math.ceil(count / 10) < page:
            raise PaginationError((page, math.ceil(count/10)))
        engine = get_engine()
        stmt = select(User)
        if admin is None:
            pass
        elif admin:
            stmt = stmt.where(User.is_admin == True)
        else:
            stmt = stmt.where(User.is_admin == False)
        stmt = stmt.order_by(User.id).limit(10).offset((page - 1) * 10)
        with engine.connect() as conn:
            result = conn.execute(stmt)
            if result:
                return result
            return []

    @classmethod
    def set_visible(cls, user_id, visible):
        engine = get_engine()
        with engine.connect() as conn:
            stmt = update(User).where(User.id == user_id).values(visible=visible)
            conn.execute(stmt)
            conn.commit()

    @classmethod
    def set_visible_by_discord_id(cls, discord_id, visible):
        user = User.get_or_create(discord_id)
        cls.set_visible(user.id, visible)

    @classmethod
    def set_admin(cls, user_id, is_admin):
        engine = get_engine()
        with engine.connect() as conn:
            stmt = update(User).where(User.id == user_id).values(is_admin=is_admin)
            conn.execute(stmt)
            conn.commit()

    @classmethod
    def set_admin_by_discord_id(cls, discord_id, is_admin):
        user = User.get_or_create(discord_id)
        cls.set_admin(user.id, is_admin)

class TransactionLog(Base):
    __tablename__ = "transaction_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(server_default=utcnow())
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    earning_submission_id: Mapped[Optional[int]] = mapped_column(ForeignKey("earning_submission.id"))
    earning_submission: Mapped["EarningSubmission"] = relationship(back_populates="transaction_record")
    spending_submission_id: Mapped[Optional[int]] = mapped_column(ForeignKey("spending_submission.id"))
    spending_submission: Mapped["SpendingSubmission"] = relationship(back_populates="transaction_record")
    admin_transaction_id: Mapped[Optional[int]] = mapped_column(ForeignKey("admin_transaction.id"))
    admin_transaction: Mapped["AdminTransaction"] = relationship(back_populates="transaction_record")
    judgement_points: Mapped[int] = mapped_column()

    @classmethod
    def count(cls, user_id):
        engine = get_engine()
        stmt = select(func.count()).where(TransactionLog.user_id == user_id).select_from(TransactionLog)
        with engine.connect() as conn:
            result = conn.execute(stmt).first()
            return result[0]

    @classmethod
    def search_by_user(cls, user_id, page=1):
        count = cls.count(user_id)
        if page < 1 or math.ceil(count / 10) < page:
            raise PaginationError((page, math.ceil(count/10)))
        engine = get_engine()
        stmt = select(TransactionLog).where(TransactionLog.user_id == user_id).order_by(desc(TransactionLog.timestamp)).limit(10).offset((page - 1) * 10)
        with engine.connect() as conn:
            result = conn.execute(stmt)
            if result:
                return result
            return []

    @classmethod
    def create_from_earning_submission(cls, earning_submission):
        e = earning_submission
        points_lodged = e.points_lodged
        alignment = e.location_alignment
        points_result = points_lodged
        if alignment == LocationAlignment.IN_ALIGNMENT:
            points_result *= 1.5
        elif alignment == LocationAlignment.IN_CONTRAVENTION:
            points_result *= 2
        engine = get_engine()
        with engine.connect() as conn:
            stmt = insert(TransactionLog).values(user_id=e.user_id, earning_submission_id=e.id, judgement_points=points_result)
            conn.execute(stmt)
            user = User.get_by_id(user_id=e.user_id)
            stmt = update(User).where(User.id == e.user_id).values(judgement_points=user.judgement_points+points_result)
            conn.execute(stmt)
            conn.commit()

    @classmethod
    def create_from_admin_transaction(cls, admin_transaction):
        a = admin_transaction
        net_points = a.net_points
        engine = get_engine()
        with engine.connect() as conn:
            stmt = insert(TransactionLog).values(user_id=a.user_id, admin_transaction_id=a.id, judgement_points=net_points)
            conn.execute(stmt)
            user = User.get_by_id(user_id=a.user_id)
            stmt = update(User).where(User.id == a.user_id).values(judgement_points=user.judgement_points+net_points)
            conn.execute(stmt)
            conn.commit()

    @classmethod
    def create_from_spending_submission(cls, spending_submission):
        s = spending_submission
        net_points = -s.cost
        engine = get_engine()
        with engine.connect() as conn:
            stmt = insert(TransactionLog).values(user_id=s.user_id, spending_submission_id=s.id, judgement_points=net_points)
            conn.execute(stmt)
            user = User.get_by_id(user_id=s.user_id)
            stmt = update(User).where(User.id == s.user_id).values(judgement_points=user.judgement_points+net_points)
            conn.execute(stmt)
            conn.commit()


class LocationAlignment(Enum):
    IN_ALIGNMENT = 0
    IN_CONTRAVENTION = 1
    NOT_APPLICABLE = 2


class EarningSubmission(Base):
    __tablename__ = "earning_submission"
    id: Mapped[int] = mapped_column(primary_key=True)
    discord_channel_id: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime.datetime] = mapped_column(server_default=utcnow())
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    points_lodged: Mapped[Optional[int]] = mapped_column()  # How many points would you like to lodge today?
    act_summary: Mapped[Optional[str]] = mapped_column(Text)
    location_alignment: Mapped[Optional[LocationAlignment]] = mapped_column()
    submitted: Mapped[bool] = mapped_column(default=False)
    approved: Mapped[Optional[bool]] = mapped_column()
    denied_reason: Mapped[Optional[str]] = mapped_column(Text)
    transaction_record: Mapped["TransactionLog"] = relationship(back_populates="earning_submission")

    @classmethod
    def get_next_id(cls):
        engine = get_engine()
        stmt = select(func.max(EarningSubmission.id)).limit(1)
        with engine.connect() as conn:
            result = conn.execute(stmt).first()
            if result[0]:
                return result[0]+1
        return 1

    @classmethod
    def create(cls, discord_channel_id, user_id):
        engine = get_engine()
        with engine.connect() as conn:
            stmt = insert(EarningSubmission).values(discord_channel_id=str(discord_channel_id), user_id=user_id)
            result = conn.execute(stmt)
            conn.commit()
            stmt = select(EarningSubmission).where(EarningSubmission.id == result.inserted_primary_key[0]).limit(1)
            return conn.execute(stmt).first()

    @classmethod
    def get_by_id(cls, submission_id):
        engine = get_engine()
        with engine.connect() as conn:
            stmt = select(EarningSubmission).where(EarningSubmission.id == submission_id).limit(1)
            return conn.execute(stmt).first()

    @classmethod
    def get_by_channel_id(cls, discord_channel_id):
        engine = get_engine()
        with engine.connect() as conn:
            stmt = select(EarningSubmission).where(EarningSubmission.discord_channel_id == discord_channel_id).limit(1)
            return conn.execute(stmt).first()

    @classmethod
    def set_points_lodged(cls, discord_channel_id, points_lodged):
        engine = get_engine()
        with engine.connect() as conn:
            stmt = update(EarningSubmission).where(EarningSubmission.discord_channel_id == discord_channel_id).values(points_lodged=points_lodged)
            conn.execute(stmt)
            conn.commit()

    @classmethod
    def set_act_summary(cls, discord_channel_id, act_summary):
        engine = get_engine()
        with engine.connect() as conn:
            stmt = update(EarningSubmission).where(EarningSubmission.discord_channel_id == discord_channel_id).values(act_summary=act_summary)
            conn.execute(stmt)
            conn.commit()

    @classmethod
    def set_location_alignment(cls, discord_channel_id, location_alignment):
        engine = get_engine()
        with engine.connect() as conn:
            stmt = update(EarningSubmission).where(EarningSubmission.discord_channel_id == discord_channel_id).values(location_alignment=location_alignment)
            conn.execute(stmt)
            conn.commit()

    @classmethod
    def submit(cls, discord_channel_id):
        engine = get_engine()
        with engine.connect() as conn:
            stmt = update(EarningSubmission).where(EarningSubmission.discord_channel_id == discord_channel_id).values(submitted=True)
            conn.execute(stmt)
            conn.commit()

    @classmethod
    def approve(cls, submission_id):
        engine = get_engine()
        with engine.connect() as conn:
            stmt = update(EarningSubmission).where(EarningSubmission.id == submission_id).values(approved=True, denied_reason=None)
            conn.execute(stmt)
            conn.commit()

    @classmethod
    def deny(cls, submission_id, reason):
        engine = get_engine()
        with engine.connect() as conn:
            stmt = update(EarningSubmission).where(EarningSubmission.id == submission_id).values(approved=False, denied_reason=reason)
            conn.execute(stmt)
            conn.commit()

    @classmethod
    def make_edits(cls, submission_id, new_channel_id):
        engine = get_engine()
        stmt = update(EarningSubmission).where(EarningSubmission.id == submission_id).values(discord_channel_id=new_channel_id, submitted=False, approved=None, denied_reason=None)
        with engine.connect() as conn:
            conn.execute(stmt)
            conn.commit()


class SpendingSubmission(Base):
    __tablename__ = "spending_submission"
    id: Mapped[int] = mapped_column(primary_key=True)
    discord_channel_id: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime.datetime] = mapped_column(server_default=utcnow())
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    cost: Mapped[int] = mapped_column(default=200)
    ability_requested: Mapped[Optional[str]] = mapped_column(Text)  # Ability Requested
    ability_description: Mapped[Optional[str]] = mapped_column(Text)  # Description of Ability
    ability_limitations: Mapped[Optional[str]] = mapped_column(Text)  # Scope/Limitations of Ability
    cost_weakness: Mapped[Optional[str]] = mapped_column(Text)  # Cost or Balancing Weakness
    cost_weakness_description: Mapped[Optional[str]] = mapped_column(Text)  # Description of Cost/Weakness
    lore_rule_compliant: Mapped[Optional[bool]] = mapped_column()  # Is your ability Lore/Rule Compliant
    submitted: Mapped[bool] = mapped_column(default=False)
    approved: Mapped[Optional[bool]] = mapped_column()  # Whether the Submission was Approved
    denied_reason: Mapped[Optional[str]] = mapped_column(Text)
    transaction_record: Mapped["TransactionLog"] = relationship(back_populates="spending_submission")

    @classmethod
    def get_next_id(cls):
        engine = get_engine()
        stmt = select(func.max(SpendingSubmission.id)).limit(1)
        with engine.connect() as conn:
            result = conn.execute(stmt).first()
            if result[0]:
                return result[0] + 1
        return 1

    @classmethod
    def create(cls, discord_channel_id, user_id):
        engine = get_engine()
        with engine.connect() as conn:
            stmt = insert(SpendingSubmission).values(discord_channel_id=str(discord_channel_id), user_id=user_id)
            result = conn.execute(stmt)
            conn.commit()
            stmt = select(SpendingSubmission).where(SpendingSubmission.id == result.inserted_primary_key[0]).limit(1)
            return conn.execute(stmt).first()

    @classmethod
    def get_by_channel_id(cls, discord_channel_id):
        engine = get_engine()
        with engine.connect() as conn:
            stmt = select(SpendingSubmission).where(SpendingSubmission.discord_channel_id == discord_channel_id).limit(1)
            return conn.execute(stmt).first()

    @classmethod
    def get_by_id(cls, submission_id):
        engine = get_engine()
        with engine.connect() as conn:
            stmt = select(SpendingSubmission).where(SpendingSubmission.id == submission_id).limit(1)
            return conn.execute(stmt).first()

    @classmethod
    def set_ability_requested(cls, discord_channel_id, ability_requested):
        engine = get_engine()
        with engine.connect() as conn:
            stmt = update(SpendingSubmission).where(SpendingSubmission.discord_channel_id == discord_channel_id).values(ability_requested=ability_requested)
            conn.execute(stmt)
            conn.commit()

    @classmethod
    def set_ability_description(cls, discord_channel_id, ability_description):
        engine = get_engine()
        with engine.connect() as conn:
            stmt = update(SpendingSubmission).where(SpendingSubmission.discord_channel_id == discord_channel_id).values(ability_description=ability_description)
            conn.execute(stmt)
            conn.commit()

    @classmethod
    def set_ability_limitations(cls, discord_channel_id, ability_limitations):
        engine = get_engine()
        with engine.connect() as conn:
            stmt = update(SpendingSubmission).where(SpendingSubmission.discord_channel_id == discord_channel_id).values(ability_limitations=ability_limitations)
            conn.execute(stmt)
            conn.commit()

    @classmethod
    def set_cost_weakness(cls, discord_channel_id, cost_weakness):
        engine = get_engine()
        with engine.connect() as conn:
            stmt = update(SpendingSubmission).where(SpendingSubmission.discord_channel_id == discord_channel_id).values(cost_weakness=cost_weakness)
            conn.execute(stmt)
            conn.commit()

    @classmethod
    def set_cost_weakness_description(cls, discord_channel_id, cost_weakness_description):
        engine = get_engine()
        with engine.connect() as conn:
            stmt = update(SpendingSubmission).where(SpendingSubmission.discord_channel_id == discord_channel_id).values(cost_weakness_description=cost_weakness_description)
            conn.execute(stmt)
            conn.commit()

    @classmethod
    def set_lore_rule_compliant(cls, discord_channel_id, lore_rule_compliant=True):
        engine = get_engine()
        with engine.connect() as conn:
            stmt = update(SpendingSubmission).where(SpendingSubmission.discord_channel_id == discord_channel_id).values(lore_rule_compliant=lore_rule_compliant)
            conn.execute(stmt)
            conn.commit()

    @classmethod
    def submit(cls, discord_channel_id):
        engine = get_engine()
        with engine.connect() as conn:
            stmt = update(SpendingSubmission).where(SpendingSubmission.discord_channel_id == discord_channel_id).values(submitted=True)
            conn.execute(stmt)
            conn.commit()

    @classmethod
    def approve(cls, submission_id):
        engine = get_engine()
        with engine.connect() as conn:
            stmt = update(SpendingSubmission).where(SpendingSubmission.id == submission_id).values(approved=True, denied_reason=None)
            conn.execute(stmt)
            conn.commit()

    @classmethod
    def deny(cls, submission_id, reason):
        engine = get_engine()
        with engine.connect() as conn:
            stmt = update(SpendingSubmission).where(SpendingSubmission.id == submission_id).values(approved=False, denied_reason=reason)
            conn.execute(stmt)
            conn.commit()

    @classmethod
    def make_edits(cls, submission_id, new_channel_id):
        engine = get_engine()
        stmt = update(SpendingSubmission).where(SpendingSubmission.id == submission_id).values(discord_channel_id=new_channel_id, submitted=False, approved=None, denied_reason=None)
        with engine.connect() as conn:
            conn.execute(stmt)
            conn.commit()

class AdminTransaction(Base):
    __tablename__ = "admin_transaction"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(server_default=utcnow())
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    admin_user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    net_points: Mapped[int] = mapped_column()
    reason: Mapped[str] = mapped_column(Text)
    transaction_record: Mapped["TransactionLog"] = relationship(back_populates="admin_transaction")

    @classmethod
    def count(cls, user_id=None, admin_id=None):
        engine = get_engine()
        stmt = select(func.count())
        if user_id:
            stmt = stmt.where(AdminTransaction.user_id == user_id)
        if admin_id:
            stmt = stmt.where(AdminTransaction.admin_user_id == admin_id)
        stmt = stmt.select_from(AdminTransaction)
        with engine.connect() as conn:
            result = conn.execute(stmt).first()
        return result[0]

    @classmethod
    def create(cls, user_id, admin_user_id, net_points, reason):
        engine = get_engine()
        with engine.connect() as conn:
            stmt = insert(AdminTransaction).values(user_id=user_id, admin_user_id=admin_user_id, net_points=net_points, reason=reason)
            result = conn.execute(stmt)
            conn.commit()
            return result.inserted_primary_key[0]

    @classmethod
    def get_by_id(cls, transaction_id):
        engine = get_engine()
        with engine.connect() as conn:
            stmt = select(AdminTransaction).where(AdminTransaction.id == transaction_id).limit(1)
            return conn.execute(stmt).first()

    @classmethod
    def search(cls, target=None, admin=None, page=1):
        count = cls.count(user_id=target.id if target else None, admin_id=admin.id if admin else None)
        if page < 1 or math.ceil(count / 10) < page:
            raise PaginationError((page, math.ceil(count/10)))
        engine = get_engine()
        stmt = select(AdminTransaction)
        if target:
            stmt = stmt.where(AdminTransaction.user_id == target.id)
        if admin:
            stmt = stmt.where(AdminTransaction.admin_user_id == admin.id)
        stmt = stmt.order_by(desc(AdminTransaction.timestamp)).limit(10).offset((page - 1) * 10)
        with engine.connect() as conn:
            result = conn.execute(stmt)
            if result:
                return result
            return []


Base.registry.configure()
