import os
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

from dotenv import load_dotenv
from supabase import create_client
from telethon.sync import TelegramClient
import parsel  # pip install parsel
import requests

# ================= LOAD ENV =================
BASE_DIR = Path(__file__).parent
ENV_PATH = BASE_DIR / ".env"

print(f"ENV FILE EXISTS: {ENV_PATH.exists()}")

load_dotenv(dotenv_path=ENV_PATH, override=True)
 
# Get env vars
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
TG_API_ID = os.getenv("TG_API_ID")
TG_API_HASH = os.getenv("TG_API_HASH")
TG_CHANNEL = os.getenv("TG_CHANNEL")
THREADS_USERNAME = os.getenv("THREADS_USERNAME")
THREADS_RSS = os.getenv("THREADS_RSS")

print("ENV loaded")

# Clean THREADS_USERNAME
THREADS_USERNAME = THREADS_USERNAME.lstrip('@') if THREADS_USERNAME else None

# Print status (remove in production)
print(f"SUPABASE_URL = {'SET' if SUPABASE_URL else 'MISSING'}")
print(f"SUPABASE_SERVICE_ROLE_KEY = {'SET' if SUPABASE_KEY else 'MISSING'}")
print(f"TG_API_ID = {'SET' if TG_API_ID else 'MISSING'}")
print(f"TG_API_HASH = {'SET' if TG_API_HASH else 'MISSING'}")
print(f"TG_CHANNEL = {'SET' if TG_CHANNEL else 'MISSING'}")
print(f"THREADS_USERNAME = {'SET' if THREADS_USERNAME else 'MISSING'}")

# Check missing vars
missing = []
if not SUPABASE_URL: missing.append("SUPABASE_URL")
if not SUPABASE_KEY: missing.append("SUPABASE_SERVICE_ROLE_KEY")
if not TG_API_ID: missing.append("TG_API_ID")
if not TG_API_HASH: missing.append("TG_API_HASH")
if not TG_CHANNEL: missing.append("TG_CHANNEL")

# THREADS_USERNAME is optional: if missing, we'll skip Threads scraping but allow
# the script to run for Telegram-only syncs. This avoids crashing when Threads
# credentials aren't provided.
if not THREADS_USERNAME and not THREADS_RSS:
    print("WARNING: THREADS_USERNAME and THREADS_RSS not set — skipping Threads fetch")
    THREADS_USERNAME = None
    THREADS_RSS = None

if missing:
    raise RuntimeError(f"Missing environment variables: {missing}")

TG_API_ID = int(TG_API_ID)
print("✅ ENV loaded successfully")

# ================= CLIENTS =================
# Some versions of the gotrue/httpx combination expect a `proxy` kwarg
# when constructing the httpx Client, but recent httpx uses `proxies`.
# Monkey-patch gotrue.SyncClient.__init__ to translate `proxy` -> `proxies`
try:
    from gotrue import http_clients as _gotrue_http_clients

    _orig_init = _gotrue_http_clients.SyncClient.__init__

    def _patched_init(self, *args, proxy=None, **kwargs):
        if proxy is not None and "proxies" not in kwargs:
            kwargs["proxies"] = proxy
        return _orig_init(self, *args, **kwargs)

    _gotrue_http_clients.SyncClient.__init__ = _patched_init
except Exception:
    # If gotrue isn't available yet or patching fails, we'll let the normal
    # error surface when attempting to create the client.
    pass

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================= HELPERS =================
def extract_threads_from_json(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract threads from Threads JSON data structure."""
    threads = []
    # Common nested_lookup patterns for thread_items
    thread_items_candidates = []
    # Possible locations for thread_items
    if isinstance(data, dict):
        if 'data' in data and isinstance(data['data'], dict) and 'thread_items' in data['data']:
            thread_items_candidates.append(data['data']['thread_items'])
        if 'thread_items' in data:
            thread_items_candidates.append(data['thread_items'])

    # Sometimes thread_items are nested deep inside 'require' payloads (as seen
    # in the Playwright-rendered HTML). Walk the structure to find any
    # occurrences of 'thread_items' and add them.
    def find_thread_items(obj):
        res = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == 'thread_items' and isinstance(v, list):
                    res.append(v)
                else:
                    res.extend(find_thread_items(v))
        elif isinstance(obj, list):
            for it in obj:
                res.extend(find_thread_items(it))
        return res

    thread_items_candidates.extend(find_thread_items(data))

    for thread_items in thread_items_candidates:
        # thread_items may be a list of item-lists, or a flat list of items
        for thread_entry in (thread_items if isinstance(thread_items, list) else []):
            # If it's a list of lists
            if isinstance(thread_entry, list):
                for thread in thread_entry:
                    if not isinstance(thread, dict):
                        continue
                    # Old shape: item_type + text_content
                    if thread.get('item_type') == 'TEXT_POST':
                        text = thread.get('text_content', '').strip()
                        tid = thread.get('thread_id') or thread.get('id')
                        if text:
                            threads.append({
                                "platform": "threads",
                                "post_url": f"https://www.threads.net/@{THREADS_USERNAME}/post/{tid}",
                                "content": text,
                                "published_at": datetime.now(timezone.utc).isoformat(),
                            })
                    # Newer shape: each item has a 'post' object with 'text' and 'pk'
                    elif 'post' in thread and isinstance(thread['post'], dict):
                        post = thread['post']
                        text = post.get('text') or post.get('caption') or post.get('caption_add_on') or post.get('accessibility_caption') or ''
                        # If text is structured (dict/list), try to extract a string
                        if isinstance(text, dict):
                            # try common nested keys
                            text = text.get('text') or text.get('rendered') or next((v for v in text.values() if isinstance(v, str)), '')
                        if isinstance(text, list):
                            text = ' '.join([t for t in text if isinstance(t, str)])
                        tid = post.get('pk') or post.get('id')
                        if text:
                            threads.append({
                                "platform": "threads",
                                "post_url": f"https://www.threads.net/@{THREADS_USERNAME}/post/{tid}",
                                "content": text.strip(),
                                "published_at": datetime.now(timezone.utc).isoformat(),
                            })
            else:
                # flat item (dict)
                thread = thread_entry
                if not isinstance(thread, dict):
                    continue
                if thread.get('item_type') == 'TEXT_POST':
                    text = thread.get('text_content', '').strip()
                    tid = thread.get('thread_id') or thread.get('id')
                    if text:
                        threads.append({
                            "platform": "threads",
                            "post_url": f"https://www.threads.net/@{THREADS_USERNAME}/post/{tid}",
                            "content": text,
                            "published_at": datetime.now(timezone.utc).isoformat(),
                        })
                elif 'post' in thread and isinstance(thread['post'], dict):
                    post = thread['post']
                    text = post.get('text') or post.get('caption') or post.get('caption_add_on') or post.get('accessibility_caption') or ''
                    if isinstance(text, dict):
                        text = text.get('text') or text.get('rendered') or next((v for v in text.values() if isinstance(v, str)), '')
                    if isinstance(text, list):
                        text = ' '.join([t for t in text if isinstance(t, str)])
                    tid = post.get('pk') or post.get('id')
                    if text:
                        threads.append({
                            "platform": "threads",
                            "post_url": f"https://www.threads.net/@{THREADS_USERNAME}/post/{tid}",
                            "content": text.strip(),
                            "published_at": datetime.now(timezone.utc).isoformat(),
                        })
    return threads

# ================= THREADS SCRAPER =================
def fetch_threads_posts(username: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetch Threads posts by requesting the public profile page and
    extracting embedded JSON datasets. This avoids running a headful
    browser and should work for public profiles that include the
    application/json[data-sjs] scripts in the HTML.
    """
    posts: List[Dict[str, Any]] = []
    url = f"https://www.threads.net/@{username}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
    except Exception as e:
        print(f"Failed to fetch Threads page: {e}")
        return posts

    if resp.status_code != 200:
        print(f"Threads page returned status {resp.status_code}")
        return posts

    selector = parsel.Selector(resp.text)
    hidden_datasets = selector.css('script[type="application/json"][data-sjs]::text').getall()
    print(f"Found {len(hidden_datasets)} JSON datasets (requests)")

    for hidden_dataset in hidden_datasets:
        try:
            data = json.loads(hidden_dataset)
            new_posts = extract_threads_from_json(data)
            posts.extend(new_posts)
            if len(posts) >= limit:
                break
        except json.JSONDecodeError:
            continue

    # If no posts were found via the static HTML, try a Playwright render
    # fallback (only if playwright is installed and browsers are available).
    if len(posts) == 0:
        print("No posts found via static HTML — trying Playwright fallback")
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            print("Playwright not installed in this environment. To enable a JS-rendered fallback run: python -m pip install playwright && python -m playwright install webkit")
            print(f"Extracted {len(posts)} Threads posts")
            return posts[:limit]

        try:
            # Ensure an event loop exists in this thread. Gradio runs user
            # callbacks inside AnyIO worker threads which may not have an
            # asyncio event loop set — some sync APIs (Playwright) rely on
            # an event loop being available. Create and set one if missing.
            try:
                import asyncio as _asyncio
                _asyncio.get_running_loop()
            except RuntimeError:
                loop = _asyncio.new_event_loop()
                _asyncio.set_event_loop(loop)

            with sync_playwright() as p:
                # Try webkit first (often more compatible on macOS), then chromium
                browser = None
                for browser_name in ("webkit", "chromium"):
                    try:
                        browser = getattr(p, browser_name).launch(headless=True)
                        break
                    except Exception as e:
                        print(f"Failed to launch {browser_name}: {e}")
                        browser = None
                if not browser:
                    print("No Playwright browser could be launched. Run: python -m playwright install webkit")
                    print(f"Extracted {len(posts)} Threads posts")
                    return posts[:limit]

                page = browser.new_page()
                page.goto(url, timeout=60000)
                page.wait_for_timeout(5000)
                content = page.content()
                selector = parsel.Selector(content)
                hidden_datasets = selector.css('script[type="application/json"][data-sjs]::text').getall()
                print(f"(playwright) Found {len(hidden_datasets)} JSON datasets")
                for hidden_dataset in hidden_datasets:
                    try:
                        data = json.loads(hidden_dataset)
                        new_posts = extract_threads_from_json(data)
                        posts.extend(new_posts)
                        if len(posts) >= limit:
                            break
                    except json.JSONDecodeError:
                        continue
                try:
                    browser.close()
                except Exception:
                    pass
        except Exception as e:
            print(f"Playwright fallback failed: {e}")

    print(f"Extracted {len(posts)} Threads posts")
    return posts[:limit]


def fetch_threads_from_rss(rss_url: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetch Threads posts from an RSS/Feed URL (e.g., rsshub) using feedparser."""
    try:
        import feedparser
    except Exception:
        print("feedparser not installed; install with: python -m pip install feedparser")
        return []

    posts: List[Dict[str, Any]] = []
    try:
        feed = feedparser.parse(rss_url)
    except Exception as e:
        print(f"Failed to parse RSS: {e}")
        return posts

    for entry in feed.entries[:limit]:
        posts.append({
            "platform": "threads",
            "post_url": getattr(entry, 'link', ''),
            "content": getattr(entry, 'title', '').strip(),
            "published_at": getattr(entry, 'published', None),
        })

    return posts

# ================= TELEGRAM =================
def fetch_telegram_posts(limit: int = 10) -> List[Dict[str, Any]]:
    posts = []

    with TelegramClient("session", TG_API_ID, TG_API_HASH) as client:
        client.connect()
        if not client.is_user_authorized():
            print("⚠️  Telegram session not authorized. Run interactively first.")
            return posts
        
        print(f"Fetching {limit} Telegram posts from {TG_CHANNEL}")
        for msg in client.iter_messages(TG_CHANNEL, limit=limit):
            if not msg.text:
                continue

            posts.append({
                "platform": "telegram",
                "post_url": f"https://t.me/{TG_CHANNEL}/{msg.id}",
                "content": msg.text,
                "published_at": msg.date.astimezone(timezone.utc).isoformat(),
            })

    return posts

# ================= SAVE =================
def save_posts(posts: List[Dict[str, Any]]) -> str:
    if not posts:
        return "No posts to save"

    # Use the Supabase client execute() return value and check .data
    from postgrest.exceptions import APIError as PostgrestAPIError

    # Try an upsert first using the platform+post_url conflict keys. If the
    # database doesn't have the matching unique constraint, fall back to
    # inserting posts one-by-one and ignore duplicate-key errors.
    try:
        res = supabase.table("posts") \
            .upsert(posts, on_conflict=("platform", "post_url")) \
            .execute()
        if getattr(res, "data", None) is None:
            raise RuntimeError("Supabase upsert failed or returned no data")
        return f"Saved/updated {len(res.data)} posts"
    except PostgrestAPIError as e:
        # If the error indicates ON CONFLICT mismatch (no matching constraint),
        # or other upsert issues, fall back to per-row insert and ignore
        # duplicate-key (23505) errors.
        msg = str(e)
        if "there is no unique or exclusion constraint" in msg or "42P10" in msg:
            inserted = 0
            for p in posts:
                try:
                    r = supabase.table("posts").insert(p).execute()
                    if getattr(r, "data", None):
                        inserted += 1
                except Exception as e2:
                    # 23505 = duplicate key value violates unique constraint
                    if isinstance(e2, Exception) and ("23505" in str(e2) or "duplicate key value" in str(e2).lower()):
                        continue
                    # For other errors re-raise
                    raise
            return f"Inserted {inserted} posts (duplicates skipped)"
        # Unknown API error — re-raise for visibility
        raise

# ================= MAIN =================
if __name__ == "__main__":
    threads_posts = []
    if THREADS_RSS:
        print("📥 Fetching Threads posts from RSS...")
        threads_posts = fetch_threads_from_rss(THREADS_RSS)
    elif THREADS_USERNAME:
        print("📥 Fetching Threads posts...")
        threads_posts = fetch_threads_posts(THREADS_USERNAME)
    else:
        print("Skipping Threads fetch (no THREADS_RSS or THREADS_USERNAME set)")

    print("📥 Fetching Telegram posts...")
    telegram_posts = fetch_telegram_posts()

    all_posts = threads_posts + telegram_posts
    print(f"Total posts: {len(all_posts)}")

    print("💾 Saving to Supabase...")
    result = save_posts(all_posts)
    print(result)

    print("✅ Done")
