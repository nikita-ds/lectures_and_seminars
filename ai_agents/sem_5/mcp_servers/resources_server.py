import json
import logging

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from mcp.server.fastmcp import FastMCP, Context


logger = logging.getLogger("social_analyst")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


mcp = FastMCP(
    name="Аналитик соцсетей",
    instructions="""
Ты аналитик социальных медиа с доступом к базе постов из различных каналов.
Используй инструменты:
- search_posts: для поиска конкретных постов по критериям
- analyze_activity: для анализа активности источников

Особенности данных:
- Данные обновляются ежедневно
- Каждый пост содержит: источник, заголовок, описание, дату публикации и ссылку
- Основные источники: 'Data канальи Никиты Зелинского'

Примеры запросов пользователей:
- "Что писали про языковые модели за последние 3 дня?"
- "Покажи посты 'Модели Vikhr' за май"
- "Какие были новости про бенчмарки?"
- "Самые активные каналы на прошлой неделе"
"""
)

def parse_date(date_str: str) -> Optional[datetime]:
    """
    Парсинг даты из различных форматов.
    """
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d"
    ]

    for format in formats:
        try:
            return datetime.strptime(date_str, format)
        except ValueError:
            continue

    return None

@mcp.resource(
    uri="file://tg_data/news.json", 
    name="social_posts",
    description="Данные из социальных сетей",
    mime_type="application/json"
)
def load_posts_data() -> List[Dict[str, Any]]:
    """
    Загрузка и предобработка данных о постах.
    Преобразует Unix timestamp в datetime и приводит поля к ожидаемому формату.
    """
    path = "tg_data/news.json"
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        
        processed_data = []

        for item in raw_data:
            try:
                published_date = datetime.fromtimestamp(item['date'])
            except (ValueError, TypeError, KeyError):

                logger.warning(f"Некорректная дата в записи: {item.get('date')}")
                continue

            text = item.get("text", "")
 
            post = {
                "source": item.get("channel", "unknown"),
                "title": (text[:50] + "...") if len(text) > 50 else text,
                "description": item.get("text", ""),
                "published_date": published_date,
                "link": item.get("link", ""),
            }
            processed_data.append(post)
        
        logger.info(f"Загружено и обработано {len(processed_data)} постов")

        return processed_data

    except Exception as e:
        logger.error(f"Ошибка загрузки данных: {str(e)}")

        return []

@mcp.tool()
async def search_posts(
    context: Context,
    sources: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    limit: int = 5
) -> str:
    """
    Поиск постов в социальных сетях по заданным критериям
    """
    posts = await context.read_resource(uri="file://tg_data/news.json")
    
    if not posts:
        return "База постов не загружена"
    
    filtered_posts = []
    
    start_dt = parse_date(start_date) if start_date else None
    end_dt = parse_date(end_date) if end_date else None
    
    for post in posts:
        post_dt = post.get("published_date")
        
        if sources and post.get("source") not in sources:
            continue
            
        if post_dt:
            if start_dt and post_dt < start_dt:
                continue
            if end_dt and post_dt > end_dt:
                continue
        else:
            continue
                
        if keywords:
            content = f"{post.get('title', '')} {post.get('description', '')}".lower()

            if not any(kw.lower() in content for kw in keywords if kw):
                continue
        
        filtered_post = {
            "source": post.get("source"),
            "title": post.get("title"),
            "published_date": post_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "link": post.get("link")
        }
        filtered_posts.append(filtered_post)
        
        if len(filtered_posts) >= limit:
            break
            
    if not filtered_posts:
        return "По заданным критериям посты не найдены"
        
    return json.dumps(filtered_posts, ensure_ascii=False, indent=2)

@mcp.tool()
async def analyze_activity(
    context: Context,
    period_days: int = 7,
    top_sources: int = 5
) -> str:
    """
    Анализ активности по источникам за указанный период
    """
    posts = await context.read_resource(uri="file://tg_data/news.json")

    if not posts:
        return "База постов не загружена"
    
    cutoff_date = datetime.now() - timedelta(days=period_days)
    source_counts = defaultdict(int)
    
    for post in posts:
        post_dt = post.get("published_date")

        if not post_dt or post_dt < cutoff_date:
            continue
            
        source_counts[post.get("source")] += 1
    
    sorted_sources = sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:top_sources]
    
    result = {
        "period": f"Последние {period_days} дней",
        "total_posts": sum(source_counts.values()),
        "top_sources": [
            {
                "source": source, 
                "posts": count
            } 
            for source, count in sorted_sources
        ]
    }
    
    return json.dumps(result, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")