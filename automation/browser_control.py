"""
browser_control.py - Browser and web control tools for JARVIS
Opens URLs, searches the web, and navigates to popular websites.
"""

import logging
import subprocess
import webbrowser
from urllib.parse import quote_plus, urlparse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known website shortcuts
# ---------------------------------------------------------------------------
SITE_MAP: dict[str, str] = {
    # Search & Productivity
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "google drive": "https://drive.google.com",
    "google docs": "https://docs.google.com",
    "google sheets": "https://sheets.google.com",
    "google calendar": "https://calendar.google.com",
    "google maps": "https://maps.google.com",
    "translate": "https://translate.google.com",
    # Microsoft
    "outlook": "https://outlook.live.com",
    "outlook mail": "https://outlook.live.com",
    "onedrive": "https://onedrive.live.com",
    "office": "https://www.office.com",
    "teams": "https://teams.microsoft.com",
    "bing": "https://www.bing.com",
    # Social
    "youtube": "https://www.youtube.com",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "linkedin": "https://www.linkedin.com",
    "reddit": "https://www.reddit.com",
    "discord": "https://discord.com/channels/@me",
    # Dev
    "github": "https://github.com",
    "gitlab": "https://gitlab.com",
    "stackoverflow": "https://stackoverflow.com",
    "stack overflow": "https://stackoverflow.com",
    "hugging face": "https://huggingface.co",
    "kaggle": "https://www.kaggle.com",
    # News
    "bbc": "https://www.bbc.com",
    "cnn": "https://www.cnn.com",
    "hackernews": "https://news.ycombinator.com",
    "hacker news": "https://news.ycombinator.com",
    # Entertainment / Shopping
    "netflix": "https://www.netflix.com",
    "spotify": "https://open.spotify.com",
    "amazon": "https://www.amazon.com",
    "ebay": "https://www.ebay.com",
    "wikipedia": "https://www.wikipedia.org",
    # AI tools
    "chatgpt": "https://chat.openai.com",
    "openai": "https://openai.com",
    "claude": "https://claude.ai",
    "gemini": "https://gemini.google.com",
    "perplexity": "https://www.perplexity.ai",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_scheme(url: str) -> str:
    """Add https:// if the URL has no scheme."""
    if not url.startswith(("http://", "https://", "ftp://", "file://")):
        return "https://" + url
    return url


def _open_with_subprocess(url: str) -> bool:
    """Try opening URL with common browsers via subprocess."""
    browsers = [
        ["explorer.exe", url],  # Windows default fallback
    ]
    for cmd in browsers:
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            continue
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def open_url(url: str) -> dict:
    """
    Open a URL in the default browser.

    Args:
        url: Full URL (scheme optional; https:// is assumed).

    Returns:
        dict with success, url, message or error.
    """
    url = _ensure_scheme(url.strip())
    try:
        # Validate URL minimally
        parsed = urlparse(url)
        if not parsed.netloc and not parsed.path:
            return {"success": False, "error": f"Invalid URL: {url}"}

        opened = webbrowser.open(url)
        if opened:
            logger.info("Opened URL: %s", url)
            return {"success": True, "url": url, "message": f"Opened: {url}"}
        # webbrowser.open can return False when no browser is registered
        raise RuntimeError("webbrowser.open returned False")
    except Exception as e:
        logger.warning("webbrowser failed (%s), trying subprocess", e)
        if _open_with_subprocess(url):
            return {"success": True, "url": url, "message": f"Opened via system: {url}"}
        return {"success": False, "url": url, "error": str(e)}


def google_search(query: str) -> dict:
    """
    Open a Google search for query in the default browser.

    Args:
        query: Search terms.

    Returns:
        dict with success, query, url, message or error.
    """
    encoded = quote_plus(query.strip())
    url = f"https://www.google.com/search?q={encoded}"
    result = open_url(url)
    result["query"] = query
    return result


def youtube_search(query: str) -> dict:
    """
    Open a YouTube search for query.

    Args:
        query: Search terms.

    Returns:
        dict with success, query, url, message or error.
    """
    encoded = quote_plus(query.strip())
    url = f"https://www.youtube.com/results?search_query={encoded}"
    result = open_url(url)
    result["query"] = query
    return result


def youtube_play(query: str) -> dict:
    """Alias for youtube_search — JARVIS will phrase result as 'playing'."""
    result = youtube_search(query)
    if result["success"]:
        result["message"] = f"Searching YouTube for '{query}'"
    return result


def open_website(site_name: str) -> dict:
    """
    Open a well-known website by its friendly name.

    Args:
        site_name: Common name e.g. 'GitHub', 'YouTube', 'ChatGPT'.

    Returns:
        dict with success, site, url, message or error.
    """
    key = site_name.strip().lower()
    url = SITE_MAP.get(key)

    if url is None:
        # Try partial match
        for k, v in SITE_MAP.items():
            if key in k or k in key:
                url = v
                break

    if url is None:
        # Treat as a domain/URL directly
        url = _ensure_scheme(site_name)

    result = open_url(url)
    result["site"] = site_name
    return result


def search_web(query: str, engine: str = "google") -> dict:
    """
    Search the web using a specified engine.

    Args:
        query:  Search query.
        engine: 'google' | 'bing' | 'duckduckgo' | 'youtube'.

    Returns:
        dict with success, query, engine, url, message or error.
    """
    engine = engine.strip().lower()
    encoded = quote_plus(query.strip())

    engine_urls: dict[str, str] = {
        "google": f"https://www.google.com/search?q={encoded}",
        "bing": f"https://www.bing.com/search?q={encoded}",
        "duckduckgo": f"https://duckduckgo.com/?q={encoded}",
        "ddg": f"https://duckduckgo.com/?q={encoded}",
        "youtube": f"https://www.youtube.com/results?search_query={encoded}",
    }

    url = engine_urls.get(engine)
    if url is None:
        return {"success": False, "error": f"Unknown search engine: '{engine}'. Use: google, bing, duckduckgo, youtube"}

    result = open_url(url)
    result["query"] = query
    result["engine"] = engine
    return result


def open_new_tab(url: str) -> dict:
    """
    Open URL in a new browser tab (best-effort; depends on OS/browser).

    Args:
        url: URL to open.

    Returns:
        dict with success, url, message or error.
    """
    url = _ensure_scheme(url.strip())
    try:
        webbrowser.open_new_tab(url)
        return {"success": True, "url": url, "message": f"Opened new tab: {url}"}
    except Exception as e:
        return open_url(url)  # Fallback


def add_site(name: str, url: str) -> dict:
    """
    Register a new site shortcut at runtime.

    Args:
        name: Friendly name (e.g. 'my company').
        url:  Full URL.

    Returns:
        dict with success, message.
    """
    SITE_MAP[name.strip().lower()] = _ensure_scheme(url.strip())
    return {"success": True, "message": f"Registered site '{name}' -> {url}"}


class BrowserControlResult:
    """Wrapper result object for BrowserControl methods."""
    def __init__(self, success: bool, message: str, data: dict | None = None) -> None:
        self.success = success
        self.message = message
        self.data = data or {}

    def __repr__(self) -> str:
        return f"<BrowserControlResult success={self.success} message='{self.message}'>"


class BrowserControl:
    """Object-oriented interface for web and browser automation."""

    def open_url(self, url: str) -> BrowserControlResult:
        res = open_url(url)
        msg = res.get("message") or res.get("error", "")
        return BrowserControlResult(success=res.get("success", False), message=msg, data=res)

    def google_search(self, query: str) -> BrowserControlResult:
        res = google_search(query)
        msg = res.get("message") or res.get("error", "")
        return BrowserControlResult(success=res.get("success", False), message=msg, data=res)

    def youtube_search(self, query: str) -> BrowserControlResult:
        res = youtube_search(query)
        msg = res.get("message") or res.get("error", "")
        return BrowserControlResult(success=res.get("success", False), message=msg, data=res)

    def open_website(self, site_name: str) -> BrowserControlResult:
        res = open_website(site_name)
        msg = res.get("message") or res.get("error", "")
        return BrowserControlResult(success=res.get("success", False), message=msg, data=res)

