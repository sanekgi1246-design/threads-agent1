"""Сбор метрик: посты (последние 30 дней), аккаунт, Telegram. Пишет в docs/data.json для дашборда."""
import time
from datetime import datetime, timedelta, timezone

import telegram
from common import env, load_state, log_error, now_iso, save_state
from threads_api import Threads


def main():
    state = load_state()
    threads = Threads(env("THREADS_ACCESS_TOKEN", required=True), env("THREADS_USER_ID", "me"))
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    for p in state["posts"]:
        if p["created_at"] < cutoff and p.get("insights"):
            continue  # старые посты уже не меняются — экономим лимиты API
        try:
            p["insights"] = threads.post_insights(p["id"])
            p["insights_at"] = now_iso()
        except Exception as e:  # noqa: BLE001
            log_error(state, f"insights {p['id']}", e)

    today = datetime.now(timezone.utc).date().isoformat()
    try:
        until = int(time.time())
        acc = threads.account_insights(since=until - 86400, until=until)
        acc["date"] = today
        state["account_history"] = [h for h in state["account_history"] if h["date"] != today] + [acc]
    except Exception as e:  # noqa: BLE001
        log_error(state, "account insights", e)

    try:
        joins, state["tg_update_offset"] = telegram.fetch_joins(state["tg_update_offset"])
        by_link = {p["cta"]["link"]: p for p in state["posts"] if p.get("cta")}
        for link, cnt in joins.items():
            if link in by_link:
                by_link[link]["tg_joins"] = by_link[link].get("tg_joins", 0) + cnt
        members = telegram.member_count()
        if members is not None:
            state["telegram_history"] = [h for h in state["telegram_history"] if h["date"] != today] + \
                                        [{"date": today, "members": members}]
    except Exception as e:  # noqa: BLE001
        log_error(state, "telegram", e)

    save_state(state)
    print("Метрики обновлены")


if __name__ == "__main__":
    main()
