# Portfolio Tracker

A terminal-based investment portfolio tracker with live prices from Yahoo Finance and ETF drill-down.

## Features

- **Portfolio overview** — view all holdings with live prices, P&L, and totals
- **Buy/sell tracking** — record transactions, holdings computed automatically
- **ETF drill-down** — select an ETF and see live prices for its top holdings
- **Keyboard-driven** — arrow keys, hotkeys, no mouse needed
- **Auto-refresh** — prices update every 60 seconds

## Quick Start

```bash
pip install -r requirements.txt
python portfolio.py
```

## Keyboard Shortcuts

| Key       | Action                        |
|-----------|-------------------------------|
| `↑` `↓`  | Navigate between rows         |
| `Enter`   | Drill into ETF holdings       |
| `Esc`     | Go back                       |
| `b`       | Add buy transaction           |
| `s`       | Add sell transaction          |
| `t`       | Transaction history           |
| `r`       | Refresh prices                |
| `q`       | Quit                          |

## Data Storage

Transactions are saved to `~/.portfolio_tracker/portfolio.json`. Holdings and P&L are always computed from the transaction log.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — module structure, data flow, design decisions
- [UX Design](docs/UX.md) — screens, navigation, color palette, layout specs
