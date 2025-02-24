import os
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from string import Template

import requests
from bs4 import BeautifulSoup

from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o", temperature=0.4)


def get_recent_filings():
    soup = BeautifulSoup(
        requests.get(
            "https://www.sec.gov/cgi-bin/browse-edgar?company=&CIK=&type=8-k&owner=include&count=40&action=getcurrent",
            headers={"User-Agent": os.getenv("SEC_AGENT")},
        ).content,
        "html.parser",
    )
    data = []
    for row in soup.find_all("table")[6].find_all("tr")[1:]:
        cells = row.find_all("td")
        if len(cells) >= 6:
            urls = [f"https://www.sec.gov{a["href"]}" for a in cells[1].find_all("a")]
            data.append(
                {
                    "date": datetime.strptime(
                        cells[3].get_text(), "%Y-%m-%d%H:%M:%S"
                    ).strftime("%Y-%m-%d %I:%M:%S %p"),
                    "cik": urls[1].split("/")[6],
                    "url": urls[1],
                    "redirect": urls[0],
                }
            )
    return data


def send_analysis(informational_analysis, ticker, filing, stock):
    msg = MIMEMultipart()
    msg["From"] = os.getenv("SMTP_FROM")
    msg["Subject"] = f"Quotient Analysis For: {ticker}"
    with open("assets/email.html", "r") as f:
        data = {
            "ticker": ticker,
            "analysis": informational_analysis,
            **filing,
            **stock,
        }
        msg.attach(
            MIMEText(
                Template(f.read()).safe_substitute(data),
                "html",
            )
        )
    with smtplib.SMTP(os.getenv("SMTP_HOST"), port=587) as smtp:
        smtp.starttls()
        smtp.login(os.getenv("SMTP_USERNAME"), os.getenv("SMTP_PASSWORD"))
        for email in os.getenv("EMAIL_LIST").split(","):
            msg["To"] = email
            smtp.sendmail(os.getenv("SMTP_FROM"), email, msg.as_string())


def log(msg, level):
    colors = {"info": "\033[34m", "good": "\033[92m", "bad": "\033[31m"}
    print(f"{colors[level]}{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} - {msg}")


class Logger:
    def __init__(self):
        self.file = open(f"logs\\{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt", "w")
        self.file.flush()
        self.stdout = sys.stdout  # Keep original stdout

    def write(self, message):
        if message.strip():
            self.file.write(message[5:] + "\n")
        self.stdout.write(message)

    def flush(self):
        self.stdout.flush()
        self.file.flush()
