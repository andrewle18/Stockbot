import os, requests
from datetime import datetime
from collections import defaultdict
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8656039428:AAGMmcl5sjFvlV68yw2w8qpxq3VlsSv8U9U")
FINNHUB_KEY    = os.environ.get("FINNHUB_KEY",   "d8insrhr01qmfrvi260g")
EXCHANGE_KEY   = os.environ.get("EXCHANGE_KEY",  "1f7a19905a978baa8d6af13f")
ANTHROPIC_KEY  = os.environ.get("ANTHROPIC_KEY", "")

user_requests = defaultdict(list)
watchlists    = defaultdict(dict)

def check_rate(uid):
    now = datetime.now().timestamp()
    user_requests[uid] = [t for t in user_requests[uid] if now - t < 60]
    if len(user_requests[uid]) >= 15: return False
    user_requests[uid].append(now); return True

# ── DATA ────────────────────────────────────────────────────

def get_gold():
    try:
        d = requests.get(f"https://v6.exchangerate-api.com/v6/{EXCHANGE_KEY}/latest/USD", timeout=10).json()
        xau = d["conversion_rates"].get("XAU"); vnd = d["conversion_rates"].get("VND", 0)
        usd_oz = 1 / xau
        return (f"🥇 *Giá Vàng Thế Giới*\n{'─'*28}\n"
                f"💵 XAU/USD: *${usd_oz:,.2f}/oz*\n"
                f"🇻🇳 Per lượng: *{usd_oz*1.2057*vnd/1e6:.2f}M đ*\n"
                f"💱 USD/VND: *{vnd:,.0f}*\n\n_📡 ExchangeRate API_")
    except Exception as e: return f"❌ {e}"

def get_forex():
    try:
        d = requests.get(f"https://v6.exchangerate-api.com/v6/{EXCHANGE_KEY}/latest/USD", timeout=10).json()
        r = d["conversion_rates"]; vnd = r.get("VND",0)
        def fmt(code): v=1/r.get(code,1); return f"*{v:.4f}* ({v*vnd:,.0f} đ)"
        return (f"💱 *Tỷ Giá Ngoại Tệ*\n{'─'*28}\n"
                f"🇺🇸 USD/VND: *{vnd:,.0f}*\n"
                f"🇪🇺 EUR/USD: {fmt('EUR')}\n🇯🇵 JPY/USD: {fmt('JPY')}\n"
                f"🇨🇳 CNY/USD: {fmt('CNY')}\n🇬🇧 GBP/USD: {fmt('GBP')}\n\n_📡 ExchangeRate API_")
    except Exception as e: return f"❌ {e}"

def get_stock_us(sym):
    try:
        q = requests.get(f"https://finnhub.io/api/v1/quote?symbol={sym}&token={FINNHUB_KEY}", timeout=10).json()
        p = requests.get(f"https://finnhub.io/api/v1/stock/profile2?symbol={sym}&token={FINNHUB_KEY}", timeout=10).json()
        if not q.get("c"): return f"❌ Không tìm thấy *{sym}*."
        price=q["c"]; prev=q["pc"]; chg=price-prev; pct=(chg/prev*100) if prev else 0
        arrow="🟢" if chg>=0 else "🔴"; sign="+" if chg>=0 else ""
        name=p.get("name",sym)
        return (f"{arrow} *{name} ({sym})*\n{'─'*28}\n"
                f"💵 Giá: *${price:.2f}*\n📈 Thay đổi: *{sign}{chg:.2f} ({sign}{pct:.2f}%)*\n"
                f"🔺 Cao: ${q['h']:.2f}  🔻 Thấp: ${q['l']:.2f}\n"
                f"📊 Tham chiếu: ${prev:.2f}\n\n_📡 Finnhub_")
    except Exception as e: return f"❌ {e}"

def get_stock_vn(sym):
    try:
        r = requests.get(f"https://iboard-query.ssi.com.vn/v2/stock/q?symbol={sym}",
                         headers={"Accept":"application/json"}, timeout=10)
        if r.status_code==200:
            d=r.json().get("data",{})
            price=d.get("lastPrice") or d.get("matchPrice",0)
            ref=d.get("refPrice",0); chg=price-ref if price and ref else 0
            pct=(chg/ref*100) if ref else 0
            arrow="🟢" if chg>=0 else "🔴"; sign="+" if chg>=0 else ""
            vol=d.get("totalVolume",0)
            return (f"{arrow} *{sym}* (HOSE/HNX)\n{'─'*28}\n"
                    f"💰 Giá: *{price:,.1f}*\n📈 Thay đổi: *{sign}{chg:,.1f} ({sign}{pct:.2f}%)*\n"
                    f"🔺 Cao: {d.get('highPrice',0):,.1f}  🔻 Thấp: {d.get('lowPrice',0):,.1f}\n"
                    f"📦 KL: {vol:,}\n\n_📡 SSI iBoard_")
        return f"❌ Không tìm thấy *{sym}*."
    except Exception as e: return f"❌ {e}"

def get_crypto(sym):
    try:
        coin_map={"BTC":"bitcoin","ETH":"ethereum","BNB":"binancecoin","SOL":"solana",
                  "XRP":"ripple","ADA":"cardano","DOGE":"dogecoin","AVAX":"avalanche-2","DOT":"polkadot"}
        cid=coin_map.get(sym.upper(), sym.lower())
        d=requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={cid}&vs_currencies=usd,vnd&include_24hr_change=true",timeout=10).json()
        if cid not in d: return f"❌ Không tìm thấy *{sym}*."
        data=d[cid]; chg=data.get("usd_24h_change",0)
        arrow="🟢" if chg>=0 else "🔴"; sign="+" if chg>=0 else ""
        return (f"{arrow} *{sym.upper()}* (Crypto)\n{'─'*28}\n"
                f"💵 USD: *${data['usd']:,.2f}*\n"
                f"🇻🇳 VND: *{data.get('vnd',0):,.0f}*\n"
                f"📈 24h: *{sign}{chg:.2f}%*\n\n_📡 CoinGecko_")
    except Exception as e: return f"❌ {e}"

def ai_analyze(sym, price_text):
    if not ANTHROPIC_KEY: return ""
    try:
        r=requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key":ANTHROPIC_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"},
            json={"model":"claude-haiku-4-5-20251001","max_tokens":200,
                  "messages":[{"role":"user","content":f"Phân tích ngắn {sym}:\n{price_text}\nNhận định 2-3 câu + rủi ro (Thấp/TB/Cao). Tiếng Việt, súc tích."}]},
            timeout=15).json()
        return "\n\n🤖 *Phân tích AI:*\n" + r["content"][0]["text"]
    except: return ""

# ── HANDLERS ────────────────────────────────────────────────

KB = ReplyKeyboardMarkup([
    ["🥇 Giá Vàng","💱 Tỷ Giá"],
    ["📊 CP Việt Nam","🇺🇸 CP Mỹ"],
    ["₿ Crypto","🔔 Cảnh Báo"],
], resize_keyboard=True)

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📈 *Bot Tài Chính AI*\n\n"
        "Gõ mã bất kỳ: `AAPL`, `VNM`, `BTC`, `XAU`\n"
        "Hoặc chọn menu:",
        parse_mode="Markdown", reply_markup=KB)

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text=update.message.text.strip(); uid=update.effective_user.id
    if not check_rate(uid):
        await update.message.reply_text("⏳ Thử lại sau 1 phút."); return

    if text=="🥇 Giá Vàng":
        msg=await update.message.reply_text("⏳...")
        await msg.edit_text(get_gold(), parse_mode="Markdown"); return
    if text=="💱 Tỷ Giá":
        msg=await update.message.reply_text("⏳...")
        await msg.edit_text(get_forex(), parse_mode="Markdown"); return
    if text=="📊 CP Việt Nam":
        await update.message.reply_text("Gõ mã VN: `VNM`, `HPG`, `VIC`, `TCB`, `MSN`", parse_mode="Markdown"); return
    if text=="🇺🇸 CP Mỹ":
        await update.message.reply_text("Gõ mã Mỹ: `AAPL`, `TSLA`, `NVDA`, `AMZN`", parse_mode="Markdown"); return
    if text=="₿ Crypto":
        await update.message.reply_text("Gõ mã: `BTC`, `ETH`, `BNB`, `SOL`, `XRP`", parse_mode="Markdown"); return
    if text=="🔔 Cảnh Báo":
        await update.message.reply_text(
            "🔔 *Đặt cảnh báo:*\n`/alert AAPL above 200`\n`/alert TSLA below 150`\n\n"
            "Xem: /myalerts\nXóa: /delalert AAPL", parse_mode="Markdown"); return

    sym=text.upper().replace(" ","")
    if sym in ["XAU","GOLD","VANG","VÀNG"]:
        msg=await update.message.reply_text("⏳..."); await msg.edit_text(get_gold(),parse_mode="Markdown"); return
    if sym in ["USD","FOREX","TỶGIÁ","TY GIA"]:
        msg=await update.message.reply_text("⏳..."); await msg.edit_text(get_forex(),parse_mode="Markdown"); return

    crypto_list=["BTC","ETH","BNB","SOL","XRP","ADA","DOGE","AVAX","DOT"]
    if sym in crypto_list:
        msg=await update.message.reply_text(f"⏳ Lấy giá *{sym}*...",parse_mode="Markdown")
        r=get_crypto(sym); await msg.edit_text(r+ai_analyze(sym,r),parse_mode="Markdown"); return

    if len(sym)<=5 and sym.isalpha():
        msg=await update.message.reply_text(f"⏳ Tìm *{sym}*...",parse_mode="Markdown")
        vn=get_stock_vn(sym)
        if "❌" not in vn: await msg.edit_text(vn+ai_analyze(sym,vn),parse_mode="Markdown"); return
        us=get_stock_us(sym)
        if "❌" not in us: await msg.edit_text(us+ai_analyze(sym,us),parse_mode="Markdown"); return
        await msg.edit_text(f"❌ Không tìm thấy *{sym}*.\nThử: `VNM`, `AAPL`, `BTC`",parse_mode="Markdown"); return

    await update.message.reply_text(f"🔍 Không nhận ra *{text}*", parse_mode="Markdown", reply_markup=KB)

async def alert_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id; args=ctx.args
    if len(args)<3:
        await update.message.reply_text("Cú pháp: `/alert AAPL above 200`",parse_mode="Markdown"); return
    sym,direction,price_str=args[0].upper(),args[1].lower(),args[2]
    try: price=float(price_str)
    except: await update.message.reply_text("❌ Giá không hợp lệ."); return
    if direction not in ["above","below"]:
        await update.message.reply_text("❌ Dùng `above` hoặc `below`.",parse_mode="Markdown"); return
    watchlists[uid][sym]={direction:price}
    sign=">" if direction=="above" else "<"
    await update.message.reply_text(f"✅ Cảnh báo: *{sym}* {sign} *{price}*",parse_mode="Markdown")

async def myalerts_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id; alerts=watchlists.get(uid,{})
    if not alerts: await update.message.reply_text("Chưa có cảnh báo.\nDùng `/alert AAPL above 200`",parse_mode="Markdown"); return
    lines=["🔔 *Cảnh báo của bạn:*"]
    for s,a in alerts.items():
        if "above" in a: lines.append(f"• {s} > {a['above']}")
        if "below" in a: lines.append(f"• {s} < {a['below']}")
    await update.message.reply_text("\n".join(lines),parse_mode="Markdown")

async def delalert_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id
    if not ctx.args: await update.message.reply_text("Cú pháp: `/delalert AAPL`",parse_mode="Markdown"); return
    sym=ctx.args[0].upper()
    if sym in watchlists[uid]: del watchlists[uid][sym]; await update.message.reply_text(f"✅ Đã xóa *{sym}*.",parse_mode="Markdown")
    else: await update.message.reply_text(f"❌ Không có cảnh báo *{sym}*.",parse_mode="Markdown")

def main():
    app=Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("alert",alert_cmd))
    app.add_handler(CommandHandler("myalerts",myalerts_cmd))
    app.add_handler(CommandHandler("delalert",delalert_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("✅ Finance Bot running...")
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__": main()
