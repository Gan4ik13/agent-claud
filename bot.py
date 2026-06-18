import os
import sys
import json
import logging
import asyncio
import aiohttp
from aiohttp import web
import re
from datetime import datetime, timedelta
from typing import Optional

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import (
    TELEGRAM_BOT_TOKEN,
    AI_PROVIDER,
    OLLAMA_URL,
    OLLAMA_MODEL,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
    HF_API_KEY,
    HF_MODEL,
    DEFAULT_MODEL,
    DB_PATH,
    SYSTEM_PROMPT,
)
from database import Database
from tools import (
    init_tools,
    search_web,
    get_weather,
    get_currency,
    add_note,
    get_notes,
    delete_note,
    search_notes,
    add_reminder,
    get_reminders,
    delete_reminder,
    check_reminders,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("bot")

db = Database(DB_PATH)
init_tools(db)

WEB_PORT = int(os.environ.get("PORT", 8080))
SELF_URL = os.environ.get("SELF_URL", "")


async def ask_ai(messages: list[dict]) -> str:
    if AI_PROVIDER == "ollama":
        return await _ask_ollama(messages)
    elif AI_PROVIDER == "openrouter":
        return await _ask_openrouter(messages)
    elif AI_PROVIDER == "huggingface":
        return await _ask_huggingface(messages)
    else:
        return "AI не настроен. Укажи AI_PROVIDER в .env"


async def _ask_ollama(messages: list[dict]) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": 2048},
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                OLLAMA_URL,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"Ollama error {resp.status}: {text[:200]}")
                    return "AI временно недоступен. Попробуй позже."
                data = await resp.json()
                return data.get("message", {}).get("content", "Нет ответа от AI.")
    except asyncio.TimeoutError:
        return "AI не отвечает (таймаут). Проверь что Ollama запущен."
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        return f"Ошибка Ollama: {e}"


FALLBACK_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "qwen/qwen3-coder:free",
    "google/gemma-3-27b-it:free",
    "mistralai/mistral-small-3.2-24b-instruct:free",
    "meta-llama/llama-4-maverick:free",
    "deepseek/deepseek-r1-0528:free",
]


async def _ask_openrouter(messages: list[dict]) -> str:
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY is empty! Set it in Render Environment Variables.")
        return "OPENROUTER_API_KEY не задан. Настрой переменную окружения в Render."
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    models_to_try = [OPENROUTER_MODEL] + [m for m in FALLBACK_MODELS if m != OPENROUTER_MODEL]
    for i, model in enumerate(models_to_try):
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 2048,
            "temperature": 0.7,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{OPENROUTER_BASE_URL}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status == 429:
                        wait = min(5 * (i + 1), 30)
                        logger.warning(f"Rate limit (429) на {model}, ждём {wait}с...")
                        await asyncio.sleep(wait)
                        continue
                    if resp.status != 200:
                        text = await resp.text()
                        logger.error(f"OpenRouter error {resp.status} ({model}): {text[:300]}")
                        continue
                    data = await resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        content = choices[0].get("message", {}).get("content", "")
                        if content:
                            logger.info(f"OpenRouter OK ({model}), {len(content)} chars")
                            return content
                        logger.warning(f"OpenRouter empty content from {model}")
                        continue
                    logger.warning(f"OpenRouter no choices from {model}: {data}")
                    continue
        except asyncio.TimeoutError:
            logger.warning(f"OpenRouter timeout on {model}")
            continue
        except Exception as e:
            logger.error(f"OpenRouter error ({model}): {e}")
            continue
    return "AI временно недоступен. Попробуй через минуту."


async def _ask_huggingface(messages: list[dict]) -> str:
    prompt = ""
    for m in messages:
        role = "User" if m["role"] == "user" else ("System" if m["role"] == "system" else "Assistant")
        prompt += f"<|start_header_id|>{role}<|end_header_id|>\n{m['content']}\n"
    prompt += "<|start_header_id|>Assistant<|end_header_id|>\n"

    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 2048, "temperature": 0.7, "return_full_text": False},
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"https://api-inference.huggingface.co/models/{HF_MODEL}",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"HF error {resp.status}: {text[:200]}")
                    return "AI временно недоступен. Попробуй позже."
                data = await resp.json()
                return data[0]["generated_text"].strip()
    except asyncio.TimeoutError:
        return "AI не отвечает (таймаут)."
    except Exception as e:
        logger.error(f"HuggingFace error: {e}")
        return f"Ошибка HuggingFace: {e}"


def build_now_context() -> str:
    now = datetime.now()
    days_ru = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
    return f"Сейчас: {now.strftime('%d.%m.%Y %H:%M')}, {days_ru[now.weekday()]}"


def detect_tools(text: str, user_id: int) -> str:
    t = text.lower().strip()
    results = []

    weather_match = re.search(
        r"(?:погод[ауеы]|weather|температур[ауеы]).*?(?:в|в |во|город |городе)?\s*([а-яА-ЯёЁ\s\-]+?)(?:\?|\.|!|$)",
        t,
    )
    if weather_match:
        city = weather_match.group(1).strip()
        if city and len(city) > 1:
            from config import WEATHER_CITIES
            city_en = WEATHER_CITIES.get(city.lower(), city)
            results.append(get_weather(city_en))
        elif "погод" in t:
            results.append(get_weather("Moscow"))

    if re.search(r"(?:курс[аы]?|валют[аые]?\b|доллар|евро|юан|usd|eur|cny)", t):
        results.append(get_currency())

    note_match = re.search(r"(?:заметк[ауеы]|запомни|сохрани|note)\s*[:：]?\s*(.+)", t, re.I)
    if note_match:
        results.append(add_note(user_id, note_match.group(1).strip()))

    if re.search(r"(?:мои\s+)?(?:заметк[аи]|notes|список\s+заметок)", t):
        results.append(get_notes(user_id))

    del_note_match = re.search(r"(?:удали|убери|удалить)\s+заметк[ауеы]\s*#?(\d+)", t)
    if del_note_match:
        results.append(delete_note(user_id, int(del_note_match.group(1))))

    search_notes_match = re.search(r"(?:найти|поиск|найти\s+в\s+заметках|найти\s+заметку)\s+(.+)", t)
    if search_notes_match:
        results.append(search_notes(user_id, search_notes_match.group(1).strip()))

    remind_match = re.search(
        r"(?:напомнить|напомни|напоминание|reminder)\s+(.+?)(?:\s+(?:в |на )(\d{1,2}[:\.]\d{2}|\d{4}-\d{2}-\d{2}\s+\d{1,2}[:\.]\d{2}|завтра|послезавтра)\s*(?:утро|день|вечер|вечера|утра|\d{1,2}[:\.]\d{2})?)?$",
        t,
        re.I,
    )
    if remind_match:
        text_part = remind_match.group(1).strip()
        time_part = remind_match.group(2) if remind_match.group(2) else ""

        now = datetime.now()
        remind_time = None

        if "завтра" in t:
            base = now + timedelta(days=1)
        elif "послезавтра" in t:
            base = now + timedelta(days=2)
        else:
            base = now

        time_match = re.search(r"(\d{1,2})[:\.](\d{2})", time_part or text_part)
        if time_match:
            h, m = int(time_match.group(1)), int(time_match.group(2))
            remind_time = base.replace(hour=h, minute=m, second=0, microsecond=0)
            text_part = re.sub(r"(?:завтра|послезавтра)?\s*(?:в |на )?\d{1,2}[:\.]\d{2}", "", text_part).strip()

        if not remind_time:
            remind_time = base.replace(hour=9, minute=0, second=0, microsecond=0)

        if remind_time < now:
            remind_time += timedelta(days=1)

        text_part = re.sub(r"^(?:чтобы|чтоб|когда|про)\s*", "", text_part).strip()
        if text_part:
            results.append(add_reminder(user_id, text_part, remind_time))

    if re.search(r"(?:мои\s+)?(?:напоминани[яе]|reminders|список\s+напоминаний)", t):
        results.append(get_reminders(user_id))

    del_remind_match = re.search(r"(?:удали|убери|удалить)\s+напоминани[яе]\s*#?(\d+)", t)
    if del_remind_match:
        results.append(delete_reminder(user_id, int(del_remind_match.group(1))))

    search_trigger = any(
        w in t
        for w in [
            "найди", "поиск", "search", "найти", "погугли", "загугли",
            "яндекс", "интернет", "кто такой", "что такое", "где", "когда",
            "сколько", "почему", "зачем", "какой", "какая", "какие",
            "новости", "происходит", "сейчас", "актуально",
        ]
    )
    if search_trigger and not results:
        results.append(search_web(text))

    return "\n\n".join(results) if results else ""


async def safe_send(update: Update, text: str):
    try:
        if len(text) > 4000:
            for i in range(0, len(text), 4000):
                await update.message.reply_text(text[i : i + 4000])
        else:
            await update.message.reply_text(text)
    except Exception as e:
        logger.error(f"Send error: {e}")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_send(
        update,
        "Привет! Я Агент Клауд.\n\n"
        "Могу:\n"
        "— Искать в интернете\n"
        "— Погоду и курсы валют\n"
        "— Заметки и напоминания\n"
        "— Помочь с текстами и планами\n\n"
        "Просто напиши вопрос или скажи что нужно!",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_send(
        update,
        "Команды:\n"
        "/start — начать\n"
        "/help — помощь\n"
        "/clear — очистить историю\n"
        "/notes — мои заметки\n"
        "/reminders — мои напоминания\n\n"
        "Или просто напиши:\n"
        "— «заметка: купить молоко»\n"
        "— «напомни завтра в 10 позвонить»\n"
        "— «погода в Питере»\n"
        "— «курсы валют»\n"
        "— любой вопрос — поищу в интернете",
    )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db.clear_history(user_id)
    await safe_send(update, "История очищена. Контекст сброшен.")


async def notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    result = get_notes(user_id)
    await safe_send(update, result)


async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    result = get_reminders(user_id)
    await safe_send(update, result)


async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info = (
        f"Provider: {AI_PROVIDER}\n"
        f"Model: {DEFAULT_MODEL}\n"
        f"Token set: {'да' if TELEGRAM_BOT_TOKEN else 'НЕТ'}\n"
        f"OpenRouter key: {'задан' if OPENROUTER_API_KEY else 'НЕ ЗАДАН'}\n"
        f"Ollama URL: {OLLAMA_URL}\n"
        f"DB: {DB_PATH}"
    )
    await safe_send(update, f"Debug info:\n{info}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    await update.message.chat.send_action(action="typing")

    tool_result = await asyncio.to_thread(detect_tools, user_text, user_id)

    history = db.get_history(user_id, limit=12)
    messages = [{"role": "system", "content": SYSTEM_PROMPT + "\n\n" + build_now_context()}]
    for m in history:
        messages.append({"role": m["role"], "content": m["content"]})

    if tool_result:
        messages.append({"role": "user", "content": user_text})
        messages.append({
            "role": "assistant",
            "content": f"Данные из инструментов:\n\n{tool_result}\n\nОтветь на вопрос пользователя на основе этих данных. Кратко и по делу.",
        })
    else:
        messages.append({"role": "user", "content": user_text})

    db.add_message(user_id, "user", user_text)

    answer = await ask_ai(messages)

    db.add_message(user_id, "assistant", answer)
    await safe_send(update, answer)


async def reminder_checker(context: ContextTypes.DEFAULT_TYPE):
    due = db.get_due_reminders()
    for r in due:
        db.complete_reminder(r["id"])
        try:
            await context.bot.send_message(
                chat_id=r["user_id"],
                text=f"Напоминание: {r['text']}",
            )
        except Exception as e:
            logger.error(f"Failed to send reminder {r['id']}: {e}")


# ========== HTTP SERVER (for Koyeb) ==========

async def handle_health(request):
    return web.json_response({"status": "ok", "provider": AI_PROVIDER, "model": DEFAULT_MODEL})


async def handle_root(request):
    return web.json_response({"service": "Agent Claud", "status": "running"})


async def start_web_server():
    app_web = web.Application()
    app_web.router.add_get("/", handle_root)
    app_web.router.add_get("/health", handle_health)
    app_web.router.add_get("/healthz", handle_health)
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEB_PORT)
    await site.start()
    logger.info(f"HTTP сервер на порту {WEB_PORT}")


# ========== SELF-PINGER ==========

async def self_ping():
    if not SELF_URL:
        return
    while True:
        await asyncio.sleep(840)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{SELF_URL}/health", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    logger.info(f"Self-ping: {resp.status}")
        except Exception as e:
            logger.warning(f"Self-ping failed: {e}")


async def post_init(application):
    await start_web_server()
    job_queue = application.job_queue
    job_queue.run_repeating(reminder_checker, interval=30, first=10)
    asyncio.create_task(self_ping())


def main():
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: Set TELEGRAM_BOT_TOKEN in .env")
        sys.exit(1)

    if AI_PROVIDER == "openrouter" and not OPENROUTER_API_KEY:
        print("ERROR: Set OPENROUTER_API_KEY in .env for OpenRouter provider")
        sys.exit(1)

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("notes", notes_command))
    app.add_handler(CommandHandler("reminders", reminders_command))
    app.add_handler(CommandHandler("debug", debug_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info(f"Bot starting! Provider: {AI_PROVIDER}, Model: {DEFAULT_MODEL}")
    if AI_PROVIDER == "openrouter":
        logger.info(f"OpenRouter key: {'set' if OPENROUTER_API_KEY else 'MISSING!'}")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
