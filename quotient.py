import os
import sys
import time
from datetime import datetime

from pytz import timezone

from analysis import analyze_filing
from util import Logger, log, get_recent_filings

if __name__ == "__main__":
    sys.stdout = Logger()
    with open(".env", "r") as file:
        for line in file:
            key, value = line.replace("\n", "").split("=", 1)
            os.environ[key] = value
    log("Quotient is running...", "info")
    while True:
        now = datetime.now(timezone("US/Eastern"))
        if now.weekday() >= 5 or not (6 <= now.hour < 22):
            time.sleep(60)
            continue
        with open(".cik", "r") as cache:
            cached_cik = cache.read()
        recent_filings = get_recent_filings()[::-1]
        for recent_filing in recent_filings[
            next(
                (
                    i
                    for i, item in enumerate(recent_filings)
                    if item.get("cik") == cached_cik
                ),
                -1,
            )
            + 1 :
        ]:
            analyze_filing(recent_filing)
        with open(".cik", "w") as cache:
            cache.write(recent_filings[-1]["cik"])
        time.sleep(60)
