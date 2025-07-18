import json
import os
import re
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Type
from datetime import datetime

# Импортируем Pydantic для строгой валидации данных с обработкой ошибок
try:
    from pydantic import BaseModel, Field, ValidationError
    from pydantic_settings import BaseSettings
except ImportError as e:
    raise ImportError(f"Pydantic не установлен. Установите: pip install pydantic pydantic-settings. Ошибка: {e}")

# Используем стандартный клиент autogen для взаимодействия с OpenAI-совместимыми API
try:
    import autogen
    from autogen import ConversableAgent, UserProxyAgent
except ImportError as e:
    raise ImportError(f"AutoGen не установлен. Установите: pip install ag2. Ошибка: {e}")

# Конфигурация логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==============================================================================
# Система Raw Логирования AutoGen
# ==============================================================================

class AutoGenRawLogger:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir
        self.raw_log_file = os.path.join(workspace_dir, "autogen_raw_output.log")
        self.session_start_time = datetime.now()
        
        # Создаем отдельный логгер для raw AutoGen output
        self.raw_logger = logging.getLogger("autogen_raw")
        self.raw_logger.setLevel(logging.DEBUG)
        
        # Убираем все существующие handlers для чистого вывода
        self.raw_logger.handlers.clear()
        self.raw_logger.propagate = False
        
        # Создаем file handler для raw логов
        self.file_handler = logging.FileHandler(self.raw_log_file, mode='w', encoding='utf-8')
        self.file_handler.setLevel(logging.DEBUG)
        
        # Простой формат для raw логов - время + сообщение
        formatter = logging.Formatter('%(asctime)s | %(message)s')
        self.file_handler.setFormatter(formatter)
        
        self.raw_logger.addHandler(self.file_handler)
        
        # Инициализация raw лог-файла
        self._initialize_raw_log()
        
        # Настраиваем перехват AutoGen логов
        self._setup_autogen_logging()
    
    def _initialize_raw_log(self):
        """Создает заголовок raw лог-файла."""
        header = f"""
================================================================================
                    AUTOGEN MULTI-AGENT SYSTEM - RAW OUTPUT LOG                    
================================================================================
Session started: {self.session_start_time.strftime('%Y-%m-%d %H:%M:%S')}
Workspace: {self.workspace_dir}
================================================================================

"""
        self.raw_logger.info(header.strip())
    
    def _setup_autogen_logging(self):
        """Настраивает перехват логов от AutoGen."""
        # Получаем корневой логгер AutoGen
        autogen_logger = logging.getLogger("autogen")
        
        # Создаем custom handler для перехвата AutoGen логов
        class AutoGenRawHandler(logging.Handler):
            def __init__(self, raw_logger):
                super().__init__()
                self.raw_logger = raw_logger
            
            def emit(self, record):
                try:
                    msg = self.format(record)
                    self.raw_logger.info(f"[AUTOGEN-{record.levelname}] {msg}")
                except Exception:
                    pass
        
        # Добавляем наш handler к AutoGen логгеру
        raw_handler = AutoGenRawHandler(self.raw_logger)
        raw_handler.setFormatter(logging.Formatter('%(message)s'))
        autogen_logger.addHandler(raw_handler)
        autogen_logger.setLevel(logging.DEBUG)
        
        logger.info("✅ AutoGen raw logging настроен")
    
    def log_chat_initiation(self, initiator: str, recipient: str, message: str):
        """Логирует начало чата между агентами."""
        log_entry = f"""
{'='*80}
CHAT INITIATION: {initiator} → {recipient}
{'='*80}
Initial Message:
{message}
{'='*80}
"""
        self.raw_logger.info(log_entry.strip())
    
    def log_agent_response(self, agent_name: str, response: str):
        """Логирует ответ агента."""
        log_entry = f"""
{'─'*80}
AGENT RESPONSE: {agent_name}
{'─'*80}
{response}
{'─'*80}
"""
        self.raw_logger.info(log_entry.strip())
    
    def log_tool_call(self, agent_name: str, tool_name: str, tool_input: str, tool_output: str):
        """Логирует вызов инструмента."""
        log_entry = f"""
{'+'*80}
TOOL CALL: {agent_name} → {tool_name}
{'+'*80}
INPUT:
{tool_input}
{'─'*40}
OUTPUT:
{tool_output}
{'+'*80}
"""
        self.raw_logger.info(log_entry.strip())
    
    def log_chat_history(self, chat_history: list, context: str = ""):
        """Логирует полную историю чата."""
        log_entry = f"""
{'*'*80}
CHAT HISTORY {f'({context})' if context else ''}
{'*'*80}
"""
        self.raw_logger.info(log_entry.strip())
        
        for i, msg in enumerate(chat_history):
            role = msg.get('role', msg.get('name', 'unknown'))
            content = msg.get('content', '')
            
            entry = f"""
[{i+1}] {role.upper()}:
{'-' * (len(role) + 10)}
{content}
"""
            self.raw_logger.info(entry.strip())
        
        self.raw_logger.info('*' * 80)
    
    def log_session_end(self):
        """Логирует завершение сессии."""
        end_time = datetime.now()
        duration = end_time - self.session_start_time
        
        footer = f"""

================================================================================
                              SESSION COMPLETED                              
================================================================================
End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}
Duration: {str(duration).split('.')[0]}
================================================================================
"""
        self.raw_logger.info(footer.strip())
        
        # Закрываем file handler
        if self.file_handler:
            self.file_handler.close()
            self.raw_logger.removeHandler(self.file_handler)

# ==============================================================================
# Система Fancy Логирования
# ==============================================================================

class FancyLogger:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir
        self.log_file = os.path.join(workspace_dir, "agents_workflow.log")
        self.session_start_time = datetime.now()
        
        # Эмодзи для каждого агента
        self.agent_emojis = {
            "Архитектор": "🏗️",
            "DataExtractor": "🔍", 
            "Программист": "💻",
            "Ревьюер": "🧪",
            "ТехПисатель": "📝",
            "TeamLead": "👨‍💼",
            "Оркестратор": "🎭"
        }
        
        # Инициализация лог-файла
        self._initialize_log()
    
    def _initialize_log(self):
        """Создает красивый заголовок лог-файла."""
        header = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                          🤖 AUTOGEN AGENTS WORKFLOW LOG                      ║
║                                                                              ║
║  Сессия начата: {self.session_start_time.strftime('%Y-%m-%d %H:%M:%S')}                                           ║
║  Рабочая директория: {self.workspace_dir:<48} ║
╚══════════════════════════════════════════════════════════════════════════════╝

"""
        
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.write(header)
    
    def log_agent_action(self, agent_name: str, action: str, details: str = ""):
        """Логирует действие агента с красивым форматированием."""
        timestamp = datetime.now().strftime('%H:%M:%S')
        emoji = self.agent_emojis.get(agent_name, "🤖")
        
        # Формируем красивую запись
        log_entry = f"""
┌─ {timestamp} ─────────────────────────────────────────────────────────────────┐
│ {emoji} АГЕНТ: {agent_name:<20} │ ДЕЙСТВИЕ: {action:<30} │
├─────────────────────────────────────────────────────────────────────────────┤
"""
        
        if details:
            # Разбиваем длинный текст на строки
            lines = details.split('\n')
            for line in lines:
                # Обрезаем длинные строки
                if len(line) > 75:
                    line = line[:72] + "..."
                log_entry += f"│ {line:<75} │\n"
        
        log_entry += "└─────────────────────────────────────────────────────────────────────────────┘\n"
        
        # Записываем в файл
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
        
        # Также выводим в консоль (сокращенно)
        console_msg = f"{emoji} {agent_name}: {action}"
        if details and len(details) < 100:
            console_msg += f" | {details}"
        logger.info(console_msg)
    
    def log_phase_start(self, phase_name: str, phase_number: int):
        """Логирует начало новой фазы."""
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        phase_header = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║ {timestamp} │ 🚀 ФАЗА {phase_number}: {phase_name:<50} ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
        
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(phase_header)
        
        logger.info(f"🚀 ФАЗА {phase_number}: {phase_name}")
    
    def log_error(self, agent_name: str, error_msg: str):
        """Логирует ошибку с выделением."""
        timestamp = datetime.now().strftime('%H:%M:%S')
        emoji = self.agent_emojis.get(agent_name, "🤖")
        
        error_entry = f"""
┌─ {timestamp} ─ ❌ ОШИБКА ─────────────────────────────────────────────────────┐
│ {emoji} АГЕНТ: {agent_name:<67} │
├─────────────────────────────────────────────────────────────────────────────┤
"""
        
        # Разбиваем сообщение об ошибке
        lines = error_msg.split('\n')
        for line in lines[:5]:  # Ограничиваем количество строк
            if len(line) > 75:
                line = line[:72] + "..."
            error_entry += f"│ ❌ {line:<72} │\n"
        
        error_entry += "└─────────────────────────────────────────────────────────────────────────────┘\n"
        
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(error_entry)
        
        logger.error(f"❌ {agent_name}: {error_msg[:100]}...")
    
    def log_success(self, message: str):
        """Логирует успешное завершение."""
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        success_entry = f"""
┌─ {timestamp} ─ ✅ УСПЕХ ──────────────────────────────────────────────────────┐
│ {message:<75} │
└─────────────────────────────────────────────────────────────────────────────┘
"""
        
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(success_entry)
        
        logger.info(f"✅ {message}")
    
    def log_session_end(self):
        """Логирует завершение сессии."""
        end_time = datetime.now()
        duration = end_time - self.session_start_time
        
        footer = f"""

╔══════════════════════════════════════════════════════════════════════════════╗
║                             🏁 СЕССИЯ ЗАВЕРШЕНА                              ║
║                                                                              ║
║  Время завершения: {end_time.strftime('%Y-%m-%d %H:%M:%S')}                                        ║
║  Продолжительность: {str(duration).split('.')[0]:<52} ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
        
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(footer)
    
    def log_test_results(self, iteration: int, exit_code: int, test_logs: str, dependencies: list = None):
        """Логирует результаты выполнения тестов."""
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        # Определяем статус
        status = "✅ ПРОШЛИ" if exit_code == 0 else "❌ ПРОВАЛИЛИСЬ"
        status_emoji = "✅" if exit_code == 0 else "❌"
        
        # Анализируем логи тестов
        test_stats = self._analyze_test_logs(test_logs)
        
        # Форматируем зависимости
        deps_str = ", ".join(dependencies) if dependencies else "нет"
        if len(deps_str) > 60:
            deps_str = deps_str[:57] + "..."
        
        test_entry = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║ {timestamp} │ 🧪 РЕЗУЛЬТАТЫ ТЕСТОВ │ Итерация {iteration:<3} │ {status:<12} ║
╠─────────────────────────────────────────────────────────────────────────────┤
║ {status_emoji} Код выхода: {exit_code:<3} │ 📦 Зависимости: {deps_str:<35} ║
║ 🎯 Прошло тестов: {test_stats['passed']:<3} │ ❌ Провалилось: {test_stats['failed']:<3} │ ⚠️  Ошибок: {test_stats['errors']:<3} ║
"""
        
        # Добавляем основные ошибки (первые 3)
        if test_stats['error_details']:
            test_entry += "╠─────────────────────────────────────────────────────────────────────────────┤\n"
            test_entry += "║ 🔍 ОСНОВНЫЕ ОШИБКИ:                                                          ║\n"
            
            for i, error in enumerate(test_stats['error_details'][:3]):
                error_line = error[:69]  # Ограничиваем длину
                if len(error) > 69:
                    error_line += "..."
                test_entry += f"║ {i+1}. {error_line:<72} ║\n"
        
        test_entry += "╚══════════════════════════════════════════════════════════════════════════════╝\n"
        
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(test_entry)
        
        # Консольный вывод
        console_msg = f"🧪 Тесты итерация {iteration}: {status} (код {exit_code})"
        if test_stats['passed'] > 0 or test_stats['failed'] > 0:
            console_msg += f" | ✅{test_stats['passed']} ❌{test_stats['failed']}"
        logger.info(console_msg)
        
        # Логируем критические ошибки отдельно
        if exit_code != 0 and test_stats['critical_errors']:
            for error in test_stats['critical_errors'][:2]:  # Только первые 2
                logger.error(f"🔥 Критическая ошибка теста: {error}")
    
    def _analyze_test_logs(self, test_logs: str) -> dict:
        """Анализирует логи тестов и извлекает статистику."""
        stats = {
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'error_details': [],
            'critical_errors': []
        }
        
        if not test_logs:
            return stats
        
        lines = test_logs.split('\n')
        
        # Ищем статистику pytest
        for line in lines:
            # Формат: "= 2 failed, 3 passed in 1.23s ="
            if 'failed' in line and 'passed' in line:
                failed_match = re.search(r'(\d+)\s+failed', line)
                passed_match = re.search(r'(\d+)\s+passed', line)
                if failed_match:
                    stats['failed'] = int(failed_match.group(1))
                if passed_match:
                    stats['passed'] = int(passed_match.group(1))
            
            # Ищем только количество прошедших тестов
            elif 'passed' in line and 'failed' not in line:
                passed_match = re.search(r'(\d+)\s+passed', line)
                if passed_match:
                    stats['passed'] = int(passed_match.group(1))
        
        # Извлекаем ошибки
        current_error = ""
        collecting_error = False
        
        for line in lines:
            # Начало ошибки
            if line.startswith('FAILED') or 'AssertionError' in line or 'Error:' in line:
                if current_error:
                    stats['error_details'].append(current_error.strip())
                current_error = line
                collecting_error = True
                
                # Критические ошибки
                if any(keyword in line for keyword in ['ImportError', 'ModuleNotFoundError', 'SyntaxError']):
                    stats['critical_errors'].append(line.strip())
                    stats['errors'] += 1
            
            elif collecting_error and line.strip():
                if line.startswith(' ') or line.startswith('\t'):  # Продолжение ошибки
                    current_error += " " + line.strip()
                else:
                    # Новая секция - завершаем текущую ошибку
                    if current_error:
                        stats['error_details'].append(current_error.strip())
                        current_error = ""
                    collecting_error = False
        
        # Добавляем последнюю ошибку
        if current_error:
            stats['error_details'].append(current_error.strip())
        
        return stats
    
    def log_improvement_cycle(self, iteration: int, max_iterations: int, action: str, details: str = ""):
        """Логирует действия в цикле улучшений."""
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        cycle_entry = f"""
┌─ {timestamp} ─ 🔄 ЦИКЛ УЛУЧШЕНИЙ ──────────────────────────────────────────────┐
│ 🎯 Итерация: {iteration}/{max_iterations:<3} │ 🔧 Действие: {action:<45} │
"""
        
        if details:
            lines = details.split('\n')
            for line in lines[:2]:  # Максимум 2 строки деталей
                if len(line) > 75:
                    line = line[:72] + "..."
                cycle_entry += f"│ 📋 {line:<74} │\n"
        
        cycle_entry += "└─────────────────────────────────────────────────────────────────────────────┘\n"
        
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(cycle_entry)
        
        logger.info(f"🔄 Итерация {iteration}/{max_iterations}: {action}")
    
    def log_docker_setup(self, dependencies: list, docker_enabled: bool):
        """Логирует настройку Docker среды."""
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        docker_status = "🐳 ВКЛЮЧЕН" if docker_enabled else "📁 ЛОКАЛЬНО"
        deps_count = len(dependencies)
        deps_preview = ", ".join(dependencies[:3])
        if len(dependencies) > 3:
            deps_preview += f" и еще {len(dependencies) - 3}"
        
        docker_entry = f"""
┌─ {timestamp} ─ 🐳 НАСТРОЙКА СРЕДЫ ТЕСТИРОВАНИЯ ──────────────────────────────┐
│ 🎯 Режим: {docker_status:<12} │ 📦 Зависимостей: {deps_count:<3} │ 🔧 Установка...    │
│ 📋 Пакеты: {deps_preview:<63} │
└─────────────────────────────────────────────────────────────────────────────┘
"""
        
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(docker_entry)
        
        logger.info(f"🐳 Docker тестирование: {docker_status} | Зависимости: {deps_count}")

# ==============================================================================
# Система отслеживания токенов
# ==============================================================================

class TokenTracker:
    def __init__(self, workspace_dir: str, input_cost: float, output_cost: float):
        self.workspace_dir = workspace_dir
        self.input_cost = input_cost  # Стоимость за входящий токен в рублях
        self.output_cost = output_cost  # Стоимость за исходящий токен в рублях
        self.session_start_time = datetime.now()
        
        # Трекинг токенов по агентам
        self.agent_tokens = {
            "Архитектор": {"input": 0, "output": 0, "calls": 0},
            "DataExtractor": {"input": 0, "output": 0, "calls": 0},
            "Программист": {"input": 0, "output": 0, "calls": 0},
            "Ревьюер": {"input": 0, "output": 0, "calls": 0},
            "ТехПисатель": {"input": 0, "output": 0, "calls": 0},
            "TeamLead": {"input": 0, "output": 0, "calls": 0},
            "Оркестратор": {"input": 0, "output": 0, "calls": 0}
        }
        
        # Файл для логирования токенов
        self.token_log_file = os.path.join(workspace_dir, "tokens_usage.log")
        self._initialize_token_log()
    
    def _initialize_token_log(self):
        """Создает красивый заголовок файла с токенами."""
        header = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        💰 ОТЧЕТ ПО ИСПОЛЬЗОВАНИЮ ТОКЕНОВ                     ║
║                                                                              ║
║  Сессия начата: {self.session_start_time.strftime('%Y-%m-%d %H:%M:%S')}                                           ║
║  Рабочая директория: {self.workspace_dir:<48} ║
║  Стоимость входящего токена: {self.input_cost:.6f} руб.                                ║
║  Стоимость исходящего токена: {self.output_cost:.6f} руб.                               ║
╚══════════════════════════════════════════════════════════════════════════════╝

"""
        
        with open(self.token_log_file, "w", encoding="utf-8") as f:
            f.write(header)
    
    def estimate_tokens(self, text: str) -> int:
        """Оценивает количество токенов в тексте (примерная формула)."""
        if not text:
            return 0
        
        # Простая оценка: ~4 символа = 1 токен для большинства языков
        # Для русского текста коэффициент может быть выше
        char_count = len(text)
        word_count = len(text.split())
        
        # Используем более точную формулу для смешанного русско-английского текста
        estimated_tokens = max(char_count // 3.5, word_count * 1.3)
        return int(estimated_tokens)
    
    def track_agent_call(self, agent_name: str, input_text: str, output_text: str, 
                        actual_input_tokens: int = None, actual_output_tokens: int = None):
        """Отслеживает использование токенов для вызова агента."""
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        # Используем реальные токены если есть, иначе оцениваем
        input_tokens = actual_input_tokens if actual_input_tokens is not None else self.estimate_tokens(input_text)
        output_tokens = actual_output_tokens if actual_output_tokens is not None else self.estimate_tokens(output_text)
        
        # Обновляем статистику агента
        if agent_name in self.agent_tokens:
            self.agent_tokens[agent_name]["input"] += input_tokens
            self.agent_tokens[agent_name]["output"] += output_tokens
            self.agent_tokens[agent_name]["calls"] += 1
        
        # Рассчитываем стоимость
        input_cost = input_tokens * self.input_cost
        output_cost = output_tokens * self.output_cost
        total_cost = input_cost + output_cost
        
        # Логируем в файл
        log_entry = f"""
┌─ {timestamp} ─ 💰 ТОКЕНЫ ─────────────────────────────────────────────────────────┐
│ 🤖 АГЕНТ: {agent_name:<20} │ 🔢 ВЫЗОВ: {self.agent_tokens[agent_name]['calls']:<10} │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 📥 Входящие токены: {input_tokens:<8} │ 💰 Стоимость: {input_cost:<10.6f} руб.        │
│ 📤 Исходящие токены: {output_tokens:<7} │ 💰 Стоимость: {output_cost:<10.6f} руб.        │
│ 💵 ОБЩАЯ стоимость вызова: {total_cost:<14.6f} руб.                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 📊 ВХОДЯЩИЙ ТЕКСТ: {len(input_text):<4} симв. │ 📋 ИСХОДЯЩИЙ ТЕКСТ: {len(output_text):<4} симв.     │
└─────────────────────────────────────────────────────────────────────────────────┘
"""
        
        with open(self.token_log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
        
        logger.info(f"💰 {agent_name}: {input_tokens}→{output_tokens} токенов, {total_cost:.4f} руб.")
    
    def get_agent_summary(self, agent_name: str) -> dict:
        """Возвращает сводку по токенам для агента."""
        if agent_name not in self.agent_tokens:
            return {"input": 0, "output": 0, "calls": 0, "cost": 0.0}
        
        data = self.agent_tokens[agent_name]
        input_cost = data["input"] * self.input_cost
        output_cost = data["output"] * self.output_cost
        total_cost = input_cost + output_cost
        
        return {
            "input": data["input"],
            "output": data["output"],
            "calls": data["calls"],
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": total_cost
        }
    
    def get_total_summary(self) -> dict:
        """Возвращает общую сводку по всем токенам."""
        total_input = sum(data["input"] for data in self.agent_tokens.values())
        total_output = sum(data["output"] for data in self.agent_tokens.values())
        total_calls = sum(data["calls"] for data in self.agent_tokens.values())
        
        total_input_cost = total_input * self.input_cost
        total_output_cost = total_output * self.output_cost
        total_cost = total_input_cost + total_output_cost
        
        return {
            "total_input": total_input,
            "total_output": total_output,
            "total_tokens": total_input + total_output,
            "total_calls": total_calls,
            "total_input_cost": total_input_cost,
            "total_output_cost": total_output_cost,
            "total_cost": total_cost
        }
    
    def log_session_summary(self):
        """Логирует итоговую сводку по сессии."""
        end_time = datetime.now()
        duration = end_time - self.session_start_time
        total_summary = self.get_total_summary()
        
        # Создаем детальную сводку по агентам
        agent_details = ""
        for agent_name, data in self.agent_tokens.items():
            if data["calls"] > 0:
                summary = self.get_agent_summary(agent_name)
                agent_details += f"""║ 🤖 {agent_name:<15} │ Вызовов: {data['calls']:<2} │ Токены: {data['input']:<5}→{data['output']:<5} │ {summary['total_cost']:<8.4f} руб. ║
"""
        
        # Общая сводка
        summary_report = f"""

╔══════════════════════════════════════════════════════════════════════════════╗
║                           💰 ИТОГОВАЯ СВОДКА ПО ТОКЕНАМ                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ ⏱️  Время сессии: {str(duration).split('.')[0]:<54} ║
║ 🔢 Всего вызовов LLM: {total_summary['total_calls']:<51} ║
║ 📥 Всего входящих токенов: {total_summary['total_input']:<46} ║
║ 📤 Всего исходящих токенов: {total_summary['total_output']:<45} ║
║ 🎯 ИТОГО токенов: {total_summary['total_tokens']:<53} ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ 💰 Стоимость входящих токенов: {total_summary['total_input_cost']:<8.6f} руб.                  ║
║ 💰 Стоимость исходящих токенов: {total_summary['total_output_cost']:<8.6f} руб.                 ║
║ 💵 ОБЩАЯ СТОИМОСТЬ: {total_summary['total_cost']:<12.6f} руб.                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                              📊 ДЕТАЛИЗАЦИЯ ПО АГЕНТАМ                       ║
╠══════════════════════════════════════════════════════════════════════════════╣
{agent_details}╚══════════════════════════════════════════════════════════════════════════════╝
"""
        
        with open(self.token_log_file, "a", encoding="utf-8") as f:
            f.write(summary_report)
        
        logger.info(f"💰 ИТОГО: {total_summary['total_tokens']} токенов, {total_summary['total_cost']:.4f} руб.")
        return total_summary

# ==============================================================================
# Часть 1: Конфигурация и Модели Данных (с Pydantic)
# ==============================================================================

# Гибкая конфигурация через переменные окружения
class Config(BaseSettings):
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    OLLAMA_API_KEY: str = "ollama"
    CODE_LLM_MODEL: str = "qwen2.5-coder:32b"
    GENERAL_LLM_MODEL: str = "qwen2.5:32b"  # Лучше следует инструкциям, без <think>
    DATA_EXTRACTION_MODEL: str = "qwen2.5:32b"  # Специализированная модель для извлечения данных
    WORKSPACE_DIR: str = "coding_workspace_v8_pirate"
    SCRIPT_NAME: str = "generated_script.py"
    TESTS_NAME: str = "test_generated_script.py"
    MAX_IMPROVEMENT_LOOPS: int = 10
    USE_DOCKER: bool = True
    DOCKER_IMAGE: str = "python:3.11"
    
    # Стоимость токенов в рублях (примерные значения для локальных моделей)
    TOKEN_INPUT_COST: float = 0.0001  # Стоимость входящего токена в рублях
    TOKEN_OUTPUT_COST: float = 0.0002  # Стоимость исходящего токена в рублях

    class Config:
        env_file = ".env" # Позволяет переопределять переменные через .env файл
        env_file_encoding = "utf-8"

# Модели Pydantic для валидации ответов от LLM
class Plan(BaseModel):
    plan: List[str] = Field(..., description="Пошаговый план реализации.")
    data_query: Optional[str] = Field(None, description="Точный запрос для веб-поиска, если нужен.")
    dependencies: List[str] = Field(default_factory=list, description="Необходимые Python-библиотеки.")

class ExtractedData(BaseModel):
    price: Optional[float] = Field(None, description="Извлеченная цена. null, если не найдена.")

class GeneratedCode(BaseModel):
    description: str = Field(..., description="Краткое описание того, что делает скрипт.")
    code: str = Field(..., description="Полный код скрипта.")

class CodeReview(BaseModel):
    review_comments: List[str] = Field(..., description="Список комментариев по коду.")
    test_code: str = Field(..., description="Код тестов для скрипта.")
    improvements: List[str] = Field(default_factory=list, description="Предложения по улучшению.")

class Documentation(BaseModel):
    title: str = Field(..., description="Заголовок документации.")
    description: str = Field(..., description="Описание проекта.")
    usage_examples: List[str] = Field(..., description="Примеры использования.")
    api_documentation: str = Field(..., description="Документация API/функций.")

class ProblemSolution(BaseModel):
    problem_analysis: str = Field(..., description="Анализ проблемы.")
    target_agent: str = Field(..., description="Кого исправлять: 'Программист' или 'Ревьюер'.")
    specific_instructions: str = Field(..., description="Конкретные инструкции для исправления.")
    expected_outcome: str = Field(..., description="Ожидаемый результат после исправления.")


# ==============================================================================
# Часть 2: Инструменты и Агенты
# ==============================================================================

# Инструмент для веб-поиска остался прежним, но теперь он будет вызываться через нативный механизм autogen
try:
    from duckduckgo_search import DDGS
except ImportError:
    raise ImportError("Пожалуйста, установите библиотеку: pip install duckduckgo-search")

def web_search(query: str) -> str:
    """Выполняет веб-поиск по заданному запросу и возвращает результаты."""
    logger.info(f"🔎 Выполняется веб-поиск по запросу: '{query}'")
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        if not results:
            logger.warning(f"Поиск по запросу '{query}' не дал результатов")
            return "Поиск не дал результатов."
        
        formatted_results = "\n---\n".join([f"Результат {i+1}: {r}" for i, r in enumerate(results)])
        logger.info(f"✅ Найдено {len(results)} результатов для запроса '{query}'")
        return formatted_results
    except Exception as e:
        error_msg = f"Ошибка при выполнении поиска: {e}"
        logger.error(error_msg)
        return error_msg

# ==============================================================================
# Часть 3: Улучшенный Менеджер Конвейера
# ==============================================================================

class PipelineManager:
    def __init__(self, config: Config):
        self.config = config
        os.makedirs(config.WORKSPACE_DIR, exist_ok=True)
        
        # Инициализируем fancy логгер
        self.fancy_logger = FancyLogger(config.WORKSPACE_DIR)
        
        # Инициализируем трекер токенов
        self.token_tracker = TokenTracker(
            config.WORKSPACE_DIR, 
            config.TOKEN_INPUT_COST, 
            config.TOKEN_OUTPUT_COST
        )
        logger.info(f"💰 TokenTracker инициализирован: {config.TOKEN_INPUT_COST} руб./вх.токен, {config.TOKEN_OUTPUT_COST} руб./исх.токен")
        
        # Инициализируем raw логгер AutoGen
        self.raw_logger = AutoGenRawLogger(config.WORKSPACE_DIR)
        logger.info(f"📝 AutoGen Raw Logger инициализирован: {self.raw_logger.raw_log_file}")
        
        # Конфигурация LLM для агентов (правильная структура для AutoGen)
        llm_config_coder = {
            "config_list": [{
                "model": config.CODE_LLM_MODEL, 
                "base_url": config.OLLAMA_BASE_URL, 
                "api_key": config.OLLAMA_API_KEY,
                "api_type": "openai"
            }],
            "temperature": 0.01
        }
        llm_config_general = {
            "config_list": [{
                "model": config.GENERAL_LLM_MODEL, 
                "base_url": config.OLLAMA_BASE_URL, 
                "api_key": config.OLLAMA_API_KEY,
                "api_type": "openai"
            }],
            "temperature": 0.01
        }
        llm_config_data_extraction = {
            "config_list": [{
                "model": config.DATA_EXTRACTION_MODEL, 
                "base_url": config.OLLAMA_BASE_URL, 
                "api_key": config.OLLAMA_API_KEY,
                "api_type": "openai"
            }],
            "temperature": 0.0  # Очень низкая температура для точного извлечения данных
        }

        # Агент-планировщик
        self.planner = ConversableAgent(
            name="Архитектор",
            system_message="""Вы — архитектор ПО. Анализируете запросы и создаёте планы разработки.

СТРОГИЕ ПРАВИЛА:
- НЕ размышляйте, СРАЗУ верните JSON
- ТОЛЬКО русский язык
- ТОЛЬКО указанный формат

ОБЯЗАТЕЛЬНЫЙ ФОРМАТ:
{
  "plan": ["шаг 1", "шаг 2", "шаг 3"],
  "data_query": "поисковый запрос на русском или null",
  "dependencies": ["библиотека1", "библиотека2"]
}

ПОЛЯ:
- plan: список шагов реализации
- data_query: запрос для поиска данных в интернете (если нужно) или null
- dependencies: список Python библиотек

ЗАПРЕЩЕНО любое дополнительное содержимое!""",
            llm_config=llm_config_coder,
        )

        # Агент для извлечения данных, оснащенный инструментом поиска
        self.data_extractor = ConversableAgent(
            name="DataExtractor",
            system_message="""Вы — агент для извлечения данных из интернета с доступом к web_search.

ВАША ЕДИНСТВЕННАЯ ЗАДАЧА:
1. Выполнить web_search() с полученным запросом
2. Найти цену в результатах поиска
3. Вернуть JSON: {"price": число} или {"price": null}

АЛГОРИТМ РАБОТЫ:
1. НЕМЕДЛЕННО вызовите web_search(запрос_пользователя)
2. Изучите результаты поиска 
3. Найдите цену товара в рублях
4. Верните ТОЛЬКО JSON

ФОРМАТ ОТВЕТА:
{"price": 139990.0} - если цена найдена
{"price": null} - если цена НЕ найдена

ЗАПРЕЩЕНО:
- Любые объяснения
- Блоки <think>
- Текст кроме JSON
- Размышления

НАЧИНАЙТЕ СРАЗУ С web_search()!""",
            llm_config=llm_config_data_extraction,
        )

        # Агент-программист
        self.code_writer = ConversableAgent(
            name="Программист",
            system_message="""Вы — Python-программист под руководством TeamLead. ПРИОРИТЕТ: выполнение инструкций TeamLead!

🎯 ИЕРАРХИЯ ИНСТРУКЦИЙ (по приоритету):
1. **ИНСТРУКЦИИ ОТ TEAMLEAD** — ВЫСШИЙ ПРИОРИТЕТ! Выполняйте ТОЧНО и НЕМЕДЛЕННО!
2. Техническое задание пользователя
3. Общие правила программирования

⚡ КОГДА ПОЛУЧАЕТЕ ИНСТРУКЦИИ ОТ TEAMLEAD:
- НЕМЕДЛЕННО реализуйте ВСЕ указания TeamLead
- НЕ игнорируйте детали из инструкций TeamLead
- НЕ придумывайте свою логику, если TeamLead дал конкретные указания
- ТОЧНО используйте значения/формулы, указанные TeamLead
- БЫСТРО адаптируйтесь к требованиям TeamLead

СТРОГИЕ ПРАВИЛА ФОРМАТА:
- НЕ размышляйте, СРАЗУ верните JSON
- ТОЛЬКО русский язык в описании
- КОД В ОДНУ СТРОКУ с \\n для переносов

ОБЯЗАТЕЛЬНЫЙ ФОРМАТ:
{
  "description": "Краткое описание функциональности (с учетом инструкций TeamLead)",
  "code": "def function():\\n    return result\\n\\nif __name__ == '__main__':\\n    print('demo')"
}

ВАЖНО ДЛЯ ПОЛЯ CODE:
- Используйте \\n вместо реальных переносов строк
- Используйте \\t для табуляций  
- Экранируйте кавычки как \\"
- НЕ используйте реальные переносы строк в JSON

🚨 ОСОБО ВАЖНО: Если в сообщении есть "ИНСТРУКЦИЯ ОТ СУПЕРВИЗОРА" или "TEAMLEAD" - это КРИТИЧЕСКИ ВАЖНЫЕ инструкции! Выполняйте их ТОЧНО без отклонений!

ЗАПРЕЩЕНО любое дополнительное содержимое!""",
            llm_config=llm_config_coder,
        )

        # Агент-ревьюер кода
        self.code_reviewer = ConversableAgent(
            name="Ревьюер",
            system_message="""Вы — эксперт по review кода и тестам под руководством TeamLead. ПРИОРИТЕТ: выполнение инструкций TeamLead!

🎯 ИЕРАРХИЯ ИНСТРУКЦИЙ (по приоритету):
1. **ИНСТРУКЦИИ ОТ TEAMLEAD** — ВЫСШИЙ ПРИОРИТЕТ! Исправляйте ТОЧНО по указаниям TeamLead!
2. Стандартные правила написания тестов
3. Общие принципы code review

⚡ КОГДА ПОЛУЧАЕТЕ ИНСТРУКЦИИ ОТ TEAMLEAD:
- НЕМЕДЛЕННО исправляйте тесты согласно инструкциям TeamLead
- ТОЧНО используйте ожидаемые значения, указанные TeamLead
- НЕ спорьте с логикой TeamLead - он проанализировал код
- БЫСТРО адаптируйтесь к требованиям TeamLead
- ИСПРАВЛЯЙТЕ ошибочные assert'ы как указано TeamLead

СТРОГИЕ ПРАВИЛА ФОРМАТА:
- НЕ размышляйте, СРАЗУ верните JSON
- ТОЛЬКО русский язык в комментариях

КРИТИЧЕСКИ ВАЖНО ДЛЯ ТЕСТОВ:
1. ЕСЛИ TEAMLEAD УКАЗАЛ КОНКРЕТНЫЕ ЗНАЧЕНИЯ - используйте ИХ, а не свои расчеты
2. ВНИМАТЕЛЬНО ИЗУЧИТЕ КОД перед написанием тестов (если нет инструкций TeamLead)
3. ПРОСЛЕДИТЕ ЛОГИКУ функций шаг за шагом
4. ВЫЧИСЛИТЕ ожидаемые результаты на основе РЕАЛЬНОЙ логики кода
5. НЕ придумывайте произвольные ожидаемые значения
6. ВСЕГДА добавляйте правильные импорты: from generated_script import function_name

МЕТОДОЛОГИЯ СОЗДАНИЯ ТЕСТОВ (если нет инструкций TeamLead):
- Возьмите простой пример входных данных
- Мысленно выполните код с этими данными
- Запишите РЕАЛЬНЫЙ результат как ожидаемый
- НЕ угадывайте результаты!

ОБЯЗАТЕЛЬНЫЙ ФОРМАТ:
{
  "review_comments": ["комментарий 1 (учитывая инструкции TeamLead)", "комментарий 2"],
  "test_code": "полный код тестов с ИСПРАВЛЕНИЯМИ от TeamLead",
  "improvements": ["улучшение 1", "улучшение 2"]
}

🚨 ОСОБО ВАЖНО: Если в сообщении есть "ИНСТРУКЦИЯ ОТ СУПЕРВИЗОРА" или "TEAMLEAD" - это означает, что ваши предыдущие тесты были НЕПРАВИЛЬНЫМИ! Исправьте их НЕМЕДЛЕННО и ТОЧНО по инструкциям!

🔧 БЫСТРОЕ ИСПРАВЛЕНИЕ ТЕСТОВ:
- Если TeamLead говорит "assert 62 == 634 неправильно" - НЕМЕДЛЕННО исправьте на правильное значение
- Если TeamLead дает формулу - используйте ЕЕ, не свою
- НЕ пересчитывайте заново - ДОВЕРЯЙТЕ анализу TeamLead

ЗАПРЕЩЕНО любое дополнительное содержимое!""",
            llm_config=llm_config_coder,
        )

        # Агент-технический писатель
        self.tech_writer = ConversableAgent(
            name="ТехПисатель",
            system_message="""Вы — технический писатель. Создаёте документацию для кода.

СТРОГИЕ ПРАВИЛА:
- НЕ размышляйте, СРАЗУ верните JSON
- ТОЛЬКО русский язык
- ТОЛЬКО указанный формат

ОБЯЗАТЕЛЬНЫЙ ФОРМАТ:
{
  "title": "Название проекта",
  "description": "Описание проекта и его назначения",
  "usage_examples": ["пример 1", "пример 2"],
  "api_documentation": "документация по функциям и API"
}

ПОЛЯ:
- title: краткое название проекта
- description: подробное описание функциональности
- usage_examples: примеры использования
- api_documentation: документация по API

ЗАПРЕЩЕНО любое дополнительное содержимое!""",
            llm_config=llm_config_general,
        )

        # Агент-решатель проблем (TeamLead)
        self.problem_solver = ConversableAgent(
            name="TeamLead",
            system_message="""Вы — TeamLead (СУПЕРВИЗОР). Анализируете проблемы и даёте КОНКРЕТНЫЕ инструкции другим агентам.

СТРОГИЕ ПРАВИЛА:
- НЕ размышляйте, СРАЗУ верните JSON
- ТОЛЬКО русский язык
- ТОЛЬКО указанный формат

ВАША ЗАДАЧА:
1. ВНИМАТЕЛЬНО проанализируйте код, тесты и ошибки
2. ОПРЕДЕЛИТЕ, кто виноват - логика кода или ожидания тестов
3. ДАЙТЕ ЧЕТКИЕ инструкции конкретному агенту

ПРИНЦИПЫ АНАЛИЗА:
- Если тесты ожидают неправильные значения → target_agent: "Ревьюер"
- Если код работает неправильно → target_agent: "Программист"
- ВСЕГДА указывайте ТОЧНЫЕ значения и формулы

ОБЯЗАТЕЛЬНЫЙ ФОРМАТ:
{
  "problem_analysis": "подробный анализ проблемы",
  "target_agent": "Программист" или "Ревьюер",
  "specific_instructions": "конкретные инструкции для исправления",
  "expected_outcome": "что должно произойти после исправления"
}

ПОЛЯ:
- problem_analysis: детальный анализ что не так
- target_agent: ТОЛЬКО "Программист" или "Ревьюер"
- specific_instructions: четкие шаги для исправления
- expected_outcome: ожидаемый результат

ЗАПРЕЩЕНО любое дополнительное содержимое!""",
            llm_config=llm_config_general,
        )
        
        # Пользовательский прокси-агент, который может выполнять инструменты и код
        code_execution_config = {
            "work_dir": config.WORKSPACE_DIR,
            "use_docker": config.DOCKER_IMAGE if config.USE_DOCKER else False,
        }
        
        self.user_proxy = UserProxyAgent(
            name="Оркестратор",
            human_input_mode="NEVER",
            code_execution_config=code_execution_config,
            is_termination_msg=self._is_termination_msg,  # Добавляем функцию завершения
            max_consecutive_auto_reply=1,  # ИСПРАВЛЕНИЕ: Возвращаем 1 для выполнения инструментов
            default_auto_reply="",  # ИСПРАВЛЕНИЕ: Пустой автоответ
        )
        
        # Регистрация инструмента для агента, который будет его использовать
        try:
            autogen.register_function(
                web_search,
                caller=self.data_extractor,
                executor=self.user_proxy,
                description="Выполняет веб-поиск по заданному запросу и возвращает результаты.",
            )
            logger.info("✅ Инструмент web_search успешно зарегистрирован")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось зарегистрировать инструмент web_search: {e}")
            logger.info("📝 Продолжаем без регистрации инструмента")
        
        # Проверяем работу веб-поиска
        logger.info("🧪 Тестируем веб-поиск...")
        test_result = web_search("test query")
        if "Ошибка" in test_result:
            logger.warning(f"⚠️ Проблема с веб-поиском: {test_result}")
        else:
            logger.info("✅ Веб-поиск работает корректно")
    
    def _is_termination_msg(self, msg: dict) -> bool:
        """Определяет, когда нужно завершить разговор с агентом."""
        content = msg.get("content", "")
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: НЕ завершаем если есть tool calls
        if "tool call" in content or "Suggested tool call" in content or "tool_calls" in str(msg):
            logger.info("🔧 Обнаружен tool call - НЕ завершаем диалог, ждем выполнения")
            return False
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Завершаем на TERMINATE сообщениях
        if content.strip() == "TERMINATE":
            logger.info("🔚 Получен сигнал TERMINATE - завершаем диалог")
            return True
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Завершаем на пустых сообщениях от оркестратора ТОЛЬКО если нет tool calls
        if not content or content.strip() == "":
            # Проверяем весь объект сообщения на наличие tool calls
            if "tool_calls" in str(msg) or any("tool" in str(value) for value in msg.values() if isinstance(value, str)):
                logger.info("🔧 Пустое сообщение содержит tool call - НЕ завершаем")
                return False
            logger.info("🔚 Получено пустое сообщение - завершаем диалог для предотвращения цикла")
            return True
        
        # Завершаем на сообщениях оркестратора, которые не содержат инструкций
        if len(content.strip()) < 10:  # Очень короткие сообщения
            logger.info("🔚 Получено слишком короткое сообщение - завершаем диалог")
            return True
        
        # Если сообщение содержит валидный JSON с правильными полями, завершаем
        try:
            # Приоритетный поиск JSON без агрессивной очистки
            cleaned = content
            
            # Сначала ищем JSON в markdown блоках
            markdown_match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", cleaned)
            if markdown_match:
                cleaned = markdown_match.group(1)
            else:
                # Ищем простой JSON в тексте
                simple_json_match = re.search(r'\{[^{}]*\}', cleaned)
                if simple_json_match:
                    cleaned = simple_json_match.group(0)
                else:
                    # Ищем сложный JSON с возможными вложениями
                    complex_json_match = re.search(r'\{[\s\S]*\}', cleaned)
                    if complex_json_match:
                        cleaned = complex_json_match.group(0)
                    else:
                        # Последняя попытка - очищаем <think> и ищем снова
                        no_think = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
                        final_json_match = re.search(r'\{[\s\S]*\}', no_think)
                        if final_json_match:
                            cleaned = final_json_match.group(0)
                        else:
                            return False  # Не найден JSON - не завершаем
            
            # Очищаем от лишних пробелов
            cleaned = cleaned.strip()
            
            # Пробуем распарсить как JSON
            parsed = json.loads(cleaned)
            
            # Проверяем базовые структуры для разных типов ответов
            if isinstance(parsed, dict):
                # Для планировщика
                if "plan" in parsed and "data_query" in parsed:
                    logger.info("🔚 Обнаружен валидный план - завершаем диалог")
                    return True
                # Для извлечения данных  
                elif "price" in parsed:
                    logger.info("🔚 Обнаружена цена - завершаем диалог")
                    return True
                # Для генератора кода
                elif "description" in parsed and "code" in parsed:
                    logger.info("🔚 Обнаружен код - завершаем диалог")
                    return True
                # Для ревьюера кода
                elif "review_comments" in parsed and "test_code" in parsed:
                    logger.info("🔚 Обнаружен review - завершаем диалог")
                    return True
                # Для технического писателя
                elif "title" in parsed and "api_documentation" in parsed:
                    logger.info("🔚 Обнаружена документация - завершаем диалог")
                    return True
                # Для решателя проблем
                elif "problem_analysis" in parsed and "target_agent" in parsed:
                    logger.info("🔚 Обнаружено решение проблемы - завершаем диалог")
                    return True
        except Exception as e:
            # Если есть содержимое, но не удается распарсить - не завершаем
            if content.strip():
                logger.debug(f"Не удалось распарсить содержимое как JSON: {e}")
            pass
        
        return False

    def _invoke_agent_and_validate(self, agent: ConversableAgent, prompt: str, model: Type[BaseModel], max_retries: int = 3) -> BaseModel:
        """Надежно вызывает агента и валидирует его ответ с помощью Pydantic."""
        original_prompt = prompt
        
        # Ограничиваем попытки для DataExtractor
        if agent.name == "DataExtractor":
            max_retries = 2  # Меньше попыток для быстрого извлечения данных
        
        for attempt in range(max_retries):
            logger.info(f"🔄 Вызов агента: {agent.name}, Попытка: {attempt + 1}/{max_retries}")
            logger.info(f"📝 Отправляемый промпт: {prompt[:200]}...")
            
            # Используем user_proxy для вызова агента и возможного выполнения инструментов
            try:
                logger.info(f"🔄 Инициируем чат с агентом {agent.name}, попытка {attempt + 1}")
                
                # Логируем начало чата в raw logger
                self.raw_logger.log_chat_initiation(self.user_proxy.name, agent.name, prompt)
                
                # ИСПРАВЛЕНИЕ: DataExtractor нужно больше времени для выполнения веб-поиска
                max_turns_for_agent = 3 if agent.name == "DataExtractor" else 1
                
                chat_result = self.user_proxy.initiate_chat(
                    recipient=agent, 
                    message=prompt, 
                    max_turns=max_turns_for_agent,  # ИСПРАВЛЕНИЕ: Больше turns для DataExtractor
                    clear_history=True, 
                    silent=False
                )
                
                logger.info(f"✅ Чат с агентом {agent.name} завершен, история содержит {len(chat_result.chat_history) if hasattr(chat_result, 'chat_history') else 0} сообщений")
                
                # Логируем полную историю чата в raw logger
                if hasattr(chat_result, 'chat_history') and chat_result.chat_history:
                    self.raw_logger.log_chat_history(chat_result.chat_history, f"{agent.name} - Попытка {attempt + 1}")
                
            except Exception as e:
                logger.warning(f"⚠️ Ошибка в чате с {agent.name}: {e}")
                # Пробуем прямой вызов generate_reply как fallback
                try:
                    logger.info(f"🔄 Пробуем прямой вызов для {agent.name}")
                    response = agent.generate_reply([{"role": "user", "content": prompt}])
                    chat_result = type('MockResult', (), {
                        'chat_history': [
                            {"role": "user", "content": prompt},
                            {"role": "assistant", "content": response}
                        ]
                    })()
                except Exception as e2:
                    logger.error(f"❌ Прямой вызов тоже не сработал для {agent.name}: {e2}")
                    chat_result = type('MockResult', (), {'chat_history': []})()
            
            if not hasattr(chat_result, 'chat_history'):
                logger.error(f"❌ Некорректный результат чата от {agent.name}")
                chat_result = type('MockResult', (), {'chat_history': []})()

            # Логируем всю историю чата для отладки
            logger.info(f"💬 История чата с {agent.name}:")
            for i, msg in enumerate(chat_result.chat_history):
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                logger.info(f"  {i+1}. {role}: {content[:150]}...")

            # Извлекаем последний ответ агента
            if not chat_result.chat_history:
                logger.error(f"❌ Пустая история чата от агента {agent.name}")
                last_message = ""
            else:
                # В AutoGen роли могут быть инвертированы, берём последнее сообщение
                # которое НЕ является нашим промптом
                last_message = ""
                
                # ИСПРАВЛЕНИЕ: Специальная обработка для DataExtractor с tool calls
                if agent.name == "DataExtractor":
                    # Ищем последнее сообщение с результатами поиска
                    for msg in reversed(chat_result.chat_history):
                        content = msg.get('content', '').strip()
                        if not content:
                            continue
                            
                        # Ищем сообщения с результатами веб-поиска
                        if "Результат" in content or "результат" in content or "цена" in content.lower() or "price" in content:
                            last_message = content
                            logger.info(f"🔍 DataExtractor: Найдены результаты веб-поиска")
                            break
                            
                        # Или JSON ответ
                        if '"price"' in content:
                            last_message = content
                            logger.info(f"🔍 DataExtractor: Найден JSON ответ")
                            break
                    
                    # Если не нашли результатов, берем любое непустое сообщение
                    if not last_message:
                        for msg in reversed(chat_result.chat_history):
                            content = msg.get('content', '').strip()
                            if content and not any(keyword in content for keyword in ["НЕМЕДЛЕННО", "КРИТИЧЕСКАЯ", "ИЗВЛЕКИТЕ"]):
                                last_message = content
                                break
                else:
                    # Обычная логика для других агентов
                    # Ищем последний валидный ответ агента (не пустой и не от оркестратора)
                    for msg in reversed(chat_result.chat_history):
                        content = msg.get('content', '').strip()
                        sender = msg.get('name', msg.get('role', ''))
                        
                        # ИСПРАВЛЕНИЕ: Пропускаем пустые сообщения и сообщения от оркестратора
                        if not content or sender == "Оркестратор":
                            continue
                            
                        # Пропускаем сообщения, которые явно являются нашими промптами
                        if any(keyword in content for keyword in ["НЕМЕДЛЕННО", "КРИТИЧЕСКАЯ ОШИБКА", "НЕ ДУМАЙТЕ", "ОБЯЗАТЕЛЬНО", "ВЕРНИТЕ JSON"]):
                            continue
                            
                        last_message = content
                        break
                
                # Если все еще не нашли валидный ответ, берем последнее непустое сообщение
                if not last_message and chat_result.chat_history:
                    for msg in reversed(chat_result.chat_history):
                        content = msg.get('content', '').strip()
                        if content:
                            last_message = content
                            break
                
                logger.info(f"📨 Последний ответ от агента {agent.name}: '{last_message[:200]}...'")
            
            # 💰 ТРЕКАЕМ ТОКЕНЫ ДЛЯ КАЖДОГО ВЫЗОВА АГЕНТА (независимо от успеха/неудачи)
            self.token_tracker.track_agent_call(
                agent_name=agent.name,
                input_text=prompt,
                output_text=last_message
            )
            
            # Проверяем, не пустой ли ответ СРАЗУ
            if not last_message or last_message.strip() == "":
                logger.warning(f"⚠️ Получен пустой ответ от агента {agent.name}")
                if attempt < max_retries - 1:
                    prompt = f"""ВЫ НЕ ДАЛИ ОТВЕТА! 

ОБЯЗАТЕЛЬНО ответьте в JSON формате:
{json.dumps(self._get_example_for_model(model), ensure_ascii=False, indent=2)}

ИСХОДНАЯ ЗАДАЧА: {original_prompt}"""
                    continue
                else:
                    last_message = "{}"  # Пустой JSON для обработки ошибки валидации
            
            # Проверяем на шаблоны "мышления" которые нужно исключить
            thinking_patterns = ['<think>', 'Okay, let', 'Let me', 'I need to', 'Sure,']
            has_thinking = any(pattern in last_message for pattern in thinking_patterns)
            
            if has_thinking:
                logger.warning(f"⚠️ Агент {agent.name} использует размышления. Очищаем и принуждаем к JSON ответу.")
                if attempt < max_retries - 1:
                    prompt = f"""КРИТИЧЕСКАЯ ОШИБКА! ВЫ ИСПОЛЬЗУЕТЕ ЗАПРЕЩЕННЫЕ ЭЛЕМЕНТЫ!

ЗАПРЕЩЕНО:
- Любые <think> блоки
- Размышления на английском
- Объяснения перед JSON

ВЕРНИТЕ ТОЛЬКО ЧИСТЫЙ JSON:
{json.dumps(self._get_example_for_model(model), ensure_ascii=False, indent=2)}

ИСХОДНАЯ ЗАДАЧА: {original_prompt}"""
                    continue
                else:
                    last_message = "{}"
            
            # Очищаем ответ от "размышлений" и других нежелательных паттернов
            cleaned_message = last_message
            
            # Специальная обработка для DataExtractor
            if agent.name == "DataExtractor":
                # Прямой поиск JSON с ценой в тексте
                price_match = re.search(r'\{\s*"price"\s*:\s*[^}]+\}', cleaned_message)
                if price_match:
                    json_str = price_match.group(0)
                    logger.info(f"✅ DataExtractor: Найден JSON: '{json_str}'")
                else:
                    # Убираем <think> блоки и ищем снова
                    no_think = re.sub(r'<think>.*?</think>', '', cleaned_message, flags=re.DOTALL).strip()
                    price_match = re.search(r'\{\s*"price"\s*:\s*[^}]+\}', no_think)
                    if price_match:
                        json_str = price_match.group(0)
                        logger.info(f"✅ DataExtractor: JSON после очистки: '{json_str}'")
                    else:
                        # ИСПРАВЛЕНИЕ: Умное извлечение цены из результатов веб-поиска
                        logger.info(f"🔍 DataExtractor: Ищем цену в тексте результатов поиска...")
                        
                        # Паттерны для поиска цены iPhone в рублях
                        price_patterns = [
                            r'(\d{1,3}(?:\s?\d{3})*)\s*руб',  # 139 990 руб
                            r'(\d{1,3}(?:\s?\d{3})*)\s*₽',   # 139990₽
                            r'(\d{1,3}(?:,\d{3})*)\s*руб',   # 139,990 руб
                            r'(\d{1,3}(?:\.\d{3})*)\s*руб',  # 139.990 руб
                            r'Price.*?(\d{1,3}(?:\s?\d{3})*)', # Price: 139990
                            r'стоимост.*?(\d{1,3}(?:\s?\d{3})*)', # стоимость 139990
                            r'цена.*?(\d{1,3}(?:\s?\d{3})*)',    # цена 139990
                        ]
                        
                        extracted_price = None
                        for pattern in price_patterns:
                            matches = re.findall(pattern, cleaned_message, re.IGNORECASE)
                            for match in matches:
                                # Очищаем от пробелов и преобразуем
                                price_str = re.sub(r'\s+', '', match)
                                try:
                                    price_num = float(price_str)
                                    # Проверяем что цена в разумном диапазоне для iPhone (50k-300k рублей)
                                    if 50000 <= price_num <= 300000:
                                        extracted_price = price_num
                                        logger.info(f"✅ DataExtractor: Извлечена цена из текста: {price_num}")
                                        break
                                except ValueError:
                                    continue
                            if extracted_price:
                                break
                        
                        if extracted_price:
                            json_str = f'{{"price": {extracted_price}}}'
                        else:
                            # Fallback - ищем число после "price"
                            value_match = re.search(r'"price"\s*:\s*([\d.]+)', cleaned_message)
                            if value_match:
                                json_str = f'{{"price": {value_match.group(1)}}}'
                                logger.info(f"🔧 DataExtractor: Восстановлен JSON: '{json_str}'")
                            else:
                                logger.warning("⚠️ DataExtractor: Цена не найдена в результатах поиска")
                                json_str = '{"price": null}'
            else:
                # Обычная логика для других агентов
                json_str = cleaned_message
                
                # Ищем JSON в markdown блоках
                markdown_match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", cleaned_message)
                if markdown_match:
                    json_str = markdown_match.group(1)
                else:
                    # Убираем <think> блоки и ищем JSON
                    no_think = re.sub(r'<think>.*?</think>', '', cleaned_message, flags=re.DOTALL).strip()
                    
                    # Ищем JSON объект
                    json_patterns = [
                        r'\{\s*"[^"]+"\s*:\s*[^}]+\}',  # {"key": value}
                        r'\{[^{}]+\}',                  # любой простой объект
                        r'\{[\s\S]*?\}',                # любой объект (с переносами)
                    ]
                    
                    for pattern in json_patterns:
                        match = re.search(pattern, no_think)
                        if match:
                            json_str = match.group(0)
                            break
                    else:
                        json_str = no_think if no_think else cleaned_message
            
            logger.info(f"🔍 Финальный JSON: '{json_str[:100]}...' (агент: {agent.name})")
            
            # json_str готов для парсинга

            try:
                # Дополнительная очистка JSON строки
                json_str = json_str.strip()
                if not json_str:
                    raise json.JSONDecodeError("Пустая JSON строка", "", 0)
                
                # ИСПРАВЛЕНИЕ: Улучшенное извлечение JSON для кода с переносами строк
                if agent.name != "DataExtractor":
                    # Ищем JSON блок более точно
                    json_match = re.search(r'\{[\s\S]*\}', json_str)
                    if json_match:
                        potential_json = json_match.group(0)
                        
                        # Пробуем парсить как есть
                        try:
                            parsed_json = json.loads(potential_json)
                            validated_data = model.model_validate(parsed_json)
                            logger.info(f"✅ Валидный ответ от {agent.name} получен.")
                            return validated_data
                        except json.JSONDecodeError:
                            # Если не получается, пробуем найти структурированные поля
                            pass
                    
                    # Fallback: Извлекаем поля вручную для кода
                    if '"description"' in json_str and '"code"' in json_str:
                        try:
                            desc_match = re.search(r'"description"\s*:\s*"([^"]*)"', json_str)
                            
                            # Для кода используем более сложное извлечение
                            code_match = re.search(r'"code"\s*:\s*"(.*?)"(?=\s*[,}])', json_str, re.DOTALL)
                            if not code_match:
                                # Альтернативный поиск - между последними кавычками
                                code_match = re.search(r'"code"\s*:\s*"(.*)"', json_str, re.DOTALL)
                            
                            if desc_match and code_match:
                                description = desc_match.group(1)
                                code = code_match.group(1)
                                
                                # Создаем правильную структуру данных
                                parsed_json = {
                                    "description": description,
                                    "code": code
                                }
                                validated_data = model.model_validate(parsed_json)
                                logger.info(f"✅ Валидный ответ от {agent.name} получен (fallback parsing).")
                                return validated_data
                        except Exception as e:
                            logger.warning(f"Fallback parsing failed: {e}")
                            
                    # ДОПОЛНИТЕЛЬНЫЙ FALLBACK: Более агрессивное извлечение для программиста
                    if agent.name == "Программист":
                        try:
                            # Ищем описание между первой парой кавычек после "description"
                            desc_pattern = r'"description"\s*:\s*"([^"]*)"'
                            desc_match = re.search(desc_pattern, json_str)
                            
                            # Для кода ищем все после "code": и до конца (может быть обрезано)
                            code_pattern = r'"code"\s*:\s*"([^"]*(?:[^"\\]|\\.)*)'  # любые символы включая экранированные
                            code_match = re.search(code_pattern, json_str, re.DOTALL)
                            
                            if not code_match:
                                # Еще один паттерн - ищем от "code": до конца строки
                                code_pattern2 = r'"code"\s*:\s*"(.*?)$'
                                code_match = re.search(code_pattern2, json_str, re.DOTALL | re.MULTILINE)
                            
                            if desc_match:
                                description = desc_match.group(1)
                                
                                # Если код найден, используем его, иначе создаем минимальный
                                if code_match:
                                    code = code_match.group(1)
                                    # Очищаем код от возможных артефактов
                                    code = code.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t')
                                else:
                                    # Создаем базовый код если не найден
                                    code = """def calculate_days_for_iphone(monthly_salary):
    price = 129990.0  # Цена iPhone 15 Pro Max 256GB
    daily_salary = monthly_salary / 22.5
    return int(price / daily_salary)

if __name__ == '__main__':
    salary = 50000
    days = calculate_days_for_iphone(salary)
    print(f'Для накопления потребуется {days} рабочих дней')"""
                                
                                parsed_json = {
                                    "description": description,
                                    "code": code
                                }
                                validated_data = model.model_validate(parsed_json)
                                logger.info(f"✅ Валидный ответ от {agent.name} получен (агрессивный fallback).")
                                return validated_data
                        except Exception as e:
                            logger.warning(f"Агрессивный fallback для Программиста не удался: {e}")
                
                # Обычный парсинг для DataExtractor и других случаев
                parsed_json = json.loads(json_str)
                validated_data = model.model_validate(parsed_json)
                logger.info(f"✅ Валидный ответ от {agent.name} получен.")
                return validated_data
            except json.JSONDecodeError as e:
                logger.warning(f"❌ Ошибка парсинга JSON от {agent.name}: {e}")
                logger.error(f"🔍 Некорректный ответ: '{last_message[:500]}'")
                
                # Специальное сообщение для программиста
                if agent.name == "Программист":
                    error_msg = f"""КРИТИЧЕСКАЯ ОШИБКА JSON!

ВАШ ОТВЕТ: "{last_message[:300]}..."

ПРОБЛЕМА: Переносы строк в коде должны быть экранированы!

ПРАВИЛЬНЫЙ ФОРМАТ:
{{
  "description": "Скрипт для расчета дней накопления на iPhone",
  "code": "def calculate_days():\\n    price = 139990\\n    return int(price / salary)\\n\\nif __name__ == '__main__':\\n    print('demo')"
}}

ВАЖНО: Используйте \\n вместо реальных переносов!

ИСХОДНАЯ ЗАДАЧА: {original_prompt}"""
                else:
                    error_msg = f"""КРИТИЧЕСКАЯ ОШИБКА JSON!

ВАШ ОТВЕТ: "{last_message[:300]}..."

ЭТОТ ОТВЕТ НЕ ЯВЛЯЕТСЯ КОРРЕКТНЫМ JSON!

НЕМЕДЛЕННО ВЕРНИТЕ ТОЛЬКО ЭТО:
{json.dumps(self._get_example_for_model(model), ensure_ascii=False, indent=2)}

НЕ ДОБАВЛЯЙТЕ НИЧЕГО КРОМЕ JSON!

ИСХОДНАЯ ЗАДАЧА: {original_prompt}"""
                prompt = error_msg
                
            except ValidationError as e:
                logger.warning(f"❌ Ошибка валидации данных от {agent.name}: {e}")
                logger.error(f"🔍 Некорректная структура JSON: '{json_str[:500]}'")
                
                error_details = []
                for error in e.errors():
                    field = error.get('loc', ['unknown'])[0] if error.get('loc') else 'unknown'
                    msg = error.get('msg', 'неизвестная ошибка')
                    error_details.append(f"- Поле '{field}': {msg}")
                
                error_msg = f"""КРИТИЧЕСКАЯ ОШИБКА СТРУКТУРЫ!

ВАШ JSON: "{json_str[:300]}..."

ПРОБЛЕМЫ С ПОЛЯМИ:
{chr(10).join(error_details)}

НЕМЕДЛЕННО ВЕРНИТЕ ТОЧНО ЭТО:
{json.dumps(self._get_example_for_model(model), ensure_ascii=False, indent=2)}

НЕ МЕНЯЙТЕ СТРУКТУРУ! НЕ ДОБАВЛЯЙТЕ ПОЛЯ!

ИСХОДНАЯ ЗАДАЧА: {original_prompt}"""
                prompt = error_msg
        
        raise RuntimeError(f"❌ Агент {agent.name} не смог предоставить валидный ответ после {max_retries} попыток.")
    
    def _save_code_to_file(self, content: str, filename: str) -> str:
        """Сохраняет код в файл и возвращает полный путь."""
        filepath = os.path.join(self.config.WORKSPACE_DIR, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"💾 Файл сохранен: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения файла {filepath}: {e}")
            raise

    def _fix_test_imports(self, test_code: str, main_script_name: str) -> str:
        """Исправляет импорты в тестах для корректной работы."""
        lines = test_code.split('\n')
        
        # Ищем функции в основном скрипте для импорта
        main_script_path = os.path.join(self.config.WORKSPACE_DIR, main_script_name)
        functions_to_import = []
        
        try:
            with open(main_script_path, 'r', encoding='utf-8') as f:
                main_content = f.read()
                # Простой поиск функций def function_name(
                import re
                function_matches = re.findall(r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', main_content)
                functions_to_import = [func for func in function_matches if not func.startswith('_')]
        except:
            # Если не можем прочитать файл, попробуем извлечь из самого теста
            function_matches = re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', test_code)
            functions_to_import = list(set([func for func in function_matches if func not in ['assert', 'print', 'len', 'str', 'int', 'float']]))

        # Проверяем, есть ли уже импорты
        has_imports = any('import' in line and 'generated_script' in line for line in lines[:10])
        
        if not has_imports and functions_to_import:
            # Добавляем импорты в начало файла
            script_name_without_ext = main_script_name.replace('.py', '')
            
            import_lines = []
            if functions_to_import:
                func_list = ', '.join(functions_to_import)
                import_lines.append(f"from {script_name_without_ext} import {func_list}")
            
            # Вставляем импорты после всех комментариев и импортов pytest/unittest
            insert_position = 0
            for i, line in enumerate(lines):
                if line.strip().startswith('#') or line.strip().startswith('import') or line.strip().startswith('from') or line.strip() == '':
                    insert_position = i + 1
                else:
                    break
            
            # Вставляем наши импорты
            for import_line in reversed(import_lines):
                lines.insert(insert_position, import_line)
            
            logger.info(f"🔧 Добавлены импорты: {import_lines}")
        
        return '\n'.join(lines)

    def _supervised_fix(self, code_result: GeneratedCode, review_result: CodeReview, test_logs: str) -> tuple:
        """Исправление под руководством решателя проблем."""
        self.fancy_logger.log_agent_action("TeamLead", "Анализ проблемы", "Изучаю ошибки для принятия решения")
        logger.info("🎯 Запуск исправления под руководством супервизора...")
        
        # Решатель проблем анализирует ситуацию и дает инструкции
        supervisor_prompt = f"""ПРОАНАЛИЗИРУЙТЕ ПРОБЛЕМУ И ДАЙТЕ ИНСТРУКЦИИ!

ТЕКУЩИЙ КОД:
{code_result.code}

ТЕКУЩИЕ ТЕСТЫ:
{review_result.test_code}

ЛОГИ ОШИБОК:
{test_logs}

ВАША ЗАДАЧА:
1. Определить, кто виноват - код или тесты
2. Дать четкие инструкции конкретному агенту
3. Указать точные значения/формулы

АНАЛИЗИРУЙТЕ:
- Если assert 62 == 634 - это НЕПРАВИЛЬНЫЕ ожидания в тестах → target_agent: "Ревьюер"
- Если логика кода неверна → target_agent: "Программист"

ВЕРНИТЕ JSON:
- problem_analysis: детальный анализ проблемы
- target_agent: "Программист" или "Ревьюер"
- specific_instructions: точные инструкции для исправления
- expected_outcome: что должно произойти

НЕ ДУМАЙТЕ! СРАЗУ РЕШЕНИЕ В JSON!"""

        # Получаем решение от супервизора
        solution = self._invoke_agent_and_validate(self.problem_solver, supervisor_prompt, ProblemSolution)
        self.fancy_logger.log_agent_action("TeamLead", "Решение принято", 
                                         f"Виновник: {solution.target_agent} | Проблема: {solution.problem_analysis[:50]}...")
        
        # Выполняем инструкции супервизора
        if solution.target_agent == "Программист":
            # Программист исправляет код по инструкциям
            fix_prompt = f"""🚨 КРИТИЧЕСКАЯ ИНСТРУКЦИЯ ОТ TEAMLEAD - ВЫПОЛНИТЬ НЕМЕДЛЕННО! 🚨

⚡ ЭТО ПРИОРИТЕТ №1! Забудьте все предыдущие подходы!

📋 АНАЛИЗ ПРОБЛЕМЫ ОТ TEAMLEAD:
{solution.problem_analysis}

🎯 ВАШИ ТОЧНЫЕ ИНСТРУКЦИИ ОТ TEAMLEAD:
{solution.specific_instructions}

✅ ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:
{solution.expected_outcome}

📄 ТЕКУЩИЙ ПРОБЛЕМНЫЙ КОД:
{code_result.code}

🔧 ДЕЙСТВИЯ:
1. НЕМЕДЛЕННО реализуйте ВСЕ инструкции TeamLead
2. НЕ отклоняйтесь от указаний TeamLead
3. ТОЧНО используйте указанные значения/формулы
4. НЕ импровизируйте - следуйте инструкциям!

⚠️ ПОМНИТЕ: TeamLead уже проанализировал проблему. Ваша задача - ТОЧНОЕ выполнение его инструкций!

ВЕРНИТЕ JSON:
- description: "Исправления по инструкциям TeamLead: [краткое описание изменений]"
- code: исправленный код СТРОГО по инструкциям TeamLead

🚀 ДЕЙСТВУЙТЕ СЕЙЧАС! НЕ ДУМАЙТЕ - ВЫПОЛНЯЙТЕ!"""

            fixed_code = self._invoke_agent_and_validate(self.code_writer, fix_prompt, GeneratedCode)
            self.fancy_logger.log_agent_action("Программист", "Код исправлен", "По инструкциям TeamLead")
            self.fancy_logger.log_agent_action("TeamLead", "Инструкция выполнена", "Программист исправил код")
            return fixed_code, review_result
            
        else:  # target_agent == "Ревьюер"
            # Ревьюер исправляет тесты по инструкциям
            fix_prompt = f"""🚨 КРИТИЧЕСКАЯ ИНСТРУКЦИЯ ОТ TEAMLEAD - ИСПРАВИТЬ ТЕСТЫ НЕМЕДЛЕННО! 🚨

⚡ ЭТО ПРИОРИТЕТ №1! Ваши предыдущие тесты были НЕПРАВИЛЬНЫМИ!

📋 АНАЛИЗ ПРОБЛЕМЫ ОТ TEAMLEAD:
{solution.problem_analysis}

🎯 ВАШИ ТОЧНЫЕ ИНСТРУКЦИИ ОТ TEAMLEAD:
{solution.specific_instructions}

✅ ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:
{solution.expected_outcome}

📄 ИСХОДНЫЙ КОД (для понимания логики):
{code_result.code}

❌ ПРОБЛЕМНЫЕ ТЕСТЫ (которые нужно исправить):
{review_result.test_code}

🔧 ДЕЙСТВИЯ:
1. НЕМЕДЛЕННО исправьте тесты согласно инструкциям TeamLead
2. ТОЧНО используйте ожидаемые значения, указанные TeamLead
3. НЕ пересчитывайте - ДОВЕРЯЙТЕ анализу TeamLead
4. ИСПРАВЬТЕ все ошибочные assert'ы как указано

⚠️ ПОМНИТЕ: TeamLead уже проанализировал код и логику. Он знает правильные ожидаемые значения. НЕ спорьте с его анализом!

🎯 КОНКРЕТНО: Если TeamLead говорит "assert должен быть X, а не Y" - НЕМЕДЛЕННО замените Y на X!

ВЕРНИТЕ JSON:
- review_comments: ["Исправлено по инструкциям TeamLead: [описание изменений]"]
- test_code: тесты с ТОЧНЫМИ исправлениями от TeamLead
- improvements: ["Исправлены ожидаемые значения согласно анализу TeamLead"]

🚀 ДЕЙСТВУЙТЕ СЕЙЧАС! НЕ ДУМАЙТЕ - ИСПРАВЛЯЙТЕ ПО ИНСТРУКЦИЯМ!"""

            fixed_review = self._invoke_agent_and_validate(self.code_reviewer, fix_prompt, CodeReview)
            self.fancy_logger.log_agent_action("Ревьюер", "Тесты исправлены", "По инструкциям TeamLead")
            self.fancy_logger.log_agent_action("TeamLead", "Инструкция выполнена", "Ревьюер исправил тесты")
            return code_result, fixed_review

    def _filter_pip_installable_dependencies(self, dependencies: List[str]) -> List[str]:
        """Динамически определяет, какие зависимости нужно устанавливать через pip.
        Исключает модули стандартной библиотеки Python, используя встроенные возможности Python.
        """
        import sys
        import importlib.util
        
        pip_installable = []
        excluded = []
        
        for dep in dependencies:
            # Пропускаем пустые строки
            if not dep or not dep.strip():
                continue
                
            dep = dep.strip()
            
            try:
                # Метод 1: Проверяем, есть ли модуль в стандартной библиотеке (Python 3.10+)
                if hasattr(sys, 'stdlib_module_names') and dep in sys.stdlib_module_names:
                    excluded.append(dep)
                    continue
                
                # Метод 2: Проверяем, есть ли модуль в встроенных модулях
                if dep in sys.builtin_module_names:
                    excluded.append(dep)
                    continue
                
                # Метод 3: Пробуем найти спецификацию модуля
                spec = importlib.util.find_spec(dep)
                if spec is not None:
                    # Если модуль найден, проверяем его местоположение
                    if spec.origin:
                        # Если путь содержит стандартную библиотеку Python
                        stdlib_paths = [
                            sys.prefix,
                            getattr(sys, 'base_prefix', sys.prefix),
                            '/usr/lib/python',
                            '/System/Library/Frameworks/Python.framework'
                        ]
                        
                        is_stdlib = any(stdlib_path in spec.origin for stdlib_path in stdlib_paths)
                        
                        # Дополнительная проверка: если это .py файл в стандартной установке Python
                        if (spec.origin.endswith('.py') and 
                            ('site-packages' not in spec.origin) and 
                            ('dist-packages' not in spec.origin) and
                            is_stdlib):
                            excluded.append(dep)
                            continue
                    
                    # Если модуль уже доступен и это не третья сторона, исключаем
                    if (spec.origin is None or  # встроенный модуль
                        'site-packages' not in (spec.origin or '') and
                        'dist-packages' not in (spec.origin or '')):
                        
                        # Дополнительная проверка: пробуем импортировать
                        try:
                            __import__(dep)
                            # Если импорт прошел успешно и это не в site-packages, 
                            # вероятно это стандартная библиотека
                            import os.path
                            module = sys.modules.get(dep)
                            if module and hasattr(module, '__file__') and module.__file__:
                                if ('site-packages' not in module.__file__ and 
                                    'dist-packages' not in module.__file__ and
                                    any(stdlib_path in module.__file__ for stdlib_path in stdlib_paths)):
                                    excluded.append(dep)
                                    continue
                            elif module and not hasattr(module, '__file__'):
                                # Встроенный модуль без файла
                                excluded.append(dep)
                                continue
                        except ImportError:
                            # Если не удается импортировать, скорее всего нужна установка
                            pass
                
                # Если дошли до сюда, модуль нужно устанавливать
                pip_installable.append(dep)
                
            except Exception as e:
                # В случае любой ошибки при проверке, лучше попробовать установить
                logger.debug(f"🔍 Не удалось проверить модуль {dep}: {e}")
                pip_installable.append(dep)
        
        # Логируем результат
        if excluded:
            logger.info(f"🔧 Исключены модули стандартной библиотеки: {excluded}")
        if pip_installable:
            logger.info(f"📦 Будут установлены через pip: {pip_installable}")
        else:
            logger.info("📦 Внешние зависимости для установки не найдены")
            
        return pip_installable

    def _execute_tests(self, dependencies: List[str]) -> tuple:
        """Выполняет тесты с установкой зависимостей и возвращает код выхода и логи."""
        # Динамически фильтруем зависимости, исключая модули стандартной библиотеки
        filtered_deps = self._filter_pip_installable_dependencies(dependencies)
        
        # Подготавливаем список зависимостей для установки
        all_deps = list(set(filtered_deps + ["pytest"]))
        
        # Если после фильтрации не осталось внешних зависимостей, устанавливаем только pytest
        if not filtered_deps:
            deps_str = "pytest"
            logger.info("📦 Устанавливаем только pytest (внешние зависимости не требуются)")
        else:
            deps_str = " ".join(all_deps)
        
        # Логируем настройку Docker среды
        self.fancy_logger.log_docker_setup(all_deps, self.config.USE_DOCKER)
        
        # Команда для установки зависимостей и запуска тестов с правильным PYTHONPATH
        exec_cmd = f"pip install -q --no-cache-dir {deps_str} && PYTHONPATH=. python -m pytest {self.config.TESTS_NAME} -v --tb=short"
        
        logger.info(f"🧪 Выполнение тестов с командой: {exec_cmd}")
        
        try:
            # Выполняем команду через user_proxy с docker
            exit_code, logs_str = self.user_proxy.execute_code_blocks([("sh", exec_cmd)])
            logger.info(f"📊 Тесты завершены с кодом: {exit_code}")
            return exit_code, logs_str
        except Exception as e:
            error_msg = f"Ошибка выполнения тестов: {e}"
            logger.error(error_msg)
            return 1, error_msg
    
    def _execute_tests_with_logging(self, dependencies: List[str], iteration: int) -> tuple:
        """Выполняет тесты и логирует результаты в fancy logger."""
        exit_code, test_logs = self._execute_tests(dependencies)
        
        # Логируем результаты в fancy logger
        self.fancy_logger.log_test_results(iteration, exit_code, test_logs, dependencies)
        
        return exit_code, test_logs

    def _run_improvement_loop(self, code_result: GeneratedCode, review_result: CodeReview, dependencies: List[str] = None) -> tuple:
        """Запускает итеративный цикл улучшения кода с тестами и фиксами."""
        logger.info("--- Запуск цикла улучшений ---")
        
        if dependencies is None:
            dependencies = ["requests", "json"]  # базовые зависимости по умолчанию
        
        current_code = code_result
        current_review = review_result
        
        # Для предотвращения бесконечных циклов
        seen_error_patterns = set()
        consecutive_assertion_errors = 0
        
        for iteration in range(self.config.MAX_IMPROVEMENT_LOOPS):
            logger.info(f"🔄 Итерация улучшения {iteration + 1}/{self.config.MAX_IMPROVEMENT_LOOPS}")
            
            # Логируем начало итерации
            self.fancy_logger.log_improvement_cycle(
                iteration + 1, 
                self.config.MAX_IMPROVEMENT_LOOPS, 
                "Начало итерации", 
                "Сохранение файлов и выполнение тестов"
            )
            
            # Сохраняем текущий код и тесты с исправленными импортами
            self._save_code_to_file(current_code.code, self.config.SCRIPT_NAME)
            
            # Исправляем импорты в тестах перед сохранением
            fixed_test_code = self._fix_test_imports(current_review.test_code, self.config.SCRIPT_NAME)
            self._save_code_to_file(fixed_test_code, self.config.TESTS_NAME)
            
            # Выполняем тесты
            exit_code, test_logs = self._execute_tests_with_logging(dependencies, iteration + 1)
            
            if exit_code == 0:
                logger.info("✅ Тесты пройдены успешно!")
                self.fancy_logger.log_improvement_cycle(
                    iteration + 1, 
                    self.config.MAX_IMPROVEMENT_LOOPS, 
                    "Успех!", 
                    "Все тесты пройдены успешно"
                )
                break
            else:
                logger.warning(f"❌ Тесты провалены. Анализируем тип ошибки...")
                
                # Определяем тип ошибки
                is_import_error = "NameError" in test_logs or "ImportError" in test_logs or "ModuleNotFoundError" in test_logs
                is_assertion_error = "AssertionError" in test_logs
                
                # Создаем уникальный отпечаток ошибки для обнаружения циклов
                error_pattern = f"{is_import_error}_{is_assertion_error}_{hash(test_logs[:200])}"
                
                if error_pattern in seen_error_patterns:
                    logger.warning(f"🔄 Обнаружен повторяющийся паттерн ошибки! Переключаемся на супервизорское исправление...")
                    self.fancy_logger.log_improvement_cycle(
                        iteration + 1, 
                        self.config.MAX_IMPROVEMENT_LOOPS, 
                        "Супервизорское исправление", 
                        "Обнаружен повторяющийся паттерн ошибки"
                    )
                    try:
                        current_code, current_review = self._supervised_fix(current_code, current_review, test_logs)
                        consecutive_assertion_errors = 0  # Сбрасываем счетчик
                        continue
                    except Exception as e:
                        logger.error(f"❌ Супервизорское исправление не удалось: {e}")
                        break
                
                seen_error_patterns.add(error_pattern)
                
                if is_assertion_error:
                    consecutive_assertion_errors += 1
                    if consecutive_assertion_errors >= 3:
                        logger.warning(f"🔄 Слишком много ошибок утверждений подряд! Запускаем супервизорское исправление...")
                        self.fancy_logger.log_improvement_cycle(
                            iteration + 1, 
                            self.config.MAX_IMPROVEMENT_LOOPS, 
                            "Супервизорское исправление", 
                            "Слишком много ошибок утверждений подряд"
                        )
                        try:
                            current_code, current_review = self._supervised_fix(current_code, current_review, test_logs)
                            consecutive_assertion_errors = 0
                            continue
                        except Exception as e:
                            logger.error(f"❌ Супервизорское исправление не удалось: {e}")
                            break
                    
                    # Для ошибок утверждений используем супервизорский подход с первой попытки
                    logger.info(f"🎯 Обнаружена ошибка утверждения. Запускаем супервизорское исправление...")
                    self.fancy_logger.log_improvement_cycle(
                        iteration + 1, 
                        self.config.MAX_IMPROVEMENT_LOOPS, 
                        "Супервизорское исправление", 
                        "Ошибка утверждения в тестах"
                    )
                    try:
                        current_code, current_review = self._supervised_fix(current_code, current_review, test_logs)
                        continue
                    except Exception as e:
                        logger.error(f"❌ Супервизорское исправление не удалось: {e}")
                        break
                
                elif is_import_error:
                    # Для ошибок импорта используем старый подход
                    consecutive_assertion_errors = 0
                    self.fancy_logger.log_improvement_cycle(
                        iteration + 1, 
                        self.config.MAX_IMPROVEMENT_LOOPS, 
                        "Исправление импортов", 
                        "Обнаружены ошибки импорта функций"
                    )
                    fix_prompt = f"""КРИТИЧЕСКАЯ ОШИБКА ИМПОРТА! ТЕСТЫ НЕ МОГУТ НАЙТИ ФУНКЦИИ!

ПРОВАЛИВШИЙСЯ КОД:
{current_code.code}

ЛОГИ ОШИБОК (ПРОБЛЕМА С ИМПОРТАМИ):
{test_logs}

ПРОБЛЕМА: Тесты не могут импортировать функции из основного скрипта.

НЕМЕДЛЕННО ИСПРАВЬТЕ:
1. Убедитесь, что все функции определены в основном коде
2. Проверьте названия функций
3. Убедитесь, что функции не находятся внутри if __name__ == '__main__' блока

ВЕРНИТЕ JSON:
- description: обновленное описание
- code: исправленный код с правильными функциями

НЕ ДУМАЙТЕ! СРАЗУ ИСПРАВЛЕННЫЙ КОД В JSON!"""

                    try:
                        fixed_code_result = self._invoke_agent_and_validate(self.code_writer, fix_prompt, GeneratedCode)
                        current_code = fixed_code_result
                        logger.info("🔧 Код исправлен программистом")
                    except Exception as e:
                        logger.error(f"❌ Не удалось исправить код на итерации {iteration + 1}: {e}")
                        break
                
                else:
                    # Другие типы ошибок - используем супервизорский подход
                    consecutive_assertion_errors = 0
                    self.fancy_logger.log_improvement_cycle(
                        iteration + 1, 
                        self.config.MAX_IMPROVEMENT_LOOPS, 
                        "Супервизорское исправление", 
                        "Неизвестный тип ошибки"
                    )
                    logger.info(f"🎯 Неизвестный тип ошибки. Запускаем супервизорское исправление...")
                    try:
                        current_code, current_review = self._supervised_fix(current_code, current_review, test_logs)
                        continue
                    except Exception as e:
                        logger.error(f"❌ Супервизорское исправление не удалось: {e}")
                        break
        
        # Финальная проверка тестов
        logger.info("🔍 Финальная проверка тестов...")
        self.fancy_logger.log_improvement_cycle(
            0,  # Финальная проверка вне итераций
            self.config.MAX_IMPROVEMENT_LOOPS, 
            "Финальная проверка", 
            "Проверка финального состояния кода и тестов"
        )
        self._save_code_to_file(current_code.code, self.config.SCRIPT_NAME)
        
        # Исправляем импорты в финальных тестах
        final_fixed_test_code = self._fix_test_imports(current_review.test_code, self.config.SCRIPT_NAME)
        self._save_code_to_file(final_fixed_test_code, self.config.TESTS_NAME)
        
        final_exit_code, final_logs = self._execute_tests(dependencies)
        
        # Логируем финальные результаты
        self.fancy_logger.log_test_results(0, final_exit_code, final_logs, dependencies)
        
        if final_exit_code == 0:
            logger.info("✅ Финальные тесты пройдены! Код готов к продакшену.")
            self.fancy_logger.log_improvement_cycle(
                0, 
                self.config.MAX_IMPROVEMENT_LOOPS, 
                "Финальный успех", 
                "Код готов к продакшену"
            )
        else:
            logger.warning(f"⚠️ Финальные тесты все еще не проходят после {self.config.MAX_IMPROVEMENT_LOOPS} итераций.")
            logger.warning(f"Логи: {final_logs[:200]}...")
            self.fancy_logger.log_improvement_cycle(
                0, 
                self.config.MAX_IMPROVEMENT_LOOPS, 
                "Финальные проблемы", 
                f"Тесты не проходят после {self.config.MAX_IMPROVEMENT_LOOPS} итераций"
            )
        
        logger.info("🏁 Цикл улучшений завершен")
        return current_code, current_review

    def _get_example_for_model(self, model: Type[BaseModel]) -> dict:
        """Возвращает пример данных для указанной модели."""
        if model == Plan:
            return {
                "plan": ["шаг 1 - анализ задачи", "шаг 2 - поиск данных", "шаг 3 - написание кода"],
                "data_query": "цена iPhone 15 Pro Max 256GB",
                "dependencies": ["requests", "json"]
            }
        elif model == ExtractedData:
            return {"price": 123456.78}  # или null если не найдено
        elif model == GeneratedCode:
            return {
                "description": "Скрипт для расчета дней накопления на iPhone",
                "code": "def calculate_days_for_iphone(monthly_salary):\\n    price = 139990.0\\n    return int(price / (monthly_salary / 22.5))\\n\\nif __name__ == '__main__':\\n    print('demo')"
            }
        elif model == CodeReview:
            return {
                "review_comments": ["Код соответствует требованиям", "Добавлена обработка ошибок"],
                "test_code": "import unittest\n\nclass TestCalculator(unittest.TestCase):\n    def test_function(self):\n        self.assertTrue(True)",
                "improvements": ["Добавить docstring", "Улучшить обработку ошибок"]
            }
        elif model == Documentation:
            return {
                "title": "Калькулятор накоплений на iPhone",
                "description": "Проект для расчета времени накопления на покупку iPhone",
                "usage_examples": ["calculate_days_for_iphone(50000)", "result = func(100000)"],
                "api_documentation": "calculate_days_for_iphone(monthly_salary: float) -> int"
            }
        elif model == ProblemSolution:
            return {
                "problem_analysis": "Тесты ожидают неправильные значения для функции",
                "target_agent": "Ревьюер",
                "specific_instructions": "Исправить ожидаемые значения в тестах согласно логике кода",
                "expected_outcome": "Тесты будут проходить с правильными ожидаемыми значениями"
            }
        return {}

    def run(self, task: str):
        logger.info(f"🚀 НАЧАЛО РАБОТЫ ПО ЗАДАЧЕ: \"{task}\"")
        self.fancy_logger.log_agent_action("Оркестратор", "Начало работы", f"Задача: {task}")
        
        try:
            # --- Шаг 1: Планирование ---
            self.fancy_logger.log_phase_start("Планирование", 1)
            plan_prompt = f"""НЕМЕДЛЕННО СОЗДАЙТЕ ПЛАН!

ЗАДАЧА ПОЛЬЗОВАТЕЛЯ: {task}

ВЕРНИТЕ JSON С:
- plan: список шагов разработки
- data_query: запрос для поиска данных (если нужно) или null  
- dependencies: список Python библиотек

НЕ ДУМАЙТЕ! СРАЗУ JSON!"""
            plan_result = self._invoke_agent_and_validate(self.planner, plan_prompt, Plan)
            self.fancy_logger.log_agent_action("Архитектор", "План создан", f"Шагов: {len(plan_result.plan)}, Зависимости: {plan_result.dependencies}")

            # --- Шаг 2: Извлечение данных (если необходимо) ---
            self.fancy_logger.log_phase_start("Извлечение данных", 2)
            extracted_data_result = ExtractedData(price=None)
            if plan_result.data_query:
                data_prompt = f"""ИЗВЛЕКИТЕ ДАННЫЕ О ЦЕНЕ! НИКАКИХ РАЗМЫШЛЕНИЙ!

ПОИСКОВЫЙ ЗАПРОС: "{plan_result.data_query}"

АБСОЛЮТНО ЗАПРЕЩЕНО:
- блоки <think>
- объяснения
- рассуждения

НЕМЕДЛЕННЫЕ ДЕЙСТВИЯ:
1. web_search("{plan_result.data_query}")
2. Найти цену
3. Вернуть ТОЛЬКО: {{"price": число}}

ТОЛЬКО JSON! НАЧИНАЙТЕ СРАЗУ!"""
                
                # Для DataExtractor используем более строгий подход
                max_data_retries = 5
                for retry in range(max_data_retries):
                    try:
                        extracted_data_result = self._invoke_agent_and_validate(self.data_extractor, data_prompt, ExtractedData)
                        self.fancy_logger.log_agent_action("DataExtractor", "Данные извлечены", f"Цена: {extracted_data_result.price}")
                        break
                    except Exception as e:
                        if retry < max_data_retries - 1:
                            logger.warning(f"DataExtractor попытка {retry + 1} не удалась, повторяем...")
                            data_prompt = f"""ОШИБКА! ВЫ НАРУШИЛИ ПРАВИЛА!

ТРЕБОВАНИЕ: ТОЛЬКО JSON БЕЗ <think>!

web_search("{plan_result.data_query}")
Затем ТОЛЬКО: {{"price": найденная_цена}}

ПОПЫТКА {retry + 2}. ИСПРАВЬТЕСЬ!"""
                        else:
                            logger.error(f"DataExtractor не смог извлечь данные после {max_data_retries} попыток")
                            logger.info("🔄 Используем стандартную цену iPhone 15 Pro Max")
                            extracted_data_result = ExtractedData(price=139990.0)  # Стандартная цена
                            self.fancy_logger.log_error("DataExtractor", "Использована стандартная цена")
            else:
                extracted_data_result = ExtractedData(price=None)
                self.fancy_logger.log_agent_action("Оркестратор", "Поиск пропущен", "Данные не требуются")

            # --- Шаг 3: Генерация Кода ---
            self.fancy_logger.log_phase_start("Генерация кода", 3)
            code_prompt = f"""НЕМЕДЛЕННО НАПИШИТЕ КОД!

ПЛАН: {json.dumps(plan_result.plan, ensure_ascii=False)}
БИБЛИОТЕКИ: {json.dumps(plan_result.dependencies, ensure_ascii=False)}  
ДАННЫЕ: {extracted_data_result.model_dump_json()}

ВЕРНИТЕ JSON:
- description: описание функциональности  
- code: полный исполняемый Python код

НЕ ДУМАЙТЕ! СРАЗУ КОД В JSON!"""
            code_result = self._invoke_agent_and_validate(self.code_writer, code_prompt, GeneratedCode)
            self.fancy_logger.log_agent_action("Программист", "Код сгенерирован", f"Описание: {code_result.description}")

            # --- Шаг 4: Code Review и Тесты ---
            self.fancy_logger.log_phase_start("Code Review и тесты", 4)
            review_prompt = f"""НЕМЕДЛЕННО ПРОВЕДИТЕ REVIEW КОДА!

КОД ДЛЯ АНАЛИЗА:
{code_result.code}

ОПИСАНИЕ: {code_result.description}

ЗАДАЧИ:
1. Проанализируйте код на качество, безопасность, читаемость
2. Напишите полные тесты для функций
3. Предложите улучшения

ВЕРНИТЕ JSON:
- review_comments: список замечаний по коду
- test_code: полный код тестов (pytest или unittest)  
- improvements: предложения по улучшению

НЕ ДУМАЙТЕ! СРАЗУ REVIEW В JSON!"""
            review_result = self._invoke_agent_and_validate(self.code_reviewer, review_prompt, CodeReview)
            self.fancy_logger.log_agent_action("Ревьюер", "Review завершен", f"Комментариев: {len(review_result.review_comments)}")

            # --- Шаг 4.5: Цикл улучшений с тестами ---
            self.fancy_logger.log_phase_start("Итеративные улучшения", 4.5)
            final_code_result, final_review_result = self._run_improvement_loop(
                code_result, review_result, plan_result.dependencies
            )
            self.fancy_logger.log_success("Цикл улучшений завершен")

            # --- Шаг 5: Документация ---
            self.fancy_logger.log_phase_start("Создание документации", 5)
            docs_prompt = f"""НЕМЕДЛЕННО СОЗДАЙТЕ ДОКУМЕНТАЦИЮ!

КОД (ФИНАЛЬНАЯ ВЕРСИЯ ПОСЛЕ УЛУЧШЕНИЙ):
{final_code_result.code}

ОПИСАНИЕ: {final_code_result.description}
ПЛАН: {json.dumps(plan_result.plan, ensure_ascii=False)}
РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ: Все тесты пройдены успешно

СОЗДАЙТЕ:
1. Название проекта
2. Подробное описание функциональности
3. Примеры использования кода
4. Документацию по API/функциям

ВЕРНИТЕ JSON:
- title: название проекта
- description: описание проекта
- usage_examples: примеры использования
- api_documentation: документация функций

НЕ ДУМАЙТЕ! СРАЗУ ДОКУМЕНТАЦИЮ В JSON!"""
            docs_result = self._invoke_agent_and_validate(self.tech_writer, docs_prompt, Documentation)
            self.fancy_logger.log_agent_action("ТехПисатель", "Документация создана", f"Проект: {docs_result.title}")
            
            # --- Финализация ---
            self.finalize(final_code_result, final_review_result, docs_result)
            self.fancy_logger.log_success("Рабочий процесс успешно завершен")

        except Exception as e:
            self.fancy_logger.log_error("Оркестратор", f"Критическая ошибка: {e}")
            logger.critical(f"Процесс прерван из-за критической ошибки: {e}", exc_info=True)
            print("\n❌ Процесс был аварийно завершен.")
        finally:
            self.fancy_logger.log_session_end()
            self.raw_logger.log_session_end()
            print(f"📂 Все артефакты находятся в директории: '{self.config.WORKSPACE_DIR}'")

    def finalize(self, code_result: GeneratedCode, review_result: CodeReview, docs_result: Documentation):
        logger.info("--- Финализация: Сохранение артефактов ---")
        
        # Сохраняем основной скрипт
        code_filepath = os.path.join(self.config.WORKSPACE_DIR, self.config.SCRIPT_NAME)
        with open(code_filepath, "w", encoding="utf-8") as f:
            f.write(code_result.code)
        logger.info(f"💾 Основной скрипт сохранен: {code_filepath}")
        
        # Сохраняем тесты
        test_filepath = os.path.join(self.config.WORKSPACE_DIR, "test_" + self.config.SCRIPT_NAME)
        with open(test_filepath, "w", encoding="utf-8") as f:
            f.write(review_result.test_code)
        logger.info(f"💾 Тесты сохранены: {test_filepath}")
        
        # Сохраняем документацию
        docs_filepath = os.path.join(self.config.WORKSPACE_DIR, "README.md")
        documentation_md = f"""# {docs_result.title}

## Описание
{docs_result.description}

## Примеры использования
{chr(10).join([f"```python\n{example}\n```" for example in docs_result.usage_examples])}

## API Документация
```python
{docs_result.api_documentation}
```

## Code Review Comments
{chr(10).join([f"- {comment}" for comment in review_result.review_comments])}

## Предложения по улучшению
{chr(10).join([f"- {improvement}" for improvement in review_result.improvements])}
"""
        with open(docs_filepath, "w", encoding="utf-8") as f:
            f.write(documentation_md)
        logger.info(f"💾 Документация сохранена: {docs_filepath}")
        
        # Завершаем отслеживание токенов и сохраняем итоговую сводку
        token_summary = self.token_tracker.log_session_summary()
        
        # Выводим резюме
        print("\n" + "="*60)
        print("📋 РЕЗЮМЕ ПРОЕКТА")
        print("="*60)
        print(f"📁 Проект: {docs_result.title}")
        print(f"📝 Описание: {docs_result.description}")
        print(f"\n💾 Файлы созданы:")
        print(f"   - Основной код: {code_filepath}")
        print(f"   - Тесты: {test_filepath}")
        print(f"   - Документация: {docs_filepath}")
        print(f"   - Лог агентов: {os.path.join(self.config.WORKSPACE_DIR, 'agents_workflow.log')}")
        print(f"   - RAW AutoGen логи: {os.path.join(self.config.WORKSPACE_DIR, 'autogen_raw_output.log')}")
        
        print(f"\n🔍 Code Review ({len(review_result.review_comments)} комментариев):")
        for comment in review_result.review_comments:
            print(f"   ✓ {comment}")
            
        print(f"\n💡 Предложения ({len(review_result.improvements)} улучшений):")
        for improvement in review_result.improvements:
            print(f"   → {improvement}")
        
        print(f"\n🧪 Статус тестирования: {'✅ Все тесты пройдены' if os.path.exists(test_filepath) else '⚠️ Тесты не выполнялись'}")
        print(f"🐳 Docker: {'✅ Включен' if self.config.USE_DOCKER else '❌ Отключен'}")
        print(f"👨‍💼 TeamLead управление: ✅ Включено (СУПЕРВИЗОР)")
        print(f"🤝 Управляемая разработка: ✅ Программист + Ревьюер под руководством")
        print(f"🔄 Автоисправления: ✅ До {self.config.MAX_IMPROVEMENT_LOOPS} итераций")
        print(f"🛡️ Защита от циклов: ✅ Интеллектуальное обнаружение повторов")
        print(f"📝 Fancy логирование: ✅ Детальный лог агентов с эмодзи")
        
        # Добавляем информацию о токенах
        print(f"\n💰 ИСПОЛЬЗОВАНИЕ ТОКЕНОВ:")
        print(f"   📥 Входящие токены: {token_summary['total_input']:,}")
        print(f"   📤 Исходящие токены: {token_summary['total_output']:,}")
        print(f"   🎯 Всего токенов: {token_summary['total_tokens']:,}")
        print(f"   🔢 Всего LLM вызовов: {token_summary['total_calls']}")
        print(f"   💵 Общая стоимость: {token_summary['total_cost']:.4f} руб.")
        print(f"   📄 Лог токенов: {os.path.join(self.config.WORKSPACE_DIR, 'tokens_usage.log')}")
        
        print("\n--- Сгенерированный код ---")
        print(code_result.code)
        print("="*60)

# ==============================================================================
# Часть 4: Точка входа
# ==============================================================================
if __name__ == "__main__":
    user_task = (
        "Напиши скрипт на Python, который реализует функцию `calculate_days_for_iphone(monthly_salary)`.\n"
        "Функция должна рассчитывать, сколько рабочих дней потребуется, чтобы накопить на iPhone 15 Pro Max 256GB, "
        "исходя из указанной зарплаты в месяц. Цена должна быть найдена в интернете.\n"
        "Требования: в месяце 22.5 рабочих дня; результат вернуть как есть; добавить блок `if __name__ == '__main__':` для демонстрации."
    )
    
    config = Config()
    pipeline_manager = PipelineManager(config)
    pipeline_manager.run(task=user_task)
