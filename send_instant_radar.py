import json
import urllib.request
import urllib.parse
from datetime import datetime

TOKEN = ""
CHAT_ID = ""

with open(r'D:\cot_dashboard\forward_live_scanner.json', 'r', encoding='utf-8') as f:
    live_states = json.load(f)

now_str = datetime.now().strftime('%Y-%m-%d %H:%M น.')
lines = [
    "🎉 <b>[ผูกบัญชีถาวรสำเร็จ 100%!] สวัสดีคุณ Superman (@my_paul_FTMO_bot)</b>",
    f"🕒 เวลาไทย: <code>{now_str}</code>",
    "✅ <b>ตั้งค่าครั้งเดียวจบ! ต่อจากนี้ระบบทำงานอัตโนมัติ ไม่ต้องกดเองอีกเลยครับ</b>",
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
        lines.append(
            f"   ⚡ <i>ถือออเดอร์ {ot['dir']} อยู่: เข้า <code>{ot['entry_price']}</code> | P&L <b>{ot['floating_r']:+}R (${ot['floating_usd']:+,.0f})</b> | ด่าน {ot['stage']} (SL <code>{ot['current_sl']}</code>)</i>"
        )

lines.append("━━━━━━━━━━━━━━━━━━━━")
lines.append("🤖 <i>บอทจำ Chat ID (1394691513) ของคุณถาวรแล้ว ระบบจะสแกนและส่งสัญญาณเข้าแชทนี้ให้อัตโนมัติทุกปิดแท่ง H4 ครับ!</i>")

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
payload = urllib.parse.urlencode({
    'chat_id': CHAT_ID,
    'text': "\n".join(lines),
    'parse_mode': 'HTML',
    'disable_web_page_preview': True
}).encode('utf-8')

req = urllib.request.Request(url, data=payload, headers={'User-Agent': 'PaulFTMOBot/4.0'})
with urllib.request.urlopen(req, timeout=15) as resp:
    res = json.loads(resp.read().decode('utf-8'))
    print("TELEGRAM_SEND_OK:", res.get('ok'))
