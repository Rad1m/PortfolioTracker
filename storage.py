"""Portfolio data storage — transactions in JSON, holdings computed."""

import json
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path

DEFAULT_PATH = Path.home() / ".portfolio_tracker" / "portfolio.json"


@dataclass
class Transaction:
    ticker: str
    type: str  # "buy" or "sell"
    shares: float
    price: float
    date: str
    note: str = ""


class Portfolio:
    def __init__(self, path: Path = DEFAULT_PATH):
        self.path = path
        self.transactions: list[Transaction] = []
        self.load()

    def load(self):
        if self.path.exists():
            data = json.loads(self.path.read_text())
            self.transactions = [Transaction(**t) for t in data.get("transactions", [])]
        else:
            self.transactions = []

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"transactions": [asdict(t) for t in self.transactions]}
        self.path.write_text(json.dumps(data, indent=2))

    def add_transaction(self, txn: Transaction):
        self.transactions.append(txn)
        self.save()

    def get_holdings(self) -> dict[str, float]:
        """Return {ticker: net_shares} for tickers with positive shares."""
        holdings: dict[str, float] = {}
        for t in self.transactions:
            if t.type == "buy":
                holdings[t.ticker] = holdings.get(t.ticker, 0) + t.shares
            elif t.type == "sell":
                holdings[t.ticker] = holdings.get(t.ticker, 0) - t.shares
        return {k: v for k, v in holdings.items() if v > 0}

    def get_avg_cost(self, ticker: str) -> float:
        """Weighted average cost of buy transactions for a ticker."""
        total_shares = 0.0
        total_cost = 0.0
        for t in self.transactions:
            if t.ticker == ticker and t.type == "buy":
                total_shares += t.shares
                total_cost += t.shares * t.price
        return total_cost / total_shares if total_shares > 0 else 0.0

    def get_transactions(self, ticker: str | None = None) -> list[Transaction]:
        if ticker:
            return [t for t in self.transactions if t.ticker == ticker]
        return list(self.transactions)
