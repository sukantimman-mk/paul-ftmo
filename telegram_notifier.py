"""
Paul FTMO V4 - Zero-Cost Cloud & Local Telegram H4 Alert System
Works 24/5 on GitHub Actions Free Cloud (PC can be 100% turned off, $0 cost)
OR locally via paul_system_dashboard.html / command line.
"""

import os
import sys
import json
import argparse
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

import paul_engine
import forward_demo_ledger

CONFIG_PATH = os.path.join(BASE_DIR, 'telegram_config.json')
STATE_PATH = os.path.join(BASE_DIR, 'telegram_alert_state.json')
COT_CACHE_PATH = os.path.join(BASE_DIR, 'cot_historical_2023_2026.json')


def load_telegram_credentials():
    """
    Loads Telegram Bot Token & Chat ID from:
    1) Environment Variables (GitHub Actions Secrets: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DASHBOARD_URL)
    2) Local file: D:\\cot_dashboard\\telegram_config.json
    """
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
    dashboard_url = os.environ.get('DASHBOARD_URL', '').strip()

    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                if not bot_token:
                    bot_token = str(cfg.get('bot_token', '')).strip()
                if not chat_id:
                    chat_id = str(cfg.get('chat_id', '')).strip()
                if not dashboard_url:
                    dashboard_url = str(cfg.get('dashboard_url', '')).strip()
        except Exception:
            pass

    return bot_token, chat_id, dashboard_url


def save_telegram_credentials(bot_token, chat_id, dashboard_url=''):
    cfg = {
        'bot_token': str(bot_token).strip(),
        'chat_id': str(chat_id).strip(),
        'dashboard_url': str(dashboard_url).strip(),
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    return cfg


def auto_detect_chat_id(bot_token):
    """
    Queries Telegram getUpdates API to automatically find the user's Chat ID
    after they click Start or send any message to their bot.
    """
    token = str(bot_token).strip()
    if not token:
        return {'ok': False, 'error': 'กรุณาใส่ Bot Token ก่อนครับ'}

    url = f"https://api.telegram.org/bot{token}/getUpdates"
    req = urllib.request.Request(url, headers={'User-Agent': 'PaulFTMOBot/4.0'})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        if not data.get('ok'):
            return {'ok': False, 'error': data.get('description', 'Invalid Bot Token')}
        results = data.get('result', [])
        for item in reversed(results):
            msg = item.get('message') or item.get('edited_message') or item.get('channel_post') or {}
            chat = msg.get('chat', {})
            if chat.get('id'):
                cid = str(chat['id'])
                title = chat.get('title') or chat.get('first_name') or chat.get('username') or 'Telegram User'
                return {'ok': True, 'chat_id': cid, 'chat_name': title}
        return {
            'ok': False,
            'error': 'ยังไม่พบข้อความในบอท — กรุณาเปิดแอป Telegram แล้วทักแชทบอทของคุณ (กด Start หรือพิมพ์ "สวัสดี") 1 ครั้ง แล้วกดปุ่มนี้อีกทีครับ!'
        }
    except Exception as e:
        return {'ok': False, 'error': f'เชื่อมต่อ Telegram ไม่สำเร็จ: {str(e)}'}


def send_telegram_message(bot_token, chat_id, text_html):
    """Sends an HTML-formatted message to Telegram."""
    if not bot_token or not chat_id:
        return {'ok': False, 'error': 'ยังไม่ได้ตั้งค่า TELEGRAM_BOT_TOKEN หรือ TELEGRAM_CHAT_ID'}

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text_html,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True
    }
    encoded = urllib.parse.urlencode(payload).encode('utf-8')
    req = urllib.request.Request(url, data=encoded, headers={'User-Agent': 'PaulFTMOBot/4.0'})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            res = json.loads(resp.read().decode('utf-8'))
            return {'ok': bool(res.get('ok')), 'response': res}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def sync_latest_cftc_cot_if_needed():
    """
    Fetches the latest weekly CFTC COT report from publicreporting.cftc.gov
    and merges any new weeks into cot_historical_2023_2026.json so Cloud runners stay fresh forever.
    """
    try:
        if not os.path.exists(COT_CACHE_PATH):
            return
        with open(COT_CACHE_PATH, 'r', encoding='utf-8') as f:
            cot_db = json.load(f)

        contracts = ['GOLD', 'JAPANESE YEN', 'CANADIAN DOLLAR', 'SWISS FRANC', 'BRITISH POUND', 'EURO FX', 'USD INDEX']
        where_clause = "(" + " or ".join([f"contract_market_name='{c}'" for c in contracts]) + ")"
        params = {
            "$where": where_clause,
            "$select": "report_date_as_yyyy_mm_dd,contract_market_name,noncomm_positions_long_all,noncomm_positions_short_all,change_in_noncomm_long_all,change_in_noncomm_short_all",
            "$order": "report_date_as_yyyy_mm_dd DESC",
            "$limit": 60
        }
        url = f"https://publicreporting.cftc.gov/resource/6dca-aqww.json?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw_rows = json.loads(resp.read().decode('utf-8'))

        updated = False
        for r in raw_rows:
            c_name = r.get('contract_market_name')
            if c_name not in cot_db:
                continue
            r_date = str(r.get('report_date_as_yyyy_mm_dd', ''))[:10]
            if not r_date:
                continue
            existing_dates = {item['date'] for item in cot_db[c_name]}
            if r_date not in existing_dates:
                l_pos = int(float(r.get('noncomm_positions_long_all', 0) or 0))
                s_pos = int(float(r.get('noncomm_positions_short_all', 0) or 0))
                chg_l = int(float(r.get('change_in_noncomm_long_all', 0) or 0))
                chg_s = int(float(r.get('change_in_noncomm_short_all', 0) or 0))
                net = l_pos - s_pos
                chg_net = chg_l - chg_s
                long_pct = round(l_pos / max(1, l_pos + s_pos) * 100.0, 1)

                hist_nets = [x['net'] for x in cot_db[c_name][-25:]] + [net]
                mn, mx = min(hist_nets), max(hist_nets)
                cot_idx = round((net - mn) / max(1, mx - mn) * 100.0, 1)

                cot_db[c_name].append({
                    'date': r_date,
                    'long': l_pos,
                    'short': s_pos,
                    'net': net,
                    'chg_net': chg_net,
                    'long_pct': long_pct,
                    'cot_idx': cot_idx
                })
                cot_db[c_name].sort(key=lambda x: x['date'])
                updated = True

        if updated:
            with open(COT_CACHE_PATH, 'w', encoding='utf-8') as f:
                json.dump(cot_db, f, indent=2, ensure_ascii=False)
            print("[+] Synced new weekly CFTC COT records into cache.")
    except Exception as e:
        print(f"[!] Note: CFTC live sync skipped ({e}), using existing cache.")


def format_urgent_pair_alert(s, event_type, dashboard_url=''):
    """Formats a dedicated rich alert message for a single pair when triggered or armed."""
    sym = s['symbol']
    name = s['name']
    tk = s['planned_ticket']
    gates = s['gates']
    ot = s.get('active_open_trade')
    bkk_now = (datetime.now(timezone.utc) + timedelta(hours=7)).strftime('%Y-%m-%d %H:%M น. (เวลาไทย)')

    if event_type == 'ENTRY_NOW':
        header = f"🟢🚨 <b>[เข้าออเดอร์ทันที!] {sym} ({name}) — ด่าน 1-2-3 ผ่านครบ 100%!</b>"
    elif event_type == 'SETUP_ARMED':
        header = f"⏳⚡ <b>[เตรียมพร้อมตั้งไม้!] {sym} ({name}) — ราคาย่อแตะเส้นฟ้า EMA50 แล้ว!</b>"
    elif event_type.startswith('ACTIVE_STAGE_'):
        header = f"🛡️💰 <b>[อัปเดตไม้ที่ถืออยู่!] {sym} ({name}) — ราคาวิ่งชนเป้าย่อยแล้ว!</b>"
    else:
        header = f"📡 <b>อัปเดตสัญญาณ {sym} ({name})</b>"

    lines = [
        header,
        f"🕒 เวลาสแกน: <code>{bkk_now}</code>",
        f"🕯️ แท่ง H4 ล่าสุด: <code>{s['last_bar_utc']}</code>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"💵 <b>ราคาปัจจุบัน:</b> <code>{s['latest_price']}</code> | <b>แผนฝั่ง:</b> <b>{s['planned_dir']}</b>",
        f"📊 <b>ตรวจสอบกฎ 1-2-3-4:</b>",
        f"  {'🟢' if gates['g1_pass'] else '🔴'} <b>ด่าน 1 (Trend+COT):</b> {gates['g1_text']}",
        f"  {'🟢' if gates['g2_pass'] else '🔴'} <b>ด่าน 2 (Pullback EMA50):</b> {gates['g2_text']}",
        f"  {'🟢' if gates['g3_pass'] else '⏳'} <b>ด่าน 3 (3-Bar BOS+RSI):</b> {gates['g3_text']}",
        "━━━━━━━━━━━━━━━━━━━━",
    ]

    if ot and event_type.startswith('ACTIVE_STAGE_'):
        e_price = ot.get('entry', ot.get('entry_price', ''))
        tp2_price = ot.get('tp', ot.get('tp2_price', ''))
        lines.extend([
            f"⚡ <b>สถานะไม้ที่ถืออยู่ ({ot.get('dir', '')}):</b>",
            f"• ราคาเข้า (Entry): <code>{e_price}</code>",
            f"• กำไรลอยตัวปัจจุบัน: <b>{ot.get('floating_r', 0):+}R (${ot.get('floating_usd', 0):+,.2f})</b>",
            f"• <b>สิ่งที่ต้องทำทันที (ด่าน 4):</b> สถานะเข้าสู่ <b>{ot.get('stage', '')}</b> -> ตั้ง SL ปัจจุบันไว้ที่ <code>{ot.get('current_sl', '')}</code> และ TP2 ที่ <code>{tp2_price}</code>",
        ])
    else:
        lines.extend([
            f"🎯 <b>ใบสั่งเทรด (พอร์ต $100,000 | ความเสี่ยง 0.75% = $750):</b>",
            f"• <b>ฝั่ง (Direction):</b> <b>{tk['dir']}</b>",
            f"• <b>ขนาด Lot (FTMO $100k):</b> <code>{tk['lots_100k']} Lots</code>",
            f"• <b>ราคาเข้า (Entry / 3-Bar BOS):</b> <code>{tk['entry']}</code>",
            f"• <b>Stop Loss (-1.0R / {tk['atr_mult']}x ATR):</b> <code>{tk['sl']}</code>",
            f"• <b>TP 1 (+1.5R แบ่งปิด 50%):</b> <code>{tk['tp1']}</code> <i>(แล้วเลื่อน SL มาที่ {tk['lock1']})</i>",
            f"• <b>Stage 2 (+2.5R):</b> <code>{tk['stage2']}</code> <i>(เลื่อน SL ล็อกกำไรที่ {tk['lock2']})</i>",
            f"• <b>TP 2 (+3.5R ปิดที่เหลือ):</b> <code>{tk['tp2']}</code>",
        ])

    if dashboard_url:
        lines.append(f"\n🌐 <a href=\"{dashboard_url}\">คลิกเปิดดูกราฟแท่งเทียน H4 สดบนมือถือ</a>")

    return "\n".join(lines)


def format_h4_radar_summary(live_states, is_test=False, dashboard_url=''):
    """Formats a compact 6-pair H4 radar summary table for Telegram."""
    bkk_now = (datetime.now(timezone.utc) + timedelta(hours=7)).strftime('%Y-%m-%d %H:%M น.')
    title = "🧪 <b>[ทดสอบระบบสำเร็จ!] เรดาร์สแกนสด 6 คู่เงิน (Paul Pro V4)</b>" if is_test else "📡 <b>สรุปเรดาร์ H4 สดทั้ง 6 คู่เงิน (Paul Pro V4 | 1-2-3-4)</b>"

    lines = [
        title,
        f"🕒 เวลาไทย: <code>{bkk_now}</code>",
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
            status_txt = f"แผน {s['planned_dir']} | ราคา <code>{s['latest_price']}</code> | รอย่อแตะ EMA50 (<code>{s['ema50']}</code>)"

        g_lights = f"[1:{'🟢' if g['g1_pass'] else '🔴'} 2:{'🟢' if g['g2_pass'] else '⏳'} 3:{'🟢' if g['g3_pass'] else '⏳'}]"
        lines.append(f"{icon} <b>{sym}</b> {g_lights}\n   ↳ {status_txt}")

        if ot:
            e_price = ot.get('entry', ot.get('entry_price', ''))
            lines.append(
                f"   ⚡ <i>มีออเดอร์ {ot.get('dir', '')} ค้างอยู่: เข้า <code>{e_price}</code> | P&L <b>{ot.get('floating_r', 0):+}R (${ot.get('floating_usd', 0):+,.0f})</b> | ด่าน {ot.get('stage', '')} (SL <code>{ot.get('current_sl', '')}</code>)</i>"
            )

    try:
        ledger = forward_demo_ledger.load_ledger()
        init_bal = ledger.get('initial_balance', 100000.0)
        bal = ledger.get('current_balance', 100000.0)
        equity = ledger.get('current_equity', 100000.0)
        floating = ledger.get('floating_pnl_usd', 0.0)
        realized_pnl = round(bal - init_bal, 2)
        realized_ret = round((realized_pnl / init_bal) * 100.0, 2) if init_bal > 0 else 0.0
        tot_pnl = round(equity - init_bal, 2)
        tot_ret = round((tot_pnl / init_bal) * 100.0, 2) if init_bal > 0 else 0.0
        open_trades = ledger.get('open_trades', [])
        open_cnt = len(open_trades)
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"💼 <b>พอร์ตจำลอง Forward Demo ($100k):</b>")
        lines.append(f"• มูลค่าพอร์ตสุทธิ (Equity): <code>${equity:,.2f}</code> (<b>{tot_ret:+.2f}% / ${tot_pnl:+,.2f}</b>)")
        lines.append(f"• กำไรลอยตัว (Floating P&L): <b>{floating:+,.2f} USD</b> ({open_cnt} ไม้กำลังวิ่งในตลาด)")
        lines.append(f"• กำไรที่ปิดจบแล้ว (Realized): <b>{realized_pnl:+,.2f} USD ({realized_ret:+.2f}%)</b>")
    except Exception:
        pass

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("💡 <i>ระบบรันบน Cloud อัตโนมัติทุกปิดแท่ง H4 (ปิดคอมได้ 100% ฟรี 0 บาท)</i>")
    if dashboard_url:
        lines.append(f"🌐 <a href=\"{dashboard_url}\">เปิดหน้ากราฟแท่งเทียน H4 ปัจจุบันสด</a>")

    return "\n".join(lines)


def run_alert_scan(send_summary=True, is_test=False, force=False):
    bot_token, chat_id, dashboard_url = load_telegram_credentials()
    sent_messages = []
    errors = []
    new_state = {}

    # 1. Sync latest CFTC COT & run full live suite
    sync_latest_cftc_cot_if_needed()
    suite_res = paul_engine.build_full_suite()
    live_states = suite_res['live_states']

    # 1.1 Update Forward Demo Ledger ($100k Autonomous Cloud Demo)
    try:
        ledger, demo_events = forward_demo_ledger.update_forward_demo_ledger(live_states)
        for dev in demo_events:
            if bot_token and chat_id:
                send_telegram_message(bot_token, chat_id, dev['message'])
                sent_messages.append(f"DEMO_{dev['type']}")
    except Exception as e:
        errors.append(f"Demo Ledger Error: {str(e)}")

    # 2. Load previous alert state to prevent duplicate spam
    prev_state = {}
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, 'r', encoding='utf-8') as f:
                prev_state = json.load(f)
        except Exception:
            prev_state = {}

    for s in live_states:
        sym = s['symbol']
        sig = s['overall_signal']
        bar_utc = s['last_bar_utc']
        ot = s.get('active_open_trade')
        ot_stage = ot['stage'] if ot else 'NONE'

        pair_key = f"{sig}|{bar_utc}"
        stage_key = f"{ot_stage}|{ot['entry_time'] if ot else ''}"
        new_state[sym] = {'pair_key': pair_key, 'stage_key': stage_key}

        old_pair_key = prev_state.get(sym, {}).get('pair_key', '')
        old_stage_key = prev_state.get(sym, {}).get('stage_key', '')

        # Trigger 1: ENTRY_NOW or SETUP_ARMED on a new H4 bar
        if sig in ('ENTRY_NOW', 'SETUP_ARMED') and (force or pair_key != old_pair_key):
            msg = format_urgent_pair_alert(s, sig, dashboard_url)
            if bot_token and chat_id:
                res = send_telegram_message(bot_token, chat_id, msg)
                if res.get('ok'):
                    sent_messages.append(f"{sym}:{sig}")
                else:
                    errors.append(res.get('error', 'Unknown error'))

        # Trigger 2: Active open trade stage upgraded (e.g. hit TP1 -> STAGE_1 or Stage 2 -> STAGE_2)
        if ot and ot_stage in ('STAGE_1', 'STAGE_2') and (force or stage_key != old_stage_key):
            msg = format_urgent_pair_alert(s, f"ACTIVE_{ot_stage}", dashboard_url)
            if bot_token and chat_id:
                res = send_telegram_message(bot_token, chat_id, msg)
                if res.get('ok'):
                    sent_messages.append(f"{sym}:ACTIVE_{ot_stage}")
                else:
                    errors.append(res.get('error', 'Unknown error'))

    # Trigger 3: H4 Radar Summary (always sent on test, or when send_summary=True)
    if send_summary or is_test:
        summary_msg = format_h4_radar_summary(live_states, is_test=is_test, dashboard_url=dashboard_url)
        if bot_token and chat_id:
            res = send_telegram_message(bot_token, chat_id, summary_msg)
            if res.get('ok'):
                sent_messages.append("H4_RADAR_SUMMARY")
            else:
                errors.append(res.get('error', 'Unknown error'))

    with open(STATE_PATH, 'w', encoding='utf-8') as f:
        json.dump(new_state, f, indent=2, ensure_ascii=False)

    return {
        'ok': len(errors) == 0 and bool(bot_token and chat_id),
        'configured': bool(bot_token and chat_id),
        'sent_messages': sent_messages,
        'errors': errors,
        'generated_at': suite_res['generated_at'],
        'live_states': live_states
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Paul Pro V4 Telegram H4 Scanner & Notifier')
    parser.add_argument('--test', action='store_true', help='Send an immediate test radar summary to Telegram')
    parser.add_argument('--force', action='store_true', help='Force send all active/armed alerts regardless of cache')
    parser.add_argument('--quiet-summary', action='store_true', help='Only send urgent ENTRY/ARMED/STAGE alerts, skip routine summary')
    args = parser.parse_args()

    result = run_alert_scan(
        send_summary=not args.quiet_summary,
        is_test=args.test,
        force=args.force
    )
    try:
        print(f"[Telegram Notifier] Configured={result['configured']} | Sent={result['sent_messages']} | Errors={result['errors']}")
    except Exception:
        pass
