import datetime
import json
import math
import os
import platform
import textwrap
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from pandas import DataFrame
from schwab.auth import easy_client
from schwab.client import Client
from yahooquery import Screener, Ticker

try:
    y_screener: Screener = Screener()
except Exception as e:
    input("Quotech requires internet connection, press Enter and try again...")
    raise SystemExit


today: datetime.datetime = datetime.datetime.now()
load_dotenv()
schwab_state: Client = easy_client(
    api_key=os.getenv("SCHWAB_KEY"),
    app_secret=os.getenv("SCHWAB_SECRET"),
    callback_url=os.getenv("SCHWAB_CALLBACK"),
    token_path="resources/schwab.json",
    interactive=False,
)
FUNDAMENTAL_FIELDS: dict[str, str] = {
    "revenue_growth": "revChangeTTM",
    "eps_growth": "epsChangePercentTTM",
    "operating_margin": "operatingMarginTTM",
    "roe": "returnOnEquity",
    "pe_ratio": "peRatio",
    "peg_ratio": "pegRatio",
    "current_ratio": "currentRatio",
    "debt_to_equity": "totalDebtToEquity",
}
db_path: str = "resources/app.db"
NEUTRAL: float = 0.5

with open("resources/benchmark_weights.json", "r") as f:
    fundamental_weights: dict[str, float] = json.load(f)
with open("resources/sector_benchmarks.json", "r") as f:
    sector_benchmarks: dict[str, dict[str, float]] = json.load(f)


def get_daily_candles(symbols: list[str]) -> dict[str, pd.DataFrame]:
    start = today - datetime.timedelta(days=300)

    def fetch(symbol: str) -> tuple[str, list[dict[str, Any]]]:
        resp = schwab_state.get_price_history_every_day(symbol, start_datetime=start)
        resp.raise_for_status()
        return symbol, resp.json()["candles"]

    with ThreadPoolExecutor() as executor:
        results = list(executor.map(fetch, symbols))

    def build(candles: list[dict[str, Any]]) -> pd.DataFrame:
        if not candles:
            return None
        df = pd.DataFrame(candles).sort_values("datetime").reset_index(drop=True)
        df["SMA20"] = df["close"].rolling(window=20).mean()
        df["SMA50"] = df["close"].rolling(window=50).mean()
        df["EMA200"] = df["close"].ewm(span=200, adjust=False).mean()
        df["VOL_SMA50"] = df["volume"].rolling(window=50).mean()

        delta = df["close"].diff()
        avg_gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
        avg_loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
        df["RSI"] = 100 - (100 / (1 + avg_gain / avg_loss))

        df["datetime"] = (
            pd.to_datetime(df["datetime"], unit="ms", utc=True)
            .dt.tz_convert(None)
            .dt.floor("D")
            .dt.strftime("%Y-%m-%d")
        )
        return df.dropna(subset=["SMA20", "SMA50", "EMA200"])

    return {
        symbol: result
        for symbol, candles in results
        if (result := build(candles)) is not None
    }


def get_crossovers(candles_df: DataFrame) -> dict:
    """Finds moving average crossovers and RSI overbought/oversold signals."""
    df = candles_df.sort_values("datetime")
    dt = df["datetime"]
    rsi = df["RSI"]
    sma50_gap = df["SMA50"] - df["EMA200"]
    sma20_50_gap = df["SMA20"] - df["SMA50"]
    sma50_prev = sma50_gap.shift(1)
    sma20_50_prev = sma20_50_gap.shift(1)
    rsi_prev = rsi.shift(1)
    return {
        "bullish": {
            "SMA50_cross_above_EMA200": dt[
                (sma50_prev <= 0) & (sma50_gap > 0)
            ].tolist(),
            "SMA20_cross_above_SMA50": dt[
                (sma20_50_prev <= 0) & (sma20_50_gap > 0)
            ].tolist(),
            "rsi_oversold": dt[(rsi_prev >= 30) & (rsi < 30)].tolist(),
            "held_rsi_oversold": dt[rsi < 30].tolist(),
        },
        "bearish": {
            "SMA50_cross_below_EMA200": dt[
                (sma50_prev >= 0) & (sma50_gap < 0)
            ].tolist(),
            "SMA20_cross_below_SMA50": dt[
                (sma20_50_prev >= 0) & (sma20_50_gap < 0)
            ].tolist(),
            "rsi_overbought": dt[(rsi_prev <= 70) & (rsi > 70)].tolist(),
            "held_rsi_overbought": dt[rsi > 70].tolist(),
        },
    }


def score_fundamentals(fundamentals: dict, profile: dict) -> dict:
    bench = (
        sector_benchmarks.get(profile.get("sectorKey"), sector_benchmarks["default"])
        if isinstance(profile, dict)
        else sector_benchmarks["default"]
    )
    raw: dict[str, float] = {
        "revenue_growth": norm_growth(fundamentals.get("revChangeTTM"), target=30),
        "eps_growth": norm_growth(fundamentals.get("epsChangePercentTTM"), target=50),
        "operating_margin": norm_profitability(
            fundamentals.get("operatingMarginTTM"), bench["margin"]
        ),
        "roe": norm_profitability(fundamentals.get("returnOnEquity"), bench["roe"]),
        "pe_ratio": norm_valuation(
            fundamentals.get("peRatio"),
            ideal=bench["pe"] * 0.6,
            max_acceptable=bench["pe"] * 2.0,
        ),
        "peg_ratio": norm_valuation(
            fundamentals.get("pegRatio"),
            ideal=bench["peg"] * 0.5,
            max_acceptable=bench["peg"] * 2.0,
        ),
        "current_ratio": norm_current_ratio(fundamentals.get("currentRatio")),
        "debt_to_equity": norm_debt_to_equity(
            fundamentals.get("totalDebtToEquity"), bench["max_de"]
        ),
    }
    weighted: dict[str, float] = {
        k: round(raw[k] * fundamental_weights[k], 3) for k in raw
    }
    weight_total = sum(fundamental_weights[k] for k in raw) or 1.0
    total = round(
        max(0.0, min(100.0, sum(weighted.values()) / weight_total * 100.0)), 2
    )
    missing = [f for c, f in FUNDAMENTAL_FIELDS.items() if fundamentals.get(f) is None]
    completeness = round(1.0 - len(missing) / len(FUNDAMENTAL_FIELDS), 3)

    def _grade(score: float) -> str:
        if score >= 88:
            return "S"
        if score >= 75:
            return "A"
        if score >= 60:
            return "B"
        if score >= 45:
            return "C"
        if score >= 30:
            return "D"
        return "F"

    return {
        "raw_scores": raw,
        "weighted_scores": weighted,
        "total_score": total,
        "grade": _grade(total),
        "data_completeness": completeness,
        "missing_fields": missing,
    }


def norm_growth(
    value: float | None, target: float, penalty_floor: float = -0.5
) -> float:
    """
    Normalize a growth metric (e.g. revenue or earnings growth) against a target.
    Positive growth is scored on a saturating 0..1 curve relative to `target`.
    Negative growth (shrinkage) is penalized down toward `penalty_floor`.
    """
    if not target or target <= 0:
        return 0.0
    if value is None:
        return NEUTRAL
    ratio = value / target
    if ratio >= 0:
        score = _saturating(ratio)
    else:
        score = penalty_floor * _saturating(-ratio)
    return round(float(score), 4)


def norm_profitability(value: float | None, target: float) -> float:
    """
    Normalize a profitability metric (e.g. margin or profit) against a target.
    Profits scale on a saturating 0.1 curve relative to `target`.
    Losses (value <= 0) receive a small negative penalty scaled by the size of the loss.
    """
    if not target or target <= 0:
        return 0.0
    if value is None:
        return NEUTRAL
    if value <= 0:
        loss_ratio = -value / target
        return round(-0.10 * _saturating(loss_ratio), 4)
    return round(float(_saturating(value / target)), 4)


def norm_valuation(value: float | None, ideal: float, max_acceptable: float) -> float:
    """
    Normalize a valuation multiple (e.g. P/E) where lower is better.
    value <= ideal: rewarded on a concave sqrt curve, floored at 0.35.
    value > ideal: decays exponentially, reaching 0.10 at `max_acceptable` and approaching 0 beyond it.
    """
    if value is None:
        return NEUTRAL
    if value <= 0:
        return 0.15
    if ideal <= 0:
        return NEUTRAL

    if value <= ideal:
        raw = math.sqrt(value / ideal)  # 0 -> 1 concave curve
        return round(float(max(raw, 0.35)), 4)

    if max_acceptable <= ideal:
        return 0.0
    decay = math.log(10) / (max_acceptable - ideal)
    score = math.exp(-decay * (value - ideal))
    return round(float(max(score, 0.0)), 4)


def norm_current_ratio(value: float | None) -> float:
    """
    Normalize the current ratio (current assets / current liabilities), rewards solvency but mildly penalizes hoarding:
    < 0.5: 0.0 (illiquid).
    0.5–1.0: linear ramp up to 0.30.
    1.0–3.0: rises steeply, saturating near ~0.91.
    >= 3.0: eases back down toward 0.75 for very high ratios (excess idle liquidity is treated as slightly inefficient).
    """
    if value is None:
        return NEUTRAL
    if value < 0.5:
        return 0.0
    if value < 1.0:
        score = 0.30 * (value - 0.5) / 0.5
    elif value < 3.0:
        ratio = value - 1.0
        score = 0.30 + 0.70 * ratio / (ratio + 0.28)
    else:
        peak = 0.30 + 0.70 * 2.0 / 2.28  # value of the curve at 3.0
        score = 0.75 + (peak - 0.75) * math.exp(-0.5 * (value - 3.0))
    return round(float(min(score, 1.0)), 4)


def norm_debt_to_equity(value: float | None, max_de: float) -> float:
    """
    Normalize the debt-to-equity ratio, where lower leverage scores higher.
    value / max_de <= 1.0: high score, declining from 1.0 toward ~0.40 as leverage approaches `max_de`.
    Above that decays exponentially toward 0.
    """
    if value is None:
        return NEUTRAL
    if value < 0:
        return 0.0
    if not max_de or max_de <= 0:
        return 0.0

    ratio = value / max_de
    if ratio <= 1.0:
        return round(float(1.0 - 0.80 * _saturating(ratio)), 4)

    boundary = 1.0 - 0.80 * _saturating(1.0)  # ~0.3985, where the curve ends
    score = boundary * math.exp(-1.5 * (ratio - 1.0))
    return round(float(max(score, 0.0)), 4)


def _saturating(ratio: float, k: float = 0.33) -> float:
    return ratio / (ratio + k)


def get_yscreener(
    screener: str = "most_actives_americas", max_results: int = 100
) -> list[str]:
    """
    Retrieves symbols from Yahoo Finance screeners including most active, undervalued growth, 52-week lows, etc.

    Beneficial for finding new investment opportunities beyond user watchlists.
    """
    data = y_screener.get_screeners(screener, count=max_results)
    stocks = data.get(screener, {}).get("quotes", [])
    return [s["symbol"] for s in stocks if len(s.get("symbol")) < 6]


def log(message: str, level: str = "INFO") -> None:
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("resources/log.txt", "a") as f:
        f.write(f"{timestamp} [{level}] {message}\n")


def get_company_profile(symbols: list[str]) -> dict:
    return Ticker(symbols).summary_profile


def report_text(selected_report: dict[str, Any]) -> str:
    profile = selected_report["profile"]
    fundamentals = selected_report["fundamentals"]
    scoring = selected_report["scoring"]

    lines: list[str] = []

    lines.append("[ COMPANY PROFILE ]")
    lines.append("-" * 20)

    for k, v in profile.items():
        if any(
            x in k
            for x in (
                "Key",
                "Disp",
                "company",
                "executive",
                "longBusinessSummary",
                "maxAge",
            )
        ):
            continue
        lines.append(f"{k:<20}: {v}")

    lines.append("")
    lines.append("Business Summary:")
    wrapped = textwrap.fill(profile.get("longBusinessSummary", ""), width=60)
    lines.extend(wrapped.split("\n"))

    lines.append("")
    lines.append("[ FINANCIAL FUNDAMENTALS ]")
    lines.append("-" * 27)

    for key in sorted(fundamentals.keys()):
        lines.append(f"{key:<25}: {format_value(key, fundamentals[key])}")

    lines.append(f"{'totalScore':<25}: {scoring['total_score']} / 100")
    lines.append(f"{'grade':<25}: {scoring['grade']}")

    return "\n".join(lines)


def get_fundamentals(symbols: list[str]) -> dict:
    resp = schwab_state.get_instruments(
        symbols=symbols,
        projection=Client.Instrument.Projection.FUNDAMENTAL,
    )
    resp.raise_for_status()
    return {
        fundamentals["symbol"]: fundamentals["fundamental"]
        for fundamentals in resp.json().get("instruments", [])
    }


def get_greeting() -> str:
    """A personal touch."""
    if today.hour < 12:
        return "Good morning."
    elif today.hour < 18:
        return "Good afternoon."
    else:
        return "Good evening."


def is_death_cross(candles_df: DataFrame) -> bool:
    """Check if the most recent candle shows a bearish MA alignment."""
    latest = candles_df.iloc[-1]
    return not latest.empty and latest["SMA20"] < latest["SMA50"] < latest["EMA200"]


def open_file(filepath: str) -> None:
    system = platform.system()
    if system == "Windows":
        os.startfile(filepath)
    elif system == "Darwin":
        os.system(f'open "{filepath}"')
    else:
        os.system(f'xdg-open "{filepath}"')


def safe_lookup(d: Any, key: Any) -> Any:
    """In the instance the dictionary is also null, return null."""
    return d.get(key) if isinstance(d, dict) else None


def format_value(key: str, value: Any) -> str:
    if value is None or (value == 0 and "Change" not in key):
        return "N/A"
    if isinstance(value, str) and " 00:0" in value:
        return value.split(" 00:0")[0]
    k = key.lower()
    percent = {"margin", "yield", "percent", "growth", "change"}
    currency = {"high", "low", "dividendamount", "eps", "bookvalue", "price"}
    ratio = {"ratio", "beta", "coverage", "factor", "debt", "equity"}
    if any(word in k for word in percent):
        return f"{value:.2f}%"
    if "marketcap" in k:
        for threshold, suffix in [(1e12, "T"), (1e9, "B"), (1e6, "M")]:
            if value >= threshold:
                return f"${value / threshold:.2f}{suffix}"
        return f"${value:,.2f}"
    if any(word in k for word in currency):
        return f"${value:,.2f}"
    if any(word in k for word in ratio):
        return f"{value:.2f}" if not isinstance(value, str) else value
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.2f}" if value <= 1000 else f"{value:,.0f}"
    return str(value)


def has_recent_crossovers(crossovers: dict) -> bool:
    """True if any signal occurred within the last 7 days."""
    cutoff = today - datetime.timedelta(days=7)
    return any(
        datetime.datetime.fromisoformat(ts) >= cutoff
        for signals in (crossovers or {}).values()
        for timestamps in (signals or {}).values()
        for ts in timestamps
    )
