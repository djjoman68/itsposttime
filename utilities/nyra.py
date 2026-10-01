"""Reads race data from NYRA's public racing pages (no API, no login).

    current_race(html)  -> the race NYRA is currently counting down to
    parse_race(html)    -> full detail for one race: post time, distance,
                           surface, and every horse's program number, odds, ML
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

NYRA_TZ = ZoneInfo("America/New_York")   # NYRA post times are Eastern
BASE_URL = "https://www.nyra.com"


def track_page_url(track):
    return f"{BASE_URL}/{track}/racing/"


def race_fragment_url(track, race_num):
    """Lightweight per-race page the NYRA site itself loads when you switch races."""
    return f"{BASE_URL}/{track}/rdl/race/?race={race_num}"


def race_page_url(track, race_num):
    """Full page for one race - fallback if the lightweight page ever changes."""
    return f"{BASE_URL}/{track}/racing/?race={race_num}"


def parse_post_time(value):
    """'2026-10-01T14:10:00' (Eastern, no zone) -> aware datetime."""
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=NYRA_TZ)


def minutes_to_post(post_time_iso, now=None):
    now = now or datetime.now(NYRA_TZ)
    secs = (parse_post_time(post_time_iso) - now).total_seconds()
    # Round up so "4 MTP" means post is within the next 4 minutes, like the tote board
    return max(0, int(-(-secs // 60)))


def current_race(html):
    """Race number and post time NYRA's page header is counting down to.
    Returns (race_number, post_time_iso) or (None, None) if nothing is upcoming."""
    soup = BeautifulSoup(html, "html.parser")
    badge = soup.find("span", class_="mtp-badge", attrs={"data-mtp-variant": "header"})
    if badge is None or not badge.get("data-post-time"):
        return None, None
    label = badge.find_previous_sibling("span")
    digits = "".join(c for c in (label.get_text() if label else "") if c.isdigit())
    if not digits:
        return None, None
    return digits, badge["data-post-time"]


def parse_race(html):
    """Detail for the race shown on the page, or None if the page layout isn't recognized."""
    soup = BeautifulSoup(html, "html.parser")

    badge = soup.find("span", class_="mtp-badge", attrs={"data-mtp-variant": "default"})
    if badge is None or not badge.get("data-post-time"):
        return None
    block = badge.find_parent("div", class_=lambda c: c and "items-baseline" in c)
    if block is None or block.find("header") is None:
        return None

    race_num = block.find("header").get_text(strip=True).replace("Race", "").strip()

    distance_div = block.find("div", attrs={"title": True})
    distance = distance_div.get_text(strip=True) if distance_div else ""
    surface = ""
    if distance_div:
        nxt = distance_div.find_next_sibling("div")
        surface = nxt.get_text(strip=True) if nxt else ""

    horses = []
    for odds_div in soup.find_all("div", attrs={"title": "Current Odds"}):
        row = odds_div.find_parent("div", class_=lambda c: c and "items-start" in c)
        if row is None:
            continue
        num_div = row.find("div", class_=lambda c: c and "order-1" in c)
        ml_div = row.find("div", attrs={"title": "Morning Line Odds"})
        horses.append({
            "program": num_div.get_text(strip=True) if num_div else "?",
            "odds": odds_div.get_text(strip=True),
            "ml": ml_div.get_text(strip=True).replace("ML", "").strip() if ml_div else "",
        })

    return {
        "race": race_num,
        "post_time": badge["data-post-time"],
        "distance": distance,
        "surface": surface,
        "horses": horses,
    }
