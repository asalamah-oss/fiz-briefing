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
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
#MainMenu, footer, header {visibility: hidden;}
.block-container {padding: 1rem 1.5rem 2rem; max-width: 100%;}
section[data-testid="stSidebar"] {background: #f7f6f3;}
section[data-testid="stSidebar"] .stRadio label {font-size: 13px;}
div[data-testid="stMetric"] {background: #f7f6f3; border-radius: 8px; padding: 8px 12px;}
.urgent-banner {background:#fee2e2;color:#b91c1c;padding:8px 12px;border-radius:6px;font-weight:500;font-size:13px;margin-bottom:8px;}
.action-banner {background:#fef3c7;color:#92400e;padding:8px 12px;border-radius:6px;font-weight:500;font-size:13px;margin-bottom:8px;}
.note-banner   {background:#dbeafe;color:#1e40af;padding:8px 12px;border-radius:6px;font-weight:500;font-size:13px;margin-bottom:8px;}
.store-ok  {background:#f0fdf4;border-radius:6px;padding:6px 10px;margin-bottom:6px;}
.store-pt  {background:#fffbeb;border-radius:6px;padding:6px 10px;margin-bottom:6px;}
.store-oo  {background:#fef2f2;border-radius:6px;padding:6px 10px;margin-bottom:6px;}
.oos-block {border:1px solid #fca5a5;border-radius:6px;padding:8px 10px;margin:4px 0;background:#fef2f2;}
.sub-direct {background:#d1fae5;color:#065f46;font-size:11px;font-weight:600;padding:1px 6px;border-radius:3px;}
.sub-strong {background:#fef3c7;color:#92400e;font-size:11px;font-weight:600;padding:1px 6px;border-radius:3px;}
.sub-weak   {background:#fee2e2;color:#991b1b;font-size:11px;font-weight:600;padding:1px 6px;border-radius:3px;}
.excl-note  {background:#f7f6f3;border:1px solid #e2ddd8;border-radius:6px;padding:6px 10px;font-size:12px;color:#888;font-style:italic;margin-bottom:8px;}
</style>
""", unsafe_allow_html=True)

# ── ANALYSIS ENGINE ──────────────────────────────────────────────────────────

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

def brand_tier(v, d):
    s = (str(v) + ' ' + str(d)).lower()
    for b, t in BRAND_TIERS.items():
        if b in s: return t
    if any(k in s for k in ['organic','natureland','bonato','earth organic']): return 'PREMIUM_ORGANIC'
    return 'STANDARD'

def get_size(d):
    d = str(d).lower()
    for p in ['200ml','330ml','250ml','500ml','750ml','1l','1.5l','2l']:
        if p in d: return p
    return 'other'

def get_flavour(d):
    d = d.lower(); return {f for f in FLAVOUR_KW if f in d}

def get_variant(d):
    d = d.lower(); return {v for v in VARIANT_KW if v in d}

def is_organic(d):
    return any(k in d.lower() for k in ['organic','natureland','bonato','earth organic'])

def detect_sold_col(columns, store_kw, month_kw):
    cands = [c for c in columns if 'Sold Qty' in c and month_kw in c and store_kw in c]
    if not cands: return None
    def sd(col):
        m = re.search(r'(\d+)\s+(?:June|Jun|May)', col)
        return int(m.group(1)) if m else 99
    return sorted(cands, key=sd)[0]

def sub_quality(oos_row, sub_row, cat_name):
    ood = str(oos_row.get('Description','')); sud = str(sub_row.get('Description',''))
    oos_p = float(oos_row.get('Net Unit Cost', 0) or 0)
    sub_p = float(sub_row.get('Net Unit Cost', 0) or 0)
    oos_v = str(oos_row.get('Vendor','')); sub_v = str(sub_row.get('Vendor',''))
    ratio = sub_p / oos_p if oos_p > 0.01 else 1.0
    price_weak       = 5.0 if cat_name == 'Water' else 3.0
    price_strong_cap = 4.0 if cat_name == 'Water' else 1.8

    if is_organic(ood) != is_organic(sud):
        return 'STRONG', 'Organic vs mainstream — functional substitute but different positioning'

    if ratio > price_weak:
        return 'WEAK', f'{ratio:.1f}x price difference — customer won\'t trade up'
    if ratio < (1 / price_weak):
        return 'WEAK', f'Sub is {(1/ratio):.1f}x cheaper — likely inferior quality perception'

    oos_fl = get_flavour(ood); sub_fl = get_flavour(sud)
    oos_vr = get_variant(ood); sub_vr = get_variant(sud)
    flavour_cap = False
    if oos_fl and sub_fl and oos_fl != sub_fl:
        return 'WEAK', f'Different flavour ({", ".join(sorted(oos_fl))} vs {", ".join(sorted(sub_fl))})'
    if (oos_fl and not sub_fl) or (not oos_fl and sub_fl): flavour_cap = True
    if oos_vr != sub_vr: flavour_cap = True

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
        if tr == 'WEAK': return 'WEAK', f'{oot} vs {sut} tier — different customer'
        if ratio > price_strong_cap or (oos_sz != sub_sz and oos_sz != 'other'): tr = 'STRONG'
        if flavour_cap and tr == 'DIRECT': tr = 'STRONG'
        return tr, {'DIRECT':'Same tier & format','STRONG':'Comparable tier'}.get(tr,'Weak')

    if ratio > price_strong_cap:  result, label = 'STRONG', f'Similar use case, {ratio:.1f}x price'
    elif ratio > 1.4:             result, label = 'STRONG', f'Comparable, {ratio:.1f}x price'
    else:                         result, label = 'DIRECT', 'Comparable brand & price'
    if flavour_cap and result == 'DIRECT':
        result, label = 'STRONG', 'Same category but different flavour/variant — not a direct replacement'
    return result, label


@st.cache_data(show_spinner=False)
def load_and_analyse(file_bytes, filename):
    inv = pd.read_excel(io.BytesIO(file_bytes))
    inv.columns = [c.strip() for c in inv.columns]
    inv = inv[inv['Status'] == 'Active'].copy()
    inv['Barcode'] = inv['Barcode'].astype(str).str.strip()
    cols = list(inv.columns)

    j7d_col  = detect_sold_col(cols, 'Jahra', 'June') or detect_sold_col(cols, 'Jahra', 'Jun')
    q7d_col  = detect_sold_col(cols, 'Qurtuba', 'June') or detect_sold_col(cols, 'Qurtuba', 'Jun')
    ss7d_col = detect_sold_col(cols, 'Sabah Salem', 'June') or detect_sold_col(cols, 'Sabah Salem', 'Jun')
    jmay_col  = detect_sold_col(cols, 'Jahra', 'May')
    qmay_col  = detect_sold_col(cols, 'Qurtuba', 'May')
    ssmay_col = detect_sold_col(cols, 'Sabah Salem', 'May')

    rename = {}
    for src, dst in [('Jahra Dark Store Stock','j'),('Qurtuba Dark Store Stock','q'),
        ('Sabah Salem Dark Store Stock','ss'),('Total SOH','total'),('Fresh/Non Fresh','fresh_type')]:
        if src in inv.columns: rename[src] = dst
    for src, dst in [(j7d_col,'j7d'),(q7d_col,'q7d'),(ss7d_col,'ss7d'),
                     (jmay_col,'jmay'),(qmay_col,'qmay'),(ssmay_col,'ssmay')]:
        if src and src in inv.columns: rename[src] = dst
    inv = inv.rename(columns=rename)

    for c in ['j','q','ss','total','j7d','q7d','ss7d','jmay','qmay','ssmay','Net Unit Cost']:
        if c not in inv.columns: inv[c] = 0
        inv[c] = pd.to_numeric(inv[c], errors='coerce').fillna(0)

    inv['ytd']  = inv['jmay'] + inv['qmay'] + inv['ssmay']
    inv['jytd'] = inv['jmay']; inv['qytd'] = inv['qmay']; inv['ssytd'] = inv['ssmay']
    inv['Sub Category'] = inv['Sub Category'].fillna('Unknown').str.strip() if 'Sub Category' in inv.columns else 'Unknown'
    inv['Category']     = inv['Category'].fillna('Unknown').str.strip() if 'Category' in inv.columns else 'Unknown'
    inv['Category'] = inv['Category'].replace({
        'WATER':'Water','BABY':'Baby','BAKERY':'Bakery','MEATS':'Meats',
        'SNACKS':'Snacks','PHARMA':'Pharma','STATIONARY':'Stationary'})
    inv['rt'] = np.where(inv['Category'].isin(PRODUCE_CATS), 'PRODUCE',
                np.where(inv['fresh_type'] == 'FRESH', 'FRESH', 'NON-FRESH'))

    STORE_SOH = {'Jahra':'j','Qurtuba':'q','Sabah Salem':'ss'}
    STORE_YTD = {'Jahra':'jytd','Qurtuba':'qytd','Sabah Salem':'ssytd'}
    results = {}

    for (cat, subcat), sub_df in inv.groupby(['Category','Sub Category']):
        ytd = int(sub_df['ytd'].sum()); ts = len(sub_df); ot = int((sub_df['total']==0).sum())
        jc = bool((sub_df['j']>0).any()); qc = bool((sub_df['q']>0).any()); sc = bool((sub_df['ss']>0).any())
        sv = sum([jc, qc, sc])
        rt = sub_df['rt'].mode().iloc[0] if len(sub_df) > 0 else 'NON-FRESH'

        store_data = {}
        for store in ['Jahra','Qurtuba','Sabah Salem']:
            col  = STORE_SOH[store]; ycol = STORE_YTD[store]
            sty  = int(sub_df[ycol].sum())
            oos_skus  = sub_df[(sub_df[col]==0) & (sub_df[ycol]>3)].sort_values(ycol, ascending=False)
            in_stock  = sub_df[sub_df[col]>0].sort_values(ycol, ascending=False)
            oos_out = []
            for _, or_ in oos_skus.head(4).iterrows():
                subs = []
                for _, sr_ in in_stock.iterrows():
                    if sr_['Barcode'] == or_['Barcode']: continue
                    strength, label = sub_quality(or_, sr_, cat)
                    if strength is None: continue
                    subs.append({'desc': sr_['Description'][:45], 'soh': int(sr_[col]),
                                 'strength': strength, 'label': label})
                subs = sorted(subs, key=lambda x: ['DIRECT','STRONG','WEAK'].index(x['strength']))
                oos_out.append({
                    'desc':        or_['Description'][:52],
                    'barcode':     str(or_['Barcode']),
                    'store_ytd':   int(or_[ycol]),
                    'network_ytd': int(or_['ytd']),
                    'vendor':      str(or_.get('Vendor',''))[:25],
                    'subs':        subs[:2],
                })
            store_data[store] = {
                'covered':       bool((sub_df[col]>0).any()),
                'oos_count':     len(oos_skus),
                'in_stock_count': len(in_stock),
                'store_ytd':     sty,
                'oos_skus':      oos_out,
                'in_stock_top':  [{'desc': r['Description'][:45], 'soh': int(r[col]), 'store_ytd': int(r[ycol])}
                                  for _, r in in_stock.head(3).iterrows()],
            }

        if sv == 0 and ytd > 15:      sev = 'URGENT'
        elif sv == 1 and ytd > 15:    sev = 'URGENT'
        elif sv == 2 and ytd > 10:    sev = 'ACTION'
        elif sv == 3:
            hv = any(any(o['store_ytd'] > 30 for o in store_data[st]['oos_skus'])
                     for st in ['Jahra','Qurtuba','Sabah Salem'])
            sev = 'NOTE' if hv else 'OK'
        else: sev = 'OK'

        if sev == 'OK': continue
        if cat not in results: results[cat] = []
        results[cat].append({
            'subcat': subcat, 'ytd': ytd, 'total_skus': ts,
            'oos_total': ot, 'stores_covered': sv,
            'severity': sev, 'rt': rt,
            'stores': store_data,
        })

    SEV_ORDER = ['URGENT','ACTION','NOTE']
    CAT_ORDER = [
        'Dairy & Eggs','Drinks','Confectionary','Fruits & Vegetables','Snacks','Ice Cream',
        'Bakery','Cupboard','Home Care','Personal Care','Water','Frozen Food','Baby','Meats',
        'Health & Lifestyle','Coffee, Tea & Creamer','Pets','Baking Essentials','Ready to Eat',
        'Pharma','Stationary',
    ]
    ordered = {}
    for cat in CAT_ORDER:
        if cat in results:
            ordered[cat] = sorted(results[cat], key=lambda x: (SEV_ORDER.index(x['severity']), -x['ytd']))
    for cat in sorted(results.keys()):
        if cat not in ordered:
            ordered[cat] = sorted(results[cat], key=lambda x: (SEV_ORDER.index(x['severity']), -x['ytd']))

    date_match = re.search(r'(\d{2}-\d{2}-\d{4})', filename)
    file_date  = date_match.group(1) if date_match else 'uploaded'
    return ordered, file_date, len(inv), filename


# ── UI ───────────────────────────────────────────────────────────────────────

SEV_ICON = {'URGENT':'🔴','ACTION':'🟡','NOTE':'🔵'}
FLAG_OPTIONS = ['—','Discontinued here','Out of season','Promo ended','Discontinued']

def get_flag(key):
    return st.session_state.get(f'flag_{key}', '—')

def render_store_card(store, sd, sub_key, flags_key):
    covered   = sd.get('covered', False)
    oc        = sd.get('oos_count', 0)
    sty       = sd.get('store_ytd', 0)
    oos_list  = sd.get('oos_skus', [])
    in_list   = sd.get('in_stock_top', [])

    if covered and oc == 0:
        status_color = 'store-ok'
        badge = '✓ All in stock'
    elif covered:
        status_color = 'store-pt'
        badge = f'{oc} OOS in sub-cat'
    else:
        status_color = 'store-oo'
        badge = '✗ No coverage'

    with st.container():
        st.markdown(f'<div class="{status_color}"><b>{store}</b> &nbsp; {badge} &nbsp;·&nbsp; YTD: {sty:,}</div>',
                    unsafe_allow_html=True)

        if in_list:
            with st.expander(f"✓ In stock ({sd.get('in_stock_count',0)} SKUs)", expanded=False):
                for sk in in_list:
                    st.markdown(f"**{sk['desc']}** — {sk['soh']}u · {sk['store_ytd']} ytd")

        if oos_list:
            for oi, oos in enumerate(oos_list):
                fkey = f"{sub_key}|{store}|{oi}"
                flag_val = get_flag(fkey)
                flagged  = flag_val != '—'

                with st.expander(
                    f"{'~~' if flagged else ''}✗ {oos['desc']}{'~~' if flagged else ''} — {oos['store_ytd']:,} store ytd / {oos['network_ytd']:,} net",
                    expanded=not flagged
                ):
                    col1, col2 = st.columns([3,1])
                    with col1:
                        st.caption(f"Vendor: {oos['vendor']}")
                    with col2:
                        new_flag = st.selectbox(
                            'Flag',
                            FLAG_OPTIONS,
                            index=FLAG_OPTIONS.index(flag_val),
                            key=f'flag_{fkey}',
                            label_visibility='collapsed',
                        )

                    if flagged:
                        st.info(f'Flagged: {flag_val} — excluded from OOS count')
                    else:
                        if oos['subs']:
                            for sub in oos['subs']:
                                tag_class = {'DIRECT':'sub-direct','STRONG':'sub-strong','WEAK':'sub-weak'}.get(sub['strength'],'sub-weak')
                                st.markdown(
                                    f'<span class="{tag_class}">{sub["strength"]}</span> &nbsp; '
                                    f'**{sub["desc"]}** ({sub["soh"]}u) &nbsp; <span style="color:#888;font-size:12px">{sub["label"]}</span>',
                                    unsafe_allow_html=True)
                        else:
                            st.error('No substitute — raise PO immediately')
        elif covered:
            st.success('No high-velocity OOS at this store')


# ── MAIN ─────────────────────────────────────────────────────────────────────

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

uploaded = st.file_uploader('Upload inventory file', type=['xlsx'], label_visibility='collapsed')

if uploaded is None:
    st.markdown("""
    <div style="background:#f7f6f3;border:1px dashed #d0ccc8;border-radius:8px;
                padding:40px;text-align:center;color:#888;margin-top:16px">
        <div style="font-size:32px;margin-bottom:12px">📂</div>
        <div style="font-size:14px;font-weight:500;color:#555;margin-bottom:6px">
            Upload your inventory file to get started</div>
        <div style="font-size:12px">Accepts Master_LIst_-_DD-MM-YYYY.xlsx · Analysis runs automatically</div>
    </div>""", unsafe_allow_html=True)
    st.stop()

with st.spinner('Analysing inventory file…'):
    try:
        data, file_date, sku_count, filename = load_and_analyse(uploaded.read(), uploaded.name)
    except Exception as e:
        st.error(f'Error: {e}')
        st.exception(e)
        st.stop()

# Summary metrics
total_u = sum(sum(1 for r in v if r['severity']=='URGENT') for v in data.values())
total_a = sum(sum(1 for r in v if r['severity']=='ACTION') for v in data.values())
total_n = sum(sum(1 for r in v if r['severity']=='NOTE')   for v in data.values())

c1,c2,c3,c4,c5 = st.columns(5)
c1.metric('File date',    file_date)
c2.metric('Active SKUs',  f'{sku_count:,}')
c3.metric('🔴 Urgent',   total_u)
c4.metric('🟡 Action',   total_a)
c5.metric('🔵 Note',     total_n)

st.divider()

# ── SIDEBAR NAV ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('### Categories')
    all_subcats = []
    for cat, items in data.items():
        u = sum(1 for r in items if r['severity']=='URGENT')
        a = sum(1 for r in items if r['severity']=='ACTION')
        badges = (f' 🔴{u}' if u else '') + (f' 🟡{a}' if a else '')
        st.markdown(f'**{cat}**{badges}')
        for r in items:
            yk = f"{r['ytd']/1000:.1f}k" if r['ytd'] >= 1000 else str(r['ytd'])
            icon = SEV_ICON.get(r['severity'],'·')
            label = f"{icon} {r['subcat']} ({yk})"
            all_subcats.append((cat, r['subcat'], label))

    # Selector
    labels = [x[2] for x in all_subcats]
    if 'selected_idx' not in st.session_state:
        st.session_state.selected_idx = 0

    selected_label = st.radio(
        'Sub-category',
        labels,
        index=st.session_state.selected_idx,
        label_visibility='collapsed',
    )
    selected_idx = labels.index(selected_label)
    sel_cat, sel_sub, _ = all_subcats[selected_idx]

# ── DETAIL VIEW ───────────────────────────────────────────────────────────────
items = data.get(sel_cat, [])
r = next((x for x in items if x['subcat'] == sel_sub), None)

if not r:
    st.info('Select a sub-category from the sidebar')
    st.stop()

# Header
rt = r.get('rt','NON-FRESH')
rt_label = {'FRESH':'Fresh · supplier-direct','PRODUCE':'Produce · supplier-direct',
            'NON-FRESH':'Non-fresh · transfer eligible'}.get(rt, rt)

col1, col2 = st.columns([3,1])
with col1:
    st.markdown(f'## {sel_sub}')
    st.caption(f'{sel_cat} · {rt_label} · {file_date}')
with col2:
    st.caption('')

# Severity banner
sev = r['severity']
sev_text = {'URGENT':f'🔴 Urgent — no adequate coverage',
            'ACTION':f'🟡 Action needed — partially covered',
            'NOTE':  f'🔵 Note — covered but high-velocity gaps'}.get(sev,'')
sev_class = {'URGENT':'urgent-banner','ACTION':'action-banner','NOTE':'note-banner'}.get(sev,'')
st.markdown(f'<div class="{sev_class}">{sev_text}</div>', unsafe_allow_html=True)

# Count flagged items
total_oos = r['oos_total']
flagged_count = sum(
    1 for st_name in ['Jahra','Qurtuba','Sabah Salem']
    for oi in range(len(r['stores'].get(st_name,{}).get('oos_skus',[])))
    if get_flag(f"{sel_sub}|{st_name}|{oi}") != '—'
)
eff_oos = total_oos - flagged_count

# KPIs
k1,k2,k3,k4 = st.columns(4)
k1.metric('Stores covered', f"{r['stores_covered']}/3")
k2.metric('SKUs in sub-cat', r['total_skus'])
k3.metric('SKUs OOS', eff_oos, delta=f'-{flagged_count} flagged' if flagged_count else None,
          delta_color='normal' if flagged_count else 'off')
k4.metric('Network YTD', f"{r['ytd']:,}")

if flagged_count:
    st.markdown(f'<div class="excl-note">{flagged_count} OOS SKU{"s" if flagged_count>1 else ""} excluded from scoring — flagged as contextual</div>',
                unsafe_allow_html=True)

st.divider()

# Store cards
sub_key = sel_sub
for store in ['Jahra','Qurtuba','Sabah Salem']:
    sd = r['stores'].get(store, {})
    render_store_card(store, sd, sub_key, f'{sel_sub}|{store}')
