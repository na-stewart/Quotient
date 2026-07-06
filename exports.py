from __future__ import annotations

import datetime
import math
import os
import textwrap
from pathlib import Path
from typing import Any

import holidays
import pandas as pd
import plotly.graph_objects as go
from PIL import Image, ImageDraw, ImageFont
from plotly.subplots import make_subplots
from reportlab.pdfgen import canvas

from utils import format_value, today

export_colors = {
    "bg": "#FFFFFF",
    "header_bg": "#1B2A4A",
    "header_text": "#FFFFFF",
    "section_title": "#1B2A4A",
    "section_bg": "#F7F8FA",
    "body_text": "#333333",
    "muted_text": "#777777",
    "key_text": "#555555",
    "value_text": "#111111",
    "divider": "#D0D5DD",
    "badge_bg": "#F0F4FF",
    "badge_border": "#A3B8EF",
    "grade_A": "#16A34A",
    "grade_B": "#2563EB",
    "grade_C": "#D97706",
    "grade_D": "#DC2626",
    "grade_F": "#991B1B",
    "chart_border": "#E2E8F0",
    "chart_bg": "#FAFBFC",
    "grid_line": "#E8ECF0",
}
export_width = 1500
export_margin = 50
export_gutter = 40
export_header_h = 110
export_section_gap = 24
export_line_height = 24
export_kv_live_height = 26
export_badge_w = 140
export_badge_h = 100
export_corner_radius = 12
export_chart_zone_pad = 16
export_fund_cols = 3
export_fund_cell_pad = 8
export_font_path = "resources/dejavu-sans-bold.ttf"


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(export_font_path, size)
    except OSError:
        for p in (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
        return ImageFont.load_default()


export_font_title = _load_font(32)
export_font_header = _load_font(18)
export_font_body = _load_font(15)
export_font_small = _load_font(13)
export_font_badge = _load_font(36)
export_font_badge_s = _load_font(14)
export_font_kv_key = _load_font(12)
export_font_kv_val = _load_font(14)


def _rounded_rect(
    draw: ImageDraw.ImageDraw,
    bbox: tuple[int, int, int, int],
    radius: int,
    fill: str | None = None,
    outline: str | None = None,
    width: int = 1,
) -> None:
    try:
        draw.rounded_rectangle(
            bbox, radius=radius, fill=fill, outline=outline, width=width
        )
    except AttributeError:
        draw.rectangle(bbox, fill=fill, outline=outline, width=width)


def _draw_divider(draw: ImageDraw.ImageDraw, x: int, y: int, length: int) -> int:
    draw.line([(x, y), (x + length, y)], fill=export_colors["divider"], width=1)
    return y + 12


def _grade_color(grade: str) -> str:
    if grade.startswith("A"):
        return export_colors["grade_A"]
    if grade.startswith("B"):
        return export_colors["grade_B"]
    if grade.startswith("C"):
        return export_colors["grade_C"]
    if grade.startswith("D"):
        return export_colors["grade_D"]
    return export_colors["grade_F"]


def _text_bbox(draw, text, font):
    return draw.textbbox((0, 0), text, font=font)


def _multiline_height(
    draw: ImageDraw.ImageDraw, text: str, font, spacing: int = 4
) -> float:
    bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=spacing)
    return bbox[3] - bbox[1]


def _draw_arrow(
    draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, direction: str, fill: str
) -> None:
    """Draw a filled triangle arrow. direction is 'up' or 'down'."""
    half = size // 2
    if direction == "up":
        points = [(cx, cy - half), (cx - half, cy + half), (cx + half, cy + half)]
    else:
        points = [(cx, cy + half), (cx - half, cy - half), (cx + half, cy - half)]
    draw.polygon(points, fill=fill)


def _flatten_crossovers(crossovers: dict | None) -> list[Any] | list[tuple]:
    """Flatten the crossovers dict into a sorted list of tuples, most recent first."""
    if not crossovers:
        return []

    rows: list[tuple] = []
    for sentiment, signals in crossovers.items():
        if not signals:
            continue
        for signal_name, timestamps in signals.items():
            for timestamp in timestamps:
                timestamp_str = (
                    str(timestamp).split(".")[0]
                    if not isinstance(timestamp, str)
                    else timestamp.split(".")[0]
                )
                rows.append((timestamp_str, sentiment, signal_name))

    rows.sort(key=lambda r: r[0], reverse=True)
    return rows[:3]


def _profile_keys(profile: dict) -> list[tuple[str, str]]:
    skip = ("Key", "Disp", "company", "executive", "longBusinessSummary", "maxAge")
    pairs = []
    for k, v in profile.items():
        if any(s in k for s in skip):
            continue
        pairs.append((k, str(v)))
    return pairs


def _calc_heights(
    profile_pairs: list[tuple[str, str]],
    fundamentals: dict,
    export_wrapped: str,
    n_crossover_rows: int = 0,
) -> tuple[int, int, int]:
    # Left column: profile + summary + crossovers
    left_h = 0
    left_h += 30 + 12  # Profile title + divider
    left_h += len(profile_pairs) * export_kv_live_height
    left_h += export_section_gap
    left_h += 30 + 12  # Summary title + divider
    export_lines = export_wrapped.count("\n") + 1
    left_h += export_lines * export_line_height
    left_h += export_section_gap
    if n_crossover_rows > 0:
        left_h += 30 + 12  # Crossovers title + divider
        left_h += min(n_crossover_rows, 8) * export_kv_live_height  # Capped at 8 rows
        left_h += export_section_gap

    # Right column: fundamentals grid + score card
    n_fund = len(fundamentals)
    fund_rows = math.ceil(n_fund / export_fund_cols)
    cell_h = 52
    right_h = 0
    right_h += 30 + 12  # Title + divider
    right_h += fund_rows * cell_h
    right_h += export_section_gap
    right_h += export_badge_h + 20  # Scorecard
    right_h += export_section_gap
    body_zone_h = max(left_h, right_h)
    chart_zone_h = max(int((export_header_h + body_zone_h + 60) / 3), 260)
    total_h = export_header_h + chart_zone_h + body_zone_h + 60
    return chart_zone_h, body_zone_h, total_h


def export_report(report: dict) -> str:
    """Generate a styled PNG report card, returns the output file path."""

    profile = report["profile"]
    fundamentals = report["fundamentals"]
    scoring = report["scoring"]

    ticker = report.get("symbol", "UNKNOWN")
    sector = profile.get("sector", "Unknown")
    industry = profile.get("industry", "Unknown")
    summary = profile.get("longBusinessSummary", "")

    score = scoring["total_score"]
    grade = scoring["grade"]
    crossovers = report.get("indicators", {})

    crossovers = {
        k: {sk: sv for sk, sv in v.items() if not sk.startswith("held_")}
        for k, v in crossovers.items()
    }
    crossover_rows = _flatten_crossovers(crossovers)

    # Load chart
    chart: Image.Image | None = None
    chart_path = Path(report.get("chart", ""))
    if chart_path.exists():
        chart = Image.open(chart_path).convert("RGB")

    # Pre-process
    profile_pairs = _profile_keys(profile)
    export_wrapped = textwrap.fill(summary, width=65)

    # Compute dynamic sizes
    chart_zone_h, body_zone_h, height = _calc_heights(
        profile_pairs,
        fundamentals,
        export_wrapped,
        n_crossover_rows=len(crossover_rows),
    )

    content_w = export_width - 2 * export_margin
    col_w = (content_w - export_gutter) // 2
    col_left_x = export_margin
    col_right_x = export_margin + col_w + export_gutter

    img = Image.new("RGB", (export_width, height), export_colors["bg"])
    draw = ImageDraw.Draw(img)

    # Header bar
    draw.rectangle(
        (0, 0, export_width, export_header_h), fill=export_colors["header_bg"]
    )

    # Logo thumbnail
    logo_size = export_header_h - 20
    logo_path = Path("resources/logo.png")
    text_indent = export_margin
    if logo_path.exists():
        logo = Image.open(logo_path).convert("RGBA")
        logo.thumbnail((logo_size, logo_size))
        logo_x = export_margin
        logo_y = (export_header_h - logo.height) // 2
        img.paste(logo, (logo_x, logo_y), logo if logo.mode == "RGBA" else None)
        text_indent = export_margin + logo.width + 16
    candles = report["candles"]
    title = ticker
    if candles is not None and not candles.empty:
        last = candles.iloc[-1]
        if pd.notna(last["close"]):
            title = f"{ticker} / {last['close']:.2f}"
    draw.text(
        (text_indent, 24),
        title,
        font=export_font_title,
        fill=export_colors["header_text"],
    )
    draw.text(
        (text_indent, 70),
        f"{sector}  •  {industry}",
        font=export_font_small,
        fill="#94A3B8",
    )

    # Score badge
    bx = export_width - export_margin - export_badge_w
    by = (export_header_h - export_badge_h) // 2

    _rounded_rect(
        draw,
        (bx, by, bx + export_badge_w, by + export_badge_h),
        radius=export_corner_radius,
        fill=export_colors["badge_bg"],
        outline=export_colors["badge_border"],
        width=2,
    )

    score_txt = f"{score}/100"
    sb = _text_bbox(draw, score_txt, export_font_header)
    sw = sb[2] - sb[0]
    draw.text(
        (bx + (export_badge_w - sw) // 2, by + 16),
        score_txt,
        font=export_font_header,
        fill=_grade_color(grade),
    )

    grade_txt = grade
    gtb = _text_bbox(draw, grade_txt, export_font_badge)
    gtw = gtb[2] - gtb[0]
    draw.text(
        (bx + (export_badge_w - gtw) // 2, by + 44),
        grade_txt,
        font=export_font_badge,
        fill=_grade_color(grade),
    )

    # Chart zone
    chart_y0 = export_header_h
    chart_y1 = export_header_h + chart_zone_h

    # Subtle background card for the chart area
    _rounded_rect(
        draw,
        (export_margin, chart_y0 + 10, export_width - export_margin, chart_y1 - 6),
        radius=export_corner_radius,
        fill=export_colors["chart_bg"],
        outline=export_colors["chart_border"],
        width=1,
    )

    if chart:
        avail_w = content_w - 2 * export_chart_zone_pad
        avail_h = chart_zone_h - 2 * export_chart_zone_pad - 10
        chart.thumbnail((avail_w, avail_h))

        # Centre chart horizontally and vertically within zone
        cx = export_margin + (content_w - chart.width) // 2
        cy = chart_y0 + (chart_zone_h - chart.height) // 2
        img.paste(chart, (cx, cy))
    else:
        placeholder = "[ Chart not available ]"
        pb = _text_bbox(draw, placeholder, export_font_body)
        pw = pb[2] - pb[0]
        draw.text(
            (export_margin + (content_w - pw) // 2, chart_y0 + chart_zone_h // 2 - 10),
            placeholder,
            font=export_font_body,
            fill=export_colors["muted_text"],
        )
    body_y0 = chart_y1 + 10
    y = body_y0
    draw.text(
        (col_left_x, y),
        "COMPANY PROFILE",
        font=export_font_header,
        fill=export_colors["section_title"],
    )
    y += 30
    y = _draw_divider(draw, col_left_x, y, col_w)
    for k, v in profile_pairs:
        display_v = (v[:42] + "…") if len(v) > 44 else v
        draw.text(
            (col_left_x, y), k, font=export_font_body, fill=export_colors["key_text"]
        )
        draw.text(
            (col_left_x + 220, y),
            display_v,
            font=export_font_body,
            fill=export_colors["value_text"],
        )
        y += export_kv_live_height
    y += export_section_gap
    draw.text(
        (col_left_x, y),
        "BUSINESS SUMMARY",
        font=export_font_header,
        fill=export_colors["section_title"],
    )
    y += 30
    y = _draw_divider(draw, col_left_x, y, col_w)
    draw.multiline_text(
        (col_left_x, y),
        export_wrapped,
        font=export_font_body,
        fill=export_colors["body_text"],
        spacing=6,
    )

    # Advance y past the summary text
    export_h = _multiline_height(draw, export_wrapped, export_font_body, spacing=6)
    y += export_h + export_section_gap

    # Crossovers
    draw.text(
        (col_left_x, y),
        "INDICATORS",
        font=export_font_header,
        fill=export_colors["section_title"],
    )
    y += 30
    y = _draw_divider(draw, col_left_x, y, col_w)

    display_rows = crossover_rows[:8]  # cap at 8 most recent

    for ts_str, sentiment, signal_name in display_rows:
        is_bull = sentiment == "bullish"
        arrow_color = export_colors["grade_A"] if is_bull else export_colors["grade_D"]

        # Small arrow indicator
        _draw_arrow(
            draw,
            cx=col_left_x + 8,
            cy=y + 9,
            size=12,
            direction="up" if is_bull else "down",
            fill=arrow_color,
        )

        # Signal name (human-readable)
        nice_name = signal_name.replace("_", " ").title()
        draw.text(
            (col_left_x + 24, y),
            nice_name,
            font=export_font_body,
            fill=export_colors["value_text"],
        )

        # Timestamp right-aligned
        date_part = ts_str.split(" ")[0] if " " in ts_str else ts_str[:10]
        db = _text_bbox(draw, date_part, export_font_small)
        dw = db[2] - db[0]
        draw.text(
            (col_left_x + col_w - dw - 4, y + 2),
            date_part,
            font=export_font_small,
            fill=export_colors["muted_text"],
        )

        y += export_kv_live_height

    # Right column
    ry = body_y0

    draw.text(
        (col_right_x, ry),
        "FINANCIAL FUNDAMENTALS",
        font=export_font_header,
        fill=export_colors["section_title"],
    )
    ry += 30
    ry = _draw_divider(draw, col_right_x, ry, col_w)

    # Multi-column grid
    fund_items = sorted(fundamentals.items(), key=lambda kv: kv[0])
    n_fund = len(fund_items)
    fund_rows = math.ceil(n_fund / export_fund_cols)
    cell_w = col_w // export_fund_cols
    cell_h = 52

    for idx, (key, raw_val) in enumerate(fund_items):
        col = idx % export_fund_cols
        row = idx // export_fund_cols

        cell_x = col_right_x + col * cell_w
        cell_y = ry + row * cell_h

        # Alternating row shading
        if row % 2 == 0:
            _rounded_rect(
                draw,
                (cell_x + 2, cell_y, cell_x + cell_w - 2, cell_y + cell_h - 4),
                radius=6,
                fill=export_colors["section_bg"],
            )

        # Vertical separator between columns
        if col > 0:
            draw.line(
                [(cell_x, cell_y + 4), (cell_x, cell_y + cell_h - 8)],
                fill=export_colors["grid_line"],
                width=1,
            )

        value = format_value(key, raw_val)

        # Key label (small, muted, top of cell)
        draw.text(
            (cell_x + export_fund_cell_pad, cell_y + 4),
            key,
            font=export_font_kv_key,
            fill=export_colors["muted_text"],
        )
        # Value (larger, bold, below label)
        draw.text(
            (cell_x + export_fund_cell_pad, cell_y + 22),
            str(value),
            font=export_font_kv_val,
            fill=export_colors["value_text"],
        )

    ry += fund_rows * cell_h + export_section_gap

    # Score / Grade summary card
    score_card_w = col_w
    score_card_h = export_badge_h + 10

    _rounded_rect(
        draw,
        (col_right_x, ry, col_right_x + score_card_w, ry + score_card_h),
        radius=export_corner_radius,
        fill=export_colors["section_bg"],
        outline=export_colors["divider"],
        width=1,
    )

    # Large grade letter on the left of the card
    glb = _text_bbox(draw, grade, export_font_badge)
    glw = glb[2] - glb[0]
    draw.text(
        (col_right_x + 30, ry + 18),
        grade,
        font=export_font_badge,
        fill=_grade_color(grade),
    )

    # Score label + value beside the grade
    label_x = col_right_x + 30 + glw + 24
    draw.text(
        (label_x, ry + 20),
        "Total Score",
        font=export_font_kv_key,
        fill=export_colors["muted_text"],
    )
    draw.text(
        (label_x, ry + 40),
        f"{score} / 100",
        font=export_font_header,
        fill=_grade_color(grade),
    )

    bar_x = label_x
    bar_y = ry + 70
    bar_w = score_card_w - (30 + glw + 24) - 40
    bar_h = 12

    _rounded_rect(
        draw,
        (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h),
        radius=6,
        fill=export_colors["grid_line"],
    )
    filled_w = int(bar_w * score / 100)
    if filled_w > 0:
        _rounded_rect(
            draw,
            (bar_x, bar_y, bar_x + filled_w, bar_y + bar_h),
            radius=6,
            fill=_grade_color(grade),
        )

    # Footer
    footer_y = height - 30
    draw.line(
        [(export_margin, footer_y - 8), (export_width - export_margin, footer_y - 8)],
        fill=export_colors["divider"],
        width=1,
    )
    draw.text(
        (export_margin, footer_y),
        f"https://github.com/na-stewart/Quotient",
        font=export_font_small,
        fill=export_colors["muted_text"],
    )

    dir_path = os.path.join("resources", "exports", today.strftime("%Y-%m-%d"))
    os.makedirs(dir_path, exist_ok=True)
    fig_path = os.path.join(dir_path, f"{report["symbol"].upper()}.png")
    img.save(str(fig_path), quality=95)
    return fig_path


def pngs_to_pdf(png_paths: list[Path]) -> str:
    first_img = Image.open(png_paths[0])
    w, h = first_img.size
    parent_dir = os.path.join(os.path.expanduser("~"), "Documents", "Quotient")
    os.makedirs(parent_dir, exist_ok=True)
    file_path = os.path.join(
        parent_dir,
        datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".pdf",
    )
    c = canvas.Canvas(file_path, pagesize=(w, h))
    for i, png_path in enumerate(png_paths):
        img = Image.open(png_path)
        img_w, img_h = img.size
        c.setPageSize((img_w, img_h))
        c.drawImage(str(png_path), 0, 0, width=img_w, height=img_h)
        c.showPage()
    c.save()
    return file_path


def plot_candles(report: dict) -> str:
    """
    Plots candlestick data, moving averages, and crossovers.

    Chart is saved as bytes to be referenced in charts.
    """
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.6, 0.2, 0.2],
        subplot_titles=(f"{report["symbol"]} Chart", "Volume", "RSI"),
    )
    fig.update_xaxes(
        rangebreaks=[
            dict(bounds=["sat", "mon"]),
            dict(
                values=[
                    dt.strftime("%Y-%m-%d")
                    for dt in pd.date_range(
                        start=today - datetime.timedelta(days=300), end=today
                    )
                    if dt in holidays.financial_holidays("NYSE")
                ]
            ),
        ]
    )
    fig.add_trace(
        go.Candlestick(
            x=report["candles"]["datetime"],
            open=report["candles"]["open"],
            high=report["candles"]["high"],
            low=report["candles"]["low"],
            close=report["candles"]["close"],
            name="Price",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=report["candles"]["datetime"],
            y=report["candles"]["SMA20"],
            mode="lines",
            name="SMA 20",
            line=dict(width=1),
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=report["candles"]["datetime"],
            y=report["candles"]["SMA50"],
            mode="lines",
            name="SMA 50",
            line=dict(width=1),
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=report["candles"]["datetime"],
            y=report["candles"]["EMA200"],
            mode="lines",
            name="EMA 200",
            line=dict(width=1),
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            x=report["candles"]["datetime"],
            y=report["candles"]["volume"],
            name="Volume",
            opacity=0.6,
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=report["candles"]["datetime"],
            y=report["candles"]["VOL_SMA50"],
            mode="lines",
            name="Vol SMA 50",
            line=dict(width=2),
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=report["candles"]["datetime"],
            y=report["candles"]["RSI"],
            mode="lines",
            name="RSI",
            line=dict(width=1),
        ),
        row=3,
        col=1,
    )
    fig.add_hline(y=70, line_dash="dash", line_width=1, opacity=0.6, row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_width=1, opacity=0.6, row=3, col=1)
    dt_to_high = dict(zip(report["candles"]["datetime"], report["candles"]["high"]))
    dt_to_low = dict(zip(report["candles"]["datetime"], report["candles"]["low"]))
    dt_to_rsi = dict(zip(report["candles"]["datetime"], report["candles"]["RSI"]))

    def _add_candle_arrows(date_times, direction):
        if direction == "bull":
            y = [
                dt_to_high[dt]
                + max((dt_to_high[dt] - dt_to_low[dt]) * 0.25, dt_to_high[dt] * 0.015)
                for dt in date_times
            ]
            sym = "triangle-up"
        else:
            y = [
                dt_to_low[dt]
                - max((dt_to_high[dt] - dt_to_low[dt]) * 0.25, dt_to_high[dt] * 0.015)
                for dt in date_times
            ]
            sym = "triangle-down"
        fig.add_trace(
            go.Scatter(
                x=date_times,
                y=y,
                mode="markers",
                marker=dict(symbol=sym, size=12),
                showlegend=False,
                hovertemplate="%{x}<extra></extra>",
            ),
            row=1,
            col=1,
        )

    def _add_rsi_markers(date_times, symbol_marker):
        fig.add_trace(
            go.Scatter(
                x=date_times,
                y=[dt_to_rsi[dt] for dt in date_times],
                mode="markers",
                marker=dict(symbol=symbol_marker, size=9),
                showlegend=False,
                hovertemplate="RSI %{y:.2f}<br>%{x}<extra></extra>",
            ),
            row=3,
            col=1,
        )

    bullish_cross_date_times = [
        dt
        for key, dts in report["indicators"]["bullish"].items()
        if "cross_above" in key
        for dt in dts
    ]
    bearish_cross_date_times = [
        dt
        for key, dts in report["indicators"]["bearish"].items()
        if "cross_below" in key
        for dt in dts
    ]
    _add_candle_arrows(sorted(set(bullish_cross_date_times)), "bull")
    _add_candle_arrows(sorted(set(bearish_cross_date_times)), "bear")
    _add_rsi_markers(report["indicators"]["bullish"].get("rsi_oversold", []), "circle")
    _add_rsi_markers(
        report["indicators"]["bearish"].get("rsi_overbought", []), "circle"
    )
    fig.update_layout(
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    fig.update_yaxes(title_text="RSI", range=[0, 100], row=3, col=1)
    dir_path = os.path.join("resources", "charts", today.strftime("%Y-%m-%d"))
    os.makedirs(dir_path, exist_ok=True)
    fig_path = os.path.join(dir_path, f"{report["symbol"].upper()}.png")
    fig.write_image(fig_path, width=1600, height=900, scale=2)
    return fig_path
