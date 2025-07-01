import re
import pytz
import json
import logging
import calendar

from datetime import datetime
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from mcp.server.fastmcp import FastMCP, Context
from typing import Dict, Any, List, Optional, Tuple
from geopy.exc import GeocoderUnavailable, GeocoderTimedOut
from kerykeion import AstrologicalSubject, KerykeionChartSVG


_ASTROLOGY_INTERPRETATIONS_CACHE = None
PLOT_OUTPUT_DIR = '/Users/dmitriifrolov/Python/mcp/astrology_plots'

logger = logging.getLogger("natal_astrologer")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

geolocator = Nominatim(
    user_agent="natal_astrologer",
    timeout=10
)
tf = TimezoneFinder()
location_cache = {}

mcp = FastMCP(
    name="Натальный астролог",
    system_prompt="""
Ты — профессиональный астролог. Твоя задача — помогать пользователям понять себя и своё будущее с помощью астрологии и 
натальных карт.

Основные функции:
1. Составление натальной карты (требуются полные данные)
2. Прогнозирование астрологических влияний (требуются данные + текущая дата)
3. Анализ совместимости (требуются полные данные двух людей)
4. Интерпретация отдельных элементов (не требует данных пользователя)

Используй доступные инструменты:
- get_natal_chart_report: составление натальной карты
- get_astrological_forecast: прогноз на основе транзитов
- get_synastry_report: анализ совместимости двух людей
- get_astrology_interpretation: объяснение планет, домов, аспектов

Если необходимо получить интерпретацию информации, то можно обратиться к базе астрологических интерпретаций:
- load_astrology_interpretations

Всегда следуй этим правилам:
1. Для натальных карт, прогнозов и синастрии всегда запрашивай полные данные:
   - Имя
   - Точная дата рождения (день, месяц, год)
   - Точное время рождения (часы и минуты)
   - Город рождения
   
2. Для интерпретации элементов данные пользователя не требуются.

3. Если пользователь спрашивает о своем конкретном положении:
   - Сначала запроси его данные
   - Затем составь натальную карту
   - После этого дай интерпретацию нужного элемента

Примеры запросов:
[Основные функции]
- "Составь мою натальную карту. Я Иван, родился 15 марта 1991 года в 18:45 в Санкт-Петербурге."
- "Какой у меня астрологический прогноз на сегодня? Мои данные: Мария, 22.07.1988, 04:10, Новосибирск."
- "Проверь совместимость меня и моей партнерши. Я: Алексей, 10.05.1985, 14:30, Москва. Она: Екатерина, 03.11.1989, 09:15, Казань."

[Интерпретация]
- "Что значит Солнце в Скорпионе?" → общее объяснение
- "Объясни Луну в Раке" → общее объяснение
- "Интерпретация Меркурия в Близнецах" → общее объяснение
- "Что означает 5 дом?" → общее объяснение
- "Объясни трин аспект" → общее объяснение

Правила использования интерпретаций:
1. Всегда используй инструмент interpret_astrology_element для объяснений
2. Для личных трактовок сначала получай натальную карту
3. Примеры запросов:
   - interpret_astrology_element("planet_in_sign", "Солнце", "Скорпион")
   - interpret_astrology_element("house", "5", null)
   - interpret_astrology_element("aspect", "трин", null)

[Комбинированные запросы]
- "Что значит мое Солнце в Скорпионе? Я родился 15.03.1991 в 18:45 в СПб" → натальная карта + интерпретация
- "Объясни 5 дом в моей карте" → сначала запросить данные
- "Интерпретация Венеры в Весах в моей карте" → сначала запросить данные

Для точных результатов:
- Используй полные названия планет (Солнце, Луна, Венера и т.д.)
- Базовые названия знаков (Скорпион, а не Скорпиона)
- Номера домов (5, а не пятый)
- Основные аспекты (соединение, оппозиция и т.д.)
"""
)


def get_location_info(city: str) -> Optional[Dict]:
    """
    Получение координат и временной зоны по названию города.

    Args:
        city (str): город
    Returns:
        result (Optional[Dict]): словарь с данными о геолокации и часовой зоне, если город найден, в противном случае - 
            None
    """
    if city in location_cache:
        return location_cache[city]
    
    try:
        location = geolocator.geocode(
            city + ", Россия", 
            language="ru", 
            timeout=10
        )

        if not location:
            return None
                
        time_zone_name = tf.timezone_at(
            lng=location.longitude, 
            lat=location.latitude
        )

        if not time_zone_name:
            return None
            
        time_zone = pytz.timezone(time_zone_name)
        offset = time_zone.utcoffset(datetime.utcnow()).total_seconds() / 3600
        
        result = {
            "city": location.address.split(",")[0],
            "lat": location.latitude,
            "lng": location.longitude,
            "tz_str": time_zone_name,
            "utc_offset": offset
        }
        
        location_cache[city] = result

        return result
        
    except (GeocoderUnavailable, GeocoderTimedOut) as e:
        logger.error(f"Ошибка геокодирования: {str(e)}")

        return None

def validate_astrological_data(name: str, 
                               year: int, 
                               month: int, 
                               day: int, 
                               hour: int, 
                               minute: int, 
                               city: str) -> Optional[str]:
    """
    Валидация входных данных для астрологических расчетов.

    Args:
        name (str): имя пользователя
        year (int): год рождения
        month (int): месяц рождения
        day (int): день рождения
        hour (int): час рождения
        minute (int): минута рождения
        city (str): город, в котором родился пользователь
    Returns:
        (str): комментарий к ошибке, либо None, если все данные корректны
    """
    if not name or len(name) < 2:
        return "Имя должно содержать минимум 2 символа"
    
    current_year = datetime.now().year

    if year < 1900 or year > current_year:
        return f"Некорректный год рождения (должен быть между 1900 и {current_year})"
    
    if month < 1 or month > 12:
        return "Некорректный месяц рождения (1-12)"
    
    if day < 1 or day > calendar.monthrange(year, month)[1]:
        return "Некорректный день рождения (1-28/29/30/31)"
    
    if hour < 0 or hour > 23:
        return "Некорректный час рождения (0-23)"
    
    if minute < 0 or minute > 59:
        return "Некорректные минуты рождения (0-59)"
    
    try:
        location = get_location_info(
            city=city
        )

        if not location:
            return "Не удалось определить координаты для указанного города"
        
        time_zone = pytz.timezone(location["tz_str"])
        birth_date = time_zone.localize(datetime(year, month, day, hour, minute))

        if birth_date > datetime.now(time_zone):
            return "Дата рождения не может быть в будущем"
        
    except ValueError as ve:
        return f"Некорректная дата рождения: {str(ve)}"
    except Exception as e:
        return f"Ошибка при проверке даты: {str(e)}"
    
    return None

def get_aspect_emoji(aspect_type: str) -> str:
    """
    Возвращает эмодзи для типа аспекта, чтобы разбавить текст.

    Args:
        aspect_type (str): название аспекта
    Returns:
        (str): разноцветные эмодзи
    """
    return {
        "conjunction": "🟣",
        "opposition": "🔴",
        "square": "🔶",
        "trine": "🟢",
        "sextile": "🔵"
    }.get(aspect_type, "▪️")

def get_aspect_interpretation(aspect_type: str) -> str:
    """
    Интерпретация аспектов.

    Args:
        aspect_type (str): название аспекта
    Returns:
        (str): краткое трактование аспекта
    """
    interpretations = {
        "conjunction": "Мощное объединение энергий, новое начало",
        "opposition": "Противостояние, необходимость баланса",
        "square": "Вызов, напряжение, необходимость действия",
        "trine": "Гармония, поддержка, удачное стечение обстоятельств",
        "sextile": "Возможности, благоприятные обстоятельства"
    }
    
    return interpretations.get(aspect_type, "Нейтральное влияние")

def get_house_interpretation(house_number: str) -> str:
    """
    Интерпретация домов гороскопа.

    Args:
        house_number (str): номер дома прописью
    Returns:
        (str): краткое трактование дома
    """
    interpretations = {
        "First": "Личность, внешний образ, самовыражение",
        "Second": "Финансы, ценности, материальные ресурсы",
        "Third": "Общение, братья/сестры, короткие поездки",
        "Fourth": "Дом, семья, корни, недвижимость",
        "Fifth": "Творчество, дети, романы, удовольствия",
        "Sixth": "Работа, здоровье, рутина, служба",
        "Seventh": "Партнерство, брак, открытые враги",
        "Eighth": "Трансформация, наследство, чужие ресурсы",
        "Ninth": "Философия, путешествия, высшее образование",
        "Tenth": "Карьера, статус, общественное признание",
        "Eleventh": "Друзья, надежды, социальные группы",
        "Twelfth": "Тайны, подсознание, изоляция, карма"
    }

    return interpretations.get(house_number, "Неизвестный дом")

@mcp.tool(
    name="get_natal_chart_report",
    description="Создает и описывает натальную карту пользователя по его данным.",
    annotations={
        "title": "Генератор натальных карт",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
def get_natal_chart_report(context: Context, 
                           name: str, 
                           year: int, 
                           month: int, 
                           day: int, 
                           hour: int, 
                           minute: int, 
                           city: str) -> str:
    """
    Создает и описывает натальную карту пользователя.
    https://pypi.org/project/kerykeion/#description

    Args:
        context (Context): контекст выполнения действия
        name (str): имя пользователя
        year (int): год рождения
        month (int): месяц рождения
        day (int): день рождения
        hour (int): час рождения
        minute (int): минута рождения
        city (str): город, в котором родился пользователь
    Returns:
        report (str): натальная карта, построенная по данным пользователя
    """
    validation_error = validate_astrological_data(name, year, month, day, hour, minute, city)

    if validation_error:
        return json.dumps(
            {
                "error": validation_error
            }
        )
    
    location = get_location_info(
        city=city
    )

    if not location:
        return json.dumps(
            {
                "error": f"Не удалось определить координаты для города '{city}'"
            }
        )
    
    try:
        user = AstrologicalSubject(
            name=name, 
            year=year, 
            month=month, 
            day=day, 
            hour=hour, 
            minute=minute,
            city=city,
            lng=location["lng"],
            lat=location["lat"],
            tz_str=location["tz_str"]
        )
        
        sun_sign = user.sun["sign"]
        moon_sign = user.moon["sign"]
        rising_sign = user.first_house["sign"]
        
        planets_data = [
            ("Солнце", user.sun),
            ("Луна", user.moon),
            ("Меркурий", user.mercury),
            ("Венера", user.venus),
            ("Марс", user.mars),
            ("Юпитер", user.jupiter),
            ("Сатурн", user.saturn),
            ("Уран", user.uranus),
            ("Нептун", user.neptune),
            ("Плутон", user.pluto)
        ]
        
        planets_in_signs = [f"{name} в {data['sign']}" for name, data in planets_data]

        houses_report = []

        for house in user._houses_list:
            house_number = str(house.name.split('_')[0])
            houses_report.append(
                {
                    "house": house_number,
                    "quality": house.quality,
                    "element": house.element,
                    "sign": house.sign,
                    "sign_num": house.sign_num,
                    "position": house.position,
                    "interpretation": get_house_interpretation(house_number)
                }
            )

        birth_chart_svg = KerykeionChartSVG(
            first_obj=user,
            chart_type='Natal',
            new_output_directory=PLOT_OUTPUT_DIR
        )
        birth_chart_svg.makeSVG()
        
        report = {
            "name": user.name,
            "sun_sign": sun_sign,
            "moon_sign": moon_sign,
            "rising_sign": rising_sign,
            "planets_in_signs": planets_in_signs,
            "houses": houses_report,
            "birth_location": location,
            "utc_offset": location["utc_offset"]
        }

        return json.dumps(
            obj=report, 
            ensure_ascii=False, 
            indent=2
        )

    except Exception as e:
        logger.exception("Ошибка при расчете натальной карты")

        return json.dumps(
            {
                "error": f"Астрологическая ошибка: {str(e)}"
            }
        )
    
@mcp.tool(
    name="get_synastry_report",
    description="Сравнивает две натальные карты для анализа совместимости пары.",
    annotations={
        "title": "Анализатор совместимости",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
def get_synastry_report(context: Context,
                        name1: str, 
                        year1: int, 
                        month1: int, 
                        day1: int, 
                        hour1: int, 
                        minute1: int, 
                        city1: str,
                        name2: str, 
                        year2: int, 
                        month2: int, 
                        day2: int, 
                        hour2: int, 
                        minute2: int, 
                        city2: str) -> str:
    """
    Сравнение двух натальных карт на предмет совместимости.

    Args:
        context (Context): контекст выполнения действия
        name1 (str): имя первого пользователя
        year1 (int): год рождения первого пользователя
        month1 (int): месяц рождения первого пользователя
        day1 (int): день рождения первого пользователя
        hour1 (int): час рождения первого пользователя
        minute1 (int): минута рождения первого пользователя
        city1 (str): город, в котором родился первый пользователь
        name2 (str): имя второго пользователя
        year2 (int): год рождения второго пользователя
        month2 (int): месяц рождения второго пользователя
        day2 (int): день рождения второго пользователя
        hour2 (int): час рождения второго пользователя
        minute2 (int): минута рождения второго пользователя
        city2 (str): город, в котором родился второй пользователь
    Returns:
        (str): сравнение натальных карт двух пользователей в контексте совместимости
    """
    try:
        location1 = get_location_info(
            city=city1
        )

        if not location1:
            return json.dumps(
                {
                    "error": f"Не удалось определить координаты для города '{city1}'"
                }
            )
            
        location2 = get_location_info(
            city=city2
        )
        if not location2:
            return json.dumps(
                {
                    "error": f"Не удалось определить координаты для города '{city2}'"
                }
            )

        user1 = AstrologicalSubject(
            name=name1, 
            year=year1, 
            month=month1, 
            day=day1, 
            hour=hour1, 
            minute=minute1,
            city=city1,
            lng=location1["lng"],
            lat=location1["lat"],
            tz_str=location1["tz_str"]
        )

        user2 = AstrologicalSubject(
            name=name2, 
            year=year2, 
            month=month2, 
            day=day2, 
            hour=hour2, 
            minute=minute2,
            city=city2,
            lng=location2["lng"],
            lat=location2["lat"],
            tz_str=location2["tz_str"]
        )

        synastry = KerykeionChartSVG(
            first_obj=user1, 
            chart_type="Synastry", 
            second_obj=user2, 
            new_output_directory=PLOT_OUTPUT_DIR, 
            chart_language='RU'
        )
        synastry.makeSVG()

        aspects = synastry.aspects_list
        aspects_report = []

        for aspect in aspects:
            emoji = get_aspect_emoji(
                aspect_type=aspect['aspect']
            )
            aspect_desc = (
                f"{emoji} {aspect['p1_name']} ({name1}) → "
                f"{aspect['p2_name']} ({name2}): "
                f"{aspect['aspect']} (орб {aspect['orbit']:.2f}°)"
            )
            aspects_report.append(aspect_desc)

        report = {
            "person1": name1,
            "person2": name2,
            "aspects": aspects_report,
            "significant_aspects_count": len(aspects),
            "positive_aspects": sum(1 for a in aspects if a['aspect'] in ['trine', 'sextile']),
            "challenging_aspects": sum(1 for a in aspects if a['aspect'] in ['square', 'opposition'])
        }
                
        return json.dumps(
            obj=report, 
            ensure_ascii=False, 
            indent=2
        )
        
    except Exception as e:
        logger.exception("Ошибка при расчете синастрии")

        return json.dumps(
            {
                "error": f"Ошибка совместимости: {str(e)}"
            }
        )

@mcp.tool(
    name="get_astrological_forecast",
    description="Составляет астрологический прогноз (транзит) на основе текущих планетарных позиций.",
    annotations={
        "title": "Генератор астрологического прогноза (транзита)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
def get_astrological_forecast(context: Context, 
                              name: str, 
                              year: int, 
                              month: int, 
                              day: int, 
                              hour: int, 
                              minute: int, 
                              city: str) -> str:
    """
    Составление астрологического прогноза (транзита).

    Args:
        context (Context): контекст выполнения действия
        name (str): имя пользователя
        year (int): год рождения
        month (int): месяц рождения
        day (int): день рождения
        hour (int): час рождения
        minute (int): минута рождения
        city (str): город, в котором родился пользователь
    Returns:
        (str): астрологический прогноз (транзит)
    """
    validation_error = validate_astrological_data(name, year, month, day, hour, minute, city)

    if validation_error:
        return json.dumps(
            {
                "error": validation_error
            }
        )
    
    location = get_location_info(
        city=city
    )
    if not location:
        return json.dumps(
            {
                "error": f"Не удалось определить координаты для города '{city}'"
            }
        )
    
    try:
        natal_chart = AstrologicalSubject(
            name=name, 
            year=year, 
            month=month, 
            day=day, 
            hour=hour, 
            minute=minute,
            city=city,
            lng=location["lng"],
            lat=location["lat"],
            tz_str=location["tz_str"]
        )
        
        now = datetime.now()
        
        transit_chart = AstrologicalSubject(
            name="Transit", 
            year=now.year, 
            month=now.month, 
            day=now.day, 
            hour=now.hour, 
            minute=now.minute,
            lng=location["lng"],
            lat=location["lat"],
            tz_str=location["tz_str"],
            city=city
        )
        
        transit = KerykeionChartSVG(
            first_obj=natal_chart, 
            chart_type="Transit", 
            second_obj=transit_chart, 
            new_output_directory=PLOT_OUTPUT_DIR, 
            chart_language='RU'
        )
        transit.makeSVG()
        
        return json.dumps(
            {
                "name": natal_chart.name,
                "forecast_date": now.strftime("%Y-%m-%d %H:%M"),
            }, 
            ensure_ascii=False, 
            indent=2
        )
        
    except Exception as e:
        logger.exception("Ошибка при расчете транзита")

        return json.dumps(
            {
                "error": f"Ошибка транзита: {str(e)}"
            }
        )

def extract_personal_data(text: str) -> Tuple[Optional[str], Optional[int], Optional[int], Optional[int], Optional[int], Optional[int], Optional[str]]:
    """
    Извлекает данные одного человека из текста.

    Args:
        text (str): входные данные, полученные от пользователя
    Returns:
        Tuple[Optional[str], Optional[int], Optional[int], Optional[int], Optional[int], Optional[int], Optional[str]]:
            кортеж с извлеченной необходимой информацией при ее наличии
    """
    name_match = re.search(
        pattern=r"(?:меня зовут|я|пользователь|первый|второй|участник)\s*[:—]?\s*([А-Яа-яЁё]{2,}(?:\s[А-Яа-яЁё]{2,})?)", 
        string=text, 
        flags=re.IGNORECASE
    )
    name = name_match.group(1).strip() if name_match else None
    
    date_match = re.search(
        pattern=r"(\d{1,2})[.\s-]*(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря|\d{1,2})[.\s-]*(\d{4})", 
        string=text, 
        flags=re.IGNORECASE
    )

    if not date_match:
        return (name, None, None, None, None, None, None)
    
    day = int(date_match.group(1))
    month_str = date_match.group(2).lower()
    
    month_map = {
        'января': 1, 
        'февраля': 2, 
        'марта': 3, 
        'апреля': 4, 
        'мая': 5, 
        'июня': 6,
        'июля': 7, 
        'августа': 8, 
        'сентября': 9, 
        'октября': 10, 
        'ноября': 11, 
        'декабря': 12
    }
    
    month = month_map.get(month_str)

    if not month:
        try:
            month = int(month_str)
        except ValueError:
            return (name, None, None, None, None, None, None)
    
    year = int(date_match.group(3))
    
    time_match = re.search(
        pattern=r"(\d{1,2})[:ч\s.]*(\d{1,2})?\s*(?:часов|часа|час|утра|дня|вечера)?", 
        string=text, 
        flags=re.IGNORECASE
    )
    hour, minute = 0, 0

    if time_match:
        try:
            hour = int(time_match.group(1))

            if time_match.group(2):
                minute = int(time_match.group(2))

            if "вечера" in text.lower() and hour < 12:
                hour += 12
        except (TypeError, ValueError):
            pass
    
    city_match = re.search(
        pattern=r"(?:город|г\.|в)\s*[:—]?\s*([А-Яа-яЁё\s-]{3,})", 
        string=text, 
        flags=re.IGNORECASE
    )
    city = city_match.group(1).strip() if city_match else None
    
    return (name, year, month, day, hour, minute, city)

@mcp.resource(
    uri="resource://astrology/interpretations",
    name="astrology_interpretations",
    description="База астрологических интерпретаций с кэшированием",
    mime_type="application/json"
)
def load_astrology_interpretations() -> dict:
    """
    Загружает астрологические интерпретации из JSON-файла.
    
    Returns:
        data (dict): cловарь с интерпретациями астрологических элементов
    """
    global _ASTROLOGY_INTERPRETATIONS_CACHE

    if _ASTROLOGY_INTERPRETATIONS_CACHE:
        return _ASTROLOGY_INTERPRETATIONS_CACHE
    
    try:
        with open("astrology_resources/interpretations.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            _ASTROLOGY_INTERPRETATIONS_CACHE = data
            
            return data
    except Exception as e:
        logger.error(f"Ошибка загрузки интерпретаций: {str(e)}")

        return {}
    
@mcp.tool(
    name="interpret_astrology_element",
    description="Возвращает интерпретацию астрологического элемента (планеты, дома, аспекта) на основе справочника.",
    annotations={
        "title": "Интерпретатор астрологических элементов",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
def interpret_astrology_element(context: Context,
                                element_type: str,
                                element_name: str,
                                element_value: Optional[str] = None) -> str:
    """
    Возвращает интерпретацию астрологического элемента на основе справочника.
    
    Args:
        context (Context): контекст выполнения действия
        element_type (str): тип элемента (sun_sign, moon_sign, planet_in_sign, house, aspect)
        element_name (str): название элемента (планета/дом/аспект)
        element_value (Optional[str]): значение элемента (знак зодиака)
    Returns:
        str: Текстовое описание интерпретации элемента
    """
    interpretations = context.read_resource(
        uri="resource://astrology/interpretations"
    )
    
    if interpretations is None:
        return "Ресурс с астрологическими интерпретациями не загружен"
    
    sign_mapping = {
        "овен": "Aries", 
        "телец": "Taurus", 
        "близнецы": "Gemini",
        "рак": "Cancer", 
        "лев": "Leo", 
        "дева": "Virgo",
        "весы": "Libra", 
        "скорпион": "Scorpio", 
        "стрелец": "Sagittarius",
        "козерог": "Capricorn", 
        "водолей": "Aquarius", 
        "рыбы": "Pisces"
    }
    
    element_type = element_type.lower()
    element_name = element_name.strip().capitalize()
    
    if element_value:
        element_value = element_value.strip().lower()
        element_value_en = sign_mapping.get(element_value, element_value)
    
    try:
        if element_type == "sun_sign":
            data = interpretations.get("sun_sign", {}).get(element_value_en, {})
            symbol = interpretations.get("sign_symbols", {}).get(element_value_en, "")

            return f"{symbol} Солнце в {element_value}:\n\n{data.get('interpretation', 'Интерпретация не найдена')}"
        
        elif element_type == "moon_sign":
            data = interpretations.get("moon_sign", {}).get(element_value_en, {})
            symbol = interpretations.get("sign_symbols", {}).get(element_value_en, "")

            return f"{symbol} Луна в {element_value}:\n\n{data.get('interpretation', 'Интерпретация не найдена')}"
        
        elif element_type == "planet_in_sign":
            planet_data = interpretations.get("planets_in_signs", {}).get(element_name, {})
            data = planet_data.get(element_value_en, {})
            symbol = data.get("symbol", "")

            return f"{symbol} {element_name} в {element_value}:\n\n{data.get('interpretation', 'Интерпретация не найдена')}"
        
        elif element_type == "house":
            try:
                house_num = int(element_name)
                data = interpretations.get("houses", {}).get(str(house_num), {})

                return f"{data.get('symbol', '🏠')} {house_num} Дом:\n\n{data.get('interpretation', 'Интерпретация не найдена')}"
            except ValueError:
                return "Неверный номер дома. Должно быть число от 1 до 12"
        
        elif element_type == "aspect":
            aspect_data = interpretations.get("aspects", {}).get(element_name.lower(), {})
            return f"{aspect_data.get('symbol', '')} {element_name.capitalize()}:\n\n{aspect_data.get('interpretation', 'Интерпретация не найдена')}"
        
        return "Неизвестный тип элемента. Доступные типы: sun_sign, moon_sign, planet_in_sign, house, aspect"
    
    except Exception as e:
        logger.error(f"Ошибка интерпретации: {str(e)}")

        return "Произошла ошибка при обработке запроса. Проверьте параметры."

@mcp.prompt(
    name="handle_astrology_query",
    description="Обрабатывает астрологические запросы пользователя, определяет нужные инструменты и возвращает структурированный ответ"
)
def handle_astrology_query(prompt: str, 
                           context: Context) -> List[Dict[str, Any]]:
    """
    Обрабатывает астрологические запросы пользователя и определяет нужные инструменты.
    
    Args:
        prompt (str): запрос пользователя
        context (Context): контекст выполнения действия
    Returns:
        List[Dict[str, Any]]: список сообщений для обработки запроса
    """
    try:
        prompt_lower = prompt.lower()

        interpretation_patterns = [
            (r"(что значит|объясни|интерпретация) (солнц[а-я]+) в ([а-я]+)", "planet_in_sign", "Солнце", 3),
            (r"(что значит|объясни|интерпретация) (лун[а-я]+) в ([а-я]+)", "planet_in_sign", "Луна", 3),
            (r"(что значит|объясни|интерпретация) (асцендент[а-я]*) в ([а-я]+)", "rising_sign", "Асцендент", 3),
            (r"(что значит|объясни|интерпретация) (меркури[я-я]+) в ([а-я]+)", "planet_in_sign", "Меркурий", 3),
            (r"(что значит|объясни|интерпретация) (венер[а-я]+) в ([а-я]+)", "planet_in_sign", "Венера", 3),
            (r"(что значит|объясни|интерпретация) (марс[а-я]*) в ([а-я]+)", "planet_in_sign", "Марс", 3),
            (r"(что значит|объясни|интерпретация) (юпитер[а-я]*) в ([а-я]+)", "planet_in_sign", "Юпитер", 3),
            (r"(что значит|объясни|интерпретация) (сатурн[а-я]*) в ([а-я]+)", "planet_in_sign", "Сатурн", 3),
            (r"(что значит|объясни|интерпретация) (уран[а-я]*) в ([а-я]+)", "planet_in_sign", "Уран", 3),
            (r"(что значит|объясни|интерпретация) (нептун[а-я]*) в ([а-я]+)", "planet_in_sign", "Нептун", 3),
            (r"(что значит|объясни|интерпретация) (плутон[а-я]*) в ([а-я]+)", "planet_in_sign", "Плутон", 3),
            (r"(что значит|объясни|интерпретация) (\d{1,2}) дом[а-я]*", "house", None, 2),
            (r"(что такое|объясни) (соединение|оппозиция|квадратура?|трин|секстиль)", "aspect", None, 2),
        ]
        
        for pattern, element_type, default_name, value_idx in interpretation_patterns:
            match = re.search(
                pattern=pattern, 
                string=prompt_lower, 
                flags=re.IGNORECASE
            )

            if match:
                element_name = default_name if default_name else match.group(value_idx)
                element_value = match.group(value_idx) if element_type != "house" else None
                
                return [
                    {
                        "role": "tool",
                        "name": "interpret_astrology_element",
                        "arguments": {
                            "element_type": element_type,
                            "element_name": element_name,
                            "element_value": element_value
                        }
                    }
                ]
        
        if "совмест" in prompt_lower or "синaстр" in prompt_lower or "пара" in prompt_lower:
            parts = re.split(
                pattern=r" и |;|,| а также | а у | а для ", 
                string=prompt, 
                flags=re.IGNORECASE
            )
            if len(parts) < 2:
                return [
                    {
                        "role": "assistant", 
                        "content": "Для анализа совместимости укажите данные двух людей. Например: "
                                    "'Проверьте совместимость меня и партнера. Я: Имя, дата, время, город. Партнер: Имя, дата, время, город.'"
                    }
                ]
            
            data1 = extract_personal_data(parts[0])
            data2 = extract_personal_data(parts[1]) if len(parts) > 1 else (None, None, None, None, None, None, None)
            
            missing1 = [field for field, value in zip(["имя", "год", "месяц", "день", "час", "минуты", "город"], data1) if not value]
            missing2 = [field for field, value in zip(["имя", "год", "месяц", "день", "час", "минуты", "город"], data2) if not value]
            
            if missing1 or missing2:
                response = "Для анализа совместимости мне нужны полные данные двух людей:\n"

                if missing1:
                    response += f"\n- Для первого человека не хватает: {', '.join(missing1)}"
                if missing2:
                    response += f"\n- Для второго человека не хватает: {', '.join(missing2)}"

                return [
                    {
                        "role": "assistant", 
                        "content": response
                    }
                ]
            
            name1, year1, month1, day1, hour1, minute1, city1 = data1
            name2, year2, month2, day2, hour2, minute2, city2 = data2
            
            result_json = get_synastry_report(
                context=context,
                name1=name1, 
                year1=year1, 
                month1=month1, 
                day1=day1, 
                hour1=hour1, 
                minute1=minute1, 
                city1=city1,
                name2=name2, 
                year2=year2, 
                month2=month2, 
                day2=day2, 
                hour2=hour2, 
                minute2=minute2, 
                city2=city2
            )
            
            data = json.loads(result_json)
            
            if "error" in data:
                return [
                    {
                        "role": "assistant", 
                        "content": f"⚠️ Ошибка: {data['error']}"
                    }
                ]
            
            response = f"## 🔮 Совместимость {name1} и {name2}\n\n"
            response += f"**Оценка совместимости:** {data['compatibility_score']}%\n"
            response += f"**Значимых аспектов:** {data['significant_aspects_count']} "
            response += f"(🟢 благоприятных: {data['positive_aspects']}, "
            response += f"🔶 напряженных: {data['challenging_aspects']})\n\n"
            response += "### Основные аспекты:\n"

            for aspect in data['aspects']:
                response += f"- {aspect}\n"
            
            response += "\n_Это общий анализ. Для детальной интерпретации рекомендуется консультация с профессиональным астрологом._"
            
            return [
                {
                    "role": "assistant", 
                    "content": response
                }
            ]
            
        else:
            name, year, month, day, hour, minute, city = extract_personal_data(
                text=prompt
            )
            missing = []

            if not name: 
                missing.append("имя")

            if not year: 
                missing.append("год рождения")

            if not month: 
                missing.append("месяц рождения")

            if not day: 
                missing.append("день рождения")

            if hour is None: 
                missing.append("час рождения")

            if minute is None: 
                missing.append("минуты рождения")

            if not city: 
                missing.append("город рождения")
            
            if missing:
                return [
                    {
                        "role": "assistant", 
                        "content": f"Для составления вашей натальной карты мне нужны: {', '.join(missing)}. " 
                                "Пожалуйста, укажите имя, полную дату рождения (например, '15 марта 1990'), "
                                "точное время рождения (например, '18:45') и город рождения."
                    }
                ]
            
            if any(word in prompt_lower for word in ["прогноз", "предсказание", "будущее", "транзит"]):
                tool_to_call = get_astrological_forecast
                response_title = f"✨ Астрологический прогноз для {name}"
            else:
                tool_to_call = get_natal_chart_report
                response_title = f"🪐 Натальная карта для {name}"
            
            result_json = tool_to_call(
                context, 
                name=name, 
                year=year, 
                month=month, 
                day=day, 
                hour=hour, 
                minute=minute, 
                city=city
            )
            
            data = json.loads(result_json)
            
            if "error" in data:
                return [
                    {
                        "role": "assistant", 
                        "content": f"⚠️ Ошибка: {data['error']}"
                    }
                ]
            elif "info" in data:
                return [
                    {
                        "role": "assistant", 
                        "content": f"ℹ️ {data['info']}"
                    }
                ]
            
            response = f"## {response_title}\n\n"
            response += f"**Дата рождения:** {day}.{month}.{year} в {hour}:{minute:02d}\n"
            response += f"**Место рождения:** {data.get('birth_location', {}).get('city', city)}\n\n"
            
            if tool_to_call == get_natal_chart_report:
                response += "### Основные показатели:\n"
                response += f"- ☀️ Солнце в {data['sun_sign']}: Ядро личности, жизненная энергия\n"
                response += f"- 🌙 Луна в {data['moon_sign']}: Эмоции, подсознание, внутренний мир\n"
                response += f"- 🌅 Асцендент в {data['rising_sign']}: Внешнее проявление, первое впечатление\n\n"
                response += "### Планеты в знаках:\n"

                for planet in data['planets_in_signs']:
                    response += f"- {planet}\n"
                
                response += "\n_Для интерпретации конкретных аспектов запросите подробный анализ._"
            
            else:
                response += f"**Прогноз на:** {data['forecast_date']}\n\n"
                
                if not data.get('transits'):
                    response += "Сейчас нет значимых астрологических влияний. Это время стабильности и планомерного развития."
                else:
                    response += "### Текущие транзиты:\n"

                    for transit in data['transits']:
                        response += f"- **{transit['aspect']}** (орб {transit['orbit']:.2f}°)\n"
                        response += f"  {transit['influence']}\n"
                
                response += "\n_Прогноз показывает общие тенденции. Для персональной интерпретации необходим индивидуальный анализ._"
            
            return [
                {
                    "role": "assistant", 
                    "content": response
                }
            ]
    
    except Exception as e:
        logger.exception("Необработанная ошибка в обработчике запроса")
        return [
            {
                "role": "assistant",
                "content": "⚠️ Произошла непредвиденная ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже."
            }
        ]
    

if __name__ == "__main__":
    mcp.run(transport="stdio")