#!/usr/bin/env python3
"""Scraper IPcuria – generuje RSS feed předběžných rozhodnutí SDEU (poslední měsíc)."""

import os
import re
from datetime import datetime, timezone, timedelta
from xml.etree.ElementTree import Element, SubElement, ElementTree, indent

import requests
from bs4 import BeautifulSoup

URL = "https://ipcuria.eu/all_preliminary_rulings.php"
CURIA_BASE = "https://curia.europa.eu/juris/liste.do?num="
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "ipcuria_feed.xml")
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def fetch_decisions():
    """Stáhne stránku a vrátí rozhodnutí z posledního měsíce."""
    resp = requests.get(URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    cutoff = datetime.now(timezone.utc) - timedelta(days=31)
    decisions = []

    # Stránka má strukturu: text "Judgement of DD Mon YYYY, " + <a href='case?reference=C-XXX/YY'>
    # následovaný <i>název</i> a <span class='breadcrumbs'> s kategoriemi
    # Oddělené <hr> tagy
    body_html = str(soup)

    # Rozdělíme podle <hr> – každý blok je jedno rozhodnutí
    blocks = re.split(r"<hr\s*/?>", body_html)

    for block in blocks:
        block_soup = BeautifulSoup(block, "html.parser")
        text = block_soup.get_text()

        # Hledáme vzor "Judgement of DD Mon YYYY" nebo "Order of DD Mon YYYY"
        date_match = re.search(
            r"(Judgement|Judgment|Order)\s+of\s+(\d{1,2}\s+\w{3}\s+\d{4})", text
        )
        if not date_match:
            continue

        decision_type = date_match.group(1)
        if decision_type in ("Judgement", "Judgment"):
            decision_type = "Judgment"

        date_str = date_match.group(2)
        try:
            dt = datetime.strptime(date_str, "%d %b %Y").replace(tzinfo=timezone.utc)
        except ValueError:
            continue

        # Filtrujeme jen poslední měsíc
        if dt < cutoff:
            continue

        # Číslo případu z odkazu
        link_tag = block_soup.find("a", href=re.compile(r"case\?reference="))
        if not link_tag:
            continue

        case_ref = link_tag.get_text(strip=True)

        # Název případu z <i>
        name_tag = block_soup.find("i")
        case_name = name_tag.get_text(strip=True) if name_tag else ""

        # Kategorie z breadcrumbs
        categories = []
        for span in block_soup.select("span.breadcrumbs"):
            cats = [a.get_text(strip=True) for a in span.find_all("a")]
            if cats:
                categories.append(" > ".join(cats))

        decisions.append({
            "case_ref": case_ref,
            "case_name": case_name,
            "date": dt,
            "date_str": date_str,
            "decision_type": decision_type,
            "categories": categories,
            "ipcuria_url": f"https://ipcuria.eu/case?reference={case_ref}",
            "curia_url": f"{CURIA_BASE}{case_ref}",
        })

    return decisions


def build_rss(decisions):
    """Vytvoří RSS 2.0 XML z rozhodnutí."""
    rss = Element("rss", version="2.0")
    channel = SubElement(rss, "channel")

    SubElement(channel, "title").text = "IPcuria – CJEU preliminary rulings (IP)"
    SubElement(channel, "link").text = URL
    SubElement(channel, "description").text = (
        "Recent preliminary rulings by the CJEU in intellectual property matters (via IPcuria)"
    )
    SubElement(channel, "language").text = "en"
    SubElement(channel, "lastBuildDate").text = datetime.now(timezone.utc).strftime(
        "%a, %d %b %Y %H:%M:%S +0000"
    )

    for d in decisions:
        item = SubElement(channel, "item")

        title = f"{d['decision_type']} {d['case_ref']}"
        if d["case_name"]:
            title += f" ({d['case_name']})"
        SubElement(item, "title").text = title

        SubElement(item, "link").text = d["curia_url"]
        SubElement(item, "guid", isPermaLink="false").text = d["case_ref"]

        desc_parts = [
            f"{d['decision_type']} of {d['date_str']}, {d['case_ref']}",
        ]
        if d["case_name"]:
            desc_parts[0] += f" ({d['case_name']})"
        for cat in d["categories"]:
            desc_parts.append(f"- {cat}")
        desc_parts.append(f"IPcuria: {d['ipcuria_url']}")
        desc_parts.append(f"CURIA: {d['curia_url']}")

        SubElement(item, "description").text = "\n".join(desc_parts)

        SubElement(item, "pubDate").text = d["date"].strftime(
            "%a, %d %b %Y 00:00:00 +0000"
        )

    return rss


def main():
    print("Stahuji IPcuria – předběžná rozhodnutí SDEU...")
    decisions = fetch_decisions()
    print(f"Nalezeno {len(decisions)} rozhodnutí z posledního měsíce")

    for d in decisions:
        print(f"  - {d['case_ref']} {d['case_name']} ({d['date_str']})")

    rss = build_rss(decisions)
    indent(rss, space="  ")

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    tree = ElementTree(rss)
    tree.write(OUTPUT, encoding="unicode", xml_declaration=True)
    print(f"RSS feed zapsán do {OUTPUT}")


if __name__ == "__main__":
    main()
