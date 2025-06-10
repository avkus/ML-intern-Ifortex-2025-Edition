FROM python:3.11-slim

WORKDIR /app

# Установка git (и gcc для сборки wheel-зависимостей)
RUN apt-get update && apt-get install -y git gcc && rm -rf /var/lib/apt/lists/*

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Установка браузеров Playwright
RUN python -m playwright install --with-deps chromium

# Инициализация crawl4ai (если требуется)
RUN crawl4ai-setup || true

# Копирование кода сервиса
COPY main.py .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 