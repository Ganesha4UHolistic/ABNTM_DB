import os, sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

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

def motilal_index_quote():
    required=["MOTILAL_API_KEY","MOTILAL_AUTH_TOKEN","MOTILAL_ACCESS_TOKEN",
              "MOTILAL_API_SECRET","MOTILAL_CLIENT_LOCAL_IP","MOTILAL_CLIENT_PUBLIC_IP",
              "MOTILAL_MAC_ADDRESS","MOTILAL_BANKNIFTY_INDEX_CODE"]
    missing=[x for x in required if not os.getenv(x)]
    if missing:
        return None,"Motilal API setup incomplete. Configure: "+", ".join(missing)
    headers={
      "Accept":"application/json","Content-Type":"application/json",
      "User-Agent":"ABNTM/1.1.0",
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
      "productname":"ABNTM","productversion":"1.1"
    }
    payload={"exchangename":"NSE","scripcode":os.getenv("MOTILAL_BANKNIFTY_INDEX_CODE")}
    try:
        response=requests.post("https://openapi.motilaloswal.com/rest/report/v3/getindexltpdata",
                               json=payload,headers=headers,timeout=10)
        response.raise_for_status()
        data=response.json()
        if data.get("status")!="SUCCESS":
            return None,"Motilal API response: "+str(data.get("message","Unknown error"))
        rows=data.get("data",[])
        if isinstance(rows,dict): rows=[rows]
        if not rows:return None,"Motilal returned no index quote. Check Bank Nifty index code."
        return rows[0],None
    except Exception as e:
        return None,f"Motilal quote request failed: {e}"

def metric(label,value,sub=""):
    st.markdown(f'<div class="metric"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="metric-sub">{sub}</div></div>',unsafe_allow_html=True)

st.markdown('<div class="hero"><h1>ABNTM 1.1</h1><p>Astro Bank Nifty Trading Model · Research-led market dashboard</p></div>',unsafe_allow_html=True)
with st.sidebar:
    st.markdown("### Control centre")
    mode=st.radio("Data mode",["Motilal Oswal live feed","Research / offline"])
    refresh=st.selectbox("Refresh interval",["5 seconds","10 seconds","30 seconds","60 seconds"],index=1)
    refresh_seconds=int(refresh.split()[0])
    st.caption("Read-only market data in this build. No orders are placed.")
    st.divider()
    st.markdown("### Model status")
    st.info("Astrology/KP engine: integration and validation pending")

if mode=="Motilal Oswal live feed":
    st_autorefresh(interval=refresh_seconds*1000,key="abntm_refresh")
now=datetime.now(TZ)
st.caption(f"India time: {now.strftime('%d %b %Y, %I:%M:%S %p')} IST")

if mode=="Motilal Oswal live feed":
    quote,error=motilal_index_quote()
    if error:
        st.warning(error)
        st.markdown("Your API keys and tokens stay on your own computer/server. Do not paste passwords, API secrets, TOTP seeds or access tokens into ChatGPT.")
        st.markdown("[Motilal Oswal API registration and documentation](https://invest.motilaloswal.com/moAPI)")
    else:
        ltp=float(quote.get("ltp",0))
        op=float(quote.get("open",0)); hi=float(quote.get("high",0)); lo=float(quote.get("low",0)); prev=float(quote.get("close",0))
        change=(ltp/prev-1)*100 if prev else 0
        cols=st.columns(4)
        with cols[0]:metric("Bank Nifty LTP",f"{ltp:,.2f}",f"{change:+.2f}% vs previous close")
        with cols[1]:metric("Session high",f"{hi:,.2f}")
        with cols[2]:metric("Session low",f"{lo:,.2f}")
        with cols[3]:metric("Session open",f"{op:,.2f}")
        st.caption("Quote timestamp is the dashboard request time; API payload timestamp may be available through WebSocket feed.")
        con=db()
        con.execute("INSERT OR REPLACE INTO quote_snapshots VALUES(?,?,?,?,?,?,?,?)",
                    (now.isoformat(timespec="seconds"),"NIFTY BANK",ltp,op,hi,lo,prev,"Motilal Oswal API"))
        con.commit();con.close()
else:
    st.info("Offline mode selected. No market value is shown as live.")

tabs=st.tabs(["Daily cockpit","Astro & KP","Signals & risk","Dasha research","Data & sources"])
with tabs[0]:
    st.markdown("### Today's trading cockpit")
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
    st.markdown("- [Motilal Oswal API portal](https://invest.motilaloswal.com/moAPI)")
    st.markdown("- [Motilal Oswal API documentation](https://invest.motilaloswal.com/moAPI/APIDocumentation/Introduction)")
    st.markdown("- [NSE Indices historical data](https://www.niftyindices.com/reports/historical-data)")
    st.markdown("- [NSE historical reports](https://www.nseindia.com/static/resources/historical-reports-capital-market-daily-monthly-archives)")
    st.markdown("- [INDstocks API reference](https://documenter.getpostman.com/view/56363899/2sBY4LShyj) — secondary connector subject to account/API entitlement confirmation.")
    st.caption("Bank Nifty index code must be looked up from Motilal's index master and entered as MOTILAL_BANKNIFTY_INDEX_CODE. Do not guess the code.")
st.divider()
st.caption("ABNTM is an experimental research and decision-support tool, not investment advice. Validate out-of-sample and after all costs before any live trading.")
