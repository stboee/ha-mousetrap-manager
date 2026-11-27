"""Constants for Mousetrap Manager."""

DOMAIN = "mousetrap_manager"
VERSION = "2026.11.27"
PLATFORMS = ["sensor", "binary_sensor", "button"]
DEFAULT_COOLDOWN = 30
STORAGE_VERSION = 1
SIGNAL_UPDATED = f"{DOMAIN}_updated"
CARD_URL = f"/{DOMAIN}/mousetrap-manager-card.js"

# Presentation only: every option remains a vibration-monitored snap trap.
SNAP_GRAPHICS = {
    "classic": ("Klassisk klappfelle", "snap"),
    "rapp_2": ("Rapp 2", "snap-rapp-2"),
    "biltema_giljotin": ("Biltema Giljotin", "snap-biltema-giljotin"),
}
