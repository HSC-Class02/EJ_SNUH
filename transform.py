import math
import pandas as pd
ALIASES={
"revenue":["매출액","영업수익","의료수익","수익(매출액)"],"gross_profit":["매출총이익"],
"operating_income":["영업이익","영업이익(손실)","영업손익"],"pretax_income":["법인세비용차감전순이익","법인세비용차감전순손익"],
"net_income":["당기순이익","당기순이익(손실)","당기순손익"],"assets":["자산총계"],"current_assets":["유동자산"],
"cash":["현금및현금성자산"],"receivables":["매출채권","의료미수금"],"inventory":["재고자산"],"ppe":["유형자산"],
"liabilities":["부채총계"],"current_liabilities":["유동부채"],"equity":["자본총계"],
"cfo":["영업활동으로 인한 현금흐름","영업활동현금흐름"],"cfi":["투자활동으로 인한 현금흐름","투자활동현금흐름"],
"cff":["재무활동으로 인한 현금흐름","재무활동현금흐름"],"interest_expense":["이자비용"],
"capex_ppe":["유형자산의 취득"],"capex_intangible":["무형자산의 취득"],"debt_short":["단기차입금"],"debt_long":["장기차입금"]}
def num(v):
    try:return float(str(v).replace(',',''))
    except:return None
def pick(rows,names):
    for n in names:
        hit=rows[rows.account_nm.fillna('').str.replace(' ','',regex=False)==n.replace(' ','')]
        if not hit.empty:
            for c in ['thstrm_amount','frmtrm_amount']:
                v=num(hit.iloc[0].get(c));
                if v is not None:return v
    return None
def div(a,b): return a/b if a is not None and b not in (None,0) else None
def build_record(rows,meta,period):
    d={k:pick(rows,v) for k,v in ALIASES.items()}; debt=(d['debt_short'] or 0)+(d['debt_long'] or 0); capex=abs(d['capex_ppe'] or 0)+abs(d['capex_intangible'] or 0)
    d.update({"period":period,"year":int(meta['bsns_year']),"report_name":meta['report_nm'],"receipt_no":meta['rcept_no'],"debt":debt or None,"capex":capex or None})
    d['fcf']=(d['cfo']-capex) if d['cfo'] is not None else None; d['net_debt']=(debt-d['cash']) if d['cash'] is not None and debt else None
    d.update({"operating_margin":div(d['operating_income'],d['revenue']),"net_margin":div(d['net_income'],d['revenue']),"current_ratio":div(d['current_assets'],d['current_liabilities']),"debt_ratio":div(d['liabilities'],d['equity']),"equity_ratio":div(d['equity'],d['assets']),"roa":div(d['net_income'],d['assets']),"roe":div(d['net_income'],d['equity']),"asset_turnover":div(d['revenue'],d['assets']),"cfo_to_net_income":div(d['cfo'],d['net_income']),"interest_coverage":div(d['operating_income'],d['interest_expense'])})
    return d
