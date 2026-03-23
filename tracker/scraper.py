"""
scraper.py
Handles all web scraping. Each supported retailer has its own function
because their HTML structures are different.
"""

import requests
from bs4 import BeautifulSoup
import re
import logging

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'en-GB,en;q=0.9',
}


class ScrapedProduct:
    """Simple data container for a scraped product."""
    def __init__(self, name, price, image_url, in_stock):
        self.name      = name
        self.price     = price      # float
        self.image_url = image_url
        self.in_stock  = in_stock   # bool


def clean_price(price_str):
    """
    Strips currency symbols and other characters from a price string
    and returns a float, or None if it can't be parsed.
    e.g. '£32.99' -> 32.99
    """
    if not price_str:
        return None
    cleaned = re.sub(r'[^\d.]', '', price_str.replace(',', '.'))
    try:
        val = float(cleaned)
        # Sanity check - prices shouldn't be £0 or £100,000+
        if 0 < val < 100000:
            return val
    except ValueError:
        pass
    return None


def scrape_amazon(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            logger.warning(f"Amazon returned {response.status_code} for {url}")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        name_tag = soup.find('span', id='productTitle')
        name = name_tag.get_text(strip=True) if name_tag else 'Unknown Product'

        # Try multiple price selectors as Amazon changes them regularly
        price = None
        for tag, attrs in [
            ('span', {'class': 'a-price-whole'}),
            ('span', {'id': 'priceblock_ourprice'}),
            ('span', {'id': 'priceblock_dealprice'}),
            ('span', {'class': 'a-offscreen'}),
        ]:
            tag_el = soup.find(tag, attrs)
            if tag_el:
                price = clean_price(tag_el.get_text())
                if price:
                    break

        image_url = None
        img = soup.find('img', id='landingImage')
        if img:
            image_url = img.get('src') or img.get('data-old-hires')

        in_stock = True
        avail = soup.find('div', id='availability')
        if avail and ('unavailable' in avail.get_text().lower() or
                      'out of stock' in avail.get_text().lower()):
            in_stock = False

        if not price:
            logger.error(f"Could not extract price from Amazon: {url}")
            return None

        return ScrapedProduct(name, price, image_url, in_stock)

    except requests.RequestException as e:
        logger.error(f"Request error for {url}: {e}")
        return None


def scrape_currys(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        name_tag = soup.find('h1', {'class': re.compile('product-title|pdp-title', re.I)})
        name = name_tag.get_text(strip=True) if name_tag else 'Unknown Product'

        price = None
        price_tag = soup.find('span', {'class': re.compile('price', re.I)})
        if price_tag:
            price = clean_price(price_tag.get_text())

        image_url = None
        img = soup.find('img', {'class': re.compile('product-image|main-image', re.I)})
        if img:
            image_url = img.get('src')

        in_stock = not bool(soup.find(string=re.compile('out of stock', re.I)))

        if not price:
            return None
        return ScrapedProduct(name, price, image_url, in_stock)

    except requests.RequestException as e:
        logger.error(f"Request error for {url}: {e}")
        return None


def scrape_john_lewis(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        name_tag = soup.find('h1')
        name = name_tag.get_text(strip=True) if name_tag else 'Unknown Product'

        price = None
        price_tag = soup.find(attrs={'data-testid': re.compile('price', re.I)})
        if not price_tag:
            price_tag = soup.find('p', {'class': re.compile('price', re.I)})
        if price_tag:
            price = clean_price(price_tag.get_text())

        image_url = None
        img = soup.find('img', {'data-testid': re.compile('product-image', re.I)})
        if img:
            image_url = img.get('src')

        if not price:
            return None
        return ScrapedProduct(name, price, image_url, True)

    except requests.RequestException as e:
        logger.error(f"Request error for {url}: {e}")
        return None


def scrape_argos(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        name_tag = soup.find('h1')
        name = name_tag.get_text(strip=True) if name_tag else 'Unknown Product'

        price = None
        price_tag = soup.find(attrs={'data-test': 'product-price'})
        if not price_tag:
            price_tag = soup.find('strong', {'class': re.compile('price', re.I)})
        if price_tag:
            price = clean_price(price_tag.get_text())

        image_url = None
        img = soup.find('img', {'class': re.compile('product-image', re.I)})
        if img:
            image_url = img.get('src')

        in_stock = not bool(soup.find(string=re.compile('out of stock', re.I)))

        if not price:
            return None
        return ScrapedProduct(name, price, image_url, in_stock)

    except requests.RequestException as e:
        logger.error(f"Request error for {url}: {e}")
        return None


SCRAPER_MAP = {
    'amazon.co.uk':  scrape_amazon,
    'currys.co.uk':  scrape_currys,
    'johnlewis.com': scrape_john_lewis,
    'argos.co.uk':   scrape_argos,
}


def scrape_product(url):
    """Picks the right scraper for the URL and returns a ScrapedProduct or None."""
    for domain, func in SCRAPER_MAP.items():
        if domain in url:
            logger.info(f"Scraping {url} with {func.__name__}")
            return func(url)
    logger.warning(f"No scraper available for URL: {url}")
    return None


def is_supported_url(url):
    return any(domain in url for domain in SCRAPER_MAP)

