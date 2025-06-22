import re
import html
import pandas as pd

from datetime import datetime, timedelta


EMOJI_PATTERN = re.compile(
	"["
	u"\U0001F600-\U0001F64F"  # смайлики
	u"\U0001F300-\U0001F5FF"  # символы и пиктограммы 
	u"\U0001F680-\U0001F6FF"  # знаки, карты, транспорт
	u"\U0001F1E0-\U0001F1FF"  # флаги (iOS)
	u"\U00002500-\U00002BEF"  # китайские иероглифы
	u"\U0001F700-\U0001F77F"  # алхимические символы
	u"\U0001F780-\U0001F7FF"  # геометрические фигуры
	u"\U0001F800-\U0001F8FF"  # доп. стрелки
	u"\U0001F900-\U0001F9FF"  # доп. символы и пиктограммы 
	u"\U0001FA00-\U0001FA6F"  # шахматные символы
	u"\U0001FA70-\U0001FAFF"  # еще символы и пиктограммы
	u"\U00002702-\U000027B0"  # глифы
	u"\U000024C2-\U0001F251"
	"]+",
	flags = re.UNICODE
)

def remove_prefix(text: str, 
                  prefix: str = 'Forwarded From ') -> str:
    """
    Удаление следов репоста из текста.

    Args:
        text (str): текст, содержащий информацию о пересылке
        prefix (str) по которому осущеставляется поиск
    Returns:
        (str): обработанный текст без следов репоста
    """
    return text[len(prefix):] if text.startswith(prefix) else text

def convert_tg_date(date: str,
                    offset: int = 3) -> str:
    """
    Конвертация даты из Telegram для дальнейшего применения фильтров.

    Args:
        date (str): дата в сыром виде
    Returns:
        (str): конвертированная дата
    """
    return (datetime.strptime(date, '%a, %d %b %Y %H:%M:%S %Z') + timedelta(hours = offset)).strftime('%Y-%m-%d %H:%M:%S')

def tg_preprocessing(tg_data: list,
                     date_from: str = None,
                     date_to: str = None) -> pd.DataFrame:
        """
        Обработка новостей и фильтрация по дате публикации (концы включаются).

        Args:
            tg_date (list) - спаршенные новости
            date_from (str) - дата, начиная с которой необходимо отфильтровать
            date_to (str) - дата, заканчивая которой необходимо отфильтровать
        Returns:
            (pd.DataFrame) - новости за указанный временной интервал с очищенными заголовками и описанием (при наличии)
        """
        news = pd.DataFrame(tg_data)

        news['published_date'] = news['published_date'].apply(lambda x: convert_tg_date(x))
        news['description'] = news['description'].apply(lambda x: clean_tg_text(x))

        if date_from and date_to:
            news = news[(news['published_date'] >= date_from) & (news['published_date'] <= date_to)]
        elif date_from and not date_to:
            news = news[news['published_date'] >= date_from]
        elif not date_from and date_to:
            news = news[news['published_date'] <= date_to]
        
        news['description'] = news['description'].apply(remove_prefix)

        return news.reset_index(drop=True)

def clean_tg_text(text: str) -> str:
    """
    Декодирование html-сущностей, удаление html-тегов.
    Очистка текста от специальных символов html, unicode, неразрывных пробелов, смайлов и прочих ненужных символов.

    Args:
        text (str): - сырой текст
    Returns:
        text (str): - обработанный текст
    """
    text = html.unescape(text)
    text = re.sub('<.*?>', '', text)
    text = text.replace('&nbsp;', ' ')
    text = re.sub(r'[«»\u200e]', '', text)
    text = re.sub(r'[^\w\s.,:%-]', '', text)
    text = re.sub(r'\xa0', ' ', text)
    text = re.sub('\s+', ' ', text).strip()
    text = EMOJI_PATTERN.sub('', text)

    return text
