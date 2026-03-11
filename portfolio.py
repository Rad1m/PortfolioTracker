#!/usr/bin/env python3
"""Portfolio Tracker — terminal app for tracking investments."""

from storage import Portfolio, Transaction
from market import get_prices, get_etf_holdings
from ui import (
    console, main_menu, display_portfolio, display_etf_holdings,
    display_transactions, prompt_transaction, select_ticker_for_drilldown,
)


def view_portfolio(portfolio: Portfolio):
    holdings = portfolio.get_holdings()
    if not holdings:
        console.print("[yellow]No holdings yet. Add a transaction first.[/]")
        return

    tickers = list(holdings.keys())
    console.print("[dim]Fetching prices...[/]")
    prices = get_prices(tickers)
    avg_costs = {t: portfolio.get_avg_cost(t) for t in tickers}
    display_tickers = display_portfolio(holdings, avg_costs, prices)

    # Drill-down loop
    while True:
        selected = select_ticker_for_drilldown(display_tickers)
        if not selected:
            break

        console.print(f"\n[dim]Fetching holdings for {selected}...[/]")
        etf_holdings = get_etf_holdings(selected)
        if not etf_holdings:
            console.print(f"[yellow]No ETF holdings data for {selected}[/]")
            continue

        holding_symbols = [h["symbol"] for h in etf_holdings]
        console.print(f"[dim]Fetching prices for {len(holding_symbols)} holdings...[/]")
        holding_prices = get_prices(holding_symbols)
        display_etf_holdings(selected, etf_holdings, holding_prices)


def add_transaction(portfolio: Portfolio):
    data = prompt_transaction()
    if data:
        txn = Transaction(**data)
        portfolio.add_transaction(txn)
        console.print(f"[green]Added {data['type'].upper()} {data['shares']} x {data['ticker']}[/]")


def show_history(portfolio: Portfolio):
    transactions = portfolio.get_transactions()
    display_transactions(transactions)


def main():
    portfolio = Portfolio()
    console.print("[bold cyan]Portfolio Tracker[/] — Live prices from Yahoo Finance\n")

    while True:
        try:
            choice = main_menu()
            if choice == "1":
                view_portfolio(portfolio)
            elif choice == "2":
                add_transaction(portfolio)
            elif choice == "3":
                show_history(portfolio)
            elif choice == "4":
                console.print("[dim]Bye![/]")
                break
        except KeyboardInterrupt:
            console.print("\n[dim]Bye![/]")
            break


if __name__ == "__main__":
    main()
