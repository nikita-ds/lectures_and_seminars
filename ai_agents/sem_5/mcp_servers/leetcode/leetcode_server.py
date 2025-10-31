import re
import json
import logging
import requests

from typing import Dict, Any, List
from mcp.server.fastmcp import FastMCP, Context

logger = logging.getLogger("leetcode_assistant")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


BASE_URL = "https://leetcode-api-pied.vercel.app/"


def format_problem_response(data: Dict) -> str:
    """
    Форматирует ответ с информацией о задаче.

    Args:
        data (Dict): словарь, полученный по запросу от API
    Return:
        response (str): отформатированный ответ API
    """
    title = data.get('title', 'Без названия')
    slug = data.get('slug', '')
    difficulty = data.get('difficulty', 'Неизвестно')
    description = data.get('content', 'Описание отсутствует')[:600] + "..." if 'content' in data else "Описание отсутствует"
    url = BASE_URL + f"problems/{slug}" if slug else ""
    
    logger.info(f"Форматирование ответа для задачи: {title} (Сложность: {difficulty})")
    
    response = (
        f"**{title}**"
        f"Сложность: **{difficulty}**"
        f"Описание: {description}"
    )

    if url:
        response += f"[Полная задача]({url})"

    return response

def format_user_response(data: Dict) -> str:
    """
    Форматирует ответ с полученной информацией о пользователе.
    
    Args:
        data (Dict): словарь, полученный по запросу от API
    Return:
        response (str): отформатированный ответ API
    """
    username = data.get('username', 'Неизвестный пользователь')
    profile = data.get('profile', {})
    real_name = profile.get('realName', 'Не указано')
    country = profile.get('countryName', 'Не указана')
    company = profile.get('company', 'Не указана')
    school = profile.get('school', 'Не указана')
    about_me = profile.get('aboutMe', 'Не указано')
    reputation = profile.get('reputation', 0)
    ranking = profile.get('ranking', 'Неизвестен')
        
    response = (
        f"**Профиль пользователя: {username}**\n\n"
        f"**Реальное имя:** {real_name}\n"
        f"**Рейтинг:** #{ranking}\n"
        f"**Репутация:** {reputation}\n"
    )
    
    if country != 'Не указана':
        response += f"**Страна:** {country}\n"

    if company != 'Не указана':
        response += f"**Компания:** {company}\n"

    if school != 'Не указана':
        response += f"**Школа:** {school}\n"

    if about_me != 'Не указано' and about_me.strip():
        response += f"**О себе:** {about_me}\n"
    
    return response

mcp = FastMCP(
    name="LeetCode ассистент",
    instructions="""
Ты — ассистент, который предоставляет доступ к задачам LeetCode.
Используй инструменты для получения задач по различным критериям.

Инструменты:
- get_daily_challenge: получить задачу дня
- get_problem_by_id: получить задачу по ID
- get_problem_by_slug: получить задачу по названию (slug)
- get_random_problem: получить случайную задачу
- search_problems: найти задачи по ключевым словам
- get_user_by_username: найти профиль пользователя по username

Примеры запросов пользователей:
- "Покажи задачу дня"
- "Получи задачу номер 154"
- "Как решить задачу Two Sum?"
- "Случайная задача"
- "Найди задачи про деревья"
- "Найди профиль пользователя awice"
"""
)

@mcp.tool(
    name="get_daily_challenge",
    description="Возвращает задачу дня с LeetCode",
    annotations={
        "title": "Задача дня LeetCode",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
def get_daily_challenge(context: Context) -> str:
    """
    Возвращает задачу дня с LeetCode.

    Args:
        context (Context): контекст выполнения действий
    Returns:
        (str): JSON с данными
    """
    logger.info("Запрос задачи дня")
    api_url = BASE_URL + "daily"

    try:
        response = requests.get(api_url)
        logger.info(f"API запрос к {api_url} выполнен. Статус код: {response.status_code}")
        
        response.raise_for_status()
        data = response.json()

        logger.info(f"Получена задача дня: {data.get('title', 'Без названия')}")
        
        return json.dumps(response.json(), ensure_ascii=False, indent=2)
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при получении задачи дня: {str(e)}")

        return json.dumps(
            {
                "error": f"Не удалось получить данные: {str(e)}"
            }
        )
    except json.JSONDecodeError:
        logger.error("Некорректный формат ответа от API")

        return json.dumps(
            {
                "error": "Некорректный формат ответа от API"
            }
        )

@mcp.tool(
    name="get_problem_by_id",
    description="Возвращает задачу LeetCode по её id",
    annotations={
        "title": "Задача по id",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
def get_problem_by_id(
    context: Context, 
    problem_id: int
) -> str:
    """
    Возвращает задачу LeetCode по её id.

    Args:
        context (Context): контекст выполнения действий
        problem_id (int): id задачи
    Returns:
        (str): JSON с данными
    """
    logger.info(f"Запрос задачи по id: {problem_id}")
    api_url = BASE_URL + f"problem/{problem_id}"

    try:
        response = requests.get(api_url)
        logger.info(f"API запрос к {api_url} выполнен. Статус код: {response.status_code}")
        
        response.raise_for_status()
        data = response.json()

        logger.info(f"Получена задача #{problem_id}: {data.get('title', 'Без названия')}")
        
        return json.dumps(response.json(), ensure_ascii=False, indent=2)
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при получении задачи #{problem_id}: {str(e)}")

        return json.dumps(
            {
                "error": f"Не удалось получить данные: {str(e)}"
            }
        )
    except json.JSONDecodeError:
        logger.error("Некорректный формат ответа от API")

        return json.dumps(
            {
                "error": "Некорректный формат ответа от API"
            }
        )

@mcp.tool(
    name="get_problem_by_slug",
    description="Возвращает задачу LeetCode по её slug (названию в URL).",
    annotations={
        "title": "Задача по названию",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
def get_problem_by_slug(
    context: Context, 
    slug: str
) -> str:
    """
    Возвращает задачу LeetCode по её slug (названию в URL).

    Args:
        context (Context): контекст выполнения действий
        slug (str): slug задачи (например, "swap-nodes-in-pairs")
    Returns:
        (str): JSON с данными
    """
    logger.info(f"Запрос задачи по slug: {slug}")
    api_url = BASE_URL + f"problem/{slug}"

    try:
        response = requests.get(api_url)
        logger.info(f"API запрос к {api_url} выполнен. Статус код: {response.status_code}")
        
        response.raise_for_status()
        data = response.json()
        logger.info(f"Получена задача: {data.get('title', 'Без названия')} (slug: {slug})")
        
        return json.dumps(response.json(), ensure_ascii=False, indent=2)
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при получении задачи по slug '{slug}': {str(e)}")

        return json.dumps(
            {
                "error": f"Не удалось получить данные: {str(e)}"
            }
        )
    except json.JSONDecodeError:
        logger.error("Некорректный формат ответа от API")

        return json.dumps(
            {
                "error": "Некорректный формат ответа от API"
            }
        )

@mcp.tool(
    name="get_random_problem",
    description="Возвращает случайную задачу с LeetCode.",
    annotations={
        "title": "Случайная задача",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
def get_random_problem(context: Context) -> str:
    """
    Возвращает случайную задачу с LeetCode.

    Args:
        context (Context): контекст выполнения действий
    Returns:
        (str): JSON с данными
    """
    logger.info("Запрос случайной задачи")
    api_url = BASE_URL + "random"

    try:
        response = requests.get(api_url)
        logger.info(f"API запрос к {api_url} выполнен. Статус код: {response.status_code}")
        
        response.raise_for_status()
        data = response.json()

        logger.info(f"Получена случайная задача: {data.get('title', 'Без названия')}")
        
        return json.dumps(response.json(), ensure_ascii=False, indent=2)
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при получении случайной задачи: {str(e)}")

        return json.dumps(
            {
                "error": f"Не удалось получить данные: {str(e)}"
            }
        )
    except json.JSONDecodeError:
        logger.error("Некорректный формат ответа от API")

        return json.dumps(
            {
                "error": "Некорректный формат ответа от API"
            }
        )

@mcp.tool(
    name="search_problems",
    description="Ищет задачи LeetCode по ключевым словам.",
    annotations={
        "title": "Поиск задач",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
def search_problems(
    context: Context, 
    query: str
) -> str:
    """
    Ищет задачи LeetCode по ключевым словам.

    Args:
        context (Context): контекст выполнения действий
        query (str): поисковый запрос
    Returns:
        (str): JSON с данными
    """
    logger.info(f"Поиск задач по запросу: {query}")
    api_url = BASE_URL + f"search?query={query}"

    try:
        response = requests.get(api_url)
        logger.info(f"API запрос к {api_url} выполнен. Статус код: {response.status_code}")
        
        response.raise_for_status()
        data = response.json()

        logger.info(f"Найдено {len(data.get('problems', []))} задач по запросу '{query}'")
        
        return json.dumps(response.json(), ensure_ascii=False, indent=2)
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при поиске задач по запросу '{query}': {str(e)}")

        return json.dumps(
            {
                "error": f"Не удалось выполнить поиск: {str(e)}"
            }
        )
    except json.JSONDecodeError:
        logger.error("Некорректный формат ответа от API")

        return json.dumps(
            {
                "error": "Некорректный формат ответа от API"
            }
        )
    
@mcp.tool(
    name="get_user_by_username",
    description="Возвращает профиль пользователя LeetCode по его username.",
    annotations={
        "title": "Профиль пользователя",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
def get_user_by_username(
    context: Context, 
    username: str
) -> str:
    """
    Возвращает профиль пользователя LeetCode по его username.

    Args:
        context (Context): контекст выполнения действий
        username (str): username пользователя
    Returns:
        (str): JSON с данными
    """
    logger.info(f"Запрос профиля пользователя по username: {username}")
    api_url = BASE_URL + f"user/{username}"
    
    try:
        context.info(f"INFO: Ищем пользователя с username: {username}")
        response = requests.get(api_url)
        logger.info(f"API запрос к {api_url} выполнен. Статус код: {response.status_code}")

        response.raise_for_status()
        data = response.json()

        logger.info(f"Получен профиль пользователя {username}: {data.get('profile', {}).get('realName', 'Аноним')}")

        return json.dumps(response.json(), ensure_ascii=False, indent=2)
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при получении профиля пользователя {username}: {str(e)}")

        return json.dumps(
            {
                "error": f"Не удалось получить данные: {str(e)}"
            }
        )
    except json.JSONDecodeError:
        logger.error("Некорректный формат ответа от API")

        return json.dumps(
            {
                "error": "Некорректный формат ответа от API"
            }
        )

@mcp.prompt(
    name="handle_leetcode_query",
    description="Обрабатывает запросы пользователя к LeetCode, определяет нужные инструменты и возвращает структурированный ответ."
)
def handle_leetcode_query(
    prompt: str, 
    context: Context
) -> List[Dict[str, Any]]:
    """
    Обработчик запросов к LeetCode.

    Распознает и обрабатывает:
    - запросы на получение задачи дня
    - запросы на получение задачи по id
    - запросы на получение задачи по названию
    - запросы на получение случайной задачи
    - поисковые запросы
    - запрос профиля пользователя по username

    Args:
        prompt (str): вопрос пользователя
        context (Context): контекст выполнения действий
    Returns:
        (List[Dict]): список сообщений в формате:
            [
                {
                    "role": "assistant", 
                    "content": "Форматированный ответ"
                }
            ]
    """
    logger.info(f"Получен запрос от пользователя: '{prompt}'")
    
    prompt_lower = prompt.lower().strip()
    
    if any(keyword in prompt_lower for keyword in ["профиль", "статистика", "пользователь", "ник", "username"]):
        logger.info("Обнаружен запрос на получение профиля пользователя")
        username_match = re.search(r'(?:пользователь|ник|username|участник)\s*[:@\s]*([a-zA-Z0-9_-]+)', prompt_lower)

        if not username_match:
            words = prompt_lower.split()

            if len(words) > 1 and words[-1] not in ["профиль", "статистика", "пользователь", "ник", "username", "участник"]:
                potential_username = words[-1]

                if re.match(r'^[a-zA-Z0-9_-]+$', potential_username):
                    username_match = (potential_username,)
        
        if username_match:
            username = username_match[0] if isinstance(username_match, tuple) else username_match
            logger.info(f"Используем username: {username}")
            result_json = get_user_by_username(context, username)
            data = json.loads(result_json)
            
            if "error" in data:
                response = f"Ошибка: {data['error']}"
            else:
                response = format_user_response(data)
        else:
            logger.info("Запрос профиля без указания username")
            response = "Пожалуйста, укажите username пользователя. Например: 'Покажи профиль пользователя frolovdmn'"
    elif any(keyword in prompt_lower for keyword in ["задача дня", "daily", "сегодняшняя", "дневная"]):
        logger.info("Обнаружен запрос на получение задачи дня")
        result_json = get_daily_challenge(context)
        data = json.loads(result_json)

        if "error" in data:
            response = f"Ошибка: {data['error']}"
        else:
            response = format_problem_response(data)
    elif any(keyword in prompt_lower for keyword in ["случайная", "random", "любая", "какую-нибудь"]):
        logger.info("Обнаружен запрос на получение случайной задачи")
        result_json = get_random_problem(context)
        data = json.loads(result_json)

        if "error" in data:
            response = f"Ошибка: {data['error']}"
        else:
            response = "**Случайная задача:**" + format_problem_response(data)
    elif "задача" in prompt_lower or "problem" in prompt_lower:
        problem_id_match = re.search(r'\b\d+\b', prompt)

        if problem_id_match:
            problem_id = int(problem_id_match.group())
            logger.info(f"Обнаружен запрос на получение задачи по id: {problem_id}")
            result_json = get_problem_by_id(context, problem_id)
            data = json.loads(result_json)

            if "error" in data:
                response = f"Ошибка: {data['error']}"
            else:
                response = f"**Задача #{problem_id}:**" + format_problem_response(data)
        else:
            logger.info("Запрос на получение задачи без указания id")
            response = "Пожалуйста, укажите id задачи. Например: 'Получи задачу номер 1234'"
    elif any(keyword in prompt_lower for keyword in ["как решить", "решение", "объясни", "про", "почему"]):
        logger.info("Обнаружен запрос на решение или объяснение задачи")
        clean_prompt = re.sub(r'(как решить|решение|объясни|про|задача)\s*', '', prompt_lower)
        slug = re.sub(r'[\s_]+', '-', clean_prompt.strip())

        if slug:
            logger.info(f"Используем slug для поиска: {slug}")
            result_json = get_problem_by_slug(context, slug)
            data = json.loads(result_json)

            if "error" in data:
                logger.info(f"Задача по slug '{slug}' не найдена, пытаемся найти через поиск")
                search_result = search_problems(context, slug)
                search_data = json.loads(search_result)

                if "error" in search_data or not search_data.get("problems"):
                    response = f"Задача '{slug}' не найдена. Попробуйте уточнить запрос."
                else:
                    response = "**Найденные задачи:**"

                    for problem in search_data["problems"][:3]:
                        response += f"- [{problem['title']}]({BASE_URL}problems/{problem['slug']})"
            else:
                response = f"**Задача: {data['title']}**" + format_problem_response(data)
        else:
            logger.info("Запрос на решение задачи без указания названия")
            response = "Пожалуйста, укажите название задачи. Например: 'Как решить Single Number?'"
    elif any(keyword in prompt_lower for keyword in ["найди", "поиск", "search"]):
        logger.info("Обнаружен поисковый запрос")
        query = re.sub(r'(найди|поиск|search)\s*', '', prompt_lower).strip()

        if query:
            logger.info(f"Выполняем поиск по запросу: {query}")
            result_json = search_problems(context, query)
            data = json.loads(result_json)

            if "error" in data or not data.get("problems"):
                response = f"По запросу '{query}' ничего не найдено."
            else:
                response = f"**Результаты поиска по запросу '{query}':**"

                for problem in data["problems"][:5]:
                    response += f"- [{problem['title']}]({BASE_URL}problems/{problem['slug']}) | {problem['difficulty']}"
        else:
            logger.info("Пустой поисковой запрос")
            response = "Пожалуйста, укажите поисковой запрос. Например: 'Найди задачи про деревья'"
    else:
        logger.info("Не распознан тип запроса, показываем справку")
        response = (
            "Я могу помочь с задачами LeetCode. Выберите один из вариантов:"
            "- какая сегодня задачу дня"
            "- найди задачу под номером 123"
            "- как решить задачу Single Number?"
            "- случайная задача"
            "- найди задачи про динамическое программирование"
            "- выведи статистику пользователя под ником dbabichev"
        )
    
    logger.info("Запрос обработан успешно")

    return [
        {
            "role": "assistant",
            "content": response
        }
    ]

if __name__ == "__main__":
    logger.info("Запуск MCP-сервера LeetCode")
    mcp.run(transport="stdio")