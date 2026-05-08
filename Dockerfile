# Используем официальный образ Python
FROM python:3.11-slim as backend

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем Python-пакеты
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код бэкенда
COPY ./core .
COPY ./eduflow .
COPY ./manage.py .

# Открываем порт Django
EXPOSE 8000

# Команда для запуска (переопределяется в docker-compose)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]