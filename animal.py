#!/usr/bin/env python3
"""
animal.py

Download Binance Vision USD-M futures daily kline ZIP files for the animal/meme
basket, unzip them, combine each symbol into its own CSV, and save the result.

Important fix:
    Uses PAGINATED S3 listing. The older version could stop early at ~500 days
    because Binance Vision directories contain both .zip and .CHECKSUM files and
    one S3 listing page is capped at 1000 objects.

Default basket:
    DOGE, POPCAT, PENGU, PEPE, WIF, SHIB, BONK, UNI

Default interval:
    4h

Recommended:
    python animal.py --start 2019-09-01

Only POPCAT re-download:
    python animal.py --coins popcat --start 2019-09-01

Bypass S3 listing and try every daily URL directly:
    python animal.py --coins popcat --start 2019-09-01 --end 2026-04-25 --direct

Install:
    python -m pip install requests
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import time
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import requests
from xml.etree import ElementTree as ET

BASE_DATA_URL = "https://data.binance.vision"
DEFAULT_INTERVAL = "4h"
DEFAULT_START = date(2019, 9, 1)

DEFAULT_COINS = ["doge", "popcat", "pengu", "pepe", "wif", "shib", "bonk", "uni"]

FRIENDLY_TO_FUTURES_SYMBOL = {
    "doge": "DOGEUSDT",
    "popcat": "POPCATUSDT",
    "pengu": "PENGUUSDT",
    "pepe": "1000PEPEUSDT",
    "wif": "WIFUSDT",
    "shib": "1000SHIBUSDT",
    "bonk": "1000BONKUSDT",
    "uni": "UNIUSDT",
}

KLINE_COLUMNS_RAW = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_asset_volume",
    "number_of_trades",
    "taker_buy_base_asset_volume",
    "taker_buy_quote_asset_volume",
    "ignore",
]

OUTPUT_COLUMNS = [
    "symbol",
    "interval",
    "open_time",
    "open_time_iso",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "close_time_iso",
    "quote_asset_volume",
    "number_of_trades",
    "taker_buy_base_asset_volume",
    "taker_buy_quote_asset_volume",
    "ignore",
    "source_file",
]


@dataclass(frozen=True)
class ZipItem:
    symbol: str
    interval: str
    file_date: date
    url: str
    filename: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download Binance Vision USD-M futures animal basket klines.")
    parser.add_argument("--coins", default=",".join(DEFAULT_COINS), help="Friendly coins, comma-separated.")
    parser.add_argument("--symbols", default=None, help="Exact Binance futures symbols, comma-separated. Overrides --coins.")
    parser.add_argument("--interval", default=DEFAULT_INTERVAL, help="Kline interval. Default: 4h")
    parser.add_argument("--start", default=DEFAULT_START.isoformat(), help="Start date inclusive. Default: 2019-09-01")
    parser.add_argument("--end", default=None, help="End date inclusive. Default: yesterday UTC")
    parser.add_argument("--outdir", default="animal_4h_csv", help="Output directory")
    parser.add_argument("--sleep", type=float, default=0.03, help="Sleep seconds between successful downloads")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout seconds")
    parser.add_argument("--retries", type=int, default=4, help="HTTP retries")
    parser.add_argument("--direct", action="store_true", help="Bypass S3 listing and generate every daily URL.")
    parser.add_argument("--keep-empty", action="store_true", help="Write empty CSV if no rows found.")
    return parser.parse_args()


def parse_date_yyyy_mm_dd(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def yesterday_utc() -> date:
    return datetime.now(timezone.utc).date() - timedelta(days=1)


def date_range(start: date, end: date) -> Iterable[date]:
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def normalize_symbols(args: argparse.Namespace) -> list[str]:
    if args.symbols:
        symbols = [x.strip().upper() for x in args.symbols.split(",") if x.strip()]
        if not symbols:
            raise SystemExit("No valid --symbols provided.")
        return list(dict.fromkeys(symbols))

    symbols: list[str] = []
    unknown: list[str] = []
    for coin in [x.strip().lower() for x in args.coins.split(",") if x.strip()]:
        mapped = FRIENDLY_TO_FUTURES_SYMBOL.get(coin)
        if mapped:
            symbols.append(mapped)
        else:
            unknown.append(coin)

    if unknown:
        known = ", ".join(sorted(FRIENDLY_TO_FUTURES_SYMBOL))
        raise SystemExit(f"Unknown friendly coin(s): {unknown}. Known: {known}. Use --symbols for exact symbols.")

    return list(dict.fromkeys(symbols))


def iso_from_ms(value: str) -> str:
    try:
        ms = int(value)
    except ValueError:
        return ""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def zip_filename(symbol: str, interval: str, d: date) -> str:
    return f"{symbol}-{interval}-{d.isoformat()}.zip"


def direct_zip_url(symbol: str, interval: str, d: date) -> str:
    return f"{BASE_DATA_URL}/data/futures/um/daily/klines/{symbol}/{interval}/{zip_filename(symbol, interval, d)}"


def make_zip_item(symbol: str, interval: str, d: date) -> ZipItem:
    filename = zip_filename(symbol, interval, d)
    return ZipItem(symbol=symbol, interval=interval, file_date=d, url=direct_zip_url(symbol, interval, d), filename=filename)


def generated_zip_items(symbol: str, interval: str, start: date, end: date) -> list[ZipItem]:
    return [make_zip_item(symbol, interval, d) for d in date_range(start, end)]


def s3_list_v2_endpoints() -> list[str]:
    return [
        "https://data.binance.vision.s3.amazonaws.com/",
        "https://s3.amazonaws.com/data.binance.vision",
        "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision",
    ]


def strip_xml_namespace(root: ET.Element) -> None:
    for elem in root.iter():
        if "}" in elem.tag:
            elem.tag = elem.tag.split("}", 1)[1]


def text_of(parent: ET.Element, tag: str) -> str:
    found = parent.find(tag)
    return "" if found is None or found.text is None else found.text


def extract_date_from_filename(filename: str, symbol: str, interval: str) -> date | None:
    pattern = rf"^{re.escape(symbol)}-{re.escape(interval)}-(\d{{4}}-\d{{2}}-\d{{2}})\.zip$"
    match = re.match(pattern, filename)
    if not match:
        return None
    try:
        return parse_date_yyyy_mm_dd(match.group(1))
    except ValueError:
        return None


def discover_all_from_s3_listing(session: requests.Session, symbol: str, interval: str, timeout: int, max_pages: int = 200) -> list[ZipItem]:
    """
    Paginated S3 ListObjectsV2 discovery.

    This fixes the partial-listing bug. One page is capped at 1000 objects, and
    Binance Vision has both .zip and .CHECKSUM files, so non-paginated discovery
    can stop after around 500 days of ZIPs.
    """
    prefix = f"data/futures/um/daily/klines/{symbol}/{interval}/"

    for endpoint in s3_list_v2_endpoints():
        items: list[ZipItem] = []
        token: str | None = None
        got_valid_xml = False

        for _ in range(max_pages):
            params = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
            if token:
                params["continuation-token"] = token

            try:
                response = session.get(endpoint, params=params, timeout=timeout)
            except requests.RequestException:
                break

            if response.status_code != 200:
                break

            try:
                root = ET.fromstring(response.text)
                strip_xml_namespace(root)
            except ET.ParseError:
                break

            got_valid_xml = True

            for contents in root.findall(".//Contents"):
                key = text_of(contents, "Key")
                if not key:
                    continue

                filename = key.rsplit("/", 1)[-1]
                if not filename.endswith(".zip"):
                    continue

                d = extract_date_from_filename(filename, symbol, interval)
                if d is None:
                    continue

                items.append(
                    ZipItem(
                        symbol=symbol,
                        interval=interval,
                        file_date=d,
                        url=f"{BASE_DATA_URL}/{key}",
                        filename=filename,
                    )
                )

            is_truncated = text_of(root, "IsTruncated").lower() == "true"
            next_token = text_of(root, "NextContinuationToken")

            if not is_truncated:
                break
            if not next_token or next_token == token:
                break

            token = next_token

        if got_valid_xml and items:
            by_filename = {item.filename: item for item in items}
            return sorted(by_filename.values(), key=lambda x: x.file_date)

    return []


def filter_items_by_date(items: list[ZipItem], start: date, end: date) -> list[ZipItem]:
    return [item for item in items if start <= item.file_date <= end]


def get_zip_bytes(session: requests.Session, item: ZipItem, timeout: int, retries: int) -> tuple[bytes | None, str | None]:
    for attempt in range(retries + 1):
        try:
            response = session.get(item.url, timeout=timeout)

            if response.status_code == 404:
                return None, "missing"

            if response.status_code in (418, 429, 500, 502, 503, 504):
                retry_after = response.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    time.sleep(min(float(retry_after), 30.0))
                else:
                    time.sleep(min(2.0 + attempt, 10.0))
                continue

            response.raise_for_status()
            return response.content, None

        except requests.RequestException as exc:
            if attempt >= retries:
                return None, repr(exc)
            time.sleep(min(1.0 + attempt, 8.0))

    return None, "unknown_failure"


def row_looks_like_header(row: list[str]) -> bool:
    if not row:
        return True
    first = row[0].strip().lower()
    return first in {"open_time", "open time"} or not first.isdigit()


def clean_raw_row(row: list[str]) -> list[str] | None:
    if not row:
        return None
    row = [x.strip() for x in row]
    if row_looks_like_header(row):
        return None
    if len(row) < len(KLINE_COLUMNS_RAW):
        return None
    return row[: len(KLINE_COLUMNS_RAW)]


def iter_rows_from_zip(zip_bytes: bytes) -> Iterable[tuple[str, list[str]]]:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        csv_names = [name for name in zf.namelist() if name.lower().endswith(".csv")]
        for name in csv_names:
            with zf.open(name) as raw:
                text = io.TextIOWrapper(raw, encoding="utf-8", newline="")
                reader = csv.reader(text)
                for row in reader:
                    cleaned = clean_raw_row(row)
                    if cleaned is not None:
                        yield name, cleaned


def write_symbol_csv(
    session: requests.Session,
    symbol: str,
    interval: str,
    items: list[ZipItem],
    outdir: Path,
    timeout: int,
    retries: int,
    sleep_seconds: float,
    keep_empty: bool,
) -> tuple[int, list[dict[str, str]], list[dict[str, str]]]:
    outpath = outdir / f"{symbol}_{interval}.csv"
    tmp_path = outpath.with_suffix(".csv.tmp")

    manifest: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    seen_open_times: set[str] = set()
    row_count = 0

    with tmp_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()

        for item in items:
            zip_bytes, err = get_zip_bytes(session, item, timeout=timeout, retries=retries)

            if err == "missing":
                manifest.append({
                    "symbol": symbol,
                    "interval": interval,
                    "date": item.file_date.isoformat(),
                    "filename": item.filename,
                    "url": item.url,
                    "status": "missing_404",
                    "rows": "0",
                })
                continue

            if err is not None or zip_bytes is None:
                errors.append({
                    "symbol": symbol,
                    "interval": interval,
                    "date": item.file_date.isoformat(),
                    "filename": item.filename,
                    "url": item.url,
                    "error": err or "empty_response",
                })
                continue

            rows_this_file = 0
            try:
                for source_file, raw_row in iter_rows_from_zip(zip_bytes):
                    row_map = dict(zip(KLINE_COLUMNS_RAW, raw_row))
                    open_time = row_map["open_time"]

                    if open_time in seen_open_times:
                        continue
                    seen_open_times.add(open_time)

                    writer.writerow({
                        "symbol": symbol,
                        "interval": interval,
                        "open_time": row_map["open_time"],
                        "open_time_iso": iso_from_ms(row_map["open_time"]),
                        "open": row_map["open"],
                        "high": row_map["high"],
                        "low": row_map["low"],
                        "close": row_map["close"],
                        "volume": row_map["volume"],
                        "close_time": row_map["close_time"],
                        "close_time_iso": iso_from_ms(row_map["close_time"]),
                        "quote_asset_volume": row_map["quote_asset_volume"],
                        "number_of_trades": row_map["number_of_trades"],
                        "taker_buy_base_asset_volume": row_map["taker_buy_base_asset_volume"],
                        "taker_buy_quote_asset_volume": row_map["taker_buy_quote_asset_volume"],
                        "ignore": row_map["ignore"],
                        "source_file": source_file,
                    })
                    rows_this_file += 1
                    row_count += 1

            except zipfile.BadZipFile:
                errors.append({
                    "symbol": symbol,
                    "interval": interval,
                    "date": item.file_date.isoformat(),
                    "filename": item.filename,
                    "url": item.url,
                    "error": "bad_zip_file",
                })
                continue

            manifest.append({
                "symbol": symbol,
                "interval": interval,
                "date": item.file_date.isoformat(),
                "filename": item.filename,
                "url": item.url,
                "status": "downloaded",
                "rows": str(rows_this_file),
            })

            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

    if row_count > 0 or keep_empty:
        tmp_path.replace(outpath)
    else:
        tmp_path.unlink(missing_ok=True)

    return row_count, manifest, errors


def write_dict_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    args = parse_args()

    symbols = normalize_symbols(args)
    interval = args.interval
    start = parse_date_yyyy_mm_dd(args.start)
    end = parse_date_yyyy_mm_dd(args.end) if args.end else yesterday_utc()

    if end < start:
        raise SystemExit(f"End date {end} is before start date {start}.")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": "animal-binance-vision-downloader/2.1"})

    print("Animal basket Binance Vision downloader")
    print(f"Symbols:  {', '.join(symbols)}")
    print(f"Interval: {interval}")
    print(f"Dates:    {start} to {end} inclusive")
    print(f"Mode:     {'direct daily URLs' if args.direct else 'paginated S3 listing'}")
    print(f"Outdir:   {outdir.resolve()}")
    print()

    all_manifest: list[dict[str, str]] = []
    all_errors: list[dict[str, str]] = []

    for symbol in symbols:
        print(f"[{symbol}] discovering files...")

        if args.direct:
            items = generated_zip_items(symbol, interval, start, end)
            print(f"[{symbol}] generated {len(items)} daily URLs")
        else:
            all_items = discover_all_from_s3_listing(session, symbol, interval, timeout=args.timeout)
            if not all_items:
                print(f"[{symbol}] S3 listing failed or empty; falling back to generated daily URLs")
                items = generated_zip_items(symbol, interval, start, end)
            else:
                available_start = all_items[0].file_date
                available_end = all_items[-1].file_date
                items = filter_items_by_date(all_items, start, end)
                print(f"[{symbol}] available {available_start} -> {available_end}; selected {len(items)} files")

        if not items:
            print(f"[{symbol}] no files selected")
            continue

        row_count, manifest, errors = write_symbol_csv(
            session=session,
            symbol=symbol,
            interval=interval,
            items=items,
            outdir=outdir,
            timeout=args.timeout,
            retries=args.retries,
            sleep_seconds=args.sleep,
            keep_empty=args.keep_empty,
        )

        all_manifest.extend(manifest)
        all_errors.extend(errors)

        output_file = outdir / f"{symbol}_{interval}.csv"
        if row_count > 0:
            print(f"[{symbol}] wrote {row_count:,} rows -> {output_file}")
        else:
            print(f"[{symbol}] no rows written")
        print()

    write_dict_rows(outdir / "download_manifest.csv", all_manifest, ["symbol", "interval", "date", "filename", "url", "status", "rows"])
    write_dict_rows(outdir / "errors.csv", all_errors, ["symbol", "interval", "date", "filename", "url", "error"])

    downloaded = sum(1 for row in all_manifest if row.get("status") == "downloaded")
    missing = sum(1 for row in all_manifest if row.get("status") == "missing_404")

    print("Done.")
    print(f"Downloaded files: {downloaded}")
    print(f"Missing files:    {missing}")
    print(f"Errors:           {len(all_errors)}")
    print(f"Manifest:         {outdir / 'download_manifest.csv'}")
    print(f"Errors CSV:       {outdir / 'errors.csv'}")

    if all_errors:
        print("\nSome files had errors. Inspect errors.csv.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
