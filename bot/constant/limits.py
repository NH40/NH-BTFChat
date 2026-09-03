import datetime as dt

# Telegram content limits
MAX_TEXT_LENGTH = 4096
MAX_CAPTION_LENGTH = 1024

# Album (media group) buffering
ALBUM_DEBOUNCE_SECONDS = 1.5

# Deletion reconciliation
RECONCILE_INTERVAL_SECONDS = 5 * 60
RECONCILE_WINDOW = dt.timedelta(days=3)
RECONCILE_BATCH_SIZE = 25

# Add-channel flow
CANCEL_WORDS = {"отмена", "cancel", "/cancel"}
