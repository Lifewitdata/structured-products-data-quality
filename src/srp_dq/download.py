"""Download official SIX structured-products snapshots with acquisition provenance."""
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from srp_dq.load import parse_text

BASE_URL = "https://www.six-structured-products.com"
INDEX_URL = f"{BASE_URL}/en/latest-news/closing-prices"
FILE_RE = re.compile(r"derivatives_(\d{4}-\d{2}-\d{2})\.csv$")
RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"


def list_files(session: requests.Session) -> dict[str, str]:
    response = session.get(INDEX_URL, timeout=60)
    response.raise_for_status()
    links = {}
    for a in BeautifulSoup(response.text, "html.parser").find_all("a", href=True):
        m = FILE_RE.search(a["href"])
        url = urljoin(BASE_URL, a["href"])
        if m and urlparse(url).netloc == urlparse(BASE_URL).netloc:
            links[m.group(1)] = url
    if not links:
        raise ValueError("SIX page contains no recognised daily CSV links")
    return dict(sorted(links.items()))


def validate_payload(payload: bytes, name: str) -> None:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        text = payload.decode("latin-1")
    result = parse_text(text, name)
    if (result.data.empty or not result.header_lines or result.bad_lines
            or result.unparseable_values or result.produced_at is None
            or result.produced_at.date() != result.snapshot_date):
        raise ValueError(f"Rejected invalid CSV payload: {name}")


def download_all(raw_dir: Path = RAW_DIR) -> list[Path]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = raw_dir / "acquisition_manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    saved = []
    with requests.Session() as session:
        session.headers["User-Agent"] = "srp-dq-portfolio/0.1"
        for day, url in list_files(session).items():
            target = raw_dir / f"derivatives_{day}.csv"
            acquired_at = None
            if target.exists():
                payload = target.read_bytes()
                digest = hashlib.sha256(payload).hexdigest()
                old = manifest.get(target.name, {})
                if old.get("sha256") and old["sha256"] != digest:
                    raise ValueError(f"Cached file checksum mismatch: {target.name}")
                validate_payload(payload, target.name)
                acquired_at = old.get("acquired_at_utc")
            else:
                response = session.get(url, timeout=120)
                response.raise_for_status()
                payload = response.content
                validate_payload(payload, target.name)
                pending = target.with_suffix(".csv.part")
                try:
                    pending.write_bytes(payload)
                    pending.replace(target)
                finally:
                    pending.unlink(missing_ok=True)
                acquired_at = datetime.now(timezone.utc).isoformat()
                time.sleep(1)
            manifest[target.name] = {
                "url": url, "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload), "acquired_at_utc": acquired_at,
                "validated_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            saved.append(target)
    pending_manifest = manifest_path.with_suffix(".json.part")
    pending_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    pending_manifest.replace(manifest_path)
    return saved


if __name__ == "__main__":
    files = download_all()
    print(f"{len(files)} validated files in {RAW_DIR}")
