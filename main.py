import json, os
from datetime import date
from pathlib import Path
import pandas as pd, yaml
from src.fetch_dart import find_corp_code,list_reports,get_json
from src.transform import build_record
ROOT=Path(__file__).resolve().parents[1]
def main():
    key=os.environ.get("DART_API_KEY")
    if not key: raise SystemExit("DART_API_KEY 환경변수가 필요합니다.")
    cfg=yaml.safe_load((ROOT/'config.yml').read_text(encoding='utf-8')); corp=find_corp_code(key,cfg['company_name'])
    reports=list_reports(key,corp,f"{cfg['start_year']}0101"); (ROOT/'data/raw/reports.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
    code_to_period={"11011":"annual","11012":"half-year","11013":"quarterly","11014":"quarterly"}; records=[]; errors=[]
    for m in reports:
        y=m.get('rcept_dt','')[:4]; nm=m.get('report_nm',''); code=next((c for c,p in cfg['report_types'].items() if str(y) in nm and False),None)
        # 보고서명으로 보고서 코드를 판정하며 정정공시는 최신 접수번호를 우선 사용
        if '사업보고서' in nm: rc='11011'
        elif '반기보고서' in nm: rc='11012'
        elif '분기보고서' in nm and any(x in nm for x in ['09.30','3분기']): rc='11014'
        elif '분기보고서' in nm: rc='11013'
        else: continue
        bsns_year=str(int(y)-1) if rc=='11011' else y
        try:
            j=get_json('fnlttSinglAcntAll.json',{'crtfc_key':key,'corp_code':corp,'bsns_year':bsns_year,'reprt_code':rc,'fs_div':cfg['fs_div']})
            rows=pd.DataFrame(j.get('list',[]));
            if not rows.empty: records.append(build_record(rows,{'bsns_year':bsns_year,'report_nm':nm,'rcept_no':m['rcept_no']},code_to_period[rc]))
        except Exception as e: errors.append({'report':nm,'error':str(e)})
    if records:
        df=pd.DataFrame(records).sort_values(['year','period']).drop_duplicates(['year','period'],keep='last')
        df.to_csv(ROOT/'data/processed/financials.csv',index=False,encoding='utf-8-sig')
        (ROOT/'docs/data.json').write_text(df.where(pd.notna(df),None).to_json(orient='records',force_ascii=False),encoding='utf-8')
    (ROOT/'data/processed/errors.json').write_text(json.dumps(errors,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'docs/updated.json').write_text(json.dumps({'updated_at':date.today().isoformat(),'corp_code':corp},ensure_ascii=False),encoding='utf-8')
if __name__=='__main__': main()
