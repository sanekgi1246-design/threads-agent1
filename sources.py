"""Реальные данные для постов, чтобы нейросеть не выдумывала цифры."""
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta

import requests

UA = {"User-Agent": "threads-crypto-agent/1.0"}


def market_snapshot(coins: list[str]) -> str:
    lines = []
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price",
                         params={"ids": ",".join(coins), "vs_currencies": "usd",
                                 "include_24hr_change": "true"}, headers=UA, timeout=20)
        for coin, d in r.json().items():
            lines.append(f"{coin}: ${d['usd']:,.2f} ({d.get('usd_24h_change', 0):+.1f}% за 24ч)")
    except Exception as e:  # noqa: BLE001
        print("coingecko:", e)
    try:
        fng = requests.get("https://api.alternative.me/fng/", headers=UA, timeout=20).json()["data"][0]
        lines.append(f"Индекс страха и жадности: {fng['value']} ({fng['value_classification']})")
    except Exception as e:  # noqa: BLE001
        print("fng:", e)
    return "\n".join(lines) or "нет свежих данных по рынку"


def latest_news(feeds: list[str], hours: int = 36, limit: int = 12) -> list[str]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    items = []
    for url in feeds:
        try:
            root = ET.fromstring(requests.get(url, headers=UA, timeout=20).content)
            for it in root.iter("item"):
                title = (it.findtext("title") or "").strip()
                pub = it.findtext("pubDate")
                try:
                    dt = parsedate_to_datetime(pub) if pub else None
                except (TypeError, ValueError):
                    dt = None
                if title and (dt is None or dt >= cutoff):
                    items.append(title)
        except Exception as e:  # noqa: BLE001
            print("feed", url, e)
    seen, out = set(), []
    for t in items:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out[:limit]
