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
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class ProductFetcher:

    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.serpapi_key = os.getenv("SHEARS_SERPAPI_API_KEY")
        self._prompts = self._load_prompts()

    # ------------------------------------------------------------------ #
    #  Setup                                                               #
    # ------------------------------------------------------------------ #

    def _load_prompts(self) -> dict[str, str]:
        names = ["simplify_titles", "product_type", "keyword"]
        prompts = {}
        for name in names:
            with open(f"{UTILS_PATH}/prompts/{name}.txt") as f:
                prompts[name] = f.read()
        return prompts

    def _prompt(self, name: str, **replacements) -> str:
        text = self._prompts[name]
        for key, value in replacements.items():
            text = text.replace(f"{{{key}}}", str(value))
        return text

    def load_used_asins(self, path=f"{UTILS_PATH}/media/used_products.json") -> set:
        if not os.path.exists(path):
            return set()
        with open(path) as f:
            return {p["asin"] for p in json.load(f)}

    def save_used_product(self, asin, clean_title, path=f"{UTILS_PATH}/media/used_products.json"):
        data = []
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
        data.append({"asin": asin, "clean_title": clean_title})
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    # ------------------------------------------------------------------ #
    #  Amazon                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _affiliate_link(asin: str, tag: str = "logostudios-20") -> str:
        return f"https://www.amazon.com/dp/{asin}?tag={tag}"

    _PRICE_RE = re.compile(r'\$\s*\d{1,4}(?:\.\d{2})?')

    @staticmethod
    def _parse_price(item: dict, title: str) -> str:
        for key in ("price", "price_string", "extracted_price"):
            val = item.get(key)
            if val:
                return str(val)
        m = ProductFetcher._PRICE_RE.search(title)
        return m.group() if m else ""

    @staticmethod
    def _pick_category(pool: list[dict]) -> str:
        names = [c["name"] for c in pool]
        weights = [c["weight"] for c in pool]
        return random.choices(names, weights=weights, k=1)[0]

    def _serpapi_get(self, params: dict, timeout: int = 30) -> dict:
        params["api_key"] = self.serpapi_key
        try:
            resp = requests.get("https://serpapi.com/search", params=params, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error("SerpApi request failed (engine=%s): %s", params.get("engine"), exc)
            return {}

    def search_category(self, category: str) -> list[dict]:
        sort_by = random.choice(["best_sellers", "date-desc-rank"])
        logger.info("Searching category '%s' sorted by: %s", category, sort_by)

        used_asins = self.load_used_asins()
        data = self._serpapi_get({
            "engine": "amazon",
            "amazon_domain": "amazon.com",
            "k": category,
            "sort_by": sort_by,
        })

        seen: set[str] = set()
        products: list[dict] = []

        for item in data.get("organic_results", [])[:10]:
            asin = item.get("asin")
            title = item.get("title")
            url = item.get("link")

            if not asin or not title or not url:
                continue
            if asin in seen or asin in used_asins:
                continue

            seen.add(asin)
            products.append({
                "asin": asin,
                "title": title,
                "url": url,
                "price": self._parse_price(item, title),
            })

        return products

    # ------------------------------------------------------------------ #
    #  AI steps                                                            #
    # ------------------------------------------------------------------ #

    def _ai(self, prompt_name: str, model: str = "gpt-4o-mini",
            temperature: float = 0, **replacements) -> str:
        prompt = self._prompt(prompt_name, **replacements)
        return open_ai_generation(prompt, model=model, temperature=temperature).strip()

    @staticmethod
    def _trim_title(title: str) -> str:
        return title.split(",")[0].strip()

    def _simplify_titles(self, products: list[dict]) -> list[dict]:
        raw = json.dumps([{"asin": p["asin"], "title": p["title"], "url": p["url"]} for p in products])
        response = self._ai("simplify_titles", PRODUCT_ARRAY=raw)

        by_url = {p["url"]: p for p in products}

        try:
            results = robust_json_loads(response)
            if isinstance(results, list):
                return [
                    {
                        **by_url.get(r.get("url"), {}),
                        **r,
                        "clean_title": self._trim_title(r.get("clean_title") or r.get("title", "")),
                    }
                    for r in results
                ]
        except Exception as exc:
            logger.warning("simplify_titles parse failed, using raw titles: %s", exc)

        return [{**p, "clean_title": self._trim_title(p["title"]), "isValid": True} for p in products]

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
    #  YouTube scoring                                                     #
    # ------------------------------------------------------------------ #

    def _youtube_score(self, simple_title: str) -> float:
        """Avg views of recent (90 day) YouTube reviews. High = proven demand."""
        try:
            import yt_dlp

            cutoff = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")
            ydl_opts = {"quiet": True, "no_warnings": True, "extract_flat": True}

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(f"ytsearch10:{simple_title} review", download=False)

            entries = result.get("entries") or []
            recent_views = sorted(
                e.get("view_count") or 0
                for e in entries
                if (e.get("upload_date") or "0") >= cutoff
            )

            if not recent_views:
                return 0.0

            # median is more robust than mean against one viral outlier
            mid = len(recent_views) // 2
            median = (recent_views[mid] + recent_views[~mid]) / 2

            # confidence ramps up to 1.0 at 3+ videos — penalises single-video flukes
            confidence = min(len(recent_views) / 3, 1.0)

            return median * confidence

        except Exception as e:
            logger.warning("YouTube scoring failed for '%s': %s", simple_title, e)
            return 0.0

    def _rank_by_youtube(self, candidates: list[dict]) -> list[dict]:
        """Score top 5 candidates in parallel, return sorted best-first."""
        top, rest = candidates[:5], candidates[5:]
        print(f"[YouTube] Scoring {len(top)} candidates...")

        titles = [c.get("clean_title") or c.get("title", "") for c in top]
        with ThreadPoolExecutor(max_workers=5) as executor:
            scores = list(executor.map(self._youtube_score, titles))

        ranked = sorted(zip(scores, top), key=lambda x: x[0], reverse=True)
        for score, c in ranked:
            print(f"  [{score:,.0f} avg views] {c.get('clean_title')}")
        return [c for _, c in ranked] + rest

    # ------------------------------------------------------------------ #
    #  Main entry point                                                    #
    # ------------------------------------------------------------------ #

    def get_product(self) -> None:
        category = self._pick_category(CATEGORY_POOL)
        raw_products = self.search_category(category)

        if not raw_products:
            raise RuntimeError(f"No products found for category: {category}")

        enriched = self._simplify_titles(raw_products)
        valid = [p for p in enriched if p.get("isValid")]

        if not valid:
            raise RuntimeError("No valid reviewable products found")

        ranked = self._rank_by_youtube(valid)
        product = ranked[0]
        # product = {'asin': 'B07RCNB2L3', 'title': 'Kasa Smart Plug HS103P4, Smart Home Wi-Fi Outlet Works with Alexa, Echo, Google Home & IFTTT, No Hub Required, Remote Control, 15 Amp, UL Certified, 4-Pack, White', 'url': 'https://www.amazon.com/TP-Link-Kasa-Smart-Wifi-Plug/dp/B07RCNB2L3/ref=sr_1_6?dib=eyJ2IjoiMSJ9.7hTYyfetPWQxEPVfu0xXQ7CKQo8onnnmdY4UocmvGW5GoO-YuQRTdJFfCErcV7Rc-D_vMhSX-iJP6Mzukjz6UBiOK98EaRmPZu1v5S7R3UQjvxyNBJMwqUyJTw-DI3-0ZZlczuJcbe4GvRfqJEAqCWTzsJBrnWEuv1pjZZjmxf2jqZmhI507wihnFJkYTTDXT9NHdbk_XqzvkYB_zk_4yJFO9u4xiyQICI_LaS_iSbtc1kH4szrR2mYz7zSAo89Si9D_EZXAoJlznL7wTPOEcFq45CIY9bqUjGeR4B7DMik.-PFc_xJa1OIp5t-1sdOqiRrnG38D-K8JXS99fyV7c3c&dib_tag=se&keywords=Smart+Home+Devices&qid=1774010429&sr=8-6', 'price': '$26.99', 'clean_title': 'Kasa Smart Plug HS103P4', 'isValid': True}
        # print("product", product)

        self.save_used_product(product["asin"], product["clean_title"])

        self.pipeline.product = ProductItem(
            asin=product["asin"],
            title=product["title"],
            simple_title=product["clean_title"],
            price=product.get("price") or "",
            url=product["url"],
            affiliate_link=self._affiliate_link(product["asin"]),
        )
