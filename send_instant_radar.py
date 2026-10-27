import os
import json
import urllib.request
import urllib.parse
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'telegram_config.json')

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

if not TOKEN or not CHAT_ID:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                TOKEN = cfg.get('bot_token', '')
                CHAT_ID = cfg.get('chat_id', '')
        except Exception as e:
            print("Config read error:", e)

if not TOKEN or not CHAT_ID:
    print("[ERROR] No Telegram Token or Chat ID found in environment or telegram_config.json")
    exit(1)

SCANNER_PATH = os.path.join(BASE_DIR, 'forward_live_scanner.json')
with open(SCANNER_PATH, 'r', encoding='utf-8') as f:
    live_states = json.load(f)

now_str = datetime.now().strftime('%Y-%m-%d %H:%M น.')
lines = [
    "🎉 <b>[ผูกบัญชีถาวรสำเร็จ 100%!] Paul FTMO Radar (@my_paul_FTMO_bot)</b>",
    f"🕒 เวลาไทย: <code>{now_str}</code>",
    "✅ <b>บอทกู้คืนความปลอดภัยและเชื่อมต่อระบบใหม่เรียบร้อยแล้วครับ</b>",
    "━━━━━━━━━━━━━━━━━━━━"
]

for s in live_states:
    sym = s['symbol']
    g = s['gates']
    tk = s['planned_ticket']
    ot = s.get('active_open_trade')

    if s['overall_signal'] == 'ENTRY_NOW':
        icon = "🟢🚨"
        status_txt = f"<b>สั่งเข้า {s['planned_dir']} ทันที!</b> @ <code>{s['latest_price']}</code> (SL <code>{tk['sl']}</code> | TP1 <code>{tk['tp1']}</code> | <code>{tk['lots_100k']} Lot</code>)"
    elif s['overall_signal'] == 'SETUP_ARMED':
        icon = "⏳⚡"
        status_txt = f"<b>ย่อแตะ EMA50 แล้ว!</b> รอเบรก {s['planned_dir']} @ <code>{tk['entry']}</code> (SL <code>{tk['sl']}</code> | <code>{tk['lots_100k']} Lot</code>)"
    else:
        icon = "🔵"
        status_txt = f"แผน <b>{s['planned_dir']}</b> | ราคา <code>{s['latest_price']}</code> | รอย่อแตะ EMA50 (<code>{s['ema50']}</code>) | จุดเบรก BOS <code>{tk['entry']}</code>"

    lights = f"[1:{'🟢' if g['g1_pass'] else '🔴'} 2:{'🟢' if g['g2_pass'] else '⏳'} 3:{'🟢' if g['g3_pass'] else '⏳'}]"
    lines.append(f"{icon} <b>{sym}</b> {lights}\n   ↳ {status_txt}")

    if ot:
        e_price = ot.get('entry', ot.get('entry_price', ''))
        lines.append(
            f"   ⚡ <i>ถือออเดอร์ {ot['dir']} อยู่: เข้า <code>{e_price}</code> | P&L <b>{ot['floating_r']:+}R (${ot['floating_usd']:+,.2f})</b> | ด่าน {ot['stage']} (SL <code>{ot['current_sl']}</code>)</i>"
        )

LEDGER_PATH = os.path.join(BASE_DIR, 'forward_demo_ledger.json')
if os.path.exists(LEDGER_PATH):
    try:
        with open(LEDGER_PATH, 'r', encoding='utf-8') as f:
            led = json.load(f)
        init_bal = led.get('initial_balance', 100000.0)
        bal = led.get('current_balance', 100000.0)
        equity = led.get('current_equity', 100000.0)
        fl = led.get('floating_pnl_usd', 0.0)
        realized_pnl = round(bal - init_bal, 2)
        realized_ret = round((realized_pnl / init_bal) * 100.0, 2) if init_bal > 0 else 0.0
        tot_pnl = round(equity - init_bal, 2)
        tot_ret = round((tot_pnl / init_bal) * 100.0, 2) if init_bal > 0 else 0.0
        open_cnt = len(led.get('open_trades', []))
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"💼 <b>สรุปพอร์ตจำลอง Forward Demo ($100,000):</b>")
        lines.append(f"• มูลค่าพอร์ตสุทธิ (Equity): <code>${equity:,.2f}</code> (<b>{tot_ret:+.2f}% / ${tot_pnl:+,.2f}</b>)")
        lines.append(f"• กำไรลอยตัว (Floating P&L): <b>{fl:+,.2f} USD</b> ({open_cnt} ไม้ถือสู้ราคาอยู่ในตลาด)")
        lines.append(f"• กำไรที่ปิดแล้ว (Realized): <b>{realized_pnl:+,.2f} USD ({realized_ret:+.2f}%)</b>")
    except Exception as e:
        pass

lines.append("━━━━━━━━━━━━━━━━━━━━")
lines.append(f"🤖 <i>เชื่อมต่อปลอดภัย Chat ID: <code>{CHAT_ID}</code> ระบบ Cloud รันอัตโนมัติ 24/5 แม้ปิดคอมครับ!</i>")

msg_text = "\n".join(lines)
payload = {
    "chat_id": CHAT_ID,
    "text": msg_text,
    "parse_mode": "HTML"
}

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
req = urllib.request.Request(
    url,
    data=urllib.parse.urlencode(payload).encode('utf-8'),
    headers={"User-Agent": "Paul-FTMO-Notifier"}
)

try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        if res.get('ok'):
            print(f"[OK] Telegram Instant Radar sent successfully to chat {CHAT_ID}!")
        else:
            print("[FAIL]", res)
except Exception as e:
    print("[ERROR]", e)
