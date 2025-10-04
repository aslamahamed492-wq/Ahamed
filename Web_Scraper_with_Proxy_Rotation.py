# Web_Scraper_with_Proxy_Rotation.py
"""
Web Scraper with Proxy Rotation (single-file)
- ProxyManager: manage, probe, rotate, and blacklist proxies
- CaptchaSolver: adapter for third-party solvers (minimal/stub)
- Scraper: fetch pages using rotating proxies, UA rotation, retries/backoff, parse & save
- Basic parser and CLI to run a URL list and export JSON/CSV

USAGE:
    python Web_Scraper_with_Proxy_Rotation.py --urls urls.txt --output-json results.json --output-csv results.csv
Or single url:
    python Web_Scraper_with_Proxy_Rotation.py --url "https://httpbin.org/html"
"""
import argparse
import random
import time
import json
import csv
import os
import threading
import logging
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# --------------------------
# Logging
# --------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# --------------------------
# ProxyManager
# --------------------------
class ProxyInfo:
    def __init__(self, proxy_str: str):
        self.proxy = proxy_str
        self.last_checked = 0.0
        self.successes = 0
        self.failures = 0
        self.avg_latency = None
        self.lock = threading.Lock()
        self.blacklisted = False

    def score(self) -> float:
        fails = self.failures + 1
        latency = self.avg_latency or 5.0
        return latency * (fails / (self.successes + 1))

class ProxyManager:
    def __init__(self, proxies: Optional[List[str]] = None, probe_url: str = "https://httpbin.org/get", timeout: float = 8.0):
        self._proxies: Dict[str, ProxyInfo] = {}
        self.probe_url = probe_url
        self.timeout = timeout
        if proxies:
            for p in proxies:
                self.add_proxy(p)

    def add_proxy(self, proxy_str: str):
        if proxy_str in self._proxies:
            return
        self._proxies[proxy_str] = ProxyInfo(proxy_str)
        logging.debug(f"Added proxy: {proxy_str}")

    def remove_proxy(self, proxy_str: str):
        if proxy_str in self._proxies:
            del self._proxies[proxy_str]

    def list_proxies(self) -> List[str]:
        return list(self._proxies.keys())

    def probe_proxy(self, proxy_str: str) -> bool:
        info = self._proxies.get(proxy_str)
        if not info:
            return False
        proxies = {"http": proxy_str, "https": proxy_str}
        t0 = time.time()
        try:
            r = requests.get(self.probe_url, proxies=proxies, timeout=self.timeout)
            latency = time.time() - t0
            with info.lock:
                info.last_checked = time.time()
                info.successes += 1
                info.avg_latency = ((info.avg_latency or latency) + latency) / 2.0
                info.blacklisted = False
            logging.debug(f"Probe ok: {proxy_str} latency={latency:.2f}s")
            return True
        except Exception as e:
            with info.lock:
                info.last_checked = time.time()
                info.failures += 1
                if info.failures > max(3, info.successes * 3):
                    info.blacklisted = True
            logging.debug(f"Probe failed: {proxy_str} ({e})")
            return False

    def bulk_probe(self, timeout_per: float = 0.2):
        for p in list(self._proxies.keys()):
            self.probe_proxy(p)
            time.sleep(timeout_per)

    def get_proxy(self, allow_blacklisted: bool = False) -> Optional[str]:
        candidates = [pi for pi in self._proxies.values() if (allow_blacklisted or not pi.blacklisted)]
        if not candidates:
            return None
        unprobed = [c for c in candidates if c.last_checked == 0]
        if unprobed:
            chosen = random.choice(unprobed).proxy
            logging.debug(f"Chose unprobed proxy: {chosen}")
            return chosen
        candidates.sort(key=lambda p: p.score())
        top_n = max(1, min(5, len(candidates)))
        chosen = random.choice(candidates[:top_n]).proxy
        logging.debug(f"Chose proxy by score: {chosen}")
        return chosen

    def report(self, proxy_str: Optional[str], success: bool, latency: Optional[float] = None):
        if not proxy_str:
            return
        info = self._proxies.get(proxy_str)
        if not info:
            return
        with info.lock:
            if success:
                info.successes += 1
                if latency:
                    info.avg_latency = ((info.avg_latency or latency) + latency) / 2.0
            else:
                info.failures += 1
                if info.failures > 10:
                    info.blacklisted = True

    def blacklist(self, proxy_str: str):
        info = self._proxies.get(proxy_str)
        if info:
            info.blacklisted = True

# --------------------------
# CaptchaSolver (minimal adapter)
# --------------------------
class CaptchaSolver:
    """
    Minimal adapter for third-party captcha solvers (e.g., 2Captcha / Anti-Captcha).
    This is a stubbed example — requires API key & provider-specific implementation.
    """

    def __init__(self, api_key: Optional[str] = None, provider: str = "2captcha"):
        self.api_key = api_key
        self.provider = provider

    def submit_image(self, image_bytes: bytes) -> Optional[str]:
        """
        Submit image captcha and return task_id. Requires real provider implementation.
        """
        raise NotImplementedError("Add provider-specific code or instantiate with real implementation.")

    def get_solution(self, task_id: str, poll_interval: int = 5, max_wait: int = 120) -> Optional[str]:
        """
        Poll for solution. Provider dependent.
        """
        raise NotImplementedError("Add provider-specific code or instantiate with real implementation.")

# --------------------------
# Scraper
# --------------------------
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117 Safari/537.36",
]

class Scraper:
    def __init__(self,
                 proxy_manager: Optional[ProxyManager] = None,
                 captcha_solver: Optional[CaptchaSolver] = None,
                 output_dir: str = "data",
                 max_retries: int = 5,
                 rate_limit: float = 0.5):
        self.proxy_manager = proxy_manager or ProxyManager([])
        self.captcha_solver = captcha_solver
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.max_retries = max_retries
        self.rate_limit = rate_limit
        self.session = requests.Session()

    def _make_headers(self) -> Dict[str, str]:
        ua = random.choice(USER_AGENTS)
        headers = {
            "User-Agent": ua,
            "Accept-Language": random.choice(["en-US,en;q=0.9", "en-GB,en;q=0.9", "en;q=0.8"]),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        return headers

    def _detect_captcha(self, text: str, status_code: int) -> bool:
        if status_code in (403, 429):
            return True
        lowered = text.lower()
        signs = ["captcha", "recaptcha", "hcaptcha", "please verify", "are you human"]
        return any(s in lowered for s in signs)

    def _save_raw(self, url: str, html: str):
        safe = url.replace("://", "_").replace("/", "_")[:240]
        fname = os.path.join(self.output_dir, f"raw_{safe}.html")
        with open(fname, "w", encoding="utf-8") as f:
            f.write(html)

    def _default_parse(self, html: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        return {"title": title, "length": len(html)}

    def fetch(self, url: str, parser: Optional[Callable[[str], Dict[str, Any]]] = None) -> Dict[str, Any]:
        last_exc = None
        for attempt in range(self.max_retries):
            proxy = self.proxy_manager.get_proxy()
            proxies = {"http": proxy, "https": proxy} if proxy else None
            headers = self._make_headers()
            try:
                t0 = time.time()
                r = self.session.get(url, headers=headers, proxies=proxies, timeout=15)
                latency = time.time() - t0
                success = (r.status_code == 200)
                self.proxy_manager.report(proxy, success, latency) if proxy else None

                if self._detect_captcha(r.text, r.status_code):
                    logging.warning(f"Detected captcha/block at {url} (status={r.status_code}) using proxy={proxy}")
                    self.proxy_manager.report(proxy, False, latency)
                    # option: try captcha solver when available (not implemented fully here)
                    raise Exception("CAPTCHA or block detected")

                r.raise_for_status()
                parsed = parser(r.text) if parser else self._default_parse(r.text)
                self._save_raw(url, r.text)
                # polite pause
                time.sleep(self.rate_limit + random.random() * 0.5)
                return {"url": url, "status": "ok", "data": parsed, "proxy": proxy}
            except Exception as e:
                last_exc = e
                logging.debug(f"Fetch attempt {attempt+1} failed for {url} with proxy={proxy}: {e}")
                # exponential backoff + jitter
                sleep_for = (2 ** attempt) + random.random()
                time.sleep(sleep_for)
                if proxy:
                    self.proxy_manager.report(proxy, False)
                continue
        logging.error(f"Failed to fetch {url} after {self.max_retries} attempts: {last_exc}")
        return {"url": url, "status": "failed", "error": str(last_exc)}
...
