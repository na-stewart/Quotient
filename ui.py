import sys
import termios
import traceback
from typing import Any

from simple_term_menu import TerminalMenu

from core import (
    get_watchlists,
    insert_watchlist,
    delete_watchlist,
    insert_symbol,
    get_symbols,
    delete_symbol,
    get_reports,
    generate_reports,
    delete_report,
)
from utils import (
    get_greeting,
    open_file,
    log,
    report_text,
)

"""
The ui module manages and renders the console based user interface.

Should reference the core module for functionality.
"""

with open("resources/menu.txt", "r") as menu_f:
    menu_title: str = menu_f.read().format(get_greeting())

with open("resources/screeners.txt") as screeners_f:
    screeners: list[str] = screeners_f.read().split("\n")


def make_menu(entries: list[str], title: str, **kwargs: Any) -> TerminalMenu:
    """Create a TerminalMenu with consistent styling."""
    return TerminalMenu(
        menu_entries=entries,
        title=title,
        menu_cursor="> ",
        menu_cursor_style=("fg_gray", "bold"),
        menu_highlight_style=("bg_blue", "fg_gray"),
        cycle_cursor=True,
        clear_screen=True,
        **kwargs,
    )


def show(menu: TerminalMenu) -> int | None:
    """Show a menu and return the selected index, or None on cancel/escape."""
    sys.stdout.write("\033[3J\033[H\033[2J")
    sys.stdout.flush()
    return menu.show()


def ui_start():
    """Main menu of the application."""
    menu = make_menu(
        ["Create Watchlist", "Watchlists", "Reports", "Quit"],
        title=menu_title,
    )
    while True:
        try:
            sel = show(menu)
            if sel is None:
                continue
            if sel == 0:
                create_watchlist()
            elif sel == 1:
                open_watchlist_menu()
            elif sel == 2:
                open_reports_menu()
            elif sel == 3:
                raise SystemExit
        except (KeyboardInterrupt, EOFError):
            continue
        except SystemExit:
            break
        except Exception:
            log("Unhandled exception occurred.\n" + traceback.format_exc(), "ERROR")
            print("\n" + traceback.format_exc())
            input("Press Enter to continue...")


def create_watchlist():
    print(menu_title)
    try:
        name = input("Title: ")
        description = input("Description: ")
    except (KeyboardInterrupt, EOFError):
        return
    watchlist = insert_watchlist(name, description)
    _input_symbols_loop(watchlist)


def _input_symbols_loop(watchlist_id: int):
    while True:
        try:
            symbol = input("Input equity symbol (or exit): ").upper()
        except (KeyboardInterrupt, EOFError):
            break
        if symbol == "EXIT" or symbol == "":
            break
        insert_symbol(watchlist_id, symbol)


def open_watchlist_menu():
    watchlists = sorted(get_watchlists(), key=lambda w: w["id"], reverse=True)
    if not watchlists:
        print(menu_title)
        print("No watchlist created.")
        input("\nPress Enter to continue...")
        return
    sel = show(
        make_menu(
            [w["name"] for w in watchlists],
            title=f"{menu_title}\nYour watchlists:",
        )
    )
    if sel is None:
        return
    selected_watchlist = watchlists[sel]
    watchlist_detail_menu(selected_watchlist)


def watchlist_detail_menu(watchlist: dict[str, Any]):
    menu = make_menu(
        ["View Symbols", "Update Symbols", "Delete Watchlist", "Back"],
        title=f"{menu_title}\n{watchlist['name']}",
    )
    while True:
        sel = show(menu)
        if sel is None or sel == 3:
            return
        symbols = get_symbols(watchlist["id"])
        if sel == 0:
            view_symbols(symbols)
        elif sel == 1:
            update_symbols(watchlist, symbols)
        elif sel == 2:
            if confirm("Delete this watchlist?"):
                delete_watchlist(watchlist["id"])
                return


def view_symbols(symbols: list[str]):
    print(menu_title)
    print("Watchlist Symbols\n" + "-" * 40)
    if not symbols:
        print("No symbols provided.")
    else:
        for symbol in symbols:
            print(symbol)
    input("\nPress Enter to continue...")


def update_symbols(watchlist: dict[str, Any], symbols: list[str]):
    update_menu = make_menu(
        ["Add Symbols", "Remove Symbols", "Back"],
        title=f"{menu_title}\nUpdate symbols:",
    )
    sel = show(update_menu)
    if sel is None or sel == 2:
        return
    print(menu_title)
    if symbols:
        print("Watchlist Symbols\n" + "-" * 40)
        for symbol in symbols:
            print(symbol)
        print()
    while True:
        try:
            symbol = input("Input equity symbol (or exit): ").upper()
        except (KeyboardInterrupt, EOFError):
            break
        if symbol == "EXIT" or symbol == "":
            break
        if sel == 0:
            insert_symbol(watchlist["id"], symbol)
            print(f"Symbol successfully added: {symbol}\n")
        else:
            if delete_symbol(watchlist["id"], symbol):
                print(f"Symbol successfully removed: {symbol}\n")
            else:
                print(f"Unable to remove symbol: {symbol}\n")


def open_reports_menu():
    menu = make_menu(
        ["View", "Generate", "Back"],
        title=f"{menu_title}\nReports:",
    )
    while True:
        sel = show(menu)
        if sel is None or sel == 2:
            return
        if sel == 0:
            view_reports()
        elif sel == 1:
            generate_reports_menu()
            termios.tcflush(sys.stdin, termios.TCIFLUSH)


def view_reports():
    reports = sorted(get_reports(), key=lambda r: r["id"], reverse=True)
    if not reports:
        print(menu_title)
        print("No reports created.")
        input("\nPress Enter to continue...")
        return
    report_dates = sorted(
        list(set(str(r["date_created"]).split()[0] for r in reports)),
        reverse=True,
    )
    sel = show(
        make_menu(
            report_dates,
            title=f"{menu_title}\nYour reports:",
        )
    )
    if sel is None:
        return
    selected_date = report_dates[sel]
    date_reports = [
        r for r in reports if str(r["date_created"]).split()[0] == selected_date
    ]
    reports_list_menu(date_reports)


def reports_list_menu(reports: list[dict[str, Any]]):
    """Navigate a list of reports for a given date."""
    while True:
        if not reports:
            return
        sel = show(
            make_menu(
                [r["symbol"] for r in reports],
                title=f"{menu_title}\nYour reports:",
            )
        )
        if sel is None:
            return
        action = report_detail_menu(reports[sel], reports)
        if action == "exit":
            return


def report_detail_menu(
    report: dict[str, Any], reports_list: list[dict[str, Any]]
) -> str | None:
    """Detail view for a single report."""
    menu = make_menu(
        [
            "Delete Report",
            "View Chart",
            "Profile",
            "Back",
            "Exit",
        ],
        title=f"{menu_title} \nReport on {report['symbol']}:",
    )
    while True:
        sel = show(menu)
        if sel is None or sel == 3:
            return None
        if sel == 4:
            return "exit"
        if sel == 0:
            if confirm("Delete this report?"):
                delete_report(report)
                if report in reports_list:
                    reports_list.remove(report)
                return None
        elif sel == 1:
            open_file(report["chart"])
        elif sel == 2:
            profile_menu(report)


def profile_menu(report: dict[str, Any]):
    """Show the report summary with an option to open the export."""
    menu = make_menu(
        ["View Export", "Back"],
        title=report_text(report) + "\n",
    )
    while True:
        sel = show(menu)
        if sel is None or sel == 1:
            return
        if sel == 0:
            print(menu_title)
            open_file(report["export"])
            print("Export opening...")


def generate_reports_menu():
    gen_menu = make_menu(
        ["From Screener", "From Watchlist", "Back"],
        title=f"{menu_title}\nGenerate report:",
    )
    sel = show(gen_menu)
    if sel is None or sel == 2:
        return
    else:
        gen_type_menu = make_menu(
            ["Indicated", "All"],
            title=f"{menu_title}\nReporting scope:",
        )
        type_sel = show(gen_type_menu)
        if sel == 0:
            generate_from_screener(type_sel == 0)
        elif sel == 1:
            generate_from_watchlist(type_sel == 0)
        termios.tcflush(sys.stdin, termios.TCIFLUSH)
        input("\nPress Enter to continue...")


def generate_from_screener(on_indication: bool):
    sel = show(
        make_menu(
            screeners,
            title=f"{menu_title}\nDynamic screeners:",
        )
    )
    if sel is None:
        return
    print(menu_title)
    generate_reports(screener=screeners[sel], on_indication=on_indication)


def generate_from_watchlist(on_indication: bool):
    watchlists = sorted(get_watchlists(), key=lambda w: w["id"])
    if not watchlists:
        print(menu_title)
        print("No watchlists created.")
        return

    sel = show(
        make_menu(
            [w["name"] for w in watchlists],
            title=f"{menu_title}\nYour watchlists:",
        )
    )
    if sel is None:
        return
    print(menu_title)
    generate_reports(watchlist_id=watchlists[sel]["id"], on_indication=on_indication)


def confirm(prompt: str = "Are you sure?") -> bool:
    sel = show(
        make_menu(
            ["Yes", "No"],
            title=f"{menu_title}\n{prompt}",
        )
    )
    return sel == 0
