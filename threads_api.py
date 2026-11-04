"""Тонкий клиент официального Threads API (graph.threads.net)."""
import time

import requests

BASE = "https://graph.threads.net/v1.0"
POST_METRICS = ["views", "likes", "replies", "reposts", "quotes", "shares"]
ACCOUNT_METRICS = ["views", "likes", "replies", "reposts", "quotes", "clicks"]


class ThreadsError(RuntimeError):
    pass


class Threads:
    def __init__(self, token: str, user_id: str = "me"):
        self.token = token
        self.user_id = user_id

    def _req(self, method: str, path: str, **params):
        params["access_token"] = self.token
        r = requests.request(method, f"{BASE}/{path}", params=params, timeout=30)
        data = r.json() if r.content else {}
        if r.status_code >= 400 or "error" in data:
            raise ThreadsError(f"{method} {path}: {data.get('error', r.text)}")
        return data

    # --- профиль ---
    def me(self):
        return self._req("GET", "me", fields="id,username,threads_profile_picture_url")

    # --- публикация: контейнер → публикация ---
    def publish_text(self, text: str, reply_to_id: str | None = None) -> str:
        params = {"media_type": "TEXT", "text": text}
        if reply_to_id:
            params["reply_to_id"] = reply_to_id
        creation = self._req("POST", f"{self.user_id}/threads", **params)["id"]
        time.sleep(3)  # Meta советует дать контейнеру обработаться
        for attempt in range(5):
            try:
                return self._req("POST", f"{self.user_id}/threads_publish", creation_id=creation)["id"]
            except ThreadsError:
                if attempt == 4:
                    raise
                time.sleep(10)

    def post_info(self, media_id: str):
        return self._req("GET", media_id, fields="id,permalink,timestamp,text")

    def publishing_limit(self):
        d = self._req("GET", f"{self.user_id}/threads_publishing_limit", fields="quota_usage,config")
        return (d.get("data") or [{}])[0]

    # --- метрики ---
    def post_insights(self, media_id: str) -> dict:
        d = self._req("GET", f"{media_id}/insights", metric=",".join(POST_METRICS))
        return {m["name"]: m["values"][0]["value"] for m in d.get("data", [])}

    def account_insights(self, since: int, until: int) -> dict:
        """Пробуем метрики пачкой, а если какая-то не поддерживается — по одной."""
        out = {}
        try:
            d = self._req("GET", f"{self.user_id}/threads_insights",
                          metric=",".join(ACCOUNT_METRICS), since=since, until=until)
            items = d.get("data", [])
        except ThreadsError:
            items = []
            for m in ACCOUNT_METRICS:
                try:
                    items += self._req("GET", f"{self.user_id}/threads_insights",
                                       metric=m, since=since, until=until).get("data", [])
                except ThreadsError:
                    pass
        for m in items:
            if "total_value" in m:
                out[m["name"]] = m["total_value"].get("value", 0)
            elif m.get("values"):
                out[m["name"]] = sum(v.get("value", 0) for v in m["values"])
            elif m.get("link_total_values"):
                out[m["name"]] = sum(v.get("value", 0) for v in m["link_total_values"])
        try:
            d = self._req("GET", f"{self.user_id}/threads_insights", metric="followers_count")
            out["followers_count"] = d["data"][0]["total_value"]["value"]
        except (ThreadsError, KeyError, IndexError):
            pass
        return out

    # --- токен ---
    @staticmethod
    def refresh_long_lived(token: str) -> dict:
        r = requests.get("https://graph.threads.net/refresh_access_token",
                         params={"grant_type": "th_refresh_token", "access_token": token}, timeout=30)
        data = r.json()
        if "access_token" not in data:
            raise ThreadsError(f"refresh failed: {data}")
        return data
