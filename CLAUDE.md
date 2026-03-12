# Project Instructions

## Data Rules
- NEVER hardcode values such as currency exchange rates, stock prices, or any market data. Always fetch the latest values from Yahoo Finance API via yfinance.

## Testing Rules
- NEVER write to the real portfolio file (~/.portfolio_tracker/portfolio.json) during tests. Always use a temporary file path (e.g. tempfile) when instantiating Portfolio in tests. Use `Portfolio(path=tmp_path)` instead of the default path.

## UI Contrast Rules
- Text MUST have good contrast against its background. Grey on grey or gold on brown is BAD. White on dark grey/black or light green on dark grey is GOOD.
- Buttons must look like buttons: visible borders, distinct background, clear hover/pressed states.
