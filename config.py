"""
config.py - reads config/config.json and config/secrets.json.

Same pattern as the plane tracker: scenes import values from here, and the
web UI saves the JSON files. Race settings (track, view, paging) are read
live via config.reload() so web UI changes apply without a restart.
"""
import json
import os

_BASE     = os.path.dirname(os.path.abspath(__file__))
_CFG_PATH = os.path.join(_BASE, "config", "config.json")
_SEC_PATH = os.path.join(_BASE, "config", "secrets.json")

DEFAULT_CONFIG = {
    "racing": {
        "track": "belmont",           # "saratoga" or "belmont"
        "view": "full",               # "full" (odds board) or "big_mtp"
        "race_window_minutes": 90,    # show the race board when next post is this close
        "page_seconds": 5,            # flip interval for fields over 10 horses
        "poll_seconds": 20,           # how often to re-read odds during the race window
    },
    "location": {
        "temperature_location": "",       # "lat,lon" - set in the web UI
        "temperature_units": "imperial",
        "clock_format": "12hr",
    },
    "display": {
        "brightness": 100,
        "brightness_night": 50,
        "night_brightness": False,
        "night_start": "22:00",
        "night_end": "06:00",
        "gpio_slowdown": 2,
        "hat_pwm_enabled": False,
        "led_rgb_sequence": "RGB",
        "forecast_days": 3,
        "forecast_mode": "daily",
        "forecast_hourly_start": "05:00",
        "forecast_hourly_end": "09:00",
        "weather_alerts_enabled": True,
    },
}

DEFAULT_SECRETS = {"tomorrow_api_key": ""}


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def ensure_files():
    """Create default config files on first run so the web UI can load."""
    os.makedirs(os.path.dirname(_CFG_PATH), exist_ok=True)
    if not os.path.exists(_CFG_PATH):
        with open(_CFG_PATH, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
    if not os.path.exists(_SEC_PATH):
        with open(_SEC_PATH, "w") as f:
            json.dump(DEFAULT_SECRETS, f, indent=2)


def reload():
    """Reload config from disk - call after the web UI saves changes."""
    global RACE_TRACK, RACE_VIEW, RACE_WINDOW_MINUTES, RACE_PAGE_SECONDS, RACE_POLL_SECONDS
    global TEMPERATURE_LOCATION, TEMPERATURE_UNITS, CLOCK_FORMAT
    global BRIGHTNESS, BRIGHTNESS_NIGHT, NIGHT_BRIGHTNESS, NIGHT_START, NIGHT_END
    global GPIO_SLOWDOWN, HAT_PWM_ENABLED, LED_RGB_SEQUENCE
    global FORECAST_DAYS, FORECAST_MODE, FORECAST_HOURLY_START, FORECAST_HOURLY_END
    global WEATHER_ALERTS_ENABLED, MASTER_TRACKER, TOMORROW_API_KEY

    cfg, sec = _load(_CFG_PATH), _load(_SEC_PATH)
    race = {**DEFAULT_CONFIG["racing"], **cfg.get("racing", {})}
    loc  = {**DEFAULT_CONFIG["location"], **cfg.get("location", {})}
    disp = {**DEFAULT_CONFIG["display"], **cfg.get("display", {})}

    RACE_TRACK          = race["track"] if race["track"] in ("saratoga", "belmont") else "saratoga"
    RACE_VIEW           = race["view"] if race["view"] in ("full", "big_mtp") else "full"
    RACE_WINDOW_MINUTES = int(race["race_window_minutes"])
    RACE_PAGE_SECONDS   = max(2, int(race["page_seconds"]))
    RACE_POLL_SECONDS   = max(10, int(race["poll_seconds"]))   # never hammer NYRA

    TEMPERATURE_LOCATION = loc["temperature_location"]
    TEMPERATURE_UNITS    = loc["temperature_units"]
    CLOCK_FORMAT         = loc["clock_format"]

    BRIGHTNESS             = disp["brightness"]
    BRIGHTNESS_NIGHT       = disp["brightness_night"]
    NIGHT_BRIGHTNESS       = disp["night_brightness"]
    NIGHT_START            = disp["night_start"]
    NIGHT_END              = disp["night_end"]
    GPIO_SLOWDOWN          = disp["gpio_slowdown"]
    HAT_PWM_ENABLED        = disp["hat_pwm_enabled"]
    LED_RGB_SEQUENCE       = disp["led_rgb_sequence"]
    FORECAST_DAYS          = disp["forecast_days"]
    FORECAST_MODE          = disp["forecast_mode"]
    FORECAST_HOURLY_START  = disp["forecast_hourly_start"]
    FORECAST_HOURLY_END    = disp["forecast_hourly_end"]
    WEATHER_ALERTS_ENABLED = disp["weather_alerts_enabled"]

    MASTER_TRACKER   = ""   # plane-tracker master/slave mode is not used here
    TOMORROW_API_KEY = sec.get("tomorrow_api_key", "")


reload()
