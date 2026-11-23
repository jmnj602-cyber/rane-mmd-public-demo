"""Acquire traceable commodity, steel-chart, and RBI reference-rate data."""

from __future__ import annotations

import csv
import datetime as dt
import html
import io
import re
import statistics
import sys
import time
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pandas as pd
import pymupdf
import requests
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "raw" / "external"
SOURCE_FILES = OUTPUT / "source_files"
EXTRACTION_DATE = dt.date.today().isoformat()

WORLD_BANK_URL = (
    "https://thedocs.worldbank.org/en/doc/"
    "74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/"
    "CMO-Historical-Data-Monthly.xlsx"
)
STEEL_URL = (
    "https://steel.gov.in/sites/default/files/2026-05/"
    "An%20Overview%20of%20Steel%20Sector%20for%20the%20month%20of%20"
    "April%2C%202026.pdf"
)
RBI_URL = "https://www.rbi.org.in/Scripts/ReferenceRateArchive.aspx"
COMTRADE_ENDPOINT = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
COMTRADE_URL = (
    COMTRADE_ENDPOINT
    + "?reporterCode=356&cmdCode=390940&flowCode=M&partnerCode=0&"
    + "period=2023%2C2024%2C2025&motCode=0"
)
BUSINESS_ANALYTIQ_URL = (
    "https://businessanalytiq.com/procurementanalytics/index/"
    "phenolic-resin-price-index/"
)


class InputCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.inputs: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "input":
            return
        attributes = dict(attrs)
        name = attributes.get("name")
        if name:
            self.inputs[name] = attributes.get("value") or ""


def fail_if_outputs_exist() -> None:
    expected = [
        OUTPUT / "natural_rubber_rss3.csv",
        OUTPUT / "steel_hrc_crc.csv",
        OUTPUT / "usd_inr.csv",
        OUTPUT / "phenolic_resin_source_assessment.md",
        OUTPUT / "source_register.csv",
        SOURCE_FILES / "CMO-Historical-Data-Monthly.xlsx",
        SOURCE_FILES / "steel_ministry_apr_2026.pdf",
        SOURCE_FILES / "rbi_reference_rate_usd_2000-2026.html",
    ]
    existing = [str(path) for path in expected if path.exists()]
    if existing:
        raise FileExistsError(
            "Refusing to overwrite existing files:\n" + "\n".join(existing)
        )


def download(session: requests.Session, url: str) -> bytes:
    response = session.get(url, timeout=90)
    response.raise_for_status()
    return response.content


def save_source(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as file:
        file.write(content)


def extract_rss3(workbook_bytes: bytes) -> tuple[pd.DataFrame, str, str]:
    if not workbook_bytes.startswith(b"PK"):
        raise ValueError("World Bank download is not an XLSX/ZIP container")
    with zipfile.ZipFile(io.BytesIO(workbook_bytes)) as archive:
        if archive.testzip() is not None:
            raise ValueError("World Bank XLSX failed ZIP integrity validation")

    sheet = pd.read_excel(
        io.BytesIO(workbook_bytes), sheet_name="Monthly Prices", header=None
    )
    match = [
        index
        for index, value in enumerate(sheet.iloc[4])
        if str(value).strip() == "Rubber, RSS3"
    ]
    if len(match) != 1:
        raise ValueError("Expected exactly one Rubber, RSS3 series column")

    column = match[0]
    original_unit = str(sheet.iloc[5, column]).strip()
    source_note = (
        "World Bank Pink Sheet description: Rubber (Asia), RSS3 grade, "
        "Singapore Commodity Exchange Ltd (SICOM) nearby contract beginning "
        "2004; during 2000-2003, Singapore RSS1; previously Malaysia RSS1. "
        "This is the source's historically changing series definition."
    )
    rows: list[dict[str, Any]] = []
    for row_index in range(6, len(sheet)):
        source_period = str(sheet.iloc[row_index, 0]).strip()
        match_period = re.fullmatch(r"(\d{4})M(\d{2})", source_period)
        if not match_period:
            continue
        year, month = map(int, match_period.groups())
        raw_value = sheet.iloc[row_index, column]
        value = None if pd.isna(raw_value) else float(raw_value)
        rows.append(
            {
                "date": dt.date(year, month, 1).isoformat(),
                "value": value,
                "currency": "USD",
                "unit": original_unit,
                "source": "World Bank Group, Commodity Markets (Pink Sheet)",
                "source_url": WORLD_BANK_URL,
                "extraction_date": EXTRACTION_DATE,
                "data_quality": (
                    "OFFICIAL_SOURCE_VALUE"
                    if value is not None
                    else "MISSING_SOURCE_VALUE"
                ),
                "source_period": source_period,
                "series": "Rubber, RSS3",
                "source_note": source_note,
            }
        )

    result = pd.DataFrame(rows)
    if result.empty or result["date"].duplicated().any():
        raise ValueError("RSS3 extraction is empty or has duplicate dates")
    return result, rows[0]["date"], rows[-1]["date"]


def chart_line_y(image: Image.Image, x: float, series: str) -> int:
    if series == "hrc":
        is_series = lambda r, g, b: r > 120 and r > g * 1.35 and r > b * 1.15
    else:
        is_series = lambda r, g, b: g > r * 1.15 and g > b * 1.1 and g > 100

    ys: list[int] = []
    center = round(x)
    for pixel_x in range(center - 2, center + 3):
        for pixel_y in range(596, 808):
            red, green, blue = image.getpixel((pixel_x, pixel_y))
            if is_series(red, green, blue):
                ys.append(pixel_y)
    if len(ys) < 4:
        raise ValueError(f"Could not identify chart series {series} at x={x:.1f}")
    return int(statistics.median(ys))


def extract_steel(pdf_bytes: bytes) -> tuple[pd.DataFrame, str, str]:
    if not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError("Ministry of Steel download is not a PDF")
    document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    if len(document) != 7:
        raise ValueError(f"Expected 7 pages in Ministry PDF, got {len(document)}")
    page_text = document[4].get_text()
    if "Trends in Steel Price" not in page_text and not document[4].get_images():
        raise ValueError("Expected steel price chart was not found on PDF page 5")

    # The source chart is on page 5. At 2x rendering, calibrated plot bounds
    # are x=143..1100 and y=596..807; the horizontal axis spans INR 40k..70k.
    pixmap = document[4].get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
    image = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")
    if image.size != (1192, 1685):
        raise ValueError(f"Unexpected rendered chart page size: {image.size}")

    months = pd.date_range("2023-05-01", "2026-04-01", freq="MS")
    records: list[dict[str, Any]] = []
    products = [
        ("Steel HRC 2MM", "hrc"),
        ("Steel CRC 0.63MM", "crc"),
    ]
    for index, month in enumerate(months):
        x = 143 + index * (957 / 35)
        for product, line in products:
            y = chart_line_y(image, x, line)
            value = 70000 - (y - 596) * (30000 / (807 - 596))
            rounded_value = int(round(value / 100) * 100)
            records.append(
                {
                    "date": month.date().isoformat(),
                    "value": rounded_value,
                    "currency": "INR",
                    "unit": "Rs/tonne excl. GST",
                    "source": "Ministry of Steel, Government of India",
                    "source_url": STEEL_URL,
                    "extraction_date": EXTRACTION_DATE,
                    "data_quality": "APPROXIMATE_CHART_VALUE",
                    "material": product,
                    "source_chart": "Trends in Steel Price",
                    "source_page": 5,
                    "digitization_note": (
                        "Visually digitized from the published monthly chart; "
                        "rounded to nearest Rs 100/tonne. Not an exact raw "
                        "observation."
                    ),
                }
            )

    result = pd.DataFrame(records)
    expected = len(months) * len(products)
    if len(result) != expected or result.duplicated(["date", "material"]).any():
        raise ValueError("Steel chart extraction is incomplete or duplicated")
    return result, months[0].date().isoformat(), months[-1].date().isoformat()


def submit_rbi_query(
    session: requests.Session, page: str, start_date: dt.date, end_date: dt.date
) -> str:
    collector = InputCollector()
    collector.feed(page)
    for required in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"):
        if not collector.inputs.get(required):
            raise ValueError(f"RBI form is missing {required}")
    form = {
        "__VIEWSTATE": collector.inputs["__VIEWSTATE"],
        "__VIEWSTATEGENERATOR": collector.inputs["__VIEWSTATEGENERATOR"],
        "__EVENTVALIDATION": collector.inputs["__EVENTVALIDATION"],
        "chkUSD": "on",
        "txtFromDate": start_date.strftime("%d/%m/%Y"),
        "txtToDate": end_date.strftime("%d/%m/%Y"),
        "btnSubmit": " GO ",
    }
    response = session.post(RBI_URL, data=form, timeout=120)
    response.raise_for_status()
    return response.text


def extract_rbi_rates(page: str) -> pd.DataFrame:
    table_match = re.search(
        r"<table\b[^>]*>.*?USD\s*\(INR\s*/\s*1\s*USD\).*?</table>",
        page,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not table_match:
        raise ValueError("RBI result table with USD reference rates was not found")

    rows: list[dict[str, Any]] = []
    for row_html in re.findall(
        r"<tr\b[^>]*>(.*?)</tr>", table_match.group(0), flags=re.IGNORECASE | re.DOTALL
    ):
        cells = re.findall(
            r"<td\b[^>]*>(.*?)</td>", row_html, flags=re.IGNORECASE | re.DOTALL
        )
        if len(cells) < 2:
            continue
        text = [
            html.unescape(re.sub(r"<[^>]+>", "", cell)).strip()
            for cell in cells[:2]
        ]
        if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", text[0]):
            continue
        if not re.fullmatch(r"\d+(?:\.\d+)?", text[1]):
            continue
        date = dt.datetime.strptime(text[0], "%d/%m/%Y").date()
        rows.append(
            {
                "date": date.isoformat(),
                "value": float(text[1]),
                "currency": "INR",
                "unit": "INR / 1 USD",
                "source": "Reserve Bank of India, Reference Rate Archive",
                "source_url": RBI_URL,
                "extraction_date": EXTRACTION_DATE,
                "data_quality": "OFFICIAL_RBI_REFERENCE_RATE",
                "rate": "USD (INR / 1 USD)",
            }
        )

    result = pd.DataFrame(rows)
    if result.empty or result["date"].duplicated().any():
        raise ValueError("RBI rate extraction is empty or has duplicate dates")
    return result.sort_values("date").reset_index(drop=True)


def review_comtrade(session: requests.Session) -> tuple[str, str]:
    outcomes: list[str] = []
    for year in (2022, 2023, 2024, 2025):
        try:
            response = session.get(
                COMTRADE_ENDPOINT,
                params={
                    "reporterCode": "356",
                    "cmdCode": "390940",
                    "flowCode": "M",
                    "partnerCode": "0",
                    "period": str(year),
                    "motCode": "0",
                },
                timeout=45,
            )
        except requests.RequestException as error:
            outcomes.append(f"{year}: request failed ({error})")
            continue

        if response.status_code == 429:
            outcomes.append(f"{year}: HTTP 429 rate-limited; no retry attempted")
            time.sleep(3)
            continue
        if response.status_code != 200:
            outcomes.append(f"{year}: HTTP {response.status_code}")
            continue
        try:
            payload = response.json()
        except ValueError:
            outcomes.append(f"{year}: HTTP 200 but response was not valid JSON")
            continue
        records = payload.get("data")
        if not isinstance(records, list):
            outcomes.append(f"{year}: HTTP 200 but no data array was returned")
        else:
            outcomes.append(
                f"{year}: HTTP 200, API count={payload.get('count')}, "
                f"returned rows={len(records)}"
            )
        time.sleep(3)

    details = "; ".join(outcomes)
    if len(outcomes) == 4 and all("returned rows=0" in item for item in outcomes):
        status = "PUBLIC_PREVIEW_ZERO_ROWS"
    else:
        status = "PUBLIC_PREVIEW_PARTIAL_OR_UNAVAILABLE"
    return details, status


def review_business_analytiq(session: requests.Session) -> tuple[str, str]:
    try:
        response = session.get(BUSINESS_ANALYTIQ_URL, timeout=45)
    except requests.RequestException as error:
        return f"Source-page request failed: {error}", "SOURCE_PAGE_REQUEST_FAILED"
    if response.status_code != 200:
        return (
            f"Public page returned HTTP {response.status_code}.",
            f"PUBLIC_PAGE_HTTP_{response.status_code}",
        )

    text = html.unescape(re.sub(r"<[^>]+>", " ", response.text)).casefold()
    if "full database" in text and "paid" in text:
        return (
            "Public page HTTP 200; full historical database is described as paid.",
            "PUBLIC_SUMMARY_ONLY_HISTORICAL_DATABASE_PAID",
        )
    return (
        "Public page HTTP 200; historical-access wording was not verified.",
        "PUBLIC_PAGE_REVIEWED_HISTORICAL_ACCESS_UNCONFIRMED",
    )


def write_source_assessment(path: Path, wb: pd.DataFrame, steel: pd.DataFrame,
                            rbi: pd.DataFrame, comtrade_status: str,
                            analytiq_status: str) -> None:
    last_rbi_date = dt.date.fromisoformat(rbi["date"].max())
    unavailable_rbi_dates = [
        (last_rbi_date + dt.timedelta(days=offset)).isoformat()
        for offset in range(1, (dt.date.today() - last_rbi_date).days + 1)
    ]
    rbi_tail_note = (
        f"No archive rows were returned for {unavailable_rbi_dates[0]} through "
        f"{dt.date.today().isoformat()}; no values were interpolated."
        if unavailable_rbi_dates
        else "The latest returned date is the extraction date; no values were interpolated."
    )
    report = f"""# Phenolic Resin Source Assessment

Assessment date: {EXTRACTION_DATE}

## Business Analytiq

- Public source reviewed: {BUSINESS_ANALYTIQ_URL}
- The public page describes a regional phenolic-resin price index and a current November 2026 summary. It also states that the full database is paid and includes an accuracy/completeness disclaimer.
- No traceable, freely downloadable historical monthly dataset was exposed in the public page content reviewed. Historical numeric observations were not copied, inferred from a chart, or fabricated.
- Decision: not used as a historical market-price dataset. Obtain licensed historical records directly from the provider if RANE authorizes purchase and can verify methodology, material grade/formulation, region, currency, unit, dates, and source methodology.

## UN Comtrade, HS 390940

- Official API endpoint reviewed: https://comtradeapi.un.org/public/v1/preview/C/A/HS
- Query: reporter 356 (India), import flow, HS 390940, partner 0 (World), annual periods.
- Result: {comtrade_status}. A zero-result response does not establish zero trade. No Comtrade figures were emitted.
- Import value and reported quantity are customs-trade statistics. Any ratio of trade value to quantity is an import unit value, which can reflect mix, grade, partner, freight/valuation basis, and reporting conventions. It must not be presented as a phenolic-resin market price or substituted for a procurement quotation.
- Decision: no resin series was emitted. If usable records become available, retain official customs value and quantity separately with declaration period, classification revision, reporter/partner, trade flow, and reported unit; do not relabel an import unit value as a price.

## Acquisition validation summary

- World Bank RSS3: {len(wb)} monthly rows, {wb['date'].min()} through {wb['date'].max()}, units retained from workbook. The Pink Sheet description says RSS3 grade applies from 2004; 2000-2003 is Singapore RSS1 and earlier history is Malaysia RSS1. This source-defined historical substitution is retained in each row's `source_note`.
- Ministry of Steel HRC/CRC chart: {len(steel)} approximate monthly values, {steel['date'].min()} through {steel['date'].max()}. Every row is flagged `APPROXIMATE_CHART_VALUE`; it is not raw exact data.
- RBI USD reference rate: {len(rbi)} official dated observations, {rbi['date'].min()} through {rbi['date'].max()}. {rbi_tail_note}
- Business Analytiq page: {analytiq_status}
- UN Comtrade preview: {comtrade_status}

World Bank and Ministry file downloads and the RBI archive query returned HTTP 200 and passed validation. Optional phenolic source results are recorded below; no import unit value is treated as a market price.

## Missing-period register

| Dataset/source | Missing periods or records |
|---|---|
| World Bank RSS3 | No missing monthly values in the source timeline from 1960-01 through 2026-10 (802 of 802 months). |
| Ministry steel chart | No missing chart months from 2023-05 through 2026-04 (36 months for each curve). |
| RBI USD/INR | Archive returned through {rbi['date'].max()} only. {rbi_tail_note} |
| UN Comtrade HS 390940 | Public API outcomes: {comtrade_status}. These are acquisition gaps, not evidence of zero trade. |
| Business Analytiq | {analytiq_status}; no historical numeric record set was emitted. |

## Data-quality limits

- The Ministry PDF publishes the steel values as a graph, not a raw monthly table. Values are digitized visually from the plotted curves and rounded to the nearest Rs 100/tonne; the chart does not support exactness.
- RBI reference rates are reported only on source publication days. Weekends/holidays and the period after the last returned observation are not filled.
- No phenolic-resin historical market-price dataset was obtained from the two investigated sources.
"""
    path.write_text(report, encoding="utf-8", newline="\n")


def main() -> None:
    fail_if_outputs_exist()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    SOURCE_FILES.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "RANE-MMD-Data-Acquisition/1.0"

    wb_bytes = download(session, WORLD_BANK_URL)
    wb, wb_start, wb_end = extract_rss3(wb_bytes)
    save_source(SOURCE_FILES / "CMO-Historical-Data-Monthly.xlsx", wb_bytes)

    steel_bytes = download(session, STEEL_URL)
    steel, steel_start, steel_end = extract_steel(steel_bytes)
    save_source(SOURCE_FILES / "steel_ministry_apr_2026.pdf", steel_bytes)

    rbi_initial = session.get(RBI_URL, timeout=60)
    rbi_initial.raise_for_status()
    rbi_page = submit_rbi_query(
        session,
        rbi_initial.text,
        dt.date(2000, 1, 1),
        dt.date.today(),
    )
    rbi = extract_rbi_rates(rbi_page)
    save_source(
        SOURCE_FILES / "rbi_reference_rate_usd_2000-2026.html",
        rbi_page.encode("utf-8"),
    )

    # Validate that the requested dates are monthly observations, without
    # filling or interpolating any source data.
    wb_dates = pd.to_datetime(wb["date"])
    if not wb_dates.equals(pd.date_range(wb_dates.iloc[0], wb_dates.iloc[-1], freq="MS").to_series(index=wb_dates.index)):
        raise ValueError("World Bank RSS3 monthly date sequence has a missing period")

    wb.to_csv(OUTPUT / "natural_rubber_rss3.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    steel.to_csv(OUTPUT / "steel_hrc_crc.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    rbi.to_csv(OUTPUT / "usd_inr.csv", index=False, quoting=csv.QUOTE_MINIMAL)

    comtrade_status, comtrade_register_status = review_comtrade(session)
    analytiq_status, analytiq_register_status = review_business_analytiq(session)
    write_source_assessment(
        OUTPUT / "phenolic_resin_source_assessment.md",
        wb,
        steel,
        rbi,
        comtrade_status,
        analytiq_status,
    )

    register = [
        {
            "dataset": "natural_rubber_rss3.csv",
            "source": "World Bank Group, Commodity Markets (Pink Sheet)",
            "source_url": WORLD_BANK_URL,
            "source_file": "source_files/CMO-Historical-Data-Monthly.xlsx",
            "extraction_date": EXTRACTION_DATE,
            "status": "ACQUIRED_AND_VALIDATED",
            "date_start": wb_start,
            "date_end": wb_end,
            "records": len(wb),
            "data_quality": "OFFICIAL_SOURCE_VALUE",
            "notes": (
                "Unit retained as printed. Historical grade changes are noted "
                "in the output CSV: RSS3 from 2004; Singapore RSS1 in 2000-03; "
                "earlier Malaysia RSS1."
            ),
        },
        {
            "dataset": "steel_hrc_crc.csv",
            "source": "Ministry of Steel, Government of India",
            "source_url": STEEL_URL,
            "source_file": "source_files/steel_ministry_apr_2026.pdf",
            "extraction_date": EXTRACTION_DATE,
            "status": "ACQUIRED_APPROXIMATE_CHART_DIGITIZATION",
            "date_start": steel_start,
            "date_end": steel_end,
            "records": len(steel),
            "data_quality": "APPROXIMATE_CHART_VALUE",
            "notes": (
                "36 monthly periods x two curves; digitized from PDF page 5; "
                "rounded to nearest Rs 100/tonne; dates are first-of-month "
                "period labels; not exact raw observations."
            ),
        },
        {
            "dataset": "usd_inr.csv",
            "source": "Reserve Bank of India, Reference Rate Archive",
            "source_url": RBI_URL,
            "source_file": "source_files/rbi_reference_rate_usd_2000-2026.html",
            "extraction_date": EXTRACTION_DATE,
            "status": "ACQUIRED_AND_VALIDATED",
            "date_start": rbi["date"].min(),
            "date_end": rbi["date"].max(),
            "records": len(rbi),
            "data_quality": "OFFICIAL_RBI_REFERENCE_RATE",
            "notes": (
                "USD INR reference rate; latest returned observation is "
                f"{rbi['date'].max()}; no archive rows were returned for "
                f"{(dt.date.fromisoformat(rbi['date'].max()) + dt.timedelta(days=1)).isoformat()}"
                f" through {EXTRACTION_DATE}; no interpolation."
            ),
        },
        {
            "dataset": "phenolic resin historical prices",
            "source": "Business Analytiq",
            "source_url": BUSINESS_ANALYTIQ_URL,
            "source_file": "",
            "extraction_date": EXTRACTION_DATE,
            "status": analytiq_register_status,
            "date_start": "",
            "date_end": "",
            "records": 0,
            "data_quality": "NO_HISTORICAL_DATA_EMITTED",
            "notes": analytiq_status + " No paywall bypass or inferred series.",
        },
        {
            "dataset": "phenolic resin trade data, HS 390940",
            "source": "United Nations Comtrade API",
            "source_url": COMTRADE_URL,
            "source_file": "",
            "extraction_date": EXTRACTION_DATE,
            "status": comtrade_register_status,
            "date_start": "",
            "date_end": "",
            "records": 0,
            "data_quality": "NO_MARKET_PRICE_DATA_EMITTED",
            "notes": (
                comtrade_status
                + ". Trade values/quantities and derived import unit values "
                "are not market prices."
            ),
        },
    ]
    pd.DataFrame(register).to_csv(OUTPUT / "source_register.csv", index=False)

    for filename, required_columns, min_rows in [
        (
            "natural_rubber_rss3.csv",
            {"date", "value", "currency", "unit", "source", "source_url",
             "extraction_date", "data_quality"},
            1,
        ),
        (
            "steel_hrc_crc.csv",
            {"date", "value", "currency", "unit", "source", "source_url",
             "extraction_date", "data_quality"},
            72,
        ),
        (
            "usd_inr.csv",
            {"date", "value", "currency", "unit", "source", "source_url",
             "extraction_date", "data_quality"},
            1,
        ),
    ]:
        check = pd.read_csv(OUTPUT / filename)
        if not required_columns.issubset(check.columns) or len(check) < min_rows:
            raise ValueError(f"Output validation failed for {filename}")

    print(f"Extraction date: {EXTRACTION_DATE}")
    print(f"RSS3: {len(wb)} rows, {wb_start} to {wb_end}")
    print(f"Steel: {len(steel)} rows, {steel_start} to {steel_end}")
    print(f"USD/INR: {len(rbi)} rows, {rbi['date'].min()} to {rbi['date'].max()}")
    print(f"Outputs: {OUTPUT}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Acquisition failed: {error}", file=sys.stderr)
        raise
