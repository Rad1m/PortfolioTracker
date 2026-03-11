# UX Design

## Design Philosophy

Clean, modern terminal aesthetic. Think a well-designed dashboard — not a retro terminal. Prioritise readability, clear hierarchy, and efficient keyboard-driven workflows. Every piece of information should earn its place on screen.

## Color Palette

Muted, modern palette on a dark base. Avoids the garish neon of legacy terminals.

| Role             | Color          | Usage                                      |
|------------------|----------------|---------------------------------------------|
| Background       | Dark charcoal  | App background                              |
| Surface          | Slightly lighter charcoal | Panels, cards, table rows          |
| Text primary     | Off-white      | Data values, labels                         |
| Text secondary   | Medium grey    | Descriptions, timestamps, hints             |
| Accent           | Soft blue      | Headers, selected row highlight, borders    |
| Positive         | Muted green    | Gains, successful actions                   |
| Negative         | Muted coral/red| Losses, errors                              |
| Warning          | Soft amber     | Alerts, market closed indicator             |
| Highlight        | Accent blue bg | Currently focused/selected row              |

## Typography & Spacing

- Monospace font (terminal default)
- Generous padding inside panels (1 cell vertical, 2 cells horizontal)
- Clear visual separation between sections using subtle borders or whitespace
- Numbers right-aligned, text left-aligned
- Percentages always include sign (+/-)

## Layout

### Main Screen — Portfolio View

```
┌─────────────────────────────────────────────────────────────┐
│  PORTFOLIO TRACKER              Total: £32,450  (+4.2%)     │
│                                 Last update: 14:32          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Ticker    Name                Shares   Price    Value  P&L │
│ ─────────────────────────────────────────────────────────── │
│▸ IUIT.L    iShares S&P 500 IT   10    £45.50   £455  +12%  │
│  VUSA.L    Vanguard S&P 500     25    £72.30  £1807   +8%  │
│  VWRL.L    Vanguard FTSE AW     15    £88.10  £1321   -2%  │
│  EQQQ.L    Invesco NASDAQ 100   20    £30.25   £605  +15%  │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  ▸ arrow cursor    ↑↓ navigate   Enter drill down           │
│  b buy   s sell   r refresh   t transactions   q quit       │
└─────────────────────────────────────────────────────────────┘
```

**Key elements:**
- Header bar with portfolio total and last update time
- Scrollable table of holdings with cursor indicator (▸)
- Selected row subtly highlighted with accent background
- Footer bar with all available hotkeys — always visible
- P&L color-coded (green/red) with percentage

### ETF Drill-Down View

Triggered by pressing `Enter` on an ETF row. Replaces the main table area.

```
┌─────────────────────────────────────────────────────────────┐
│  IUIT.L — iShares S&P 500 Info Tech     Price: £45.50      │
│  Top Holdings                           Weight coverage: 72%│
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  #   Symbol   Name                Weight   Price    Day %   │
│ ─────────────────────────────────────────────────────────── │
│  1   AAPL     Apple Inc.          22.8%   $189.50   +1.2%  │
│  2   MSFT     Microsoft Corp.     21.5%   $415.20   +0.8%  │
│  3   NVDA     NVIDIA Corp.        10.2%   $875.30   +3.1%  │
│  4   AVGO     Broadcom Inc.        4.8%   $168.40   -0.5%  │
│  5   ...                                                    │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  Esc back   ↑↓ navigate   r refresh                        │
└─────────────────────────────────────────────────────────────┘
```

**Key elements:**
- Header shows the parent ETF info
- Top holdings table with weight, live price, day change
- `Esc` returns to the portfolio view
- Same styling as the main table for consistency

### Transaction Entry

Triggered by `b` (buy) or `s` (sell). Modal overlay on top of current view.

```
┌──────────────── Add Transaction ─────────────────┐
│                                                   │
│  Type:    BUY                                     │
│  Ticker:  [IUIT.L          ]                      │
│  Shares:  [10              ]                      │
│  Price:   [45.50           ]                      │
│  Date:    [2026-03-11      ]                      │
│  Note:    [                ]                      │
│                                                   │
│           [ Confirm ]    [ Cancel ]               │
│                                                   │
│  Tab next field   Enter confirm   Esc cancel      │
└───────────────────────────────────────────────────┘
```

**Key elements:**
- Modal dialog — does not navigate away from the portfolio view
- Pre-fills date with today
- Tab to move between fields
- Type (buy/sell) is pre-set based on which key was pressed
- Validation: non-empty ticker, positive shares/price, valid date format

### Transaction History

Triggered by `t`. Full-screen table view.

```
┌─────────────────────────────────────────────────────────────┐
│  Transaction History                          14 total      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Date         Type   Ticker    Shares   Price   Total       │
│ ─────────────────────────────────────────────────────────── │
│  2026-03-11   BUY    IUIT.L     10     45.50    455.00     │
│  2026-03-10   SELL   VUSA.L      5     72.30    361.50     │
│  2026-03-08   BUY    VWRL.L     15     88.10  1,321.50     │
│  ...                                                        │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  Esc back   ↑↓ scroll                                      │
└─────────────────────────────────────────────────────────────┘
```

## Navigation Model

All navigation is keyboard-driven. No mouse required (though Textual supports mouse clicks on rows as a bonus).

### Global Keys

| Key       | Action                          |
|-----------|---------------------------------|
| `q`       | Quit app                        |
| `r`       | Refresh prices                  |
| `?`       | Show help overlay               |

### Portfolio View Keys

| Key       | Action                          |
|-----------|---------------------------------|
| `↑` `↓`  | Move cursor between holdings    |
| `Enter`   | Drill into selected ETF         |
| `b`       | Add buy transaction             |
| `s`       | Add sell transaction            |
| `t`       | View transaction history        |

### Drill-Down View Keys

| Key       | Action                          |
|-----------|---------------------------------|
| `↑` `↓`  | Scroll holdings list            |
| `Esc`     | Return to portfolio view        |
| `r`       | Refresh prices                  |

### Transaction Form Keys

| Key       | Action                          |
|-----------|---------------------------------|
| `Tab`     | Next field                      |
| `Shift+Tab`| Previous field                 |
| `Enter`   | Confirm (when on Confirm button)|
| `Esc`     | Cancel and close                |

## Auto-Refresh

- Prices refresh automatically every 60 seconds
- A subtle "refreshing..." indicator appears in the header during fetch
- Last update timestamp shown in the header
- Manual refresh with `r` at any time
- Price cells briefly flash when value changes (subtle highlight for ~1s)

## Responsive Behaviour

- Table columns adapt to terminal width
- Name column truncates first (ticker and numbers always visible)
- Minimum supported width: 80 columns
- If terminal is too narrow, show a message suggesting resize

## Empty States

- **No holdings**: centred message — "No holdings yet. Press **b** to add your first transaction."
- **No ETF data**: inline message — "Holdings data not available for this ticker."
- **Fetch error**: amber warning — "Could not fetch prices. Press **r** to retry."

## Transitions

- Screen changes are instant (no animations — this is a terminal)
- Drill-down pushes a new screen; `Esc` pops back
- Modal forms overlay the current screen with a dimmed background
