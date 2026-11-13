"""
Paul FTMO V4 - Interactive Telegram Bot Listener (Real-Time Command Service)
Listens for user commands in Telegram:
  - 📜 "ดูประวัติออเดอร์" / "/history" / "ประวัติ" / "ขอดูประวัติ" -> Displays recent order history & closed trades
  - 📡 "สรุปสถานะตอนนี้" / "/status" / "สรุป" -> Displays H4 clean radar summary
  - 💼 "ดูพอร์ต ($100k)" / "/portfolio" / "พอร์ต" -> Displays current equity & balance
  - 🔄 "สั่งสแกนกราฟสด" / "/scan" -> Triggers immediate live scan
  - 🥇 "XAUUSD (ทองคำ)" -> Shows gold setup & active status
"""

import os
import sys
import time
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta

if sys.stdout and getattr(sys.stdout, 'encoding', None) != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import telegram_notifier
import forward_demo_ledger
from forward_demo_ledger import format_pair_name, format_dir_short, format_bkk_time, format_price

CONFIG_PATH = os.path.join(BASE_DIR, 'telegram_config.json')
CSV_PATH = os.path.join(BASE_DIR, 'paul_pro_trades.csv')
SCANNER_PATH = os.path.join(BASE_DIR, 'forward_live_scanner.json')

KEYBOARD_MARKUP = {
    "keyboard": [
        [{"text": "📜 ดูประวัติออเดอร์"}, {"text": "📡 สรุปสถานะตอนนี้"}],
        [{"text": "💼 ดูพอร์ต ($100k)"}, {"text": "🔄 สั่งสแกนกราฟสด"}],
        [{"text": "🥇 XAUUSD (ทองคำ)"}, {"text": "🇪🇺 EURUSD"}, {"text": "🇬🇧 GBPUSD"}],
        [{"text": "🇯🇵 USDJPY"}, {"text": "🇨🇦 USDCAD"}, {"text": "🇨🇭 USDCHF"}]
    ],
    "resize_keyboard": True
}


def send_tg_reply(bot_token, chat_id, text_html):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text_html,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": KEYBOARD_MARKUP
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"Error sending reply: {e}")
        return None


def build_trade_history_report(limit=5):
    """Builds clean, easy-to-read order history in Thai."""
    bkk_str = format_bkk_time()
    ledger = forward_demo_ledger.load_ledger()
    open_trades = ledger.get('open_trades', [])
    
    # Read trades from CSV
    trades_data = []
    if os.path.exists(CSV_PATH):
        try:
            import pandas as pd
            df = pd.read_csv(CSV_PATH)
            if not df.empty:
                trades_data = df.to_dict('records')
        except Exception:
            pass

    lines = [
        f"📜 <b>ประวัติออเดอร์ล่าสุด (Paul FTMO Pro V4)</b>",
        f"🕒 <code>{bkk_str}</code>",
        "━━━━━━━━━━━━━━━━━━",
    ]

    # 1. Active Open Trades
    if open_trades:
        lines.append(f"🔥 <b>ไม้ที่กำลังถืออยู่ ({len(open_trades)} ไม้):</b>")
        for t in open_trades:
            sym = t['symbol']
            pair_lbl = format_pair_name(sym, short=True)
            dir_lbl = format_dir_short(t['dir'])
            fl_usd = t.get('floating_usd', 0.0)
            fl_r = t.get('floating_r', 0.0)
            fl_icon = "🟢" if fl_usd >= 0 else "🔴"
            stage_code = t.get('stage', 'OPEN')
            lock_txt = " <i>(บังทุนแล้ว)</i>" if stage_code != 'OPEN' else ""
            lines.append(
                f"• <b>{pair_lbl}</b> ({dir_lbl} <code>{t.get('lots', 1.0)}L</code>) @ <code>{format_price(t['entry'], sym)}</code>\n"
                f"   ↳ กำไรลอย: {fl_icon} <b>{fl_usd:+,.1f}$ ({fl_r:+.1f}R)</b> | SL <code>{format_price(t['current_sl'], sym)}</code>{lock_txt}"
            )
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━")
    else:
        lines.append("💼 <b>พอร์ตว่าง:</b> ไม่มีออเดอร์ค้างอยู่ในขณะนี้")
        lines.append("━━━━━━━━━━━━━━━━━━")

    # 2. Closed Trades
    if trades_data:
        closed_tail = trades_data[-limit:][::-1]
        lines.append(f"🏁 <b>ประวัติ {len(closed_tail)} ไม้ล่าสุดที่ปิดจบแล้ว:</b>\n")
        
        idx = 1
        for r in closed_tail:
            sym = str(r.get('symbol', ''))
            pair_lbl = format_pair_name(sym, short=True)
            dir_lbl = format_dir_short(str(r.get('dir', '')))
            pnl = float(r.get('pnl_usd', 0.0))
            pnl_icon = "🟢" if pnl >= 0 else "🔴"
            res = str(r.get('res', ''))
            res_thai = (
                "ชน TP เต็ม 🎉" if res == 'FULL_WIN' else
                "แบ่งปิด TP1 + ล็อกทุน" if res in ('TRAIL_WIN', 'PARTIAL_WIN') else
                "ชน SL ตามแผน"
            )
            r_val = float(r.get('r_net_after_fee', 0.0))
            
            lines.append(
                f"{idx}. <b>{pair_lbl}</b> ({dir_lbl}) — {pnl_icon} <b>{pnl:+,.2f}$ ({r_val:+.2f}R)</b>\n"
                f"   • เข้า: <code>{format_price(r.get('entry_price'), sym)}</code> ➔ ปิด: <code>{format_price(r.get('exit_price'), sym)}</code> ({res_thai})\n"
                f"   • เวลา: <code>{r.get('entry_time', '')}</code> ➔ <code>{r.get('exit_time', '')}</code>\n"
            )
            idx += 1
            
        lines.append("━━━━━━━━━━━━━━━━━━")
        total_cnt = len(trades_data)
        wins = [x for x in trades_data if x.get('res') in ('FULL_WIN', 'TRAIL_WIN', 'PARTIAL_WIN')]
        wr = (len(wins) / total_cnt) * 100 if total_cnt > 0 else 0.0
        tot_pnl = sum(float(x.get('pnl_usd', 0.0)) for x in trades_data)
        
        lines.append("📊 <b>สถิติรวมของระบบ:</b>")
        lines.append(f"• ทั้งหมด: <code>{total_cnt} ไม้</code> | Win Rate: <b>{wr:.1f}%</b>")
        lines.append(f"• กำไรสะสมสุทธิ: <b>{tot_pnl:+,.2f} USD</b>")

    return "\n".join(lines)


def handle_incoming_text(text, bot_token, chat_id):
    """Processes user text and routes to appropriate response."""
    text_clean = text.strip().lower()

    # 1. Order History
    if any(k in text_clean for k in ['ประวัติ', 'history', 'ขอดูประวัติ', 'ออเดอร์', 'orders', 'trades', 'ไม้', '/history', '/trades']):
        report = build_trade_history_report(5)
        send_tg_reply(bot_token, chat_id, report)
        return

    # 2. Current Status / Radar
    if any(k in text_clean for k in ['สถานะ', 'สรุป', 'status', 'radar', 'อัปเดต', 'update', '/status', '/radar']):
        live_states = []
        if os.path.exists(SCANNER_PATH):
            with open(SCANNER_PATH, 'r', encoding='utf-8') as f:
                live_states = json.load(f)
        summary = telegram_notifier.format_h4_radar_summary(live_states)
        send_tg_reply(bot_token, chat_id, summary)
        return

    # 3. Portfolio
    if any(k in text_clean for k in ['พอร์ต', 'portfolio', 'balance', 'equity', 'ยอดเงิน', '/portfolio']):
        ledger = forward_demo_ledger.load_ledger()
        init_bal = ledger.get('initial_balance', 100000.0)
        equity = ledger.get('current_equity', 100000.0)
        tot_pnl = round(equity - init_bal, 2)
        tot_ret = round((tot_pnl / init_bal) * 100.0, 2) if init_bal > 0 else 0.0
        open_tr = ledger.get('open_trades', [])
        
        msg = "\n".join([
            "💼 <b>สรุปพอร์ต FTMO $100k (Paul Pro V4)</b>",
            f"🕒 <code>{format_bkk_time()}</code>",
            "━━━━━━━━━━━━━━━━━━",
            f"• ยอดเงินในพอร์ต (Equity): <code>${equity:,.2f}</code>",
            f"• กำไรสุทธิสะสม: <b>{tot_ret:+.2f}% ({tot_pnl:+,.2f} USD)</b>",
            f"• กำลังถือครอง: <code>{len(open_tr)} ไม้</code>",
            "━━━━━━━━━━━━━━━━━━",
            "✅ บอทจัดการความเสี่ยงและเฝ้าตัดขาดทุนตามกฎ FTMO 100%"
        ])
        send_tg_reply(bot_token, chat_id, msg)
        return

    # 4. Trigger Scan
    if any(k in text_clean for k in ['สแกน', 'scan', '/scan', 'refresh']):
        send_tg_reply(bot_token, chat_id, "⏳ <b>กำลังทำการสแกนกราฟ H4 สดเดี๋ยวนี้...</b>\nกรุณารอสักครู่ บอทจะส่งผลสรุปมาให้ครับ")
        try:
            telegram_notifier.run_alert_scan(send_summary=True, force=True)
        except Exception as e:
            send_tg_reply(bot_token, chat_id, f"⚠️ การสแกนขัดข้อง: {e}")
        return

    # 5. Default Welcome / Help
    welcome = "\n".join([
        "🤖 <b>คำสั่งระบบ Paul FTMO Bot</b>",
        "━━━━━━━━━━━━━━━━━━",
        "คุณสามารถพิมพ์คำสั่งหรือกดปุ่มเมนูด้านล่างได้ทันทีครับ:",
        "• กด <b>📜 ดูประวัติออเดอร์</b> — เช็คประวัติไม้ที่ปิดล่าสุดและสถิติ",
        "• กด <b>📡 สรุปสถานะตอนนี้</b> — ดูสถานะรอบ H4 และไม้ที่กำลังถือ",
        "• กด <b>💼 ดูพอร์ต ($100k)</b> — เช็ค Equity และผลตอบแทนรวม",
        "• กด <b>🔄 สั่งสแกนกราฟสด</b> — สั่งให้บอทสแกนแท่ง 4 ชม. ทันที",
        "━━━━━━━━━━━━━━━━━━",
        "👇 <i>สามารถแตะปุ่มที่คีย์บอร์ดด้านล่างได้เลยครับ</i>"
    ])
    send_tg_reply(bot_token, chat_id, welcome)


def run_polling_service():
    """Runs long polling loop to receive Telegram commands."""
    bot_token, chat_id, _ = telegram_notifier.load_telegram_credentials()
    if not bot_token:
        print("[!] Error: No TELEGRAM_BOT_TOKEN found!")
        return

    print("=" * 60)
    print("🤖 PAUL FTMO TELEGRAM INTERACTIVE COMMAND SERVICE")
    print(f"[*] Target Chat ID: {chat_id}")
    print("[*] Listening for incoming commands (Press Ctrl+C to stop)...")
    print("=" * 60)

    # First delete any existing webhook to ensure getUpdates works
    try:
        del_url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook"
        urllib.request.urlopen(del_url, timeout=10)
    except Exception:
        pass

    offset = None
    while True:
        try:
            poll_url = f"https://api.telegram.org/bot{bot_token}/getUpdates?timeout=20"
            if offset:
                poll_url += f"&offset={offset}"
            
            req = urllib.request.Request(poll_url, headers={"User-Agent": "PaulBot/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                
            if data.get('ok') and data.get('result'):
                for update in data['result']:
                    offset = update['update_id'] + 1
                    msg = update.get('message', {})
                    text = msg.get('text', '')
                    from_user = msg.get('from', {}).get('first_name', 'Trader')
                    from_id = str(msg.get('chat', {}).get('id', ''))
                    
                    if text:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] From {from_user} ({from_id}): {text}")
                        # If chat_id is matched or no chat_id was restricted
                        handle_incoming_text(text, bot_token, from_id)

        except urllib.error.URLError as ue:
            time.sleep(3)
        except Exception as e:
            print(f"Polling loop error: {e}")
            time.sleep(3)


if __name__ == '__main__':
    run_polling_service()
