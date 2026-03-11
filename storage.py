"""Portfolio data storage — transactions in JSON, holdings computed."""

import csv
import json
from dataclasses import dataclass, asdict
from datetime import date, datetime
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
    portfolio: str = ""  # portfolio tag; empty = untagged


class Portfolio:
    def __init__(self, path: Path = DEFAULT_PATH):
        self.path = path
        self.transactions: list[Transaction] = []
        self.portfolios: list[str] = []
        self.display_currency: str = "USD"
        self.sort_mode: str = "ticker"
        self.load()

    def load(self):
        if self.path.exists():
            text = self.path.read_text().strip()
            if text:
                data = json.loads(text)
                self.transactions = [Transaction(**t) for t in data.get("transactions", [])]
                self.portfolios = data.get("portfolios", [])
                self.display_currency = data.get("display_currency", "USD")
                self.sort_mode = data.get("sort_mode", "ticker")
            else:
                self.transactions = []
        else:
            self.transactions = []

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "display_currency": self.display_currency,
            "sort_mode": self.sort_mode,
            "portfolios": self.portfolios,
            "transactions": [asdict(t) for t in self.transactions],
        }
        self.path.write_text(json.dumps(data, indent=2))

    def add_transaction(self, txn: Transaction):
        self.transactions.append(txn)
        self.save()

    def _filtered_transactions(self, portfolio_name: str | None) -> list[Transaction]:
        """Return transactions filtered by portfolio tag. None means all."""
        if portfolio_name is None:
            return list(self.transactions)
        return [t for t in self.transactions if t.portfolio == portfolio_name]

    def get_holdings(self, portfolio_name: str | None = None) -> dict[str, float]:
        """Return {ticker: net_shares} for tickers with positive shares."""
        holdings: dict[str, float] = {}
        for t in self._filtered_transactions(portfolio_name):
            if t.type == "buy":
                holdings[t.ticker] = holdings.get(t.ticker, 0) + t.shares
            elif t.type == "sell":
                holdings[t.ticker] = holdings.get(t.ticker, 0) - t.shares
        return {k: v for k, v in holdings.items() if v > 0}

    def get_avg_cost(self, ticker: str, portfolio_name: str | None = None) -> float:
        """Weighted average cost of buy transactions for a ticker."""
        total_shares = 0.0
        total_cost = 0.0
        for t in self._filtered_transactions(portfolio_name):
            if t.ticker == ticker and t.type == "buy":
                total_shares += t.shares
                total_cost += t.shares * t.price
        return total_cost / total_shares if total_shares > 0 else 0.0

    def get_transactions(self, ticker: str | None = None, portfolio_name: str | None = None) -> list[Transaction]:
        txns = self._filtered_transactions(portfolio_name)
        if ticker:
            return [t for t in txns if t.ticker == ticker]
        return txns

    def has_transaction(self, txn: Transaction) -> bool:
        """Check if an identical transaction already exists."""
        for t in self.transactions:
            if (t.ticker == txn.ticker and t.type == txn.type
                    and t.shares == txn.shares and t.price == txn.price
                    and t.date == txn.date and t.portfolio == txn.portfolio):
                return True
        return False

    def add_portfolio(self, name: str) -> bool:
        """Add a new named portfolio. Returns False if name already exists."""
        if name in self.portfolios:
            return False
        self.portfolios.append(name)
        self.save()
        return True

    def remove_portfolio(self, name: str) -> None:
        """Remove a portfolio name. Transactions with this tag become untagged."""
        if name in self.portfolios:
            self.portfolios.remove(name)
            for t in self.transactions:
                if t.portfolio == name:
                    t.portfolio = ""
            self.save()

    def import_csv(self, path: Path, portfolio_name: str = "") -> dict:
        """Import transactions from a broker CSV file.

        Returns dict with keys: imported (int), skipped (int), errors (list[str])
        """
        imported = 0
        skipped = 0
        errors: list[str] = []

        try:
            text = path.read_text(encoding="utf-8-sig")
        except Exception as e:
            return {"imported": 0, "skipped": 0, "errors": [f"Cannot read file: {e}"]}

        reader = csv.DictReader(text.splitlines())
        fields = reader.fieldnames or []

        # Detect format by columns present
        if "Trade Date" in fields and "Purchase Price" in fields:
            parser = self._parse_ibkr_row
        else:
            return {"imported": 0, "skipped": 0,
                    "errors": [f"Unrecognised CSV format. Columns: {', '.join(fields)}"]}

        for i, row in enumerate(reader, 2):
            try:
                txn = parser(row)
                if txn is None:
                    continue
                txn.portfolio = portfolio_name
                if self.has_transaction(txn):
                    skipped += 1
                else:
                    self.transactions.append(txn)
                    imported += 1
            except Exception as e:
                errors.append(f"Row {i}: {e}")

        if imported > 0:
            self.transactions.sort(key=lambda t: t.date)
            self.save()

        return {"imported": imported, "skipped": skipped, "errors": errors}

    @staticmethod
    def _parse_ibkr_row(row: dict) -> Transaction | None:
        """Parse a row from IBKR/Yahoo Finance portfolio CSV export."""
        ticker = row.get("Symbol", "").strip()
        if not ticker:
            return None

        trade_date_raw = row.get("Trade Date", "").strip()
        if not trade_date_raw:
            return None

        date_str = datetime.strptime(trade_date_raw, "%Y%m%d").strftime("%Y-%m-%d")
        price = float(row.get("Purchase Price", 0))
        shares = float(row.get("Quantity", 0))
        if shares <= 0:
            return None

        comment = row.get("Comment", "").strip()
        return Transaction(
            ticker=ticker,
            type="buy",
            shares=shares,
            price=price,
            date=date_str,
            note=comment,
        )
