"""Telegram: персональные ссылки-приглашения для атрибуции + уведомления админу."""
import requests

from common import env


def _api(method: str, **params):
    token = env("TG_BOT_TOKEN")
    if not token:
        return None
    r = requests.post(f"https://api.telegram.org/bot{token}/{method}", json=params, timeout=30)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method}: {data.get('description')}")
    return data["result"]


def enabled() -> bool:
    return bool(env("TG_BOT_TOKEN") and env("TG_CHANNEL_ID"))


def create_invite_link(name: str) -> str | None:
    """Отдельная ссылка на каждый CTA-пост — так видно, какой пост привёл подписчиков."""
    if not enabled():
        return None
    res = _api("createChatInviteLink", chat_id=env("TG_CHANNEL_ID"), name=name[:32])
    return res["invite_link"]


def member_count() -> int | None:
    if not enabled():
        return None
    return _api("getChatMemberCount", chat_id=env("TG_CHANNEL_ID"))


def fetch_joins(offset: int) -> tuple[dict, int]:
    """Читает события вступлений и группирует их по ссылке-приглашению.
    Telegram хранит апдейты 24 ч, метрики собираются каждые 3 ч — ничего не теряется."""
    if not enabled():
        return {}, offset
    joins: dict[str, int] = {}
    while True:
        updates = _api("getUpdates", offset=offset, timeout=0, limit=100,
                       allowed_updates=["chat_member"])
        if not updates:
            break
        for u in updates:
            offset = u["update_id"] + 1
            cm = u.get("chat_member")
            if not cm:
                continue
            old, new = cm["old_chat_member"]["status"], cm["new_chat_member"]["status"]
            link = (cm.get("invite_link") or {}).get("invite_link")
            if link and old in ("left", "kicked") and new == "member":
                joins[link] = joins.get(link, 0) + 1
    return joins, offset


def notify(text: str) -> None:
    chat = env("TG_ADMIN_CHAT_ID")
    if chat and env("TG_BOT_TOKEN"):
        try:
            _api("sendMessage", chat_id=chat, text=text[:4000], disable_web_page_preview=True)
        except Exception as e:  # noqa: BLE001
            print("notify failed:", e)
