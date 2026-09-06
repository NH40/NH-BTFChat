"""Telegram parses messages with parse_mode=HTML, so any '<' that is not part of
an allowed tag makes the API reject the whole message (and the button "does not open").
Guard the user-facing texts against stray angle brackets like ``<вселенная>``.
"""

import re

import pytest

from bot.texts import help as help_texts
from bot.texts import tournament as tournament_texts

_ALLOWED_TAG = re.compile(r"</?(b|i|u|s|a|code|pre|tg-spoiler|blockquote)(\s[^<>]*)?>")


def _stray_angle_brackets(text: str) -> str:
    return _ALLOWED_TAG.sub("", text)


def _collect_strings(module) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for name in dir(module):
        if name.startswith("_"):
            continue
        value = getattr(module, name)
        if isinstance(value, str):
            found.append((name, value))
        elif isinstance(value, dict):
            for key, item in value.items():
                if isinstance(item, str):
                    found.append((f"{name}[{key!r}]", item))
                elif isinstance(item, tuple):
                    for part in item:
                        if isinstance(part, str):
                            found.append((f"{name}[{key!r}]", part))
    return found


@pytest.mark.parametrize("module", [help_texts, tournament_texts])
def test_no_stray_angle_brackets_in_texts(module):
    offenders = [
        name
        for name, text in _collect_strings(module)
        if "<" in _stray_angle_brackets(text) or ">" in _stray_angle_brackets(text)
    ]
    assert not offenders, f"stray angle brackets in {module.__name__}: {offenders}"
