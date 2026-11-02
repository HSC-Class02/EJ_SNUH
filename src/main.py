import json
import os
import re
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

from src.fetch_dart import find_corp_code, get_json, list_reports
from src.transform import build_record

ROOT = Path(__file__).resolve().parents[1]
DATA_COLUMNS = [
    "year", "period", "report_name", "revenue", "operating_income",
    "net_income", "assets", "liabilities", "equity", "cfo", "fcf",
    "operating_margin", "net_margin", "current_ratio", "debt_ratio",
    "equity_ratio", "roa", "roe",
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

    # 공시 제목에 분기 숫자가 없는 경우에도 분기보고서임을 로그에 남긴다.
    if "분기보고서" in name:
        if "09.30" in name or "9.30" in name or "3분기" in name:
            return str(receipt_year), "11014", "quarterly"
        return str(receipt_year), "11013", "quarterly"
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


def main():
    raw_dir = ROOT / "data" / "raw"
    processed_dir = ROOT / "data" / "processed"
    docs_dir = ROOT / "docs"
    data_json = docs_dir / "data.json"

    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    # 새 수집 결과가 없을 때 기존 대시보드 데이터를 빈 값으로 덮어쓰지 않는다.
    existing_data = read_existing_dashboard_data(data_json)
    records = []
    reports = []
    errors = []
    corp_code = None
    status = "no_dart_financials"
    message = "DART 재무자료를 확인하지 못했습니다. 기존 자료가 있으면 그대로 표시합니다."

    config_path = ROOT / "config.yml"
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        api_key = os.environ.get("DART_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("GitHub Actions Secret DART_API_KEY가 설정되지 않았습니다.")

        corp_code = find_corp_code(api_key, config.get("company_name", "서울대학교병원"))
        reports = list_reports(
            api_key,
            corp_code,
            f'{int(config.get("start_year", 2010))}0101',
        )
        write_json(raw_dir / "reports.json", reports)

        if not reports:
            status = "no_dart_reports"
            message = "OpenDART 기업코드는 확인했지만 설정된 기간에 수집 가능한 공시가 없습니다."
        else:
            codes = {"11011": "annual", "11012": "half-year", "11013": "quarterly", "11014": "quarterly"}
            for report in reports:
                classified = classify_report(report)
                if not classified:
                    continue

                year, report_code, period = classified
                report_name = report.get("report_nm", "")
                try:
                    rows, fs_div = fetch_financial_statement(
                        api_key,
                        corp_code,
                        year,
                        report_code,
                        config.get("fs_div", "OFS"),
                    )
                    if rows:
                        record = build_record(
                            pd.DataFrame(rows),
                            {"bsns_year": year, "report_nm": report_name},
                            period,
                        )
                        record["fs_div"] = fs_div
                        records.append(record)
                    else:
                        errors.append({
                            "report": report_name,
                            "year": year,
                            "report_code": report_code,
                            "error": "해당 보고서의 재무제표 계정 데이터가 없습니다.",
                        })
                except Exception as exc:
                    errors.append({
                        "report": report_name,
                        "year": year,
                        "report_code": report_code,
                        "error": str(exc),
                    })

            if records:
                frame = pd.DataFrame(records)
                frame = frame.sort_values(["year", "period"]).drop_duplicates(
                    ["year", "period"], keep="last"
                )
                frame.to_csv(
                    processed_dir / "financials.csv",
                    index=False,
                    encoding="utf-8-sig",
                )
                frame_for_json = frame.where(pd.notna(frame), None)
                data_json.write_text(
                    frame_for_json.to_json(
                        orient="records",
                        force_ascii=False,
                        date_format="iso",
                    ),
                    encoding="utf-8",
                )
                status = "success" if not errors else "partial"
                message = (
                    f"DART 재무자료 {len(frame)}개 기간을 수집했습니다."
                    if not errors
                    else f"DART 재무자료 {len(frame)}개 기간을 수집했습니다. 일부 보고서는 계정 데이터가 없어 제외했습니다."
                )
            else:
                status = "no_usable_financials"
                message = "공시 목록은 확인했으나 대시보드용 재무제표 계정 데이터는 확보하지 못했습니다."

    except Exception as exc:
        error_text = str(exc)
        errors.append({"stage": "DART collection", "error": error_text})
        if "기업목록에 없습니다" in error_text:
            status = "no_dart_registration"
            message = "서울대학교병원은 현재 OpenDART 기업목록에서 확인되지 않아 DART 자료를 수집할 수 없습니다. 대시보드 배포는 계속하며 ALIO 자료 연동이 필요합니다."
        else:
            status = "error"
            message = f"DART 수집 단계에서 오류가 발생했습니다: {error_text}"

    # 데이터가 없는 상황에서도 Pages가 배포되도록 유효한 JSON 파일을 항상 만든다.
    if not data_json.exists():
        write_json(data_json, [])
    write_json(processed_dir / "errors.json", errors)
    write_json(raw_dir / "reports.json", reports)

    if not (processed_dir / "financials.csv").exists():
        pd.DataFrame(columns=DATA_COLUMNS).to_csv(
            processed_dir / "financials.csv",
            index=False,
            encoding="utf-8-sig",
        )

    write_json(
        docs_dir / "updated.json",
        {
            "updated_at": date.today().isoformat(),
            "data_source": "OpenDART",
            "status": status,
            "message": message,
            "corp_code": corp_code,
            "report_count": len(reports),
            "record_count": len(records),
            "previous_data_preserved": bool(existing_data) and not bool(records),
        },
    )

    if status not in ("success", "partial"):
        print(f"::warning::{message}")
    else:
        print(message)


if __name__ == "__main__":
    main()
