"""
Fiz Availability Briefing
Upload the Master_LIst inventory file → instant availability briefing widget.

Rules embedded:
- FRESH SKUs → always supplier-direct to store (never transfer)
- PRODUCE (Fruits & Vegetables) → supplier-direct, seasonal
- NON-FRESH → transfer eligible
- Rawdatain = premium local mineral water — Arwa/Abraaj are VALUE tier, different customer
- Water: 200ml/330ml convenience formats cannot substitute 1L+ household formats
- Substitute quality: DIRECT / STRONG / WEAK based on brand tier, format, price
"""

import streamlit as st
import pandas as pd
import numpy as np
import io
import re

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
.brief-shell {
    display: flex; height: 640px;
    border: 1px solid #e2ddd8; border-radius: 10px;
    overflow: hidden;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #fff;
}
.brief-nav {
    width: 220px; flex-shrink: 0; background: #f7f6f3;
    border-right: 1px solid #e2ddd8;
    display: flex; flex-direction: column; overflow: hidden;
}
.nav-head { padding: 10px 12px 8px; border-bottom: 1px solid #e2ddd8; flex-shrink: 0; }
.nav-head-title { font-size: 12px; font-weight: 500; color: #1a1a1a; }
.nav-head-sub { font-size: 10px; color: #888; margin-top: 2px; }
.nav-scroll { flex: 1; overflow-y: auto; }
.cat-hdr {
    font-size: 9px; font-weight: 600; text-transform: uppercase;
    letter-spacing: .08em; color: #888;
    padding: 7px 12px 2px; border-top: 1px solid #e2ddd8;
    background: #f7f6f3; display: flex; align-items: center;
}
.cat-hdr:first-child { border-top: none; }
.cat-badges { display: flex; gap: 3px; margin-left: auto; }
.cb-u { font-size: 9px; font-weight: 600; padding: 1px 4px; border-radius: 3px; background: #fee2e2; color: #b91c1c; }
.cb-a { font-size: 9px; font-weight: 600; padding: 1px 4px; border-radius: 3px; background: #fef3c7; color: #92400e; }
.ni { display: flex; align-items: center; padding: 5px 8px 5px 0; cursor: pointer; border-left: 2px solid transparent; }
.ni:hover { background: #fff; }
.ni.on { background: #fff; border-left-color: #E8622A; }
.ni-i { width: 24px; text-align: center; font-size: 11px; flex-shrink: 0; }
.ni-l { flex: 1; font-size: 11px; color: #555; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ni.on .ni-l { color: #1a1a1a; font-weight: 500; }
.ni-y { font-size: 9px; color: #aaa; padding-right: 6px; flex-shrink: 0; }
.brief-main { flex: 1; min-width: 0; display: flex; flex-direction: column; overflow: hidden; }
.mbar { padding: 9px 14px; border-bottom: 1px solid #e2ddd8; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; flex-shrink: 0; }
.mbar-t { font-size: 13px; font-weight: 500; color: #1a1a1a; }
.mbar-c { font-size: 11px; color: #888; }
.chip { font-size: 10px; font-weight: 500; padding: 2px 7px; border-radius: 10px; }
.chip-f { background: #fef3c7; color: #92400e; }
.chip-p { background: #d1fae5; color: #065f46; }
.chip-n { background: #dbeafe; color: #1e40af; }
.mbar-s { font-size: 10px; color: #888; margin-left: auto; }
.mcontent { flex: 1; overflow-y: auto; padding: 12px 14px; background: #fafaf8; }
.kpis { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.kpi { background: #fff; border: 1px solid #e2ddd8; border-radius: 6px; padding: 6px 12px; }
.kpi-l { font-size: 9px; color: #888; text-transform: uppercase; letter-spacing: .05em; }
.kpi-v { font-size: 19px; font-weight: 500; color: #1a1a1a; line-height: 1.2; }
.kpi-v.r { color: #dc2626; } .kpi-v.a { color: #d97706; } .kpi-v.g { color: #16a34a; }
.sev { padding: 5px 10px; border-radius: 6px; font-size: 11px; font-weight: 500; margin-bottom: 10px; }
.sev-u { background: #fee2e2; color: #b91c1c; }
.sev-a { background: #fef3c7; color: #92400e; }
.sev-n { background: #dbeafe; color: #1e40af; }
.stores { display: flex; flex-direction: column; gap: 8px; }
.sblk { border: 1px solid #e2ddd8; border-radius: 6px; overflow: hidden; }
.shdr { padding: 6px 10px; display: flex; align-items: center; gap: 8px; border-bottom: 1px solid #e2ddd8; }
.shdr.ok { background: #f0fdf4; } .shdr.pt { background: #fffbeb; } .shdr.oo { background: #fef2f2; }
.sname { font-size: 12px; font-weight: 500; color: #1a1a1a; }
.sbdg { font-size: 9px; font-weight: 600; padding: 1px 6px; border-radius: 4px; }
.bOk { background: #16a34a; color: #fff; } .bPt { background: #d97706; color: #fff; } .bOo { background: #dc2626; color: #fff; }
.sytd { font-size: 10px; color: #888; margin-left: auto; }
.sbdy { padding: 8px 10px; background: #fff; }
.dl { font-size: 9px; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; color: #888; margin: 6px 0 3px; }
.dl:first-child { margin-top: 0; }
.ik { display: flex; align-items: center; gap: 6px; padding: 3px 0; border-bottom: 1px solid #f0ede9; font-size: 11.5px; }
.ik:last-child { border-bottom: none; }
.ik-d { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #1a1a1a; }
.ik-m { font-size: 9px; color: #888; flex-shrink: 0; text-align: right; }
.oosw { display: flex; flex-direction: column; gap: 4px; margin-top: 2px; }
.oosb { border: 1px solid #fca5a5; border-radius: 5px; overflow: hidden; }
.oosh { display: flex; align-items: flex-start; gap: 6px; padding: 6px 8px; background: #fef2f2; }
.oosd { flex: 1; font-size: 11px; font-weight: 500; color: #1a1a1a; line-height: 1.4; min-width: 0; }
.oosy { font-size: 10px; color: #888; flex-shrink: 0; text-align: right; line-height: 1.5; }
.flags { display: flex; gap: 8px; padding: 4px 8px; background: #f7f6f3; flex-wrap: wrap; }
.flag-lbl { font-size: 10px; color: #888; }
.subs { padding: 4px 8px 6px; border-top: 1px dashed #e2ddd8; }
.subs-l { font-size: 9px; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; color: #888; margin-bottom: 3px; }
.subr { display: flex; align-items: flex-start; gap: 5px; padding: 2px 0; }
.stag { font-size: 9px; font-weight: 600; padding: 1px 5px; border-radius: 3px; flex-shrink: 0; margin-top: 1px; white-space: nowrap; }
.st-d { background: #d1fae5; color: #065f46; }
.st-s { background: #fef3c7; color: #92400e; }
.st-w { background: #fee2e2; color: #991b1b; }
.subd { flex: 1; font-size: 11px; color: #555; line-height: 1.4; min-width: 0; }
.subs-soh { font-size: 10px; color: #888; flex-shrink: 0; }
.no-sub { font-size: 11px; color: #dc2626; font-style: italic; padding: 2px 0; }
.all-ok { font-size: 11px; color: #16a34a; padding: 3px 0; }
</style>
""", unsafe_allow_html=True)


# ── ANALYSIS ENGINE ────────────────────────────────────────────────────────────

PRODUCE_CATS = ['Fruits & Vegetables']

BRAND_TIERS = {
    'rawdatain': 'PREMIUM_LOCAL',
    'evian': 'PREMIUM_INTL', 'volvic': 'PREMIUM_INTL',
    'san pellegrino': 'PREMIUM_INTL', 'perrier': 'PREMIUM_INTL',
    'fiji': 'PREMIUM_INTL',
    'masafi': 'MID',
    'arwa': 'VALUE', 'abraaj': 'VALUE', 'aquagulf': 'VALUE',
}

FLAVOUR_KW = {
    'mint','strawberry','chocolate','mango','vanilla','lemon','orange',
    'banana','peach','blueberry','raspberry','caramel','mocha','cherry',
    'apple','watermelon','grape','lime','coconut','passion','hazelnut',
    'coffee','honey','cinnamon','rose','saffron','tropical',
}
VARIANT_KW = {
    'zero','diet','light','sugar free','no sugar','low fat','full fat',
    'skimmed','semi skimmed','fat free','reduced fat','unsalted','salted',
    'whole','wholegrain','wholemeal',
}

def get_flavour(d):
    d = d.lower(); return {f for f in FLAVOUR_KW if f in d}

def get_variant(d):
    d = d.lower(); return {v for v in VARIANT_KW if v in d}

def is_organic(d):
    return any(k in d.lower() for k in ['organic','natureland','bonato','earth organic'])

def sub_quality(oos_row, sub_row, cat_name):
    ood = str(oos_row.get('Description','')); sud = str(sub_row.get('Description',''))
    oos_p = float(oos_row.get('Net Unit Cost', 0) or 0)
    sub_p = float(sub_row.get('Net Unit Cost', 0) or 0)
    oos_v = str(oos_row.get('Vendor','')); sub_v = str(sub_row.get('Vendor',''))
    ratio = sub_p / oos_p if oos_p > 0.01 else 1.0
    price_weak      = 5.0 if cat_name == 'Water' else 3.0
    price_strong_cap = 4.0 if cat_name == 'Water' else 1.8

    # 1. Organic mismatch — check first (organic/mainstream is a customer type split)
    oos_org = is_organic(ood); sub_org = is_organic(sud)
    if oos_org != sub_org:
        return 'STRONG', 'Strong — organic vs mainstream, functional substitute but different positioning'

    # 2. Price ratio — fires after organic check
    if ratio > price_weak:
        return 'WEAK', f'Weak — {ratio:.1f}x price difference, customer won\'t trade up'
    if ratio < (1 / price_weak):
        return 'WEAK', f'Weak — sub is {(1/ratio):.1f}x cheaper, likely inferior quality perception'

    # 3. Flavour / variant mismatch — global
    oos_fl = get_flavour(ood); sub_fl = get_flavour(sud)
    oos_vr = get_variant(ood); sub_vr = get_variant(sud)
    flavour_cap = False
    if oos_fl and sub_fl and oos_fl != sub_fl:
        return 'WEAK', f'Weak — different flavour ({", ".join(sorted(oos_fl))} vs {", ".join(sorted(sub_fl))})'
    if (oos_fl and not sub_fl) or (not oos_fl and sub_fl): flavour_cap = True
    if oos_vr != sub_vr: flavour_cap = True  # zero vs regular, salted vs unsalted, etc.

    # 4. Water tier logic
    if cat_name == 'Water':
        oot = brand_tier(oos_v, ood); sut = brand_tier(sub_v, sud)
        oos_sz = get_size(ood); sub_sz = get_size(sud)
        if oos_sz in {'200ml','330ml','250ml'} and sub_sz in {'500ml','750ml','1l','1.5l','2l'}:
            return None, None
        tier_map = {
            ('PREMIUM_LOCAL','PREMIUM_LOCAL'):'DIRECT',('PREMIUM_INTL','PREMIUM_INTL'):'DIRECT',
            ('PREMIUM_LOCAL','PREMIUM_INTL'):'STRONG',('PREMIUM_INTL','PREMIUM_LOCAL'):'STRONG',
            ('MID','MID'):'DIRECT',('VALUE','VALUE'):'DIRECT',
        }
        tr = tier_map.get((oot, sut), 'WEAK')
        if tr == 'WEAK': return 'WEAK', f'Weak — {oot} vs {sut} tier, different customer'
        if ratio > price_strong_cap or (oos_sz != sub_sz and oos_sz != 'other'): tr = 'STRONG'
        if flavour_cap and tr == 'DIRECT': tr = 'STRONG'
        return tr, {'DIRECT':'Direct — same tier & format','STRONG':'Strong — comparable tier'}.get(tr,'Weak')

    # 5. General
    if ratio > price_strong_cap:  result, label = 'STRONG', f'Strong — similar use case, {ratio:.1f}x price'
    elif ratio > 1.4:             result, label = 'STRONG', f'Strong — comparable, {ratio:.1f}x price'
    else:                         result, label = 'DIRECT', 'Direct — comparable brand & price'
    if flavour_cap and result == 'DIRECT':
        result, label = 'STRONG', 'Strong — same category but different flavour/variant, not a direct replacement'
    return result, label


@st.cache_data(show_spinner=False)
def load_and_analyse(file_bytes, filename):
    inv = pd.read_excel(io.BytesIO(file_bytes))
    inv.columns = [c.strip() for c in inv.columns]
    inv = inv[inv['Status'] == 'Active'].copy()
    inv['Barcode'] = inv['Barcode'].astype(str).str.strip()

    cols = list(inv.columns)

    # Detect velocity columns
    j7d_col  = detect_sold_col(cols, 'Jahra', 'June') or detect_sold_col(cols, 'Jahra', 'Jun')
    q7d_col  = detect_sold_col(cols, 'Qurtuba', 'June') or detect_sold_col(cols, 'Qurtuba', 'Jun')
    ss7d_col = detect_sold_col(cols, 'Sabah Salem', 'June') or detect_sold_col(cols, 'Sabah Salem', 'Jun')
    jmay_col  = detect_sold_col(cols, 'Jahra', 'May')
    qmay_col  = detect_sold_col(cols, 'Qurtuba', 'May')
    ssmay_col = detect_sold_col(cols, 'Sabah Salem', 'May')

    # Build rename map — only rename what exists
    rename = {}
    for src, dst in [
        ('Jahra Dark Store Stock', 'j'),
        ('Qurtuba Dark Store Stock', 'q'),
        ('Sabah Salem Dark Store Stock', 'ss'),
        ('Ardiya - Distribution Center Stock', 'ar'),
        ('Total SOH', 'total'),
        ('Fresh/Non Fresh', 'fresh_type'),
    ]:
        if src in inv.columns:
            rename[src] = dst
    for src, dst in [
        (j7d_col, 'j7d'), (q7d_col, 'q7d'), (ss7d_col, 'ss7d'),
        (jmay_col, 'jmay'), (qmay_col, 'qmay'), (ssmay_col, 'ssmay'),
    ]:
        if src and src in inv.columns:
            rename[src] = dst
    inv = inv.rename(columns=rename)

    for c in ['j', 'q', 'ss', 'ar', 'total', 'j7d', 'q7d', 'ss7d',
              'jmay', 'qmay', 'ssmay', 'Net Unit Cost']:
        if c not in inv.columns:
            inv[c] = 0
        inv[c] = pd.to_numeric(inv[c], errors='coerce').fillna(0)

    inv['ytd']  = inv['jmay'] + inv['qmay'] + inv['ssmay']
    inv['jytd'] = inv['jmay']
    inv['qytd'] = inv['qmay']
    inv['ssytd'] = inv['ssmay']
    inv['Sub Category'] = inv['Sub Category'].fillna('Unknown').str.strip() if 'Sub Category' in inv.columns else 'Unknown'
    inv['Category']     = inv['Category'].fillna('Unknown').str.strip() if 'Category' in inv.columns else 'Unknown'

    CAT_MERGE = {
        'WATER': 'Water', 'BABY': 'Baby', 'BAKERY': 'Bakery',
        'MEATS': 'Meats', 'SNACKS': 'Snacks', 'PHARMA': 'Pharma',
        'STATIONARY': 'Stationary',
    }
    inv['Category'] = inv['Category'].replace(CAT_MERGE)

    inv['rt'] = np.where(
        inv['Category'].isin(PRODUCE_CATS), 'PRODUCE',
        np.where(inv['fresh_type'] == 'FRESH', 'FRESH', 'NON-FRESH')
    )

    STORE_SOH = {'Jahra': 'j',    'Qurtuba': 'q',    'Sabah Salem': 'ss'}
    STORE_YTD = {'Jahra': 'jytd', 'Qurtuba': 'qytd', 'Sabah Salem': 'ssytd'}

    results = {}

    for (cat, subcat), sub_df in inv.groupby(['Category', 'Sub Category']):
        ytd_total  = int(sub_df['ytd'].sum())
        total_skus = len(sub_df)
        oos_total  = int((sub_df['total'] == 0).sum())
        j_cov  = bool((sub_df['j'] > 0).any())
        q_cov  = bool((sub_df['q'] > 0).any())
        ss_cov = bool((sub_df['ss'] > 0).any())
        sv = sum([j_cov, q_cov, ss_cov])
        rt = sub_df['rt'].mode().iloc[0] if len(sub_df) > 0 else 'NON-FRESH'

        store_data = {}
        for store in ['Jahra', 'Qurtuba', 'Sabah Salem']:
            col  = STORE_SOH[store]
            ycol = STORE_YTD[store]
            sty  = int(sub_df[ycol].sum())
            oos_skus = sub_df[(sub_df[col] == 0) & (sub_df[ycol] > 3)].sort_values(ycol, ascending=False)
            in_stock  = sub_df[sub_df[col] > 0].sort_values(ycol, ascending=False)

            oos_out = []
            for _, oos_row in oos_skus.head(4).iterrows():
                subs = []
                for _, sub_row in in_stock.iterrows():
                    if sub_row['Barcode'] == oos_row['Barcode']:
                        continue
                    strength, label = sub_quality(oos_row, sub_row, cat)
                    if strength is None:
                        continue
                    subs.append({
                        'desc':     sub_row['Description'][:45],
                        'soh':      int(sub_row[col]),
                        'strength': strength,
                        'label':    label,
                    })
                subs = sorted(subs, key=lambda x: ['DIRECT', 'STRONG', 'WEAK'].index(x['strength']))
                oos_out.append({
                    'desc':        oos_row['Description'][:52],
                    'barcode':     str(oos_row['Barcode']),
                    'store_ytd':   int(oos_row[ycol]),
                    'network_ytd': int(oos_row['ytd']),
                    'vendor':      str(oos_row.get('Vendor', ''))[:25],
                    'subs':        subs[:2],
                })

            store_data[store] = {
                'covered':       bool((sub_df[col] > 0).any()),
                'oos_count':     len(oos_skus),
                'in_stock_count': len(in_stock),
                'store_ytd':     sty,
                'oos_skus':      oos_out,
                'in_stock_top':  [
                    {'desc': r['Description'][:45], 'soh': int(r[col]), 'store_ytd': int(r[ycol])}
                    for _, r in in_stock.head(3).iterrows()
                ],
            }

        if sv == 0 and ytd_total > 15:      sev = 'URGENT'
        elif sv == 1 and ytd_total > 15:    sev = 'URGENT'
        elif sv == 2 and ytd_total > 10:    sev = 'ACTION'
        elif sv == 3:
            hv = any(
                any(o['store_ytd'] > 30 for o in store_data[st]['oos_skus'])
                for st in ['Jahra', 'Qurtuba', 'Sabah Salem']
            )
            sev = 'NOTE' if hv else 'OK'
        else:
            sev = 'OK'

        if sev == 'OK':
            continue

        if cat not in results:
            results[cat] = []
        results[cat].append({
            'subcat': subcat, 'ytd': ytd_total, 'total_skus': total_skus,
            'oos_total': oos_total, 'stores_covered': sv,
            'severity': sev, 'rt': rt,
            'j_cov': j_cov, 'q_cov': q_cov, 'ss_cov': ss_cov,
            'stores': store_data,
        })

    SEV_ORDER = ['URGENT', 'ACTION', 'NOTE']
    CAT_ORDER = [
        'Dairy & Eggs', 'Drinks', 'Confectionary', 'Fruits & Vegetables',
        'Snacks', 'Ice Cream', 'Bakery', 'Cupboard', 'Home Care', 'Personal Care',
        'Water', 'Frozen Food', 'Baby', 'Meats', 'Health & Lifestyle',
        'Coffee, Tea & Creamer', 'Pets', 'Baking Essentials', 'Ready to Eat',
        'Pharma', 'Stationary',
    ]
    ordered = {}
    for cat in CAT_ORDER:
        if cat in results:
            ordered[cat] = sorted(results[cat],
                                  key=lambda x: (SEV_ORDER.index(x['severity']), -x['ytd']))
    for cat in sorted(results.keys()):
        if cat not in ordered:
            ordered[cat] = sorted(results[cat],
                                  key=lambda x: (SEV_ORDER.index(x['severity']), -x['ytd']))

    date_match = re.search(r'(\d{2}-\d{2}-\d{4})', filename)
    file_date  = date_match.group(1) if date_match else 'uploaded'

    return ordered, file_date, len(inv), filename


# ── WIDGET RENDERER ────────────────────────────────────────────────────────────

SEV_ICON  = {'URGENT': '🔴', 'ACTION': '🟡', 'NOTE': '🔵'}
SEV_LABEL = {
    'URGENT': '🔴 Urgent — no adequate coverage',
    'ACTION': '🟡 Action needed — partially covered',
    'NOTE':   '🔵 Note — covered but high-velocity gaps within sub-category',
}
RT_CHIP  = {'FRESH': 'chip-f', 'PRODUCE': 'chip-p', 'NON-FRESH': 'chip-n'}
RT_LABEL = {
    'FRESH':     'Fresh · supplier-direct',
    'PRODUCE':   'Produce · supplier-direct',
    'NON-FRESH': 'Non-fresh · transfer eligible',
}


def build_nav_html(data, cur_cat, cur_sub, file_date, sku_count):
    html = f'''
    <div class="nav-head">
        <div class="nav-head-title">Availability briefing</div>
        <div class="nav-head-sub">{file_date} · {sku_count:,} SKUs</div>
    </div>
    <div class="nav-scroll">'''
    for cat, items in data.items():
        u = sum(1 for r in items if r['severity'] == 'URGENT')
        a = sum(1 for r in items if r['severity'] == 'ACTION')
        badges = ''
        if u: badges += f'<span class="cb-u">{u}U</span>'
        if a: badges += f'<span class="cb-a">{a}A</span>'
        html += f'<div class="cat-hdr">{cat}<div class="cat-badges">{badges}</div></div>'
        for r in items:
            yk = f"{r['ytd']/1000:.1f}k" if r['ytd'] >= 1000 else str(r['ytd'])
            on = ' on' if (cat == cur_cat and r['subcat'] == cur_sub) else ''
            html += f'''<div class="ni{on}">
                <div class="ni-i">{SEV_ICON.get(r["severity"],"·")}</div>
                <span class="ni-l" title="{r["subcat"]}">{r["subcat"]}</span>
                <span class="ni-y">{yk}</span>
            </div>'''
    html += '</div>'
    return html


def build_detail_html(r, file_date):
    if not r:
        return '', '<div style="padding:40px;text-align:center;color:#888">Select a sub-category</div>'

    rt    = r.get('rt', 'NON-FRESH')
    cov_c = 'g' if r['stores_covered'] == 3 else ('a' if r['stores_covered'] == 2 else 'r')
    oos_c = 'g' if r['oos_total'] == 0 else ('a' if r['oos_total'] < r['total_skus'] * 0.3 else 'r')
    sev_c = 'u' if r['severity'] == 'URGENT' else ('a' if r['severity'] == 'ACTION' else 'n')

    mbar = f'''
    <div><span class="mbar-t">{r["subcat"]}</span>&nbsp;
         <span class="mbar-c">· {r.get("_cat","")}</span></div>
    <span class="chip {RT_CHIP.get(rt,"chip-n")}">{RT_LABEL.get(rt,rt)}</span>
    <span class="mbar-s">{r["total_skus"]} SKUs · {r["oos_total"]} OOS · {r["ytd"]:,} YTD · {file_date}</span>
    '''

    detail = f'''
    <div class="kpis">
        <div class="kpi"><div class="kpi-l">Stores covered</div><div class="kpi-v {cov_c}">{r["stores_covered"]}/3</div></div>
        <div class="kpi"><div class="kpi-l">SKUs in sub-cat</div><div class="kpi-v">{r["total_skus"]}</div></div>
        <div class="kpi"><div class="kpi-l">SKUs OOS</div><div class="kpi-v {oos_c}">{r["oos_total"]}</div></div>
        <div class="kpi"><div class="kpi-l">Network YTD</div><div class="kpi-v">{r["ytd"]:,}</div></div>
    </div>
    <div class="sev sev-{sev_c}">{SEV_LABEL.get(r["severity"],"")}</div>
    <div class="stores">'''

    for store in ['Jahra', 'Qurtuba', 'Sabah Salem']:
        sd  = r['stores'].get(store, {})
        hc  = 'ok' if sd.get('covered') and sd.get('oos_count', 0) == 0 else \
              ('pt' if sd.get('covered') else 'oo')
        bc  = 'bOk' if hc == 'ok' else ('bPt' if hc == 'pt' else 'bOo')
        bt  = f"{sd.get('oos_count',0)} OOS within sub-cat" if hc == 'pt' else \
              ('All in stock' if hc == 'ok' else 'No coverage')

        detail += f'''
        <div class="sblk">
          <div class="shdr {hc}">
            <span class="sname">{store}</span>
            <span class="sbdg {bc}">{bt}</span>
            <span class="sytd">Store YTD: {sd.get("store_ytd",0):,}</span>
          </div>
          <div class="sbdy">'''

        if sd.get('in_stock_top'):
            detail += '<div class="dl">In stock</div>'
            for sk in sd['in_stock_top'][:3]:
                detail += f'''
                <div class="ik">
                  <span style="color:#16a34a;font-size:12px;flex-shrink:0">✓</span>
                  <span class="ik-d" title="{sk["desc"]}">{sk["desc"]}</span>
                  <span class="ik-m">{sk["soh"]}u · {sk["store_ytd"]} ytd</span>
                </div>'''

        if sd.get('oos_skus'):
            detail += '<div class="dl" style="margin-top:6px">Out of stock</div><div class="oosw">'
            for oos in sd['oos_skus']:
                detail += f'''
                <div class="oosb">
                  <div class="oosh">
                    <span style="color:#dc2626;font-size:12px;margin-top:1px;flex-shrink:0">✗</span>
                    <div class="oosd">{oos["desc"]}<br>
                      <span style="font-size:10px;font-weight:400;color:#888">{oos["vendor"]}</span>
                    </div>
                    <div class="oosy"><b>{oos["store_ytd"]:,}</b> store ytd<br>{oos["network_ytd"]:,} net</div>
                  </div>
                  <div class="flags">
                    <span class="flag-lbl">☐ Discontinued here</span>
                    <span class="flag-lbl">☐ Out of season</span>
                    <span class="flag-lbl">☐ Promo ended</span>
                    <span class="flag-lbl">☐ Discontinued</span>
                  </div>
                  <div class="subs">
                    <div class="subs-l">Substitutes</div>'''
                if oos['subs']:
                    for s in oos['subs']:
                        tc = 'st-d' if s['strength'] == 'DIRECT' else \
                             ('st-s' if s['strength'] == 'STRONG' else 'st-w')
                        detail += f'''
                        <div class="subr">
                          <span class="stag {tc}">{s["strength"]}</span>
                          <span class="subd">{s["desc"]}
                            <span style="color:#888;font-size:10px"> · {s["label"]}</span>
                          </span>
                          <span class="subs-soh">{s["soh"]}u</span>
                        </div>'''
                else:
                    detail += '<div class="no-sub">No substitute — raise PO immediately</div>'
                detail += '</div></div>'
            detail += '</div>'
        elif sd.get('covered'):
            detail += '<div class="all-ok">✓ No high-velocity OOS at this store</div>'

        detail += '</div></div>'

    detail += '</div>'
    return mbar, detail


def render_widget(data, file_date, sku_count):
    # Session state
    if 'cur_cat' not in st.session_state or st.session_state.cur_cat not in data:
        st.session_state.cur_cat = next(iter(data))
        st.session_state.cur_sub = data[st.session_state.cur_cat][0]['subcat']

    cur_cat = st.session_state.cur_cat
    cur_sub = st.session_state.cur_sub

    # Find current record
    items = data.get(cur_cat, [])
    r = next((x for x in items if x['subcat'] == cur_sub), None)
    if r:
        r = dict(r)
        r['_cat'] = cur_cat

    # Build HTML
    nav_html    = build_nav_html(data, cur_cat, cur_sub, file_date, sku_count)
    mbar_html, detail_html = build_detail_html(r, file_date)

    widget = f'''
    <div class="brief-shell">
      <nav class="brief-nav">{nav_html}</nav>
      <div class="brief-main">
        <div class="mbar">{mbar_html}</div>
        <div class="mcontent">{detail_html}</div>
      </div>
    </div>'''

    st.markdown(widget, unsafe_allow_html=True)

    # Navigation buttons (below widget)
    st.markdown("---")
    st.markdown("**Navigate sub-categories:**")
    for cat, items in data.items():
        with st.expander(
            f"{'🔴' if any(r['severity']=='URGENT' for r in items) else '🟡' if any(r['severity']=='ACTION' for r in items) else '🔵'} **{cat}**",
            expanded=(cat == cur_cat)
        ):
            cols = st.columns(3)
            for i, r in enumerate(items):
                icon = SEV_ICON.get(r['severity'], '·')
                yk   = f"{r['ytd']/1000:.1f}k" if r['ytd'] >= 1000 else str(r['ytd'])
                lbl  = f"{icon} {r['subcat']} ({yk})"
                is_active = (cat == cur_cat and r['subcat'] == cur_sub)
                btn_type = "primary" if is_active else "secondary"
                if cols[i % 3].button(lbl, key=f"nav_{cat}_{r['subcat']}",
                                       use_container_width=True, type=btn_type):
                    st.session_state.cur_cat = cat
                    st.session_state.cur_sub = r['subcat']
                    st.rerun()


# ── MAIN ────────────────────────────────────────────────────────────────────────

# Header
st.markdown("""
<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
  <div style="width:36px;height:36px;background:#E8622A;border-radius:8px;
              display:flex;align-items:center;justify-content:center;font-size:20px">📦</div>
  <div>
    <div style="font-size:20px;font-weight:600;color:#1a1a1a">Fiz · Availability Briefing</div>
    <div style="font-size:12px;color:#888">Upload the Master_LIst inventory file to generate the briefing</div>
  </div>
</div>
""", unsafe_allow_html=True)

uploaded = st.file_uploader(
    "Upload Master_LIst inventory file",
    type=['xlsx'],
    label_visibility="collapsed",
)

if uploaded is None:
    st.markdown("""
    <div style="background:#f7f6f3;border:1px dashed #d0ccc8;border-radius:8px;
                padding:40px;text-align:center;color:#888;margin-top:16px">
        <div style="font-size:32px;margin-bottom:12px">📂</div>
        <div style="font-size:14px;font-weight:500;color:#555;margin-bottom:6px">
            Upload your inventory file to get started
        </div>
        <div style="font-size:12px">Accepts Master_LIst_-_DD-MM-YYYY.xlsx · Analysis runs automatically</div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

with st.spinner("Analysing inventory file…"):
    try:
        data, file_date, sku_count, filename = load_and_analyse(
            uploaded.read(), uploaded.name
        )
    except Exception as e:
        st.error(f"Error processing file: {e}")
        st.exception(e)
        st.stop()

# Summary metrics
total_u = sum(sum(1 for r in items if r['severity'] == 'URGENT') for items in data.values())
total_a = sum(sum(1 for r in items if r['severity'] == 'ACTION') for items in data.values())
total_n = sum(sum(1 for r in items if r['severity'] == 'NOTE')   for items in data.values())

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("File date", file_date)
c2.metric("Active SKUs", f"{sku_count:,}")
c3.metric("🔴 Urgent", total_u)
c4.metric("🟡 Action", total_a)
c5.metric("🔵 Note", total_n)

st.markdown("<div style='margin-bottom:12px'></div>", unsafe_allow_html=True)

render_widget(data, file_date, sku_count)

# ── PATCH: Updated sub_quality rules (applied 26-Jun-2026) ────────────────────
# 1. Price ratio cap applies globally (not just water):
#    > 3x price difference → WEAK regardless of tier
#    > 1.8x → STRONG at best, never DIRECT
# 2. Flavour variant rule applies globally:
#    OOS has flavour keyword, sub doesn't (or vice versa) → cap STRONG
#    Both have flavours but different → WEAK
