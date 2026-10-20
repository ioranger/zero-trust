"""Look candidate references up in Crossref by title and print the candidates.

Crossref is queried with the bibliographic form of the title, and the top hits
are printed with their DOI and metadata so a citation can be entered from the
authoritative record rather than from a search snippet.

    python -u artifacts/analysis/crossref_lookup_titles.py
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CANDIDATES = [
    "Enhancing the resilience of UAV networks against GPS spoofing attacks via byzantine distributed detection algorithm",
    "Dynamic Selection Techniques for Detecting GPS Spoofing Attacks on UAVs",
    "Multi-model fusion for robust detection and resilient mitigation of BeiDou spoofing in decentralized UAV swarm systems",
    "A Review of GNSS Spoofing Detection Based on Multi-Source Fusion",
    "Range-based Multi-Robot Integrity Monitoring Against Cyberattacks and Faults: An Anchor-Free Approach",
    "Trustworthy UAV Cooperative Localization: Information Analysis of Performance and Security",
    "A Hierarchical Blockchain-Based Trust Measurement Method for Drone Cluster Nodes",
    "SENTINEL: Integrity-Aware Cooperative Navigation for Connected UAV Swarms Under GNSS Spoofing",
    "Deep-Ensemble-Learning-Based GPS Spoofing Detection for Cellular-Connected UAVs",
    "A trustworthy data collection scheme based on active spot-checking in UAV-Assisted WSNs",
    "A Real-time Framework for Trust Monitoring in a Network of Unmanned Aerial Vehicles",
]


def query(title: str, rows: int = 3) -> list[dict]:
    url = ("https://api.crossref.org/works?query.bibliographic="
           + urllib.parse.quote(title) + f"&rows={rows}&select=DOI,title,container-title,"
           "author,issued,volume,page,type,publisher")
    req = urllib.request.Request(url, headers={"User-Agent": "paper-check/1.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)["message"]["items"]


def main() -> int:
    out = {}
    for title in CANDIDATES:
        print("=" * 120)
        print(f"QUERY: {title}")
        try:
            items = query(title)
        except Exception as e:
            print(f"  LOOKUP FAILED: {e}")
            print()
            continue
        for i, it in enumerate(items, 1):
            t = (it.get("title") or [""])[0]
            cont = (it.get("container-title") or [""])[0]
            yr = str((it.get("issued", {}).get("date-parts") or [[None]])[0][0])
            auth = "; ".join(f"{a.get('family','')}, {a.get('given','')}".strip(", ")
                             for a in it.get("author", [])[:6])
            print(f"  [{i}] {it.get('DOI')}")
            print(f"      title    : {t}")
            print(f"      venue   : {cont}  ({yr})  vol {it.get('volume','')} p {it.get('page','')}")
            print(f"      authors : {auth}")
            out.setdefault(title, []).append({
                "doi": it.get("DOI"), "title": t, "container": cont, "year": yr,
                "volume": it.get("volume", ""), "page": it.get("page", ""),
                "authors": auth, "type": it.get("type", ""),
                "publisher": it.get("publisher", ""),
            })
        print()
    Path(r"F:\zero trust\realdata\crossref_candidates.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote crossref_candidates.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
