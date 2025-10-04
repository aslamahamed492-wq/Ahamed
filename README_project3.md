# Project 3 — Web Scraper with Proxy Rotation

## 📌 Project Description
Build a robust web scraper that rotates proxies to bypass geo-restrictions and anti-bot defenses, detects and handles CAPTCHAs using third-party solving services, implements retry strategies and backoff, and extracts structured data (JSON/CSV) while minimizing detection risk.

---

## 🧭 Responsibilities / Requirements
1. **Proxy Management System**
   - Source and validate HTTP/HTTPS/SOCKS proxies (free or paid).
   - Implement rotating proxy logic with automatic failover and health metrics (latency, success rate, anonymity).
   - Blacklist dead/unreliable proxies automatically.

2. **HTTP Request Handling**
   - Send requests through rotating proxies using `requests` (sync) or `aiohttp` (async).
   - Rotate `User-Agent` headers and randomize other fingerprinting headers per request.
   - Maintain session cookies across proxy switches when needed.

3. **CAPTCHA Solving Integration**
   - Detect CAPTCHAs in HTML responses and take automated action.
   - Integrate with services like 2Captcha / Anti-Captcha (submit → poll → apply solution).
   - Implement timeouts, cost tracking, and safe retry behavior.

4. **HTML Parsing & Data Extraction**
   - Parse with `BeautifulSoup` or `lxml` using CSS selectors / XPath.
   - Extract structured data; export to JSON and CSV formats.
   - Optionally support JavaScript rendering via Selenium / Playwright when necessary.

5. **Resilience & Stealth**
   - Exponential backoff and retry strategies for transient errors (403/429/503).
   - Randomize request intervals and mimic human-like patterns.
   - Implement honeypot avoidance and request throttling to reduce detection risk.

---

## 🧩 Architecture & Key Components
- **Proxy Manager (class)**
  - Fetch/parse proxy lists, support authenticated proxies.
  - Probe proxies (latency, anonymity tests), maintain health scores.
  - Provide `get_proxy()` with rotation + failover and `report(proxy, success)` API.

- **HTTP Engine / Session Manager**
  - Wrapper around `requests.Session` or `aiohttp.ClientSession` to:
    - Rotate proxies and headers per request.
    - Handle cookies, persistent sessions, and per-proxy sessions where needed.
    - Provide automatic retries with exponential backoff and jitter.

- **CAPTCHA Solver Module**
  - Abstraction over third-party solver APIs (2Captcha, Anti-Captcha):
    - `submit_captcha(image_or_sitekey, proxy=None) -> task_id`
    - `get_solution(task_id) -> solution_string|None`
  - Detect captcha types (image, reCAPTCHA v2/v3, hCaptcha) and adapt.

- **Parser / Extractor**
  - Configurable parsers (CSS/XPath) for each target site.
  - Data validation, normalization and output to JSON/CSV.

- **Stealth Module**
  - User-Agent rotation list, header fuzzing, Accept-Language rotation.
  - Request timing (random sleep, human-like intervals) and optional mouse/keyboard simulation for browser-based scraping.

- **Storage & Output**
  - Save raw pages, structured output, and logs.
  - Maintain per-proxy telemetry and scraping metrics for analysis.

---

## 🔧 Example (Simplified) — Core Flow (sync requests)
```python
import random, time, requests
from bs4 import BeautifulSoup

PROXIES = ["http://user:pass@1.2.3.4:8080", "socks5://5.6.7.8:9050"]
USER_AGENTS = ["Mozilla/5.0 ...", "Mozilla/5.0 (Macintosh) ..."]

def get_proxy():
    return random.choice(PROXIES)

def fetch(url):
    for attempt in range(5):
        proxy = get_proxy()
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        try:
            r = requests.get(url, proxies={"http": proxy, "https": proxy}, headers=headers, timeout=10)
            if "captcha" in r.text.lower():
                # Integrate CAPTCHA solver workflow here
                raise Exception("CAPTCHA detected")
            r.raise_for_status()
            return r.text
        except requests.RequestException:
            time.sleep(2 ** attempt + random.random())
    raise RuntimeError("Failed after retries")
```

---

## ⚙️ Implementation Best Practices & Tips
- Use **connection pooling** and sessions to reuse TCP connections for speed and stealth.
- Always **respect robots.txt** and target sites' ToS—avoid illegal scraping.
- Mask repetitive fingerprints: rotate headers, vary intervals, and avoid fixed patterns.
- Rate-limit per domain and implement **circuit-breakers** for persistent failures.
- Use **atomic writes** when saving scraped data to avoid corruption on crashes.
- Track proxy costs and solver costs; place caps to avoid runaway bills.

---

## ✅ Outputs & Deliverables
- `proxy_manager.py` — proxy pool, probing, rotation
- `scraper.py` — scraping engine with retry/backoff and parser hooks
- `captcha_solver.py` — integration module for third-party solvers
- `parsers/` — site-specific extraction rules (CSS/XPath)
- `data/` — saved raw pages and exported JSON/CSV results
- `logs/` — telemetry, proxy metrics, error reports

---

## ⚠️ Legal & Ethical Considerations
- Confirm that scraping a target site is allowed by its Terms of Service and your local laws.
- Avoid harvesting personal data without consent.
- Use throttling and respectful crawling to prevent service disruption.

---

## 🎯 Learning Outcomes
- Build advanced HTTP clients with proxy rotation and session management.
- Integrate external CAPTCHA solving services and manage costs/latency.
- Design fault-tolerant scraping pipelines with retry/backoff and failover.
- Implement stealth techniques and understand anti-bot countermeasures.
- Export clean, validated datasets for downstream use.

---

## 📌 Next Steps / Extensions
- Add async support with `aiohttp` and concurrency control.
- Build a web UI to monitor proxies, success rates, and scraped data.
- Integrate Puppeteer/Playwright for better JS rendering and stealth automation.
- Add distributed scraping with a task queue (Redis + Celery / RQ).

---
