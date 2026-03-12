"""PySide6 dialogs for Portfolio Tracker."""

from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

C_ACCENT = "#5b9bd5"
C_SURFACE = "#2a2a2a"
C_BG = "#1e1e1e"
C_TEXT = "#d4d4d4"
C_NEGATIVE = "#d16969"


def _dialog_style():
    return f"""
    QDialog {{
        background: {C_SURFACE};
        color: {C_TEXT};
    }}
    QLabel {{
        color: {C_TEXT};
    }}
    QLineEdit {{
        background: {C_BG};
        color: {C_TEXT};
        border: 1px solid #444;
        padding: 6px;
        border-radius: 3px;
    }}
    QLineEdit:focus {{
        border: 1px solid {C_ACCENT};
    }}
    QPushButton {{
        background: #3a3a3a;
        color: {C_TEXT};
        border: 1px solid #555;
        padding: 6px 16px;
        border-radius: 3px;
        min-width: 80px;
    }}
    QPushButton:hover {{
        background: #444;
    }}
    QPushButton#btn-confirm {{
        background: {C_ACCENT};
        color: white;
        border: none;
    }}
    QPushButton#btn-confirm:hover {{
        background: #4a8bc4;
    }}
    QListWidget {{
        background: {C_BG};
        color: {C_TEXT};
        border: 1px solid #444;
        border-radius: 3px;
    }}
    QListWidget::item:selected {{
        background: #2a4a6b;
    }}
    QTextBrowser {{
        background: {C_BG};
        color: {C_TEXT};
        border: none;
    }}
    """


class TransactionDialog(QDialog):
    """Dialog for adding a buy/sell transaction."""

    def __init__(self, txn_type="buy", portfolio_name="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Add Transaction — {txn_type.upper()}")
        self.setFixedWidth(400)
        self.setStyleSheet(_dialog_style())
        self.txn_type = txn_type
        self.result_data = None

        layout = QFormLayout(self)
        layout.setSpacing(8)

        self._ticker = QLineEdit()
        self._ticker.setPlaceholderText("e.g. IUIT.L")
        layout.addRow("Ticker:", self._ticker)

        self._shares = QLineEdit()
        self._shares.setPlaceholderText("10")
        layout.addRow("Shares:", self._shares)

        self._price = QLineEdit()
        self._price.setPlaceholderText("45.50")
        layout.addRow("Price:", self._price)

        self._date = QLineEdit(date.today().isoformat())
        layout.addRow("Date:", self._date)

        self._note = QLineEdit()
        self._note.setPlaceholderText("(optional)")
        layout.addRow("Note:", self._note)

        self._portfolio = QLineEdit(portfolio_name)
        self._portfolio.setPlaceholderText("(leave empty for untagged)")
        layout.addRow("Portfolio:", self._portfolio)

        self._error = QLabel("")
        self._error.setStyleSheet(f"color: {C_NEGATIVE};")
        layout.addRow(self._error)

        btn_layout = QHBoxLayout()
        confirm = QPushButton("Confirm")
        confirm.setObjectName("btn-confirm")
        confirm.clicked.connect(self._submit)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(confirm)
        btn_layout.addWidget(cancel)
        layout.addRow(btn_layout)

        self._ticker.setFocus()

    def _submit(self):
        ticker = self._ticker.text().strip().upper()
        if not ticker:
            self._error.setText("Ticker is required")
            return

        try:
            shares = float(self._shares.text().strip())
            if shares <= 0:
                raise ValueError
        except ValueError:
            self._error.setText("Shares must be a positive number")
            return

        try:
            price = float(self._price.text().strip())
            if price <= 0:
                raise ValueError
        except ValueError:
            self._error.setText("Price must be a positive number")
            return

        date_str = self._date.text().strip()
        try:
            from datetime import datetime
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            self._error.setText("Date must be YYYY-MM-DD")
            return

        self.result_data = {
            "ticker": ticker,
            "type": self.txn_type,
            "shares": shares,
            "price": price,
            "date": date_str,
            "note": self._note.text().strip(),
            "portfolio": self._portfolio.text().strip(),
        }
        self.accept()


class ImportDialog(QDialog):
    """Dialog for importing transactions from CSV."""

    def __init__(self, portfolio_name="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import CSV")
        self.setFixedWidth(500)
        self.setStyleSheet(_dialog_style())
        self.portfolio_name = portfolio_name
        self.import_result = None

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        path_layout = QHBoxLayout()
        self._filepath = QLineEdit()
        self._filepath.setPlaceholderText("/path/to/portfolio.csv")
        path_layout.addWidget(self._filepath)
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._browse)
        path_layout.addWidget(browse)
        layout.addLayout(path_layout)

        self._error = QLabel("")
        self._error.setStyleSheet(f"color: {C_NEGATIVE};")
        layout.addWidget(self._error)

        self._result_label = QLabel("")
        layout.addWidget(self._result_label)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        import_btn = QPushButton("Import")
        import_btn.setObjectName("btn-confirm")
        import_btn.clicked.connect(self._do_import)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(import_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select CSV file", "", "CSV Files (*.csv)")
        if path:
            self._filepath.setText(path)

    def _do_import(self):
        filepath = self._filepath.text().strip()
        if not filepath:
            self._error.setText("File path is required")
            return

        path = Path(filepath).expanduser()
        if not path.exists():
            self._error.setText(f"File not found: {path}")
            return
        if path.suffix.lower() != ".csv":
            self._error.setText("File must be a .csv file")
            return

        # Get portfolio from parent window
        from storage import Portfolio
        main_win = self.parent()
        while main_win and not hasattr(main_win, "portfolio"):
            main_win = main_win.parent()
        if not main_win:
            self._error.setText("Internal error: cannot find portfolio")
            return

        portfolio = main_win.portfolio
        result = portfolio.import_csv(path, portfolio_name=self.portfolio_name)
        imported = result["imported"]
        skipped = result["skipped"]
        errors = result["errors"]

        parts = []
        if imported:
            parts.append(f"{imported} imported")
        if skipped:
            parts.append(f"{skipped} duplicates skipped")
        if errors:
            parts.append(f"{len(errors)} errors")
            self._error.setText(errors[0])

        self._result_label.setText("  ".join(parts))
        self.import_result = result

        if imported > 0:
            self.accept()


class ConfirmDialog(QDialog):
    """Simple Yes/No confirmation dialog."""

    def __init__(self, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirm")
        self.setFixedWidth(400)
        self.setStyleSheet(_dialog_style())

        layout = QVBoxLayout(self)
        label = QLabel(message)
        label.setWordWrap(True)
        layout.addWidget(label)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        yes = QPushButton("Yes")
        yes.setObjectName("btn-confirm")
        yes.clicked.connect(self.accept)
        no = QPushButton("No")
        no.clicked.connect(self.reject)
        btn_layout.addWidget(yes)
        btn_layout.addWidget(no)
        layout.addLayout(btn_layout)


class CreatePortfolioDialog(QDialog):
    """Dialog for creating a new named portfolio."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Portfolio")
        self.setFixedWidth(350)
        self.setStyleSheet(_dialog_style())
        self.portfolio_name = None

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Portfolio name:"))
        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. Retirement")
        layout.addWidget(self._name)

        self._error = QLabel("")
        self._error.setStyleSheet(f"color: {C_NEGATIVE};")
        layout.addWidget(self._error)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        create = QPushButton("Create")
        create.setObjectName("btn-confirm")
        create.clicked.connect(self._submit)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btn_layout.addWidget(create)
        btn_layout.addWidget(cancel)
        layout.addLayout(btn_layout)

        self._name.setFocus()

    def _submit(self):
        name = self._name.text().strip()
        if not name:
            self._error.setText("Name is required")
            return
        self.portfolio_name = name
        self.accept()


class MoveToPortfolioDialog(QDialog):
    """Dialog for selecting a target portfolio."""

    def __init__(self, portfolios, current_portfolio="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Move to Portfolio")
        self.setFixedWidth(350)
        self.setStyleSheet(_dialog_style())
        self._portfolios = portfolios
        self._current = current_portfolio
        self.selected_portfolio = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Current: {current_portfolio or '(untagged)'}"))

        self._list = QListWidget()
        self._list.addItem("(untagged)")
        for name in portfolios:
            label = f"{name}  ← current" if name == current_portfolio else name
            self._list.addItem(label)
        self._list.itemDoubleClicked.connect(self._on_select)
        layout.addWidget(self._list)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        select_btn = QPushButton("Select")
        select_btn.setObjectName("btn-confirm")
        select_btn.clicked.connect(self._on_confirm)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(select_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _on_select(self, item):
        row = self._list.row(item)
        if row == 0:
            self.selected_portfolio = ""
        else:
            self.selected_portfolio = self._portfolios[row - 1]
        self.accept()

    def _on_confirm(self):
        row = self._list.currentRow()
        if row < 0:
            return
        if row == 0:
            self.selected_portfolio = ""
        else:
            self.selected_portfolio = self._portfolios[row - 1]
        self.accept()


class HelpDialog(QDialog):
    """Dialog showing keyboard shortcuts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setFixedSize(500, 450)
        self.setStyleSheet(_dialog_style())

        layout = QVBoxLayout(self)
        text = QTextBrowser()
        text.setOpenLinks(False)
        text.setHtml(f"""
        <h3 style="color:{C_ACCENT}">Global</h3>
        <pre>  Q  Quit    R  Refresh    ?  Help</pre>

        <h3 style="color:{C_ACCENT}">Portfolio View</h3>
        <pre>  ↑↓    Navigate          Enter  Drill into ticker
  B     Buy               S      Sell
  T     Transaction history
  A     Allocation
  O     Sort              C      Currency
  I     Import CSV        N      New Portfolio
  D     Delete portfolio
  M     Move ticker
  1-9   Switch portfolio tabs</pre>

        <h3 style="color:{C_ACCENT}">Drill-Down / History / Allocation</h3>
        <pre>  Esc   Back
  D     Delete transaction (History only)
  M     Move transaction (History only)</pre>

        <h3 style="color:{C_ACCENT}">Transaction Form</h3>
        <pre>  Tab/Shift+Tab  Navigate fields
  Enter          Confirm    Esc  Cancel</pre>
        """)
        layout.addWidget(text)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignCenter)
