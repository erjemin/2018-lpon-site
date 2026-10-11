#!/usr/bin/env python3
"""
MCP (Model Context Protocol) сервер для интеграции локальной нейросети oMLX в PyCharm / Junie.

Данный скрипт реализует стандартный протокол MCP по транспорту stdio с использованием
исключительно стандартной библиотеки Python 3.12+ (urllib, json, sys, os).
Он транслирует команды от внешнего агента (Junie) в запросы к локальному REST API oMLX.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional


def load_env_file() -> None:
    """
    Загружает переменные окружения из файла .env в корне проекта,
    если они еще не установлены в системном окружении.
    Не перезаписывает уже существующие переменные окружения.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    candidate_paths = [
        os.path.join(project_root, ".env"),
        os.path.join(os.getcwd(), ".env"),
    ]

    for env_path in candidate_paths:
        if os.path.isfile(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        clean_line = line.strip()
                        if not clean_line or clean_line.startswith("#") or "=" not in clean_line:
                            continue
                        key, val = clean_line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip('"').strip("'")
                        if key and key not in os.environ:
                            os.environ[key] = val
                break
            except Exception:
                pass


# Автоматическая загрузка конфигурации из .env при старте скрипта
load_env_file()

# Конфигурация по умолчанию (динамически берется из переменных окружения / .env)
DEFAULT_OMLX_BASE_URL: str = os.environ.get("OMLX_BASE_URL", "http://127.0.0.1:8008/v1")
DEFAULT_OMLX_API_KEY: str = os.environ.get("OMLX_API_KEY", "")
DEFAULT_OMLX_MODEL: str = os.environ.get("OMLX_MODEL_NAME", "default")
REQUEST_TIMEOUT_SECONDS: int = int(os.environ.get("OMLX_TIMEOUT", "120"))


def make_omlx_request(endpoint: str, data: Optional[Dict[str, Any]] = None, method: str = "GET") -> Dict[str, Any]:
    """
    Выполняет HTTP-запрос к локальному REST API oMLX.

    :param endpoint: Относительный путь эндпоинта (например, '/chat/completions' или '/models').
    :param data: Тело запроса в формате словаря (для POST-запросов).
    :param method: HTTP-метод ('GET' или 'POST').
    :return: Распарсенный JSON-ответ от сервера oMLX.
    :raises RuntimeError: При ошибках подключения или получении некорректного ответа.
    """
    base_url = DEFAULT_OMLX_BASE_URL.rstrip("/")
    url = f"{base_url}{endpoint}"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEFAULT_OMLX_API_KEY}",
        "User-Agent": "MCP-oMLX-Bridge/1.0",
    }

    payload_bytes = json.dumps(data).encode("utf-8") if data is not None else None
    request = urllib.request.Request(url=url, data=payload_bytes, headers=headers, method=method)

    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            raw_body = response.read().decode("utf-8")
            return json.loads(raw_body)
    except urllib.error.HTTPError as error:
        err_msg = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ошибка oMLX API HTTP {error.code}: {err_msg}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Не удалось подключиться к oMLX по адресу {url}. Проверьте, запущен ли oMLX. Ошибка: {error.reason}"
        ) from error
    except Exception as error:
        raise RuntimeError(f"Непредвиденная ошибка при запросе к oMLX: {str(error)}") from error


def get_available_models() -> List[str]:
    """
    Получает список идентификаторов моделей, доступных на сервере oMLX.

    :return: Список строк с названиями моделей.
    """
    try:
        result = make_omlx_request("/models", method="GET")
        data = result.get("data", [])
        return [m.get("id", "") for m in data if isinstance(m, dict) and m.get("id")]
    except Exception:
        return []


def resolve_model_name(requested_model: str = "") -> str:
    """
    Определяет точное имя модели для использования в запросе.
    Если имя не указано или равно 'default', пытается автоматически выбрать
    первую доступную модель из списка активных на локальном сервере oMLX.

    :param requested_model: Запрошенное пользователем или конфигурацией имя модели.
    :return: Выбранное имя модели.
    """
    clean_model = requested_model.strip()
    if clean_model and clean_model.lower() != "default":
        return clean_model

    if DEFAULT_OMLX_MODEL and DEFAULT_OMLX_MODEL.lower() != "default":
        return DEFAULT_OMLX_MODEL

    available_models = get_available_models()
    if available_models:
        return available_models[0]

    return "default"


def tool_ask_local_model(
    prompt: str,
    system_prompt: str = "",
    model: str = "",
    temperature: float = 0.2,
    max_tokens: Optional[int] = None,
) -> str:
    """
    Отправляет запрос к локальной модели oMLX для генерации текста или решения задачи.

    :param prompt: Текст запроса (пользовательский промпт).
    :param system_prompt: Опциональная системная инструкция.
    :param model: Имя модели (если пусто, выбирается активная модель oMLX).
    :param temperature: Температура генерации (от 0.0 до 1.0).
    :param max_tokens: Ограничение на максимальное количество токенов в ответе.
    :return: Сгенерированный локальной моделью текст ответа.
    """
    target_model = resolve_model_name(model)

    messages: List[Dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload: Dict[str, Any] = {
        "model": target_model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    result = make_omlx_request("/chat/completions", data=payload, method="POST")

    choices = result.get("choices", [])
    if not choices:
        return "Ответ от oMLX пуст или не содержит вариантов (choices)."

    message_content = choices[0].get("message", {}).get("content", "")
    return str(message_content)


def tool_check_local_model_status() -> str:
    """
    Проверяет статус подключения к oMLX и возвращает список доступных локальных моделей.

    :return: Строка с отчетом о доступности сервера и списке загруженных моделей.
    """
    try:
        result = make_omlx_request("/models", method="GET")
        data = result.get("data", [])
        model_ids = [m.get("id", "unknown") for m in data if isinstance(m, dict)]
        models_str = ", ".join(model_ids) if model_ids else "Модели не обнаружены в ответе"
        return f"Сервер oMLX доступен по адресу {DEFAULT_OMLX_BASE_URL}. Доступные модели: {models_str}."
    except Exception as error:
        return f"Проверка статуса завершилась ошибкой: {str(error)}"


def tool_review_code_locally(code_snippet: str, instructions: str = "") -> str:
    """
    Выполняет локальный анализ и ревью фрагмента кода силами oMLX.

    :param code_snippet: Исходный код для анализа.
    :param instructions: Дополнительные требования к проверке (например, поиск багов, оптимизация).
    :return: Замечания и рекомендации локальной модели.
    """
    sys_prompt = (
        "Ты — опытный локальный ассистент по ревью кода. "
        "Проанализируй предоставленный фрагмент кода, найди потенциальные ошибки, "
        "узкие места и предложи конкретные улучшения без лишних вводных слов."
    )
    user_prompt = f"Код для ревью:\n```\n{code_snippet}\n```"
    if instructions:
        user_prompt += f"\n\nСпециальные указания:\n{instructions}"

    return tool_ask_local_model(prompt=user_prompt, system_prompt=sys_prompt, temperature=0.1)


# Спецификация поддерживаемых MCP-инструментов
MCP_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "ask_local_model",
        "description": (
            "Отправляет запрос локальной модели oMLX (на Apple Silicon) и возвращает ответ. "
            "Используется для делегирования локальных вычислений, обработки больших текстов, "
            "генерации вариантов или сохранения приватности."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Основной текст запроса или задачи для локальной модели.",
                },
                "system_prompt": {
                    "type": "string",
                    "description": "Опциональная системная инструкция для локальной модели.",
                },
                "model": {
                    "type": "string",
                    "description": "Имя конкретной модели oMLX. Если не указано, берется активная модель.",
                },
                "temperature": {
                    "type": "number",
                    "description": "Температура генерации (по умолчанию 0.2).",
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Максимальное количество токенов в ответе.",
                },
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "check_local_model_status",
        "description": "Проверяет доступность локального сервера oMLX и возвращает список моделей.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "review_code_locally",
        "description": "Запускает локальное ревью фрагмента кода на модели oMLX.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code_snippet": {
                    "type": "string",
                    "description": "Фрагмент кода для анализа.",
                },
                "instructions": {
                    "type": "string",
                    "description": "Особые пожелания или фокус внимания при анализе.",
                },
                "model": {
                    "type": "string",
                    "description": "Имя конкретной модели oMLX.",
                },
            },
            "required": ["code_snippet"],
        },
    },
]


def send_response(response: Dict[str, Any]) -> None:
    """
    Отправляет JSON-RPC ответ в стандартный поток вывода stdout.

    :param response: Словарь с ответом по спецификации JSON-RPC 2.0.
    """
    body = json.dumps(response, ensure_ascii=False)
    sys.stdout.write(body + "\n")
    sys.stdout.flush()


def handle_request(message: Dict[str, Any]) -> None:
    """
    Обрабатывает входящее JSON-RPC сообщение протокола MCP.

    :param message: Распарсенное входящее сообщение.
    """
    msg_id = message.get("id")
    method = message.get("method")
    params = message.get("params", {})

    # Уведомления без id (например, notifications/initialized) не требуют ответа
    if msg_id is None:
        return

    if method == "initialize":
        # Ответ на инициализацию сервера MCP
        send_response({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "omlx-local-bridge",
                    "version": "1.0.0"
                }
            }
        })
        return

    if method == "ping":
        send_response({"jsonrpc": "2.0", "id": msg_id, "result": {}})
        return

    if method == "tools/list":
        send_response({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": MCP_TOOLS
            }
        })
        return

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        try:
            if tool_name == "ask_local_model":
                max_tokens_val = arguments.get("max_tokens")
                output = tool_ask_local_model(
                    prompt=arguments.get("prompt", ""),
                    system_prompt=arguments.get("system_prompt", ""),
                    model=arguments.get("model", ""),
                    temperature=float(arguments.get("temperature", 0.2)),
                    max_tokens=int(max_tokens_val) if max_tokens_val is not None else None,
                )
            elif tool_name == "check_local_model_status":
                output = tool_check_local_model_status()
            elif tool_name == "review_code_locally":
                output = tool_review_code_locally(
                    code_snippet=arguments.get("code_snippet", ""),
                    instructions=arguments.get("instructions", ""),
                )
            else:
                send_response({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32601,
                        "message": f"Неизвестный инструмент: {tool_name}"
                    }
                })
                return

            send_response({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": output
                        }
                    ],
                    "isError": False
                }
            })
        except Exception as error:
            send_response({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Ошибка выполнения инструмента {tool_name}: {str(error)}"
                        }
                    ],
                    "isError": True
                }
            })
        return

    # Неподдерживаемый метод
    send_response({
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {
            "code": -32601,
            "message": f"Метод не поддерживается: {method}"
        }
    })


def main() -> None:
    """Главный цикл чтения сообщений из stdin."""
    for line in sys.stdin:
        clean_line = line.strip()
        if not clean_line:
            continue
        try:
            message = json.loads(clean_line)
            handle_request(message)
        except json.JSONDecodeError:
            # Игнорируем некорректные JSON-строки
            continue
        except Exception as error:
            # Логируем фатальные сбои в stderr
            sys.stderr.write(f"Ошибка MCP сервера: {str(error)}\n")
            sys.stderr.flush()


if __name__ == "__main__":
    main()
