import os, requests
from datetime import datetime
from collections import defaultdict
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8656039428:AAGMmcl5sjFvlV68yw2w8qpxq3VlsSv8U9U")
FINNHUB_KEY    = os.environ.get("FINNHUB_KEY",   "d8insrhr01qmfrvi260g")
EXCHANGE_KEY   = os.environ.get("EXCHANGE_KEY",  "1f7a19905a978baa8d6af13f")

user_requests = defaultdict(list)
watchlists    = defaultdict(dict)

def check_rate(uid):
    now = datetime.now().timestamp()
    user_requests[uid] = [t for t in user_requests[uid] if now - t < 60]
    if len(user_requests[uid]) >= 15: return False
    user_requests[uid].append(now); return True

# ── DATA ────────────────────────────────────────────────────

def get_exchange_rates():
    """Fetch once, reuse for gold + forex"""
    r = requests.get(f"https://v6.exchangerate-api.com/v6/{EXCHANGE_KEY}/latest/USD", timeout=10)
    r.raise_for_status()
    return r.json()["conversion_rates"]

def get_gold():
    try:
        rates = get_exchange_rates()
        xau = rates.get("XAU"); vnd = rates.get("VND", 0)
        if not xau: return "❌ Không lấy được giá vàng."
        usd_oz = 1 / xau
        luong_vnd = usd_oz * 1.2057 * vnd
        return (f"🥇 *Giá Vàng Thế Giới*\n{'─'*28}\n"
                f"💵 XAU/USD: *${usd_oz:,.2f}/oz*\n"
                f"⚖️ 1 lượng: *{luong_vnd/1e6:.3f}M đ*\n"
                f"💱 USD/VND: *{vnd:,.0f}*\n\n_📡 ExchangeRate API_")
    except Exception as e: return f"❌ Lỗi vàng: {e}"

def get_forex():
    try:
        rates = get_exchange_rates()
        vnd = rates.get("VND", 0)
        def fmt(code):
            v = 1 / rates.get(code, 1)
            return f"*{v:.4f}* ({v*vnd:,.0f} đ)"
        return (f"💱 *Tỷ Giá Ngoại Tệ*\n{'─'*28}\n"
                f"🇺🇸 USD/VND: *{vnd:,.0f}*\n"
                f"🇪🇺 EUR: {fmt('EUR')}\n"
                f"🇯🇵 JPY: {fmt('JPY')}\n"
                f"🇨🇳 CNY: {fmt('CNY')}\n"
                f"🇬🇧 GBP: {fmt('GBP')}\n\n_📡 ExchangeRate API_")
    except Exception as e: return f"❌ Lỗi tỷ giá: {e}"

def get_stock_us(sym):
    try:
        q = requests.get(f"https://finnhub.io/api/v1/quote?symbol={sym}&token={FINNHUB_KEY}", timeout=10).json()
        p = requests.get(f"https://finnhub.io/api/v1/stock/profile2?symbol={sym}&token={FINNHUB_KEY}", timeout=10).json()
        price = q.get("c", 0)
        if not price: return None
        prev = q.get("pc", 0); chg = price - prev
        pct = (chg / prev * 100) if prev else 0
        arrow = "🟢" if chg >= 0 else "🔴"; sign = "+" if chg >= 0 else ""
        name = p.get("name", sym)
        return (f"{arrow} *{name} ({sym})*\n{'─'*28}\n"
                f"💵 Giá: *${price:.2f}*\n"
                f"📈 Thay đổi: *{sign}{chg:.2f} ({sign}{pct:.2f}%)*\n"
                f"🔺 Cao: ${q.get('h',0):.2f}  🔻 Thấp: ${q.get('l',0):.2f}\n"
                f"📊 Tham chiếu: ${prev:.2f}\n\n_📡 Finnhub_")
    except Exception as e: return None

def get_stock_vn(sym):
    """Try multiple VN stock APIs"""
    # API 1: VNDirect
    try:
        url = f"https://finfo-api.vndirect.com.vn/v4/stocks?q=code:{sym}&fields=code,floor,type,ceilingPrice,floorPrice,referencePrice,matchPrice,matchVolume,priceChange,percentPriceChange,totalMatchVolume,highPrice,lowPrice"
        r = requests.get(url, headers={"Accept": "application/json"}, timeout=10)
        if r.status_code == 200:
            data = r.json().get("data", [])
            if data:
                d = data[0]
                price = d.get("matchPrice") or d.get("referencePrice", 0)
                ref = d.get("referencePrice", 0)
                chg = d.get("priceChange", 0) or (price - ref)
                pct = d.get("percentPriceChange", 0) or ((chg/ref*100) if ref else 0)
                high = d.get("highPrice", 0); low = d.get("lowPrice", 0)
                vol = d.get("totalMatchVolume", 0)
                arrow = "🟢" if chg >= 0 else "🔴"; sign = "+" if chg >= 0 else ""
                floor = d.get("floor", "HOSE")
                return (f"{arrow} *{sym}* ({floor})\n{'─'*28}\n"
                        f"💰 Giá: *{price:,.2f}*\n"
                        f"📈 Thay đổi: *{sign}{chg:,.2f} ({sign}{pct:.2f}%)*\n"
                        f"🔺 Cao: {high:,.2f}  🔻 Thấp: {low:,.2f}\n"
                        f"📊 Tham chiếu: {ref:,.2f}\n"
                        f"📦 KL: {vol:,}\n\n_📡 VNDirect_")
    except: pass

    # API 2: MSN/Cafef style via tcbs
    try:
        url2 = f"https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/bars-long-term?ticker={sym}&type=stock&resolution=D&from=1700000000&to=9999999999"
        r2 = requests.get(url2, timeout=10)
        if r2.status_code == 200:
            bars = r2.json().get("data", [])
            if bars:
                last = bars[-1]
                price = last.get("close", 0)
                prev = bars[-2].get("close", 0) if len(bars) > 1 else price
                chg = price - prev; pct = (chg/prev*100) if prev else 0
                arrow = "🟢" if chg >= 0 else "🔴"; sign = "+" if chg >= 0 else ""
                return (f"{arrow} *{sym}* (VN)\n{'─'*28}\n"
                        f"💰 Giá đóng cửa: *{price:,.2f}*\n"
                        f"📈 Thay đổi: *{sign}{chg:,.2f} ({sign}{pct:.2f}%)*\n"
                        f"🔺 Cao: {last.get('high',0):,.2f}  🔻 Thấp: {last.get('low',0):,.2f}\n"
                        f"📦 KL: {last.get('volume',0):,}\n\n_📡 TCBS_")
    except: pass

    return None

def get_crypto(sym):
    """CoinGecko free API"""
    try:
        coin_map = {
            "BTC":"bitcoin","ETH":"ethereum","BNB":"binancecoin",
            "SOL":"solana","XRP":"ripple","ADA":"cardano",
            "DOGE":"dogecoin","AVAX":"avalanche-2","DOT":"polkadot","USDT":"tether"
        }
        cid = coin_map.get(sym.upper(), sym.lower())
        headers = {"accept": "application/json"}
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={cid}&vs_currencies=usd,vnd&include_24hr_change=true&include_market_cap=true"
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        d = r.json()
        if cid not in d: return None
        data = d[cid]
        chg = data.get("usd_24h_change", 0)
        arrow = "🟢" if chg >= 0 else "🔴"; sign = "+" if chg >= 0 else ""
        mcap = data.get("usd_market_cap", 0)
        return (f"{arrow} *{sym.upper()}* (Crypto)\n{'─'*28}\n"
                f"💵 USD: *${data['usd']:,.4f}*\n"
                f"🇻🇳 VND: *{data.get('vnd',0):,.0f}*\n"
                f"📈 24h: *{sign}{chg:.2f}%*\n"
                f"💎 Vốn hóa: ${mcap/1e9:.2f}B\n\n_📡 CoinGecko_")
    except Exception as e:
        return None

def smart_lookup(sym):
    """Auto-detect and lookup symbol"""
    sym = sym.upper().strip()

    # Gold keywords
    if sym in ["XAU","GOLD","VANG","VÀNG","AU"]:
        return get_gold()

    # Forex keywords
    if sym in ["USD","FOREX","TYGIA","NGOAITE"]:
        return get_forex()

    # Known crypto
    crypto_list = ["BTC","ETH","BNB","SOL","XRP","ADA","DOGE","AVAX","DOT","USDT"]
    if sym in crypto_list:
        return get_crypto(sym)

    # Try VN stock first (shorter codes)
    if len(sym) <= 3:
        vn = get_stock_vn(sym)
        if vn: return vn

    # Try US stock
    us = get_stock_us(sym)
    if us: return us

    # Try VN stock (longer codes like VHM, HPG)
    vn = get_stock_vn(sym)
    if vn: return vn

    # Try crypto as fallback
    crypto = get_crypto(sym)
    if crypto: return crypto

    return f"❌ Không tìm thấy *{sym}*.\n\nThử:\n• CP VN: `VNM`, `HPG`, `VIC`, `TCB`\n• CP Mỹ: `AAPL`, `TSLA`, `NVDA`\n• Crypto: `BTC`, `ETH`, `SOL`\n• Vàng: `XAU`\n• Tỷ giá: `USD`"

# ── KEYBOARD ────────────────────────────────────────────────

KB = ReplyKeyboardMarkup([
    ["🥇 Giá Vàng", "💱 Tỷ Giá"],
    ["📊 CP Việt Nam", "🇺🇸 CP Mỹ"],
    ["₿ Crypto", "🔔 Cảnh Báo"],
], resize_keyboard=True)

# ── HANDLERS ────────────────────────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📈 *Bot Tài Chính AI*\n\n"
        "Gõ mã bất kỳ:\n"
        "`VNM` `HPG` `VIC` — Cổ phiếu VN\n"
        "`AAPL` `TSLA` `NVDA` — Cổ phiếu Mỹ\n"
        "`BTC` `ETH` `SOL` — Crypto\n"
        "`XAU` — Giá vàng\n"
        "`USD` — Tỷ giá\n\n"
        "Hoặc chọn menu bên dưới 👇",
        parse_mode="Markdown", reply_markup=KB)

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    uid = update.effective_user.id
    if not check_rate(uid):
        await update.message.reply_text("⏳ Thử lại sau 1 phút."); return

    # Menu buttons
    if text == "🥇 Giá Vàng":
        msg = await update.message.reply_text("⏳ Đang lấy giá vàng...")
        await msg.edit_text(get_gold(), parse_mode="Markdown"); return
    if text == "💱 Tỷ Giá":
        msg = await update.message.reply_text("⏳ Đang lấy tỷ giá...")
        await msg.edit_text(get_forex(), parse_mode="Markdown"); return
    if text == "📊 CP Việt Nam":
        await update.message.reply_text("Gõ mã CP VN:\n`VNM` `HPG` `VIC` `VHM` `TCB` `MSN` `MWG`", parse_mode="Markdown"); return
    if text == "🇺🇸 CP Mỹ":
        await update.message.reply_text("Gõ mã CP Mỹ:\n`AAPL` `TSLA` `NVDA` `AMZN` `MSFT` `META`", parse_mode="Markdown"); return
    if text == "₿ Crypto":
        await update.message.reply_text("Gõ mã crypto:\n`BTC` `ETH` `BNB` `SOL` `XRP` `DOGE`", parse_mode="Markdown"); return
    if text == "🔔 Cảnh Báo":
        await update.message.reply_text(
            "🔔 *Đặt cảnh báo giá:*\n\n"
            "`/alert AAPL above 200` — báo khi > $200\n"
            "`/alert TSLA below 150` — báo khi < $150\n\n"
            "Xem danh sách: /myalerts\n"
            "Xóa: /delalert AAPL", parse_mode="Markdown"); return

    # Auto lookup
    msg = await update.message.reply_text(f"🔍 Đang tìm *{text.upper()}*...", parse_mode="Markdown")
    result = smart_lookup(text)
    await msg.edit_text(result, parse_mode="Markdown")

async def alert_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; args = ctx.args
    if len(args) < 3:
        await update.message.reply_text("Cú pháp: `/alert AAPL above 200`", parse_mode="Markdown"); return
    sym, direction, price_str = args[0].upper(), args[1].lower(), args[2]
    try: price = float(price_str)
    except: await update.message.reply_text("❌ Giá không hợp lệ."); return
    if direction not in ["above","below"]:
        await update.message.reply_text("❌ Dùng `above` hoặc `below`.", parse_mode="Markdown"); return
    watchlists[uid][sym] = {direction: price}
    sign = ">" if direction == "above" else "<"
    await update.message.reply_text(f"✅ Cảnh báo: *{sym}* {sign} *{price}*\nBot ping bạn khi đạt ngưỡng!", parse_mode="Markdown")

async def myalerts_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; alerts = watchlists.get(uid, {})
    if not alerts:
        await update.message.reply_text("Chưa có cảnh báo.\nDùng `/alert AAPL above 200`", parse_mode="Markdown"); return
    lines = ["🔔 *Cảnh báo của bạn:*"]
    for s, a in alerts.items():
        if "above" in a: lines.append(f"• {s} > {a['above']}")
        if "below" in a: lines.append(f"• {s} < {a['below']}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def delalert_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not ctx.args:
        await update.message.reply_text("Cú pháp: `/delalert AAPL`", parse_mode="Markdown"); return
    sym = ctx.args[0].upper()
    if sym in watchlists[uid]:
        del watchlists[uid][sym]
        await update.message.reply_text(f"✅ Đã xóa cảnh báo *{sym}*.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ Không có cảnh báo *{sym}*.", parse_mode="Markdown")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("alert", alert_cmd))
    app.add_handler(CommandHandler("myalerts", myalerts_cmd))
    app.add_handler(CommandHandler("delalert", delalert_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("✅ Finance Bot running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__": main()
