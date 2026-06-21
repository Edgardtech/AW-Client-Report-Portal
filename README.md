# AW Client Report Portal
**Windbrook Solutions — Internal Staff Tool**

A web portal for generating quarterly SACS (cashflow) and TCC (net worth) PDF reports for financial planning clients.

---

## Quick Start (Local)

```bash
pip install -r requirements.txt
python run.py
# Open http://localhost:5000
```

**Default credentials:**
- `admin / windbrook2026`
- `rebecca / windbrook2026`
- `maryann / windbrook2026`

---

## Deploy to Railway

1. Push repo to GitHub
2. New project on [railway.app](https://railway.app) → Deploy from GitHub
3. Set env var: `SECRET_KEY=your-secret-here`
4. Done — Railway auto-detects Procfile

---

## What It Does

| Feature | Status |
|---|---|
| Staff login | ✅ |
| Client profile management | ✅ |
| Quarterly data entry form | ✅ |
| Live auto-calculations | ✅ |
| SACS PDF generation | ✅ |
| TCC PDF generation | ✅ |
| Report history | ✅ |

## Business Rules Implemented

- `Excess = Inflow - Outflow`
- `Private Reserve Target = (6 × monthly expenses) + insurance deductibles`
- `Client 1 Retirement Total = sum of Client 1 retirement balances`
- `Client 2 Retirement Total = sum of Client 2 retirement balances`
- `Non-Retirement Total = non-retirement accounts only (trust excluded)`
- `Grand Total Net Worth = Ret1 + Ret2 + Non-Ret + Trust (Zillow)`
- **Liabilities are shown separately — NOT subtracted from net worth**

## Stack

- **Backend:** Python + Flask
- **Database:** SQLite
- **PDF:** ReportLab
- **Frontend:** HTML + CSS + Vanilla JS
- **Deploy:** Railway / Render (Procfile included)

## V2 Ideas (Out of Scope)

- Zillow API auto-fetch
- Schwab balance auto-pull
- RightCapital integration
- Dropbox auto-save
- Client-facing expense worksheet
