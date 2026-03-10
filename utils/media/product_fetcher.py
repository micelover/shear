from utils.core.config import DIR_PATH, DATA_PATH, SOURCE_PATH, UTILS_PATH
from utils.core.settings import CATEGORY_POOL, KEYWORD_AMOUNT
from utils.core.edit import open_ai_generation, robust_json_loads
from utils.core.product_model import ProductItem

import os
import re
import ast
import json
import random
import logging
from typing import Optional
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

ASIN_RE = re.compile(r"/dp/([A-Z0-9]{10})|/gp/product/([A-Z0-9]{10})")

@dataclass
class RawProduct:
    title: str
    url: str


class ProductFetcher:

    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.serpapi_key = os.getenv("SERPAPI_API_KEY")
        self._prompts = self._load_prompts()

    # ------------------------------------------------------------------ #
    #  Setup                                                               #
    # ------------------------------------------------------------------ #

    def _load_prompts(self) -> dict[str, str]:
        names = ["simplify_titles", "product_selector", "product_type", "keyword"]
        prompts = {}
        for name in names:
            path = f"{UTILS_PATH}/prompts/{name}.txt"
            with open(path) as f:
                prompts[name] = f.read()
        return prompts

    def _prompt(self, name: str, **replacements) -> str:
        """Return a prompt template with all {placeholders} replaced."""
        text = self._prompts[name]
        for key, value in replacements.items():
            text = text.replace(f"{{{key}}}", str(value))
        return text

    # ------------------------------------------------------------------ #
    #  Amazon helpers                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_asin(url: str) -> Optional[str]:
        m = ASIN_RE.search(url)
        return (m.group(1) or m.group(2)) if m else None

    @staticmethod
    def _affiliate_link(asin: str, tag: str = "logostudios-20") -> str:
        return f"https://www.amazon.com/dp/{asin}?tag={tag}"

    @staticmethod
    def _pick_category(pool: list[dict]) -> str:
        names = [c["name"] for c in pool]
        weights = [c["weight"] for c in pool]
        return random.choices(names, weights=weights, k=1)[0]

    # ------------------------------------------------------------------ #
    #  SerpApi calls                                                        #
    # ------------------------------------------------------------------ #

    def _serpapi_get(self, params: dict, timeout: int = 10) -> dict:
        """Thin wrapper around SerpApi with unified error handling."""
        params["api_key"] = self.serpapi_key
        try:
            resp = requests.get("https://serpapi.com/search", params=params, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error("SerpApi request failed (engine=%s): %s", params.get("engine"), exc)
            return {}

    def search_featured(self, category: str) -> list[RawProduct]:
        data = self._serpapi_get({
            "engine": "amazon",
            "amazon_domain": "amazon.com",
            "k": category,
            "sort_by": "featured",
        })
        seen: set[str] = set()
        products: list[RawProduct] = []

        for item in data.get("organic_results", [])[:10]:
            asin = item.get("asin")
            title = item.get("title")
            url = item.get("link")
            if asin and title and url and asin not in seen:
                seen.add(asin)
                products.append(RawProduct(title=title, url=url))

        return products

    def search_movers_shakers(self) -> list[RawProduct]:
        CATEGORY_CONFIG = [
            {
                "name": "electronics",
                "query": 'site:amazon.com "Movers & Shakers" electronics "gp/movers-and-shakers"',
                "limit": 10,
            },
            {
                "name": "computers_accessories",
                "query": 'site:amazon.com "Movers & Shakers" "Computers & Accessories" "gp/movers-and-shakers"',
                "limit": 5,
            },
        ]

        all_products: list[RawProduct] = []
        seen_asins: set[str] = set()
        seen_urls: set[str] = set()
        seen_titles: set[str] = set()

        def _normalize(t: str) -> str:
            return t.lower().strip().replace("-", "").replace(",", "")

        for cat in CATEGORY_CONFIG:
            data = self._serpapi_get({"engine": "google", "q": cat["query"], "num": 5}, timeout=15)
            organic = data.get("organic_results") or []
            if not organic:
                logger.warning("No Google results for category: %s", cat["name"])
                continue

            # Prefer an actual Amazon movers page; fall back to first result
            page_url = next(
                (r.get("cached_page_link") or r.get("link")
                 for r in organic
                 if "amazon.com" in r.get("link", "") and "movers-and-shakers" in r.get("link", "")),
                organic[0].get("link"),
            )
            if not page_url:
                continue

            try:
                html = requests.get(page_url, timeout=20, headers={"User-Agent": "Mozilla/5.0"}).text
            except Exception as exc:
                logger.error("HTML fetch failed for %s: %s", cat["name"], exc)
                continue

            soup = BeautifulSoup(html, "html.parser")
            count = 0

            for a in soup.find_all("a", href=True):
                if count >= cat["limit"]:
                    break

                href = a["href"]
                m = ASIN_RE.search(href)
                if not m:
                    continue

                asin = m.group(1) or m.group(2)
                title = a.get_text(" ", strip=True) or (a.find("img") or {}).get("alt", "").strip()
                if not title or len(title) < 6:
                    continue

                url = ("https://www.amazon.com" + href if href.startswith("/") else href).split("?")[0]
                norm = _normalize(title)

                if asin in seen_asins or url in seen_urls or norm in seen_titles:
                    continue

                seen_asins.add(asin)
                seen_urls.add(url)
                seen_titles.add(norm)
                all_products.append(RawProduct(title=title, url=url))
                count += 1

        return all_products

    def fetch_product_details(self, url: str, affiliate_tag: str = "logostudios-20") -> Optional[dict]:
        asin = self._extract_asin(url)
        if not asin:
            logger.error("ASIN not found in URL: %s", url)
            return None

        data = self._serpapi_get({"engine": "amazon", "amazon_domain": "amazon.com", "k": asin})
        results = data.get("organic_results", [])
        if not results:
            logger.warning("No results for ASIN: %s", asin)
            return None

        item = results[0]
        return {
            "asin": asin,
            "title": item.get("title"),
            "price": item.get("price"),
            "url": url,
            "affiliate_link": self._affiliate_link(asin, affiliate_tag),
        }

    # ------------------------------------------------------------------ #
    #  AI steps                                                            #
    # ------------------------------------------------------------------ #

    def _ai(self, prompt_name: str, model: str = "gpt-4o-mini",
            temperature: float = 0, **replacements) -> str:
        prompt = self._prompt(prompt_name, **replacements)
        return open_ai_generation(prompt, model=model, temperature=temperature).strip()

    def _simplify_titles(self, products: list[RawProduct]) -> list[dict]:
        raw = json.dumps([{"title": p.title, "url": p.url} for p in products])
        response = self._ai("simplify_titles", PRODUCT_ARRAY=raw)
        return robust_json_loads(response)

    def _find_best_products(self, product_arr: list[dict]) -> list[dict]:
        response = self._ai("product_selector", PRODUCT_ARRAY=json.dumps(product_arr))
        return robust_json_loads(response)

    def classify_product(self, product: str) -> None:
        self.pipeline.product_type = self._ai("product_type", product_name=product, temperature=0.7)

    def generate_keywords(self, product: str) -> None:
        response = self._ai(
            "keyword",
            temperature=0.2,
            product=product,
            low=KEYWORD_AMOUNT["low"],
            high=KEYWORD_AMOUNT["high"],
        )
        self.pipeline.keywords = ast.literal_eval(response)

    # ------------------------------------------------------------------ #
    #  Main entry point                                                    #
    # ------------------------------------------------------------------ #

    def _fetch_raw_products(self) -> list[RawProduct]:
        if random.random() < 0.75:
            category = self._pick_category(CATEGORY_POOL)
            logger.info("Searching featured products in category: %s", category)
            return self.search_featured(category)
        logger.info("Searching Movers & Shakers")
        return self.search_movers_shakers()

    def GetProduct(self) -> None:
        raw_results = self._fetch_raw_products()
        logger.debug("Raw results: %s", raw_results)

        simple_products = self._simplify_titles(raw_results)
        logger.debug("Simplified: %s", simple_products)

        best_products = self._find_best_products(simple_products)
        chosen = random.choice(best_products)

        details = self.fetch_product_details(chosen["url"])
        if not details:
            raise RuntimeError(f"Could not fetch details for {chosen['url']}")

        combined = {**chosen, **details}
        allowed = ProductItem.__annotations__.keys()
        self.pipeline.product = ProductItem(**{k: v for k, v in combined.items() if k in allowed})