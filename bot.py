import os, requests, yfinance as yf
from datetime import datetime
from collections import defaultdict
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8656039428:AAGMmcl5sjFvlV68yw2w8qpxq3VlsSv8U9U")
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
    r = requests.get(f"https://v6.exchangerate-api.com/v6/{EXCHANGE_KEY}/latest/USD", timeout=10)
    r.raise_for_status()
    return r.json()["conversion_rates"]

def get_gold():
    try:
        # Use yfinance for gold price
        gold = yf.Ticker("GC=F")
        info = gold.fast_info
        price = info.last_price
        prev = info.previous_close
        chg = price - prev
        pct = (chg / prev * 100) if prev else 0
        sign = "+" if chg >= 0 else ""
        arrow = "🟢" if chg >= 0 else "🔴"

        # Get VND rate
        try:
            rates = get_exchange_rates()
            vnd = rates.get("VND", 25000)
        except:
            vnd = 25400

        luong_vnd = price * 1.2057 * vnd
        return (f"🥇 *Giá Vàng Thế Giới*\n{'─'*28}\n"
                f"{arrow} XAU/USD: *${price:,.2f}/oz*\n"
                f"📈 Thay đổi: *{sign}{chg:.2f} ({sign}{pct:.2f}%)*\n"
                f"⚖️ 1 lượng: *{luong_vnd/1e6:.3f}M đ*\n"
                f"💱 USD/VND: *{vnd:,.0f}*\n\n_📡 Yahoo Finance_")
    except Exception as e:
        return f"❌ Lỗi vàng: {e}"

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
    except Exception as e:
        return f"❌ Lỗi tỷ giá: {e}"

def get_stock(sym):
    """Universal stock lookup via yfinance"""
    try:
        # Map VN stocks to Yahoo Finance format
        vn_suffix = ["VNM","HPG","VIC","VHM","TCB","MSN","MWG","VPB","BID","CTG",
                     "GAS","SAB","VRE","PLX","HDB","MBB","ACB","STB","VJC","FPT",
                     "REE","PNJ","DXG","NVL","PDR","VCI","SSI","HCM","VND","SHS"]
        
        ticker_sym = sym
        is_vn = sym.upper() in vn_suffix
        if is_vn:
            ticker_sym = f"{sym.upper()}.VN"

        ticker = yf.Ticker(ticker_sym)
        info = ticker.fast_info
        price = info.last_price
        prev = info.previous_close

        if not price:
            return None

        chg = price - prev if prev else 0
        pct = (chg / prev * 100) if prev else 0
        arrow = "🟢" if chg >= 0 else "🔴"
        sign = "+" if chg >= 0 else ""
        high = info.year_high
        low = info.year_low

        # Get name
        try:
            name = ticker.info.get("shortName") or ticker.info.get("longName") or sym
        except:
            name = sym

        market = "HOSE/HNX" if is_vn else "NYSE/NASDAQ"
        currency = "VND" if is_vn else "USD"
        fmt = f"{price:,.1f}" if is_vn else f"${price:,.2f}"
        fmt_chg = f"{chg:,.1f}" if is_vn else f"${chg:,.2f}"

        return (f"{arrow} *{name} ({sym.upper()})*\n"
                f"_{market}_\n{'─'*28}\n"
                f"💰 Giá: *{fmt} {currency}*\n"
                f"📈 Thay đổi: *{sign}{fmt_chg} ({sign}{pct:.2f}%)*\n"
                f"📊 Đóng cửa hôm qua: {prev:,.1f if is_vn else f'${prev:,.2f}'}\n"
                f"📅 52w: {low:,.1f if is_vn else f'${low:,.2f}'} – {high:,.1f if is_vn else f'${high:,.2f}'}\n\n"
                f"_📡 Yahoo Finance_")
    except Exception as e:
        return None

def get_crypto(sym):
    try:
        coin_map = {
            "BTC":"BTC-USD","ETH":"ETH-USD","BNB":"BNB-USD",
            "SOL":"SOL-USD","XRP":"XRP-USD","ADA":"ADA-USD",
            "DOGE":"DOGE-USD","AVAX":"AVAX-USD","DOT":"DOT-USD"
        }
        ticker_sym = coin_map.get(sym.upper(), f"{sym.upper()}-USD")
        ticker = yf.Ticker(ticker_sym)
        info = ticker.fast_info
        price = info.last_price
        prev = info.previous_close
        if not price: return None

        chg = price - prev if prev else 0
        pct = (chg / prev * 100) if prev else 0
        arrow = "🟢" if chg >= 0 else "🔴"
        sign = "+" if chg >= 0 else ""

        # Convert to VND
        try:
            rates = get_exchange_rates()
            vnd = rates.get("VND", 25400)
            price_vnd = price * vnd
        except:
            price_vnd = 0

        return (f"{arrow} *{sym.upper()}* (Crypto)\n{'─'*28}\n"
                f"💵 USD: *${price:,.4f}*\n"
                f"🇻🇳 VND: *{price_vnd:,.0f}*\n"
                f"📈 24h: *{sign}{pct:.2f}%*\n\n_📡 Yahoo Finance_")
    except:
        return None

def smart_lookup(sym):
    sym = sym.upper().strip()
    if sym in ["XAU","GOLD","VANG","VÀNG","AU"]: return get_gold()
    if sym in ["USD","FOREX","TYGIA"]: return get_forex()

    crypto_list = ["BTC","ETH","BNB","SOL","XRP","ADA","DOGE","AVAX","DOT"]
    if sym in crypto_list:
        r = get_crypto(sym)
        return r if r else f"❌ Không lấy được giá *{sym}*."

    r = get_stock(sym)
    if r: return r

    return (f"❌ Không tìm thấy *{sym}*.\n\n"
            f"Thử:\n• CP VN: `VNM` `HPG` `VIC` `TCB`\n"
            f"• CP Mỹ: `AAPL` `TSLA` `NVDA`\n"
            f"• Crypto: `BTC` `ETH` `SOL`\n"
            f"• Vàng: `XAU` | Tỷ giá: `USD`")

# ── KEYBOARD & HANDLERS ─────────────────────────────────────

KB = ReplyKeyboardMarkup([
    ["🥇 Giá Vàng", "💱 Tỷ Giá"],
    ["📊 CP Việt Nam", "🇺🇸 CP Mỹ"],
    ["₿ Crypto", "🔔 Cảnh Báo"],
], resize_keyboard=True)

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📈 *Bot Tài Chính AI*\n\n"
        "Gõ mã bất kỳ:\n"
        "`VNM` `HPG` `VIC` — Cổ phiếu VN\n"
        "`AAPL` `TSLA` `NVDA` — Cổ phiếu Mỹ\n"
        "`BTC` `ETH` `SOL` — Crypto\n"
        "`XAU` — Giá vàng | `USD` — Tỷ giá\n\n"
        "Hoặc chọn menu 👇",
        parse_mode="Markdown", reply_markup=KB)

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    uid = update.effective_user.id
    if not check_rate(uid):
        await update.message.reply_text("⏳ Thử lại sau 1 phút."); return

    if text == "🥇 Giá Vàng":
        msg = await update.message.reply_text("⏳ Đang lấy giá vàng...")
        await msg.edit_text(get_gold(), parse_mode="Markdown"); return
    if text == "💱 Tỷ Giá":
        msg = await update.message.reply_text("⏳ Đang lấy tỷ giá...")
        await msg.edit_text(get_forex(), parse_mode="Markdown"); return
    if text == "📊 CP Việt Nam":
        await update.message.reply_text("Gõ mã: `VNM` `HPG` `VIC` `VHM` `TCB` `FPT`", parse_mode="Markdown"); return
    if text == "🇺🇸 CP Mỹ":
        await update.message.reply_text("Gõ mã: `AAPL` `TSLA` `NVDA` `AMZN` `META`", parse_mode="Markdown"); return
    if text == "₿ Crypto":
        await update.message.reply_text("Gõ mã: `BTC` `ETH` `BNB` `SOL` `XRP`", parse_mode="Markdown"); return
    if text == "🔔 Cảnh Báo":
        await update.message.reply_text(
            "🔔 *Đặt cảnh báo:*\n`/alert AAPL above 200`\n`/alert TSLA below 150`\n\n"
            "Xem: /myalerts | Xóa: /delalert AAPL", parse_mode="Markdown"); return

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
    await update.message.reply_text(f"✅ Cảnh báo: *{sym}* {sign} *{price}*", parse_mode="Markdown")

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
        await update.message.reply_text(f"✅ Đã xóa *{sym}*.", parse_mode="Markdown")
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
