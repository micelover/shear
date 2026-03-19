from utils.core.config import UTILS_PATH
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
from urllib.parse import unquote

import requests
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()
logger = logging.getLogger(__name__)

ASIN_RE = re.compile(r"/dp/([A-Z0-9]{10})|/gp/product/([A-Z0-9]{10})")

@dataclass
class RawProduct:
    asin: str
    title: str
    url: str

class ProductFetcher:

    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.serpapi_key = os.getenv("SHEARS_SERPAPI_API_KEY")
        self._prompts = self._load_prompts()

    # ------------------------------------------------------------------ #
    #  Setup                                                             #
    # ------------------------------------------------------------------ #

    def load_used_asins(self, path=f"{UTILS_PATH}/media/used_products.json"):
        if not os.path.exists(path):
            return set()

        with open(path) as f:
            data = json.load(f)

        return {p["asin"] for p in data}

    def _load_prompts(self) -> dict[str, str]:
        names = ["simplify_titles", "product_type", "keyword"]
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
        # First try direct search
        m = ASIN_RE.search(url)
        if m:
            return m.group(1) or m.group(2)
        
        # If not found, try URL-decoding (handles click-tracking URLs with encoded parameters)
        decoded_url = unquote(url)
        m = ASIN_RE.search(decoded_url)
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

    def _serpapi_get(self, params: dict, timeout: int = 30) -> dict:
        """Thin wrapper around SerpApi with unified error handling."""
        params["api_key"] = self.serpapi_key
        try:
            resp = requests.get("https://serpapi.com/search", params=params, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error("SerpApi request failed (engine=%s): %s", params.get("engine"), exc)
            return {}

    def search_category(self, category: str) -> list[RawProduct]:
        sort_by = random.choice(["featured", "review_rank", "best_sellers", "date-desc-rank"])
        logger.info("Sorting products by: %s", sort_by)

        used_asins = self.load_used_asins()

        data = self._serpapi_get({
            "engine": "amazon",
            "amazon_domain": "amazon.com",
            "k": category,
            "sort_by": sort_by,
        })

        seen: set[str] = set()
        products: list[RawProduct] = []

        for item in data.get("organic_results", [])[:10]:
            asin = item.get("asin")
            title = item.get("title")
            url = item.get("link")

            if not asin or not title or not url:
                continue

            # skip duplicates in this search
            if asin in seen:
                continue

            # skip products already used in past videos
            if asin in used_asins:
                continue

            seen.add(asin)
            products.append(RawProduct(asin=asin, title=title, url=url))

        return products

    def fetch_product_details(self, url: str, affiliate_tag: str = "logostudios-20") -> Optional[dict]:
        asin = self._extract_asin(url)
        if not asin:
            logger.error("ASIN not found in URL: %s", url)
            return None

        data = self._serpapi_get({
            "engine": "amazon_product",
            "amazon_domain": "amazon.com",
            "asin": asin,
        })
        product = data.get("product_results") or data.get("product") or {}
        if not product:
            logger.warning("No results for ASIN: %s", asin)
            return None

        return {
            "asin": asin,
            "title": product.get("title"),
            "price": product.get("price"),
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
        raw = json.dumps([
            {
                "asin": p.asin,
                "title": p.title,
                "url": p.url
            }
            for p in products
        ])

        response = self._ai("simplify_titles", PRODUCT_ARRAY=raw)

        def _fallback_results() -> list[dict]:
            logger.warning("Falling back to raw product titles due to invalid GPT JSON")
            return [
                {
                    "asin": p.asin,
                    "title": p.title,
                    "url": p.url,
                    "clean_title": p.title,
                    "simple_title": p.title,
                    "isValid": True,
                }
                for p in products
            ]

        try:
            results = robust_json_loads(response)
            if isinstance(results, list):
                return results
        except Exception as exc:
            logger.warning("simplify_titles parse failed, attempting repair: %s", exc)

        repair_prompt = (
            "Fix this into strict valid JSON only. Return a JSON array of objects and nothing else. "
            "Preserve all fields and values exactly as much as possible.\n\n"
            f"{response}"
        )

        try:
            repaired = open_ai_generation(repair_prompt, model="gpt-4o-mini", temperature=0)
            repaired_results = robust_json_loads(repaired)
            if isinstance(repaired_results, list):
                return repaired_results
        except Exception as exc:
            logger.warning("simplify_titles repair parse failed: %s", exc)

        return _fallback_results()
    
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

    def save_used_product(self, asin, clean_title, path=f"{UTILS_PATH}/media/used_products.json"):
        data = []

        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)

        data.append({
            "asin": asin,
            "clean_title": clean_title
        })

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    # ------------------------------------------------------------------ #
    #  Main entry point                                                    #
    # ------------------------------------------------------------------ #

    def _fetch_raw_products(self) -> list[RawProduct]:
        category = self._pick_category(CATEGORY_POOL)
        logger.info("Searching featured products in category: %s", category)
        return self.search_category(category)
    
    def GetProduct(self) -> None:
        raw_results = self._fetch_raw_products()
        logger.debug("Raw results: %s", raw_results)

        simple_products = self._simplify_titles(raw_results)

        valid_products = [p for p in simple_products if p.get("isValid")]

        if not valid_products:
            raise RuntimeError("GPT returned no valid reviewable products")

        logger.debug("valid_products: %s", valid_products)

        random.shuffle(valid_products)
        details = None
        chosen = None
        for candidate in valid_products:
            details = self.fetch_product_details(candidate["url"])
            if details:
                chosen = candidate
                break

        if not details or not chosen:
            raise RuntimeError("Could not fetch details for any valid product")

        combined = {**chosen, **details}

        combined["simple_title"] = (
            combined.get("simple_title")
            or combined.get("clean_title")
            or combined.get("title")
        )
        combined["clean_title"] = combined.get("clean_title") or combined["simple_title"]

        # save to used_products.json
        self.save_used_product(combined["asin"], combined["clean_title"])

        allowed = ProductItem.__annotations__.keys()
        self.pipeline.product = ProductItem(
            **{k: v for k, v in combined.items() if k in allowed}
        )