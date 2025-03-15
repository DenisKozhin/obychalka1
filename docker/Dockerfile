FROM python:3.10-slim-bullseye

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY . .

# Запуск бота
CMD ["python", "main.py"]
