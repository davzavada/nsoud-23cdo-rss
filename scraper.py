#!/usr/bin/env python3
"""Scraper úřední desky NS ČR – generuje RSS feed pro senát 23 Cdo."""

import os
import re
from datetime import datetime, timezone
from xml.etree.ElementTree import Element, SubElement, ElementTree, indent

import requests
from bs4 import BeautifulSoup

URL = "https://www.nsoud.cz/uredni-deska/obcanskopravni-a-obchodni-kolegium/vyhlasovana-rozhodnuti"
BASE_URL = "https://www.nsoud.cz"
SENAT = "23 Cdo"
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "feed.xml")


def fetch_decisions():
    """Stáhne stránku a vrátí seznam rozhodnutí senátu 23 Cdo."""
    resp = requests.get(URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    decisions = []
    # Hledáme tabulku s rozhodnutími
    for row in soup.select("table tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        case_number = cells[0].get_text(strip=True)
        # Normalizujeme mezery pro porovnání
        case_normalized = re.sub(r"\s+", " ", case_number)

        if SENAT not in case_normalized:
            continue

        date_text = cells[1].get_text(strip=True)

        # Hledáme PDF odkaz
        pdf_link = ""
        link_tag = row.find("a", href=True)
        if link_tag:
            href = link_tag["href"]
            pdf_link = href if href.startswith("http") else BASE_URL + href

        decisions.append({
            "case_number": case_normalized,
            "date": date_text,
            "pdf_url": pdf_link,
        })

    return decisions


def build_rss(decisions):
    """Vytvoří RSS 2.0 XML z rozhodnutí."""
    rss = Element("rss", version="2.0", attrib={
        "xmlns:dc": "http://purl.org/dc/elements/1.1/"
    })
    channel = SubElement(rss, "channel")

    SubElement(channel, "title").text = "NS ČR – senát 23 Cdo – vyhlašovaná rozhodnutí"
    SubElement(channel, "link").text = URL
    SubElement(channel, "description").text = (
        "Rozhodnutí senátu 23 Cdo vyhlášená na úřední desce Nejvyššího soudu ČR"
    )
    SubElement(channel, "language").text = "cs"
    SubElement(channel, "lastBuildDate").text = datetime.now(timezone.utc).strftime(
        "%a, %d %b %Y %H:%M:%S +0000"
    )

    for d in decisions:
        item = SubElement(channel, "item")
        SubElement(item, "title").text = d["case_number"]

        if d["pdf_url"]:
            SubElement(item, "link").text = d["pdf_url"]
            SubElement(item, "guid", isPermaLink="true").text = d["pdf_url"]
        else:
            # Fallback GUID z case number
            SubElement(item, "guid", isPermaLink="false").text = d["case_number"]

        SubElement(item, "description").text = (
            f"Rozhodnutí {d['case_number']} vyhlášeno {d['date']}"
        )

        # Převod data DD.MM.YYYY
        try:
            dt = datetime.strptime(d["date"], "%d.%m.%Y").replace(tzinfo=timezone.utc)
            SubElement(item, "pubDate").text = dt.strftime(
                "%a, %d %b %Y 12:00:00 +0000"
            )
            SubElement(item, "dc:date").text = dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    return rss


def main():
    print(f"Stahuji úřední desku NS ČR...")
    decisions = fetch_decisions()
    print(f"Nalezeno {len(decisions)} rozhodnutí senátu {SENAT}")

    for d in decisions:
        print(f"  - {d['case_number']} ({d['date']})")

    rss = build_rss(decisions)
    indent(rss, space="  ")

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    tree = ElementTree(rss)
    tree.write(OUTPUT, encoding="unicode", xml_declaration=True)
    print(f"RSS feed zapsán do {OUTPUT}")


if __name__ == "__main__":
    main()
