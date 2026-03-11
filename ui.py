"""Terminal UI — tables, prompts, display helpers using rich."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, FloatPrompt, Confirm
from rich import box

console = Console()


def main_menu() -> str:
    console.print()
    console.print(Panel(
        "[bold]1[/] View Portfolio\n"
        "[bold]2[/] Add Transaction\n"
        "[bold]3[/] Transaction History\n"
        "[bold]4[/] Quit",
        title="[bold cyan]Portfolio Tracker[/]",
        box=box.ROUNDED,
    ))
    return Prompt.ask("Choose", choices=["1", "2", "3", "4"], default="1")


def display_portfolio(holdings: dict[str, float], avg_costs: dict[str, float],
                      prices: dict[str, dict]) -> list[str]:
    """Display portfolio table. Returns list of tickers in display order."""
    if not holdings:
        console.print("[yellow]No holdings. Add a transaction first.[/]")
        return []

    table = Table(title="Portfolio", box=box.SIMPLE_HEAVY)
    table.add_column("#", style="dim", width=3)
    table.add_column("Ticker", style="bold")
    table.add_column("Name")
    table.add_column("Shares", justify="right")
    table.add_column("Avg Cost", justify="right")
    table.add_column("Price", justify="right")
    table.add_column("Currency", justify="center")
    table.add_column("Value", justify="right")
    table.add_column("P&L", justify="right")
    table.add_column("P&L %", justify="right")

    tickers = sorted(holdings.keys())
    total_value = 0.0
    total_cost = 0.0

    for i, ticker in enumerate(tickers, 1):
        shares = holdings[ticker]
        avg = avg_costs.get(ticker, 0)
        info = prices.get(ticker, {})
        price = info.get("price", 0)
        currency = info.get("currency", "")
        name = info.get("name", ticker)

        value = shares * price
        cost = shares * avg
        pnl = value - cost
        pnl_pct = (pnl / cost * 100) if cost > 0 else 0

        total_value += value
        total_cost += cost

        pnl_color = "green" if pnl >= 0 else "red"
        table.add_row(
            str(i),
            ticker,
            name[:25],
            f"{shares:.2f}",
            f"{avg:.2f}",
            f"{price:.2f}",
            currency,
            f"{value:.2f}",
            f"[{pnl_color}]{pnl:+.2f}[/]",
            f"[{pnl_color}]{pnl_pct:+.1f}%[/]",
        )

    console.print(table)

    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0
    pnl_color = "green" if total_pnl >= 0 else "red"
    console.print(Panel(
        f"Total Value: [bold]{total_value:,.2f}[/]  |  "
        f"Total Cost: {total_cost:,.2f}  |  "
        f"P&L: [{pnl_color}]{total_pnl:+,.2f} ({total_pnl_pct:+.1f}%)[/]",
        box=box.ROUNDED,
    ))

    return tickers


def display_etf_holdings(ticker: str, holdings: list[dict], prices: dict[str, dict]):
    """Display ETF top holdings table."""
    if not holdings:
        console.print(f"[yellow]No holdings data available for {ticker}[/]")
        return

    table = Table(title=f"Top Holdings — {ticker}", box=box.SIMPLE_HEAVY)
    table.add_column("#", style="dim", width=3)
    table.add_column("Symbol", style="bold")
    table.add_column("Name")
    table.add_column("Weight %", justify="right")
    table.add_column("Price", justify="right")
    table.add_column("Currency", justify="center")
    table.add_column("Day %", justify="right")

    for i, h in enumerate(holdings, 1):
        symbol = h["symbol"]
        info = prices.get(symbol, {})
        price = info.get("price", 0)
        currency = info.get("currency", "")
        change = info.get("change_pct", 0)
        name = info.get("name", h.get("name", symbol))

        chg_color = "green" if change >= 0 else "red"
        table.add_row(
            str(i),
            symbol,
            name[:30],
            f"{h['weight']:.1f}%",
            f"{price:.2f}" if price else "N/A",
            currency,
            f"[{chg_color}]{change:+.2f}%[/]" if price else "N/A",
        )

    console.print(table)


def display_transactions(transactions):
    """Display transaction history."""
    if not transactions:
        console.print("[yellow]No transactions recorded.[/]")
        return

    table = Table(title="Transactions", box=box.SIMPLE_HEAVY)
    table.add_column("Date", style="dim")
    table.add_column("Type")
    table.add_column("Ticker", style="bold")
    table.add_column("Shares", justify="right")
    table.add_column("Price", justify="right")
    table.add_column("Total", justify="right")
    table.add_column("Note")

    for t in sorted(transactions, key=lambda x: x.date, reverse=True):
        type_color = "green" if t.type == "buy" else "red"
        total = t.shares * t.price
        table.add_row(
            t.date,
            f"[{type_color}]{t.type.upper()}[/]",
            t.ticker,
            f"{t.shares:.2f}",
            f"{t.price:.2f}",
            f"{total:.2f}",
            t.note or "",
        )

    console.print(table)


def prompt_transaction() -> dict | None:
    """Interactive prompts to create a transaction. Returns dict or None if cancelled."""
    console.print()
    ticker = Prompt.ask("Ticker (e.g. IUIT.L)").strip().upper()
    if not ticker:
        return None

    txn_type = Prompt.ask("Type", choices=["buy", "sell"], default="buy")
    shares = FloatPrompt.ask("Shares")
    price = FloatPrompt.ask("Price per share")

    from datetime import date
    date_str = Prompt.ask("Date", default=date.today().isoformat())
    note = Prompt.ask("Note (optional)", default="")

    if not Confirm.ask(
        f"Confirm {txn_type.upper()} {shares} x {ticker} @ {price} on {date_str}?"
    ):
        return None

    return {
        "ticker": ticker,
        "type": txn_type,
        "shares": shares,
        "price": price,
        "date": date_str,
        "note": note,
    }


def select_ticker_for_drilldown(tickers: list[str]) -> str | None:
    """Ask user to pick a ticker to drill down into. Returns ticker or None."""
    choice = Prompt.ask(
        "\nEnter [bold]#[/] to drill into ETF holdings (or [bold]0[/] to go back)",
        default="0",
    )
    try:
        idx = int(choice)
        if 1 <= idx <= len(tickers):
            return tickers[idx - 1]
    except ValueError:
        # Maybe they typed the ticker directly
        choice = choice.upper()
        if choice in tickers:
            return choice
    return None
