import io, os, zipfile, xml.etree.ElementTree as ET
from pathlib import Path
import requests, yaml
BASE="https://opendart.fss.or.kr/api"
ROOT=Path(__file__).resolve().parents[1]

def get_json(path, params):
    r=requests.get(f"{BASE}/{path}",params=params,timeout=60); r.raise_for_status(); j=r.json()
    if j.get("status") not in ("000",None): raise RuntimeError(f"DART {j.get('status')}: {j.get('message')}")
    return j

def find_corp_code(api_key, company_name):
    r=requests.get(f"{BASE}/corpCode.xml",params={"crtfc_key":api_key},timeout=60); r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z: root=ET.fromstring(z.read("CORPCODE.xml"))
    exact=[]
    for x in root.findall("list"):
        name=(x.findtext("corp_name") or "").strip()
        if name==company_name: exact.append((x.findtext("corp_code"),x.findtext("stock_code") or ""))
    if not exact: raise RuntimeError(f"DART 고유번호 목록에서 '{company_name}'을 찾지 못했습니다.")
    exact.sort(key=lambda x: bool(x[1]),reverse=True)
    return exact[0][0]

def list_reports(key,corp,bgn):
    out=[]
    for page in range(1,101):
        j=get_json("list.json",{"crtfc_key":key,"corp_code":corp,"bgn_de":bgn,"page_no":page,"page_count":100})
        out += j.get("list",[])
        if page>=int(j.get("total_page",1)): break
    allowed=("사업보고서","반기보고서","분기보고서")
    return [x for x in out if any(t in x.get("report_nm","") for t in allowed)]
