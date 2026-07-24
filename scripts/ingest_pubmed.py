"""
Ingest PubMed abstracts via NCBI E-utilities into a running backend.

This hits the free, public E-utilities API (esearch -> efetch), extracts
title/abstract/publication date, and posts SourceDocument-shaped JSON to
the /ingest endpoint. Not runnable inside this sandbox (no network path
to eutils.ncbi.nlm.nih.gov here) but is a real, working integration for
your own environment.

Usage:
    python scripts/ingest_pubmed.py --query "atrial fibrillation anticoagulation guideline" \
        --max-results 50 --specialty cardiology --api-url http://localhost:8000

NCBI usage notes:
- Free, no API key required for low-volume use; register for an NCBI
  API key (env var NCBI_API_KEY) to raise rate limits from 3 to 10 req/s.
- Respect NCBI's usage policy: identify your tool via `tool=` and
  `email=` params (edit DEFAULT_TOOL/DEFAULT_EMAIL below).
- Only abstracts are fetched here (open metadata). Full text requires
  the separate PMC Open Access subset - see ingest_pmc_oa.py (not
  included yet; same pattern, different endpoint).
"""
import argparse
import os
import xml.etree.ElementTree as ET
from datetime import date

import httpx

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
DEFAULT_TOOL = "healthcare-knowledge-navigator"
DEFAULT_EMAIL = "replace-with-your-contact-email@example.com"


def esearch(query: str, max_results: int, api_key: str | None) -> list[str]:
    params = {
        "db": "pubmed", "term": query, "retmax": max_results, "retmode": "json",
        "tool": DEFAULT_TOOL, "email": DEFAULT_EMAIL,
    }
    if api_key:
        params["api_key"] = api_key
    resp = httpx.get(f"{EUTILS_BASE}/esearch.fcgi", params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()["esearchresult"]["idlist"]


def efetch(pmids: list[str], api_key: str | None) -> ET.Element:
    params = {
        "db": "pubmed", "id": ",".join(pmids), "retmode": "xml",
        "tool": DEFAULT_TOOL, "email": DEFAULT_EMAIL,
    }
    if api_key:
        params["api_key"] = api_key
    resp = httpx.get(f"{EUTILS_BASE}/efetch.fcgi", params=params, timeout=60)
    resp.raise_for_status()
    return ET.fromstring(resp.text)


def parse_articles(root: ET.Element, specialty: list[str]) -> list[dict]:
    docs = []
    for article in root.findall(".//PubmedArticle"):
        pmid = article.findtext(".//PMID")
        title = article.findtext(".//ArticleTitle") or "Untitled"
        abstract_parts = [el.text or "" for el in article.findall(".//AbstractText")]
        abstract = "\n".join(abstract_parts).strip()
        if not abstract:
            continue  # skip records with no usable text

        year = article.findtext(".//PubDate/Year") or article.findtext(".//PubDate/MedlineDate", "")[:4]
        try:
            pub_date = date(int(year), 1, 1).isoformat()
        except (ValueError, TypeError):
            pub_date = date.today().isoformat()

        docs.append({
            "doc_id": f"pubmed-{pmid}",
            "title": title,
            "source": "PubMed",
            "specialty": specialty,
            "authority_tier": 3,  # default to "primary study"; re-classify systematic
                                   # reviews/meta-analyses to tier 1/2 via PublicationType if needed
            "evidence_grade": None,
            "publication_date": pub_date,
            "url_or_doi": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "license": "open",
            "full_text": f"{title}\n\nAbstract\n{abstract}",
        })
    return docs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--max-results", type=int, default=50)
    parser.add_argument("--specialty", action="append", default=[])
    parser.add_argument("--api-url", default="http://localhost:8000")
    args = parser.parse_args()

    api_key = os.environ.get("NCBI_API_KEY")

    pmids = esearch(args.query, args.max_results, api_key)
    print(f"Found {len(pmids)} PubMed IDs for query: {args.query!r}")
    if not pmids:
        return

    root = efetch(pmids, api_key)
    docs = parse_articles(root, args.specialty or ["general"])
    print(f"Parsed {len(docs)} articles with usable abstracts")

    resp = httpx.post(f"{args.api_url}/ingest", json=docs, timeout=120)
    resp.raise_for_status()
    print(resp.json())


if __name__ == "__main__":
    main()
