import os
import re
import json
import logging
import pandas as pd

from dotenv import load_dotenv
from binance.client import Client
from ta.trend import SMAIndicator
from ta.momentum import RSIIndicator
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any, List
from mcp.server.fastmcp import FastMCP, Context


logger = logging.getLogger("binance_mcp")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
load_dotenv("config.env")


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[Dict]:
    """
    Контекст жизненного цикла MCP сервера.
    
    Устанавливает и закрывает соединение с Binance API:
    - получает API ключи из переменных окружения
    - инициализирует клиент Binance для тестовой сети
    - предоставляет клиент через контекст инструментам
    
    Yields:
        (AsyncIterator[Dict]): cловарь контекста с клиентом Binance под ключом 'client'
    """
    client = None

    try:
        api_key = os.getenv("testnet_api_key")
        secret_key = os.getenv("testnet_secret_key")

        if not api_key or not secret_key:
            logger.error("API keys not found in environment variables")

            yield {
                "client": None
            }

            return
            
        client = Client(
            api_key=api_key,
            api_secret=secret_key,
            testnet=True,
            tld="com"
        )
        logger.info("Connected to Binance Testnet")

        yield {
            "client": client
        }
    except Exception as e:
        logger.error(f"Connection error: {e}")
        yield {
            "client": None
        }
    finally:
        if client:
            logger.info("Closing Binance connection")

mcp = FastMCP(
    name="BinanceMCP", 
    lifespan=lifespan
)

@mcp.tool()
def get_balance(asset: str, 
                context: Context) -> str:
    """
    Получение баланса указанного актива.
    
    Args:
        asset (str): код актива (BTC, ETH ...)
        context (Context): контекст выполнения действий с клиентом Binance
    Returns:
        (str): JSON-строка с балансом или сообщение об ошибке
    """
    client: Client = context.request_context.lifespan_context.get("client")

    if not client:
        return "Error: No connection to Binance"
    try:
        balance = client.get_asset_balance(
            asset=asset
        )

        return json.dumps(balance)
    except Exception as e:
        context.logger.error(f"Balance error: {str(e)}")

        return f"Error: {str(e)}"

@mcp.tool()
def get_klines(symbol: str, 
               interval: str, 
               limit: int, 
               context: Context) -> str:
    """
    Получение исторических данных (свечей).
    
    Args:
        symbol (str): nорговая пара (BTCUSDT, ETHUSDT)
        interval (str): таймфрейм (1m, 5m, 1h, 1d)
        limit (int): количество свечей (1-1000)
        context (Context): контекст выполнения действий
    Returns:
        (str): JSON-строка с массивом свечей:
            [timestamp, open, high, low, close, volume, ...]
    """
    client: Client = context.request_context.lifespan_context.get("client")

    if not client:
        return "Error: No connection to Binance"
    try:
        klines = client.get_klines(
            symbol=symbol, 
            interval=interval, 
            limit=limit
        )

        return json.dumps(klines)
    except Exception as e:
        context.logger.error(f"Klines error: {str(e)}")

        return f"Error: {str(e)}"

@mcp.tool()
def place_order(symbol: str, 
                side: str,
                quantity: float, 
                context: Context) -> str:
    """
    Размещение заказа.
    
    Args:
        symbol (str): торговая пара
        side (str): направление (BUY/SELL)
        quantity (float): количество активов
        context (Context): контекст выполнения действия
    Returns:
        (str): JSON-строка с результатом заказа или ошибкой
    """
    client: Client = context.request_context.lifespan_context.get("client")

    if not client:
        return "Error: No connection to Binance"
    try:
        order = client.create_order(
            symbol=symbol,
            side=side.upper(),
            type='MARKET',
            quantity=quantity
        )
        context.logger.info(f"Order executed: {order}")

        return json.dumps(order)
    except Exception as e:
        context.logger.error(f"Order error: {str(e)}")

        return f"Error: {str(e)}"

@mcp.tool()
def calculate_indicators(symbol: str, 
                         interval: str, 
                         limit: int = 100, 
                         context: Context = None) -> str:
    """
    Расчет технических индикаторов и генерация сигнала.
    
    Логика сигналов:
    - Buy: цена > SMA(20) и RSI(14) < 30
    - Sell: цена < SMA(20) и RSI(14) > 70
    - Hold: во всех остальных случаях
    
    Args:
        symbol (str): торговая пара
        interval (str): таймфрейм
        limit (int): количество свечей для анализа
        context (Context): контекст выполнения действия
    Returns:
        (str): JSON-строка с показателями:
            {
                "price": текущая цена,
                "sma_20": значение SMA,
                "rsi_14": значение RSI,
                "signal": торговый сигнал
            }
    """
    raw_data = get_klines(symbol, interval, limit, context)

    if "Error" in raw_data:
        return raw_data
    
    try:
        klines = json.loads(raw_data)
        data = pd.DataFrame(
            data=klines, 
            columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume','close_time', 'quote_asset_volume', 
                'number_of_trades', 'taker_buy_base_volume', 'taker_buy_quote_volume', 'ignore'
            ]
        )
        numeric_cols = [
            'open', 'high', 'low', 'close', 'volume'
        ]

        data[numeric_cols] = data[numeric_cols].apply(pd.to_numeric)
        data['timestamp'] = pd.to_datetime(
            data=['timestamp'], 
            unit='ms'
        )
        
        data['sma_20'] = SMAIndicator(
            close=data['close'], 
            window=20
        ).sma_indicator()
        data['rsi_14'] = RSIIndicator(
            close=data['close'], 
            window=14
        ).rsi()

        latest = data.iloc[-1]
        signal = "Hold"

        if latest['close'] > latest['sma_20'] and latest['rsi_14'] < 30:
            signal = "Buy (Oversold, price above SMA)"
        elif latest['close'] < latest['sma_20'] and latest['rsi_14'] > 70:
            signal = "Sell (Overbought, price below SMA)"

        return json.dumps(
            {
                "price": latest['close'],
                "sma_20": latest['sma_20'],
                "rsi_14": latest['rsi_14'],
                "signal": signal
            }
        )
    except Exception as e:
        return f"Data processing error: {str(e)}"

@mcp.prompt()
def execute_strategy(prompt: str, 
                     context: Context) -> List[Dict[str, Any]]:
    """
    Обработчик команд на выполнение торговых операций. 
    
    Распознает типовые команды вида:
    - "купить 0.5 BTC"
    - "продать 10 ETH"
    
    Args:
        prompt (str): входной промпт пользователя
        context (Context): контекст выполнения действия
    Returns:
        (List[Dict]): список сообщений в формате MCP
    """
    buy_match = re.search(r"(купить|buy)\s+(\d+\.?\d*)\s+(\w+)", prompt, re.IGNORECASE)
    sell_match = re.search(r"(продать|sell)\s+(\d+\.?\d*)\s+(\w+)", prompt, re.IGNORECASE)
    
    if buy_match:
        _, quantiy, symbol = buy_match.groups()
        order = place_order(
            symbol=symbol, 
            side="BUY", 
            quantiy=float(quantiy), 
            context=context
        )

        return [
            {
                "role": "assistant", 
                "content": f"Buy order executed: {order}"
            }
        ]
        
    elif sell_match:
        _, quantiy, symbol = sell_match.groups()
        order = place_order(
            symbol=symbol, 
            side="SELL", 
            quantiy=float(quantiy), 
            context=context
        )
        
        return [
            {
                "role": "assistant", 
                "content": f"Sell order executed: {order}"
            }
        ]
        
    return [
        {
            "role": "assistant", 
            "content": "Command not recognized"
        }
    ]

@mcp.prompt()
def analyze_signal(prompt: str, 
                   context: Context) -> List[Dict[str, Any]]:
    """
    Обработчик запросов на анализ рынка.
    
    Распознает команды вида:
    - "BTCUSDT на 1h таймфрейме"
    
    Args:
        prompt (str): входной промпт пользователя
        context (Context): контекст выполнения действия
    Returns:
        (List[Dict]): список сообщений с результатами анализа
    """
    symbol_match = re.search(r"(\w+)\s+на", prompt, re.IGNORECASE)
    interval_match = re.search(r"на\s+(\w+)\s+таймфрейме", prompt, re.IGNORECASE)
    
    if symbol_match and interval_match:
        symbol = symbol_match.group(1).upper()
        interval = interval_match.group(1)
        result = calculate_indicators(
            symbol=symbol, 
            interval=interval, 
            limit=100, 
            context=context
        )

        return [
            {
                "role": "assistant", 
                "content": result
            }
        ]
    
    return [
        {
            "role": "assistant", 
            "content": "Please specify symbol and timeframe"
        }
    ]


if __name__ == "__main__":
    mcp.run(transport="stdio")