import re
from typing import Optional, Tuple

import aiohttp
from bs4 import BeautifulSoup


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)


async def fetch_html(url: str) -> Optional[str]:
    """Скачать HTML страницы."""
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, headers={"User-Agent": USER_AGENT}) as resp:
            if resp.status != 200:
                return None
            return await resp.text()


def extract_title(html: str) -> Optional[str]:
    """Достаём название товара из og:title / title / h1."""
    soup = BeautifulSoup(html, "html.parser")

    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return og_title["content"].strip()

    if soup.title and soup.title.string:
        return soup.title.string.strip()

    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)

    return None


def extract_price(html: str) -> Optional[int]:
    """
    Очень простой парсер цены:
    ищет в тексте первое число с 4+ цифрами рядом с '₽' или 'руб'.
    Это не идеально, но для демо и многих карточек этого хватит.
    """
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)

    price_pattern = re.compile(r"(\d[\d\s]{3,})\s*(?:₽|руб\.?)", re.IGNORECASE)
    match = price_pattern.search(text)
    if not match:
        return None

    digits = re.sub(r"\D", "", match.group(1))
    if not digits:
        return None

    try:
        return int(digits)
    except ValueError:
        return None


async def fetch_product_info(url: str) -> Tuple[Optional[str], Optional[int]]:
    """
    Возвращает (title, price) для товара по ссылке.
    """
    html = await fetch_html(url)
    if html is None:
        return None, None

    title = extract_title(html)
    price = extract_price(html)
    return title, price
