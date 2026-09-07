from aiogram import Router

from bot.handlers import channels, membership, posts, start

routers: list[Router] = [
    start.router,
    channels.router,
    membership.router,
    posts.router,
]

__all__ = ["routers"]
