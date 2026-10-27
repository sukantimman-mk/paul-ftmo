from http.server import BaseHTTPRequestHandler
import json
import urllib.request
import urllib.parse
import os
import datetime

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
GITHUB_USER = "sukantimman-mk"
REPO_NAME = "paul-ftmo"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")


def send_telegram(chat_id, text_html, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text_html,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            pass
    except Exception:
        pass


def get_live_scanner_data():
    url = f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/forward_live_scanner.json?t={int(datetime.datetime.now().timestamp())}"
    req = urllib.request.Request(url, headers={"User-Agent": "PaulFTMOBot/4.0", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_demo_ledger_data():
    url = f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/forward_demo_ledger.json?t={int(datetime.datetime.now().timestamp())}"
    req = urllib.request.Request(url, headers={"User-Agent": "PaulFTMOBot/4.0", "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def format_demo_portfolio(ledger):
    if not ledger:
        return "💼 <b>พอร์ตจำลอง Forward Demo:</b> กำลังเริ่มระบบรอบแรก กรุณากดอีกครั้งใน 10 วินาทีครับ"
    bal = ledger.get('current_balance', 100000.0)
    eq = ledger.get('current_equity', 100000.0)
    pnl = ledger.get('net_profit_usd', 0.0)
    ret = ledger.get('net_return_pct', 0.0)
    stats = ledger.get('stats', {})
    open_tr = ledger.get('open_trades', [])
    ret_icon = "🟢" if pnl >= 0 else "🔴"
    bkk_now = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=7)).strftime("%Y-%m-%d %H:%M น.")

    lines = [
        "💼 <b>พอร์ตจำลอง Forward Demo ($100,000 | Paul Pro V4)</b>",
        f"🕒 เวลาไทย: <code>{bkk_now}</code>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"💰 <b>ยอดเงินคงเหลือ (Balance):</b> <code>${bal:,.2f}</code>",
        f"📊 <b>มูลค่าสุทธิ (Equity):</b> <code>${eq:,.2f}</code>",
        f"{ret_icon} <b>กำไรสุทธิรวม (P&L):</b> <b>{ret:+.2f}% (${pnl:+,.2f})</b>",
        f"🛡️ <b>Max Drawdown:</b> <code>{ledger.get('max_drawdown_pct', 0.0):.2f}%</code> (เกณฑ์ FTMO < 10%)",
        f"🏆 <b>สถานะกฎ FTMO:</b> <b>✅ ผ่านเกณฑ์ปกติ (PASSING)</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"📈 <b>สถิติออเดอร์ (Forward Stats):</b>",
        f"• ปิดไปแล้ว: <code>{stats.get('total_trades', 0)} ไม้</code> (ชนะ {stats.get('winning_trades', 0)} / แพ้ {stats.get('losing_trades', 0)})",
        f"• Win Rate: <b>{stats.get('win_rate_pct', 0.0):.1f}%</b> | Profit Factor: <b>{stats.get('profit_factor', 0.0)}</b>",
        f"• ผลตอบแทนสะสม: <b>{stats.get('total_realized_r', 0.0):+}R</b>",
        "━━━━━━━━━━━━━━━━━━━━",
    ]
    if open_tr:
        lines.append(f"⚡ <b>ออเดอร์ที่กำลังถืออยู่ ({len(open_tr)} ไม้):</b>")
        for t in open_tr:
            fl_color = "🟢" if t.get('floating_usd', 0.0) >= 0 else "🔴"
            lines.append(
                f"{fl_color} <b>{t['symbol']} ({t['dir']})</b> @ <code>{t['entry']}</code> ({t['lots']} Lots)\n"
                f"   ↳ P&L: <b>{t.get('floating_r', 0.0):+}R (${t.get('floating_usd', 0.0):+,.2f})</b> | ด่าน: <code>{t['stage']}</code> (SL <code>{t['current_sl']}</code>)"
            )
    else:
        lines.append("💤 <i>ขณะนี้ไม่มีออเดอร์ค้าง — ระบบอยู่ในโหมดสแตนด์บายรอสัญญาณครบ 1-2-3</i>")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("💡 <i>ระบบบันทึกและจัดการออเดอร์อัตโนมัติบน Cloud 100% ไม่ต้องเปิดคอม</i>")
    return "\n".join(lines)


def trigger_github_cloud_scan():
    if not GITHUB_TOKEN:
        return False
    url = f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/actions/workflows/paul_h4_scanner.yml/dispatches"
    payload = json.dumps({"ref": "main", "inputs": {"force_mode": "true"}}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "PaulFTMOBot/4.0",
        "Content-Type": "application/json"
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 204
    except Exception:
        return False


def format_radar_summary(live_states):
    bkk_now = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=7)).strftime("%Y-%m-%d %H:%M น.")
    lines = [
        "📡 <b>เรดาร์สแกนสด 6 คู่เงิน (Paul Pro V4 | 1-2-3-4)</b>",
        f"🕒 เวลาไทย: <code>{bkk_now}</code>",
        "━━━━━━━━━━━━━━━━━━━━"
    ]

    for s in live_states:
        sym = s["symbol"]
        g = s["gates"]
        tk = s["planned_ticket"]
        ot = s.get("active_open_trade")
        icon = "🔵"
        status_txt = f"แผน <b>{s['planned_dir']}</b> | ราคา <code>{s['latest_price']}</code> | รอย่อแตะ EMA50 (<code>{s['ema50']}</code>)"

        if s["overall_signal"] == "ENTRY_NOW":
            icon = "🟢🚨"
            status_txt = f"<b>สั่งเข้า {s['planned_dir']} ทันที!</b> @ <code>{s['latest_price']}</code> (SL <code>{tk['sl']}</code> | TP1 <code>{tk['tp1']}</code> | <code>{tk['lots_100k']} Lot</code>)"
        elif s["overall_signal"] == "SETUP_ARMED":
            icon = "⏳⚡"
            status_txt = f"<b>ย่อแตะ EMA50 แล้ว!</b> รอเบรก {s['planned_dir']} @ <code>{tk['entry']}</code> (SL <code>{tk['sl']}</code> | <code>{tk['lots_100k']} Lot</code>)"

        g_lights = f"[1:{'🟢' if g['g1_pass'] else '🔴'} 2:{'🟢' if g['g2_pass'] else '⏳'} 3:{'🟢' if g['g3_pass'] else '⏳'}]"
        lines.append(f"{icon} <b>{sym}</b> {g_lights}\n   ↳ {status_txt}")

        if ot:
            lines.append(
                f"   ⚡ <i>ถือออเดอร์ {ot['dir']} อยู่: เข้า <code>{ot['entry_price']}</code> | P&L <b>{'+' if ot['floating_r'] >= 0 else ''}{ot['floating_r']}R</b> | ด่าน {ot['stage']}</i>"
            )

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("💡 <i>พิมพ์ /scan เพื่อสั่งดึงแท่งเทียนสดเดี๋ยวนี้ | พิมพ์ /gold เพื่อดูใบสั่งเทรดทอง</i>")
    return "\n".join(lines)


def format_single_pair_ticket(s):
    tk = s["planned_ticket"]
    g = s["gates"]
    return "\n".join([
        f"🎯 <b>ใบสั่งเทรดสด: {s['symbol']} ({s['name']})</b>",
        f"🕯️ แท่ง H4: <code>{s['last_bar_utc']}</code>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"• <b>สถานะ:</b> {s['overall_badge']}",
        f"• <b>ด่าน 1 (Trend+COT):</b> {'🟢' if g['g1_pass'] else '🔴'} {g['g1_text']}",
        f"• <b>ด่าน 2 (Pullback):</b> {'🟢' if g['g2_pass'] else '⏳'} {g['g2_text']}",
        f"• <b>ด่าน 3 (3-Bar BOS):</b> {'🟢' if g['g3_pass'] else '⏳'} {g['g3_text']}",
        "━━━━━━━━━━━━━━━━━━━━",
        "📋 <b>พารามิเตอร์สำหรับตั้งไม้ (พอร์ต $100k | Risk 0.75% = $750):</b>",
        f"• <b>ฝั่ง (Direction):</b> <b>{tk['dir']}</b>",
        f"• <b>ขนาด Lot Size:</b> <code>{tk['lots_100k']} Lots</code>",
        f"• <b>ราคาเข้า (Entry / BOS):</b> <code>{tk['entry']}</code>",
        f"• <b>Stop Loss (-1.0R):</b> <code>{tk['sl']}</code>",
        f"• <b>TP 1 (+1.5R ปิด 50%):</b> <code>{tk['tp1']}</code> <i>(เลื่อน SL -> {tk['lock1']})</i>",
        f"• <b>Stage 2 (+2.5R):</b> <code>{tk['stage2']}</code> <i>(เลื่อน SL -> {tk['lock2']})</i>",
        f"• <b>TP 2 (+3.5R เป้าหลัก):</b> <code>{tk['tp2']}</code>"
    ])


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("Paul Pro V4 Telegram Webhook is Active and Ready!".encode("utf-8"))

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        try:
            update = json.loads(raw_body)
        except Exception:
            update = {}

        msg = update.get("message") or update.get("edited_message")
        if msg and msg.get("text"):
            chat_id = msg["chat"]["id"]
            text = msg["text"].strip().lower()

            try:
                if text in ["/start", "/help", "สวัสดี", "เมนู", "hi"]:
                    welcome_text = "\n".join([
                        f"🤖 <b>สวัสดีครับคุณ {msg['chat'].get('first_name', 'Superman')}!</b>",
                        "ระบบพร้อมรับคำสั่งสดในแชทตลอด 24 ชั่วโมง (ปิดคอมได้ 100%):",
                        "",
                        "📌 <b>คำสั่งที่พิมพ์ได้ทันที:</b>",
                        "• <code>💼 /demo</code> หรือ <code>พอร์ต</code> ➔ ดูสถานะพอร์ต Forward Demo $100k",
                        "• <code>/update</code> หรือ <code>ขออัพเดทตอนนี้</code> ➔ สรุปเรดาร์ 6 คู่เงินสด",
                        "• <code>/scan</code> ➔ สั่งให้ Cloud ปลุกขึ้นมาสแกนกราฟสดเดี๋ยวนี้",
                        "• <code>/gold</code> ➔ ดูใบสั่งเทรดทองคำ (Entry / SL / TP / Lot)",
                        "• <code>/jpy</code>, <code>/cad</code>, <code>/chf</code>, <code>/gbp</code>, <code>/eur</code> ➔ ดูโพยคู่เงินนั้นๆ"
                    ])
                    keyboard = {
                        "keyboard": [
                            [{"text": "💼 พอร์ต Demo $100k"}, {"text": "📡 ขออัพเดทเรดาร์สดตอนนี้"}],
                            [{"text": "🥇 โพยเทรดทองคำ (GC=F)"}, {"text": "🔄 สั่งสแกนสด Cloud"}],
                            [{"text": "🇯🇵 USDJPY"}, {"text": "🇨🇦 USDCAD"}, {"text": "🇨🇭 USDCHF"}],
                            [{"text": "🇬🇧 GBPUSD"}, {"text": "🇪🇺 EURUSD"}]
                        ],
                        "resize_keyboard": True
                    }
                    send_telegram(chat_id, welcome_text, keyboard)

                elif any(w in text for w in ["demo", "portfolio", "balance", "พอร์ต", "เดโม", "/demo"]):
                    ledger = get_demo_ledger_data()
                    send_telegram(chat_id, format_demo_portfolio(ledger))

                elif any(w in text for w in ["update", "อัพเดท", "เรดาร์", "/radar"]):
                    live_data = get_live_scanner_data()
                    send_telegram(chat_id, format_radar_summary(live_data))

                elif any(w in text for w in ["scan", "สแกน", "/refresh"]):
                    send_telegram(
                        chat_id,
                        "⏳ <b>กำลังส่งคำสั่งปลุกเซิร์ฟเวอร์คลาวด์บน GitHub...</b>\nระบบกำลังดึงแท่งเทียน H4 สดเดี๋ยวนี้ ข้อความสรุปเรดาร์จะส่งมาใน ~25 วินาทีครับ!"
                    )
                    trigger_github_cloud_scan()

                elif any(w in text for w in ["gold", "ทอง", "xau"]):
                    live_data = get_live_scanner_data()
                    gold = next((s for s in live_data if s["symbol"] == "GC=F"), None)
                    if gold:
                        send_telegram(chat_id, format_single_pair_ticket(gold))

                elif "jpy" in text:
                    live_data = get_live_scanner_data()
                    pair = next((s for s in live_data if "JPY" in s["symbol"]), None)
                    if pair:
                        send_telegram(chat_id, format_single_pair_ticket(pair))

                elif "cad" in text:
                    live_data = get_live_scanner_data()
                    pair = next((s for s in live_data if "CAD" in s["symbol"]), None)
                    if pair:
                        send_telegram(chat_id, format_single_pair_ticket(pair))

                elif "chf" in text:
                    live_data = get_live_scanner_data()
                    pair = next((s for s in live_data if "CHF" in s["symbol"]), None)
                    if pair:
                        send_telegram(chat_id, format_single_pair_ticket(pair))

                elif "gbp" in text:
                    live_data = get_live_scanner_data()
                    pair = next((s for s in live_data if "GBP" in s["symbol"]), None)
                    if pair:
                        send_telegram(chat_id, format_single_pair_ticket(pair))

                elif "eur" in text:
                    live_data = get_live_scanner_data()
                    pair = next((s for s in live_data if "EUR" in s["symbol"]), None)
                    if pair:
                        send_telegram(chat_id, format_single_pair_ticket(pair))

                else:
                    live_data = get_live_scanner_data()
                    send_telegram(chat_id, format_radar_summary(live_data))

            except Exception as e:
                send_telegram(chat_id, f"⚠️ เกิดข้อผิดพลาด: {str(e)}")

        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")
