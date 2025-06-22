import json
import logging
import requests

from typing import Dict, Any, List
from mcp.server.fastmcp import FastMCP, Context


logger = logging.getLogger("space_assistant")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

mcp = FastMCP(
    name="Астрономический ассистент",
    system_prompt="""
Ты — ассистент, который знает всё о текущем положении дел в космосе.
Используй инструменты, чтобы отвечать на вопросы о космонавтах и Международной космической станции (МКС).

Инструменты:
- get_astronauts: Узнать, кто сейчас находится в космосе.
- get_iss_location: Узнать текущие координаты МКС.

Примеры запросов пользователей:
- "Сколько людей сейчас в космосе?"
- "Кто сейчас на МКС?"
- "Где сейчас летит МКС?"
"""
)

@mcp.tool()
def get_astronauts(context: Context) -> str:
    """
    Возвращает список людей, находящихся в данный момент в космосе.

    Args:
        context (Context): контекст выполнения действий
    Returns:
        (str): JSON-строка с данными
    """
    api_url = "http://api.open-notify.org/astros.json"

    try:
        response = requests.get(api_url)

        if response.status_code == 200:
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
        else:
            return json.dumps({"error": f"API вернуло ошибку: {response.status_code}"})
    except requests.exceptions.RequestException as e:
        return json.dumps({"error": "Не удалось подключиться к сервису Open Notify."})

@mcp.tool()
def get_iss_location(context: Context) -> str:
    """
    Возвращает текущие географические координаты МКС.

    Args:
        context (Context): контекст выполнения действий
    Returns:
        (str): JSON-строка с данными3
    """
    api_url = "http://api.open-notify.org/iss-now.json"

    try:
        response = requests.get(api_url)

        if response.status_code == 200:
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
        else:
            return json.dumps({"error": f"API вернуло ошибку: {response.status_code}"})
    except requests.exceptions.RequestException as e:
        return json.dumps({"error": "Не удалось подключиться к сервису Open Notify."})

@mcp.prompt()
def handle_space_query(prompt: str, 
                       context: Context) -> List[Dict[str, Any]]:
    """
    Обработчик запросов о космической деятельности.
    
    Распознает и обрабатывает:
    - запросы о людях в космосе (по ключевым словам: "кто", "люди", "космонавт", "астронавт")
    - запросы о местоположении МКС (по ключевым словам: "где", "МКС", "координаты")
    
    Логика обработки:
    1. Определяет тип запроса по ключевым словам
    2. Вызывает соответствующий инструмент API
    3. Форматирует ответ в читаемом виде
    4. Для координат МКС генерирует ссылку на Google Maps
    
    Args:
        prompt (str): вопрос пользователя
        context (Context): контекст выполнения действий
        
    Returns:
        (List[Dict]): список сообщений в формате:
            [{"role": "assistant", "content": "Форматированный ответ"}]
    """
    prompt_lower = prompt.lower()
    
    if "кто" in prompt_lower or "люди" in prompt_lower or "космонавт" in prompt_lower or "астронавт" in prompt_lower:
        result_json = get_astronauts(context)
        data = json.loads(result_json)
        
        if "error" in data:
            response = f"⚠️ Произошла ошибка: {data['error']}"
        else:
            response = f"👨‍🚀 **Сейчас в космосе {data['number']} человек:**\n\n"
            crafts = {}

            for person in data['people']:
                if person['craft'] not in crafts:
                    crafts[person['craft']] = []

                crafts[person['craft']].append(person['name'])
            
            for craft, names in crafts.items():
                response += f"**Корабль '{craft}':**\n"

                for name in names:
                    response += f"- {name}\n"

                response += "\n"

    elif "где" in prompt_lower or "мкс" in prompt_lower or "координаты" in prompt_lower:
        result_json = get_iss_location(context)
        data = json.loads(result_json)
        
        if "error" in data:
            response = f"⚠️ Произошла ошибка: {data['error']}"
        else:
            lat = data['iss_position']['latitude']
            lon = data['iss_position']['longitude']
            response = (
                f"**Текущее положение МКС:**\n"
                f"- Широта: {lat}\n"
                f"- Долгота: {lon}\n\n"
                f"Вы можете посмотреть это на карте: [ссылка](https://www.google.com/maps/search/?api=1&query={lat},{lon})"
            )
    else:
        response = "Я могу рассказать, кто сейчас в космосе или где летит МКС. Что вас интересует?"

    return [
        {
            "role": "assistant",
            "content": response
        }
    ]


if __name__ == "__main__":
    mcp.run(transport="stdio")