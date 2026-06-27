# Fiz Availability Briefing App

Interactive availability briefing widget for Fiz dark stores (Jahra, Qurtuba, Sabah Salem).

## What it does

Upload your daily `Master_LIst_-_DD-MM-YYYY.xlsx` inventory file and the app instantly generates:

- **21 category tabs** with sub-category navigation
- **Per-store availability** with OOS SKUs, store YTD vs network YTD
- **Substitute quality scoring** — DIRECT / STRONG / WEAK per OOS SKU
- **Context flags** — Discontinued here / Out of season / Promo ended / Discontinued
- **Severity classification** — 🔴 Urgent / 🟡 Action / 🔵 Note

## Rules embedded

- **FRESH** SKUs → always supplier-direct to store (never transfer)
- **PRODUCE** (Fruits & Vegetables) → supplier-direct, seasonal
- **NON-FRESH** → transfer eligible
- **Rawdatain** = premium local mineral water — Arwa/Abraaj are VALUE tier, different customer, never a direct substitute
- **Water format rule** — 200ml/330ml convenience formats cannot substitute 1L+ household formats

## Deploy to Streamlit Community Cloud (free, 5 minutes)

1. Push this folder to a GitHub repo (can be private)
2. Go to https://share.streamlit.io
3. Click **New app**
4. Connect your GitHub repo, set `app.py` as the main file
5. Click **Deploy** — you get a public URL like `https://yourapp.streamlit.app`
6. Share that URL with your team

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open http://localhost:8501

## Daily workflow

1. Download the latest inventory file from your system
2. Open the app URL
3. Upload the file → briefing generates in ~5 seconds
4. Share the URL with the team (the app is always live, they just upload the file)

## File format expected

The app auto-detects column names from the inventory file. It looks for:
- `Jahra Dark Store Stock`, `Qurtuba Dark Store Stock`, `Sabah Salem Dark Store Stock`
- `Fresh/Non Fresh`
- `Category`, `Sub Category`, `Description`, `Vendor`, `Barcode`
- `Status` (filters to Active only)
- Sold qty columns containing "Sold Qty" + "June"/"Jun" or "May" in the name

If your column names change, update the `col_map` dict in `load_and_analyse()` in `app.py`.
