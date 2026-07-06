import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


from exports import plot_candles, export_report, pngs_to_pdf
from utils import (
    db_path,
    get_yscreener,
    get_crossovers,
    get_fundamentals,
    get_company_profile,
    log,
    safe_lookup,
    score_fundamentals,
    open_file,
    get_daily_candles,
    has_recent_crossovers,
    is_death_cross,
)

"""The core module is intended for handling interaction logic and equity report generation."""


def create_watchlist_table():
    """Watchlists store equity symbols of interest."""
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                date_created DATETIME DEFAULT CURRENT_TIMESTAMP,
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT
            );
            """)
        conn.commit()


def has_recent_report(symbol: str) -> bool:
    """Checks if a report for a symbol was created recently."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            f"""
            SELECT EXISTS(
                SELECT 1 FROM report 
                WHERE symbol = ? 
                AND date_created >= datetime('now', '-7 days')
            )
            """,
            (symbol,),
        )
        return cursor.fetchone()[0]


def get_watchlists() -> list[dict]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM watchlist")
        return [dict(row) for row in cursor.fetchall()]


def insert_watchlist(name: str, description: str) -> int:
    if not name:
        raise ValueError("Watchlist name cannot be empty.")
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO watchlist (name, description) VALUES (?, ?)",
            (name, description),
        )
        conn.commit()
        log(f"Watchlist {name} has been created.")
        return cursor.lastrowid


def delete_watchlist(watchlist_id: str) -> bool:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute("DELETE FROM watchlist WHERE id = ?", (watchlist_id,))
        conn.commit()
        success = cursor.rowcount > 0
        if success:
            log(f"Watchlist with id {watchlist_id} has been deleted.")
        return success


def create_symbol_table():
    """A symbol is the equity ticker that is stored within a watchlist."""
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS watchlist_symbol (
                date_created DATETIME DEFAULT CURRENT_TIMESTAMP,
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                watchlist INTEGER NOT NULL,
                FOREIGN KEY (watchlist)
                    REFERENCES watchlist (id)
                    ON DELETE CASCADE
            );
            """)
        conn.commit()


def get_symbols(watchlist_id: int) -> list[dict]:
    """Retrieves symbols associated with a watchlist."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM watchlist_symbol WHERE watchlist = ?",
            (watchlist_id,),
        )
        return [row["ticker"] for row in cursor.fetchall()]


def insert_symbol(watchlist_id: int, symbol: str) -> int:
    if len(symbol) == 0 or len(symbol) > 5:
        raise ValueError("Invalid symbol.")
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO watchlist_symbol (ticker, watchlist) VALUES (?, ?)",
            (symbol.upper().replace(" ", ""), watchlist_id),
        )
        conn.commit()
        log(f"{symbol} has been inserted into watchlist with id {watchlist_id}.")
        return cursor.lastrowid


def delete_symbol(watchlist_id: int, symbol: str) -> bool:
    if len(symbol) == 0 or len(symbol) > 5:
        raise ValueError("Invalid symbol.")
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM watchlist_symbol WHERE ticker = ? AND watchlist = ?",
            (
                symbol,
                watchlist_id,
            ),
        )
        conn.commit()
        success = cursor.rowcount > 0
        if success:
            log(f"{symbol} has been deleted from watchlist with id {watchlist_id}.")
        return success


def create_report_table():
    """Reports contain information on equities of interest including fundamentals and profile."""
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS report (
                date_created DATETIME DEFAULT CURRENT_TIMESTAMP,
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                profile TEXT NOT NULL,
                indicators TEXT NOT NULL,
                fundamentals TEXT NOT NULL,
                scoring TEXT NOT NULL,
                candles TEXT NOT NULL,
                screener TEXT,
                chart TEXT,
                export TEXT,
                watchlist INTEGER,
                FOREIGN KEY (watchlist)
                    REFERENCES watchlist (id)
                    ON DELETE CASCADE
            );
            """)


def get_reports() -> list[dict]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM report")
        rows = [dict(row) for row in cursor.fetchall()]
    json_fields = {"indicators", "fundamentals", "profile", "scoring", "candles"}
    for row in rows:
        for field in json_fields:
            if field in row and isinstance(row[field], str):
                row[field] = json.loads(row[field])
    return rows


def insert_report(report: dict) -> int:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO report (symbol, indicators, fundamentals, watchlist, screener, profile, chart, scoring, candles, export) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                report["symbol"],
                json.dumps(report["indicators"], default=str),
                json.dumps(report["fundamentals"], default=str),
                report["watchlist"],
                report["screener"],
                json.dumps(report["profile"], default=str),
                report["chart"],
                json.dumps(report["scoring"], default=str),
                json.dumps(report["candles"].to_dict(orient="records"), default=str),
                report["export"],
            ),
        )
        conn.commit()
        log(f"Report for {report["symbol"]} has been created.")
        return cursor.lastrowid


def delete_report(report: dict) -> bool:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM report WHERE id = ?",
            (report["id"],),
        )
        conn.commit()
        log(f"Report with id {report["id"]} has been deleted.")
        os.remove(report["chart"])
        os.remove(report["export"])
        return cursor.rowcount > 0


def generate_reports(
    screener: str = None, watchlist_id: int = None, on_indication: bool = False
):
    log("Report generation initialized, retrieving symbols.")
    print("Report generation initiated, retrieving symbols...")
    symbols = get_yscreener(screener) if screener else get_symbols(watchlist_id)
    symbols = [s for s in symbols if not has_recent_report(s)]
    print("Loading candlestick data, please wait...")
    all_candles = get_daily_candles(symbols)
    reports = []
    for i, symbol in enumerate(symbols):
        print(f"Analyzing {symbol}... {i + 1}/{len(symbols)}")
        candles_df = all_candles.get(symbol)
        if candles_df is None:
            continue
        crossovers = get_crossovers(candles_df)
        if on_indication and (
            not has_recent_crossovers(crossovers) or is_death_cross(candles_df)
        ):
            continue
        reports.append(
            {
                "symbol": symbol,
                "indicators": crossovers,
                "screener": screener,
                "watchlist": watchlist_id,
                "candles": candles_df,
            }
        )

    if not reports:
        return

    print("Loading reports, please wait...\n\n[ REPORTS ]")
    print("-" * 27)
    report_symbols = [r["symbol"] for r in reports]
    profile = get_company_profile(report_symbols)
    fundamentals = get_fundamentals(report_symbols)

    def build_report(report):
        """Build a single report, runs in thread pool."""
        symbol = report["symbol"]
        fundamentals_data = safe_lookup(fundamentals, symbol)
        report["fundamentals"] = fundamentals_data
        report["profile"] = safe_lookup(profile, symbol)
        if not fundamentals_data:
            return None
        report["scoring"] = score_fundamentals(fundamentals_data, report["profile"])
        if report["scoring"]["grade"] == "F":
            return None

        report["chart"] = plot_candles(report)
        report["export"] = export_report(report)
        insert_report(report)
        log(f"Report generated for {symbol}.")
        print(f"Report generated for {symbol}.")
        return report["export"]

    with ThreadPoolExecutor() as executor:
        results = executor.map(build_report, reports)
        export_paths = [p for p in results if p is not None]
    if export_paths:
        export_paths.sort(key=lambda e: e[1] is None)
        sorted_paths = [Path(p) for p in export_paths]
        summary_path = pngs_to_pdf(sorted_paths)
        open_file(summary_path)
        print(f"Doc saved to {summary_path}")
    else:
        print("No reports generated.")
