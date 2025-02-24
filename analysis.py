import os
import threading

import markdown
import requests
import yfinance
from bs4 import BeautifulSoup
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from util import send_analysis, log, llm


def stock_metrics(ticker):
    ticker = yfinance.Ticker(ticker)
    fast_info = ticker.fast_info
    return {
        "day_high": round(fast_info["dayHigh"], 3),
        "day_low": round(fast_info["dayLow"], 3),
        "last_price": round(fast_info["lastPrice"], 3),
        "last_volume": fast_info["lastVolume"],
        "market_cap": round(fast_info["marketCap"], 3),
        "open": round(fast_info["open"], 3),
        "previous_close": round(fast_info["previousClose"], 3),
        "average_volume": fast_info["threeMonthAverageVolume"],
        "close_deviation": round(
            (
                (fast_info["lastPrice"] - fast_info["previousClose"])
                / fast_info["previousClose"]
            )
            * 100,
            2,
        ),
        "turnover": round(
            (fast_info["lastPrice"] * fast_info["lastVolume"])
            / fast_info["marketCap"]
            * 100,
            3,
        ),
    }


def inquire_filing(url, prompt):
    soup = BeautifulSoup(
        requests.get(url, headers={"User-Agent": os.getenv("SEC_AGENT")}).content,
        "html.parser",
    )
    chain = (
        PromptTemplate(
            input_variables=["document"],
            template=prompt + "\n\n{document}",
        )
        | llm
        | StrOutputParser()
    )
    return chain.invoke({"document": soup.find("document").text})


def analyze_filing(filing):
    response = requests.get(
        "https://www.sec.gov/files/company_tickers.json",
        headers={"User-Agent": os.getenv("SEC_AGENT")},
    )
    ticker = None
    for item in response.json().values():
        if str(item["cik_str"]).zfill(10) == str(filing["cik"]).zfill(10):
            ticker = item["ticker"]
    if not ticker:
        log(f"CIK ({filing["cik"]}) not associated with ticker.", "bad")
        return

    log(
        f"Analyzing {ticker} ({filing["cik"]}), determining market cap eligibility.",
        "info",
    )
    try:
        stock = stock_metrics(ticker)
        if stock["market_cap"] <= int(os.getenv("MARKET_CAP_THRESHOLD")):
            log(f"Market cap ({stock["market_cap"]}) insufficient for analysis.", "bad")
            return
        log(
            f"Market cap ({stock["market_cap"]}) sufficient for analysis, determining volume eligibility.",
            "good",
        )
        if stock["average_volume"] >= int(os.getenv("VOLUME_THRESHOLD")):
            log(
                f"Volume ({stock["average_volume"]}) sufficient for analysis, determining impact eligibility.",
                "good",
            )
        else:
            log(
                f"Volume ({stock["average_volume"]}) insufficient for analysis, determining turnover eligibility.",
                "bad",
            )

            if abs(stock["turnover"]) >= float(os.getenv("TURNOVER_THRESHOLD")):
                log(
                    f"Turnover ({stock["turnover"]}%) sufficient for analysis, determining impact eligibility.",
                    "good",
                )
            else:
                log(
                    f"Turnover ({stock["turnover"]}%) insufficient for analysis.",
                    "bad",
                )
                return
        if inquire_filing(
            filing["url"],
            os.getenv("DETERMINATION_PROMPT"),
        ).startswith("Yes"):
            log(
                "Impact eligibility sufficient for an investment, completing analysis.",
                "good",
            )
            threading.Thread(
                target=lambda: send_analysis(
                    markdown.markdown(
                        inquire_filing(
                            filing["url"], os.getenv("EXPLANATION_PROMPT")
                        ).replace("8-K", "")
                    ),
                    ticker,
                    filing,
                    stock,
                )
            ).start()
        else:
            log("Impact eligibility insufficient for an investment.", "bad")
    except Exception as e:
        log(f"An error occurred during analysis: {e}", "bad")
