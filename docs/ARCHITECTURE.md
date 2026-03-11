# Architecture

## Overview

Portfolio Tracker is a terminal-based investment tracker built with Python and Textual. It provides real-time price data from Yahoo Finance with keyboard-driven navigation.

## Module Structure

```
PortfolioTracker/
  portfolio.py        # Entry point — Textual App, screen definitions
  storage.py          # Data layer — Transaction log, JSON persistence
  market.py           # Market data — yfinance wrapper, caching
  ui.py               # UI components — Textual widgets, styles
  docs/               # Project documentation
  requirements.txt    # Dependencies
```

## Data Flow

```
User Input (keyboard)
    |
    v
portfolio.py (App / Screens)
    |
    +---> storage.py (read/write transactions)
    |         |
    |         v
    |     ~/.portfolio_tracker/portfolio.json
    |
    +---> market.py (fetch prices, ETF holdings)
              |
              v
          Yahoo Finance API (via yfinance)
```

## Key Design Decisions

- **JSON over SQLite** — simple to debug, portable, sufficient for personal use (<1000 transactions)
- **Computed holdings** — transactions are the source of truth; holdings are always derived
- **In-memory cache (60s TTL)** — avoids hammering Yahoo Finance during navigation
- **Textual framework** — modern TUI with widgets, key bindings, reactive updates, built on top of rich

## Dependencies

| Library   | Purpose                        |
|-----------|--------------------------------|
| textual   | Terminal UI framework          |
| yfinance  | Yahoo Finance market data      |
| rich      | Text formatting (used by Textual internally) |

## Data Storage

Transactions are stored at `~/.portfolio_tracker/portfolio.json`:

```json
{
  "transactions": [
    {
      "ticker": "IUIT.L",
      "type": "buy",
      "shares": 10,
      "price": 45.50,
      "date": "2026-03-11",
      "note": ""
    }
  ]
}
```

Holdings (shares per ticker) and P&L are always computed from this transaction log — never stored directly.
