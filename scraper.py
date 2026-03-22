#!/usr/bin/env python3
"""Scraper úřední desky NS ČR – generuje RSS feed pro senát 23 Cdo."""

import os
import re
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element, SubElement, ElementTree, indent

import requests
from bs4 import BeautifulSoup

URL = "https://www.nsoud.cz/uredni-deska/obcanskopravni-a-obchodni-kolegium/vyhlasovana-rozhodnuti"
BASE_URL = "https://www.nsoud.cz"
SENAT = "23 Cdo"
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "feed.xml")


def _detect_decision_type(pdf_url):
    """Detekuje typ rozhodnutí z názvu PDF souboru."""
    url_lower = pdf_url.lower()
    if "rozsudku" in url_lower or "rozsudek" in url_lower:
        return "Rozsudek"
    if "usneseni" in url_lower or "usnesen" in url_lower:
        return "Usnesení"
    return "Rozhodnutí"


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

        decision_type = _detect_decision_type(pdf_link) if pdf_link else "Rozhodnutí"

        decisions.append({
            "case_number": case_normalized,
            "date": date_text,
            "pdf_url": pdf_link,
            "decision_type": decision_type,
        })

    return decisions


DC_NS = "http://purl.org/dc/elements/1.1/"
PRISM_NS = "http://prismstandard.org/namespaces/basic/2.0/"

# Registrujeme namespace prefixy aby XML výstup byl čistý
ET.register_namespace("dc", DC_NS)
ET.register_namespace("prism", PRISM_NS)


def build_rss(decisions):
    """Vytvoří RSS 2.0 XML s Dublin Core a PRISM metadaty pro Zotero."""
    rss = Element("rss", version="2.0")

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
        SubElement(item, "title").text = (
            f"{d['decision_type']} {d['case_number']}"
        )

        if d["pdf_url"]:
            SubElement(item, "link").text = d["pdf_url"]
            SubElement(item, "guid", isPermaLink="true").text = d["pdf_url"]
            SubElement(item, "enclosure", url=d["pdf_url"], type="application/pdf")
        else:
            SubElement(item, "guid", isPermaLink="false").text = d["case_number"]

        SubElement(item, "description").text = (
            f"{d['decision_type']} Nejvyššího soudu sp. zn. {d['case_number']}, "
            f"vyhlášeno dne {d['date']}. "
            f"Senát 23 Cdo, občanskoprávní a obchodní kolegium."
        )

        # Dublin Core metadata – Zotero je parsuje
        SubElement(item, f"{{{DC_NS}}}creator").text = "Nejvyšší soud"
        SubElement(item, f"{{{DC_NS}}}publisher").text = "Nejvyšší soud"
        SubElement(item, f"{{{DC_NS}}}type").text = d["decision_type"]
        SubElement(item, f"{{{DC_NS}}}source").text = (
            "Úřední deska – občanskoprávní a obchodní kolegium"
        )
        SubElement(item, f"{{{DC_NS}}}language").text = "cs"
        SubElement(item, f"{{{DC_NS}}}identifier").text = d["case_number"]
        SubElement(item, f"{{{DC_NS}}}subject").text = "občanské právo; obchodní právo"

        # PRISM metadata
        SubElement(item, f"{{{PRISM_NS}}}publicationName").text = (
            "Sbírka rozhodnutí Nejvyššího soudu"
        )

        # Převod data DD.MM.YYYY na RFC 822 + dc:date (ISO 8601)
        try:
            dt = datetime.strptime(d["date"], "%d.%m.%Y").replace(tzinfo=timezone.utc)
            SubElement(item, "pubDate").text = dt.strftime(
                "%a, %d %b %Y 00:00:00 +0000"
            )
            SubElement(item, f"{{{DC_NS}}}date").text = dt.strftime("%Y-%m-%d")
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
