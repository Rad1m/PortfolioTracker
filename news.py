"""Financial news feed — Google News RSS, portfolio-aware."""

import time
import webbrowser
from dataclasses import dataclass
from urllib.parse import quote

import feedparser

# In-memory cache
_cache: dict[str, tuple[float, list]] = {}
CACHE_TTL = 300  # 5 minutes, same as market data


@dataclass
class NewsItem:
    ticker: str
    title: str
    url: str
    published: str  # human-readable relative time
    source: str
    timestamp: float = 0.0  # epoch for sorting


def _relative_time(published_parsed) -> tuple[str, float]:
    """Convert feedparser time struct to relative time string + epoch."""
    if not published_parsed:
        return "just now", time.time()
    epoch = time.mktime(published_parsed)
    diff = time.time() - epoch
    if diff < 3600:
        mins = max(1, int(diff / 60))
        return f"{mins}m ago", epoch
    if diff < 86400:
        hours = int(diff / 3600)
        return f"{hours}h ago", epoch
    days = int(diff / 86400)
    return f"{days}d ago", epoch


def _extract_source(title: str) -> tuple[str, str]:
    """Google News titles end with ' - Source Name'. Split them."""
    if " - " in title:
        parts = title.rsplit(" - ", 1)
        return parts[0].strip(), parts[1].strip()
    return title, ""


def _search_term(ticker: str, name: str) -> str:
    """Build a Google News search term for a ticker.

    For well-known US tickers (no suffix), use the ticker symbol.
    For European ETFs / funds with suffixes or ISIN-like IDs, use the cleaned name.
    Skips tickers where no meaningful search term can be derived.
    """
    base = ticker.split(".")[0]

    # US tickers without exchange suffix (IBIT, AAPL) — use ticker directly
    if "." not in ticker and not base[:2].isdigit():
        return ticker

    # For everything else, try to extract a meaningful name
    cleaned = _clean_name(name)
    return cleaned


# Words too generic to be useful search terms
_SKIP_WORDS = {
    "plc", "ltd", "inc", "the", "and", "for", "etf", "ucits", "acc",
    "dist", "fund", "class", "share", "registered", "inhaber", "dis",
    "hedged", "ii", "iii", "iv", "v", "vi", "vii", "i", "a", "b", "c",
    "d", "pf", "ipf", "ief", "ex", "public", "limited", "company",
    "solutions", "sector", "index",
}

# Currency codes to strip
_CURRENCIES = {"usd", "eur", "chf", "gbp", "jpy", "hkd", "sgd", "aud", "cad"}


def _clean_name(name: str) -> str:
    """Extract the most searchable part of a fund/ETF name.

    Goal: turn 'iShares S&P 500 Information Technology Sector UCITS ETF USD (Acc)'
    into 'S&P 500 Information Technology'
    """
    if not name:
        return ""
    import re
    # Remove parenthesized content
    name = re.sub(r"\([^)]*\)", " ", name)
    # Remove dashes used as separators
    name = name.replace(" - ", " ")
    # Filter out noise words
    words = []
    for w in name.split():
        w_lower = w.lower().rstrip(".,;:")
        if w_lower in _SKIP_WORDS or w_lower in _CURRENCIES:
            continue
        if len(w) <= 1:
            continue
        words.append(w)
    # Skip overly generic results (just brand names like "iShares" alone)
    result = " ".join(words[:5]).strip()
    # Must have at least one meaningful word beyond a brand name
    if len(result) < 5:
        return ""
    return result


def fetch_news(
    tickers: list[str],
    names: dict[str, str] | None = None,
    max_per_ticker: int = 5,
) -> list[NewsItem]:
    """Fetch news for a list of tickers from Google News RSS.

    Args:
        tickers: List of ticker symbols.
        names: Optional {ticker: display_name} mapping for better search.
        max_per_ticker: Max articles per batch query.

    Returns deduplicated, sorted list of NewsItem.
    """
    if not tickers:
        return []
    names = names or {}

    # Check cache
    cache_key = ",".join(sorted(tickers))
    if cache_key in _cache:
        ts, items = _cache[cache_key]
        if time.time() - ts < CACHE_TTL:
            return items

    # Build search terms for each ticker
    search_terms: list[tuple[str, str]] = []  # (ticker, search_term)
    for t in tickers:
        name = names.get(t, t)
        term = _search_term(t, name)
        if term:
            search_terms.append((t, term))

    all_items: list[NewsItem] = []
    seen_urls: set[str] = set()

    # Batch search terms into groups of 3
    batch_size = 3
    for i in range(0, len(search_terms), batch_size):
        batch = search_terms[i : i + batch_size]
        query = " OR ".join(f'"{term}"' for _, term in batch)
        url = f"https://news.google.com/rss/search?q={quote(query)}&hl=en&gl=US&ceid=US:en"

        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_ticker * len(batch)]:
                if entry.link in seen_urls:
                    continue
                seen_urls.add(entry.link)

                title, source = _extract_source(entry.get("title", ""))
                rel_time, epoch = _relative_time(entry.get("published_parsed"))

                # Tag with the most relevant ticker from the batch
                matched_ticker = batch[0][0]
                title_upper = title.upper()
                for t, term in batch:
                    # Check if ticker base or search term appears in title
                    base = t.split(".")[0].upper()
                    if base in title_upper or term.upper().split()[0] in title_upper:
                        matched_ticker = t
                        break

                all_items.append(NewsItem(
                    ticker=matched_ticker,
                    title=title,
                    url=entry.link,
                    published=rel_time,
                    source=source,
                    timestamp=epoch,
                ))
        except Exception:
            continue

    # Sort by timestamp (newest first), limit total
    all_items.sort(key=lambda x: x.timestamp, reverse=True)
    result = all_items[:30]

    _cache[cache_key] = (time.time(), result)
    return result


def clear_cache():
    """Clear news cache."""
    _cache.clear()


def open_article(url: str):
    """Open a news article in the system browser."""
    webbrowser.open(url)
