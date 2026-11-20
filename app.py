import os, sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# Load settings from a local .env file if present (never upload .env).
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

TZ=ZoneInfo("Asia/Kolkata")
DB=os.getenv("ABNTM_DB","abntm_live.db")
st.set_page_config(page_title="ABNTM | Astro Bank Nifty",page_icon="📈",layout="wide")
st.markdown("""
<style>
.stApp{background:#f4f6fb;color:#15233b}.block-container{padding-top:1rem;max-width:1500px}
.hero{background:linear-gradient(115deg,#101f3c,#243d66);padding:24px 28px;border-radius:18px;color:white;margin-bottom:18px}
.hero h1{font-size:30px;margin:0 0 6px;color:white}.hero p{color:#d7e2f5;margin:0}
.metric{background:white;border:1px solid #e3e8f1;border-radius:14px;padding:16px;min-height:105px}
.metric-label{font-size:12px;color:#65738b;text-transform:uppercase;letter-spacing:.06em}
.metric-value{font-size:26px;font-weight:700;color:#14233d;margin-top:7px}
.metric-sub{font-size:12px;color:#68778e;margin-top:4px}
.panel{background:white;border:1px solid #e3e8f1;border-radius:14px;padding:18px;margin-bottom:12px}
</style>""",unsafe_allow_html=True)

def db():
    c=sqlite3.connect(DB,check_same_thread=False)
    c.execute("""CREATE TABLE IF NOT EXISTS quote_snapshots(
    ts_ist TEXT,instrument TEXT,last_price REAL,open REAL,high REAL,low REAL,
    prev_close REAL,source TEXT,PRIMARY KEY(ts_ist,instrument))""")
    c.commit()
    return c

def to_float(x):
    try:
        return float(x)
    except (TypeError,ValueError):
        return None

# ---------------------------------------------------------------------------
# Data providers. Each returns (quote, candles, error):
#   quote   = {"ltp","open","high","low","prev_close","ts"} or None
#   candles = DataFrame with time/open/high/low/close, or None
#   error   = message string, or None
# All providers are read-only market data. No orders are ever placed, so the
# broker static-IP rule for order placement does not apply to this app.
# ---------------------------------------------------------------------------

@st.cache_data(ttl=4,show_spinner=False)
def yahoo_quote():
    try:
        r=requests.get("https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEBANK",
                       params={"interval":"1m","range":"1d"},
                       headers={"User-Agent":"Mozilla/5.0"},timeout=10)
        r.raise_for_status()
        res=(r.json().get("chart") or {}).get("result") or []
        if not res:
            return None,None,"Yahoo Finance returned no data for Bank Nifty (^NSEBANK)."
        res=res[0]; meta=res.get("meta",{})
        candles=None
        if res.get("timestamp"):
            q=res["indicators"]["quote"][0]
            candles=pd.DataFrame({
                "time":pd.to_datetime(res["timestamp"],unit="s",utc=True).tz_convert(TZ),
                "open":q.get("open"),"high":q.get("high"),"low":q.get("low"),"close":q.get("close")
            }).dropna()
        has=candles is not None and not candles.empty
        quote={
            "ltp":to_float(meta.get("regularMarketPrice")),
            "open":float(candles["open"].iloc[0]) if has else None,
            "high":to_float(meta.get("regularMarketDayHigh")) or (float(candles["high"].max()) if has else None),
            "low":to_float(meta.get("regularMarketDayLow")) or (float(candles["low"].min()) if has else None),
            "prev_close":to_float(meta.get("chartPreviousClose") or meta.get("previousClose")),
            "ts":datetime.fromtimestamp(meta["regularMarketTime"],TZ) if meta.get("regularMarketTime") else None,
        }
        if quote["ltp"] is None:
            return None,candles,"Yahoo Finance response had no last price."
        return quote,candles,None
    except Exception as e:
        return None,None,f"Yahoo Finance request failed: {e}"

@st.cache_data(ttl=4,show_spinner=False)
def fyers_quote():
    app_id=os.getenv("FYERS_APP_ID"); token=os.getenv("FYERS_ACCESS_TOKEN")
    symbol=os.getenv("FYERS_BANKNIFTY_SYMBOL","NSE:NIFTYBANK-INDEX")
    try:
        r=requests.get("https://api-t1.fyers.in/data/quotes",params={"symbols":symbol},
                       headers={"Authorization":f"{app_id}:{token}"},timeout=10)
        try:
            data=r.json()
        except ValueError:
            r.raise_for_status(); raise
        if data.get("s")!="ok" or not data.get("d"):
            return None,None,"Fyers API response: "+str(data.get("message") or data)
        v=data["d"][0].get("v",{})
        if not isinstance(v,dict) or v.get("s")=="error":
            return None,None,"Fyers returned no quote. Check FYERS_BANKNIFTY_SYMBOL."
        tt=to_float(v.get("tt"))
        quote={
            "ltp":to_float(v.get("lp")),"open":to_float(v.get("open_price")),
            "high":to_float(v.get("high_price")),"low":to_float(v.get("low_price")),
            "prev_close":to_float(v.get("prev_close_price")),
            "ts":datetime.fromtimestamp(tt,TZ) if tt else None,
        }
        return quote,None,None
    except Exception as e:
        return None,None,f"Fyers quote request failed: {e}"

@st.cache_data(ttl=4,show_spinner=False)
def motilal_quote():
    headers={
      "Accept":"application/json","Content-Type":"application/json",
      "User-Agent":"ABNTM/1.2.0",
      "Authorization":os.getenv("MOTILAL_AUTH_TOKEN"),
      "ApiKey":os.getenv("MOTILAL_API_KEY"),
      "ClientLocalIp":os.getenv("MOTILAL_CLIENT_LOCAL_IP"),
      "ClientPublicIp":os.getenv("MOTILAL_CLIENT_PUBLIC_IP"),
      "MacAddress":os.getenv("MOTILAL_MAC_ADDRESS"),
      "SourceId":"WEB","osname":os.getenv("MOTILAL_OS_NAME","Windows"),
      "osversion":os.getenv("MOTILAL_OS_VERSION","10"),
      "browsername":os.getenv("MOTILAL_BROWSER_NAME","Chrome"),
      "browserversion":os.getenv("MOTILAL_BROWSER_VERSION",""),
      "apisecretkey":os.getenv("MOTILAL_API_SECRET"),
      "accesstoken":os.getenv("MOTILAL_ACCESS_TOKEN"),
      "productname":"ABNTM","productversion":"1.2"
    }
    payload={"exchangename":"NSE","scripcode":os.getenv("MOTILAL_BANKNIFTY_INDEX_CODE")}
    try:
        response=requests.post("https://openapi.motilaloswal.com/rest/report/v3/getindexltpdata",
                               json=payload,headers=headers,timeout=10)
        response.raise_for_status()
        data=response.json()
        if data.get("status")!="SUCCESS":
            return None,None,"Motilal API response: "+str(data.get("message","Unknown error"))
        rows=data.get("data",[])
        if isinstance(rows,dict): rows=[rows]
        if not rows:return None,None,"Motilal returned no index quote. Check Bank Nifty index code."
        q=rows[0]
        quote={"ltp":to_float(q.get("ltp")),"open":to_float(q.get("open")),"high":to_float(q.get("high")),
               "low":to_float(q.get("low")),"prev_close":to_float(q.get("close")),"ts":None}
        return quote,None,None
    except Exception as e:
        return None,None,f"Motilal quote request failed: {e}"

PROVIDERS={
    "Yahoo Finance (free, no account)":{
        "fetch":yahoo_quote,"required":[],
        "note":"No account, keys or static IP needed. Unofficial source; prices may be delayed. Good for research and testing.",
        "link":"https://finance.yahoo.com/quote/%5ENSEBANK/"},
    "Fyers API (free, data needs no static IP)":{
        "fetch":fyers_quote,"required":["FYERS_APP_ID","FYERS_ACCESS_TOKEN"],
        "note":"Free with a Fyers account. Fyers states static IP is needed only for order placement, not data APIs. Access token must be regenerated daily via Fyers login.",
        "link":"https://myapi.fyers.in/docsv3"},
    "Motilal Oswal API":{
        "fetch":motilal_quote,
        "required":["MOTILAL_API_KEY","MOTILAL_AUTH_TOKEN","MOTILAL_ACCESS_TOKEN","MOTILAL_API_SECRET",
                    "MOTILAL_CLIENT_LOCAL_IP","MOTILAL_CLIENT_PUBLIC_IP","MOTILAL_MAC_ADDRESS",
                    "MOTILAL_BANKNIFTY_INDEX_CODE"],
        "note":"Requires Motilal API registration, IP and MAC headers.",
        "link":"https://invest.motilaloswal.com/moAPI"},
    "Research / offline":None,
}

def metric(label,value,sub=""):
    st.markdown(f'<div class="metric"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="metric-sub">{sub}</div></div>',unsafe_allow_html=True)

def fmt(x):
    return f"{x:,.2f}" if x is not None else "—"

st.markdown('<div class="hero"><h1>ABNTM 1.2</h1><p>Astro Bank Nifty Trading Model · Research-led market dashboard</p></div>',unsafe_allow_html=True)
with st.sidebar:
    st.markdown("### Control centre")
    source=st.selectbox("Data source",list(PROVIDERS.keys()),index=0)
    refresh=st.selectbox("Refresh interval",["5 seconds","10 seconds","30 seconds","60 seconds"],index=1)
    refresh_seconds=int(refresh.split()[0])
    st.caption("Read-only market data in this build. No orders are placed.")
    provider=PROVIDERS[source]
    if provider:
        st.caption(provider["note"])
        if provider["required"]:
            with st.expander("Settings status",expanded=False):
                for var in provider["required"]:
                    st.markdown(f"{'✅' if os.getenv(var) else '❌'} `{var}`")
                st.caption("Values are never shown. Set them in a local .env file.")
    st.divider()
    st.markdown("### Model status")
    st.info("Astrology/KP engine: integration and validation pending")

if provider:
    st_autorefresh(interval=refresh_seconds*1000,key="abntm_refresh")
now=datetime.now(TZ)
st.caption(f"India time: {now.strftime('%d %b %Y, %I:%M:%S %p')} IST")

candles=None
if provider:
    missing=[x for x in provider["required"] if not os.getenv(x)]
    if missing:
        st.warning(f"{source} setup incomplete. Configure: "+", ".join(missing))
        st.markdown("Your API keys and tokens stay on your own computer/server. Never paste passwords, API secrets, TOTP seeds or access tokens into chat tools.")
        st.markdown(f"[{source} documentation]({provider['link']})")
    else:
        quote,candles,error=provider["fetch"]()
        if error:
            st.warning(error)
        else:
            ltp=quote["ltp"]; prev=quote["prev_close"]
            change=(ltp/prev-1)*100 if ltp and prev else None
            cols=st.columns(4)
            with cols[0]:metric("Bank Nifty LTP",fmt(ltp),f"{change:+.2f}% vs previous close" if change is not None else "")
            with cols[1]:metric("Session high",fmt(quote["high"]))
            with cols[2]:metric("Session low",fmt(quote["low"]))
            with cols[3]:metric("Session open",fmt(quote["open"]))
            stamp=quote["ts"].strftime('%d %b %Y, %I:%M:%S %p IST') if quote["ts"] else "not provided by source (request time used)"
            st.caption(f"Source: {source} · Quote time: {stamp}")
            con=db()
            con.execute("INSERT OR REPLACE INTO quote_snapshots VALUES(?,?,?,?,?,?,?,?)",
                        (now.isoformat(timespec="seconds"),"NIFTY BANK",ltp,quote["open"],quote["high"],
                         quote["low"],prev,source))
            con.commit();con.close()
else:
    st.info("Offline mode selected. No market value is shown as live.")

tabs=st.tabs(["Daily cockpit","Astro & KP","Signals & risk","Dasha research","Data & sources"])
with tabs[0]:
    st.markdown("### Today's trading cockpit")
    if candles is not None and not candles.empty:
        st.markdown("**Bank Nifty intraday (1-minute closes)**")
        st.line_chart(candles.set_index("time")["close"],height=280)
    else:
        con=db()
        hist=pd.read_sql_query("SELECT ts_ist,last_price FROM quote_snapshots WHERE instrument='NIFTY BANK' ORDER BY ts_ist DESC LIMIT 500",con)
        con.close()
        if len(hist)>1:
            st.markdown("**Saved quote snapshots**")
            hist["ts_ist"]=pd.to_datetime(hist["ts_ist"])
            st.line_chart(hist.sort_values("ts_ist").set_index("ts_ist")["last_price"],height=280)
    c1,c2,c3=st.columns(3)
    with c1:st.markdown('<div class="panel"><b>Market structure</b><p>VWAP · opening range · CPR · EMA20/50 · RSI14</p><h3>Awaiting validated intraday candles</h3></div>',unsafe_allow_html=True)
    with c2:st.markdown('<div class="panel"><b>Derivatives positioning</b><p>Futures OI · options OI · IV · PCR</p><h3>Awaiting authorised derivatives feed</h3></div>',unsafe_allow_html=True)
    with c3:st.markdown('<div class="panel"><b>Banking breadth</b><p>HDFC · ICICI · Axis · SBI · Kotak</p><h3>Constituent tokens to be mapped</h3></div>',unsafe_allow_html=True)
    st.markdown("**Session blocks:** 09:15–09:30 · 09:30–10:15 · 10:15–11:30 · 11:30–13:00 · 13:00–14:15 · 14:15–15:30 IST")
with tabs[1]:
    st.markdown("### Astrology & KP engine")
    st.write("Bank Nifty reference: 15 September 2003 · 09:55 IST · Mumbai. Launch Dasha: Venus–Rahu. Venus Mahadasha began June 1995; Venus–Rahu ended 24 August 2005.")
    st.warning("Daily ephemeris, KP cusp/sub-lord and Dasha activation scores will only be published after cross-checking against the user's astrology software.")
with tabs[2]:
    st.markdown("### Signal and risk monitor")
    st.write("Composite direction, timing and volatility scores will combine astrology with technical and breadth confirmation.")
    st.error("Execution is disabled. No automated orders or trade recommendations are generated by this prototype.")
with tabs[3]:
    st.markdown("### Mahadasha–Antardasha research")
    st.write("Exact-period returns, OHLC extremes, drawdowns, volatility and reversal rates populate after full historical data import.")
with tabs[4]:
    st.markdown("### Data sources and provenance")
    st.markdown("- [Yahoo Finance – Bank Nifty (^NSEBANK)](https://finance.yahoo.com/quote/%5ENSEBANK/) — free, unofficial, may be delayed.")
    st.markdown("- [Fyers API v3 documentation](https://myapi.fyers.in/docsv3) — free; static IP needed only for order placement.")
    st.markdown("- [Motilal Oswal API portal](https://invest.motilaloswal.com/moAPI)")
    st.markdown("- [Motilal Oswal API documentation](https://invest.motilaloswal.com/moAPI/APIDocumentation/Introduction)")
    st.markdown("- [NSE Indices historical data](https://www.niftyindices.com/reports/historical-data)")
    st.markdown("- [NSE historical reports](https://www.nseindia.com/static/resources/historical-reports-capital-market-daily-monthly-archives)")
    st.markdown("- [INDstocks API reference](https://documenter.getpostman.com/view/56363899/2sBY4LShyj) — secondary connector subject to account/API entitlement confirmation.")
    st.caption("For Motilal, the Bank Nifty index code must be looked up from Motilal's index master and entered as MOTILAL_BANKNIFTY_INDEX_CODE. Do not guess the code.")
st.divider()
st.caption("ABNTM is an experimental research and decision-support tool, not investment advice. Validate out-of-sample and after all costs before any live trading.")
