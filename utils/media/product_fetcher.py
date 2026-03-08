from utils.core.config import DIR_PATH, DATA_PATH, SOURCE_PATH, UTILS_PATH
from utils.core.settings import CATEGORY_POOL, KEYWORD_AMOUNT
from utils.core.edit import open_ai_generation, robust_json_loads
from utils.media.product_model import ProductItem

import os
from dotenv import load_dotenv
import requests
import ast
import re
import json
import requests
from bs4 import BeautifulSoup
import random




load_dotenv()

class ProductFetcher():

    def __init__(self, pipeline):
        self.pipeline = pipeline

        self.SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")

        with open(f'{UTILS_PATH}/prompts/simplify_titles.txt', 'r') as file:
            self.orignial_simplify_titles_prompt = file.read()

        with open(f'{UTILS_PATH}/prompts/product_selector.txt', 'r') as file:
            self.orignial_product_selector_prompt = file.read()

        with open(f'{UTILS_PATH}/prompts/keyword.txt', 'r') as file:
            self.orignial_keyword_prompt = file.read()

    def generate_affiliate_link(self, asin, affiliate_tag):
        return f"https://www.amazon.com/dp/{asin}?tag={affiliate_tag}"

    def search_movers_shakers(self, serpapi_key):

        CATEGORY_CONFIG = [
            {
                "name": "electronics",
                "google_query": 'site:amazon.com "Movers & Shakers" electronics "gp/movers-and-shakers"',
                "limit": 10
            },
            {
                "name": "computers_accessories",
                "google_query": 'site:amazon.com "Movers & Shakers" "Computers & Accessories" "gp/movers-and-shakers"',
                "limit": 5
            }
        ]

        all_results = []
        seen_asins = set()
        seen_urls = set()
        seen_titles = set()

        def normalize_title(t: str) -> str:
            return t.lower().strip().replace("-", "").replace(",", "")

        asin_re = re.compile(r"/dp/([A-Z0-9]{10})|/gp/product/([A-Z0-9]{10})")

        for category in CATEGORY_CONFIG:

            google_params = {
                "engine": "google",
                "q": category["google_query"],
                "api_key": serpapi_key,
                "num": 5,
            }

            try:
                g = requests.get(
                    "https://serpapi.com/search",
                    params=google_params,
                    timeout=15
                ).json()
            except Exception as e:
                print(f"Google request failed for {category['name']}: {e}")
                continue

            organic = g.get("organic_results", []) or []
            if not organic:
                print(f"No Google results for {category['name']}")
                continue

            target_url = None
            cached_url = None

            for r in organic:
                link = r.get("link", "")
                if "amazon.com" in link and "movers-and-shakers" in link:
                    target_url = link
                    cached_url = r.get("cached_page_link")
                    break

            if not target_url:
                target_url = organic[0].get("link")

            page_url_to_fetch = cached_url or target_url

            try:
                html = requests.get(
                    page_url_to_fetch,
                    timeout=20,
                    headers={"User-Agent": "Mozilla/5.0"}
                ).text
            except Exception as e:
                print(f"Failed HTML fetch for {category['name']}: {e}")
                continue

            soup = BeautifulSoup(html, "html.parser")

            candidates = []

            for a in soup.find_all("a", href=True):
                href = a["href"]
                m = asin_re.search(href)
                if not m:
                    continue

                asin = m.group(1) or m.group(2)

                title = a.get_text(" ", strip=True)

                if not title:
                    img = a.find("img")
                    if img and img.get("alt"):
                        title = img["alt"].strip()

                if not title or len(title) < 6:
                    continue

                if href.startswith("/"):
                    url = "https://www.amazon.com" + href.split("?")[0]
                else:
                    url = href.split("?")[0]

                candidates.append((asin, title, url))

            count = 0

            for asin, title, url in candidates:
                norm = normalize_title(title)

                if asin in seen_asins:
                    continue
                if url in seen_urls:
                    continue
                if norm in seen_titles:
                    continue

                seen_asins.add(asin)
                seen_urls.add(url)
                seen_titles.add(norm)

                all_results.append({
                    "title": title,
                    "url": url,
                })

                count += 1
                if count >= category["limit"]:
                    break

        return all_results
    
    def search_featured(self, category, serpapi_key):

        params = {
            "engine": "amazon",
            "amazon_domain": "amazon.com",
            "k": category,
            "api_key": serpapi_key,
            "sort_by": "featured"
        }

        try:
            response = requests.get(
                "https://serpapi.com/search",
                params=params,
                timeout=10
            )
            data = response.json()
        except Exception as e:
            print(f"Request failed: {e}")
            return []

        results = data.get("organic_results", [])
        if not results:
            return []

        seen_asins = set()
        products = []

        for item in results[:10]:
            asin = item.get("asin")
            title = item.get("title")
            url = item.get("link")

            if not asin or not title or not url:
                continue

            if asin in seen_asins:
                continue

            seen_asins.add(asin)

            products.append({
                "title": title,
                "url": url
            })

        return products
            
    def pick_category(self, category_pool):
        categories = [c["name"] for c in category_pool]
        weights = [c["weight"] for c in category_pool]

        chosen = random.choices(categories, weights=weights, k=1)[0]
        return chosen
    
    def search_catagory(self, serpapi_key):
        catagory = self.pick_category(CATEGORY_POOL)
        print(catagory)
        all_products = self.search_featured(catagory, serpapi_key)
        return all_products
        

    def fetch_product_details(self, url, serpapi_key, affiliate_tag="logostudios-20"):
        """
        Given an Amazon URL:
        - Extract ASIN
        - Fetch title + price via SerpApi Amazon engine
        - Generate affiliate link
        """

        # -------- 1️⃣ Extract ASIN --------
        asin_match = re.search(r"/dp/([A-Z0-9]{10})|/gp/product/([A-Z0-9]{10})", url)
        if not asin_match:
            print("ASIN not found in URL")
            return None

        asin = asin_match.group(1) or asin_match.group(2)

        # -------- 2️⃣ Query SerpApi Amazon Engine --------
        params = {
            "engine": "amazon",
            "amazon_domain": "amazon.com",
            "k": asin,  # search directly by ASIN
            "api_key": serpapi_key
        }

        try:
            response = requests.get(
                "https://serpapi.com/search",
                params=params,
                timeout=10
            )
            data = response.json()
        except Exception as e:
            print(f"SerpApi request failed: {e}")
            return None

        results = data.get("organic_results", [])
        if not results:
            print("No product results returned.")
            return None

        # Usually first result matches ASIN search
        item = results[0]

        title = item.get("title")
        price = item.get("price")

        affiliate_link = self.generate_affiliate_link(asin, affiliate_tag)

        return {
            "asin": asin,
            "title": title,
            "price": price,
            "url": url,
            "affiliate_link": affiliate_link
        }
    
    def _simplify_titles(self, fetched_products):
        fetched_products = json.dumps(fetched_products)
        simplify_titles_prompt = self.orignial_simplify_titles_prompt.replace("{PRODUCT_ARRAY}", str(fetched_products))
        response = open_ai_generation(simplify_titles_prompt, model="gpt-5-mini", temperature=0)
        response = response.strip()
        print("response:", response)

        simple_products = robust_json_loads(response)

        return simple_products 
    
    def _find_best_product(self, product_arr):
        product_arr = json.dumps(product_arr)
        product_selector_prompt = self.orignial_product_selector_prompt.replace("{PRODUCT_ARRAY}", str(product_arr))
        response = open_ai_generation(product_selector_prompt, model="gpt-5-mini", temperature=0)
        response = response.strip()
        
        selected = robust_json_loads(response)

        return selected 

            
    def generate_keywords(self, product):
        keyword_prompt = (self.orignial_keyword_prompt
            .replace("{product}", product)
            .replace("{low}", KEYWORD_AMOUNT["low"])
            .replace("{high}", KEYWORD_AMOUNT["high"])
        )
        keyword_str = open_ai_generation(keyword_prompt, model="gpt-5-mini", temperature=0.2)
        keyword_arr = ast.literal_eval(keyword_str)


        self.pipeline.keywords = keyword_arr

    def GetProduct(self):     
        # # raw_results = self.search_catagory(self.SERPAPI_API_KEY)
        # raw_results = self.search_movers_shakers(self.SERPAPI_API_KEY)

        # # if random.random() < 0.5:
        # #     raw_results = self.search_catagory(self.SERPAPI_API_KEY)
        # # else:
        # #     raw_results = self.search_movers_shakers(self.SERPAPI_API_KEY)
        # print("raw_results:", raw_results)

        # simple_products = self._simplify_titles(raw_results)
        # print("simple_products:", simple_products)

        # best_products = self._find_best_product(simple_products)

        # chosen_product = random.choice(best_products)

        # product_info = self.fetch_product_details(chosen_product["url"], self.SERPAPI_API_KEY)
        # combined = chosen_product | product_info
        # print("combined:", combined)

        # combined = ProductItem(title='Bambu Lab P1S 3D Printer, Fully Enclosed, Support Up to 16 Colors/Multi Materials, 500mm/s Fast Printing & High Precision, CoreXY & Auto Bed Leveling, Ready-to-Use FDM 3D Printers Large Print Size', simple_title='Bambu Lab P1S 3D Printer', price='$449.00', asin='B0CHDM8VVZ', url='https://www.amazon.com/P1S-Enclosed-Materials-Printing-Precision/dp/B0CHDM8VVZ/ref=sr_1_6?dib=eyJ2IjoiMSJ9.hII_b9f0CnDiVQDdIho_7Cj1ptrONhulhq9eoan4HS5viitl0KrcP2N35tf8Q4OIfLB3ddC2E-q_bHKPf19wqDHk5S-1B2YF_jFUYK1wBATgWV3D8nUSThaMiJZm3zvyGa-2q3y73N1jLREzRfyKE2MN2v_E55SRHHh_FsT8Afa-2LucfPC8wwON6eSnxV8BTGTMh0GJyFkcg55Rs6Yi1zXeYth8xMwFrG6_I7z0i0A.1uGSiFzzmvuA6jealDUC2Cc5Rf8sI-dhFS5XXoOvQ_g&dib_tag=se&keywords=3D+Printers&qid=1772159785&sr=8-6', affiliate_link='https://www.amazon.com/dp/B0CHDM8VVZ?tag=logostudios-20')
        combined = {'url': 'https://www.amazon.com/Oura-Ring-Ceramic-Cloud-Before/dp/B0FKQZ3QDB/ref=zg_bsms_g_electronics_d_sccl_8/145-1241867-4089513', 'simple_title': 'Oura Ring 4 Ceramic Cloud', 'asin': 'B0FKQZ3QDB', 'title': 'Oura Ring 4 Ceramic Cloud - Size 4 - Size Before You Buy', 'price': '$499.00', 'affiliate_link': 'https://www.amazon.com/dp/B0FKQZ3QDB?tag=logostudios-20'}
        allowed_fields = ProductItem.__annotations__.keys()

        filtered = {k: v for k, v in combined.items() if k in allowed_fields}

        self.pipeline.product = ProductItem(**filtered)

        return None      
            










