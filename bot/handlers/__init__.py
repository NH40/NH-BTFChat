from aiogram import Router

from bot.handlers import channels, membership, posts, start
from bot.handlers import tournament as tournament_handlers

routers: list[Router] = [
    start.router,
    channels.router,
    membership.router,
    posts.router,
    *tournament_handlers.routers,
]

__all__ = ["routers"]
