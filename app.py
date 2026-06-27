"""
Fiz Availability Briefing
Upload the Master_LIst inventory file → instant availability briefing widget.
"""

import streamlit as st
import pandas as pd
import numpy as np
import io, re, json

st.set_page_config(
    page_title="Fiz · Availability Briefing",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
#MainMenu, footer, header {visibility: hidden;}
.block-container {padding: 1rem 1.5rem 2rem; max-width: 100%;}
div[data-testid="stMetric"] {background: #f7f6f3; border-radius: 8px; padding: 8px 12px;}
</style>
""", unsafe_allow_html=True)

# ── ANALYSIS ENGINE ──────────────────────────────────────────────────────────

PRODUCE_CATS = ['Fruits & Vegetables']
BRAND_TIERS = {
    'rawdatain':'PREMIUM_LOCAL','evian':'PREMIUM_INTL','volvic':'PREMIUM_INTL',
    'san pellegrino':'PREMIUM_INTL','perrier':'PREMIUM_INTL','fiji':'PREMIUM_INTL',
    'masafi':'MID','arwa':'VALUE','abraaj':'VALUE','aquagulf':'VALUE',
}
FLAVOUR_KW = {
    'mint','strawberry','chocolate','mango','vanilla','lemon','orange','banana',
    'peach','blueberry','raspberry','caramel','mocha','cherry','apple','watermelon',
    'grape','lime','coconut','passion','hazelnut','coffee','honey','cinnamon',
    'rose','saffron','tropical',
}
VARIANT_KW = {
    'zero','diet','light','sugar free','no sugar','low fat','full fat','skimmed',
    'semi skimmed','fat free','reduced fat','unsalted','salted','whole','wholegrain','wholemeal',
}

def brand_tier(v,d):
    s=(str(v)+' '+str(d)).lower()
    for b,t in BRAND_TIERS.items():
        if b in s: return t
    if any(k in s for k in ['organic','natureland','bonato','earth organic']): return 'PREMIUM_ORGANIC'
    return 'STANDARD'
def get_size(d):
    d=str(d).lower()
    for p in ['200ml','330ml','250ml','500ml','750ml','1l','1.5l','2l']:
        if p in d: return p
    return 'other'
def get_flavour(d): return {f for f in FLAVOUR_KW if f in d.lower()}
def get_variant(d): return {v for v in VARIANT_KW if v in d.lower()}
def is_organic(d):  return any(k in d.lower() for k in ['organic','natureland','bonato','earth organic'])

def detect_sold_col(columns, store_kw, month_kw):
    cands=[c for c in columns if 'Sold Qty' in c and month_kw in c and store_kw in c]
    if not cands: return None
    def sd(col):
        m=re.search(r'(\d+)\s+(?:June|Jun|May)',col); return int(m.group(1)) if m else 99
    return sorted(cands,key=sd)[0]

def sub_quality(or_,sr_,cat):
    ood=str(or_.get('Description','')); sud=str(sr_.get('Description',''))
    oos_p=float(or_.get('Net Unit Cost',0) or 0); sub_p=float(sr_.get('Net Unit Cost',0) or 0)
    oos_v=str(or_.get('Vendor','')); sub_v=str(sr_.get('Vendor',''))
    ratio=sub_p/oos_p if oos_p>0.01 else 1.0
    pw=5.0 if cat=='Water' else 3.0; psc=4.0 if cat=='Water' else 1.8
    if is_organic(ood)!=is_organic(sud):
        return 'STRONG','Organic vs mainstream — functional substitute but different positioning'
    if ratio>pw: return 'WEAK',f'{ratio:.1f}x price difference — customer won\'t trade up'
    if ratio<(1/pw): return 'WEAK',f'Sub is {(1/ratio):.1f}x cheaper — likely inferior quality'
    ofl=get_flavour(ood); sfl=get_flavour(sud); ovr=get_variant(ood); svr=get_variant(sud)
    fcap=False
    if ofl and sfl and ofl!=sfl: return 'WEAK',f'Different flavour ({", ".join(sorted(ofl))} vs {", ".join(sorted(sfl))})'
    if (ofl and not sfl) or (not ofl and sfl): fcap=True
    if ovr!=svr: fcap=True
    if cat=='Water':
        oot=brand_tier(oos_v,ood); sut=brand_tier(sub_v,sud)
        osz=get_size(ood); ssz=get_size(sud)
        if osz in {'200ml','330ml','250ml'} and ssz in {'500ml','750ml','1l','1.5l','2l'}: return None,None
        tier_map={('PREMIUM_LOCAL','PREMIUM_LOCAL'):'DIRECT',('PREMIUM_INTL','PREMIUM_INTL'):'DIRECT',
            ('PREMIUM_LOCAL','PREMIUM_INTL'):'STRONG',('PREMIUM_INTL','PREMIUM_LOCAL'):'STRONG',
            ('MID','MID'):'DIRECT',('VALUE','VALUE'):'DIRECT'}
        tr=tier_map.get((oot,sut),'WEAK')
        if tr=='WEAK': return 'WEAK',f'{oot} vs {sut} tier — different customer'
        if ratio>psc or (osz!=ssz and osz!='other'): tr='STRONG'
        if fcap and tr=='DIRECT': tr='STRONG'
        return tr,{'DIRECT':'Same tier & format','STRONG':'Comparable tier'}.get(tr,'Weak')
    if ratio>psc: r,l='STRONG',f'Similar use case, {ratio:.1f}x price'
    elif ratio>1.4: r,l='STRONG',f'Comparable, {ratio:.1f}x price'
    else: r,l='DIRECT','Comparable brand & price'
    if fcap and r=='DIRECT': r,l='STRONG','Same category but different flavour/variant'
    return r,l

@st.cache_data(show_spinner=False)
def load_and_analyse(file_bytes, filename):
    inv=pd.read_excel(io.BytesIO(file_bytes)); inv.columns=[c.strip() for c in inv.columns]
    inv=inv[inv['Status']=='Active'].copy(); inv['Barcode']=inv['Barcode'].astype(str).str.strip()
    cols=list(inv.columns)
    j7d=detect_sold_col(cols,'Jahra','June') or detect_sold_col(cols,'Jahra','Jun')
    q7d=detect_sold_col(cols,'Qurtuba','June') or detect_sold_col(cols,'Qurtuba','Jun')
    ss7d=detect_sold_col(cols,'Sabah Salem','June') or detect_sold_col(cols,'Sabah Salem','Jun')
    jmay=detect_sold_col(cols,'Jahra','May'); qmay=detect_sold_col(cols,'Qurtuba','May')
    ssmay=detect_sold_col(cols,'Sabah Salem','May')
    rn={}
    for src,dst in [('Jahra Dark Store Stock','j'),('Qurtuba Dark Store Stock','q'),
        ('Sabah Salem Dark Store Stock','ss'),('Total SOH','total'),('Fresh/Non Fresh','fresh_type')]:
        if src in inv.columns: rn[src]=dst
    for src,dst in [(j7d,'j7d'),(q7d,'q7d'),(ss7d,'ss7d'),(jmay,'jmay'),(qmay,'qmay'),(ssmay,'ssmay')]:
        if src and src in inv.columns: rn[src]=dst
    inv=inv.rename(columns=rn)
    for c in ['j','q','ss','total','j7d','q7d','ss7d','jmay','qmay','ssmay','Net Unit Cost']:
        if c not in inv.columns: inv[c]=0
        inv[c]=pd.to_numeric(inv[c],errors='coerce').fillna(0)
    inv['ytd']=inv['jmay']+inv['qmay']+inv['ssmay']
    inv['jytd']=inv['jmay']; inv['qytd']=inv['qmay']; inv['ssytd']=inv['ssmay']
    inv['Sub Category']=inv['Sub Category'].fillna('Unknown').str.strip() if 'Sub Category' in inv.columns else 'Unknown'
    inv['Category']=inv['Category'].fillna('Unknown').str.strip() if 'Category' in inv.columns else 'Unknown'
    inv['Category']=inv['Category'].replace({'WATER':'Water','BABY':'Baby','BAKERY':'Bakery',
        'MEATS':'Meats','SNACKS':'Snacks','PHARMA':'Pharma','STATIONARY':'Stationary'})
    inv['rt']=np.where(inv['Category'].isin(PRODUCE_CATS),'PRODUCE',
               np.where(inv['fresh_type']=='FRESH','FRESH','NON-FRESH'))
    STORE_SOH={'Jahra':'j','Qurtuba':'q','Sabah Salem':'ss'}
    STORE_YTD={'Jahra':'jytd','Qurtuba':'qytd','Sabah Salem':'ssytd'}
    results={}
    for (cat,subcat),sub_df in inv.groupby(['Category','Sub Category']):
        ytd=int(sub_df['ytd'].sum()); ts=len(sub_df); ot=int((sub_df['total']==0).sum())
        jc=bool((sub_df['j']>0).any()); qc=bool((sub_df['q']>0).any()); sc=bool((sub_df['ss']>0).any())
        sv=sum([jc,qc,sc]); rt=sub_df['rt'].mode().iloc[0]
        store_data={}
        for store in ['Jahra','Qurtuba','Sabah Salem']:
            col=STORE_SOH[store]; ycol=STORE_YTD[store]; sty=int(sub_df[ycol].sum())
            oos_skus=sub_df[(sub_df[col]==0)&(sub_df[ycol]>3)].sort_values(ycol,ascending=False)
            in_stock=sub_df[sub_df[col]>0].sort_values(ycol,ascending=False)
            oos_out=[]
            for _,or_ in oos_skus.head(4).iterrows():
                subs=[]
                for _,sr_ in in_stock.iterrows():
                    if sr_['Barcode']==or_['Barcode']: continue
                    st_r,lb=sub_quality(or_,sr_,cat)
                    if st_r is None: continue
                    subs.append({'desc':sr_['Description'][:45],'soh':int(sr_[col]),'strength':st_r,'label':lb})
                subs=sorted(subs,key=lambda x:['DIRECT','STRONG','WEAK'].index(x['strength']))
                oos_out.append({'desc':or_['Description'][:52],'barcode':str(or_['Barcode']),
                    'store_ytd':int(or_[ycol]),'network_ytd':int(or_['ytd']),
                    'vendor':str(or_.get('Vendor',''))[:25],'subs':subs[:2]})
            store_data[store]={'covered':bool((sub_df[col]>0).any()),'oos_count':len(oos_skus),
                'in_stock_count':len(in_stock),'store_ytd':sty,'oos_skus':oos_out,
                'in_stock_top':[{'desc':r['Description'][:45],'soh':int(r[col]),'store_ytd':int(r[ycol])}
                                for _,r in in_stock.head(3).iterrows()]}
        if sv==0 and ytd>15: sev='URGENT'
        elif sv==1 and ytd>15: sev='URGENT'
        elif sv==2 and ytd>10: sev='ACTION'
        elif sv==3:
            hv=any(any(o['store_ytd']>30 for o in store_data[st]['oos_skus']) for st in ['Jahra','Qurtuba','Sabah Salem'])
            sev='NOTE' if hv else 'OK'
        else: sev='OK'
        if sev=='OK': continue
        if cat not in results: results[cat]=[]
        results[cat].append({'subcat':subcat,'ytd':ytd,'total_skus':ts,'oos_total':ot,
            'stores_covered':sv,'severity':sev,'rt':rt,'stores':store_data})
    SEV_ORDER=['URGENT','ACTION','NOTE']
    CAT_ORDER=['Dairy & Eggs','Drinks','Confectionary','Fruits & Vegetables','Snacks','Ice Cream',
        'Bakery','Cupboard','Home Care','Personal Care','Water','Frozen Food','Baby','Meats',
        'Health & Lifestyle','Coffee, Tea & Creamer','Pets','Baking Essentials','Ready to Eat','Pharma','Stationary']
    ordered={}
    for cat in CAT_ORDER:
        if cat in results: ordered[cat]=sorted(results[cat],key=lambda x:(SEV_ORDER.index(x['severity']),-x['ytd']))
    for cat in sorted(results.keys()):
        if cat not in ordered: ordered[cat]=sorted(results[cat],key=lambda x:(SEV_ORDER.index(x['severity']),-x['ytd']))
    dm=re.search(r'(\d{2}-\d{2}-\d{4})',filename)
    return ordered, dm.group(1) if dm else 'uploaded', len(inv), filename


# ── WIDGET HTML BUILDER ──────────────────────────────────────────────────────

def build_widget_html(data, file_date, sku_count, cur_cat, cur_sub, flags):
    """Build the full widget HTML. Nav clicks post a message to Streamlit."""

    SI={'URGENT':'🔴','ACTION':'🟡','NOTE':'🔵'}
    SEVL={'URGENT':'🔴 Urgent — no adequate coverage',
          'ACTION':'🟡 Action needed — partially covered',
          'NOTE':  '🔵 Note — covered but high-velocity gaps'}
    SEVC={'URGENT':'sv-u','ACTION':'sv-a','NOTE':'sv-n'}
    RTL={'FRESH':'Fresh · supplier-direct','PRODUCE':'Produce · supplier-direct',
         'NON-FRESH':'Non-fresh · transfer eligible'}
    RTC={'FRESH':'chip-f','PRODUCE':'chip-p','NON-FRESH':'chip-n'}
    FL=['Discontinued here','Out of season','Promo ended','Discontinued']
    FK=['dl','os','pe','dc']

    # ── NAV ───────────────────────────────────────────────────────────────────
    nav_html = ''
    for cat, items in data.items():
        u=sum(1 for r in items if r['severity']=='URGENT')
        a=sum(1 for r in items if r['severity']=='ACTION')
        badges=(f'<span class="cbu">{u}U</span>' if u else '')+(f'<span class="cba">{a}A</span>' if a else '')
        nav_html += f'<div class="ch">{cat}<div class="cbs">{badges}</div></div>'
        for r in items:
            yk=f"{r['ytd']/1000:.1f}k" if r['ytd']>=1000 else str(r['ytd'])
            is_on = (cat==cur_cat and r['subcat']==cur_sub)
            flagged_n = sum(1 for st in ['Jahra','Qurtuba','Sabah Salem']
                           for oi in range(len(r['stores'].get(st,{}).get('oos_skus',[])))
                           if flags.get(f"{r['subcat']}|{st}|{oi}",{}).get('any'))
            flag_badge = f'<span class="ni-f">{flagged_n}⊘</span>' if flagged_n else ''
            # Use data attributes + onclick that posts message to parent
            cat_esc = cat.replace("'","\\'"); sub_esc = r['subcat'].replace("'","\\'")
            nav_html += f'''<div class="ni{'  on' if is_on else ''}" onclick="selectSub('{cat_esc}','{sub_esc}')">
                <div class="ni-i">{SI.get(r['severity'],'·')}</div>
                <span class="ni-l" title="{r['subcat']}">{r['subcat']}</span>
                {flag_badge}<span class="ni-y">{yk}</span>
            </div>'''

    # ── DETAIL ────────────────────────────────────────────────────────────────
    items = data.get(cur_cat, [])
    r = next((x for x in items if x['subcat']==cur_sub), None)

    if not r:
        detail_html = '<div style="padding:40px;text-align:center;color:#888">Select a sub-category</div>'
        mbar_html = '<span class="mb-t">—</span>'
    else:
        rt = r.get('rt','NON-FRESH')
        # Count effective OOS (excluding flagged)
        eff_oos = sum(
            1 for st in ['Jahra','Qurtuba','Sabah Salem']
            for oi,o in enumerate(r['stores'].get(st,{}).get('oos_skus',[]))
            if not flags.get(f"{cur_sub}|{st}|{oi}",{}).get('any')
        )
        excl = r['oos_total'] - eff_oos
        cCl='g' if r['stores_covered']==3 else ('a' if r['stores_covered']==2 else 'r')
        oCl='g' if eff_oos==0 else ('a' if eff_oos<r['total_skus']*0.3 else 'r')

        mbar_html = f'''
        <div><span class="mb-t">{cur_sub}</span>&nbsp;<span class="mb-c">· {cur_cat}</span></div>
        <span class="chip {RTC.get(rt,'chip-n')}">{RTL.get(rt,rt)}</span>
        <span class="mb-s">{r["total_skus"]} SKUs · {r["oos_total"]} OOS · {r["ytd"]:,} YTD · {file_date}</span>'''

        detail_html = f'''
        <div class="ks">
            <div class="kp"><div class="kl">Stores covered</div><div class="kv {cCl}">{r["stores_covered"]}/3</div></div>
            <div class="kp"><div class="kl">SKUs in sub-cat</div><div class="kv">{r["total_skus"]}</div></div>
            <div class="kp"><div class="kl">SKUs OOS</div><div class="kv {oCl}">{eff_oos}</div></div>
            <div class="kp"><div class="kl">Network YTD</div><div class="kv">{r["ytd"]:,}</div></div>
        </div>'''
        if excl:
            detail_html += f'<div class="excl">{excl} OOS SKU{"s" if excl>1 else ""} excluded — flagged as contextual</div>'
        detail_html += f'<div class="sv {SEVC[r["severity"]]}">{SEVL[r["severity"]]}</div><div class="ss">'

        for store in ['Jahra','Qurtuba','Sabah Salem']:
            si = ['Jahra','Qurtuba','Sabah Salem'].index(store)
            sd = r['stores'].get(store,{})
            hc = 'ok' if sd.get('covered') and sd.get('oos_count',0)==0 else ('pt' if sd.get('covered') else 'oo')
            bg = 'gok' if hc=='ok' else ('gpt' if hc=='pt' else 'goo')
            bt = f"{sd.get('oos_count',0)} OOS in sub-cat" if hc=='pt' else ('All in stock' if hc=='ok' else 'No coverage')
            detail_html += f'''<div class="sb">
                <div class="sh {hc}"><span class="sn">{store}</span>
                <span class="sg {bg}">{bt}</span>
                <span class="syt">YTD: {sd.get("store_ytd",0):,}</span></div>
                <div class="sbdy">'''

            if sd.get('in_stock_top'):
                detail_html += '<div class="dl">In stock</div>'
                for sk in sd['in_stock_top'][:3]:
                    detail_html += f'<div class="ik"><span style="color:var(--color-text-success,#16a34a);font-size:11px;flex-shrink:0">✓</span><span class="id" title="{sk["desc"]}">{sk["desc"]}</span><span class="im">{sk["soh"]}u · {sk["store_ytd"]} ytd</span></div>'

            if sd.get('oos_skus'):
                detail_html += '<div class="dl" style="margin-top:5px">Out of stock</div><div class="ow">'
                for oi, oos in enumerate(sd['oos_skus']):
                    fkey = f"{cur_sub}|{store}|{oi}"
                    f_state = flags.get(fkey, {})
                    flagged = f_state.get('any', False)
                    detail_html += f'<div class="ob{"  flagged" if flagged else ""}" id="ob_{si}_{oi}">'
                    detail_html += f'''<div class="oh">
                        <span style="color:#dc2626;font-size:11px;flex-shrink:0;margin-top:1px">✗</span>
                        <div class="od">{oos["desc"]}<br><span class="ov">{oos["vendor"]}</span></div>
                        <div class="oy"><b>{oos["store_ytd"]:,}</b> store<br>{oos["network_ytd"]:,} net</div>
                    </div>'''
                    detail_html += '<div class="fg">'
                    for fi, fk in enumerate(FK):
                        is_on = f_state.get(fk, False)
                        bid = f"fb_{si}_{oi}_{fk}"
                        detail_html += f'''<label onclick="toggleFlag('{fkey}','{fk}','{bid}','ob_{si}_{oi}','sv_{si}_{oi}');return false;">
                            <div class="fb{"  on" if is_on else ""}" id="{bid}">{"✓" if is_on else ""}</div>
                            <span class="fl">{FL[fi]}</span></label>'''
                    detail_html += f'<span class="fsv" id="sv_{si}_{oi}">✓ saved</span></div>'
                    detail_html += '<div class="ub"><div class="ul">Substitutes</div>'
                    if oos['subs']:
                        for sub in oos['subs']:
                            tc = 'utd' if sub['strength']=='DIRECT' else ('uts' if sub['strength']=='STRONG' else 'utw')
                            detail_html += f'<div class="ur"><span class="ut {tc}">{sub["strength"]}</span><span class="ud">{sub["desc"]} <span style="font-size:9px;color:#888">· {sub["label"]}</span></span><span class="us">{sub["soh"]}u</span></div>'
                    else:
                        detail_html += '<div class="ns">No substitute — raise PO immediately</div>'
                    detail_html += '</div></div>'
                detail_html += '</div>'
            elif sd.get('covered'):
                detail_html += '<div class="aok">✓ No high-velocity OOS at this store</div>'
            detail_html += '</div></div>'
        detail_html += '</div>'

    # ── FULL HTML ─────────────────────────────────────────────────────────────
    flags_json = json.dumps(flags)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:13px}}
.w{{display:flex;height:620px;border:1px solid #e2ddd8;border-radius:10px;overflow:hidden;background:#fff}}
.nv{{width:218px;flex-shrink:0;background:#f7f6f3;border-right:1px solid #e2ddd8;display:flex;flex-direction:column}}
.nh{{padding:10px 12px 8px;border-bottom:1px solid #e2ddd8;flex-shrink:0}}
.nh-t{{font-size:12px;font-weight:500;color:#1a1a1a}}
.nh-s{{font-size:10px;color:#888;margin-top:2px}}
.nb{{flex:1;overflow-y:auto}}
.ch{{font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:#888;padding:7px 12px 2px;border-top:1px solid #e2ddd8;background:#f7f6f3;position:sticky;top:0;z-index:2;display:flex;align-items:center;gap:3px}}
.ch:first-child{{border-top:none}}
.cbs{{display:flex;gap:3px;margin-left:auto}}
.cbu{{font-size:9px;font-weight:600;padding:1px 4px;border-radius:3px;background:#fee2e2;color:#b91c1c}}
.cba{{font-size:9px;font-weight:600;padding:1px 4px;border-radius:3px;background:#fef3c7;color:#92400e}}
.ni{{display:flex;align-items:center;padding:5px 8px 5px 0;cursor:pointer;border-left:2px solid transparent;user-select:none}}
.ni:hover{{background:#fff}}
.ni.on{{background:#fff;border-left-color:#E8622A}}
.ni-i{{width:24px;text-align:center;font-size:11px;flex-shrink:0}}
.ni-l{{flex:1;font-size:11px;color:#555;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.ni.on .ni-l{{color:#1a1a1a;font-weight:500}}
.ni-y{{font-size:9px;color:#aaa;padding-right:6px;flex-shrink:0}}
.ni-f{{font-size:9px;color:#aaa;flex-shrink:0;padding-right:3px}}
.mn{{flex:1;min-width:0;display:flex;flex-direction:column;overflow:hidden}}
.mb{{padding:8px 14px;border-bottom:1px solid #e2ddd8;display:flex;align-items:center;gap:8px;flex-wrap:wrap;flex-shrink:0}}
.mb-t{{font-size:13px;font-weight:500;color:#1a1a1a}}
.mb-c{{font-size:11px;color:#888}}
.chip{{font-size:10px;font-weight:500;padding:2px 7px;border-radius:10px}}
.chip-f{{background:#fef3c7;color:#92400e}}.chip-p{{background:#d1fae5;color:#065f46}}.chip-n{{background:#dbeafe;color:#1e40af}}
.mb-s{{font-size:10px;color:#888;margin-left:auto}}
.ct{{flex:1;overflow-y:auto;padding:12px 14px;background:#fafaf8}}
.ks{{display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap}}
.kp{{background:#fff;border:1px solid #e2ddd8;border-radius:6px;padding:5px 12px}}
.kl{{font-size:9px;color:#888;text-transform:uppercase;letter-spacing:.04em}}
.kv{{font-size:18px;font-weight:500;color:#1a1a1a;line-height:1.2}}
.kv.r{{color:#dc2626}}.kv.a{{color:#d97706}}.kv.g{{color:#16a34a}}
.sv{{padding:5px 10px;border-radius:6px;font-size:11px;font-weight:500;margin-bottom:8px}}
.sv-u{{background:#fee2e2;color:#b91c1c}}.sv-a{{background:#fef3c7;color:#92400e}}.sv-n{{background:#dbeafe;color:#1e40af}}
.excl{{font-size:10px;color:#888;font-style:italic;padding:3px 8px;background:#fff;border-radius:6px;margin-bottom:8px;border:1px solid #e2ddd8}}
.ss{{display:flex;flex-direction:column;gap:8px}}
.sb{{border:1px solid #e2ddd8;border-radius:6px;overflow:hidden}}
.sh{{padding:5px 10px;display:flex;align-items:center;gap:8px;border-bottom:1px solid #e2ddd8}}
.sh.ok{{background:#f0fdf4}}.sh.pt{{background:#fffbeb}}.sh.oo{{background:#fef2f2}}
.sn{{font-size:12px;font-weight:500;color:#1a1a1a}}
.sg{{font-size:9px;font-weight:600;padding:1px 5px;border-radius:4px}}
.gok{{background:#16a34a;color:#fff}}.gpt{{background:#d97706;color:#fff}}.goo{{background:#dc2626;color:#fff}}
.syt{{font-size:10px;color:#888;margin-left:auto}}
.sbdy{{padding:7px 10px;background:#fff}}
.dl{{font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;color:#888;margin:5px 0 2px}}
.dl:first-child{{margin-top:0}}
.ik{{display:flex;align-items:center;gap:6px;padding:2px 0;border-bottom:1px solid #f0ede9;font-size:11px}}
.ik:last-child{{border-bottom:none}}
.id{{flex:1;color:#1a1a1a;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.im{{font-size:9px;color:#888;flex-shrink:0}}
.ow{{display:flex;flex-direction:column;gap:3px;margin-top:3px}}
.ob{{border:1px solid #fca5a5;border-radius:5px;overflow:hidden;transition:opacity .2s}}
.ob.flagged{{opacity:0.32}}
.oh{{display:flex;align-items:flex-start;gap:5px;padding:5px 8px;background:#fef2f2}}
.od{{flex:1;font-size:11px;font-weight:500;color:#1a1a1a;line-height:1.35;min-width:0}}
.ov{{font-size:9px;font-weight:400;color:#888}}
.oy{{font-size:9px;color:#888;flex-shrink:0;text-align:right;line-height:1.5}}
.fg{{display:flex;gap:5px;padding:3px 8px;background:#f7f6f3;flex-wrap:wrap;align-items:center}}
.fg label{{display:flex;align-items:center;gap:3px;cursor:pointer;user-select:none}}
.fb{{width:12px;height:12px;border:1px solid #ccc;border-radius:2px;display:flex;align-items:center;justify-content:center;font-size:8px;background:#fff;flex-shrink:0;transition:all .12s}}
.fb.on{{background:#3b82f6;border-color:#3b82f6;color:#fff}}
.fl{{font-size:9px;color:#888;white-space:nowrap}}
.fsv{{font-size:9px;color:#16a34a;margin-left:auto;opacity:0;transition:opacity .25s}}
.fsv.show{{opacity:1}}
.ub{{padding:3px 8px 5px;border-top:1px dashed #e2ddd8}}
.ul{{font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;color:#888;margin-bottom:2px}}
.ur{{display:flex;align-items:flex-start;gap:4px;padding:1px 0}}
.ut{{font-size:9px;font-weight:600;padding:1px 5px;border-radius:3px;flex-shrink:0;white-space:nowrap}}
.utd{{background:#d1fae5;color:#065f46}}.uts{{background:#fef3c7;color:#92400e}}.utw{{background:#fee2e2;color:#991b1b}}
.ud{{flex:1;font-size:10.5px;color:#555;line-height:1.35;min-width:0}}
.us{{font-size:9px;color:#888;flex-shrink:0}}
.ns{{font-size:10.5px;color:#dc2626;font-style:italic;padding:2px 0}}
.aok{{font-size:10.5px;color:#16a34a;padding:2px 0}}
</style>
</head>
<body>
<div class="w">
  <nav class="nv">
    <div class="nh"><div class="nh-t">Fiz · Availability Briefing</div><div class="nh-s">{file_date} · {sku_count:,} SKUs</div></div>
    <div class="nb">{nav_html}</div>
  </nav>
  <div class="mn">
    <div class="mb">{mbar_html}</div>
    <div class="ct">{detail_html}</div>
  </div>
</div>

<script>
var FLAGS = {flags_json};
window._fiz_flags = FLAGS;

function selectSub(cat, sub) {{
  if (window._fiz_setStateValue) {{
    window._fiz_setStateValue('selection', {{cat: cat, sub: sub}});
  }}
}}

function toggleFlag(fkey, fk, bid, oid, sid) {{
  if (!FLAGS[fkey]) FLAGS[fkey] = {{dl:0,os:0,pe:0,dc:0,any:false}};
  FLAGS[fkey][fk] = FLAGS[fkey][fk] ? 0 : 1;
  FLAGS[fkey].any = !!(FLAGS[fkey].dl||FLAGS[fkey].os||FLAGS[fkey].pe||FLAGS[fkey].dc);
  var b=document.getElementById(bid);
  if(b){{b.className='fb'+(FLAGS[fkey][fk]?' on':'');b.textContent=FLAGS[fkey][fk]?'✓':'';}}
  var bl=document.getElementById(oid);
  if(bl){{bl.className='ob'+(FLAGS[fkey].any?' flagged':'');}}
  var sv=document.getElementById(sid);
  if(sv){{sv.className='fsv show';setTimeout(function(){{sv.className='fsv';}},1600);}}
  window._fiz_flags = FLAGS;
  if (window._fiz_setStateValue) {{
    window._fiz_setStateValue('flags', FLAGS);
  }}
}}
</script>
</body>
</html>"""


# ── MAIN APP ──────────────────────────────────────────────────────────────────

st.markdown("""
<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
  <div style="width:36px;height:36px;background:#E8622A;border-radius:8px;
              display:flex;align-items:center;justify-content:center;font-size:20px">📦</div>
  <div>
    <div style="font-size:20px;font-weight:600;color:#1a1a1a">Fiz · Availability Briefing</div>
    <div style="font-size:12px;color:#888">Upload the Master_LIst inventory file</div>
  </div>
</div>
""", unsafe_allow_html=True)

uploaded = st.file_uploader('Upload inventory file', type=['xlsx'], label_visibility='collapsed')

if uploaded is None:
    st.markdown("""
    <div style="background:#f7f6f3;border:1px dashed #d0ccc8;border-radius:8px;
                padding:40px;text-align:center;color:#888;margin-top:16px">
        <div style="font-size:32px;margin-bottom:12px">📂</div>
        <div style="font-size:14px;font-weight:500;color:#555;margin-bottom:6px">Upload your inventory file to get started</div>
        <div style="font-size:12px">Accepts Master_LIst_-_DD-MM-YYYY.xlsx · Analysis runs automatically</div>
    </div>""", unsafe_allow_html=True)
    st.stop()

with st.spinner('Analysing inventory file…'):
    try:
        data, file_date, sku_count, filename = load_and_analyse(uploaded.read(), uploaded.name)
    except Exception as e:
        st.error(f'Error: {e}'); st.exception(e); st.stop()

# Session state
if 'cur_cat' not in st.session_state or st.session_state.cur_cat not in data:
    st.session_state.cur_cat = next(iter(data))
    st.session_state.cur_sub = data[st.session_state.cur_cat][0]['subcat']
if 'flags' not in st.session_state:
    st.session_state.flags = {}

# Summary metrics
total_u=sum(sum(1 for r in v if r['severity']=='URGENT') for v in data.values())
total_a=sum(sum(1 for r in v if r['severity']=='ACTION') for v in data.values())
total_n=sum(sum(1 for r in v if r['severity']=='NOTE') for v in data.values())
c1,c2,c3,c4,c5=st.columns(5)
c1.metric('File date',file_date); c2.metric('Active SKUs',f'{sku_count:,}')
c3.metric('🔴 Urgent',total_u); c4.metric('🟡 Action',total_a); c5.metric('🔵 Note',total_n)

# ── REGISTER V2 COMPONENT (once at module level) ─────────────────────────────
_BRIEFING_COMPONENT = st.components.v2.component(
    "fiz_briefing_widget",
    html="<div id='root'></div>",
    js="""
export default function(component) {
  const { data, parentElement, setStateValue } = component;
  if (!data || !data.html) return;

  const root = parentElement.querySelector('#root');
  if (!root) return;

  // Inject the widget HTML
  root.style.cssText = 'height:640px;overflow:hidden;';
  root.innerHTML = data.html;

  // Execute any inline scripts
  root.querySelectorAll('script').forEach(function(oldScript) {
    const newScript = document.createElement('script');
    newScript.textContent = oldScript.textContent;
    oldScript.parentNode.replaceChild(newScript, oldScript);
  });

  // Wire all onclick elements to pass setStateValue into scope
  root.querySelectorAll('[onclick]').forEach(function(el) {
    const orig = el.getAttribute('onclick');
    el.removeAttribute('onclick');
    el.addEventListener('click', function(e) {
      e.stopPropagation();
      // Make setStateValue available to the onclick functions
      const fn = new Function('setStateValue', 'FLAGS', orig);
      try {
        const FLAGS = window._fiz_flags || {};
        fn(setStateValue, FLAGS);
      } catch(err) { console.warn('click err', err); }
    });
  });

  // Store flags reference for toggleFlag calls
  window._fiz_setStateValue = setStateValue;
  window._fiz_flags = data.flags || {};
}
""",
    isolate_styles=False,
)

# Build and render widget
widget_html = build_widget_html(
    data, file_date, sku_count,
    st.session_state.cur_cat,
    st.session_state.cur_sub,
    st.session_state.flags,
)

result = _BRIEFING_COMPONENT(
    key="briefing",
    data={"html": widget_html, "flags": st.session_state.flags},
    on_selection_change=lambda: None,
    on_flags_change=lambda: None,
)

# Handle result
if result is not None:
    selection = result.get("selection")
    new_flags  = result.get("flags")
    changed = False
    if selection and isinstance(selection, dict):
        new_cat = selection.get("cat"); new_sub = selection.get("sub")
        if new_cat and new_sub and (new_cat != st.session_state.cur_cat or new_sub != st.session_state.cur_sub):
            st.session_state.cur_cat = new_cat
            st.session_state.cur_sub = new_sub
            changed = True
    if new_flags and new_flags != st.session_state.flags:
        st.session_state.flags = new_flags
        changed = True
    if changed:
        st.rerun()
