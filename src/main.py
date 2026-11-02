import json
import os
import re
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

from src.fetch_dart import find_corp_code, get_json, list_reports
from src.fetch_alio import fetch_alio_financials
from src.transform import build_record

ROOT = Path(__file__).resolve().parents[1]
DATA_COLUMNS = [
    "year", "period", "report_name", "revenue", "operating_income",
    "net_income", "assets", "liabilities", "equity", "cfo", "fcf",
    "operating_margin", "net_margin", "current_ratio", "debt_ratio",
    "equity_ratio", "roa", "roe", "data_source",
]


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )


def read_existing_dashboard_data(path: Path):
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def classify_report(report):
    name = str(report.get("report_nm", ""))
    receipt_date = str(report.get("rcept_dt", ""))
    receipt_year = int(receipt_date[:4]) if receipt_date[:4].isdigit() else date.today().year

    if "사업보고서" in name:
        return str(receipt_year - 1), "11011", "annual"
    if "반기보고서" in name:
        return str(receipt_year), "11012", "half-year"

    quarter_match = re.search(r"([13])\s*분기", name)
    if quarter_match:
        quarter = quarter_match.group(1)
        return str(receipt_year), ("11013" if quarter == "1" else "11014"), "quarterly"

    if "분기보고서" in name:
        report_code = "11014" if ("09.30" in name or "9.30" in name) else "11013"
        return str(receipt_year), report_code, "quarterly"
    return None


def fetch_financial_statement(api_key, corp_code, year, report_code, preferred_fs):
    fs_order = [preferred_fs, "CFS" if preferred_fs == "OFS" else "OFS"]
    last_error = None
    for fs_div in fs_order:
        try:
            result = get_json(
                "fnlttSinglAcntAll.json",
                {
                    "crtfc_key": api_key,
                    "corp_code": corp_code,
                    "bsns_year": year,
                    "reprt_code": report_code,
                    "fs_div": fs_div,
                },
            )
            rows = result.get("list") or []
            if rows:
                return rows, fs_div
        except Exception as exc:
            last_error = exc
    if last_error:
        raise last_error
    return [], preferred_fs


def collect_dart(config, raw_dir):
    api_key = os.environ.get("DART_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GitHub Actions Secret DART_API_KEY가 설정되지 않았습니다.")

    corp_code = find_corp_code(api_key, config.get("company_name", "서울대학교병원"))
    reports = list_reports(
        api_key,
        corp_code,
        f'{int(config.get("start_year", 2010))}0101',
    )
    write_json(raw_dir / "dart_reports.json", reports)

    records = []
    errors = []
    codes = {"11011": "annual", "11012": "half-year", "11013": "quarterly", "11014": "quarterly"}
    for report in reports:
        classified = classify_report(report)
        if not classified:
            continue
        year, report_code, period = classified
        try:
            rows, fs_div = fetch_financial_statement(
                api_key, corp_code, year, report_code, config.get("fs_div", "OFS")
            )
            if rows:
                record = build_record(
                    pd.DataFrame(rows),
                    {"bsns_year": year, "report_nm": report.get("report_nm", "")},
                    period,
                )
                record["data_source"] = "OpenDART"
                record["fs_div"] = fs_div
                records.append(record)
            else:
                errors.append({
                    "source": "OpenDART",
                    "report": report.get("report_nm", ""),
                    "year": year,
                    "error": "재무제표 계정 데이터가 없습니다.",
                })
        except Exception as exc:
            errors.append({
                "source": "OpenDART",
                "report": report.get("report_nm", ""),
                "year": year,
                "error": str(exc),
            })
    return records, errors, corp_code, len(reports)


def main():
    raw_dir = ROOT / "data" / "raw"
    processed_dir = ROOT / "data" / "processed"
    docs_dir = ROOT / "docs"
    data_json = docs_dir / "data.json"
    for directory in (raw_dir, processed_dir, docs_dir):
        directory.mkdir(parents=True, exist_ok=True)

    existing_data = read_existing_dashboard_data(data_json)
    records = []
    errors = []
    corp_code = None
    dart_report_count = 0
    alio_urls = []
    data_source = "OpenDART"
    status = "pending"
    message = "DART 및 ALIO 자료를 조회하고 있습니다."

    try:
        config = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8")) or {}
    except Exception as exc:
        config = {"company_name": "서울대학교병원", "start_year": 2010, "fs_div": "OFS"}
        errors.append({"source": "config", "error": str(exc)})

    # 1) DART는 확인 가능한 자료를 우선 사용한다.
    try:
        records, dart_errors, corp_code, dart_report_count = collect_dart(config, raw_dir)
        errors.extend(dart_errors)
        if records:
            data_source = "OpenDART"
            status = "success"
            message = f"OpenDART 재무자료 {len(records)}개 기간을 수집했습니다."
        elif dart_report_count == 0:
            message = "DART 기업코드는 확인했으나 공시 목록이 0건입니다. ALIO 재무공시로 전환합니다."
    except Exception as exc:
        errors.append({"source": "OpenDART", "stage": "collection", "error": str(exc)})
        message = f"DART 자료가 없어 ALIO 공시를 조회합니다: {exc}"

    # 2) DART 재무자료가 없으면 ALIO의 공식 재무공시 3120/3130을 사용한다.
    if not records:
        try:
            alio_records, alio_urls = fetch_alio_financials(raw_dir / "alio")
            records = alio_records
            data_source = "ALIO"
            status = "success"
            years = [r["year"] for r in records]
            message = (
                f"ALIO 요약 재무상태표·손익계산서에서 "
                f"{min(years)}~{max(years)}년 {len(records)}개 연도 자료를 수집했습니다."
            )
        except Exception as exc:
            errors.append({"source": "ALIO", "stage": "collection", "error": str(exc)})
            status = "fallback_failed"
            message = f"ALIO 자료 수집도 실패했습니다. 세부 오류 로그를 확인하세요: {exc}"

    # 새 수집값이 있으면 파일을 갱신한다. 모두 실패했을 때 기존 값은 덮어쓰지 않는다.
    if records:
        frame = pd.DataFrame(records)
        frame = frame.sort_values(["year", "period"]).drop_duplicates(
            ["year", "period"], keep="last"
        )
        for column in DATA_COLUMNS:
            if column not in frame.columns:
                frame[column] = None
        frame = frame[DATA_COLUMNS]
        frame.to_csv(
            processed_dir / "financials.csv",
            index=False,
            encoding="utf-8-sig",
        )
        data_json.write_text(
            frame.where(pd.notna(frame), None).to_json(
                orient="records", force_ascii=False
            ),
            encoding="utf-8",
        )
    elif not data_json.exists():
        write_json(data_json, [])

    write_json(processed_dir / "errors.json", errors)
    write_json(
        docs_dir / "updated.json",
        {
            "updated_at": date.today().isoformat(),
            "data_source": data_source,
            "status": status,
            "message": message,
            "corp_code": corp_code,
            "dart_report_count": dart_report_count,
            "record_count": len(records),
            "alio_source_urls": alio_urls,
            "previous_data_preserved": bool(existing_data) and not bool(records),
        },
    )

    if status != "success":
        print(f"::warning::{message}")
        print(f"Collection errors: {len(errors)} (saved to data/processed/errors.json)")
    else:
        print(message)


if __name__ == "__main__":
    main()
