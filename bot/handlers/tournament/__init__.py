from aiogram import Router

from bot.handlers.tournament import admin, bracket, challenge, poll, profile, rounds, scoring

routers: list[Router] = [
    admin.router,
    poll.router,
    profile.router,
    challenge.router,
    rounds.router,
    scoring.router,
    bracket.router,
]

__all__ = ["routers"]
