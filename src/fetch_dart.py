import io, zipfile, requests, xml.etree.ElementTree as ET
BASE = "https://opendart.fss.or.kr/api"
def get_json(endpoint, params):
    r=requests.get(f"{BASE}/{endpoint}",params=params,timeout=45); r.raise_for_status()
    data=r.json()
    if data.get("status") not in ("000", "013"):
        raise RuntimeError(f"OpenDART {data.get('status')}: {data.get('message')}")
    return data
def find_corp_code(key, company_name):
    r=requests.get(f"{BASE}/corpCode.xml",params={"crtfc_key":key},timeout=60); r.raise_for_status()
    try:
        z=zipfile.ZipFile(io.BytesIO(r.content))
        root=ET.fromstring(z.read(z.namelist()[0]))
    except Exception as e:
        raise RuntimeError("OpenDART 기업고유번호 파일을 읽을 수 없습니다. API 키와 응답을 확인하세요.") from e
    matches=[]
    for item in root.findall("list"):
        name=(item.findtext("corp_name") or "").strip()
        if name == company_name: matches.append(item.findtext("corp_code"))
    if not matches:
        raise RuntimeError(f"'{company_name}'이 OpenDART 기업목록에 없습니다. 상장 여부와 무관하게 OpenDART 등록 여부가 필요합니다. ALIO 결산자료를 별도 수집원으로 사용하세요.")
    return matches[0]
def list_reports(key, corp_code, start_date):
    out=[]; page=1
    while True:
        j=get_json("list.json",{"crtfc_key":key,"corp_code":corp_code,"bgn_de":start_date,"end_de":"20991231","pblntf_ty":"A","page_no":page,"page_count":100,"last_reprt_at":"Y"})
        out.extend(j.get("list",[]))
        if page >= int(j.get("total_page",1)): break
        page += 1
    return out
