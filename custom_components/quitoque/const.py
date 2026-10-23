"""Constants for the Quitoque integration."""

from datetime import timedelta

DOMAIN = "quitoque"
PLATFORMS = ["sensor", "button"]

CONF_RECIPES_URL = "recipes_url"
CONF_TARGET_CALENDAR = "target_calendar"
CONF_EVENT_PREFIX = "event_prefix"
CONF_PDF_RETENTION_DAYS = "pdf_retention_days"
CONF_NOTIFY_AFTER_SYNC = "notify_after_sync"
CONF_NOTIFY_NEW_ORDER = "notify_new_order"
CONF_NOTIFY_BEFORE_DEADLINE = "notify_before_deadline"
CONF_NOTIFY_DEADLINE_DAYS = "notify_deadline_days"
CONF_NOTIFY_REMINDER_TIME = "reminder_send_time"
CONF_NOTIFY_CHANNEL = "notify_channel"
CONF_NOTIFY_MOBILE_TARGETS = "notify_mobile_targets"
CONF_NOTIFY_NEW_TITLE = "notify_new_title"
CONF_NOTIFY_DEADLINE_TITLE = "notify_deadline_title"
CONF_NOTIFY_MOBILE_NEW_MESSAGE = "notify_mobile_new_message"
CONF_NOTIFY_MOBILE_DEADLINE_MESSAGE = "notify_mobile_deadline_message"
CONF_EVENT_START = "event_start"
CONF_EVENT_DURATION = "event_duration"

DEFAULT_NAME = "Quitoque"
DEFAULT_SCAN_INTERVAL = timedelta(hours=6)
DEFAULT_EVENT_START = "18:00:00"
DEFAULT_EVENT_DURATION = 60
DEFAULT_PDF_RETENTION_DAYS = 7
DEFAULT_NOTIFY_AFTER_SYNC = False
DEFAULT_NOTIFY_DEADLINE_DAYS = 3
DEFAULT_NOTIFY_REMINDER_TIME = "08:00:00"
DEFAULT_NOTIFY_NEW_TITLE = "Nouvelle sélection Quitoque disponible"
DEFAULT_NOTIFY_DEADLINE_TITLE = "Quitoque : clôture des recettes"
DEFAULT_NOTIFY_MOBILE_NEW_MESSAGE = "Votre box du {delivery_date} est maintenant modifiable. Choisissez vos recettes !"
DEFAULT_NOTIFY_MOBILE_DEADLINE_MESSAGE = "Votre box du {delivery_date} sera clôturée le {deadline_date} à 23h59. Vérifiez vos recettes !"

BASE_URL = "https://www.quitoque.fr"
LOGIN_URL = f"{BASE_URL}/login"
LOGIN_CHECK_URL = f"{BASE_URL}/login-check"
DASHBOARD_URL = f"{BASE_URL}/tableau-de-bord"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

MARKER_PREFIX = "HA_QUITOQUE"
