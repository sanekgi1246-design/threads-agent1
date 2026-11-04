"""Главный шаг агента: выбрать рубрику → собрать факты → написать пост → проверить → опубликовать.

Запуск:  python -m agent.post          (DRY_RUN=1 — только показать, не публиковать)
"""
import difflib
import random
from datetime import datetime, timezone

import llm, sources, telegram
from common import DRY_RUN, env, load_config, load_state, log_error, now_iso, save_state
from threads_api import Threads


def engagement_score(ins: dict) -> float:
    """Взвешенная вовлечённость на просмотр: ответы и репосты ценнее лайков."""
    views = ins.get("views") or 0
    if views < 20:
        return None
    pts = ins.get("likes", 0) + 3 * ins.get("replies", 0) + 4 * (
        ins.get("reposts", 0) + ins.get("quotes", 0) + ins.get("shares", 0))
    return pts / views


def rubric_stats(state: dict, rubrics: dict) -> dict:
    stats = {k: [] for k in rubrics}
    for p in state["posts"]:
        s = engagement_score(p.get("insights") or {})
        if s is not None and p.get("rubric") in stats:
            stats[p["rubric"]].append(s)
    return stats


def pick_rubric(state: dict, cfg: dict) -> str:
    rubrics, lc = cfg["rubrics"], cfg["learning"]
    stats = rubric_stats(state, rubrics)
    under = [k for k, v in stats.items() if len(v) < lc["min_posts_per_rubric"]]
    last = state["posts"][-1]["rubric"] if state["posts"] else None
    if under:  # сначала даём каждой рубрике шанс
        pool = [k for k in under if k != last] or under
        return random.choice(pool)
    if random.random() < lc["explore_rate"]:
        return random.choice([k for k in rubrics if k != last])
    ranked = sorted(stats, key=lambda k: sum(stats[k]) / len(stats[k]), reverse=True)
    return ranked[0] if ranked[0] != last else ranked[1]


def best_examples(state: dict, n: int = 3) -> list[str]:
    scored = [(engagement_score(p.get("insights") or {}), p["text"]) for p in state["posts"]]
    scored = [x for x in scored if x[0] is not None]
    return [t for _, t in sorted(scored, reverse=True)[:n]]


SYSTEM = """Ты — автор постов для Threads в нише: {niche}.
Голос: {voice}
Жёсткие правила:
- Язык: {language}. Длина: до {max_chars} символов, включая пробелы.
- Используй ТОЛЬКО цифры и факты из блока «Факты». Нет факта — не пиши цифру.
- Никаких финансовых советов, прогнозов цены, призывов купить/продать, обещаний дохода.
- Не упоминай Telegram и ссылки — это добавится отдельно.
- Не повторяй темы и формулировки недавних постов.
Верни строго JSON: {{"topic": "тема в 3-6 словах", "text": "готовый текст поста"}}"""


def build_prompt(cfg: dict, rubric_key: str, state: dict) -> str:
    r = cfg["rubrics"][rubric_key]
    facts = sources.market_snapshot(cfg["market"]["coins"])
    if r.get("needs_news"):
        news = sources.latest_news(cfg["news_feeds"])
        facts += "\n\nСвежие заголовки:\n" + "\n".join(f"- {t}" for t in news)
    recent = "\n".join(f"- {p.get('topic', '')}: {p['text'][:120]}" for p in state["posts"][-15:])
    examples = "\n---\n".join(best_examples(state))
    return (f"Рубрика: «{r['title']}». Задача: {r['brief']}\n\n"
            f"Дата: {datetime.now(timezone.utc):%d.%m.%Y}\n\nФакты:\n{facts}\n\n"
            f"Недавние посты (не повторяй):\n{recent or 'пока нет'}\n\n"
            f"Посты, которые зашли лучше всего (ориентир по стилю, не копируй):\n{examples or 'пока нет'}")


def validate(text: str, cfg: dict, state: dict) -> str | None:
    if not text or len(text) > cfg["posting"]["max_chars"]:
        return f"длина {len(text or '')} > {cfg['posting']['max_chars']}"
    low = text.lower()
    for bad in cfg["banned_phrases"]:
        if bad.lower() in low:
            return f"запрещённая фраза «{bad}»"
    if "http" in low or "t.me" in low:
        return "ссылка в основном посте"
    for p in state["posts"][-30:]:
        if difflib.SequenceMatcher(None, low, p["text"].lower()).ratio() > cfg["posting"]["similarity_threshold"]:
            return "слишком похож на недавний пост"
    return None


def posts_today(state: dict) -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    return sum(1 for p in state["posts"] if p["created_at"].startswith(today))


def main():
    cfg = load_config()
    state = load_state()
    if posts_today(state) >= cfg["posting"]["max_posts_per_day"] and not DRY_RUN:
        print("Дневной лимит постов достигнут")
        return

    rubric = pick_rubric(state, cfg)
    system = SYSTEM.format(niche=cfg["niche"], voice=cfg["voice"], language=cfg["language"],
                           max_chars=cfg["posting"]["max_chars"])
    prompt = build_prompt(cfg, rubric, state)

    draft, problem = None, None
    for attempt in range(4):
        extra = f"\n\nПредыдущая версия отклонена: {problem}. Исправь." if problem else ""
        try:
            draft = llm.chat_json(system, prompt + extra)
        except Exception as e:  # noqa: BLE001
            problem = str(e)[:200]
            continue
        draft["text"] = draft.get("text", "").strip()
        problem = validate(draft["text"], cfg, state)
        if not problem:
            break
    if problem:
        log_error(state, "generate", problem)
        save_state(state)
        telegram.notify(f"⚠️ Threads-агент не смог написать пост: {problem}")
        raise SystemExit(1)

    n = len(state["posts"]) + 1
    with_cta = n % cfg["telegram"]["cta_every"] == 0
    print(f"[{rubric}] {draft['topic']}\n{draft['text']}\n({len(draft['text'])} симв., CTA={with_cta})")
    if DRY_RUN:
        return

    threads = Threads(env("THREADS_ACCESS_TOKEN", required=True), env("THREADS_USER_ID", "me"))
    post_id = threads.publish_text(draft["text"])
    info = threads.post_info(post_id)
    record = {"id": post_id, "permalink": info.get("permalink"), "created_at": now_iso(),
              "rubric": rubric, "topic": draft.get("topic", ""), "text": draft["text"],
              "cta": None, "insights": {}, "tg_joins": 0}

    if with_cta:
        try:
            link = telegram.create_invite_link(f"th-{datetime.now(timezone.utc):%m%d%H%M}-{rubric[:10]}") \
                   or cfg["telegram"]["channel_url"]
            cta_text = random.choice(cfg["telegram"]["cta_templates"]).format(link=link)
            reply_id = threads.publish_text(cta_text, reply_to_id=post_id)
            record["cta"] = {"reply_id": reply_id, "link": link}
        except Exception as e:  # noqa: BLE001
            log_error(state, "cta", e)

    state["posts"].append(record)
    save_state(state)
    telegram.notify(f"✅ Опубликован пост [{cfg['rubrics'][rubric]['title']}]\n{record['permalink']}\n\n{draft['text']}")


if __name__ == "__main__":
    main()
