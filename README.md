# Агент Клауд — AI Telegram Assistant

Бесплатный AI-ассистент в Telegram.

## Быстрый старт (локально)

```bash
pip install -r requirements.txt
cp .env.example .env
# отредактируй .env
python bot.py
```

## AI провайдеры

| Провайдер | Стоимость | Лимиты | Как получить |
|-----------|-----------|--------|-------------|
| **Ollama** | Бесплатно | Без лимитов | [ollama.ai](https://ollama.ai) — скачай и запусти |
| **OpenRouter** | Бесплатно | 50 запросов/день | [openrouter.ai](https://openrouter.ai) |
| **HuggingFace** | Бесплатно | ~1000 запросов/день | [huggingface.co](https://huggingface.co/settings/tokens) |

В `.env` укажи `AI_PROVIDER`:

```env
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-...
```

## Деплой на сервер (24/7)

### Вариант 1: Docker (любой сервер)

```bash
git clone <repo>
cd agent-claud
cp .env.example .env
# отредактируй .env
docker compose up -d
```

### Вариант 2: Oracle Cloud Free Tier (навсегда бесплатно)

1. Зарегистрируйся на [cloud.oracle.com](https://cloud.oracle.com)
2. Создай VM: Ubuntu 22.04, 4 CPU, 24GB RAM (Free Tier)
3. Подключись по SSH:

```bash
# Установи Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Клонируй проект
git clone <repo>
cd agent-claud
cp .env.example .env
nano .env  # вставь токены

# Запусти
docker compose up -d
```

Если хочешь Ollama на сервере:

```bash
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3.2
# В .env: AI_PROVIDER=ollama
docker compose up -d
```

### Вариант 3: Railway.app (бесплатно, но с лимитами)

1. Зарегистрируйся на [railway.app](https://railway.app)
2. Подключи GitHub репозиторий
3. Добавь переменные окружения в настройках
4. Railway автоматически задеплоит

## Команды бота

- `/start` — приветствие
- `/help` — справка
- `/notes` — мои заметки
- `/reminders` — мои напоминания
- `/clear` — очистить историю

## Архитектура

```
bot.py        — Telegram бот + AI провайдеры
tools.py      — инструменты (поиск, погода, заметки, напоминания)
database.py   — SQLite (заметки, напоминания, история)
config.py     — настройки
data/bot.db   — база данных (создаётся автоматически)
```

## Требования

- Python 3.10+
- Telegram-токен от @BotFather
- Один из AI провайдеров (Ollama / OpenRouter / HuggingFace)
