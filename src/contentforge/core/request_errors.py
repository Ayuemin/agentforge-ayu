"""Concise, actionable diagnostics for OpenRouter requests.

Do not log Authorization headers, serialized prompts, or API credentials.
"""
from __future__ import annotations

import httpx


def describe_error(error: BaseException, *, timeout: int | None = None) -> str:
    name = type(error).__name__
    if isinstance(error, httpx.TimeoutException):
        wait = f" за {timeout} сек." if timeout else ""
        return (
            f"{name}: OpenRouter не ответил вовремя{wait} "
            "Проверь интернет, время ожидания в настройках и доступность модели."
        )
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        explanations = {
            400: "Некорректные параметры запроса или модель не принимает их.",
            401: "API-ключ OpenRouter отклонён.",
            402: "Недостаточно средств на OpenRouter.",
            403: "Нет доступа к модели или запросу.",
            404: "Модель не найдена или недоступна.",
            408: "Время ожидания запроса истекло на сервере.",
            413: "Слишком большой запрос или контекст.",
            422: "Некорректные входные данные.",
            429: "Превышен лимит запросов; попробуй позднее.",
            500: "Временная ошибка сервера.",
            502: "Ошибка шлюза сервера.",
            503: "Модель или сервер временно недоступны.",
            504: "Шлюз модели не дождался ответа.",
        }
        return f"HTTP {status}: {explanations.get(status, 'Ошибка OpenRouter.')}"
    if isinstance(error, httpx.TransportError):
        return f"{name}: ошибка соединения с OpenRouter. Проверь интернет."
    # Some exceptions (ReadTimeout, certain JSON/AssertionError cases) have
    # an empty str(), so preserve at least the exception type.
    message = str(error).strip()
    return f"{name}: {message[:350]}" if message else f"{name}: сообщение ошибки отсутствует"
