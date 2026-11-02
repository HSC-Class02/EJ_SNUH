import pandas as pd
def _amount(df, names):
    for name in names:
        rows=df[df["account_nm"].astype(str).str.replace(" ","",regex=False).eq(name.replace(" ",""))]
        if not rows.empty:
            row=rows.iloc[0]
            for col in ("thstrm_amount","thstrm_add_amount"):
                if col in row and pd.notna(row[col]):
                    try: return float(str(row[col]).replace(",","").strip())
                    except (ValueError,TypeError): pass
    return None
def build_record(df, meta, period):
    revenue=_amount(df,["매출액","수익(매출액)","의료수익","사업수익","영업수익"])
    op=_amount(df,["영업이익","영업손실"])
    net=_amount(df,["당기순이익","당기순손실","당기순이익(손실)"])
    assets=_amount(df,["자산총계"]); liabilities=_amount(df,["부채총계"]); equity=_amount(df,["자본총계"])
    cfo=_amount(df,["영업활동현금흐름","영업활동으로 인한 현금흐름"])
    capex=_amount(df,["유형자산의 취득","유형자산 취득"])
    div=lambda a,b: a/b if a is not None and b not in (None,0) else None
    year=int(meta["bsns_year"])
    return {"year":year,"period":period,"report_name":meta.get("report_nm",""),"revenue":revenue,"operating_income":op,"net_income":net,"assets":assets,"liabilities":liabilities,"equity":equity,"cfo":cfo,"fcf":cfo-capex if cfo is not None and capex is not None else None,"operating_margin":div(op,revenue),"net_margin":div(net,revenue),"current_ratio":None,"debt_ratio":div(liabilities,equity),"equity_ratio":div(equity,assets),"roa":div(net,assets),"roe":div(net,equity)}
