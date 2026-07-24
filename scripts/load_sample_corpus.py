"""
Loads data/sample_corpus/cardiology_demo_corpus.json into a running
backend via the /ingest endpoint.

Usage:
    python scripts/load_sample_corpus.py [--url http://localhost:8000]
"""
import argparse
import json
from pathlib import Path

import httpx

DEFAULT_CORPUS = Path(__file__).parent.parent / "data" / "sample_corpus" / "cardiology_demo_corpus.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    args = parser.parse_args()

    docs = json.loads(Path(args.corpus).read_text())
    resp = httpx.post(f"{args.url}/ingest", json=docs, timeout=60)
    resp.raise_for_status()
    print(resp.json())


if __name__ == "__main__":
    main()
