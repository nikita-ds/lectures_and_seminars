import os
import json
import arxiv

from typing import List, Dict
from mcp.server.fastmcp import FastMCP


PAPER_DIR = "papers"
os.makedirs(
    name=PAPER_DIR, 
    exist_ok=True
)

mcp = FastMCP(
    name="llm_research",
    system_prompt = """
    Ты - помощник для анализа научных статей по LLM и Computer Science. 
    Используй инструменты для поиска и анализа статей. 
    Отвечай на русском языке.
    """
)


@mcp.tool()
def search_papers(topic: str, 
                  max_results: int = 10) -> List[str]:
    """
    Поиск свежих статей на arXiv по теме LLM и Computer Science.
    
    Args:
        topic (str): тема для поиска
        max_results (int): максимальное количество результатов (по умолчанию: 10)
    Returns:
        paper_ids (List[str]): список id найденных статей
    """
    client = arxiv.Client()
    
    filtered_query = f"{topic} AND (cat:cs.* OR cat:cs.CL)"
    
    search = arxiv.Search(
        query=filtered_query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )
    
    papers = list(client.results(search))
    
    topic_dir = topic.lower().replace(" ", "_")
    path = os.path.join(PAPER_DIR, topic_dir)
    os.makedirs(path, exist_ok=True)
    
    file_path = os.path.join(path, "papers.json")
    
    try:
        with open(file_path, "r") as f:
            papers_info = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        papers_info = {}
    
    paper_ids = []

    for paper in papers:
        paper_id = paper.get_short_id()
        paper_ids.append(paper_id)
        
        if paper_id not in papers_info:
            papers_info[paper_id] = {
                'title': paper.title,
                'authors': [author.name for author in paper.authors],
                'summary': paper.summary,
                'pdf_url': paper.pdf_url,
                'published': str(paper.published.date()),
                'primary_category': paper.primary_category,
                'categories': paper.categories,
                'comment': paper.comment,
                'links': [link.href for link in paper.links]
            }
    
    with open(file_path, "w") as f:
        json.dump(papers_info, f, indent=2)
    
    print(f"Найдено {len(papers)} статей по теме '{topic}'")

    return paper_ids

@mcp.tool()
def get_paper_details(paper_id: str) -> str:
    """
    Получение доп. информации из статьи по её id.
    
    Args:
        paper_id (str): id статьи
    Returns:
        (str): JSON с деталями статьи или сообщение об ошибке
    """
    for topic_dir in os.listdir(PAPER_DIR):
        topic_path = os.path.join(PAPER_DIR, topic_dir)

        if os.path.isdir(topic_path):
            file_path = os.path.join(topic_path, "papers.json")

            if os.path.exists(file_path):
                try:
                    with open(file_path, "r") as f:
                        papers = json.load(f)

                        if paper_id in papers:
                            return json.dumps(papers[paper_id], indent=2)
                except Exception as e:
                    print(f"Ошибка чтения {file_path}: {str(e)}")
    
    return f"Статья с ID {paper_id} не найдена"

@mcp.tool()
def analyze_trends(topics: List[str], 
                   years: List[int] = [2020, 2021, 2022, 2023, 2024, 2025]) -> Dict[str, Dict]:
    """
    Анализ трендов по нескольким темам за указанные годы.
    
    Args:
        topics (List[str]): список тем для анализа
        years ((List[int])): годы для анализа (по умолчанию: [2020, 2021, 2022, 2023, 2024, 2025])
    Returns:
        trends (Dict[str, Dict]): словарь с количеством публикаций по темам и годам
    """
    trends = {
        topic: {year: 0 for year in years} for topic in topics
    }
    
    for topic in topics:
        topic_dir = topic.lower().replace(" ", "_")
        file_path = os.path.join(PAPER_DIR, topic_dir, "papers.json")
        
        if os.path.exists(file_path):
            try:
                with open(file_path, "r") as f:
                    papers = json.load(f)

                    for _, details in papers.items():
                        pub_year = int(details['published'].split('-')[0])

                        if pub_year in years:
                            trends[topic][pub_year] += 1
            except Exception as e:
                print(f"Ошибка анализа трендов для {topic}: {str(e)}")
    
    return trends

@mcp.tool()
def find_related_papers(paper_id: str) -> List[str]:
    """
    Найти похожие статьи по id исходной статьи.
    
    Args:
        paper_id (str): id исходной статьи
    Returns:
        related_papers (List[str]): список id похожих статей
    """
    paper_details = {}
    
    for topic_dir in os.listdir(PAPER_DIR):
        topic_path = os.path.join(PAPER_DIR, topic_dir)
        file_path = os.path.join(topic_path, "papers.json")

        if os.path.exists(file_path):
            try:
                with open(file_path, "r") as f:
                    papers = json.load(f)

                    if paper_id in papers:
                        paper_details = papers[paper_id]
            except:
                continue
    
    if not paper_details:
        return []
    
    keywords = set(paper_details['title'].lower().split()[:5])
    related_papers = []

    for topic_dir in os.listdir(PAPER_DIR):
        topic_path = os.path.join(PAPER_DIR, topic_dir)
        file_path = os.path.join(topic_path, "papers.json")
        
        if os.path.exists(file_path):
            try:
                with open(file_path, "r") as f:
                    papers = json.load(f)

                    for pid, details in papers.items():
                        if pid == paper_id:
                            continue
                            
                        title_words = set(details['title'].lower().split())

                        if keywords & title_words:
                            related_papers.append(pid)
            except:
                continue
    
    return related_papers[:10]

@mcp.resource("papers://topics")
def list_research_topics() -> str:
    """
    Список доступных тем исследований.

    Returns:
        content (str): список доступных тем
    """
    topics = []

    for item in os.listdir(PAPER_DIR):
        item_path = os.path.join(PAPER_DIR, item)

        if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, "papers.json")):
            topics.append(item.replace("_", " ").title())
    
    content = "## Доступные темы исследований\n\n"

    if topics:
        content += "\n".join(f"- {topic}" for topic in topics)
        content += "\n\nИспользуйте @topic для доступа к статьям по теме"
    else:
        content += "Пока нет сохраненных тем. Используйте search_papers для поиска статей."
    
    return content

@mcp.resource("papers://{topic}/recent")
def get_recent_papers(topic: str) -> str:
    """
    Получить последние статьи по теме.

    Args:
        topic (str): тема статьи
    Returns:
        content (str): послдение статьи по данной тематике
    """
    topic_dir = topic.lower().replace(" ", "_")
    file_path = os.path.join(PAPER_DIR, topic_dir, "papers.json")
    
    if not os.path.exists(file_path):
        return f"Статьи по теме '{topic}' не найдены\n\nИспользуйте search_papers для поиска."
    
    try:
        with open(file_path, "r") as f:
            papers = json.load(f)
        
        sorted_papers = sorted(
            papers.items(),
            key=lambda x: x[1]['published'],
            reverse=True
        )[:5]
        
        content = f"## Последние статьи по теме: {topic.replace('_', ' ').title()}\n\n"
        
        for paper_id, details in sorted_papers:
            content += f"### {details['title']}\n"
            content += f"- **ID**: {paper_id}\n"
            content += f"- **Авторы**: {', '.join(details['authors'][:3])}{' и др.' if len(details['authors']) > 3 else ''}\n"
            content += f"- **Опубликовано**: {details['published']}\n"
            content += f"- **Категории**: {', '.join(details['categories'])}\n"
            content += f"- **Аннотация**: {details['summary'][:200]}...\n\n"
            content += "---\n\n"
        
        return content
    except Exception as e:
        return f"Ошибка при чтении статей: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport='stdio')