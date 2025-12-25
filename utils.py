import aiohttp
from datetime import datetime
import pytz
import time

# Fuso horário do Brasil
BR_TZ = pytz.timezone("America/Sao_Paulo")

def now() -> datetime:
    """Retorna a hora atual em timezone BR_TZ"""
    return datetime.now(tz=BR_TZ)

def format_datetime_br(dt: datetime) -> str:
    """Formata datetime para string dd/mm/yyyy HH:MM:SS em horário de Brasília"""
    if not isinstance(dt, datetime):
        return str(dt)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.utc).astimezone(BR_TZ)
    else:
        dt = dt.astimezone(BR_TZ)
    return dt.strftime("%d/%m/%Y %H:%M:%S")

def ms_to_str(ms: float) -> str:
    """Converte milissegundos em string Hh Mm Ss"""
    seconds = int(ms / 1000)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m {s:02d}s"

async def get_site_status(url: str) -> dict:
    """
    Faz requisição HTTP ao site e retorna dicionário com status
    {'online': bool, 'http_code': int, 'response_time': int, 'timestamp': datetime}
    """
    start_time = time.time()
    timeout = aiohttp.ClientTimeout(total=10)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.get(url) as response:
                response_time = int((time.time() - start_time) * 1000)
                code = response.status
                online = 200 <= code < 300
                return {
                    "online": online,
                    "http_code": code,
                    "response_time": response_time,
                    "timestamp": now()
                }
        except Exception as e:
            return {
                "online": False,
                "http_code": None,
                "response_time": 0,
                "timestamp": now(),
                "error": str(e)
            }