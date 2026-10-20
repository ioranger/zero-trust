"""Verify every citation's metadata against Crossref before it enters the paper.

A wrong DOI or a wrong page range in a manuscript is a real defect, and the
authoritative record is the Crossref metadata, so every entry is checked
against it rather than copied from a search snippet.
"""

import json
import sys
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DOIS = [
    "10.1109/TPDS.2014.2317719",      # Chae, DiPippo, Sun 2014
    "10.1155/2015/859731",            # Mendoza & Kleinschmidt 2015
    "10.1155/2018/6063456",           # Caminha, Perkusich, Perkusich 2018
    "10.1145/3392058",                # Salimitari et al. 2020
    "10.11591/eei.v12i6.6110",        # Kannan et al. 2023
    "10.1007/s42979-026-05087-1",      # Ziauddin et al. 2026
    # Position-aware trust and integrity monitoring in UAV swarms.
    "10.1109/lra.2025.3534068",       # Vijay et al. 2025, anchor-free integrity monitoring
    "10.1016/j.ress.2025.112101",     # Zhong et al. 2026, distributed GPS-spoofing detection
    "10.1109/jiot.2022.3195320",      # Dang et al. 2022, deep ensemble GPS-spoofing detection
    "10.1109/tvt.2025.3555490",       # Fang, Han, Schotten 2025, cooperative-localization security
    "10.3390/electronics15153326",    # Zhao, Fu, Li 2026, GNSS spoofing detection review
    "10.7717/peerj-cs.3875",          # Tariq & Ahamed Ahanger 2026, BeiDou spoofing in swarms
    "10.1109/infocomwkshps50562.2020.9162761",  # Keshavarz et al. 2020, UAV trust monitoring
]

print(f"{'DOI':<34}{'type':<9}{'year':<6}{'container':<44}title")
print("-" * 150)
out = {}
for doi in DOIS:
    url = f"https://api.crossref.org/works/{doi}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "paper-check/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            m = json.load(r)["message"]
    except Exception as e:
        print(f"{doi:<34}LOOKUP FAILED: {e}")
        continue
    authors = "; ".join(
        f"{a.get('family', '')}, {a.get('given', '')}".strip(", ")
        for a in m.get("author", []))
    year = str((m.get("issued", {}).get("date-parts") or [[None]])[0][0])
    cont = (m.get("container-title") or [""])[0]
    title = (m.get("title") or [""])[0]
    vol = m.get("volume", "")
    page = m.get("page", "")
    out[doi] = {
        "authors": authors, "year": year, "container": cont, "title": title,
        "volume": vol, "page": page, "type": m.get("type", ""),
        "publisher": m.get("publisher", ""),
    }
    print(f"{doi:<34}{m.get('type',''):<9}{year:<6}{cont[:42]:<44}{title[:70]}")
    print(f"{'':<34}authors: {authors}")
    print(f"{'':<34}volume {vol}, pages {page}, publisher {m.get('publisher','')}")
    print()

Path(r"F:\zero trust\realdata\crossref_verified.json").write_text(
    json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"wrote crossref_verified.json ({len(out)} entries)")
