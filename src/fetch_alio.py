"""서울대학교병원 ALIO 재무공시 수집기.

ALIO 항목별 공시의 shell 페이지에서 공개된 doc.html fragment 경로를 찾아
요약 재무상태표(3120), 요약 손익계산서(3130)를 수집한다.
공시 표의 단위(백만원 등)를 확인한 뒤 dashboard 표준 단위인 원으로 환산한다.
"""
from __future__ import annotations

import re
import time
from html import unescape
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

BASES = ("https://www.alio.go.kr", "https://alio.go.kr")
SNUH_DISCLOSURE = "https://www.snuh.org/content/M004006002.do"
REPORTS = {
    "balance": {"item_no": "3120", "title": "요약 재무상태표"},
    "income": {"item_no": "3130", "title": "요약 손익계산서"},
}
DOC_URL_RE = re.compile(
    r"""\.load\(\s*["'](?P<path>/upload/disclosure/[^"']+/doc\.html)["']""",
    re.IGNORECASE,
)
YEAR_RE = re.compile(r"(20\d{2})\s*년")
UNIT_RE = re.compile(r"단위\s*[:：]\s*(백만원|천원|원)")
NUMBER_RE = re.compile(r"^-?\d[\d,]*(?:\.\d+)?$")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
    "Referer": SNUH_DISCLOSURE,
}


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value or "")).strip()


def _expand_rows(trs):
    """rowspan/colspan이 있는 HTML 표를 사각형 셀 그리드로 전개."""
    grid = {}
    for row_index, tr in enumerate(trs):
        col_index = 0
        for cell in tr.find_all(["th", "td"], recursive=False):
            while (row_index, col_index) in grid:
                col_index += 1
            rowspan = int(cell.get("rowspan") or 1)
            colspan = int(cell.get("colspan") or 1)
            for dr in range(rowspan):
                for dc in range(colspan):
                    grid[(row_index + dr, col_index + dc)] = cell
            col_index += colspan
    if not grid:
        return []
    row_count = max(r for r, _ in grid) + 1
    col_count = max(c for _, c in grid) + 1
    return [[grid.get((r, c)) for c in range(col_count)] for r in range(row_count)]


def _cell_text(cell) -> str:
    return _clean(cell.get_text(" ", strip=True)) if cell else ""


def _parse_number(raw: str) -> Optional[float]:
    text = _clean(raw).replace(",", "")
    if text in ("", "-", "–", "—", "해당사항 없음"):
        return None
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1].strip()
    if NUMBER_RE.fullmatch(text):
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _unit_multiplier(html: str) -> float:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    match = UNIT_RE.search(text)
    if not match:
        # ALIO 서울대학교병원 최신 재무공시 표의 공시단위는 백만원이다.
        return 1_000_000.0
    return {"백만원": 1_000_000.0, "천원": 1_000.0, "원": 1.0}[match.group(1)]


def _table_records(html: str, kind: str) -> dict[int, dict]:
    soup = BeautifulSoup(html, "html.parser")
    multiplier = _unit_multiplier(html)
    collected: dict[int, dict] = {}

    for table in soup.find_all("table"):
        trs = table.find_all("tr")
        grid = _expand_rows(trs)
        if len(grid) < 3:
            continue

        # ALIO 재무공시는 연도 헤더에 'YYYY년 결산'을 사용한다.
        header_index = None
        year_columns = {}
        for row_index, row in enumerate(grid[:6]):
            hits = {}
            for col_index, cell in enumerate(row):
                match = YEAR_RE.search(_cell_text(cell))
                if match:
                    hits[col_index] = int(match.group(1))
            if len(hits) >= 2:
                header_index = row_index
                year_columns = hits
                break
        if header_index is None:
            continue

        first_year_col = min(year_columns)
        if first_year_col == 0:
            continue

        for row in grid[header_index + 1:]:
            if len(row) <= max(year_columns):
                continue
            label_parts = []
            for cell in row[:first_year_col]:
                label = _cell_text(cell)
                if label and (not label_parts or label != label_parts[-1]):
                    label_parts.append(label)
            label = re.sub(r"[\s()（）]", "", "".join(label_parts))
            if not label:
                continue

            metric = None
            if kind == "balance":
                if "자산총계" in label:
                    metric = "assets"
                elif "부채총계" in label:
                    metric = "liabilities"
                elif "자본총계" in label:
                    metric = "equity"
                elif "유동자산" in label and "비유동자산" not in label:
                    metric = "current_assets"
                elif "유동부채" in label and "비유동부채" not in label:
                    metric = "current_liabilities"
            else:
                if label in ("매출", "순매출", "매출액"):
                    metric = "revenue"
                elif label.startswith("영업이익") and "영업이익외" not in label:
                    metric = "operating_income"
                elif label.startswith(("당기순이익", "당기순손익")):
                    metric = "net_income"

            if metric is None:
                continue

            for col_index, year in year_columns.items():
                value = _parse_number(_cell_text(row[col_index]))
                if value is None:
                    continue
                collected.setdefault(year, {})[metric] = value * multiplier

    return collected


def _fetch_fragment(session: requests.Session, item_no: str) -> tuple[str, str]:
    """ALIO 보고서 shell 및 실제 표 fragment를 조회한다."""
    last_error = None
    for base in BASES:
        shell_url = f"{base}/item/itemReportTerm.do"
        try:
            response = session.get(
                shell_url,
                params={
                    "apbaId": "C0083",
                    "reportFormRootNo": item_no,
                    "disclosureNo": "",
                },
                headers={**HEADERS, "Origin": base},
                timeout=40,
            )
            response.raise_for_status()
            if not response.encoding or response.encoding.lower() == "iso-8859-1":
                response.encoding = response.apparent_encoding or "utf-8"
            shell = response.text
            match = DOC_URL_RE.search(shell)
            if not match:
                # 공시 페이지가 직접 fragment URL을 출력하는 형태도 지원한다.
                match = re.search(
                    r"""(?P<path>/upload/disclosure/[^"']+/doc\.html)""",
                    shell,
                    re.IGNORECASE,
                )
            if not match:
                raise RuntimeError(
                    f"ALIO 보고서 {item_no}에서 doc.html 경로를 찾지 못했습니다. "
                    f"HTTP {response.status_code}, 응답 길이 {len(shell)}"
                )

            time.sleep(1.5)
            doc_url = base + match.group("path")
            doc_response = session.get(
                doc_url,
                headers={**HEADERS, "Origin": base, "Referer": response.url},
                timeout=40,
            )
            doc_response.raise_for_status()
            if not doc_response.encoding or doc_response.encoding.lower() == "iso-8859-1":
                doc_response.encoding = doc_response.apparent_encoding or "utf-8"
            return doc_response.text, doc_url
        except (requests.RequestException, RuntimeError) as exc:
            last_error = exc
            time.sleep(1.5)
    raise RuntimeError(f"ALIO 항목 {item_no} 수집 실패: {last_error}")


def fetch_alio_financials(raw_dir: Path) -> tuple[list[dict], list[str]]:
    """두 ALIO 재무공시를 수집하고 annual dashboard records로 변환한다."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    combined: dict[int, dict] = {}
    source_urls = []
    errors = []

    for kind, config in REPORTS.items():
        item_no = config["item_no"]
        try:
            html, source_url = _fetch_fragment(session, item_no)
            (raw_dir / f"snuh_alio_{kind}_{item_no}.html").write_text(
                html, encoding="utf-8"
            )
            source_urls.append(source_url)
            rows_by_year = _table_records(html, kind)
            for year, metrics in rows_by_year.items():
                combined.setdefault(year, {}).update(metrics)
        except Exception as exc:
            errors.append(f"{config['title']} ({item_no}): {exc}")

    records = []
    for year, values in sorted(combined.items()):
        revenue = values.get("revenue")
        operating_income = values.get("operating_income")
        net_income = values.get("net_income")
        assets = values.get("assets")
        liabilities = values.get("liabilities")
        equity = values.get("equity")
        current_assets = values.get("current_assets")
        current_liabilities = values.get("current_liabilities")

        def ratio(numerator, denominator):
            if numerator is None or denominator in (None, 0):
                return None
            return numerator / denominator

        # 손익계산서와 재무상태표의 핵심 항목이 확인된 연도만 게시한다.
        if not any(v is not None for v in (revenue, operating_income, net_income, assets, liabilities, equity)):
            continue

        records.append({
            "year": year,
            "period": "annual",
            "report_name": "ALIO 결산자료",
            "revenue": revenue,
            "operating_income": operating_income,
            "net_income": net_income,
            "assets": assets,
            "liabilities": liabilities,
            "equity": equity,
            "cfo": None,
            "fcf": None,
            "operating_margin": ratio(operating_income, revenue),
            "net_margin": ratio(net_income, revenue),
            "current_ratio": ratio(current_assets, current_liabilities),
            "debt_ratio": ratio(liabilities, equity),
            "equity_ratio": ratio(equity, assets),
            "roa": ratio(net_income, assets),
            "roe": ratio(net_income, equity),
            "data_source": "ALIO",
        })

    if not records:
        raise RuntimeError(
            "ALIO 재무공시에서 분석 가능한 연도별 재무수치를 추출하지 못했습니다. "
            + " | ".join(errors)
        )
    return records, source_urls
