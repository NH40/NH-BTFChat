import re

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{5,32}$")
TME_LINK_RE = re.compile(r"(?:https?://)?(?:www\.)?t(?:elegram)?\.me/([A-Za-z0-9_]{5,32})/?$", re.IGNORECASE)
INVITE_LINK_RE = re.compile(r"t(?:elegram)?\.me/(\+|joinchat/)", re.IGNORECASE)
