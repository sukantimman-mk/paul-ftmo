"""
Paul FTMO V4 - Zero-Cost Cloud & Local Telegram H4 Alert System
Works 24/5 on GitHub Actions Free Cloud (PC can be 100% turned off, $0 cost)
OR locally via paul_system_dashboard.html / command line.
Redesigned for 3-second human readability in plain Thai (Zero spam, zero pending-order confusion).
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
from forward_demo_ledger import (
    escape_html,
    format_pair_name,
    format_dir_thai,
    format_dir_short,
    format_bkk_time,
    format_price,
    format_stage_thai,
)

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
    with open(CONFIG_PATH, 'w', encoding='utf-8', newline='\n') as f:
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
        try:
            import re
            clean_plain = re.sub(r'<[^>]+>', '', text_html)
            fallback_payload = {
                'chat_id': chat_id,
                'text': clean_plain,
                'disable_web_page_preview': True
            }
            fb_encoded = urllib.parse.urlencode(fallback_payload).encode('utf-8')
            fb_req = urllib.request.Request(url, data=fb_encoded, headers={'User-Agent': 'PaulFTMOBot/4.0'})
            with urllib.request.urlopen(fb_req, timeout=20) as resp:
                res = json.loads(resp.read().decode('utf-8'))
                return {'ok': bool(res.get('ok')), 'response': res}
        except Exception:
            pass
        return {'ok': False, 'error': str(e)}


def sync_latest_cftc_cot_if_needed():
    """
    Fetches the latest weekly CFTC COT report from publicreporting.cftc.gov
    and merges/repairs any new weeks into cot_historical_2023_2026.json so Cloud runners stay fresh forever.
    """
    try:
        if not os.path.exists(COT_CACHE_PATH):
            return
        with open(COT_CACHE_PATH, 'r', encoding='utf-8') as f:
            cot_db = json.load(f)

        contracts = list(cot_db.keys())
        where_clause = "(" + " or ".join([f"contract_market_name='{c}'" for c in contracts]) + ")"
        params = {
            "$where": where_clause,
            "$select": (
                "report_date_as_yyyy_mm_dd,contract_market_name,"
                "noncomm_positions_long_all,noncomm_positions_short_all,"
                "comm_positions_long_all,comm_positions_short_all,"
                "nonrept_positions_long_all,nonrept_positions_short_all,"
                "change_in_noncomm_long_all,change_in_noncomm_short_all,"
                "change_in_comm_long_all,change_in_comm_short_all,"
                "open_interest_all"
            ),
            "$order": "report_date_as_yyyy_mm_dd DESC",
            "$limit": 1000
        }
        url = f"https://publicreporting.cftc.gov/resource/6dca-aqww.json?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw_rows = json.loads(resp.read().decode('utf-8'))

        updated = False
        for r in reversed(raw_rows):
            c_name = r.get('contract_market_name')
            if c_name not in cot_db:
                continue
            r_date = str(r.get('report_date_as_yyyy_mm_dd', ''))[:10]
            if not r_date:
                continue

            existing_map = {item['date']: item for item in cot_db[c_name]}
            existing_rec = existing_map.get(r_date)
            needs_repair = (
                existing_rec is not None and (
                    'nl' not in existing_rec or
                    'ns' not in existing_rec or
                    'c_net' not in existing_rec or
                    'oi' not in existing_rec or
                    'nr_net' not in existing_rec
                )
            )

            if existing_rec is None or needs_repair:
                l_pos = int(float(r.get('noncomm_positions_long_all', 0) or 0))
                s_pos = int(float(r.get('noncomm_positions_short_all', 0) or 0))
                c_l = int(float(r.get('comm_positions_long_all', 0) or 0))
                c_s = int(float(r.get('comm_positions_short_all', 0) or 0))
                nr_l = int(float(r.get('nonrept_positions_long_all', 0) or 0))
                nr_s = int(float(r.get('nonrept_positions_short_all', 0) or 0))
                chg_l = int(float(r.get('change_in_noncomm_long_all', 0) or 0))
                chg_s = int(float(r.get('change_in_noncomm_short_all', 0) or 0))
                chg_cl = int(float(r.get('change_in_comm_long_all', 0) or 0))
                chg_cs = int(float(r.get('change_in_comm_short_all', 0) or 0))
                oi = int(float(r.get('open_interest_all', 0) or 0))

                net = l_pos - s_pos
                c_net = c_l - c_s
                nr_net = nr_l - nr_s
                chg_net = chg_l - chg_s
                chg_c_net = chg_cl - chg_cs
                long_pct = round(l_pos / max(1, l_pos + s_pos) * 100.0, 1)

                prior_rows = [x for x in cot_db[c_name] if x['date'] < r_date]
                hist_nets = [x['net'] for x in prior_rows[-51:]] + [net]
                mn, mx = min(hist_nets), max(hist_nets)
                cot_idx = round((net - mn) / max(1, mx - mn) * 100.0, 1) if mx != mn else 50.0

                new_entry = {
                    'date': r_date,
                    'nl': l_pos,
                    'ns': s_pos,
                    'long': l_pos,
                    'short': s_pos,
                    'net': net,
                    'c_net': c_net,
                    'nr_net': nr_net,
                    'chg_l': chg_l,
                    'chg_s': chg_s,
                    'chg_net': chg_net,
                    'chg_c_net': chg_c_net,
                    'oi': oi,
                    'long_pct': long_pct,
                    'cot_idx': cot_idx
                }

                if existing_rec is not None:
                    existing_rec.update(new_entry)
                else:
                    cot_db[c_name].append(new_entry)
                cot_db[c_name].sort(key=lambda x: x['date'])
                updated = True

        if updated:
            with open(COT_CACHE_PATH, 'w', encoding='utf-8', newline='\n') as f:
                json.dump(cot_db, f, indent=2, ensure_ascii=False)
            print("[+] Synced & verified weekly CFTC COT records (52W index + full schema) into cache.")
    except Exception as e:
        print(f"[!] Note: CFTC live sync skipped ({e}), using existing cache.")


def format_urgent_pair_alert(s, event_type, dashboard_url=''):
    """Formats a clear single-pair card in plain Thai (kept for backward compatibility & direct lookups)."""
    sym = s['symbol']
    pair_lbl = format_pair_name(sym)
    tk = s['planned_ticket']
    ot = s.get('active_open_trade')
    bkk_str = format_bkk_time()
    dir_full = format_dir_thai(s['planned_dir'])
    break_word = "ปิดสูงกว่า" if s['planned_dir'] == 'BUY' else "ปิดต่ำกว่า"

    if event_type in ('ENTRY_NOW', 'EXECUTE_NOW'):
        header = f"🟢🚀 <b>[เข้าไม้ใหม่แล้ว!] {pair_lbl} — ฝั่ง {tk['dir']} ({tk['lots_100k']} Lots)</b>"
        action = "✅ <b>บอทดำเนินการเข้าไม้ให้อัตโนมัติแล้ว</b> (เปิดแอป cTrader เช็คดูได้เลยครับ)"
    elif ot or event_type.startswith('ACTIVE_'):
        header = f"🔥 <b>[กำลังถือไม้อยู่] {pair_lbl}</b>"
        action = "✅ <b>ไม่ต้องกดอะไรเพิ่มครับ</b> — บอทเฝ้าแบ่งปิด TP และตัด SL ให้เองอัตโนมัติ"
    elif event_type in ('SETUP_ARMED', 'READY_WAIT_BOS'):
        header = f"👀 <b>[เฝ้าระวังใกล้จุดเข้า — ยังไม่ออกไม้!] {pair_lbl}</b>"
        action = (
            f"✋ <b>ไม่ต้องตั้งไม้ Pending ล่วงหน้าครับ!</b> — รอแท่ง 4 ชม. {break_word} "
            f"<code>{format_price(tk['entry'], sym)}</code> แล้วบอทจะกดเข้าไม้ให้เองอัตโนมัติ"
        )
    else:
        header = f"💤 <b>[พักตัวห่างจุดเข้า] {pair_lbl}</b>"
        action = "✅ <b>ไม่ต้องทำอะไรครับ</b> — ราคายังไม่เข้าโซนย่อตัว รอบอทแจ้งเตือนเมื่อใกล้จุดเข้า"

    lines = [
        header,
        f"🕒 <code>{bkk_str} (เวลาไทย)</code>",
        "━━━━━━━━━━━━━━━━━━━━",
        "👉 <b>สิ่งที่คุณต้องทำ:</b>",
        action,
        "━━━━━━━━━━━━━━━━━━━━",
        f"• คู่เงิน: <b>{pair_lbl}</b> | ราคาตอนนี้: <code>{format_price(s['latest_price'], sym)}</code>",
        f"• ฝั่งที่เล็ง: <b>{dir_full}</b> | ขนาดแผน: <code>{tk['lots_100k']} Lots</code>",
        f"• จุดเบรกที่รอ: <code>{format_price(tk['entry'], sym)}</code>",
        f"• 🛑 SL แผน: <code>{format_price(tk['sl'], sym)}</code> | 💰 TP1: <code>{format_price(tk['tp1'], sym)}</code> | 🏆 TP2: <code>{format_price(tk['tp2'], sym)}</code>",
    ]
    if dashboard_url:
        lines.append(f"\n🌐 <a href=\"{dashboard_url}\">เปิดดูกราฟแท่งเทียน 4 ชม. สดบนมือถือ</a>")
    return "\n".join(lines)


def format_h4_radar_summary(live_states, is_test=False, dashboard_url='', ledger=None, prev_state=None, new_entry_syms=None):
    """
    Formats an ultra-clean, 3-second human-readable H4 status summary for Telegram.
    Clearly separates:
      1) What the user needs to do right now (Top Action Box)
      2) Open Trades currently running
      3) Watchlist pairs near breakout (explicitly stating DO NOT place pending orders)
      4) Cancelled watchlist pairs (explicitly stating no order was opened, nothing to cancel)
      5) Resting pairs far from entry (1 compact line)
      6) FTMO $100k Portfolio & cTrader connection status
    """
    bkk_str = format_bkk_time()
    if ledger is None:
        ledger = forward_demo_ledger.load_ledger()
    if prev_state is None:
        prev_state = {}
    new_entry_set = set(new_entry_syms or [])

    open_trades = ledger.get('open_trades', [])
    open_syms = {t['symbol'] for t in open_trades}

    entry_now_unopened = []
    armed_pairs = []
    cancelled_watch_pairs = []
    resting_pairs = []

    for s in live_states:
        sym = s['symbol']
        if sym in open_syms:
            continue
        sig = s['overall_signal']
        old_sig = prev_state.get(sym, {}).get('pair_key', '').split('|')[0]

        if sig in ('ENTRY_NOW', 'EXECUTE_NOW'):
            entry_now_unopened.append(s)
        elif sig in ('SETUP_ARMED', 'READY_WAIT_BOS'):
            armed_pairs.append(s)
        else:
            if old_sig in ('SETUP_ARMED', 'READY_WAIT_BOS'):
                cancelled_watch_pairs.append(s)
            else:
                resting_pairs.append(s)

    title = (
        "📡 <b>สรุปสถานะพอร์ต & สัญญาณ (ทดสอบข้อความรูปแบบใหม่)</b>"
        if is_test else
        "📡 <b>สรุปสถานะพอร์ต & สัญญาณ (รอบปิดแท่ง 4 ชม.)</b>"
    )

    if new_entry_set:
        joined_new = ", ".join(format_pair_name(sym, short=True) for sym in new_entry_set)
        action_box = (
            f"🚀 <b>รอบนี้มี \"เข้าไม้ใหม่\" แล้ว ({joined_new})</b>\n"
            "บอทส่งคำสั่งเข้าพอร์ตให้แล้ว — ดูรายละเอียดราคาเข้า / SL / TP ในข้อความใบออเดอร์ด้านบนได้เลยครับ"
        )
    elif entry_now_unopened:
        joined_en = ", ".join(format_pair_name(s['symbol'], short=True) for s in entry_now_unopened)
        action_box = f"🟢 <b>พบสัญญาณเข้าไม้ ({joined_en})</b> — บอทกำลังดำเนินการเข้าออเดอร์ให้อัตโนมัติครับ"
    elif open_trades:
        action_box = (
            f"✅ <b>ไม่ต้องกดอะไรครับ (ถือไม้รันกำไรต่อ)</b>\n"
            f"ตอนนี้ถืออยู่ <b>{len(open_trades)} ไม้</b> บอทเฝ้าแบ่งปิด TP1 และตัด SL บน cTrader ให้เองอัตโนมัติ"
        )
    else:
        action_box = (
            "✅ <b>ไม่ต้องทำอะไรครับ</b> — รอบนี้ยังไม่มีสัญญาณเข้าไม้ใหม่\n"
            "<i>(ระบบนี้ไม่ตั้งไม้ Pending ล่วงหน้า — รอแท่ง 4 ชม. ปิดเบรกครบเกณฑ์ บอทจะกดเข้าไม้ให้เองอัตโนมัติ)</i>"
        )

    lines = [
        title,
        f"🕒 <code>{bkk_str} (เวลาไทย)</code>",
        "━━━━━━━━━━━━━━━━━━━━",
        "👉 <b>สิ่งที่คุณต้องทำตอนนี้:</b>",
        action_box,
        "━━━━━━━━━━━━━━━━━━━━",
    ]

    # Bucket 0 (only if --test caught an unopened ENTRY_NOW)
    if entry_now_unopened:
        lines.append("🟢 <b>สัญญาณเข้าไม้รอบนี้:</b>")
        for s in entry_now_unopened:
            sym = s['symbol']
            tk = s['planned_ticket']
            lines.append(
                f"• <b>{format_pair_name(sym)}</b> — ฝั่ง <b>{format_dir_short(s['planned_dir'])}</b> "
                f"(<code>{tk['lots_100k']} Lot</code>) ที่ราคา <code>{format_price(s['latest_price'], sym)}</code>"
            )
        lines.append("")

    # Bucket 1: Open Trades
    lines.append("🔥 <b>ไม้ที่กำลังถืออยู่ในพอร์ต:</b>")
    if open_trades:
        for t in open_trades:
            sym = t['symbol']
            pair_lbl = format_pair_name(sym)
            dir_lbl = format_dir_short(t['dir'])
            fl_usd = t.get('floating_usd', 0.0)
            fl_r = t.get('floating_r', 0.0)
            fl_icon = "🟢" if fl_usd >= 0 else "🔴"
            stage_code = t.get('stage', 'OPEN')
            tp_info = (
                f"เป้า TP1 <code>{format_price(t['tp1'], sym)}</code> / TP2 <code>{format_price(t['tp2'], sym)}</code>"
                if stage_code == 'OPEN' else
                f"เป้า TP2 <code>{format_price(t['tp2'], sym)}</code> <i>(แบ่งปิดครึ่งแรกแล้ว)</i>"
            )
            lines.append(
                f"• <b>{pair_lbl}</b> ({dir_lbl} <code>{t.get('lots', 1.0)} Lot</code>) — {fl_icon} <b>{fl_usd:+,.2f} USD ({fl_r:+}R)</b>\n"
                f"   ↳ เข้าที่ <code>{format_price(t['entry'], sym)}</code> | SL <code>{format_price(t['current_sl'], sym)}</code> | {tp_info}"
            )
    else:
        lines.append("• ไม่มีออเดอร์ค้าง (พอร์ตว่าง 0 ไม้)")

    # Bucket 2: Watchlist (SETUP_ARMED)
    lines.append("")
    lines.append("👀 <b>คู่ที่กำลังเฝ้าระวังใกล้จุดเข้า (ห้ามตั้งไม้ล่วงหน้า):</b>")
    if armed_pairs:
        for s in armed_pairs:
            sym = s['symbol']
            tk = s['planned_ticket']
            pair_lbl = format_pair_name(sym)
            dir_lbl = format_dir_short(s['planned_dir'])
            break_word = "ปิดสูงกว่า" if s['planned_dir'] == 'BUY' else "ปิดต่ำกว่า"
            lines.append(
                f"• <b>{pair_lbl}</b> — เล็งฝั่ง <b>{dir_lbl}</b>\n"
                f"   ↳ ราคาตอนนี้ <code>{format_price(s['latest_price'], sym)}</code> | "
                f"รอแท่ง 4 ชม. {break_word} <code>{format_price(tk['entry'], sym)}</code> บอทจะเข้าไม้ให้เอง"
            )
    else:
        lines.append("• ไม่มีคู่ที่อยู่ในโซนเฝ้าระวังรอบนี้")

    # Bucket 3: Cancelled Watchlist (only shown when a previously watched pair dropped back)
    if cancelled_watch_pairs:
        lines.append("")
        lines.append("⚪ <b>คู่ที่ยกเลิกการเฝ้าระวังรอบนี้:</b>")
        for s in cancelled_watch_pairs:
            pair_lbl = format_pair_name(s['symbol'])
            lines.append(
                f"• <b>{pair_lbl}</b> — ยกเลิกเฝ้าระวังแล้ว "
                "<i>(ราคาไม่เบรกจุดเข้า — ก่อนหน้านี้ยังไม่ได้ออกไม้ จึงไม่ต้องกดยกเลิกอะไรครับ)</i>"
            )

    # Bucket 4: Resting pairs (WAIT_PULLBACK)
    if resting_pairs:
        lines.append("")
        resting_names = ", ".join(format_pair_name(s['symbol'], short=True) for s in resting_pairs)
        lines.append(f"💤 <b>คู่ที่ยังพักตัวห่างจุดเข้า (ไม่ต้องสนใจ):</b>\n• {resting_names}")

    # Footer: Portfolio & cTrader Live Status
    init_bal = ledger.get('initial_balance', 100000.0)
    equity = ledger.get('current_equity', 100000.0)
    tot_pnl = round(equity - init_bal, 2)
    tot_ret = round((tot_pnl / init_bal) * 100.0, 2) if init_bal > 0 else 0.0
    closed_cnt = len(ledger.get('closed_trades', []))

    ctrader_tag = ""
    try:
        import ftmo_fix_trader
        fcfg = ftmo_fix_trader.load_fix_config()
        if fcfg.get('password') and fcfg.get('account_id'):
            ctrader_tag = f" (cTrader <code>#{fcfg['account_id']}</code> 🟢)"
    except Exception:
        pass

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💼 <b>พอร์ต FTMO $100k</b>{ctrader_tag}")
    lines.append(f"• เงินพอร์ตสุทธิ: <code>${equity:,.2f}</code> (<b>{tot_ret:+.2f}% / {tot_pnl:+,.2f} USD</b>)")
    lines.append(f"• ถืออยู่: <code>{len(open_trades)} ไม้</code> | ปิดจบแล้ว: <code>{closed_cnt} ไม้</code>")

    if dashboard_url:
        lines.append(f"🌐 <a href=\"{dashboard_url}\">เปิดดูกราฟแท่งเทียน 4 ชม. สดบนมือถือ</a>")

    return "\n".join(lines)


def run_alert_scan(send_summary=True, is_test=False, force=False):
    bot_token, chat_id, dashboard_url = load_telegram_credentials()
    sent_messages = []
    errors = []

    # 1. Load previous alert state first (for watchlist cancellation detection & deduplication)
    prev_state = {}
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, 'r', encoding='utf-8') as f:
                prev_state = json.load(f)
        except Exception:
            prev_state = {}

    # 2. Sync latest CFTC COT & run full live suite
    sync_latest_cftc_cot_if_needed()
    suite_res = paul_engine.build_full_suite()
    live_states = suite_res['live_states']

    # 3. Side-effect-free path when --test is used
    if is_test:
        ledger = forward_demo_ledger.load_ledger()
        summary_msg = format_h4_radar_summary(
            live_states,
            is_test=True,
            dashboard_url=dashboard_url,
            ledger=ledger,
            prev_state=prev_state,
            new_entry_syms=[]
        )
        if bot_token and chat_id:
            res = send_telegram_message(bot_token, chat_id, summary_msg)
            if res.get('ok'):
                sent_messages.append("H4_TEST_SUMMARY")
            else:
                errors.append(res.get('error', 'Unknown error'))
        return {
            'ok': len(errors) == 0 and bool(bot_token and chat_id),
            'configured': bool(bot_token and chat_id),
            'sent_messages': sent_messages,
            'errors': errors,
            'generated_at': suite_res['generated_at'],
            'live_states': live_states
        }

    # 4. Normal H4 Scan: Update Forward Demo Ledger & Execute Live cTrader Orders Atomically
    ledger = forward_demo_ledger.load_ledger()
    demo_events = []
    new_entry_syms = []
    try:
        ledger, demo_events = forward_demo_ledger.update_forward_demo_ledger(
            live_states,
            execute_live_fix=True,
            dry_run=False
        )
        for dev in demo_events:
            if dev.get('type') == 'TRADE_OPENED' and dev.get('symbol'):
                new_entry_syms.append(dev['symbol'])
            if bot_token and chat_id:
                res = send_telegram_message(bot_token, chat_id, dev['message'])
                if res.get('ok'):
                    sent_messages.append(f"TRADE_{dev['type']}:{dev.get('symbol', '')}")
                else:
                    errors.append(res.get('error', 'Unknown error'))
    except Exception as e:
        errors.append(f"Demo Ledger Error: {str(e)}")

    # 5. Send 1 Unified H4 Status Summary Card (deduplicated per H4 slot & paused when weekend market is frozen)
    now_utc = datetime.now(timezone.utc)
    h4_slot_key = f"{now_utc.strftime('%Y-%m-%d')}_{(now_utc.hour // 4) * 4:02d}UTC"
    max_bar_utc = max((s['last_bar_utc'] for s in live_states), default='')
    is_weekend_frozen = (
        now_utc.weekday() in (5, 6) and
        bool(max_bar_utc) and
        max_bar_utc == prev_state.get('_last_market_bar_utc', '')
    )

    should_send_summary = send_summary and (
        force or
        bool(demo_events) or
        (h4_slot_key != prev_state.get('_last_summary_slot', '') and not is_weekend_frozen)
    )

    if should_send_summary:
        summary_msg = format_h4_radar_summary(
            live_states,
            is_test=False,
            dashboard_url=dashboard_url,
            ledger=ledger,
            prev_state=prev_state,
            new_entry_syms=new_entry_syms
        )
        if bot_token and chat_id:
            res = send_telegram_message(bot_token, chat_id, summary_msg)
            if res.get('ok'):
                sent_messages.append("H4_STATUS_SUMMARY")
            else:
                errors.append(res.get('error', 'Unknown error'))

    # 6. Persist updated pair states for next H4 scan's transition tracking
    open_trades_by_sym = {t['symbol']: t for t in ledger.get('open_trades', [])}
    new_state = {
        '_last_summary_slot': h4_slot_key if should_send_summary else prev_state.get('_last_summary_slot', ''),
        '_last_market_bar_utc': max_bar_utc
    }
    for s in live_states:
        sym = s['symbol']
        tr_open = open_trades_by_sym.get(sym)
        eff_sig = 'ACTIVE_OPEN' if tr_open else s['overall_signal']
        ot_stage = tr_open.get('stage', 'OPEN') if tr_open else 'NONE'
        ot_etime = tr_open.get('entry_time', '') if tr_open else ''
        new_state[sym] = {
            'pair_key': f"{eff_sig}|{s['last_bar_utc']}",
            'stage_key': f"{ot_stage}|{ot_etime}"
        }

    with open(STATE_PATH, 'w', encoding='utf-8', newline='\n') as f:
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
    parser.add_argument('--test', action='store_true', help='Send an immediate test status summary to Telegram without modifying state')
    parser.add_argument('--force', action='store_true', help='Force send H4 status summary even within same H4 slot')
    parser.add_argument('--quiet-summary', action='store_true', help='Only send trade execution/management alerts, skip H4 status summary')
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
