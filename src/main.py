import json, os
from datetime import date
from pathlib import Path
import pandas as pd, yaml
from src.fetch_dart import find_corp_code, list_reports, get_json
from src.transform import build_record
ROOT=Path(__file__).resolve().parents[1]
def main():
    key=os.environ.get("DART_API_KEY")
    if not key: raise SystemExit("DART_API_KEY Secret이 필요합니다.")
    cfg=yaml.safe_load((ROOT/"config.yml").read_text(encoding="utf-8"))
    corp=find_corp_code(key,cfg["company_name"])
    reports=list_reports(key,corp,f'{cfg["start_year"]}0101')
    (ROOT/"data/raw").mkdir(parents=True,exist_ok=True); (ROOT/"data/processed").mkdir(parents=True,exist_ok=True); (ROOT/"docs").mkdir(exist_ok=True)
    (ROOT/"data/raw/reports.json").write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding="utf-8")
    codes={"11011":"annual","11012":"half-year","11013":"quarterly","11014":"quarterly"}
    records=[]; errors=[]
    for m in reports:
        nm=m.get("report_nm",""); y=m.get("rcept_dt","")[:4]
        if "사업보고서" in nm: rc="11011"; year=str(int(y)-1)
        elif "반기보고서" in nm: rc="11012"; year=y
        elif "분기보고서" in nm and any(s in nm for s in ["09.30","3분기"]): rc="11014"; year=y
        elif "분기보고서" in nm: rc="11013"; year=y
        else: continue
        try:
            j=get_json("fnlttSinglAcntAll.json",{"crtfc_key":key,"corp_code":corp,"bsns_year":year,"reprt_code":rc,"fs_div":cfg.get("fs_div","OFS")})
            if j.get("list"): records.append(build_record(pd.DataFrame(j["list"]),{"bsns_year":year,"report_nm":nm},codes[rc]))
        except Exception as e: errors.append({"report":nm,"error":str(e)})
    if not records:
        (ROOT/"data/processed/errors.json").write_text(json.dumps(errors,ensure_ascii=False,indent=2),encoding="utf-8")
        raise SystemExit("OpenDART에서 분석 가능한 재무자료를 찾지 못했습니다. data/processed/errors.json을 확인하세요. 서울대학교병원은 ALIO 결산자료 수집 경로가 필요할 수 있습니다.")
    df=pd.DataFrame(records).sort_values(["year","period"]).drop_duplicates(["year","period"],keep="last")
    df.to_csv(ROOT/"data/processed/financials.csv",index=False,encoding="utf-8-sig")
    (ROOT/"docs/data.json").write_text(df.where(pd.notna(df),None).to_json(orient="records",force_ascii=False),encoding="utf-8")
    (ROOT/"data/processed/errors.json").write_text(json.dumps(errors,ensure_ascii=False,indent=2),encoding="utf-8")
    (ROOT/"docs/updated.json").write_text(json.dumps({"updated_at":date.today().isoformat(),"corp_code":corp},ensure_ascii=False),encoding="utf-8")
if __name__=="__main__": main()
