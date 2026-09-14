from aiogram import Router

from bot.handlers import channels, membership, posts, start, tasks

routers: list[Router] = [
    start.router,
    channels.router,
    tasks.router,
    membership.router,
    posts.router,
]

__all__ = ["routers"]
