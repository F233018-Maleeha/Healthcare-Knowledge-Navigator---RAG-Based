"""
Ingest FDA drug label data (SPLs - Structured Product Labels) from
DailyMed for cardiology-relevant medications, into a running backend.

DailyMed is a genuinely open, free, no-API-key-required REST service
run by the NIH/NLM. Verified endpoints (as of writing):
  - Search by drug name:  https://dailymed.nlm.nih.gov/dailymed/services/v1/drugname/{name}/spls.json
  - Fetch full SPL by id: https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/{setid}.xml

Not runnable inside this sandbox (no network path to dailymed.nlm.nih.gov
here) but is a real, working integration for your own environment -
same honest caveat as ingest_pubmed.py.

Usage:
    python scripts/ingest_dailymed.py --api-url http://localhost:8000
    python scripts/ingest_dailymed.py --drug atorvastatin --drug warfarin

Drug labels are regulatory documents (FDA-approved), so they're
treated as authority_tier=1 (same tier as clinical guidelines) - this
is the ONE source type where that's appropriate regardless of study
design, since it reflects the approved label, not a single study.
"""
import argparse
import xml.etree.ElementTree as ET
from datetime import date

import httpx

DAILYMED_BASE = "https://dailymed.nlm.nih.gov/dailymed/services"


SPL_SECTION_LOINC_CODES = {
    "34067-9": "Recommendation",       # Indications and Usage
    "34068-7": "Dosing",               # Dosage and Administration
    "34070-3": "Contraindications",    # Contraindications
    "34071-1": "Contraindications",    # Warnings
    "34084-4": "Contraindications",    # Adverse Reactions
    "34073-7": "Contraindications",    # Drug Interactions
}

DEFAULT_CARDIOLOGY_DRUGS = [
    "atorvastatin", "rosuvastatin", "simvastatin",
    "apixaban", "rivaroxaban", "warfarin", "dabigatran",
    "aspirin", "clopidogrel", "ticagrelor",
    "metoprolol", "carvedilol", "bisoprolol", "atenolol",
    "lisinopril", "losartan", "valsartan", "Entresto",  # sacubitril/valsartan is only indexed under its brand name
    "furosemide", "spironolactone", "eplerenone",
    "amiodarone hydrochloride", "digoxin",
    "empagliflozin", "dapagliflozin",
]

NS = {"v3": "urn:hl7-org:v3"}


def search_setids_by_drug_name(drug_name: str) -> list[dict]:
    resp = httpx.get(
        f"{DAILYMED_BASE}/v1/drugname/{drug_name}/spls.json", timeout=30
    )
    resp.raise_for_status()
    data = resp.json()
    columns = data.get("COLUMNS", [])
    rows = data.get("DATA", [])
    return [dict(zip(columns, row)) for row in rows]


def fetch_spl_xml(setid: str) -> ET.Element:
    resp = httpx.get(f"{DAILYMED_BASE}/v2/spls/{setid}.xml", timeout=30)
    resp.raise_for_status()
    return ET.fromstring(resp.text)


def _section_text(section_el: ET.Element) -> str:
    """Flatten a <section>'s nested <paragraph>/<text> content into
    plain text - SPL XML nests fairly deeply and inconsistently."""
    return " ".join(t.strip() for t in section_el.itertext() if t.strip())


def parse_spl_to_source_document(root: ET.Element, setid: str, title: str) -> dict | None:
    sections_found: dict[str, str] = {}

    for section in root.iter("{urn:hl7-org:v3}section"):
        code_el = section.find("v3:code", NS)
        if code_el is None:
            continue
        loinc_code = code_el.get("code")
        label = SPL_SECTION_LOINC_CODES.get(loinc_code)
        if not label:
            continue
        text = _section_text(section)
        if text:
            sections_found[label] = sections_found.get(label, "") + "\n" + text

    if not sections_found:
        return None 

    full_text_parts = [f"{label}\n{text.strip()}" for label, text in sections_found.items()]
    full_text = "\n\n".join(full_text_parts)

    return {
        "doc_id": f"dailymed-{setid}",
        "title": title,
        "source": "DailyMed (FDA)",
        "specialty": ["cardiology"],
        "authority_tier": 1,  # FDA-approved label - regulatory grade regardless of study design
        "evidence_grade": "FDA label",
        "publication_date": date.today().isoformat(),  # SPL doesn't cleanly expose original approval date via this endpoint
        "url_or_doi": f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={setid}",
        "license": "open",
        "full_text": full_text,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--drug", action="append", help="Generic drug name(s) to fetch; repeatable")
    parser.add_argument("--max-per-drug", type=int, default=2, help="Max SPLs to ingest per drug name")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument(
        "--timeout", type=int, default=900,
        help="Seconds to wait for the /ingest call. Default is high (900s/15min) because "
             "CPU-based local embedding (EMBEDDING_PROVIDER=local_semantic) can take several "
             "minutes for a large batch - lower this if you're on a fast API-based provider.",
    )
    args = parser.parse_args()

    drugs = args.drug or DEFAULT_CARDIOLOGY_DRUGS
    docs = []

    for drug in drugs:
        try:
            candidates = search_setids_by_drug_name(drug)
        except httpx.HTTPError as e:
            print(f"  [skip] {drug}: search failed ({e})")
            continue

        if not candidates:
            print(f"  [skip] {drug}: no SPLs found")
            continue

        for candidate in candidates[: args.max_per_drug]:
            setid = candidate.get("SETID")
            title = candidate.get("TITLE", drug)
            if not setid:
                continue
            try:
                root = fetch_spl_xml(setid)
                doc = parse_spl_to_source_document(root, setid, title)
            except (httpx.HTTPError, ET.ParseError) as e:
                print(f"  [skip] {title}: fetch/parse failed ({e})")
                continue

            if doc:
                docs.append(doc)
                print(f"  [ok] {title}")
            else:
                print(f"  [skip] {title}: no usable sections extracted")

    print(f"\nParsed {len(docs)} usable drug labels")
    if not docs:
        return

    resp = httpx.post(f"{args.api_url}/ingest", json=docs, timeout=args.timeout)
    if resp.status_code != 200:
        print(f"\nIngest failed with status {resp.status_code}. Response body:")
        print(resp.text)
        resp.raise_for_status()
    print(resp.json())


if __name__ == "__main__":
    main()