# ABNTM Live Dashboard Starter — Motilal Oswal edition

## Selected configuration
Primary live market-data broker: Motilal Oswal.
Secondary option: INDstocks/INDmoney, subject to account access and terms.
Use case: personal use first.
Access target: responsive web dashboard for laptop and mobile.
Trading execution: deliberately disabled in this starter.

## What is included
- Streamlit dashboard shell with mobile-friendly layout.
- Motilal Oswal REST index quote adapter scaffold.
- Automatic 5/10/30/60-second snapshot refresh.
- Local SQLite quote snapshot storage.
- Astrology/KP, risk, Dasha research and data-provenance tabs.
- Environment variable template; no credentials embedded.

## Setup
1. Python 3.10+.
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and set credentials as environment variables (or use a secure secrets manager).
4. Register your own app at https://invest.motilaloswal.com/moAPI and follow the broker's official authentication process.
5. Obtain the Bank Nifty index code from the official Motilal index master/API documentation and set `MOTILAL_BANKNIFTY_INDEX_CODE`. Do not guess the token.
6. Run `streamlit run app.py`.

## Data sources (pick in the sidebar)
| Source | Cost | Account / keys | Static IP | Notes |
|---|---|---|---|---|
| Yahoo Finance (default) | Free | None | Not needed | Unofficial; may be delayed. Includes 1-minute intraday chart. |
| Fyers API | Free | Fyers account, `FYERS_APP_ID`, `FYERS_ACCESS_TOKEN` | Not needed for data APIs (Fyers: static IP only for order placement) | Access token must be regenerated daily. |
| Motilal Oswal API | Free with account | 8 `MOTILAL_*` settings | Check with Motilal | Original connector. |

SEBI's April 2026 retail-algo rules require a whitelisted static IP for API **order placement**. This app is read-only and never places orders.

Settings go in a local `.env` file (copied from `.env.example`); the app loads it automatically. The sidebar "Settings status" shows ✅/❌ per setting without revealing values.

## Important integration notes
- The current adapter calls Motilal's documented `getindexltpdata` REST endpoint. It is a periodic quote snapshot, not tick streaming.
- Motilal's API docs state authentication headers and show that access tokens expire at 6 AM. A robust production build must implement the supported login/token renewal flow securely and handle OTP/TOTP; this starter intentionally does not store passwords or TOTP secrets.
- For real-time intraday updates, implement Motilal's documented WebSocket Broadcast, including auth validation, index registration, heartbeat, reconnect, stale-feed detection and local timestamping.
- Add instrument-master mapping for Bank Nifty constituents and NSEFO futures/options. Confirm all security codes against current broker master files.
- Confirm the broker's API subscription, permissions, terms and rate limits directly with Motilal Oswal before deployment.
- INDstocks/INDmoney API reference lists snapshot quotes, OHLCV historical candles and WebSocket price feed. Confirm access, static-IP requirements, entitlement and legal data usage with INDmoney before enabling a second connector.

## Research/data integrity
Use NSE Indices official historical index OHLC for Bank Nifty daily price history. For derivatives, preserve contract-level expiry, strike, option type, lot size, OI, volume, IV/Greeks and timestamps from an authorised source. Keep raw files immutable; record source, download time, timezone, instrument ID and checksum. Never use current constituent membership to backfill past breadth without historical constituent/weight data.

## Next production milestones
1. Validate Motilal API credentials and retrieve the Bank Nifty index quote.
2. Add WebSocket stream and constituent instrument map.
3. Add historical OHLCV ingestion and derivatives data.
4. Integrate Swiss Ephemeris and KP engine; reconcile with the user's astrology software.
5. Backtest Dasha/transit/KP signals against technical-only baseline with walk-forward tests.
6. Add paper-trade journal and daily report. Keep order execution disabled until user explicitly requests and approves a separately reviewed implementation.
