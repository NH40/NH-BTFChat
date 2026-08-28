from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.models import BotUser, Subscription, TargetChat


async def upsert_target_chat(
    session: AsyncSession,
    *,
    tg_chat_id: int,
    title: str | None,
    chat_type: str,
    owner_id: int,
) -> TargetChat:
    result = await session.execute(select(TargetChat).where(TargetChat.tg_chat_id == tg_chat_id))
    target_chat = result.scalar_one_or_none()
    if target_chat:
        target_chat.title = title
        target_chat.chat_type = chat_type
    else:
        target_chat = TargetChat(
            tg_chat_id=tg_chat_id, title=title, chat_type=chat_type, owner_user_id=owner_id
        )
        session.add(target_chat)
    await session.commit()
    await session.refresh(target_chat)
    return target_chat


async def list_target_chats(session: AsyncSession, owner_id: int) -> list[TargetChat]:
    result = await session.execute(select(TargetChat).where(TargetChat.owner_user_id == owner_id))
    return list(result.scalars().all())


async def create_subscription(
    session: AsyncSession, channel_id: int, target_chat_id: int, tg_user_id: int
) -> Subscription:
    user_result = await session.execute(select(BotUser).where(BotUser.tg_user_id == tg_user_id))
    user = user_result.scalar_one()

    existing = await session.execute(
        select(Subscription).where(
            Subscription.channel_id == channel_id,
            Subscription.target_chat_id == target_chat_id,
        )
    )
    sub = existing.scalar_one_or_none()
    if sub:
        return sub

    sub = Subscription(owner_user_id=user.id, channel_id=channel_id, target_chat_id=target_chat_id)
    session.add(sub)
    await session.commit()
    await session.refresh(sub)
    return sub


async def list_subscriptions_for_user(session: AsyncSession, tg_user_id: int) -> list[Subscription]:
    user_result = await session.execute(select(BotUser).where(BotUser.tg_user_id == tg_user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        return []

    result = await session.execute(
        select(Subscription)
        .options(selectinload(Subscription.channel), selectinload(Subscription.target_chat))
        .where(Subscription.owner_user_id == user.id)
    )
    return list(result.scalars().all())


async def delete_subscription(session: AsyncSession, sub_id: int, tg_user_id: int) -> None:
    user_result = await session.execute(select(BotUser).where(BotUser.tg_user_id == tg_user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        return

    sub = await session.get(Subscription, sub_id)
    if sub and sub.owner_user_id == user.id:
        await session.delete(sub)
        await session.commit()


async def list_targets_for_channel(session: AsyncSession, channel_id: int) -> list[int]:
    result = await session.execute(
        select(TargetChat.tg_chat_id)
        .join(Subscription, Subscription.target_chat_id == TargetChat.id)
        .where(Subscription.channel_id == channel_id)
    )
    return [row[0] for row in result.all()]
