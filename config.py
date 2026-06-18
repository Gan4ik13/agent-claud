import os
import base64
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DEFAULT_KEY_B64 = "c2stb3ItdjEtNDVhNGYzZWIxMzk3NzhhYTUyYzJjNmUwZWRiNDdkM2NmYTE4ZGNjYTg0MmIzMzBjNDNkMWJmN2IwMTk2ODYwYQ=="

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

AI_PROVIDER = os.getenv("AI_PROVIDER", "openrouter")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

OPENROUTER_API_KEY = base64.b64decode(DEFAULT_KEY_B64).decode()
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")

HF_API_KEY = os.getenv("HF_API_KEY", "")
HF_MODEL = os.getenv("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct")

DEFAULT_MODEL = OLLAMA_MODEL if AI_PROVIDER == "ollama" else (OPENROUTER_MODEL if AI_PROVIDER == "openrouter" else HF_MODEL)

DB_PATH = Path(__file__).parent / "data" / "bot.db"

WEATHER_CITIES = {
    "москва": "Moscow",
    "питер": "Saint Petersburg",
    "санкт-петербург": "Saint Petersburg",
    "петербург": "Saint Petersburg",
    "новосибирск": "Novosibirsk",
    "екатеринбург": "Yekaterinburg",
    "казань": "Kazan",
    "нижний новгород": "Nizhny Novgorod",
    "челябинск": "Chelyabinsk",
    "самара": "Samara",
    "омск": "Omsk",
    "ростов": "Rostov-on-Don",
    "ростов-на-дону": "Rostov-on-Don",
    "уфа": "Ufa",
    "волгоград": "Volgograd",
    "красноярск": "Krasnoyarsk",
    "спб": "Saint Petersburg",
    "мск": "Moscow",
}

SYSTEM_PROMPT = """Ты — Агент Клауд, персональный AI-ассистент Михаила.

О Михаиле:
- 31 год, живёт в Москве
- COO, 11 лет опыта
- Зарплата: 300к+ net, удалёнка
- Предпочтения: мясо, НЕ рыба/морепродукты/яйца/грибы

Твои инструменты:
- search_web: поиск в интернете (используй для любых вопросов требующих актуальной информации)
- get_weather: погода в городе
- get_currency: курсы валют ЦБ РФ
- add_note: сохранить заметку
- get_notes: показать заметки
- delete_note: удалить заметку
- add_reminder: поставить напоминание
- get_reminders: показать напоминания
- delete_reminder: удалить напоминание

Правила:
- Отвечай на русском, кратко и по делу
- Используй инструменты когда нужно найти актуальную информацию
- Для погоды спроси город если не указан
- Для напоминаний уточни время если не указано
- Не придумывай факты — лучше поищи в интернете
- Будь дружелюбным, но профессиональным
"""
