import requests
from bs4 import BeautifulSoup
import time
import random
import csv
import json
import re
from urllib.parse import urljoin, urlparse
from collections import Counter
from textblob import TextBlob  # For sentiment analysis and keyword extraction
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from playwright.async_api import async_playwright
import asyncio


# Configuration
BASE_URL = "https://listado.mercadolibre.com.ar/"  # Correct search listing format for Argentina
DEBUG = True  # Enable debug logging
HEADERS = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    },
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    },
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    },
]

# --- Utility Functions ---


def get_random_header():
    """Returns a random User-Agent header."""
    return random.choice(HEADERS)


def debug_print(message):
    """Print debug messages if DEBUG is enabled."""
    if DEBUG:
        print(f"[DEBUG] {message}")


def fetch_page(url, retries=3, backoff_factor=0.5):
    """Fetches a web page with retries and exponential backoff."""
    for i in range(retries):
        try:
            headers = get_random_header()
            debug_print(f"Using headers: {headers}")
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            debug_print(f"Response status code: {response.status_code}")
            debug_print(f"Response headers: {dict(response.headers)}")
            content = response.text
            debug_print("Using requests auto-decoded content")
            time.sleep(random.uniform(1, 3))  # Rate limiting
            return content
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {e}")
            if i < retries - 1:
                sleep_time = backoff_factor * (2**i)
                print(f"Retrying in {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)
            else:
                print(f"Failed to fetch {url} after {retries} retries.")
                return None


# --- Scraper Functions ---


def scrape_search_results(keyword, num_pages=1):
    """
    Scrapes product data from Mercado Libre search result pages.
    Extracts product URL, price, location, and shipping info.
    """
    products_data = []
    print(f"Scraping search results for '{keyword}' across {num_pages} page(s)...")

    for page in range(num_pages):
        search_url = f"{BASE_URL}{keyword}_Desde_{page * 50 + 1}"  # Mercado Libre uses 50 results per page
        print(f"Fetching search page: {search_url}")
        html_content = fetch_page(search_url)

        if html_content:
            soup = BeautifulSoup(html_content, "html.parser")

            # Try different possible selectors for product listings
            product_listings = soup.find_all("li", class_="ui-search-layout__item")
            if not product_listings:
                product_listings = soup.find_all(
                    "div", class_="ui-search-result__content"
                )
            if not product_listings:
                product_listings = soup.find_all("div", class_="ui-search-result")

            if not product_listings:
                print("No product listings found. Possible reasons:")
                print("1. The page structure has changed")
                print("2. The search returned no results")
                print("3. The request was blocked")
                print("\nHTML content preview:")
                print(html_content[:500])  # Print first 500 chars for debugging
                break

            for product in product_listings:
                try:
                    # Get product URL - try multiple possible selectors
                    url_tag = (
                        product.find("a", class_="ui-search-item__group__element")
                        or product.find("a", class_="ui-search-link")
                        or product.find("a", href=True)
                    )

                    if not url_tag or not url_tag.get("href"):
                        print("Skipping product: No valid URL found")
                        continue

                    url = url_tag["href"]

                    # Only process real product URLs
                    parsed_url = urlparse(url)
                    # Aceptamos solo dominios de MercadoLibre Argentina
                    if "mercadolibre.com.ar" not in parsed_url.netloc:
                        print(f"Skipping non-MercadoLibre URL: {url}")
                        continue

                    # Aceptamos productos si la URL contiene '/articulo/', '/MLA-' o '/p/MLA'
                    if not ("/articulo/" in url or "/MLA-" in url or "/p/MLA" in url):
                        print(f"Skipping non-product URL: {url}")
                        continue

                    # Initialize product data with required fields
                    product_data = {
                        "url": url,
                        "price": "N/A",
                        "category_path": "N/A",
                        "description": "N/A",
                        "num_sales": "N/A",
                        "review_snippets": [],
                    }

                    # Price selectors
                    price_whole_tag = product.find(
                        "span", class_="andes-money-amount__fraction"
                    ) or product.find("span", class_="price-tag-fraction")
                    price_decimals_tag = product.find(
                        "span", class_="andes-money-amount__cents"
                    ) or product.find("span", class_="price-tag-cents")
                    if price_whole_tag:
                        price = price_whole_tag.get_text(strip=True)
                        if price_decimals_tag:
                            price += "." + price_decimals_tag.get_text(strip=True)
                        product_data["price"] = price

                    # Location - only include if not N/A
                    location_tag = product.find(
                        "span", class_="ui-search-item__group__element--location"
                    ) or product.find("span", class_="ui-search-item__location")
                    location = (
                        location_tag.get_text(strip=True) if location_tag else "N/A"
                    )
                    if location != "N/A":
                        product_data["location"] = location

                    # Product reviews summary - only include if not N/A
                    product_reviews_summary_tag = product.find(
                        "span", class_="ui-search-reviews__amount"
                    ) or product.find("span", class_="ui-search-item__reviews")
                    product_reviews_summary = (
                        product_reviews_summary_tag.get_text(strip=True)
                        if product_reviews_summary_tag
                        else "N/A"
                    )
                    if product_reviews_summary != "N/A":
                        product_data["product_reviews_summary"] = (
                            product_reviews_summary
                        )

                    products_data.append(product_data)

                except Exception as e:
                    print(f"Error processing product: {str(e)}")
                    continue
        else:
            print(f"Could not fetch search page {search_url}. Skipping.")

    return products_data


def setup_driver():
    """Set up and return a configured Chrome WebDriver."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(f"user-agent={HEADERS[0]['User-Agent']}")

    driver = webdriver.Chrome(options=chrome_options)
    return driver


async def scrape_product_page(product_url):
    """
    Navigates into product detail pages and extracts description,
    number of sales, review snippets, and category path using Playwright.
    """
    product_details = {
        "description": "N/A",
        "num_sales": "N/A",
        "review_snippets": [],
        "category_path": "N/A",
    }

    print(f"Fetching product detail page: {product_url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=HEADERS[0]["User-Agent"],
            viewport={"width": 1920, "height": 1080},
        )

        try:
            page = await context.new_page()
            await page.goto(product_url, wait_until="networkidle")

            # Wait and get actual product title
            try:
                await page.wait_for_selector("h1.ui-pdp-title", timeout=15000)
                title_element = await page.query_selector("h1.ui-pdp-title")
                if title_element:
                    title = await title_element.text_content()
                    if title and title.strip():
                        product_details["title"] = title.strip()
            except Exception as e:
                print(f"Error extracting title: {str(e)}")

            # Add a small delay to ensure dynamic content loads
            await page.wait_for_timeout(1500)

            # Scroll to load dynamic content
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)
            await page.evaluate("window.scrollTo(0, 0)")

            # Description
            description_selectors = [
                "div.item-description__text",
                "p.ui-pdp-description__content",
                "div.ui-pdp-description__content",
                "div.ui-pdp-description__content__container",
                "div.ui-pdp-description__content__container__text",
            ]

            for selector in description_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        product_details["description"] = await element.text_content()
                        break
                except Exception:
                    continue

            # Number of sales - Improved extraction with multiple patterns
            try:
                sales_selectors = [
                    "span.ui-pdp-subtitle",
                    "p.ui-pdp-subtitle",
                    "span.ui-pdp-header__subtitle",
                    "div.ui-pdp-header__info",
                    "div.ui-pdp-seller__sales-info",
                    "span.ui-pdp-seller__sales-info__text",
                ]

                for selector in sales_selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            text = await element.text_content()
                            # Match various sales number formats
                            patterns = [
                                r"\+?(\d+)\s+(?:vendidos|ventas|unidades vendidas|unidades|compras|compradores)",
                                r"\+?(\d+(?:[.,]\d+)?)\s*(?:mil|miles)\s+(?:vendidos|ventas)",
                                r"más de\s+(\d+(?:[.,]\d+)?)\s+(?:vendidos|ventas)",
                            ]

                            for pattern in patterns:
                                match = re.search(pattern, text, re.IGNORECASE)
                                if match:
                                    num = match.group(1)
                                    # Convert "mil" to actual number
                                    if "mil" in text.lower() or "miles" in text.lower():
                                        num = str(int(float(num) * 1000))
                                    product_details["num_sales"] = num
                                    break
                            if product_details["num_sales"] != "N/A":
                                break
                    except Exception:
                        continue
            except Exception as e:
                print(f"Error getting sales info: {str(e)}")

            # Review snippets - Improved extraction with multiple selectors
            try:
                review_selectors = [
                    "p.ui-review-capability-comments__comment__content",
                    "div.ui-review-capability__comment__content",
                    "p.ui-review-capability__comment__content",
                ]

                for selector in review_selectors:
                    review_elements = await page.query_selector_all(selector)
                    if review_elements:
                        for review in review_elements[:5]:  # Get top 5 reviews
                            review_text = await review.text_content()
                            if review_text and len(review_text.strip()) > 10:
                                product_details["review_snippets"].append(
                                    review_text.strip()
                                )
                        if product_details["review_snippets"]:
                            break
            except Exception as e:
                print(f"Error getting reviews: {str(e)}")

            # Category path
            try:
                category_elements = await page.query_selector_all(
                    "a.andes-breadcrumb__link"
                )
                if category_elements:
                    category_path = []
                    for element in category_elements:
                        category_path.append(await element.text_content())
                    product_details["category_path"] = " > ".join(category_path)
            except Exception as e:
                print(f"Error getting category path: {str(e)}")

            # Debug information
            if DEBUG:
                print(f"Found {len(product_details['review_snippets'])} reviews")
                print(f"Sales: {product_details['num_sales']}")

        except Exception as e:
            print(f"Error scraping product page: {str(e)}")

        finally:
            await browser.close()

    return product_details


def scrape_product_page_sync(product_url):
    """Synchronous wrapper for the async scrape_product_page function."""
    return asyncio.run(scrape_product_page(product_url))


def analyze_context_sentiment(text, positive_words, negative_words):
    """Helper function to analyze sentiment for a specific context without recursion."""
    if not text:
        return {"sentiment": "neutral", "polarity": 0.0, "confidence": 0.0}

    text_lower = text.lower()
    positive_count = sum(1 for word in positive_words if word in text_lower)
    negative_count = sum(1 for word in negative_words if word in text_lower)

    total_words = positive_count + negative_count
    if total_words == 0:
        polarity = 0.0
    else:
        polarity = (positive_count - negative_count) / total_words

    if polarity > 0.2:
        sentiment = "positive"
    elif polarity < -0.2:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    confidence = min(1.0, (positive_count + negative_count) / 10)

    return {"sentiment": sentiment, "polarity": polarity, "confidence": confidence}


def analyze_sentiment(text):
    """Performs detailed sentiment analysis on text with Spanish language support."""
    if not text or text == "N/A":
        return {
            "sentiment": "neutral",
            "polarity": 0.0,
            "subjectivity": 0.0,
            "confidence": 0.0,
            "key_phrases": [],
            "emotions": {},
            "dominant_emotion": "neutral",
            "emotional_intensity": 0.0,
            "context_sentiment": {},
            "sentiment_trend": "neutral",
            "contextual_phrases": [],
        }

    # Spanish sentiment indicators
    positive_words = {
        "excelente",
        "bueno",
        "genial",
        "perfecto",
        "recomiendo",
        "recomendado",
        "satisfecho",
        "contento",
        "feliz",
        "increíble",
        "maravilloso",
        "fantástico",
        "óptimo",
        "ideal",
        "super",
        "muy bueno",
        "muy bien",
        "cumple",
        "cumplió",
        "funciona",
        "funcionó",
        "rápido",
        "rápida",
        "eficiente",
        "calidad",
    }

    negative_words = {
        "malo",
        "mal",
        "pésimo",
        "terrible",
        "horrible",
        "decepcionado",
        "decepción",
        "problema",
        "problemas",
        "falla",
        "fallas",
        "defecto",
        "defectos",
        "lento",
        "lenta",
        "caro",
        "costoso",
        "no funciona",
        "no recomendado",
        "no recomiendo",
        "insatisfecho",
        "insatisfecha",
    }

    # Convert to lowercase for comparison
    text_lower = text.lower()

    # Count positive and negative words
    positive_count = sum(1 for word in positive_words if word in text_lower)
    negative_count = sum(1 for word in negative_words if word in text_lower)

    # Calculate polarity (-1 to 1)
    total_words = positive_count + negative_count
    if total_words == 0:
        polarity = 0.0
    else:
        polarity = (positive_count - negative_count) / total_words

    # Determine sentiment
    if polarity > 0.2:
        sentiment = "positive"
    elif polarity < -0.2:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    # Calculate subjectivity (0 to 1)
    emotional_words = positive_words.union(negative_words)
    emotional_count = sum(1 for word in emotional_words if word in text_lower)
    total_words_in_text = len(text_lower.split())
    subjectivity = (
        emotional_count / total_words_in_text if total_words_in_text > 0 else 0.0
    )

    # Enhanced emotion detection
    emotions = {
        "joy": {
            "words": [
                "feliz",
                "contento",
                "alegre",
                "satisfecho",
                "encantado",
                "genial",
                "excelente",
            ],
            "intensity": 1.0,
        },
        "trust": {
            "words": [
                "confiable",
                "seguro",
                "recomendado",
                "garantizado",
                "original",
                "auténtico",
            ],
            "intensity": 0.9,
        },
        "fear": {
            "words": [
                "preocupado",
                "inseguro",
                "dudoso",
                "temeroso",
                "problema",
                "falla",
            ],
            "intensity": -0.8,
        },
        "surprise": {
            "words": [
                "sorpresa",
                "increíble",
                "asombroso",
                "impresionante",
                "maravilloso",
            ],
            "intensity": 0.7,
        },
        "sadness": {
            "words": ["decepcionado", "triste", "insatisfecho", "molesto", "terrible"],
            "intensity": -0.6,
        },
        "disgust": {
            "words": ["terrible", "horrible", "pésimo", "deplorable", "no funciona"],
            "intensity": -0.9,
        },
        "anger": {
            "words": ["enojado", "frustrado", "irritado", "molesto", "defectuoso"],
            "intensity": -0.7,
        },
        "anticipation": {
            "words": ["esperanzado", "optimista", "confiado", "positivo", "recomiendo"],
            "intensity": 0.8,
        },
    }

    # Calculate emotion scores with intensity
    emotion_scores = {emotion: 0.0 for emotion in emotions}
    for emotion, data in emotions.items():
        for word in data["words"]:
            if word in text_lower:
                emotion_scores[emotion] += data["intensity"]

    # Normalize emotion scores
    total_emotions = sum(abs(score) for score in emotion_scores.values())
    if total_emotions > 0:
        emotion_scores = {k: v / total_emotions for k, v in emotion_scores.items()}

    # Get dominant emotion
    dominant_emotion = (
        max(emotion_scores.items(), key=lambda x: x[1])[0]
        if any(emotion_scores.values())
        else "neutral"
    )

    # Context-specific sentiment analysis
    contexts = {
        "product_quality": {
            "keywords": ["calidad", "durabilidad", "material", "resistente"],
            "weight": 1.2,
        },
        "price_value": {
            "keywords": ["precio", "valor", "económico", "caro", "barato"],
            "weight": 1.0,
        },
        "usability": {
            "keywords": ["fácil", "sencillo", "intuitivo", "complicado"],
            "weight": 1.1,
        },
        "customer_service": {
            "keywords": ["atención", "soporte", "ayuda", "servicio"],
            "weight": 0.9,
        },
    }

    context_scores = {}
    for context, data in contexts.items():
        context_text = " ".join(
            word
            for word in text_lower.split()
            if any(kw in word for kw in data["keywords"])
        )
        if context_text:
            context_sentiment = analyze_context_sentiment(
                context_text, positive_words, negative_words
            )
            context_scores[context] = {
                "sentiment": context_sentiment["sentiment"],
                "polarity": context_sentiment["polarity"] * data["weight"],
                "confidence": context_sentiment["confidence"],
            }

    # Sentiment trend detection
    trend_indicators = {
        "improving": ["mejoró", "superó", "avanzó", "evolucionó", "progresó"],
        "declining": ["empeoró", "degradó", "retrocedió", "falló", "decepcionó"],
        "stable": ["mantiene", "consistente", "estable", "igual", "similar"],
    }

    trend_scores = {trend: 0 for trend in trend_indicators}
    for trend, indicators in trend_indicators.items():
        trend_scores[trend] = sum(
            1 for indicator in indicators if indicator in text_lower
        )

    # Enhanced key phrase extraction with context
    def extract_contextual_phrases(text, word, window=5):
        words = text.lower().split()
        try:
            idx = words.index(word)
            start = max(0, idx - window)
            end = min(len(words), idx + window + 1)
            phrase = " ".join(words[start:end])

            sentiment_words = positive_words.union(negative_words)
            sentiment_context = [w for w in words[start:end] if w in sentiment_words]

            return {
                "phrase": phrase,
                "sentiment_context": sentiment_context,
                "position": idx / len(words),
            }
        except ValueError:
            return None

    contextual_phrases = []
    for word in positive_words.union(negative_words):
        if word in text_lower:
            phrase_data = extract_contextual_phrases(text_lower, word)
            if phrase_data:
                contextual_phrases.append(phrase_data)

    # Calculate confidence based on the strength of sentiment indicators
    confidence = min(1.0, (positive_count + negative_count) / 10)

    return {
        "sentiment": sentiment,
        "polarity": polarity,
        "subjectivity": subjectivity,
        "confidence": confidence,
        "key_phrases": [
            p["phrase"]
            for p in sorted(
                contextual_phrases,
                key=lambda x: len(x["sentiment_context"]),
                reverse=True,
            )[:5]
        ],
        "emotions": emotion_scores,
        "dominant_emotion": dominant_emotion,
        "emotional_intensity": sum(abs(score) for score in emotion_scores.values()),
        "context_sentiment": context_scores,
        "sentiment_trend": max(trend_scores.items(), key=lambda x: x[1])[0]
        if any(trend_scores.values())
        else "neutral",
        "contextual_phrases": sorted(
            contextual_phrases, key=lambda x: len(x["sentiment_context"]), reverse=True
        )[:5],
    }


def extract_customer_feedback(text_list):
    """Extracts detailed customer feedback from text."""
    feedback = {
        "satisfaction_levels": {
            "very_satisfied": 0,
            "satisfied": 0,
            "neutral": 0,
            "dissatisfied": 0,
            "very_dissatisfied": 0,
        },
        "common_themes": Counter(),
        "specific_issues": [],
        "praise_points": [],
        "suggestions": [],
    }

    satisfaction_indicators = {
        "very_satisfied": [
            "excelente",
            "perfecto",
            "increíble",
            "maravilloso",
            "fantástico",
        ],
        "satisfied": ["bueno", "bien", "recomiendo", "cumple", "funciona"],
        "neutral": ["normal", "regular", "aceptable", "básico"],
        "dissatisfied": ["malo", "problema", "falla", "lento", "caro"],
        "very_dissatisfied": [
            "pésimo",
            "terrible",
            "horrible",
            "decepción",
            "no funciona",
        ],
    }

    for text in text_list:
        if not text or text == "N/A":
            continue

        text_lower = text.lower()

        # Analyze satisfaction level
        for level, indicators in satisfaction_indicators.items():
            if any(indicator in text_lower for indicator in indicators):
                feedback["satisfaction_levels"][level] += 1
                break

        # Extract common themes
        themes = {
            "price": ["precio", "costo", "caro", "barato", "económico"],
            "quality": ["calidad", "durabilidad", "resistente", "premium"],
            "performance": ["rápido", "velocidad", "rendimiento", "eficiente"],
            "usability": ["fácil", "sencillo", "intuitivo", "complicado"],
            "support": ["atención", "soporte", "ayuda", "servicio"],
            "delivery": ["envío", "entrega", "llegada", "shipping"],
        }

        for theme, keywords in themes.items():
            if any(keyword in text_lower for keyword in keywords):
                feedback["common_themes"][theme] += 1

        # Extract specific issues
        issue_indicators = ["problema", "falla", "error", "defecto", "no funciona"]
        if any(indicator in text_lower for indicator in issue_indicators):
            # Get the sentence containing the issue
            sentences = text.split(".")
            for sentence in sentences:
                if any(indicator in sentence.lower() for indicator in issue_indicators):
                    feedback["specific_issues"].append(sentence.strip())

        # Extract praise points
        praise_indicators = ["excelente", "bueno", "genial", "perfecto", "recomiendo"]
        if any(indicator in text_lower for indicator in praise_indicators):
            sentences = text.split(".")
            for sentence in sentences:
                if any(
                    indicator in sentence.lower() for indicator in praise_indicators
                ):
                    feedback["praise_points"].append(sentence.strip())

        # Extract suggestions
        suggestion_indicators = [
            "mejorar",
            "sugerencia",
            "recomendación",
            "debería",
            "podría",
        ]
        if any(indicator in text_lower for indicator in suggestion_indicators):
            sentences = text.split(".")
            for sentence in sentences:
                if any(
                    indicator in sentence.lower() for indicator in suggestion_indicators
                ):
                    feedback["suggestions"].append(sentence.strip())

    # Clean up and limit lists
    feedback["specific_issues"] = list(set(feedback["specific_issues"]))[:5]
    feedback["praise_points"] = list(set(feedback["praise_points"]))[:5]
    feedback["suggestions"] = list(set(feedback["suggestions"]))[:5]

    return feedback


def extract_keywords(text):
    """Extracts top keywords from text."""
    if not text:  # Handle empty string
        return []
    words = re.findall(r"\b\w+\b", text.lower())
    stop_words = set(
        [
            "de",
            "la",
            "el",
            "en",
            "y",
            "a",
            "los",
            "las",
            "un",
            "una",
            "por",
            "para",
            "con",
            "no",
            "es",
            "se",
            "del",
            "al",
            "que",
            "más",
            "mi",
            "me",
            "su",
            "sus",
            "lo",
            "le",
            "si",
            "pero",
            "o",
            "sin",
            "también",
            "muy",
            "como",
            "cuando",
            "donde",
            "quien",
            "que",
            "este",
            "esta",
            "estos",
            "estas",
            "son",
            "fue",
            "un",
            "una",
            "unos",
            "unas",
            "es",
            "son",
            "ha",
            "han",
            "tener",
            "estar",
            "ser",
            "hacer",
            "haber",
        ]
    )
    # Filter out stop words and single-character words
    filtered_words = [
        word for word in words if word not in stop_words and len(word) > 1
    ]
    word_counts = Counter(filtered_words)
    return [word for word, count in word_counts.most_common(5)]  # Top 5 keywords


def extract_insights(product_data):
    """
    Analyzes product data to extract comprehensive marketing insights.
    Provides structured analysis of pricing, features, customer sentiment, and competitive positioning.
    """
    # Initialize data structures
    price_data = []
    feature_mentions = Counter()
    all_reviews_text = []
    all_descriptions_text = []
    category_distribution = Counter()

    # Collect and process data
    for product in product_data:
        # Price analysis
        if product.get("price") != "N/A":
            try:
                price = float(product["price"].replace(".", "").replace(",", "."))
                price_data.append(price)
            except (ValueError, AttributeError):
                pass

        # Category analysis
        if product.get("category_path") != "N/A":
            category_distribution[product["category_path"]] += 1

        # Collect text data
        all_reviews_text.extend(product.get("review_snippets", []))
        if product.get("description"):
            all_descriptions_text.append(product["description"])

    # Price Analysis
    price_insights = {
        "price_range": {
            "min": min(price_data) if price_data else "N/A",
            "max": max(price_data) if price_data else "N/A",
            "avg": sum(price_data) / len(price_data) if price_data else "N/A",
        },
        "price_segments": {
            "budget": len(
                [p for p in price_data if p < sum(price_data) / len(price_data) * 0.7]
            )
            if price_data
            else 0,
            "mid_range": len(
                [
                    p
                    for p in price_data
                    if sum(price_data) / len(price_data) * 0.7
                    <= p
                    <= sum(price_data) / len(price_data) * 1.3
                ]
            )
            if price_data
            else 0,
            "premium": len(
                [p for p in price_data if p > sum(price_data) / len(price_data) * 1.3]
            )
            if price_data
            else 0,
        },
    }

    # Feature Analysis
    feature_keywords = {
        "material": [
            "material",
            "tela",
            "algodón",
            "poliéster",
            "cuero",
            "plástico",
            "metal",
            "madera",
            "acero",
            "aluminio",
            "fibra",
            "sintético",
            "natural",
        ],
        "size": [
            "talle",
            "tamaño",
            "medida",
            "dimensiones",
            "largo",
            "ancho",
            "alto",
            "profundidad",
            "peso",
            "capacidad",
            "volumen",
        ],
        "color": [
            "color",
            "colores",
            "tono",
            "multicolor",
            "estampado",
            "diseño",
            "patrón",
            "motivo",
        ],
        "brand": [
            "marca",
            "original",
            "genuino",
            "auténtico",
            "oficial",
            "certificado",
        ],
        "condition": [
            "nuevo",
            "usado",
            "reacondicionado",
            "restaurado",
            "seminuevo",
            "como nuevo",
        ],
        "warranty": [
            "garantía",
            "garantizado",
            "devolución",
            "cambio",
            "servicio técnico",
            "soporte",
        ],
        "shipping": [
            "envío",
            "entrega",
            "gratis",
            "gratuito",
            "sin cargo",
            "retiro",
            "pickup",
            "sucursal",
        ],
        "package": [
            "incluye",
            "contenido",
            "accesorios",
            "manual",
            "instrucciones",
            "caja",
            "embalaje",
        ],
        "quality": [
            "calidad",
            "premium",
            "resistente",
            "durable",
            "robusto",
            "fuerte",
            "resistencia",
        ],
        "design": [
            "diseño",
            "estilo",
            "moderno",
            "clásico",
            "elegante",
            "exclusivo",
            "único",
        ],
        "comfort": [
            "cómodo",
            "ergonómico",
            "suave",
            "flexible",
            "adaptable",
            "ajustable",
        ],
        "safety": [
            "seguro",
            "certificado",
            "normas",
            "estándar",
            "aprobado",
            "testeado",
        ],
        "maintenance": [
            "mantenimiento",
            "limpieza",
            "cuidado",
            "lavado",
            "conservación",
        ],
        "compatibility": [
            "compatible",
            "universal",
            "adaptador",
            "conexión",
            "acoplamiento",
        ],
        "sustainability": [
            "ecológico",
            "sustentable",
            "reciclable",
            "biodegradable",
            "ambiental",
        ],
    }

    feature_analysis = {}
    for category, keywords in feature_keywords.items():
        mentions = 0
        for desc in all_descriptions_text:
            for keyword in keywords:
                if keyword.lower() in desc.lower():
                    mentions += 1
        feature_analysis[category] = mentions

    # Enhanced Sentiment Analysis
    def analyze_sentiment_by_category(text_list, categories):
        results = {}
        for category in categories:
            category_text = " ".join(
                [
                    t
                    for t in text_list
                    if any(kw in t.lower() for kw in categories[category])
                ]
            )
            sentiment = analyze_sentiment(category_text)
            results[category] = sentiment
        return results

    sentiment_categories = {
        "quality": ["calidad", "durabilidad", "resistente", "premium"],
        "performance": ["rápido", "velocidad", "rendimiento", "eficiente"],
        "value": ["precio", "valor", "económico", "caro", "barato"],
        "usability": ["fácil", "sencillo", "intuitivo", "complicado", "difícil"],
    }

    # Detailed sentiment analysis for reviews
    reviews_sentiment = analyze_sentiment(" ".join(all_reviews_text))

    sentiment_analysis = {
        "overall": {"reviews": reviews_sentiment},
        "by_category": {
            "reviews": analyze_sentiment_by_category(
                all_reviews_text, sentiment_categories
            ),
        },
    }

    # Enhanced Customer Feedback Analysis
    customer_feedback = {
        "reviews": extract_customer_feedback(all_reviews_text),
    }

    # Competitive Analysis
    competitive_analysis = {
        "category_distribution": dict(category_distribution),
        "price_positioning": {
            "market_average": sum(price_data) / len(price_data)
            if price_data
            else "N/A",
            "price_competitiveness": "high"
            if price_data and min(price_data) < sum(price_data) / len(price_data) * 0.9
            else "low",
        },
    }

    # Marketing Recommendations
    marketing_recommendations = {
        "key_selling_points": [
            feature for feature, count in feature_analysis.items() if count > 0
        ],
        "target_audience": "premium"
        if price_insights["price_segments"]["premium"]
        > price_insights["price_segments"]["budget"]
        else "budget",
        "pricing_strategy": "premium"
        if price_insights["price_segments"]["premium"]
        > price_insights["price_segments"]["budget"]
        else "competitive",
        "feature_highlights": [
            f
            for f, s in sentiment_analysis["by_category"]["reviews"].items()
            if s["sentiment"] == "positive"
        ],
        "improvement_areas": [
            f
            for f, s in sentiment_analysis["by_category"]["reviews"].items()
            if s["sentiment"] == "negative"
        ],
        # New enhanced recommendations
        "market_positioning": {
            "price_position": "premium"
            if price_insights["price_segments"]["premium"]
            > price_insights["price_segments"]["budget"]
            else "budget",
            "quality_position": "high"
            if sentiment_analysis["by_category"]["reviews"]
            .get("quality", {})
            .get("sentiment")
            == "positive"
            else "standard",
            "value_proposition": "quality-focused"
            if sentiment_analysis["by_category"]["reviews"]
            .get("quality", {})
            .get("sentiment")
            == "positive"
            else "price-focused",
        },
        "customer_segments": {
            "primary": "quality-conscious"
            if sentiment_analysis["by_category"]["reviews"]
            .get("quality", {})
            .get("sentiment")
            == "positive"
            else "price-sensitive",
            "secondary": "value-seekers"
            if sentiment_analysis["by_category"]["reviews"]
            .get("value", {})
            .get("sentiment")
            == "positive"
            else "feature-focused",
        },
        "marketing_channels": {
            "primary": "social_media"
            if any(
                "social" in theme.lower()
                for theme in customer_feedback["reviews"]["common_themes"]
            )
            else "search_engines",
            "secondary": "marketplace"
            if any(
                "envío" in theme.lower()
                for theme in customer_feedback["reviews"]["common_themes"]
            )
            else "direct_sales",
        },
        "content_strategy": {
            "key_messages": [
                f"Highlight {feature}"
                for feature in feature_analysis
                if feature_analysis[feature] > 0
            ],
            "unique_selling_propositions": [
                f"Emphasize {feature}"
                for feature, sentiment in sentiment_analysis["by_category"][
                    "reviews"
                ].items()
                if sentiment["sentiment"] == "positive"
                and sentiment["confidence"] > 0.7
            ],
            "content_focus": "quality"
            if sentiment_analysis["by_category"]["reviews"]
            .get("quality", {})
            .get("sentiment")
            == "positive"
            else "value",
        },
        "promotional_strategy": {
            "discount_approach": "selective"
            if price_insights["price_segments"]["premium"] > 0
            else "aggressive",
            "bundling_opportunities": [
                feature
                for feature, count in feature_analysis.items()
                if count > 0 and feature in ["package", "compatibility", "accessories"]
            ],
            "seasonal_focus": "year-round"
            if len(customer_feedback["reviews"]["common_themes"]) > 3
            else "peak_seasons",
        },
        "competitive_advantages": {
            "price_advantage": "high"
            if price_insights["price_segments"]["budget"]
            > price_insights["price_segments"]["premium"]
            else "low",
            "quality_advantage": "high"
            if sentiment_analysis["by_category"]["reviews"]
            .get("quality", {})
            .get("sentiment")
            == "positive"
            else "low",
            "service_advantage": "high"
            if sentiment_analysis["by_category"]["reviews"]
            .get("customer_service", {})
            .get("sentiment")
            == "positive"
            else "low",
        },
        "action_items": [
            {"priority": "high", "action": f"Enhance {area}"}
            for area in [
                f
                for f, s in sentiment_analysis["by_category"]["reviews"].items()
                if s["sentiment"] == "negative"
            ]
        ]
        + [
            {"priority": "medium", "action": f"Promote {feature}"}
            for feature in [
                f
                for f, s in sentiment_analysis["by_category"]["reviews"].items()
                if s["sentiment"] == "positive"
            ]
        ]
        + [
            {
                "priority": "low",
                "action": "Monitor market trends"
                if len(customer_feedback["reviews"]["suggestions"]) > 0
                else "Maintain current strategy",
            }
        ],
        "risk_mitigation": {
            "price_risks": "high"
            if price_insights["price_segments"]["budget"]
            > price_insights["price_segments"]["premium"]
            else "low",
            "quality_risks": "high"
            if sentiment_analysis["by_category"]["reviews"]
            .get("quality", {})
            .get("sentiment")
            == "negative"
            else "low",
            "service_risks": "high"
            if sentiment_analysis["by_category"]["reviews"]
            .get("customer_service", {})
            .get("sentiment")
            == "negative"
            else "low",
        },
        "growth_opportunities": [
            {
                "area": feature,
                "potential": "high"
                if sentiment_analysis["by_category"]["reviews"]
                .get(feature, {})
                .get("sentiment")
                == "positive"
                else "medium",
            }
            for feature in feature_analysis
            if feature_analysis[feature] > 0
        ],
    }

    # Compile all insights
    insights = {
        "price_analysis": price_insights,
        "feature_analysis": feature_analysis,
        "sentiment_analysis": sentiment_analysis,
        "customer_feedback": customer_feedback,
        "competitive_analysis": competitive_analysis,
        "marketing_recommendations": marketing_recommendations,
    }

    return insights


def save_to_csv(data, filename):
    """Saves a list of dictionaries to a CSV file."""
    if not data:
        print(f"No data to save to {filename}.")
        return
    keys = data[0].keys()
    with open(filename, "w", newline="", encoding="utf-8") as f:
        dict_writer = csv.DictWriter(f, keys)
        dict_writer.writeheader()
        dict_writer.writerows(data)
    print(f"Data saved to {filename}")


def save_to_json(data, filename):
    """Saves a list of dictionaries to a JSON file."""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"Data saved to {filename}")


# --- CLI Interface ---

import argparse


async def main_async():
    parser = argparse.ArgumentParser(
        description="Mercado Libre Scraper and Marketing Insights Tool"
    )
    parser.add_argument(
        "--keyword", type=str, required=True, help="Keyword to search on Mercado Libre"
    )
    parser.add_argument(
        "--pages", type=int, default=1, help="Number of search result pages to scrape"
    )
    parser.add_argument(
        "--output_csv",
        type=str,
        default="mercadolibre_products.csv",
        help="Output CSV filename",
    )
    parser.add_argument(
        "--output_json",
        type=str,
        default="mercadolibre_products.json",
        help="Output JSON filename",
    )
    parser.add_argument(
        "--insights_json",
        type=str,
        default="mercadolibre_insights.json",
        help="Output JSON filename for marketing insights",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        help="Number of concurrent product page scrapes",
    )

    args = parser.parse_args()

    print(
        f"Starting Mercado Libre Scraper for keyword: {args.keyword}, pages: {args.pages}"
    )

    # Step 1: Scrape search results
    products_data = scrape_search_results(args.keyword, args.pages)

    # Step 2: Scrape product detail pages and enrich data
    if products_data:
        print("Scraping product detail pages...")
        enriched_products_data = []

        # Process products in batches to avoid overwhelming the server
        for i in range(0, len(products_data), args.concurrency):
            batch = products_data[i : i + args.concurrency]
            tasks = []

            for product in batch:
                print(
                    f"Processing product {i + 1}/{len(products_data)}: {product['url']}"
                )
                tasks.append(scrape_product_page(product["url"]))

            # Wait for all tasks in the batch to complete
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results and handle any exceptions
            for product, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    print(f"Error processing {product['url']}: {str(result)}")
                    enriched_products_data.append(
                        product
                    )  # Keep original data if scraping fails
                else:
                    # Merge product details with existing search result data
                    enriched_product = {**product, **result}
                    enriched_products_data.append(enriched_product)

            # Add delay between batches to avoid rate limiting
            if i + args.concurrency < len(products_data):
                await asyncio.sleep(random.uniform(2, 4))

        products_data = enriched_products_data

        # Step 3: Analyze and Extract Insights
        print("Analyzing data and extracting marketing insights...")
        marketing_insights = extract_insights(products_data)

        # Save insights
        save_to_json(marketing_insights, args.insights_json)
    else:
        print("No product data to analyze.")

    # Step 4: Save scraped data
    if products_data:
        save_to_csv(products_data, args.output_csv)
        save_to_json(products_data, args.output_json)
    else:
        print("No products scraped to save.")

    print("Scraping and analysis complete.")


def main():
    """Entry point for the script."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
