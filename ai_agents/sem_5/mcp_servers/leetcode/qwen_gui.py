import os
import logging

from qwen_agent.gui import WebUI
from qwen_agent.agents import Assistant


logger = logging.getLogger("leetcode_assistant")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


llm_cfg = {
    'model': 'qwen3:30b-a3b-instruct-2507-q4_K_M',
    'model_server': 'http://localhost:11434/v1',
    'api_key': 'ollama',
    'enable_thinking': True,
    'generate_cfg': {
        'fncall_prompt_type': 'nous',
        'max_input_tokens': 64000,
        'repetition_penalty': 1.05,
        'temperature': 0.7,
        'top_k': 20,
        'top_p': 0.8,
        'use_raw_api': True
    }
}


USER_NAME = 'User'


def app_gui():
    if not os.path.exists('leetcode_server.py'):
        logger.error("Файл leetcode_server.py не найден в текущей директории!")
        logger.info("Текущая директория: " + os.getcwd())
        logger.info("Содержимое директории: " + str(os.listdir()))
    
    logger.info("Инициализация ассистента LeetCode")
    
    assistant = Assistant(
        llm=llm_cfg,
        system_message=(
            "Вы - агентская система для подготовки к алгоритмическим задачам LeetCode.\n"
            "Вы можете:\n"
            "- Получать задачи (задача дня, случайная задача, задача по ID или названию)\n"
            "- Выводить статистику пользователя по username\n"
            "- Объяснять задачи, рассказывать об оптимальных решениях и сложности в терминах Big O\n"
            "- Помогать с написанием кода ТОЛЬКО если вас об этом прямо просят\n\n"
            
            "ВАЖНО: не пиши решение, если тебя не попросили это сделать!! Только объясняй задачу."
            
            "Правила работы:\n"
            "- Для получения задачи используйте MCP-сервер:\n"
            "  * Для задачи дня: вызовите get_daily_challenge\n"
            "  * Для задачи по ID: вызовите get_problem_by_id\n"
            "  * Для задачи по названию: вызовите get_problem_by_slug\n"
            "  * Для случайной задачи: вызовите get_random_problem\n"
            "  * Для поиска задач: вызовите search_problems\n"
            "  * Для профиля пользователя: вызовите get_user_by_username\n\n"
            
            "- ВСЕГДА сначала предлагайте подсказки и объяснение логики решения, НЕ ПИШИТЕ код автоматически\n"
            "- Пишите код ТОЛЬКО в формате LeetCode, когда вас об этом прямо просят, используя разметку:\n"
            "```python\n"
            "  class Solution:\n"
            "      def function_name(self, параметры) -> тип_возврата:\n"
            "          # ваш код здесь\n\n"
            "```"
            "- ВСЕГДА оборачивайте полный код в разметку с указанием языка Python: ```python ... ```"
            
            "- Объясняйте временную и пространственную сложность в терминах Big O notation\n"
            "- Предлагайте альтернативные подходы к решению задачи\n"
            "- Если пользователь не уточнил, что ему нужно, уточните запрос"
        ),
        name='Stefan Pochmann',
        description='Легенда',
        function_list=[
            {
                'mcpServers': {
                    'leetcode_tools': {
                        'command': 'python',
                        'args': [
                            'leetcode_server.py'
                        ]
                    }
                }
            }
        ]
    )
    
    logger.info("Ассистент успешно инициализирован")
    
    chatbot_config = {
        'user.name': USER_NAME,
        'prompt.suggestions': [
            'Какая сегодня задача дня?',
            'Покажи задачу под номером 371',
            'Как решить задачу Meeting Rooms?',
            'Случайная задача',
            'Объясни оптимальное решение для задачи Valid Parentheses',
            'Проверь мое решение'
        ],
        'verbose': True,
        'title': 'Помощник по алгоритмическим задачам LeetCode',
        'show_prompt_suggestions': True,
        'input.placeholder': 'Введите ваш вопрос: давай разберем задачу',
        'agent.avatar': '/Users/dmitriifrolov/Python/mcp/stephan.jpeg',
        'user.avatar': '/Users/dmitriifrolov/Python/mcp/harold.jpeg'
    }
    
    logger.info("Конфигурация чат-бота готова")
    logger.info("Запуск веб-интерфейса")
    
    web_ui = WebUI(
        agent=assistant,
        chatbot_config=chatbot_config,
    )
    
    return web_ui

if __name__ == '__main__':
    logger.info("="*50)
    logger.info("Запуск системы LeetCode Assistant")
    logger.info("="*50)

    try:
        web_ui = app_gui()
        logger.info("Запуск веб-интерфейса")
        web_ui.run()
    except KeyboardInterrupt:
        logger.info("Получен сигнал завершения работы. Остановка системы")
    except Exception as e:
        logger.exception("Критическая ошибка при запуске системы")
        raise
    finally:
        logger.info("Завершение работы системы")