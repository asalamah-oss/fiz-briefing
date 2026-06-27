"""
Fiz Availability Briefing v2
Two uploads: Master_LIst (daily) + Order History (persistent via storage)
"""

import streamlit as st
import pandas as pd
import numpy as np
import io, re, json, datetime


# ── GITHUB PERSISTENCE ────────────────────────────────────────────────────────
import base64, requests

def _gh_headers():
    token = st.secrets.get("GITHUB_TOKEN", "")
    return {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

def _gh_repo():
    return st.secrets.get("GITHUB_REPO", "asalamah-oss/fiz-briefing")

def gh_read(path):
    """Read a file from GitHub repo. Returns content string or None."""
    try:
        url = f"https://api.github.com/repos/{_gh_repo()}/contents/{path}"
        r = requests.get(url, headers=_gh_headers(), timeout=10)
        if r.status_code == 200:
            data = r.json()
            return base64.b64decode(data['content']).decode('utf-8'), data['sha']
        return None, None
    except Exception:
        return None, None

def gh_write(path, content, sha=None):
    """Write a file to GitHub repo. sha required for updates."""
    try:
        url = f"https://api.github.com/repos/{_gh_repo()}/contents/{path}"
        payload = {
            "message": f"auto: update {path}",
            "content": base64.b64encode(content.encode('utf-8')).decode('utf-8'),
        }
        if sha:
            payload["sha"] = sha
        r = requests.put(url, headers=_gh_headers(), json=payload, timeout=15)
        return r.status_code in [200, 201]
    except Exception:
        return False

st.set_page_config(page_title="Fiz · Availability Briefing", page_icon="📦",
                   layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
#MainMenu,footer,header{visibility:hidden;}
.block-container{padding:1rem 1.5rem 2rem;max-width:100%;}
div[data-testid="stMetric"]{background:#f7f6f3;border-radius:8px;padding:8px 12px;}
</style>""", unsafe_allow_html=True)

# ── CONSTANTS ─────────────────────────────────────────────────────────────────
PRODUCE_CATS = ['Fruits & Vegetables']
BRAND_TIERS = {
    'rawdatain':'PREMIUM_LOCAL','evian':'PREMIUM_INTL','volvic':'PREMIUM_INTL',
    'san pellegrino':'PREMIUM_INTL','perrier':'PREMIUM_INTL','fiji':'PREMIUM_INTL',
    'masafi':'MID','arwa':'VALUE','abraaj':'VALUE','aquagulf':'VALUE',
}
FLAVOUR_KW = {'mint','strawberry','chocolate','mango','vanilla','lemon','orange','banana',
    'peach','blueberry','raspberry','caramel','mocha','cherry','apple','watermelon',
    'grape','lime','coconut','passion','hazelnut','coffee','honey','cinnamon','rose','saffron','tropical'}
VARIANT_KW = {'zero','diet','light','sugar free','no sugar','low fat','full fat','skimmed',
    'semi skimmed','fat free','reduced fat','unsalted','salted','whole','wholegrain','wholemeal'}
CAT_ORDER = ['Dairy & Eggs','Drinks','Confectionary','Fruits & Vegetables','Snacks','Ice Cream',
    'Bakery','Cupboard','Home Care','Personal Care','Water','Frozen Food','Baby','Meats',
    'Health & Lifestyle','Coffee, Tea & Creamer','Pets','Baking Essentials','Ready to Eat','Pharma','Stationary']
SEV_ORDER  = ['URGENT','ACTION','NOTE','OVERSTOCK']
FLAG_KEYS  = ['dl','os','pe','dc','ssl']
FLAG_LABELS= {'dl':'Discontinued here','os':'Out of season','pe':'Promo ended',
              'dc':'Discontinued','ssl':'Supplier service level'}
RESOLUTION_LABELS = {
    'DC_TRANSFER':       '🔄 Transfer from DC',
    'RAISE_PO':          '📦 Raise PO',
    'PO_DIRECT':         '🌱 Raise PO direct',
    'OVERSTOCK_ELSEWHERE':'⚠️ Overstock elsewhere',
}
OH_STORAGE_KEY = 'fiz_order_history_v2'

# ── SUB-QUALITY ENGINE ────────────────────────────────────────────────────────
PRODUCT_TYPE_TOKENS = [
    'feta','cheddar','mozzarella','brie','edam','gouda','halloumi','haloumi',
    'kashkaval','ricotta','parmesan','emmental','gruyere','labneh','cream cheese',
    'processed cheese','white cheese','cottage cheese','mascarpone','camembert',
    'toast','pita','baguette','croissant','sourdough','bagel','tortilla',
    'tannour','tandoor','simit','brioche',
    'instant coffee','ground coffee','coffee beans','coffee capsule','coffee pod',
    'green tea','black tea','herbal tea','chamomile',
    'olive oil','sunflower oil','coconut oil','corn oil','sesame oil','avocado oil',
    'orange juice','apple juice','mango juice','pomegranate juice','grape juice',
    'chicken','beef','lamb','turkey','tuna','salmon','shrimp','prawn','sardine',
    'oat milk','almond milk','soy milk','soya milk','coconut milk','goat milk',
    'greek','skyr',
    'blueberr','strawberr','raspberr','blackberr',
    'mango','watermelon','banana','apple','orange','lemon','lime',
    'grape','peach','apricot','cherry','fig','pomegranate','guava','kiwi',
    'pear','plum','nectarine','clementine','mandarin','grapefruit',
    'potato','tomato','cucumber','capsicum','onion','carrot','zucchini',
    'eggplant','spinach','rocket','parsley','coriander','basil','lettuce',
    'broccoli','cauliflower','celery','leek','pumpkin',
    'brown sugar','white sugar','caster sugar','icing sugar','coconut sugar',
    'basmati','jasmine','arborio',
    'spaghetti','penne','fusilli','macaroni','linguine','rigatoni',
    'dark chocolate','milk chocolate','white chocolate',
]

def get_product_token(desc):
    d = desc.lower()
    for token in PRODUCT_TYPE_TOKENS:
        if token in d:
            return token
    return None

def product_types_conflict(desc1, desc2):
    t1 = get_product_token(desc1)
    t2 = get_product_token(desc2)
    if t1 is None or t2 is None:
        return False
    return t1 != t2

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

def sub_quality(oos_rsp, oos_v, oos_d, sub_rsp, sub_v, sub_d, cat):
    if product_types_conflict(oos_d, sub_d):
        return None, None
    ratio = sub_rsp/oos_rsp if oos_rsp>0.01 else 1.0
    pw = 5.0 if cat=='Water' else 3.0; psc = 4.0 if cat=='Water' else 1.8
    if is_organic(oos_d)!=is_organic(sub_d): return 'STRONG'
    if ratio>pw or ratio<(1/pw): return 'WEAK'
    ofl=get_flavour(oos_d); sfl=get_flavour(sub_d)
    ovr=get_variant(oos_d); svr=get_variant(sub_d)
    fcap=False
    if ofl and sfl and ofl!=sfl: return 'WEAK'
    if (ofl and not sfl) or (not ofl and sfl): fcap=True
    if ovr!=svr: fcap=True
    if cat=='Water':
        oot=brand_tier(oos_v,oos_d); sut=brand_tier(sub_v,sub_d)
        osz=get_size(oos_d); ssz=get_size(sub_d)
        if osz in {'200ml','330ml','250ml'} and ssz in {'500ml','750ml','1l','1.5l','2l'}: return None
        tier_map={('PREMIUM_LOCAL','PREMIUM_LOCAL'):'DIRECT',('PREMIUM_INTL','PREMIUM_INTL'):'DIRECT',
            ('PREMIUM_LOCAL','PREMIUM_INTL'):'STRONG',('PREMIUM_INTL','PREMIUM_LOCAL'):'STRONG',
            ('MID','MID'):'DIRECT',('VALUE','VALUE'):'DIRECT'}
        tr=tier_map.get((oot,sut),'WEAK')
        if tr=='WEAK': return 'WEAK'
        if ratio>psc or (osz!=ssz and osz!='other'): return 'STRONG'
        if fcap and tr=='DIRECT': return 'STRONG'
        return tr
    if ratio>psc: r='STRONG'
    elif ratio>1.4: r='STRONG'
    else: r='DIRECT'
    if fcap and r=='DIRECT': r='STRONG'
    return r

def detect_sold_col(columns, store_kw, month_kw):
    cands=[c for c in columns if 'Sold Qty' in c and month_kw in c and store_kw in c]
    if not cands: return None
    def sd(col):
        m=re.search(r'(\d+)\s+(?:June|Jun|May)',col); return int(m.group(1)) if m else 99
    return sorted(cands,key=sd)[0]

# ── ORDER HISTORY PROCESSOR ───────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def process_order_history(oh_bytes_list, inv_item_ids):
    """Combine multiple order history files, compute velocity per SKU per store."""
    frames = []
    for b in oh_bytes_list:
        df = pd.read_csv(io.BytesIO(b))
        frames.append(df)
    oh = pd.concat(frames, ignore_index=True).drop_duplicates(subset=['Order_ID'])
    item_cols = [c for c in oh.columns if c.startswith('Item ')]
    oh['date'] = pd.to_datetime(oh['Transaction_Timestamp']).dt.date
    oh['store_norm'] = oh['Store'].str.strip().replace(
        {'Sabah Al Salem':'Sabah Salem','Qurtoba':'Qurtuba','Jahra':'Jahra'})
    long = oh[['Order_ID','date','store_norm']+item_cols].melt(
        id_vars=['Order_ID','date','store_norm'], value_vars=item_cols, value_name='item_id'
    ).dropna(subset=['item_id'])
    long['item_id'] = long['item_id'].astype(int)
    long['qty'] = 1
    long = long[long['item_id'].isin(inv_item_ids)]

    today = long['date'].max()
    l7_start = today - datetime.timedelta(days=7)

    ytd = long.groupby(['item_id','store_norm']).agg(
        ytd_units=('qty','sum'), ytd_days=('date','nunique')).reset_index()
    ytd['true_daily'] = ytd['ytd_units'] / ytd['ytd_days']

    l7 = long[long['date']>=l7_start].groupby(['item_id','store_norm']).agg(
        l7_units=('qty','sum')).reset_index()

    # Network YTD for top SKU availability KPIs
    net = long.groupby('item_id')['qty'].sum().reset_index().rename(columns={'qty':'net_ytd'})

    return ytd, l7, net, str(today)

# ── MAIN ANALYSIS ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def run_analysis(inv_bytes, inv_filename, vel_key, ytd_json, l7_json, net_json):
    """Run full briefing analysis. vel_key changes when velocity data is updated."""
    # Load inventory
    inv = pd.read_excel(io.BytesIO(inv_bytes))
    inv.columns = [c.strip() for c in inv.columns]
    inv = inv[inv['Status']=='Active'].copy()
    inv['Item ID'] = pd.to_numeric(inv['Item ID'], errors='coerce')
    inv['Barcode']  = inv['Barcode'].astype(str).str.strip()

    # Numeric cols
    for c in ['Jahra Dark Store Stock','Qurtuba Dark Store Stock','Sabah Salem Dark Store Stock',
              'Ardiya - Distribution Center Stock','Total SOH','RSP','Net Unit Cost']:
        if c in inv.columns:
            inv[c] = pd.to_numeric(inv[c], errors='coerce').fillna(0)

    inv['is_fresh'] = inv['Fresh/Non Fresh'].isin(['FRESH']) | inv['Category'].isin(PRODUCE_CATS)
    inv['Category'] = inv['Category'].fillna('Unknown').str.strip().replace(
        {'WATER':'Water','BABY':'Baby','BAKERY':'Bakery','MEATS':'Meats',
         'SNACKS':'Snacks','PHARMA':'Pharma','STATIONARY':'Stationary'})
    inv['Sub Category'] = inv['Sub Category'].fillna('Unknown').str.strip()

    # Velocity data passed as serialised JSON to avoid session state in cached fn
    import io as _io
    ytd_df = pd.read_json(_io.StringIO(ytd_json)) if ytd_json else None
    l7_df  = pd.read_json(_io.StringIO(l7_json))  if l7_json  else None
    net_df = pd.read_json(_io.StringIO(net_json))  if net_json  else None

    STORE_SOH = {'Jahra':'Jahra Dark Store Stock','Qurtuba':'Qurtuba Dark Store Stock',
                 'Sabah Salem':'Sabah Salem Dark Store Stock'}
    results = {}

    for (cat, subcat), sub_df in inv.groupby(['Category','Sub Category']):
        subcat_result = {'subcat':subcat,'cat':cat,'stores':{}}
        has_issue = False

        for store, soh_col in STORE_SOH.items():
            in_stock_df  = sub_df[sub_df[soh_col]>0].copy()
            oos_df       = sub_df[sub_df[soh_col]==0].copy()

            # Attach velocity to OOS items
            if ytd_df is not None:
                sv = ytd_df[ytd_df['store_norm']==store][['item_id','true_daily','ytd_units','ytd_days']]
                l7s= l7_df[l7_df['store_norm']==store][['item_id','l7_units']] if l7_df is not None else pd.DataFrame(columns=['item_id','l7_units'])
                oos_df = oos_df.merge(sv.rename(columns={'item_id':'Item ID'}), on='Item ID', how='left')
                oos_df = oos_df.merge(l7s.rename(columns={'item_id':'Item ID'}), on='Item ID', how='left')
                in_stock_df = in_stock_df.merge(sv.rename(columns={'item_id':'Item ID'}), on='Item ID', how='left')
                for c in ['true_daily','ytd_units','ytd_days','l7_units']:
                    for df in [oos_df, in_stock_df]:
                        if c in df.columns: df[c] = df[c].fillna(0)
                        else: df[c] = 0
            else:
                for df in [oos_df, in_stock_df]:
                    for c in ['true_daily','ytd_units','ytd_days','l7_units']: df[c] = 0

            # Days of cover for in-stock items
            in_stock_df['days_cover'] = np.where(
                in_stock_df['true_daily']>0,
                in_stock_df[soh_col]/in_stock_df['true_daily'], 999)

            # Filter OOS to velocity ≥ 0.5
            oos_sig = oos_df[oos_df['true_daily']>=0.5].sort_values('true_daily',ascending=False)

            oos_out = []
            for _, oos in oos_sig.head(6).iterrows():
                # Find best substitute at this store
                best_str = None; best_sub_desc = None; best_sub_soh = 0
                for _, s_row in in_stock_df.iterrows():
                    if s_row['Item ID'] == oos['Item ID']: continue
                    strength = sub_quality(
                        float(oos.get('RSP',0)), str(oos.get('Vendor','')), str(oos.get('Description','')),
                        float(s_row.get('RSP',0)), str(s_row.get('Vendor','')), str(s_row.get('Description','')),
                        cat)
                    if strength is None: continue
                    if best_str is None or SEV_ORDER_SUB.index(strength) < SEV_ORDER_SUB.index(best_str):
                        best_str = strength; best_sub_desc = str(s_row['Description'])[:45]
                        best_sub_soh = int(s_row[soh_col])
                    if best_str == 'DIRECT': break

                # Resolution label
                dc_soh = float(oos.get('Ardiya - Distribution Center Stock',0))
                is_fresh = bool(oos.get('is_fresh',False))
                if is_fresh:
                    resolution = 'PO_DIRECT'
                elif dc_soh > 0:
                    resolution = 'DC_TRANSFER'
                else:
                    # Check if another store is overstocked
                    other_overstocked = False
                    for other_store, other_col in STORE_SOH.items():
                        if other_store == store: continue
                        other_soh = float(oos.get(other_col, 0))
                        other_vel = float(oos.get('true_daily', 0))
                        if other_soh > 0 and other_vel > 0 and (other_soh/other_vel) > 45:
                            other_overstocked = True; break
                    resolution = 'OVERSTOCK_ELSEWHERE' if other_overstocked else 'RAISE_PO'

                # Severity
                v = float(oos.get('true_daily',0))
                if v >= 10 and best_str != 'DIRECT':
                    sev = 'URGENT'
                elif v >= 5 and best_str not in ['DIRECT','STRONG']:
                    sev = 'URGENT'
                elif v >= 2 and best_str is None:
                    sev = 'URGENT'
                elif v >= 2:
                    sev = 'ACTION'
                elif v < 2 and best_str is None:
                    sev = 'ACTION'
                else:
                    sev = 'NOTE'

                oos_out.append({
                    'item_id':   int(oos['Item ID']),
                    'desc':      str(oos['Description'])[:52],
                    'vendor':    str(oos.get('Vendor',''))[:25],
                    'velocity':  round(v,2),
                    'ytd':       int(oos.get('ytd_units',0)),
                    'l7':        int(oos.get('l7_units',0)),
                    'rsp':       float(oos.get('RSP',0)),
                    'dc_soh':    int(dc_soh),
                    'resolution':resolution,
                    'severity':  sev,
                    'best_sub_strength': best_str,
                    'best_sub_desc':     best_sub_desc,
                    'best_sub_soh':      best_sub_soh,
                })

            # Overstock items
            net_oos_ids = set()
            for other_col in STORE_SOH.values():
                net_oos_ids |= set(sub_df[sub_df[other_col]==0]['Item ID'].tolist())
            overstock_out = []
            for _, ov in in_stock_df[in_stock_df['days_cover']>45].iterrows():
                if ov['Item ID'] in net_oos_ids: continue  # another store is OOS, justified
                overstock_out.append({
                    'item_id':    int(ov['Item ID']),
                    'desc':       str(ov['Description'])[:52],
                    'vendor':     str(ov.get('Vendor',''))[:25],
                    'soh':        int(ov[soh_col]),
                    'days_cover': round(float(ov['days_cover']),0),
                    'velocity':   round(float(ov.get('true_daily',0)),2),
                    'rsp':        float(ov.get('RSP',0)),
                })

            # In-stock top
            in_stock_top = [{'desc':str(r['Description'])[:45],'soh':int(r[soh_col]),
                             'velocity':round(float(r.get('true_daily',0)),2),
                             'days_cover':round(float(r.get('days_cover',0)),0)}
                            for _,r in in_stock_df.sort_values('true_daily',ascending=False).head(3).iterrows()]

            store_ytd = int(in_stock_df.get('ytd_units',pd.Series([0])).sum() +
                           oos_df.get('ytd_units',pd.Series([0])).sum()) if ytd_df is not None else 0

            subcat_result['stores'][store] = {
                'covered':        len(in_stock_df) > 0,
                'oos_count':      len(oos_out),
                'overstock_count':len(overstock_out),
                'store_ytd':      store_ytd,
                'oos_skus':       oos_out,
                'overstock_skus': overstock_out,
                'in_stock_top':   in_stock_top,
            }
            if oos_out or overstock_out:
                has_issue = True

        if not has_issue:
            continue

        all_sevs = [o['severity'] for st in subcat_result['stores'].values() for o in st['oos_skus']]
        if 'URGENT'    in all_sevs: subcat_result['severity'] = 'URGENT'
        elif 'ACTION'  in all_sevs: subcat_result['severity'] = 'ACTION'
        elif all_sevs:              subcat_result['severity'] = 'NOTE'
        else:                       subcat_result['severity'] = 'OVERSTOCK'

        subcat_result['ytd'] = sum(
            subcat_result['stores'][st]['store_ytd'] for st in subcat_result['stores'])
        subcat_result['total_skus'] = len(sub_df)
        subcat_result['rt'] = 'FRESH' if sub_df['is_fresh'].any() else 'NON-FRESH'
        results.setdefault(cat, []).append(subcat_result)

    for cat in results:
        results[cat].sort(key=lambda x: (SEV_ORDER.index(x['severity']), -x['ytd']))

    ordered = {}
    for cat in CAT_ORDER:
        if cat in results: ordered[cat] = results[cat]
    for cat in sorted(results.keys()):
        if cat not in ordered: ordered[cat] = results[cat]

    date_match = re.search(r'(\d{2}-\d{2}-\d{4})', inv_filename)
    file_date  = date_match.group(1) if date_match else 'uploaded'

    # KPIs
    kpis = _compute_kpis(inv, net_df, ytd_df, l7_df)
    kpis['file_date'] = file_date
    kpis['sku_count'] = len(inv)
    kpis['urgent']    = sum(sum(1 for r in v if r['severity']=='URGENT') for v in ordered.values())
    kpis['action']    = sum(sum(1 for r in v if r['severity']=='ACTION') for v in ordered.values())
    kpis['note']      = sum(sum(1 for r in v if r['severity']=='NOTE') for v in ordered.values())
    kpis['overstock_cats'] = sum(sum(1 for r in v if r['severity']=='OVERSTOCK') for v in ordered.values())

    return ordered, kpis

SEV_ORDER_SUB = ['DIRECT','STRONG','WEAK']

def _compute_kpis(inv, net_df, ytd_df, l7_df):
    kpis = {}
    inv_c = inv.copy()
    for c in ['Jahra Dark Store Stock','Qurtuba Dark Store Stock','Sabah Salem Dark Store Stock',
              'Ardiya - Distribution Center Stock','Total SOH','RSP']:
        inv_c[c] = pd.to_numeric(inv_c.get(c,0), errors='coerce').fillna(0)

    # Revenue at risk
    if ytd_df is not None:
        all_vel = ytd_df.merge(inv_c[['Item ID','Total SOH','RSP']].rename(columns={'Item ID':'item_id'}),
                                on='item_id', how='left')
        oos_vel = all_vel[(all_vel['Total SOH']==0) & (all_vel['true_daily']>=0.5)]
        kpis['rev_risk'] = round(float((oos_vel['true_daily']*oos_vel['RSP']).sum()),0)
        kpis['skus_at_risk'] = int((oos_vel['true_daily']>=2).sum())
    else:
        kpis['rev_risk'] = 0; kpis['skus_at_risk'] = 0

    # DC transfer opps
    dc_store_opps = 0
    for _scol in ['Jahra Dark Store Stock','Qurtuba Dark Store Stock','Sabah Salem Dark Store Stock']:
        if _scol in inv_c.columns:
            dc_store_opps += int(((inv_c[_scol]==0) & (inv_c['Ardiya - Distribution Center Stock']>0)).sum())
    kpis['dc_opps'] = dc_store_opps

    # Overstock count
    if ytd_df is not None:
        net_vel = ytd_df.groupby('item_id')['true_daily'].mean().reset_index()
        inv_m = inv_c[['Item ID','Total SOH']].rename(columns={'Item ID':'item_id'}).merge(net_vel,on='item_id',how='left')
        inv_m['true_daily'] = inv_m['true_daily'].fillna(0)
        inv_m['days_cover']  = np.where(inv_m['true_daily']>0,inv_m['Total SOH']/inv_m['true_daily'],999)
        kpis['overstock_count'] = int(((inv_m['days_cover']>45) & (inv_m['true_daily']>0) & (inv_m['Total SOH']>0)).sum())
        kpis['dead_stock_count'] = int(((inv_m['Total SOH']>0) & (inv_m['true_daily']==0)).sum())
    else:
        kpis['overstock_count'] = 0
        kpis['dead_stock_count'] = 0

    # Availability by tier
    if net_df is not None:
        inv_ids = inv_c[['Item ID','Total SOH','Jahra Dark Store Stock',
                         'Qurtuba Dark Store Stock','Sabah Salem Dark Store Stock']].rename(columns={'Item ID':'item_id'})
        for c in ['Total SOH','Jahra Dark Store Stock','Qurtuba Dark Store Stock','Sabah Salem Dark Store Stock']:
            inv_ids[c] = pd.to_numeric(inv_ids[c],errors='coerce').fillna(0)
        inv_ids['all3'] = ((inv_ids['Jahra Dark Store Stock']>0) &
                           (inv_ids['Qurtuba Dark Store Stock']>0) &
                           (inv_ids['Sabah Salem Dark Store Stock']>0))
        top_merged = net_df.merge(inv_ids,on='item_id',how='inner')
        avail = {}
        for tier in [100,200,500,1000]:
            top_n = top_merged.nlargest(tier,'net_ytd')
            oos_n = (top_n['Total SOH']==0).sum()
            full3 = top_n['all3'].sum()
            avail[tier] = {'network': round((tier-oos_n)/tier*100,1),
                           'full3':   round(full3/tier*100,1),
                           'oos_n':   int(oos_n)}
        kpis['avail'] = avail
        # L7 velocity health - % of top 100 that sold in last 7 days
        if l7_df is not None:
            top100_ids = set(top_merged.nlargest(100,'net_ytd')['item_id'].tolist())
            sold_l7 = set(l7_df[l7_df['l7_units']>0]['item_id'].tolist())
            kpis['l7_health'] = round(len(top100_ids & sold_l7)/len(top100_ids)*100,1) if top100_ids else 0
        else:
            kpis['l7_health'] = 0
    else:
        kpis['avail'] = {t:{'network':0,'full3':0,'oos_n':0} for t in [100,200,500,1000]}
        kpis['l7_health'] = 0

    return kpis


# ── WIDGET HTML BUILDER ───────────────────────────────────────────────────────
def build_widget_html(data, kpis, cur_cat, cur_sub, flags, avail_tier):
    SI   = {'URGENT':'🔴','ACTION':'🟡','NOTE':'🔵','OVERSTOCK':'🟠'}
    SEVC = {'URGENT':'sv-u','ACTION':'sv-a','NOTE':'sv-n','OVERSTOCK':'sv-o'}
    SEVL = {'URGENT':'🔴 Urgent — high-velocity OOS, no adequate substitute',
            'ACTION':'🟡 Action needed — OOS with substitute available or moderate velocity',
            'NOTE':  '🔵 Note — low-velocity OOS',
            'OVERSTOCK':'🟠 Overstock — SKUs exceeding 45 days cover'}
    RTL  = {'FRESH':'Fresh · supplier-direct','PRODUCE':'Produce · supplier-direct',
            'NON-FRESH':'Non-fresh · transfer eligible'}
    RTC  = {'FRESH':'chip-f','PRODUCE':'chip-p','NON-FRESH':'chip-n'}
    FL   = ['Discontinued here','Out of season','Promo ended','Discontinued','Supplier service level']
    FK   = ['dl','os','pe','dc','ssl']

    # ── NAV ───────────────────────────────────────────────────────────────────
    nav_html = ''
    for cat, items in data.items():
        u=sum(1 for r in items if r['severity']=='URGENT')
        a=sum(1 for r in items if r['severity']=='ACTION')
        badges=(f'<span class="cbu">{u}U</span>' if u else '')+(f'<span class="cba">{a}A</span>' if a else '')
        nav_html += f'<div class="ch">{cat}<div class="cbs">{badges}</div></div>'
        for r in items:
            yk = f"{r['ytd']/1000:.1f}k" if r['ytd']>=1000 else str(r['ytd'])
            is_on = (cat==cur_cat and r['subcat']==cur_sub)
            flagged_n = sum(1 for st in ['Jahra','Qurtuba','Sabah Salem']
                for oi in range(len(r['stores'].get(st,{}).get('oos_skus',[])))
                if flags.get(f"{r['subcat']}|{st}|{oi}",{}).get('any'))
            flag_badge = f'<span class="ni-f">{flagged_n}⊘</span>' if flagged_n else ''
            ce = cat.replace("'","\\'"); se = r['subcat'].replace("'","\\'")
            nav_html += f'''<div class="ni{'  on' if is_on else ''}" onclick="selectSub('{ce}','{se}')">
              <div class="ni-i">{SI.get(r['severity'],'·')}</div>
              <span class="ni-l" title="{r['subcat']}">{r['subcat']}</span>
              {flag_badge}<span class="ni-y">{yk}</span></div>'''

    # ── KPI STRIP ─────────────────────────────────────────────────────────────
    avail = kpis.get('avail',{}).get(avail_tier,{'network':0,'full3':0,'oos_n':0})
    kpi_html = f'''
    <div class="kstrip">
      <div class="kp"><div class="kl">Revenue at risk · no direct sub</div><div class="kv r">{kpis.get("rev_risk",0):,.0f} KD/day</div></div>
      <div class="kp"><div class="kl">SKUs at risk (vel≥2)</div><div class="kv r">{kpis.get("skus_at_risk",0)}</div></div>
      <div class="kp kp-avail">
        <div class="kl">Availability · Top
          <span class="tier-btn{'  on' if avail_tier==100 else ''}" onclick="setTier(100)">100</span>
          <span class="tier-btn{'  on' if avail_tier==200 else ''}" onclick="setTier(200)">200</span>
          <span class="tier-btn{'  on' if avail_tier==500 else ''}" onclick="setTier(500)">500</span>
          <span class="tier-btn{'  on' if avail_tier==1000 else ''}" onclick="setTier(1000)">1k</span>
        </div>
        <div class="kv-row">
          <span class="kv-s">Network <b>{avail['network']}%</b></span>
          <span class="kv-s">Full coverage <b>{avail['full3']}%</b></span>
        </div>
      </div>
      <div class="kp"><div class="kl">DC transfer opps</div><div class="kv g">{kpis.get("dc_opps",0)}</div></div>
      <div class="kp"><div class="kl">Real overstock</div><div class="kv a">{kpis.get("overstock_count",0)}</div></div>
      <div class="kp"><div class="kl">Dead stock</div><div class="kv a">{kpis.get("dead_stock_count",0)}</div></div>
      <div class="kp"><div class="kl">L7 velocity health</div><div class="kv g">{kpis.get("l7_health",0)}%</div></div>
    </div>'''

    # ── DETAIL ────────────────────────────────────────────────────────────────
    items = data.get(cur_cat,[])
    r = next((x for x in items if x['subcat']==cur_sub), None)

    if not r:
        mbar_html   = '<span class="mb-t">Select a sub-category →</span>'
        detail_html = '<div style="padding:40px;text-align:center;color:#888">Select a sub-category from the left nav</div>'
    else:
        rt = r.get('rt','NON-FRESH')
        eff_oos = sum(1 for st in ['Jahra','Qurtuba','Sabah Salem']
                      for oi,o in enumerate(r['stores'].get(st,{}).get('oos_skus',[]))
                      if not flags.get(f"{cur_sub}|{st}|{oi}",{}).get('any'))
        excl = sum(1 for st in ['Jahra','Qurtuba','Sabah Salem']
                   for oi in range(len(r['stores'].get(st,{}).get('oos_skus',[])))
                   if flags.get(f"{cur_sub}|{st}|{oi}",{}).get('any'))
        stores_covered = sum(1 for st in ['Jahra','Qurtuba','Sabah Salem'] if r['stores'].get(st,{}).get('covered',False))
        cCl = 'g' if stores_covered>=3 else ('a' if stores_covered>=2 else 'r')
        oCl = 'g' if eff_oos==0 else ('a' if eff_oos<r['total_skus']*0.3 else 'r')

        mbar_html = f'''
        <div><span class="mb-t">{cur_sub}</span>&nbsp;<span class="mb-c">· {cur_cat}</span></div>
        <span class="chip {RTC.get(rt,'chip-n')}">{RTL.get(rt,rt)}</span>
        <span class="mb-s">{r["total_skus"]} SKUs · {r["ytd"]:,} YTD · {kpis.get("file_date","")}</span>'''

        detail_html = f'''<div class="ks">
          <div class="kp2"><div class="kl">SKUs in sub-cat</div><div class="kv2">{r["total_skus"]}</div></div>
          <div class="kp2"><div class="kl">SKUs OOS</div><div class="kv2 {oCl}">{eff_oos}</div></div>
          <div class="kp2"><div class="kl">Network YTD</div><div class="kv2">{r["ytd"]:,}</div></div>
        </div>'''
        if excl:
            detail_html += f'<div class="excl">{excl} OOS SKU{"s" if excl>1 else ""} excluded — flagged as contextual</div>'
        if r["severity"] in ("URGENT","ACTION","OVERSTOCK"):
            detail_html += f'<div class="sv {SEVC[r["severity"]]}">{SEVL[r["severity"]]}</div>'
        detail_html += '<div class="ss">'

        for store in ['Jahra','Qurtuba','Sabah Salem']:
            si  = ['Jahra','Qurtuba','Sabah Salem'].index(store)
            sd  = r['stores'].get(store,{})
            hc  = 'ok' if sd.get('covered') and sd.get('oos_count',0)==0 and sd.get('overstock_count',0)==0 \
                  else ('pt' if sd.get('covered') else 'oo')
            bg  = 'gok' if hc=='ok' else ('gpt' if hc=='pt' else 'goo')
            oc  = sd.get('oos_count',0); ovc = sd.get('overstock_count',0)
            parts = []
            if oc:  parts.append(f'{oc} OOS')
            if ovc: parts.append(f'{ovc} overstock')
            if not parts: parts = ['All in stock'] if hc=='ok' else ['No coverage']
            bt = ' · '.join(parts)

            detail_html += f'''<div class="sb">
              <div class="sh {hc}"><span class="sn">{store}</span>
              <span class="sg {bg}">{bt}</span>
              <span class="syt">YTD: {sd.get("store_ytd",0):,}</span></div>
              <div class="sbdy">'''

            if sd.get('in_stock_top'):
                detail_html += '<div class="dl">In stock — top sellers</div>'
                for sk in sd['in_stock_top'][:3]:
                    dc_str = f" · {sk['days_cover']:.0f}d cover" if sk.get('days_cover',0) < 999 else ''
                    detail_html += f'<div class="ik"><span style="color:#16a34a;font-size:11px;flex-shrink:0">✓</span><span class="id" title="{sk["desc"]}">{sk["desc"]}</span><span class="im">{sk["velocity"]}/day · {sk["soh"]}u{dc_str}</span></div>'

            if sd.get('oos_skus'):
                detail_html += '<div class="dl" style="margin-top:5px">Out of stock</div><div class="ow">'
                for oi, oos in enumerate(sd['oos_skus']):
                    fkey  = f"{cur_sub}|{store}|{oi}"
                    f_st  = flags.get(fkey,{})
                    flagged = f_st.get('any',False)
                    res   = RESOLUTION_LABELS.get(oos.get('resolution','RAISE_PO'),'📦 Raise PO')
                    sev_c = {'URGENT':'ob-u','ACTION':'ob-a','NOTE':'ob-n'}.get(oos.get('severity','NOTE'),'ob-n')
                    detail_html += f'<div class="ob {sev_c}{"  flagged" if flagged else ""}" id="ob_{si}_{oi}">'
                    detail_html += f'''<div class="oh">
                      <span class="sev-dot">{SI.get(oos["severity"],"·")}</span>
                      <div class="od">{oos["desc"]}<br><span class="ov">{oos["vendor"]}</span></div>
                      <div class="oy">
                        <b>{oos["velocity"]}</b>/day<br>
                        <span class="res-tag">{res}</span>
                        {f'<span class="dc-badge">DC: {oos["dc_soh"]}u</span>' if oos.get("dc_soh",0)>0 else ''}
                      </div></div>'''
                    detail_html += '<div class="fg">'
                    for fi,fk in enumerate(FK):
                        on = f_st.get(fk,False)
                        bid= f"fb_{si}_{oi}_{fk}"
                        detail_html += f'''<label onclick="toggleFlag('{fkey}','{fk}','{bid}','ob_{si}_{oi}','sv_{si}_{oi}');return false;">
                          <div class="fb{"  on" if on else ""}" id="{bid}">{"✓" if on else ""}</div>
                          <span class="fl">{FL[fi]}</span></label>'''
                    detail_html += f'<span class="fsv" id="sv_{si}_{oi}">✓ saved</span></div>'
                    detail_html += '<div class="ub"><div class="ul">Best substitute</div>'
                    if oos.get('best_sub_strength'):
                        tc = {'DIRECT':'utd','STRONG':'uts','WEAK':'utw'}.get(oos['best_sub_strength'],'utw')
                        detail_html += f'<div class="ur"><span class="ut {tc}">{oos["best_sub_strength"]}</span><span class="ud">{oos["best_sub_desc"]}</span><span class="us">{oos["best_sub_soh"]}u</span></div>'
                    else:
                        detail_html += '<div class="ns">No substitute — raise PO immediately</div>'
                    detail_html += '</div></div>'
                detail_html += '</div>'

            if sd.get('overstock_skus'):
                detail_html += '<div class="dl" style="margin-top:5px;color:#d97706">⚠️ Overstock (&gt;45 days cover)</div><div class="ow">'
                for ov in sd['overstock_skus'][:4]:
                    detail_html += f'''<div class="ob ob-ov">
                      <div class="oh-ov">
                        <div class="od">{ov["desc"]}<br><span class="ov">{ov["vendor"]}</span></div>
                        <div class="oy"><b>{ov["days_cover"]:.0f}d</b> cover<br>{ov["soh"]}u · {ov["velocity"]}/day</div>
                      </div></div>'''
                detail_html += '</div>'

            if not sd.get('oos_skus') and not sd.get('overstock_skus') and sd.get('covered'):
                detail_html += '<div class="aok">✓ No issues at this store</div>'
            detail_html += '</div></div>'
        detail_html += '</div>'

    flags_json = json.dumps(flags)

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:13px}}
.shell{{display:flex;flex-direction:column;height:780px;border:1px solid #e2ddd8;border-radius:10px;overflow:hidden;background:#fff}}
.kstrip{{display:flex;gap:0;border-bottom:1px solid #e2ddd8;background:#f7f6f3;flex-shrink:0;flex-wrap:wrap}}
.kp{{padding:8px 14px;border-right:1px solid #e2ddd8;min-width:120px}}
.kp-avail{{min-width:220px}}
.kl{{font-size:9px;color:#888;text-transform:uppercase;letter-spacing:.04em;margin-bottom:3px;display:flex;align-items:center;gap:4px}}
.kv{{font-size:20px;font-weight:500;color:#1a1a1a;line-height:1.2}}
.kv.r{{color:#dc2626}}.kv.a{{color:#d97706}}.kv.g{{color:#16a34a}}
.kv-row{{display:flex;gap:12px}}
.kv-s{{font-size:13px;color:#1a1a1a}}
.kv-s b{{font-weight:600}}
.tier-btn{{cursor:pointer;padding:1px 5px;border-radius:3px;font-size:9px;color:#888;border:1px solid #e2ddd8;background:#fff;user-select:none}}
.tier-btn.on{{background:#1a1a1a;color:#fff;border-color:#1a1a1a}}
.main{{display:flex;flex:1;overflow:hidden}}
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
.kp2{{background:#fff;border:1px solid #e2ddd8;border-radius:6px;padding:5px 12px}}
.kv2{{font-size:18px;font-weight:500;color:#1a1a1a;line-height:1.2}}
.kv2.r{{color:#dc2626}}.kv2.a{{color:#d97706}}.kv2.g{{color:#16a34a}}
.sv{{padding:5px 10px;border-radius:6px;font-size:11px;font-weight:500;margin-bottom:8px}}
.sv-u{{background:#fee2e2;color:#b91c1c}}.sv-a{{background:#fef3c7;color:#92400e}}
.sv-n{{background:#dbeafe;color:#1e40af}}.sv-o{{background:#ffedd5;color:#9a3412}}
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
.ob{{border-radius:5px;overflow:hidden;transition:opacity .2s}}
.ob.flagged{{opacity:0.32}}
.ob-u{{border:1px solid #fca5a5}}.ob-a{{border:1px solid #fcd34d}}.ob-n{{border:1px solid #bfdbfe}}.ob-ov{{border:1px solid #fed7aa}}
.oh{{display:flex;align-items:flex-start;gap:5px;padding:5px 8px}}
.ob-u .oh{{background:#fef2f2}}.ob-a .oh{{background:#fffbeb}}.ob-n .oh{{background:#eff6ff}}
.oh-ov{{display:flex;align-items:flex-start;gap:5px;padding:5px 8px;background:#fff7ed}}
.sev-dot{{font-size:11px;flex-shrink:0;margin-top:1px}}
.od{{flex:1;font-size:11px;font-weight:500;color:#1a1a1a;line-height:1.35;min-width:0}}
.ov{{font-size:9px;font-weight:400;color:#888}}
.oy{{font-size:9px;color:#888;flex-shrink:0;text-align:right;line-height:1.6;display:flex;flex-direction:column;align-items:flex-end;gap:2px}}
.res-tag{{font-size:9px;font-weight:600;color:#1e40af;white-space:nowrap}}
.dc-badge{{font-size:9px;background:#dbeafe;color:#1e40af;padding:1px 5px;border-radius:3px}}
.fg{{display:flex;gap:5px;padding:3px 8px;background:#f7f6f3;flex-wrap:wrap;align-items:center}}
.fg label{{display:flex;align-items:center;gap:3px;cursor:pointer;user-select:none}}
.fb{{width:12px;height:12px;border:1px solid #ccc;border-radius:2px;display:flex;align-items:center;justify-content:center;font-size:8px;background:#fff;flex-shrink:0}}
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
.kp2 .kl{{font-size:9px;color:#888;text-transform:uppercase;letter-spacing:.04em}}
</style></head><body>
<div class="shell">
  <div class="kstrip">{kpi_html}</div>
  <div class="main">
    <nav class="nv">
      <div class="nh"><div class="nh-t">Fiz · Availability Briefing</div>
      <div class="nh-s">{kpis.get("file_date","")} · {kpis.get("sku_count",0):,} SKUs</div></div>
      <div class="nb">{nav_html}</div>
    </nav>
    <div class="mn">
      <div class="mb">{mbar_html}</div>
      <div class="ct">{detail_html}</div>
    </div>
  </div>
</div>
<script>
var FLAGS={flags_json};
window._fiz_flags=FLAGS;
function selectSub(cat,sub){{if(window._fiz_setStateValue)window._fiz_setStateValue('selection',{{cat:cat,sub:sub}});}}
function setTier(t){{if(window._fiz_setStateValue)window._fiz_setStateValue('tier',t);}}
function toggleFlag(fkey,fk,bid,oid,sid){{
  if(!FLAGS[fkey])FLAGS[fkey]={{dl:0,os:0,pe:0,dc:0,ssl:0,any:false}};
  FLAGS[fkey][fk]=FLAGS[fkey][fk]?0:1;
  FLAGS[fkey].any=!!(FLAGS[fkey].dl||FLAGS[fkey].os||FLAGS[fkey].pe||FLAGS[fkey].dc||FLAGS[fkey].ssl);
  var b=document.getElementById(bid);if(b){{b.className='fb'+(FLAGS[fkey][fk]?' on':'');b.textContent=FLAGS[fkey][fk]?'✓':'';}}
  var bl=document.getElementById(oid);if(bl)bl.className=bl.className.replace(' flagged','')+(FLAGS[fkey].any?' flagged':'');
  var sv=document.getElementById(sid);if(sv){{sv.className='fsv show';setTimeout(function(){{sv.className='fsv';}},1600);}}
  window._fiz_flags=FLAGS;
  if(window._fiz_setStateValue)window._fiz_setStateValue('flags',FLAGS);
}}
</script></body></html>"""


# ── V2 COMPONENT ─────────────────────────────────────────────────────────────
_BRIEFING_COMPONENT = st.components.v2.component(
    "fiz_briefing_v2",
    html="<div id='root'></div>",
    js="""
export default function(component) {
  const { data, parentElement, setStateValue } = component;
  if (!data || !data.html) return;
  const root = parentElement.querySelector('#root');
  if (!root) return;
  root.style.cssText = 'height:780px;overflow:hidden;';
  root.innerHTML = data.html;
  root.querySelectorAll('script').forEach(function(old) {
    const s = document.createElement('script');
    s.textContent = old.textContent; old.parentNode.replaceChild(s, old);
  });
  root.querySelectorAll('[onclick]').forEach(function(el) {
    const orig = el.getAttribute('onclick'); el.removeAttribute('onclick');
    el.addEventListener('click', function(e) {
      e.stopPropagation();
      window._fiz_setStateValue = setStateValue;
      window._fiz_flags = window._fiz_flags || {};
      try { eval(orig); } catch(err) { console.warn(err); }
    });
  });
  window._fiz_setStateValue = setStateValue;
  window._fiz_flags = data.flags || {};
}
""",
    isolate_styles=False,
)


# ── MAIN APP ──────────────────────────────────────────────────────────────────
st.markdown("""
<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
  <div style="width:36px;height:36px;background:#E8622A;border-radius:8px;
    display:flex;align-items:center;justify-content:center;font-size:20px">📦</div>
  <div>
    <div style="font-size:20px;font-weight:600;color:#1a1a1a">Fiz · Availability Briefing</div>
    <div style="font-size:12px;color:#888">Upload the Master_LIst file to generate the briefing</div>
  </div>
</div>""", unsafe_allow_html=True)

# ── FILE UPLOADS ──────────────────────────────────────────────────────────────
col_inv, col_oh = st.columns([2,2])
with col_inv:
    st.caption("📋 Daily inventory file")
    uploaded_inv = st.file_uploader('Inventory', type=['xlsx'], label_visibility='collapsed', key='inv_upload')
with col_oh:
    st.caption("📦 Order history (upload once — stored automatically)")
    uploaded_oh  = st.file_uploader('Order history', type=['csv'],  label_visibility='collapsed', key='oh_upload')

# ── ORDER HISTORY PERSISTENCE ─────────────────────────────────────────────────
if uploaded_oh is not None:
    oh_bytes = uploaded_oh.read()
    st.session_state['oh_bytes'] = oh_bytes
    st.session_state['oh_name']  = uploaded_oh.name
    st.success(f"✓ Order history loaded: {uploaded_oh.name} — processing velocity...")
elif 'oh_bytes' in st.session_state:
    st.info(f"📦 Using stored order history: {st.session_state.get('oh_name','')}")
else:
    # Try loading pre-computed velocity from GitHub
    if 'vel_ytd' not in st.session_state:
        with st.spinner("Loading velocity data from GitHub..."):
            vel_csv, _ = gh_read("data/velocity_ytd.csv")
            l7_csv, _  = gh_read("data/velocity_l7.csv")
            net_csv, _ = gh_read("data/velocity_net.csv")
            meta, _    = gh_read("data/velocity_meta.txt")
            if vel_csv and l7_csv and net_csv:
                import io as _io2
                st.session_state['vel_ytd']    = pd.read_csv(_io2.StringIO(vel_csv))
                st.session_state['vel_l7']     = pd.read_csv(_io2.StringIO(l7_csv))
                st.session_state['vel_net']    = pd.read_csv(_io2.StringIO(net_csv))
                st.session_state['vel_oh_key'] = 'github'
                st.session_state['oh_name']    = meta.strip() if meta else 'GitHub'
                st.success(f"✓ Velocity data loaded from GitHub ({st.session_state['oh_name']})")

if uploaded_inv is None:
    st.markdown("""
    <div style="background:#f7f6f3;border:1px dashed #d0ccc8;border-radius:8px;
        padding:32px;text-align:center;color:#888;margin-top:8px">
      <div style="font-size:28px;margin-bottom:8px">📂</div>
      <div style="font-size:14px;font-weight:500;color:#555;margin-bottom:4px">Upload the daily Master_LIst file to get started</div>
      <div style="font-size:12px">Order history only needs to be uploaded once</div>
    </div>""", unsafe_allow_html=True)
    st.stop()

# ── COMPUTE VELOCITY ──────────────────────────────────────────────────────────
inv_bytes = uploaded_inv.read()
if 'oh_bytes' in st.session_state:
    inv_temp = pd.read_excel(io.BytesIO(inv_bytes))
    inv_temp.columns = [c.strip() for c in inv_temp.columns]
    inv_temp = inv_temp[inv_temp['Status']=='Active']
    inv_temp['Item ID'] = pd.to_numeric(inv_temp['Item ID'], errors='coerce')
    inv_item_ids = set(inv_temp['Item ID'].dropna().astype(int).tolist())

    oh_key = hash(st.session_state['oh_bytes'])
    if st.session_state.get('vel_oh_key') != oh_key:
        with st.spinner('Processing order history and saving velocity data…'):
            ytd_df, l7_df, net_df, oh_date = process_order_history(
                [st.session_state['oh_bytes']], inv_item_ids)
            st.session_state['vel_ytd']    = ytd_df
            st.session_state['vel_l7']     = l7_df
            st.session_state['vel_net']    = net_df
            st.session_state['vel_oh_key'] = oh_key
            st.session_state['vel_date']   = oh_date
            # Save pre-computed velocity to GitHub for persistence
            _, sha_ytd = gh_read("data/velocity_ytd.csv")
            _, sha_l7  = gh_read("data/velocity_l7.csv")
            _, sha_net = gh_read("data/velocity_net.csv")
            _, sha_meta= gh_read("data/velocity_meta.txt")
            saved = (
                gh_write("data/velocity_ytd.csv", ytd_df.to_csv(index=False), sha_ytd) and
                gh_write("data/velocity_l7.csv",  l7_df.to_csv(index=False),  sha_l7)  and
                gh_write("data/velocity_net.csv",  net_df.to_csv(index=False),  sha_net)  and
                gh_write("data/velocity_meta.txt", st.session_state.get('oh_name','order history'), sha_meta)
            )
            if saved:
                st.success("✓ Velocity data saved to GitHub — won't need to re-upload order history again")
            else:
                st.warning("⚠️ Could not save velocity to GitHub — will need to re-upload order history on next session")
else:
    if 'vel_ytd' not in st.session_state:
        st.warning("⚠️ Upload order history to enable velocity-based analysis.")

# ── RUN ANALYSIS ─────────────────────────────────────────────────────────────
vel_key = str(st.session_state.get('vel_oh_key','none'))
_ytd_json = st.session_state['vel_ytd'].to_json() if 'vel_ytd' in st.session_state and st.session_state['vel_ytd'] is not None else None
_l7_json  = st.session_state['vel_l7'].to_json()  if 'vel_l7'  in st.session_state and st.session_state['vel_l7']  is not None else None
_net_json = st.session_state['vel_net'].to_json()  if 'vel_net'  in st.session_state and st.session_state['vel_net']  is not None else None
with st.spinner('Analysing inventory…'):
    try:
        data, kpis = run_analysis(inv_bytes, uploaded_inv.name, vel_key, _ytd_json, _l7_json, _net_json)
    except Exception as e:
        st.error(f'Error: {e}'); st.exception(e); st.stop()

# ── SESSION STATE ─────────────────────────────────────────────────────────────
if 'cur_cat' not in st.session_state or st.session_state.cur_cat not in data:
    st.session_state.cur_cat  = next(iter(data))
    st.session_state.cur_sub  = data[st.session_state.cur_cat][0]['subcat']
if 'flags'      not in st.session_state: st.session_state.flags      = {}
if 'avail_tier' not in st.session_state: st.session_state.avail_tier = 100

# ── FLAGGED ITEMS VIEW ────────────────────────────────────────────────────────
flagged_tab, briefing_tab = st.tabs(["🚩 Flagged items", "📋 Briefing"])

with flagged_tab:
    flags = st.session_state.flags
    flagged_rows = []
    for cat, items in data.items():
        for r in items:
            for store in ['Jahra','Qurtuba','Sabah Salem']:
                for oi, oos in enumerate(r['stores'].get(store,{}).get('oos_skus',[])):
                    fkey = f"{r['subcat']}|{store}|{oi}"
                    f_st = flags.get(fkey,{})
                    for fk, fl in FLAG_LABELS.items():
                        if f_st.get(fk):
                            flagged_rows.append({
                                'Flag':        fl,
                                'Sub-category':r['subcat'],
                                'Category':    cat,
                                'Store':       store,
                                'SKU':         oos['desc'],
                                'Vendor':      oos['vendor'],
                                'Velocity':    oos['velocity'],
                                'YTD':         oos['ytd'],
                                'RSP':         oos['rsp'],
                                'Resolution':  RESOLUTION_LABELS.get(oos.get('resolution',''),''),
                                'Severity':    oos['severity'],
                            })
    if flagged_rows:
        df_flags = pd.DataFrame(flagged_rows).sort_values(['Flag','Category','Sub-category'])
        st.markdown(f"**{len(df_flags)} flagged items** across {df_flags['Flag'].nunique()} flag types")
        for flag_type, grp in df_flags.groupby('Flag'):
            with st.expander(f"**{flag_type}** — {len(grp)} items", expanded=True):
                st.dataframe(grp.drop(columns=['Flag']).reset_index(drop=True),
                             use_container_width=True, hide_index=True)
        csv = df_flags.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Export all flagged items as CSV", csv,
                           file_name=f"fiz_flagged_{kpis.get('file_date','')}.csv",
                           mime='text/csv')
    else:
        st.info("🚩 No flagged items yet. Check boxes in the briefing to flag OOS SKUs.")

with briefing_tab:
    widget_html = build_widget_html(
        data, kpis,
        st.session_state.cur_cat,
        st.session_state.cur_sub,
        st.session_state.flags,
        st.session_state.avail_tier,
    )
    result = _BRIEFING_COMPONENT(
        key="briefing_v2",
        data={"html": widget_html, "flags": st.session_state.flags},
        on_selection_change=lambda: None,
        on_flags_change=lambda: None,
        on_tier_change=lambda: None,
    )
    if result is not None:
        changed = False
        sel = result.get('selection')
        if sel and isinstance(sel,dict):
            nc,ns = sel.get('cat'),sel.get('sub')
            if nc and ns and (nc!=st.session_state.cur_cat or ns!=st.session_state.cur_sub):
                st.session_state.cur_cat=nc; st.session_state.cur_sub=ns; changed=True
        nf = result.get('flags')
        if nf and nf!=st.session_state.flags:
            st.session_state.flags=nf; changed=True
        nt = result.get('tier')
        if nt and nt!=st.session_state.avail_tier:
            st.session_state.avail_tier=nt; changed=True
        if changed: st.rerun()
