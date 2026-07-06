print("Initializing Quotient, please standby...")

from core import (
    create_symbol_table,
    create_report_table,
)
from core import (
    create_watchlist_table,
)
from ui import ui_start

"""
This module is the starting point for running the Quotient Financial reporting program.

Do so through your terminal application with the command: "python3 main.py"

Intended for initialization of the user interface, database, etc.
"""

if __name__ == "__main__":
    create_watchlist_table()
    create_symbol_table()
    create_report_table()
    ui_start()
