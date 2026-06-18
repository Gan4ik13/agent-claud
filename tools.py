import logging
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional

from ddgs import DDGS

from database import Database

logger = logging.getLogger(__name__)

db: Optional[Database] = None


def init_tools(database: Database):
    global db
    db = database


# ========== SEARCH ==========

def search_web(query: str) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5, region="wt-wt"))
        if not results:
            return "Ничего не найдено по запросу: " + query
        lines = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            body = r.get("body", "")
            url = r.get("href", "")
            lines.append(f"{i}. {title}\n{body}\n{url}")
        return "\n\n".join(lines)
    except Exception as e:
        logger.error(f"[SEARCH ERROR] {e}")
        return f"Ошибка поиска: {e}"


# ========== WEATHER ==========

def get_weather(city: str = "Moscow") -> str:
    try:
        encoded = urllib.parse.quote(city)
        url = f"https://wttr.in/{encoded}?format=j1&lang=ru"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        current = data["current_condition"][0]
        temp = current["temp_C"]
        feels = current["FeelsLikeC"]
        desc = current.get("lang_ru", [{}])[0].get("value", current["weatherDesc"][0]["value"])
        humidity = current["humidity"]
        wind = current["windspeedKmph"]

        forecast_lines = []
        for day in data.get("weather", [])[:3]:
            date = day["date"]
            max_t = day["maxtempC"]
            min_t = day["mintempC"]
            forecast_lines.append(f"  {date}: {min_t}..{max_t}°C")

        forecast = "\n".join(forecast_lines) if forecast_lines else ""

        result = (
            f"Погода в {city}:\n"
            f"Температура: {temp}°C (ощущается {feels}°C)\n"
            f"{desc}, влажность {humidity}%, ветер {wind} км/ч"
        )
        if forecast:
            result += f"\n\nПрогноз на 3 дня:\n{forecast}"
        return result
    except Exception as e:
        logger.error(f"[WEATHER ERROR] {e}")
        return "Не удалось получить погоду. Попробуй позже."


# ========== CURRENCY ==========

def get_currency() -> str:
    try:
        url = "https://www.cbr-xml-daily.ru/daily_json.js"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        usd = data["Valute"]["USD"]
        eur = data["Valute"]["EUR"]
        cny = data["Valute"]["CNY"]

        def fmt(v):
            diff = v["Value"] - v["Previous"]
            sign = "+" if diff >= 0 else ""
            return f"{v['Value']:.2f} ₽ ({sign}{diff:.2f})"

        return (
            f"Курсы ЦБ РФ на {data.get('Date', 'сегодня')}:\n\n"
            f"USD: {fmt(usd)}\n"
            f"EUR: {fmt(eur)}\n"
            f"CNY: {fmt(cny)}"
        )
    except Exception as e:
        logger.error(f"[CURRENCY ERROR] {e}")
        return "Не удалось получить курсы. Попробуй позже."


# ========== NOTES ==========

def add_note(user_id: int, text: str, tags: str = "") -> str:
    note_id = db.add_note(user_id, text, tags)
    return f"Заметка #{note_id} сохранена: {text}"


def get_notes(user_id: int) -> str:
    notes = db.get_notes(user_id)
    if not notes:
        return "У тебя пока нет заметок."
    lines = []
    for n in notes:
        tags = f" [{n['tags']}]" if n.get("tags") else ""
        date = n["created_at"][:16] if n.get("created_at") else ""
        lines.append(f"#{n['id']}{tags} ({date}):\n{n['text']}")
    return "Твои заметки:\n\n" + "\n\n".join(lines)


def delete_note(user_id: int, note_id: int) -> str:
    if db.delete_note(user_id, note_id):
        return f"Заметка #{note_id} удалена."
    return f"Заметка #{note_id} не найдена."


def search_notes(user_id: int, query: str) -> str:
    notes = db.search_notes(user_id, query)
    if not notes:
        return f"Нет заметок по запросу: {query}"
    lines = []
    for n in notes:
        lines.append(f"#{n['id']}: {n['text'][:200]}")
    return "Найдено:\n" + "\n".join(lines)


# ========== REMINDERS ==========

def add_reminder(user_id: int, text: str, remind_at: datetime) -> str:
    reminder_id = db.add_reminder(user_id, text, remind_at)
    formatted = remind_at.strftime("%d.%m.%Y в %H:%M")
    return f"Напоминание #{reminder_id} поставлено на {formatted}: {text}"


def get_reminders(user_id: int) -> str:
    reminders = db.get_all_reminders(user_id)
    if not reminders:
        return "У тебя нет напоминаний."
    lines = []
    for r in reminders:
        status = "✓" if r["is_done"] else "⏳"
        try:
            dt = datetime.fromisoformat(r["remind_at"])
            when = dt.strftime("%d.%m.%Y %H:%M")
        except (ValueError, TypeError):
            when = r["remind_at"]
        lines.append(f"#{r['id']} {status} [{when}]: {r['text']}")
    return "Напоминания:\n\n" + "\n".join(lines)


def delete_reminder(user_id: int, reminder_id: int) -> str:
    if db.delete_reminder(user_id, reminder_id):
        return f"Напоминание #{reminder_id} удалено."
    return f"Напоминание #{reminder_id} не найдено."


def check_reminders() -> list[tuple[int, str]]:
    due = db.get_due_reminders()
    results = []
    for r in due:
        db.complete_reminder(r["id"])
        results.append((r["user_id"], f"Напоминание: {r['text']}"))
    return results
