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
    'semi skimmed','fat free','reduced fat','unsalted','salted','whole','wholegrain','wholemeal',
    'full cream','half cream','lactose free','lactose-free'}
CAT_ORDER = ['Dairy & Eggs','Drinks','Confectionary','Fruits & Vegetables','Snacks','Ice Cream',
    'Bakery','Cupboard','Home Care','Personal Care','Water','Frozen Food','Baby','Meats',
    'Health & Lifestyle','Coffee, Tea & Creamer','Pets','Baking Essentials','Ready to Eat','Pharma','Stationary']
SEV_ORDER  = ['URGENT','ACTION','NOTE','OVERSTOCK']
FLAG_KEYS  = ['dl','os','pe','dc','ssl','sf']
FLAG_LABELS= {'dl':'Discontinued here','os':'Out of season','pe':'Promo ended',
              'dc':'Discontinued','ssl':'Supplier service level','sf':'Wrong substitute'}
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
    'grill lite','grill cheese','grill',
    'blue cheese','danablu','manchego','akawi','ackawi','areesh',
    'nabulce','nabulsi','baladi','baladai','braided','shalal','shallal','jeddal',
    'helix','monterey jack','colby','burrata','bulgarian','super sharp',
    'topi','babybel',
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
    'basmati','jasmine','arborio',
    'spaghetti','penne','fusilli','macaroni','linguine','rigatoni',
    'dark chocolate','milk chocolate','white chocolate',
]

STRICT_SUBCATS = {
    # Block cheese — types clearly named (feta, cheddar, brie etc)
    'Block Cheese','Organic Block Cheese',
    # Produce — different fruit/veg types are never subs
    'Fruits','Organic Fruits','Veggies','Organic Veggies','Organic Herbs',
    # Coffee — instant vs ground vs capsule are never subs
    'Ground Coffee & Beans','Instant Coffee','Coffee Capsules','Organic Instant Coffee',
    # Oils — olive vs sunflower are never subs
    'Oils & Ghee','Organic Oils & Ghee',
    # Fish/meat — tuna vs salmon are never subs
    'Canned Fish & Meats','Organic Canned Fish & Meats',
    # Bread — toast vs flatbread are never subs
    'Toast','Flat Bread','Healthy Breads',
}
# Sub-categories where AI handles all pairs (algo only does hard type conflict check)
AI_HANDLED_SUBCATS = {
    'Sliced Cheese','Shredded & Grated Cheese','Spread Cheese',
    'Canned Cheese','Organic Sliced Cheese','Organic Shredded & Grated Cheese',
    'Laban','Greek Yogurt','Plain Yogurt','Flavored Yogurt',
    'Long Life Milk','Fresh Milk','Flavored Milk',
}

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

def sub_quality(oos_rsp, oos_v, oos_d, sub_rsp, sub_v, sub_d, cat, subcat=''):
    if product_types_conflict(oos_d, sub_d):
        return None
    # Strict sub-categories: require positive type token match
    # (skipped for AI_HANDLED_SUBCATS where AI makes the call)
    if subcat in STRICT_SUBCATS and subcat not in AI_HANDLED_SUBCATS:
        t1 = get_product_token(oos_d)
        t2 = get_product_token(sub_d)
        if t1 is None or t2 is None or t1 != t2:
            return None
    ratio = sub_rsp/oos_rsp if oos_rsp>0.01 else 1.0
    pw = 5.0 if cat=='Water' else 3.0; psc = 4.0 if cat=='Water' else 1.8
    if is_organic(oos_d)!=is_organic(sub_d): return 'STRONG'
    if ratio>pw or ratio<(1/pw): return 'WEAK'
    ofl=get_flavour(oos_d); sfl=get_flavour(sub_d)
    ovr=get_variant(oos_d); svr=get_variant(sub_d)
    fcap=False
    if ofl and sfl and ofl!=sfl: return 'WEAK'
    if (ofl and not sfl) or (not ofl and sfl): fcap=True
    # Fat content conflict — different fat levels are never direct substitutes
    FAT_VARIANTS = {'low fat','full fat','fat free','skimmed','semi skimmed',
                    'reduced fat','full cream','half cream','0%','skimmed'}
    _ofat = ovr & FAT_VARIANTS
    _sfat = svr & FAT_VARIANTS
    if _ofat and _sfat and _ofat != _sfat: return None
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


# ── AI SUBSTITUTE ASSESSMENT ──────────────────────────────────────────────────

@st.cache_data(show_spinner=False, ttl=86400)
def load_sub_cache_data():
    """Load cached AI substitute assessments from GitHub."""
    csv_txt, sha = gh_read("data/sub_assessments.csv")
    if csv_txt:
        import io as _sio
        df = pd.read_csv(_sio.StringIO(csv_txt))
        cache = {}
        for _, row in df.iterrows():
            try:
                cache[(int(row['oos_id']), int(row['sub_id']))] = (
                    str(row['strength']), str(row['reason']))
            except: pass
        return cache, sha
    return {}, None

def save_sub_cache_data(cache_dict):
    """Save AI assessments back to GitHub."""
    rows = ["oos_id,sub_id,strength,reason"]
    for (oos_id, sub_id), (strength, reason) in cache_dict.items():
        reason_clean = str(reason).replace(',', ';').replace('\n', ' ')
        rows.append(f"{oos_id},{sub_id},{strength},{reason_clean}")
    _, sha = gh_read("data/sub_assessments.csv")
    gh_write("data/sub_assessments.csv", "\n".join(rows), sha)

def ai_assess_batch(pairs):
    """
    pairs: list of (oos_id, sub_id, oos_desc, oos_vendor, oos_rsp,
                    sub_desc, sub_vendor, sub_rsp, sub_soh, subcat)
    Returns: dict (oos_id, sub_id) -> (strength, reason)
    """
    import requests as _req
    if not pairs: return {}
    results = {}
    BATCH = 10

    for i in range(0, len(pairs), BATCH):
        batch = pairs[i:i+BATCH]
        lines = []
        for j, p in enumerate(batch):
            _, _, od, ov, op, sd, sv, sp, ss, _ = p
            lines.append(
                f"{j+1}. OOS: {od} | {ov} | {op:.3f} KD"
                f" → SUB: {sd} | {sv} | {sp:.3f} KD | {ss}u"
            )
        subcat = batch[0][9]
        prompt = (
            f"Kuwait grocery substitute assessment. Sub-category: {subcat}\n\n"
            + "\n".join(lines)
            + "\n\nFor each pair: is the substitute a DIRECT replacement?\n"
            + "DIRECT = customer would fully accept (same type, same fat content, similar price, same use)\n"
            + "NONE = not a direct substitute\n\n"
            + "IMPORTANT RULES:\n"
            + "- Different fat content = NONE (low fat vs full fat vs fat free vs skimmed vs full cream)\n"
            + "- Different cheese type = NONE (cheddar vs feta vs mozzarella vs halloumi etc)\n"
            + "- Processed cheese vs natural cheese = NONE\n"
            + "- Different milk alternative type = NONE (oat vs almond vs soy vs coconut vs dairy)\n"
            + "- Different fruit or vegetable type = NONE\n\n"
            + "Reply: [n]. [DIRECT/NONE] — [reason max 8 words]"
        )
        try:
            r = _req.post(
                "https://api.anthropic.com/v1/messages",
                headers={"Content-Type": "application/json", "x-api-key": st.secrets.get("ANTHROPIC_API_KEY",""), "anthropic-version": "2023-06-01"},
                json={"model": "claude-sonnet-4-6", "max_tokens": 300,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=30
            )
            if r.status_code == 200:
                text = r.json()["content"][0]["text"]
                for j, p in enumerate(batch):
                    for line in text.split("\n"):
                        line = line.strip()
                        if line.startswith(f"{j+1}."):
                            rest = line[len(f"{j+1}."):].strip()
                            pts = rest.split("—", 1)
                            strength = pts[0].strip().upper()
                            if strength not in ["DIRECT","STRONG","WEAK","NONE"]:
                                strength = "WEAK"
                            reason = pts[1].strip() if len(pts) > 1 else ""
                            results[(p[0], p[1])] = (strength, reason)
                            break
        except: pass
    return results


def find_better_sub(oos_desc, oos_vendor, oos_rsp, oos_id,
                    blacklisted_sub_id, in_stock_items, subcat, ai_cache):
    """
    Called when team flags a substitute as wrong.
    Asks AI to pick the best alternative from remaining in-stock SKUs.
    Returns updated ai_cache with blacklisted pair set to NONE
    and new best pair assessed.
    """
    import requests as _req

    # Blacklist the flagged pair permanently
    ai_cache[(oos_id, blacklisted_sub_id)] = ('NONE', 'Flagged as wrong by team')

    # Build candidate list excluding blacklisted
    candidates = [r for r in in_stock_items if r['item_id'] != blacklisted_sub_id
                  and ai_cache.get((oos_id, r['item_id']), ('',''))[0] != 'NONE']

    if not candidates:
        return ai_cache, None

    cand_lines = []
    for i, c in enumerate(candidates[:10]):
        cand_lines.append(f"{i+1}. {c['desc']} | {c['vendor']} | {c['rsp']:.3f} KD | {c['soh']}u")

    prompt = (
        f"Kuwait grocery app. Sub-category: {subcat}\n\n"
        f"OOS product: {oos_desc} | {oos_vendor} | {oos_rsp:.3f} KD\n"
        f"The team flagged the previous suggestion as WRONG.\n\n"
        f"From these in-stock alternatives, which is the BEST substitute?\n\n"
        + "\n".join(cand_lines)
        + "\n\nReply: [number]. [DIRECT/STRONG/WEAK/NONE] \u2014 [reason \u226410 words]\n"
        "If none are suitable, reply: NONE \u2014 no adequate substitute available"
    )

    try:
        r = _req.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json", "x-api-key": st.secrets.get("ANTHROPIC_API_KEY",""), "anthropic-version": "2023-06-01"},
            json={"model": "claude-sonnet-4-6", "max_tokens": 80,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=20
        )
        if r.status_code == 200:
            text = r.json()["content"][0]["text"].strip()
            if text.upper().startswith("NONE"):
                return ai_cache, None
            # Parse "3. STRONG — same brand different format"
            import re as _re
            m = _re.match(r'(\d+)\.\s*(DIRECT|STRONG|WEAK|NONE)\s*[—-]\s*(.*)', text)
            if m:
                idx = int(m.group(1)) - 1
                strength = m.group(2).upper()
                reason = m.group(3).strip()
                if 0 <= idx < len(candidates):
                    best = candidates[idx]
                    key = (oos_id, best['item_id'])
                    ai_cache[key] = (strength, reason)
                    return ai_cache, best
    except:
        pass

    return ai_cache, None

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

    # Store-level sold sets for assortment availability (90d and 30d)
    _cut90 = today - datetime.timedelta(days=90)
    _cut30 = today - datetime.timedelta(days=30)
    sold_sets = {}
    for _store in ['Jahra','Qurtuba','Sabah Salem']:
        _s = long[long['store_norm']==_store]
        sold_sets[_store] = {
            '90d': set(_s[_s['date']>=_cut90]['item_id'].unique().astype(int).tolist()),
            '30d': set(_s[_s['date']>=_cut30]['item_id'].unique().astype(int).tolist()),
        }

    return ytd, l7, net, str(today), sold_sets


def is_promo(desc):
    """Returns True if SKU description indicates a promotional item."""
    import re as _re
    d = str(desc).lower()
    if _re.search(r'\bpromo\b', d): return True
    if _re.search(r'special offer', d): return True
    if _re.search(r'\bbonus pack\b', d): return True
    if _re.search(r'\d+\+\d+\s*free', d): return True
    if _re.search(r'\b\d+\+1\b', d): return True
    if _re.search(r'promo pack', d): return True
    if _re.search(r'value pack', d): return True
    if _re.search(r'gift pack', d): return True
    if _re.search(r'twin pack', d): return True
    if _re.search(r'\bbundle\b', d): return True
    return False


# ── FLAG HELPERS ──────────────────────────────────────────────────────────────
PERMANENT_FLAGS   = {'dl', 'dc'}     # hide from briefing + exclude from availability
OPERATIONAL_FLAGS = {'os', 'pe', 'ssl'}  # dim in briefing + exclude from KPIs

def flag_state(item_id, store, oi, flags):
    """Returns ('hidden', 'dimmed', or 'normal') for an OOS SKU."""
    fkey = f"{store}|{item_id}"
    # Try both key formats
    for k in [fkey, f"{store}|{item_id}|{oi}"]:
        fval = flags.get(k, {})
        if any(fval.get(f) for f in PERMANENT_FLAGS):
            return 'hidden'
        if any(fval.get(f) for f in OPERATIONAL_FLAGS):
            return 'dimmed'
    return 'normal'

def get_flagged_item_ids(flags, flag_types):
    """Returns set of item_ids that have any of the given flag types set."""
    ids = set()
    for fkey, fval in flags.items():
        if any(fval.get(f) for f in flag_types):
            # Extract item_id from key formats: "store|item_id" or "subcat|store|oi"
            parts = fkey.split('|')
            for p in parts:
                try:
                    ids.add(int(p))
                except: pass
    return ids

# ── MAIN ANALYSIS ─────────────────────────────────────────────────────────────
SEV_ORDER_SUB = ['DIRECT']

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
                best_sub_reason = ""
                # Step 1: algo pre-filter (instant, free)
                candidates = []
                for _, s_row in in_stock_df.iterrows():
                    if s_row['Item ID'] == oos['Item ID']: continue
                    algo_str = sub_quality(
                        float(oos.get('RSP',0)), str(oos.get('Vendor','')), str(oos.get('Description','')),
                        float(s_row.get('RSP',0)), str(s_row.get('Vendor','')), str(s_row.get('Description','')),
                        cat, subcat)
                    if algo_str is None: continue
                    candidates.append((s_row, algo_str))
                # Step 2: use AI cache if available, else fall back to algo result
                ai_cache = st.session_state.get('ai_sub_cache', {})
                for s_row, algo_str in candidates:
                    key = (int(oos['Item ID']), int(s_row['Item ID']))
                    if key in ai_cache:
                        strength, reason = ai_cache[key]
                        # Only DIRECT counts
                        if strength != 'DIRECT': continue
                    else:
                        # No AI result yet — use algo as fallback (DIRECT only)
                        if algo_str != 'DIRECT': continue
                        strength = 'DIRECT'
                        reason = ""
                        # Queue for AI verification
                        if '_ai_queue' not in st.session_state:
                            st.session_state['_ai_queue'] = []
                        queue_item = (
                            int(oos['Item ID']), int(s_row['Item ID']),
                            str(oos.get('Description','')), str(oos.get('Vendor','')),
                            float(oos.get('RSP',0)),
                            str(s_row['Description']), str(s_row.get('Vendor','')),
                            float(s_row.get('RSP',0)), int(s_row[soh_col]), subcat
                        )
                        if queue_item not in st.session_state['_ai_queue']:
                            st.session_state['_ai_queue'].append(queue_item)
                    best_str = 'DIRECT'
                    best_sub_desc = str(s_row['Description'])[:45]
                    best_sub_soh = int(s_row[soh_col])
                    best_sub_reason = reason
                    break  # Found a DIRECT — stop looking

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

                # Severity — DIRECT substitute only
                v = float(oos.get('true_daily',0))
                has_direct = (best_str == 'DIRECT')
                if v >= 5 and not has_direct:
                    sev = 'URGENT'
                elif v >= 0.5 and not has_direct:
                    sev = 'ACTION'
                elif has_direct:
                    sev = 'NOTE'
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
                    'best_sub_reason':   best_sub_reason,
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

    kpis['top_ids'] = {}  # computed live in main app

    # Save any new AI assessments to GitHub cache
    if st.session_state.get('ai_cache_dirty') and st.session_state.get('ai_sub_cache'):
        save_sub_cache_data(st.session_state['ai_sub_cache'])
        st.session_state['ai_cache_dirty'] = False

    return ordered, kpis


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
        kpis['skus_at_risk'] = int((oos_vel['true_daily']>=5).sum())
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
    _hidden_ids_w  = get_flagged_item_ids(flags, PERMANENT_FLAGS)
    _dimmed_ids_w  = get_flagged_item_ids(flags, OPERATIONAL_FLAGS)
    # Filter to only show sub-cats/SKUs relevant to selected tier
    top_ids = set(kpis.get('top_ids', {}).get(avail_tier, []))
    SI   = {'URGENT':'🔴','ACTION':'🟡','NOTE':'🔵','OVERSTOCK':'🟠'}
    SEVC = {'URGENT':'sv-u','ACTION':'sv-a','NOTE':'sv-n','OVERSTOCK':'sv-o'}
    SEVL = {'URGENT':'🔴 Urgent — high-velocity OOS, no adequate substitute',
            'ACTION':'🟡 Action needed — OOS with substitute available or moderate velocity',
            'NOTE':  '🔵 Note — low-velocity OOS',
            'OVERSTOCK':'🟠 Overstock — SKUs exceeding 45 days cover'}
    RTL  = {'FRESH':'Fresh · supplier-direct','PRODUCE':'Produce · supplier-direct',
            'NON-FRESH':'Non-fresh · transfer eligible'}
    RTC  = {'FRESH':'chip-f','PRODUCE':'chip-p','NON-FRESH':'chip-n'}
    FL   = ['Discontinued here','Out of season','Promo ended','Discontinued','Supplier service level','Wrong substitute']
    FK   = ['dl','os','pe','dc','ssl','sf']

    # ── NAV ───────────────────────────────────────────────────────────────────
    nav_html = ''
    # Apply top N filter — top_ids is a set of item_ids for selected tier
    # If top_ids is empty or None, show everything
    def _in_top(r):
        if not top_ids:  # empty set or None = show all
            return True
        for st_data in r['stores'].values():
            for o in st_data.get('oos_skus',[]):
                try:
                    if int(o.get('item_id',0)) in top_ids: return True
                except: pass
            for o in st_data.get('overstock_skus',[]):
                try:
                    if int(o.get('item_id',0)) in top_ids: return True
                except: pass
        return False

    for cat, items in data.items():
        items = [r for r in items if _in_top(r)]
        if not items: continue
        # Skip sub-cats where all OOS items are permanently flagged (hidden)
        def _has_visible_oos(r):
            for sd in r['stores'].values():
                for o in sd.get('oos_skus',[]):
                    if int(o.get('item_id',0)) not in _hidden_ids_w:
                        return True
            return False
        items = [r for r in items if _has_visible_oos(r) or r.get('overstock_skus')]
        if not items: continue
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
      <div class="kp kp-click" onclick="selectKpi('rev_risk')"><div class="kl">Revenue at risk · no direct sub ↗</div><div class="kv r">{kpis.get("rev_risk",0):,.0f} KD/day</div></div>
      <div class="kp"><div class="kl">SKUs at risk (vel≥2)</div><div class="kv r">{kpis.get("skus_at_risk",0)}</div></div>
      <div class="kp kp-avail">
        <div class="kl">Availability · Top {avail_tier}</div>
        <div class="kv-row">
          <span class="kv-s">Network <b>{avail['network']}%</b></span>
          <span class="kv-s">Full coverage <b>{avail['full3']}%</b></span>
        </div>
      </div>
      <div class="kp kp-click" onclick="selectKpi('dc_opps')"><div class="kl">DC transfer opps ↗</div><div class="kv g">{kpis.get("dc_opps",0)}</div></div>
      <div class="kp kp-click" onclick="selectKpi('overstock')"><div class="kl">Real overstock ↗</div><div class="kv a">{kpis.get("overstock_count",0)}</div></div>
      <div class="kp kp-click" onclick="selectKpi('dead_stock')"><div class="kl">Dead stock ↗</div><div class="kv a">{kpis.get("dead_stock_count",0)}</div></div>
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

            # Filter OOS to top N only
            _oos_filtered = [o for o in sd.get('oos_skus',[])
                             if top_ids is None or int(o.get('item_id',0)) in top_ids]
            if _oos_filtered:
                sd = dict(sd); sd['oos_skus'] = _oos_filtered
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
                    _oos_id = int(oos.get('item_id',0))
                    if _oos_id in _hidden_ids_w:
                        continue  # skip permanently flagged items entirely
                    _is_dimmed = _oos_id in _dimmed_ids_w
                    _dim_style = 'opacity:0.4;' if _is_dimmed else ''
                    if _is_dimmed:
                        detail_html += f'<div class="oi" style="{_dim_style}"><div class="on">{oos["desc"][:52]}</div><div class="ov">{oos["vendor"][:25]}</div><div class="os" style="color:#888">⚑ Flagged — excluded from KPIs</div></div>'
                        continue
                    if oos.get('best_sub_strength') == 'DIRECT':
                        reason_txt = oos.get('best_sub_reason','')
                        reason_html = f' <span style="font-size:9px;color:#888">· {reason_txt}</span>' if reason_txt else ''
                        detail_html += f'<div class="ur"><span class="ut utd">DIRECT</span><span class="ud">{oos["best_sub_desc"]}{reason_html}</span><span class="us">{oos["best_sub_soh"]}u</span></div>'
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
function selectKpi(kpi){{if(window._fiz_setStateValue)window._fiz_setStateValue('kpi_drill',kpi);}}
function toggleFlag(fkey,fk,bid,oid,sid){{
  if(!FLAGS[fkey])FLAGS[fkey]={{dl:0,os:0,pe:0,dc:0,ssl:0,any:false}};
  FLAGS[fkey][fk]=FLAGS[fkey][fk]?0:1;
  FLAGS[fkey].any=!!(FLAGS[fkey].dl||FLAGS[fkey].os||FLAGS[fkey].pe||FLAGS[fkey].dc||FLAGS[fkey].ssl||FLAGS[fkey].sf);
  var b=document.getElementById(bid);if(b){{b.className='fb'+(FLAGS[fkey][fk]?' on':'');b.textContent=FLAGS[fkey][fk]?'✓':'';}}
  var bl=document.getElementById(oid);if(bl)bl.className=bl.className.replace(' flagged','')+(FLAGS[fkey].any?' flagged':'');
  var sv=document.getElementById(sid);if(sv){{sv.className='fsv show';setTimeout(function(){{sv.className='fsv';}},1600);}}
  window._fiz_flags=FLAGS;
  if(window._fiz_setStateValue)window._fiz_setStateValue('flags',FLAGS);
}}
</script></body></html>"""


# ── V2 COMPONENT ─────────────────────────────────────────────────────────────
_BRIEFING_COMPONENT = st.components.v2.component(
    "fiz_briefing_v3",
    html="<div id='root'></div>",
    js="""
export default function(component) {
  const { data, parentElement, setStateValue } = component;
  if (!data || !data.html) return;
  const root = parentElement.querySelector('#root');
  if (!root) return;

  // Only re-render if content changed
  if (root._lastHtmlKey === data.key) {
    // Just update the setStateValue reference
    window._fiz_setStateValue = setStateValue;
    return;
  }
  root._lastHtmlKey = data.key;
  root.style.cssText = 'height:780px;overflow:hidden;';
  root.innerHTML = data.html;

  // Execute inline scripts
  root.querySelectorAll('script').forEach(function(old) {
    const s = document.createElement('script');
    s.textContent = old.textContent;
    old.parentNode.replaceChild(s, old);
  });

  // Wire onclick handlers — keep setStateValue in scope
  root.querySelectorAll('[onclick]').forEach(function(el) {
    const orig = el.getAttribute('onclick');
    el.removeAttribute('onclick');
    el.addEventListener('click', function(e) {
      window._fiz_setStateValue = setStateValue;
      window._fiz_flags = window._fiz_flags || {};
      try {
        // Strip 'return false' so click propagates naturally
        const code = orig.split('return false').join('');
        eval(code);
      } catch(err) { console.warn('fiz click err:', err, orig); }
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
                # Load sold_sets
                import json as _json_ss2
                _ss_raw, _ = gh_read("data/sold_sets.json")
                if _ss_raw:
                    _ss_loaded = _json_ss2.loads(_ss_raw)
                    st.session_state['sold_sets'] = {
                        store: {k: set(v) for k,v in sv.items()}
                        for store, sv in _ss_loaded.items()}
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
st.session_state['inv_bytes_cache'] = inv_bytes  # cache for KPI drill-down tab
if 'oh_bytes' in st.session_state:
    inv_temp = pd.read_excel(io.BytesIO(inv_bytes))
    inv_temp.columns = [c.strip() for c in inv_temp.columns]
    inv_temp = inv_temp[inv_temp['Status']=='Active']
    inv_temp['Item ID'] = pd.to_numeric(inv_temp['Item ID'], errors='coerce')
    inv_item_ids = set(inv_temp['Item ID'].dropna().astype(int).tolist())

    oh_key = hash(st.session_state['oh_bytes'])
    if st.session_state.get('vel_oh_key') != oh_key:
        with st.spinner('Processing order history and saving velocity data…'):
            ytd_df, l7_df, net_df, oh_date, sold_sets = process_order_history(
                [st.session_state['oh_bytes']], inv_item_ids)
            st.session_state['vel_ytd']    = ytd_df
            st.session_state['vel_l7']     = l7_df
            st.session_state['vel_net']    = net_df
            st.session_state['vel_oh_key'] = oh_key
            st.session_state['vel_date']   = oh_date
            st.session_state['sold_sets']  = sold_sets
            # Save pre-computed velocity to GitHub for persistence
            _, sha_ytd = gh_read("data/velocity_ytd.csv")
            _, sha_l7  = gh_read("data/velocity_l7.csv")
            _, sha_net = gh_read("data/velocity_net.csv")
            _, sha_meta= gh_read("data/velocity_meta.txt")
            import json as _json_ss
            _, sha_ss = gh_read("data/sold_sets.json")
            # Convert sets to lists for JSON serialization
            _ss_json = {store: {k: list(v) for k,v in sv.items()}
                        for store, sv in sold_sets.items()}
            saved = (
                gh_write("data/velocity_ytd.csv", ytd_df.to_csv(index=False), sha_ytd) and
                gh_write("data/velocity_l7.csv",  l7_df.to_csv(index=False),  sha_l7)  and
                gh_write("data/velocity_net.csv",  net_df.to_csv(index=False),  sha_net)  and
                gh_write("data/velocity_meta.txt", st.session_state.get('oh_name','order history'), sha_meta) and
                gh_write("data/sold_sets.json", _json_ss(_ss_json), sha_ss)
            )
            if saved:
                st.success("✓ Velocity data saved to GitHub — won't need to re-upload order history again")
            else:
                st.warning("⚠️ Could not save velocity to GitHub — will need to re-upload order history on next session")
else:
    if 'vel_ytd' not in st.session_state:
        st.warning("⚠️ Upload order history to enable velocity-based analysis.")

# ── RUN ANALYSIS ─────────────────────────────────────────────────────────────
vel_key = str(st.session_state.get('vel_oh_key','none')) + '_v24'
_ytd_json = st.session_state['vel_ytd'].to_json() if 'vel_ytd' in st.session_state and st.session_state['vel_ytd'] is not None else None
_l7_json  = st.session_state['vel_l7'].to_json()  if 'vel_l7'  in st.session_state and st.session_state['vel_l7']  is not None else None
_net_json = st.session_state['vel_net'].to_json()  if 'vel_net'  in st.session_state and st.session_state['vel_net']  is not None else None
# Load master table + AI cache from GitHub on startup
if 'ai_sub_cache' not in st.session_state:
    with st.spinner('Loading substitute data from GitHub…'):
        # Load master table first (permanent, sub-cat level)
        _mt_csv, _ = gh_read("data/sub_master.csv")
        _master_cache = {}
        if _mt_csv:
            import io as _io_mt_load
            _mt_df_load = pd.read_csv(_io_mt_load.StringIO(_mt_csv))
            for _, _row in _mt_df_load.iterrows():
                try:
                    _master_cache[(int(_row['oos_id']), int(_row['sub_id']))] = (
                        str(_row['strength']), str(_row['reason']))
                except: pass

        # Load session AI cache (ad-hoc assessments)
        _ai_cache, _ = load_sub_cache_data()

        # Merge: master table takes priority over session cache
        _combined = {**_ai_cache, **_master_cache}
        st.session_state['ai_sub_cache'] = _combined
        st.session_state['ai_cache_dirty'] = False

        _master_subcats = len(_mt_df_load['subcat'].unique()) if _mt_csv and len(_master_cache) > 0 else 0
        if _master_subcats > 0:
            st.success(f"✓ Master table: {len(_master_cache):,} pairs ({_master_subcats} sub-cats) + {len(_ai_cache):,} session assessments")
        elif _ai_cache:
            st.success(f"✓ {len(_ai_cache):,} substitute assessments loaded from cache")

with st.spinner('Analysing inventory…'):
    try:
        data, kpis = run_analysis(inv_bytes, uploaded_inv.name, vel_key, _ytd_json, _l7_json, _net_json)
    except Exception as e:
        st.error(f'Error: {e}'); st.exception(e); st.stop()

# ── SESSION STATE ─────────────────────────────────────────────────────────────
if 'cur_cat' not in st.session_state or st.session_state.cur_cat not in data:
    st.session_state.cur_cat  = next(iter(data))
    st.session_state.cur_sub  = data[st.session_state.cur_cat][0]['subcat']
if 'flags' not in st.session_state:
    _saved_flags, _ = gh_read("data/flags.json")
    if _saved_flags:
        try:
            st.session_state.flags = json.loads(_saved_flags)
        except:
            st.session_state.flags = {}
    else:
        st.session_state.flags = {}
if 'avail_tier' not in st.session_state: st.session_state.avail_tier = 100

# ── FLAGGED ITEMS VIEW ────────────────────────────────────────────────────────
# ── NATIVE KPI STRIP ─────────────────────────────────────────────────────────
avail = kpis.get('avail',{}).get(st.session_state.avail_tier,{'network':0,'full3':0,'oos_n':0})

# Compute severity counts live based on current tier filter
_tier_now = st.session_state.avail_tier
_vel_net_kpi = st.session_state.get('vel_net')
if _tier_now > 0 and _vel_net_kpi is not None:
    _top_ids_kpi = set(_vel_net_kpi.nlargest(_tier_now,'net_ytd')['item_id'].astype(int).tolist())
else:
    _top_ids_kpi = None  # All — no filter

def _subcat_in_top_kpi(r):
    if _top_ids_kpi is None: return True
    for _sd in r['stores'].values():
        for _o in _sd.get('oos_skus',[]):
            if int(_o.get('item_id',0)) in _top_ids_kpi: return True
    return False

_filtered_data = {cat: [r for r in items if _subcat_in_top_kpi(r)]
                  for cat, items in data.items()}
_filtered_data = {cat: items for cat, items in _filtered_data.items() if items}

# Exclude flagged items from severity counts
_flags_now = st.session_state.get('flags', {})
_hidden_ids   = get_flagged_item_ids(_flags_now, PERMANENT_FLAGS)
_dimmed_ids   = get_flagged_item_ids(_flags_now, OPERATIONAL_FLAGS)
_excluded_ids = _hidden_ids | _dimmed_ids  # both excluded from KPI counts

def _oos_counts(data_dict, sev):
    count = 0
    for v in data_dict.values():
        for r in v:
            for sd in r['stores'].values():
                for o in sd.get('oos_skus',[]):
                    if r['severity']==sev and int(o.get('item_id',0)) not in _excluded_ids:
                        count += 1
                        break  # count subcat-store once
    return count

_live_u = sum(1 for v in _filtered_data.values() for r in v if r['severity']=='URGENT'
              and not all(int(o.get('item_id',0)) in _excluded_ids
                         for sd in r['stores'].values()
                         for o in sd.get('oos_skus',[])))
_live_a = sum(1 for v in _filtered_data.values() for r in v if r['severity']=='ACTION'
              and not all(int(o.get('item_id',0)) in _excluded_ids
                         for sd in r['stores'].values()
                         for o in sd.get('oos_skus',[])))
_live_n = sum(1 for v in _filtered_data.values() for r in v if r['severity']=='NOTE'
              and not all(int(o.get('item_id',0)) in _excluded_ids
                         for sd in r['stores'].values()
                         for o in sd.get('oos_skus',[])))

_k1,_k2,_k3,_k4,_k5,_k6,_k7 = st.columns(7)
_k1.metric("🔴 Urgent",        _live_u)
_k2.metric("🟡 Action",        _live_a)
_k3.metric("🔵 Note",          _live_n)
_k4.metric(f"OOS vel≥2/day", kpis.get('skus_at_risk',0))
_k5.metric("DC transfer opps", kpis.get('dc_opps',0))
_k6.metric("Real overstock",   kpis.get('overstock_count',0))
_k7.metric("Dead stock",       kpis.get('dead_stock_count',0))

_ab1,_ab2,_ab3,_ab4,_ab4b,_ab5,_ab6 = st.columns([1,1,1,1,1,2,2])
with _ab1:
    if st.button("Top 100",  type="primary" if st.session_state.avail_tier==100  else "secondary", use_container_width=True, key="tier_100"):
        st.session_state.avail_tier=100;  st.rerun()
with _ab2:
    if st.button("Top 200",  type="primary" if st.session_state.avail_tier==200  else "secondary", use_container_width=True, key="tier_200"):
        st.session_state.avail_tier=200;  st.rerun()
with _ab3:
    if st.button("Top 500",  type="primary" if st.session_state.avail_tier==500  else "secondary", use_container_width=True, key="tier_500"):
        st.session_state.avail_tier=500;  st.rerun()
with _ab4:
    if st.button("Top 1K",   type="primary" if st.session_state.avail_tier==1000 else "secondary", use_container_width=True, key="tier_1k"):
        st.session_state.avail_tier=1000; st.rerun()
with _ab4b:
    if st.button("All",      type="primary" if st.session_state.avail_tier==0    else "secondary", use_container_width=True, key="tier_all"):
        st.session_state.avail_tier=0;    st.rerun()
with _ab5:
    # Compute per-store availability live
    _live_avail = {'network': 0, 'jahra': 0, 'qurtuba': 0, 'ss': 0, 'oos_n': 0}
    _vel_net = st.session_state.get('vel_net')
    _inv_bytes_avail = st.session_state.get('inv_bytes_cache')
    if _vel_net is not None and _inv_bytes_avail is not None:
        try:
            import io as _io_av
            _inv_av = pd.read_excel(io.BytesIO(_inv_bytes_avail))
            _inv_av.columns = [c.strip() for c in _inv_av.columns]
            _inv_av = _inv_av[_inv_av['Status']=='Active'].copy()
            _inv_av['Item ID'] = pd.to_numeric(_inv_av['Item ID'], errors='coerce')
            for _c in ['Jahra Dark Store Stock','Qurtuba Dark Store Stock',
                       'Sabah Salem Dark Store Stock','Total SOH']:
                if _c in _inv_av.columns:
                    _inv_av[_c] = pd.to_numeric(_inv_av[_c], errors='coerce').fillna(0)
            _top_n_av = st.session_state.avail_tier
            _flags_avail = st.session_state.get('flags', {})
            _hidden_avail = get_flagged_item_ids(_flags_avail, PERMANENT_FLAGS)
            if _top_n_av > 0:
                _top_ids_av = set(_vel_net.nlargest(_top_n_av,'net_ytd')['item_id'].astype(int).tolist())
                _top_inv_av = _inv_av[_inv_av['Item ID'].isin(_top_ids_av) &
                                      ~_inv_av['Item ID'].isin(_hidden_avail)]
                _n = len(_top_inv_av)
            else:
                _top_inv_av = _inv_av[~_inv_av['Item ID'].isin(_hidden_avail)]
                _n = len(_top_inv_av)
            if _n > 0:
                _oos_av   = (_top_inv_av['Total SOH']==0).sum()
                _jahra_av = (_top_inv_av['Jahra Dark Store Stock']>0).sum()
                _qurt_av  = (_top_inv_av['Qurtuba Dark Store Stock']>0).sum()
                _ss_av    = (_top_inv_av['Sabah Salem Dark Store Stock']>0).sum()
                _live_avail = {
                    'network': round((_n-_oos_av)/_n*100,1),
                    'jahra':   round(_jahra_av/_n*100,1),
                    'qurtuba': round(_qurt_av/_n*100,1),
                    'ss':      round(_ss_av/_n*100,1),
                    'oos_n':   int(_oos_av)
                }
        except: pass
    _tier_label = f"Top {st.session_state.avail_tier}" if st.session_state.avail_tier > 0 else "All"
    st.metric(f"Network availability · {_tier_label}",
              f"{_live_avail['network']}%",
              delta=f"-{_live_avail['oos_n']} fully OOS", delta_color="inverse")
with _ab6:
    # Per-store with 3 tiers each
    _sold_sets = st.session_state.get('sold_sets', {})
    _inv_bytes_ss = st.session_state.get('inv_bytes_cache')
    _store_avail = {}
    if _inv_bytes_ss:
        try:
            import io as _io_ss
            _inv_ss = pd.read_excel(io.BytesIO(_inv_bytes_ss))
            _inv_ss.columns = [c.strip() for c in _inv_ss.columns]
            _inv_ss = _inv_ss[_inv_ss['Status']=='Active'].copy()
            _inv_ss['Item ID'] = pd.to_numeric(_inv_ss['Item ID'], errors='coerce')
            _all_ids_ss = set(_inv_ss['Item ID'].dropna().astype(int).tolist())
            _scols = {'Jahra':'Jahra Dark Store Stock',
                      'Qurtuba':'Qurtuba Dark Store Stock',
                      'Sabah Salem':'Sabah Salem Dark Store Stock'}
            # Mark promo SKUs
            _inv_ss['_is_promo'] = _inv_ss['Description'].apply(is_promo)
            _core_ids_ss = set(_inv_ss[~_inv_ss['_is_promo']]['Item ID'].dropna().astype(int).tolist())
            for _st2, _sc2 in _scols.items():
                if _sc2 in _inv_ss.columns:
                    _inv_ss[_sc2] = pd.to_numeric(_inv_ss[_sc2], errors='coerce').fillna(0)
                    _in_stk = set(_inv_ss[_inv_ss[_sc2]>0]['Item ID'].dropna().astype(int).tolist())
                    _s90 = _sold_sets.get(_st2,{}).get('90d', set())
                    _s30 = _sold_sets.get(_st2,{}).get('30d', set())
                    _core_in_stk = _in_stk & _core_ids_ss
                    _core_s90 = _s90 & _core_ids_ss
                    _core_s30 = _s30 & _core_ids_ss
                    _store_avail[_st2] = {
                        'full':      round(len(_in_stk)/len(_all_ids_ss)*100,1) if _all_ids_ss else 0,
                        '90d':       round(len(_in_stk & _s90)/len(_s90)*100,1) if _s90 else 0,
                        '30d':       round(len(_in_stk & _s30)/len(_s30)*100,1) if _s30 else 0,
                        'core_full': round(len(_core_in_stk)/len(_core_ids_ss)*100,1) if _core_ids_ss else 0,
                        'core_90d':  round(len(_core_in_stk & _core_s90)/len(_core_s90)*100,1) if _core_s90 else 0,
                        'core_30d':  round(len(_core_in_stk & _core_s30)/len(_core_s30)*100,1) if _core_s30 else 0,
                    }
        except: pass
    _c_j, _c_q, _c_ss2 = st.columns(3)
    for _col2, _stn in [(_c_j,'Jahra'),(_c_q,'Qurtuba'),(_c_ss2,'Sabah Salem')]:
        _sa = _store_avail.get(_stn, {'full':0,'90d':0,'30d':0,'core_full':0,'core_90d':0,'core_30d':0})
        _col2.markdown(f"**{_stn}**")
        _col2.markdown(
            f"All: **{_sa['full']}%** | 90d: **{_sa['90d']}%** | 30d: **{_sa['30d']}%**  \n"
            f"*Ex-promo:* **{_sa['core_full']}%** | **{_sa['core_90d']}%** | **{_sa['core_30d']}%**"
        )

st.divider()

flagged_tab, briefing_tab, kpi_tab, admin_tab = st.tabs(["🚩 Flagged items", "📋 Briefing", "📊 KPI Drill-down", "⚙️ Master Table"])

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

    # AI enrichment button
    _queue = st.session_state.get('_ai_queue', [])
    _cached = len(st.session_state.get('ai_sub_cache', {}))
    _col_ai1, _col_ai2 = st.columns([2,6])
    with _col_ai1:
        _btn_label = f"🤖 Enrich substitutes with AI ({len(_queue)} pairs to assess)" if _queue else f"✓ AI enriched ({_cached:,} pairs cached)"
        _btn_disabled = len(_queue) == 0
        if st.button(_btn_label, disabled=_btn_disabled, key="ai_enrich_btn"):
            with st.spinner(f"Assessing {len(_queue)} substitute pairs with AI… (may take 1-2 minutes)"):
                if _queue:
                    new_results = ai_assess_batch(_queue)
                    ai_cache = st.session_state.get('ai_sub_cache', {})
                    ai_cache.update(new_results)
                    st.session_state['ai_sub_cache'] = ai_cache
                    st.session_state['_ai_queue'] = []
                    save_sub_cache_data(ai_cache)
                    st.success(f"✓ {len(new_results)} pairs assessed and cached. Reloading…")
                    st.rerun()

    # Compute top_ids live so nav filter always reflects current tier
    _vel_net_live = st.session_state.get('vel_net')
    _tier_live = st.session_state.avail_tier
    if _vel_net_live is not None and _tier_live > 0:
        _live_top_ids = set(_vel_net_live.nlargest(_tier_live,'net_ytd')['item_id'].astype(int).tolist())
        kpis['top_ids'] = {_tier_live: list(_live_top_ids)}
    else:
        kpis['top_ids'] = {}  # empty = show all

    widget_html = build_widget_html(
        data, kpis,
        st.session_state.cur_cat,
        st.session_state.cur_sub,
        st.session_state.flags,
        st.session_state.avail_tier,
    )
    result = _BRIEFING_COMPONENT(
        key=f"briefing_v3_{st.session_state.avail_tier}",
        data={"html": widget_html, "flags": st.session_state.flags,
              "key": f"{st.session_state.cur_cat}|{st.session_state.cur_sub}|{len(st.session_state.flags)}|{st.session_state.avail_tier}"},
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
            # Check for new 'wrong substitute' flags and save to GitHub
            for fkey, fval in nf.items():
                old_fval = st.session_state.flags.get(fkey, {})
                if fval.get('sf') and not old_fval.get('sf'):
                    # New wrong substitute flag — append to sub_feedback.csv
                    parts = fkey.split('|')
                    if len(parts) >= 2:
                        _subcat, _store = parts[0], parts[1]
                        _oi = int(parts[2]) if len(parts) > 2 else 0
                        _oos_desc = ''
                        _sub_desc = ''
                        _strength = ''
                        try:
                            _r = next((r for cat_items in data.values()
                                      for r in cat_items if r['subcat']==_subcat), None)
                            if _r:
                                _oos = _r['stores'].get(_store,{}).get('oos_skus',[])
                                if _oi < len(_oos):
                                    _oos_desc = _oos[_oi].get('desc','')
                                    _sub_desc = _oos[_oi].get('best_sub_desc','')
                                    _strength = _oos[_oi].get('best_sub_strength','')
                        except: pass
                        _fb_row = f"{kpis.get('file_date','')},{_subcat},{_store},{_oos_desc},{_sub_desc},{_strength},wrong_substitute\n"
                        _fb_csv, _fb_sha = gh_read("data/sub_feedback.csv")
                        if _fb_csv is None:
                            _fb_csv = "date,subcat,store,oos_desc,sub_desc,algo_strength,feedback\n"
                        gh_write("data/sub_feedback.csv", _fb_csv + _fb_row, _fb_sha)
            # Auto-clear operational flags for SKUs now back in stock
            PERSISTENT_FLAGS = {'dl', 'dc'}  # Discontinued here, Discontinued
            if 'inv_bytes_cache' in st.session_state:
                try:
                    import io as _io3
                    _inv_check = pd.read_excel(io.BytesIO(st.session_state['inv_bytes_cache']))
                    _inv_check.columns = [c.strip() for c in _inv_check.columns]
                    _inv_check['Item ID'] = pd.to_numeric(_inv_check['Item ID'], errors='coerce')
                    _inv_check['Total SOH'] = pd.to_numeric(_inv_check.get('Total SOH', 0), errors='coerce').fillna(0)
                    _in_stock_ids = set(_inv_check[_inv_check['Total SOH']>0]['Item ID'].dropna().astype(int).tolist())
                    keys_to_clear = []
                    for _fkey, _fval in nf.items():
                        # fkey format: "subcat|store|oi" — need item_id
                        # Check via data if this OOS SKU is now back in stock
                        _fparts = _fkey.split('|')
                        if len(_fparts) >= 3:
                            _fsubcat, _fstore, _foi = _fparts[0], _fparts[1], int(_fparts[2])
                            _fr = next((r for cat_items in data.values()
                                       for r in cat_items if r['subcat']==_fsubcat), None)
                            if _fr:
                                _foos_list = _fr['stores'].get(_fstore,{}).get('oos_skus',[])
                                if _foi < len(_foos_list):
                                    _fitem_id = _foos_list[_foi].get('item_id',0)
                                    if _fitem_id in _in_stock_ids:
                                        # SKU back in stock — clear non-persistent flags
                                        for _fk in list(_fval.keys()):
                                            if _fk not in PERSISTENT_FLAGS and _fk != 'any':
                                                nf[_fkey][_fk] = 0
                                        nf[_fkey]['any'] = any(
                                            nf[_fkey].get(k,0) for k in PERSISTENT_FLAGS)
                except:
                    pass
            st.session_state.flags=nf
            # Persist flags to GitHub on every change
            try:
                _fj = json.dumps(nf)
                _, _fs = gh_read("data/flags.json")
                gh_write("data/flags.json", _fj, _fs)
            except Exception as _fe:
                pass
            changed=True
        nt = result.get('tier')
        if nt and nt!=st.session_state.avail_tier:
            st.session_state.avail_tier=nt; changed=True
        nk = result.get('kpi_drill')
        if nk and nk!=st.session_state.get('kpi_drill'):
            st.session_state.kpi_drill=nk; changed=True
        if changed: st.rerun()

with admin_tab:
    st.markdown("### Substitution Master Table Builder")
    st.markdown("Build a permanent AI-assessed substitution table for any sub-category. Results saved to GitHub and used by all future analysis runs.")

    # Load existing master table
    _mt_csv, _mt_sha = gh_read("data/sub_master.csv")
    if _mt_csv:
        import io as _io_mt
        _mt_df = pd.read_csv(_io_mt.StringIO(_mt_csv))
        _covered_subcats = sorted(_mt_df['subcat'].unique().tolist()) if 'subcat' in _mt_df.columns else []
        st.success(f"✓ Master table: {len(_mt_df):,} pairs across {len(_covered_subcats)} sub-categories")
        if _covered_subcats:
            st.caption("Covered: " + ", ".join(_covered_subcats))
    else:
        _mt_df = pd.DataFrame()
        _covered_subcats = []
        st.info("No master table yet — build one sub-category at a time.")

    st.divider()

    # Sub-category selector
    _all_subcats = sorted(inv_temp['Sub Category'].unique().tolist()) if 'inv_temp' in dir() else []
    if not _all_subcats and 'inv_bytes_cache' in st.session_state:
        import io as _io_mt2
        _inv_mt = pd.read_excel(io.BytesIO(st.session_state['inv_bytes_cache']))
        _inv_mt.columns = [c.strip() for c in _inv_mt.columns]
        _inv_mt = _inv_mt[_inv_mt['Status']=='Active']
        _all_subcats = sorted(_inv_mt['Sub Category'].dropna().unique().tolist())

    _sel_subcat = st.selectbox(
        "Select sub-category to assess",
        [s for s in _all_subcats if s not in _covered_subcats] + 
        (['--- Already covered ---'] + _covered_subcats if _covered_subcats else []),
        key="master_subcat_sel"
    )

    if _sel_subcat and not _sel_subcat.startswith('---'):
        # Show SKU count
        if 'inv_bytes_cache' in st.session_state:
            import io as _io_mt3
            _inv_sel = pd.read_excel(io.BytesIO(st.session_state['inv_bytes_cache']))
            _inv_sel.columns = [c.strip() for c in _inv_sel.columns]
            _inv_sel = _inv_sel[(_inv_sel['Status']=='Active') & (_inv_sel['Sub Category']==_sel_subcat)].copy()
            _inv_sel['Item ID'] = pd.to_numeric(_inv_sel['Item ID'], errors='coerce')
            _inv_sel['RSP'] = pd.to_numeric(_inv_sel['RSP'], errors='coerce').fillna(0)
            _n_skus = len(_inv_sel)
            _n_pairs = _n_skus * (_n_skus - 1) // 2
            _n_batches = (_n_pairs * 2) // 10 + 1

            st.markdown(f"**{_sel_subcat}** — {_n_skus} SKUs → {_n_pairs:,} unique pairs → ~{_n_batches} API calls")
            st.caption(f"Estimated cost: ~${_n_batches * 0.003:.2f} | Time: ~{max(1, _n_batches // 10)} minutes")

            # Show SKUs
            with st.expander(f"View all {_n_skus} SKUs in this sub-category"):
                st.dataframe(_inv_sel[['Item ID','Description','Vendor','RSP']].reset_index(drop=True),
                             use_container_width=True, hide_index=True)

            # Build SKU list once, used by both test and full build
            _exclude_kw = ['caviar','lumpfish','cleaning','detergent']
            _skus_list = [s for s in _inv_sel[['Item ID','Description','Vendor','RSP']].to_dict('records')
                          if not any(k in str(s.get('Description','')).lower() for k in _exclude_kw)]

            # Test mode — assess 5 pairs first
            _test_col, _full_col = st.columns([1,2])
            with _test_col:
                if st.button(f"🧪 Test full sub-category (no save)", key="test_master_btn"):
                    # Run full assessment on all pairs but don't save to GitHub
                    _test_all_pairs = [(_skus_list[i], _skus_list[j])
                                       for i in range(len(_skus_list))
                                       for j in range(i+1, len(_skus_list))]
                    _test_results = {}
                    _test_progress = st.progress(0, text=f"Testing {len(_test_all_pairs)} pairs…")
                    _batch_size_t = 10
                    import requests as _rq_t, time as _tm_t

                    for _bi_t in range(0, len(_test_all_pairs), _batch_size_t):
                        _batch_t = _test_all_pairs[_bi_t:_bi_t+_batch_size_t]
                        _lines_t = []
                        for _j_t, (_o_t, _s_t) in enumerate(_batch_t):
                            _lines_t.append(
                                f"{_j_t+1}. OOS: {_o_t['Description']} | {str(_o_t.get('Vendor',''))[:20]} | {float(_o_t['RSP']):.3f} KD"
                                f" → SUB: {_s_t['Description']} | {str(_s_t.get('Vendor',''))[:20]} | {float(_s_t['RSP']):.3f} KD"
                            )
                        _prompt_t = (
                            f"Kuwait grocery substitute assessment. Sub-category: {_sel_subcat}\n\n"
                            + "\n".join(_lines_t)
                            + "\n\nFor each pair: is the substitute a DIRECT replacement?\n"
                            + "DIRECT = customer would fully accept this substitute (same type, similar price, same use)\n"
                            + "NONE = not a direct substitute\n\n"
                            + "Reply: [n]. [DIRECT/NONE] — [reason max 8 words]"
                        )
                        try:
                            _tr = _rq_t.post(
                                "https://api.anthropic.com/v1/messages",
                                headers={"Content-Type": "application/json",
                                         "x-api-key": st.secrets.get("ANTHROPIC_API_KEY",""),
                                         "anthropic-version": "2023-06-01"},
                                json={"model": "claude-sonnet-4-6", "max_tokens": 400,
                                      "messages": [{"role": "user", "content": _prompt_t}]},
                                timeout=30
                            )
                            if _tr.status_code == 200:
                                _txt_t = _tr.json()["content"][0]["text"]
                                for _j_t, (_o_t, _s_t) in enumerate(_batch_t):
                                    for _ln_t in _txt_t.split("\n"):
                                        _ln_t = _ln_t.strip()
                                        if _ln_t.startswith(f"{_j_t+1}."):
                                            _rest_t = _ln_t[len(f"{_j_t+1}."):].strip()
                                            _pts_t = _rest_t.split("—", 1)
                                            _str_t = _pts_t[0].strip().upper()
                                            if _str_t not in ["DIRECT","NONE"]: _str_t = "NONE"
                                            _rsn_t = _pts_t[1].strip() if len(_pts_t) > 1 else ""
                                            _test_results[(int(_o_t['Item ID']), int(_s_t['Item ID']))] = (_str_t, _rsn_t)
                                            _test_results[(int(_s_t['Item ID']), int(_o_t['Item ID']))] = (_str_t, _rsn_t)
                                            break
                        except: pass
                        _test_progress.progress(
                            min((_bi_t+_batch_size_t)/max(len(_test_all_pairs),1), 1.0),
                            text=f"Tested {min(_bi_t+_batch_size_t, len(_test_all_pairs))}/{len(_test_all_pairs)} pairs"
                        )
                        _tm_t.sleep(0.15)

                    _test_progress.progress(1.0, text="Done")

                    # Show results grouped by strength
                    st.markdown(f"**Results: {len(_test_results)} pairs assessed**")
                    for _strength_show in ["DIRECT","STRONG","WEAK","NONE"]:
                        _matches = [(k,v) for k,v in _test_results.items()
                                    if v[0]==_strength_show and k[0] < k[1]]
                        if _matches:
                            with st.expander(f"**{_strength_show}** — {len(_matches)} pairs", expanded=(_strength_show in ["DIRECT","STRONG"])):
                                for (_oid_t, _sid_t), (_str_t, _rsn_t) in sorted(_matches):
                                    _on = next((s['Description'] for s in _skus_list if int(s['Item ID'])==_oid_t), str(_oid_t))
                                    _sn = next((s['Description'] for s in _skus_list if int(s['Item ID'])==_sid_t), str(_sid_t))
                                    st.markdown(f"- `{_on[:40]}` → `{_sn[:40]}` · *{_rsn_t}*")

                    st.info("✓ Test complete — results not saved. Click 'Build master table' to save permanently.")

            with _full_col:
                if st.button(f"🤖 Build master table for {_sel_subcat}", type="primary", key="build_master_btn"):
                    _all_pairs = [(a,b) for i,a in enumerate(_skus_list)
                                  for j,b in enumerate(_skus_list) if i < j]
                    _progress = st.progress(0, text=f"Assessing {len(_all_pairs)} pairs...")
                    _results = {}
                    _batch_size = 10
                    import time as _tm
                    import requests as _rq2

                    for _bi in range(0, len(_all_pairs), _batch_size):
                        _batch = _all_pairs[_bi:_bi+_batch_size]
                        _lines2 = []
                        for _j2, (_o2, _s2) in enumerate(_batch):
                            _lines2.append(
                                f"{_j2+1}. OOS: {_o2['Description']} | {str(_o2.get('Vendor',''))[:20]} | {float(_o2['RSP']):.3f} KD"
                                f" → SUB: {_s2['Description']} | {str(_s2.get('Vendor',''))[:20]} | {float(_s2['RSP']):.3f} KD"
                            )
                        _prompt2 = (
                            f"Kuwait grocery substitute assessment. Sub-category: {_sel_subcat}\n\n"
                            + "\n".join(_lines2)
                            + "\n\nFor each pair: is the substitute a DIRECT replacement?\n"
                            + "DIRECT = customer would fully accept (same type, same fat content, similar price, same use)\n"
                            + "NONE = not a direct substitute\n\n"
                            + "IMPORTANT RULES:\n"
                            + "- Different fat content = NONE (low fat ≠ full fat ≠ fat free ≠ skimmed ≠ full cream)\n"
                            + "- Different cheese type = NONE (cheddar ≠ feta ≠ mozzarella ≠ halloumi etc)\n"
                            + "- Processed cheese ≠ natural cheese = NONE\n"
                            + "- Different fruit/veg type = NONE\n\n"
                            + "Reply: [n]. [DIRECT/NONE] — [reason max 8 words]"
                        )
                        try:
                            _r2 = _rq2.post(
                                "https://api.anthropic.com/v1/messages",
                                headers={"Content-Type": "application/json", "x-api-key": st.secrets.get("ANTHROPIC_API_KEY",""), "anthropic-version": "2023-06-01"},
                                json={"model": "claude-sonnet-4-6", "max_tokens": 400,
                                      "messages": [{"role": "user", "content": _prompt2}]},
                                timeout=30
                            )
                            if _r2.status_code == 200:
                                _txt2 = _r2.json()["content"][0]["text"]
                                for _j2, (_o2, _s2) in enumerate(_batch):
                                    for _ln2 in _txt2.split("\n"):
                                        _ln2 = _ln2.strip()
                                        if _ln2.startswith(f"{_j2+1}."):
                                            _rest2 = _ln2[len(f"{_j2+1}."):].strip()
                                            _pts2 = _rest2.split("—", 1)
                                            _str2 = _pts2[0].strip().upper()
                                            if _str2 not in ["DIRECT","NONE"]:
                                                _str2 = "NONE"
                                            _rsn2 = _pts2[1].strip() if len(_pts2) > 1 else ""
                                            _fwd2 = (int(_o2['Item ID']), int(_s2['Item ID']))
                                            _rev2 = (int(_s2['Item ID']), int(_o2['Item ID']))
                                            _results[_fwd2] = (_str2, _rsn2)
                                            if _rev2 not in _results:
                                                _results[_rev2] = (_str2, _rsn2)
                                            break
                        except: pass
                        _pct2 = min((_bi + _batch_size) / max(len(_all_pairs),1), 1.0)
                        _progress.progress(_pct2, text=f"Assessed {min(_bi+_batch_size, len(_all_pairs))}/{len(_all_pairs)} pairs — {len(_results)} results")
                        _tm.sleep(0.15)

                    _progress.progress(1.0, text=f"Done — {len(_results)} pairs assessed")

                    # Merge with existing master table
                    _new_rows2 = []
                    for (_oid2, _sid2), (_str2, _rsn2) in _results.items():
                        _new_rows2.append({'oos_id':_oid2,'sub_id':_sid2,
                                           'subcat':_sel_subcat,'strength':_str2,
                                           'reason':str(_rsn2).replace(',',';')})
                    _new_df2 = pd.DataFrame(_new_rows2)
                    if len(_mt_df) > 0:
                        _merged2 = pd.concat([_mt_df[_mt_df['subcat']!=_sel_subcat], _new_df2], ignore_index=True)
                    else:
                        _merged2 = _new_df2

                    _merged_csv2 = _merged2.to_csv(index=False)
                    _, _cur_sha2 = gh_read("data/sub_master.csv")
                    if gh_write("data/sub_master.csv", _merged_csv2, _cur_sha2):
                        st.success(f"✓ {len(_new_rows2)} pairs saved to master table for {_sel_subcat}")
                        load_sub_cache_data.clear()
                        st.rerun()
                    else:
                        st.error("Failed to save to GitHub")

with kpi_tab:
    _ytd_kpi = st.session_state.get('vel_ytd')
    if _ytd_kpi is None:
        st.info("Upload order history to enable KPI drill-down.")
    else:
        kpi_choice = st.selectbox("Select metric to drill into", [
            f"Availability — Top {st.session_state.avail_tier} OOS SKUs",
            "OOS SKUs with velocity ≥ 2/day",
            "DC transfer opportunities",
            "Real overstock (>45 days cover)",
            "Dead stock (zero velocity)",
        ])
        import io as _io_kpi
        _inv_kpi_bytes = st.session_state.get('inv_bytes_cache')
        if _inv_kpi_bytes:
            _inv_kpi = pd.read_excel(io.BytesIO(_inv_kpi_bytes))
            _inv_kpi.columns = [c.strip() for c in _inv_kpi.columns]
            _inv_kpi = _inv_kpi[_inv_kpi['Status']=='Active'].copy()
            _inv_kpi['Item ID'] = pd.to_numeric(_inv_kpi['Item ID'], errors='coerce')
            for _c in ['Jahra Dark Store Stock','Qurtuba Dark Store Stock',
                       'Sabah Salem Dark Store Stock','Ardiya - Distribution Center Stock',
                       'Total SOH','RSP']:
                if _c in _inv_kpi.columns:
                    _inv_kpi[_c] = pd.to_numeric(_inv_kpi[_c], errors='coerce').fillna(0)
            _nv = _ytd_kpi.groupby('item_id')['true_daily'].mean().reset_index()
            _im = _inv_kpi[['Item ID','Description','Category','Sub Category','RSP',
                             'Jahra Dark Store Stock','Qurtuba Dark Store Stock',
                             'Sabah Salem Dark Store Stock',
                             'Ardiya - Distribution Center Stock','Total SOH']].rename(
                columns={'Item ID':'item_id'}).merge(_nv, on='item_id', how='left')
            _im['true_daily'] = _im['true_daily'].fillna(0)
            _im['days_cover'] = np.where(_im['true_daily']>0,
                _im['Total SOH']/_im['true_daily'], 999)

            if kpi_choice.startswith("Availability"):
                # Top N SKUs that are OOS at any store
                _net_ytd_df = st.session_state.get('vel_net')
                if _net_ytd_df is not None:
                    _top_n = st.session_state.avail_tier
                    _top_ids = _net_ytd_df.nlargest(_top_n,'net_ytd')['item_id'].tolist()
                    _top_inv = _im[_im['item_id'].isin(_top_ids)].copy()
                    _oos_any = _top_inv[_top_inv['Total SOH']==0].copy()
                    _oos_missing = _top_inv[
                        (_top_inv['Total SOH']>0) &
                        ((_top_inv['Jahra Dark Store Stock']==0) |
                         (_top_inv['Qurtuba Dark Store Stock']==0) |
                         (_top_inv['Sabah Salem Dark Store Stock']==0))
                    ].copy()
                    _top_inv_merged = _top_inv.merge(
                        _net_ytd_df[['item_id','net_ytd']], on='item_id', how='left')
                    _oos_any = _oos_any.merge(
                        _net_ytd_df[['item_id','net_ytd']], on='item_id', how='left')
                    _oos_missing = _oos_missing.merge(
                        _net_ytd_df[['item_id','net_ytd']], on='item_id', how='left')

                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric(f"Top {_top_n} SKUs", _top_n)
                    col_b.metric("Fully OOS (no stock anywhere)", len(_oos_any))
                    col_c.metric("Missing ≥1 store", len(_oos_missing))

                    st.markdown("#### Fully OOS — no stock at any store")
                    if len(_oos_any):
                        _oos_any['Network YTD'] = _oos_any['net_ytd'].fillna(0).astype(int)
                        _oos_any['Velocity'] = _oos_any['true_daily'].round(2)
                        _oos_any = _oos_any.sort_values('Network YTD', ascending=False)
                        st.dataframe(_oos_any[['Description','Category','Sub Category',
                            'Network YTD','Velocity','RSP',
                            'Ardiya - Distribution Center Stock']].rename(
                            columns={'Ardiya - Distribution Center Stock':'DC Stock'}).reset_index(drop=True),
                            use_container_width=True, hide_index=True)
                    else:
                        st.success(f"All Top {_top_n} SKUs have stock somewhere in the network!")

                    st.markdown("#### Missing at ≥1 store (in stock somewhere but not everywhere)")
                    if len(_oos_missing):
                        _oos_missing['Network YTD'] = _oos_missing['net_ytd'].fillna(0).astype(int)
                        _oos_missing['Jahra'] = _oos_missing['Jahra Dark Store Stock'].apply(lambda x: '✓' if x>0 else '✗')
                        _oos_missing['Qurtuba'] = _oos_missing['Qurtuba Dark Store Stock'].apply(lambda x: '✓' if x>0 else '✗')
                        _oos_missing['Sabah Salem'] = _oos_missing['Sabah Salem Dark Store Stock'].apply(lambda x: '✓' if x>0 else '✗')
                        _oos_missing['DC Stock'] = _oos_missing['Ardiya - Distribution Center Stock'].astype(int)
                        _oos_missing = _oos_missing.sort_values('Network YTD', ascending=False)
                        st.dataframe(_oos_missing[['Description','Category','Sub Category',
                            'Network YTD','Jahra','Qurtuba','Sabah Salem','DC Stock','RSP']].reset_index(drop=True),
                            use_container_width=True, hide_index=True)
                    _df_kpi = _oos_any  # for export

            elif kpi_choice.startswith("OOS SKUs"):
                _rows_kpi = []
                for _st, _col in [('Jahra','Jahra Dark Store Stock'),
                                   ('Qurtuba','Qurtuba Dark Store Stock'),
                                   ('Sabah Salem','Sabah Salem Dark Store Stock')]:
                    _sv = _ytd_kpi[_ytd_kpi['store_norm']==_st][['item_id','true_daily']]
                    _s = _inv_kpi[_inv_kpi[_col]==0][['Item ID','Description','Category',
                        'Sub Category','RSP']].rename(columns={'Item ID':'item_id'}).merge(
                        _sv, on='item_id', how='inner')
                    _s = _s[_s['true_daily']>=2].copy(); _s['Store'] = _st
                    _rows_kpi.append(_s)
                _df_kpi = pd.concat(_rows_kpi).sort_values('true_daily', ascending=False)
                _df_kpi['Velocity'] = _df_kpi['true_daily'].round(2)
                st.metric("OOS SKUs with vel ≥ 2/day", len(_df_kpi))
                st.dataframe(_df_kpi[['Store','Description','Category','Sub Category',
                    'Velocity','RSP']].reset_index(drop=True),
                    use_container_width=True, hide_index=True)
            elif kpi_choice.startswith("DC"):
                _rows_kpi = []
                for _st, _col in [('Jahra','Jahra Dark Store Stock'),
                                   ('Qurtuba','Qurtuba Dark Store Stock'),
                                   ('Sabah Salem','Sabah Salem Dark Store Stock')]:
                    _s = _inv_kpi[(_inv_kpi[_col]==0) &
                                  (_inv_kpi['Ardiya - Distribution Center Stock']>0)].copy()
                    _s['Store'] = _st; _rows_kpi.append(_s)
                _df_kpi = pd.concat(_rows_kpi).rename(
                    columns={'Ardiya - Distribution Center Stock':'DC Stock'})
                _df_kpi = _df_kpi.sort_values(['Category','Sub Category'])
                st.metric("DC transfer opportunities", len(_df_kpi))
                st.dataframe(_df_kpi[['Store','Description','Category','Sub Category',
                    'DC Stock','RSP']].reset_index(drop=True),
                    use_container_width=True, hide_index=True)
            elif kpi_choice.startswith("Real"):
                _df_kpi = _im[(_im['days_cover']>45) & (_im['true_daily']>0) &
                               (_im['Total SOH']>0)].copy()
                _df_kpi['Days Cover'] = _df_kpi['days_cover'].round(0).astype(int)
                _df_kpi['Velocity'] = _df_kpi['true_daily'].round(2)
                _df_kpi = _df_kpi.sort_values('days_cover', ascending=False)
                st.metric("Overstocked SKUs", len(_df_kpi))
                st.dataframe(_df_kpi[['Description','Category','Sub Category',
                    'Total SOH','Velocity','Days Cover','RSP']].reset_index(drop=True),
                    use_container_width=True, hide_index=True)
            elif kpi_choice.startswith("Dead"):
                _df_kpi = _im[(_im['Total SOH']>0) & (_im['true_daily']==0)].copy()
                _df_kpi = _df_kpi.sort_values('Total SOH', ascending=False)
                st.metric("Dead stock SKUs", len(_df_kpi))
                st.dataframe(_df_kpi[['Description','Category','Sub Category',
                    'Total SOH','RSP']].reset_index(drop=True),
                    use_container_width=True, hide_index=True)

            _csv_kpi = _df_kpi.to_csv(index=False).encode('utf-8')
            st.download_button("⬇️ Export as CSV", _csv_kpi,
                file_name=f"fiz_kpi_{kpis.get('file_date','')}.csv", mime='text/csv')
