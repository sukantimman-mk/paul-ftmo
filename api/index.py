from http.server import BaseHTTPRequestHandler
import json
import urllib.request
import os
import datetime

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
GITHUB_USER = "sukantimman-mk"
REPO_NAME = "paul-ftmo"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

PAIR_DISPLAY_MAP = {
    "GC=F": ("🥇 XAUUSD (ทองคำ)", "🥇 XAUUSD"),
    "EURUSD=X": ("🇪🇺 EURUSD", "🇪🇺 EURUSD"),
    "GBPUSD=X": ("🇬🇧 GBPUSD", "🇬🇧 GBPUSD"),
    "USDJPY=X": ("🇯🇵 USDJPY", "🇯🇵 USDJPY"),
    "USDCAD=X": ("🇨🇦 USDCAD", "🇨🇦 USDCAD"),
    "USDCHF=X": ("🇨🇭 USDCHF", "🇨🇭 USDCHF"),
}

THAI_MONTHS = [
    "", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
    "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."
]

STAGE_THAI = {
    "OPEN": "ถือเต็มไม้ (รอลุ้นเป้าแรก TP1)",
    "STAGE_1": "แบ่งปิดกำไร 50% แล้ว + บังหน้าทุนแล้ว (ไร้ความเสี่ยง)",
    "STAGE_2": "แบ่งปิด 50% แล้ว + ล็อกกำไรเพิ่มที่ +1.5R (รอลุ้น TP2)",
}


def format_pair_name(sym, short=False):
    info = PAIR_DISPLAY_MAP.get(sym)
    if info:
        return info[1] if short else info[0]
    return str(sym).replace("=X", "")


def format_dir_thai(direction):
    return "🟢 BUY (ขาขึ้น)" if direction == "BUY" else "🔴 SELL (ขาลง)"


def format_dir_short(direction):
    return "🟢 BUY" if direction == "BUY" else "🔴 SELL"


def format_bkk_time():
    bkk = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=7)
    return f"{bkk.day:02d} {THAI_MONTHS[bkk.month]} {bkk.year} | {bkk.strftime('%H:%M')} น."


def format_price(val, sym):
    try:
        v = float(val)
    except Exception:
        return str(val)
    if sym == "GC=F":
        return f"{v:.2f}"
    if "JPY" in str(sym):
        return f"{v:.3f}"
    return f"{v:.4f}"


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
        with urllib.request.urlopen(req, timeout=15):
            pass
    except Exception:
        pass


def _fetch_github_json(filename, default=None):
    ts = int(datetime.datetime.now().timestamp())
    url = f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/{filename}?t={ts}"
    req = urllib.request.Request(url, headers={"User-Agent": "PaulFTMOBot/4.0", "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return default


def get_live_scanner_data():
    return _fetch_github_json("forward_live_scanner.json", default=[])


def get_demo_ledger_data():
    return _fetch_github_json("forward_demo_ledger.json", default=None)


def get_alert_state_data():
    return _fetch_github_json("telegram_alert_state.json", default={})


def format_demo_portfolio(ledger):
    if not ledger:
        return "💼 <b>พอร์ต FTMO $100k:</b> กำลังโหลดข้อมูลล่าสุด กรุณากดอีกครั้งใน 5 วินาทีครับ"
    bal = ledger.get("current_balance", 100000.0)
    eq = ledger.get("current_equity", 100000.0)
    pnl = ledger.get("net_profit_usd", 0.0)
    ret = ledger.get("net_return_pct", 0.0)
    stats = ledger.get("stats", {})
    open_tr = ledger.get("open_trades", [])
    ftmo = ledger.get("ftmo_rules", {})
    ret_icon = "🟢" if pnl >= 0 else "🔴"
    bkk_str = format_bkk_time()

    if open_tr:
        action_line = f"✅ <b>ไม่ต้องกดอะไรเพิ่ม</b> — กำลังถือรันเทรนด์อยู่ {len(open_tr)} ไม้ (บอทเฝ้าปิด TP / SL ให้เองอัตโนมัติ)"
    else:
        action_line = "✅ <b>พอร์ตว่าง (0 ไม้) — ไม่ต้องทำอะไรครับ</b> รอบอทเข้าไม้อัตโนมัติเมื่อสัญญาณครบเกณฑ์"

    lines = [
        "💼 <b>สรุปพอร์ต FTMO $100,000 (Paul Pro V4)</b>",
        f"🕒 <code>{bkk_str} (เวลาไทย)</code>",
        "━━━━━━━━━━━━━━━━━━━━",
        "👉 <b>สถานะพอร์ตตอนนี้:</b>",
        action_line,
        "━━━━━━━━━━━━━━━━━━━━",
        f"💰 เงินคงเหลือ (Balance): <code>${bal:,.2f}</code>",
        f"📊 มูลค่าพอร์ตสุทธิ (Equity): <code>${eq:,.2f}</code>",
        f"{ret_icon} กำไร/ขาดทุนรวม: <b>{pnl:+,.2f} USD ({ret:+.2f}%)</b>",
        f"🛡️ ขาดทุนสูงสุดสะสม (Max DD): <code>{ledger.get('max_drawdown_pct', 0.0):.2f}%</code> <i>(เกณฑ์ FTMO ห้ามเกิน 10%)</i>",
        f"🏆 กฎความเสี่ยง FTMO: <b>{'✅ ปลอดภัยตามเกณฑ์' if ftmo.get('status', 'PASSING_HEALTHY') == 'PASSING_HEALTHY' else '⚠️ ใกล้เพดานความเสี่ยง'}</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "📈 <b>สถิติไม้ที่ปิดจบแล้ว:</b>",
        f"• ปิดจบแล้ว: <code>{stats.get('total_trades', 0)} ไม้</code> (ชนะ {stats.get('winning_trades', 0)} / แพ้ {stats.get('losing_trades', 0)})",
        f"• อัตราชนะ (Win Rate): <b>{stats.get('win_rate_pct', 0.0):.1f}%</b> | กำไรสะสม: <b>{stats.get('total_realized_r', 0.0):+}R</b>",
        "━━━━━━━━━━━━━━━━━━━━",
    ]
    if open_tr:
        lines.append(f"🔥 <b>ไม้ที่กำลังถืออยู่ตอนนี้ ({len(open_tr)} ไม้):</b>")
        for t in open_tr:
            sym = t["symbol"]
            fl_usd = t.get("floating_usd", 0.0)
            fl_r = t.get("floating_r", 0.0)
            fl_icon = "🟢" if fl_usd >= 0 else "🔴"
            st_lbl = STAGE_THAI.get(t.get("stage", "OPEN"), t.get("stage", "OPEN"))
            lines.append(
                f"• <b>{format_pair_name(sym)}</b> ({format_dir_short(t['dir'])} <code>{t.get('lots', 1.0)} Lot</code>)\n"
                f"   ↳ เข้าที่ <code>{format_price(t['entry'], sym)}</code> | {fl_icon} <b>{fl_usd:+,.2f} USD ({fl_r:+}R)</b>\n"
                f"   ↳ SL ปัจจุบัน: <code>{format_price(t['current_sl'], sym)}</code> | <i>{st_lbl}</i>"
            )
    else:
        lines.append("🔥 <b>ไม้ที่กำลังถืออยู่ตอนนี้:</b>\n• ไม่มีออเดอร์ค้าง (พอร์ตว่าง 0 ไม้)")
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


def format_radar_summary(live_states, ledger=None):
    bkk_str = format_bkk_time()
    open_trades = (ledger or {}).get("open_trades", [])
    open_syms = {t["symbol"] for t in open_trades}

    armed_pairs = []
    resting_pairs = []
    entry_pairs = []

    for s in live_states:
        sym = s["symbol"]
        if sym in open_syms:
            continue
        sig = s.get("overall_signal", "")
        if sig in ("ENTRY_NOW", "EXECUTE_NOW"):
            entry_pairs.append(s)
        elif sig in ("SETUP_ARMED", "READY_WAIT_BOS"):
            armed_pairs.append(s)
        else:
            resting_pairs.append(s)

    if entry_pairs:
        names = ", ".join(format_pair_name(s["symbol"], short=True) for s in entry_pairs)
        action_box = f"🟢 <b>มีสัญญาณเข้าไม้ ({names})</b> — บอทส่งคำสั่งเข้าพอร์ตอัตโนมัติแล้ว (เช็คแอป cTrader ได้เลย)"
    elif open_trades:
        action_box = (
            f"✅ <b>ไม่ต้องกดอะไรครับ (ถือไม้รันกำไรต่อ)</b>\n"
            f"ตอนนี้ถืออยู่ <b>{len(open_trades)} ไม้</b> บอทเฝ้าแบ่งปิด TP1 และตัด SL ให้เองอัตโนมัติ"
        )
    else:
        action_box = (
            "✅ <b>ไม่ต้องทำอะไรครับ</b> — ตอนนี้ยังไม่มีสัญญาณเข้าไม้ใหม่\n"
            "<i>(ระบบนี้ไม่ตั้ง Pending ล่วงหน้า — รอแท่ง 4 ชม. ปิดเบรกครบเกณฑ์ บอทจะกดเข้าไม้ให้เองอัตโนมัติ)</i>"
        )

    lines = [
        "📡 <b>สรุปสถานะพอร์ต & สัญญาณทั้ง 6 คู่เงิน</b>",
        f"🕒 <code>{bkk_str} (เวลาไทย)</code>",
        "━━━━━━━━━━━━━━━━━━━━",
        "👉 <b>สิ่งที่คุณต้องทำตอนนี้:</b>",
        action_box,
        "━━━━━━━━━━━━━━━━━━━━",
        "🔥 <b>ไม้ที่กำลังถืออยู่ในพอร์ต:</b>",
    ]

    if open_trades:
        for t in open_trades:
            sym = t["symbol"]
            fl_usd = t.get("floating_usd", 0.0)
            fl_r = t.get("floating_r", 0.0)
            fl_icon = "🟢" if fl_usd >= 0 else "🔴"
            lines.append(
                f"• <b>{format_pair_name(sym)}</b> ({format_dir_short(t['dir'])} <code>{t.get('lots', 1.0)} Lot</code>) — {fl_icon} <b>{fl_usd:+,.2f} USD ({fl_r:+}R)</b>\n"
                f"   ↳ เข้าที่ <code>{format_price(t['entry'], sym)}</code> | SL <code>{format_price(t['current_sl'], sym)}</code> | TP2 <code>{format_price(t['tp2'], sym)}</code>"
            )
    else:
        lines.append("• ไม่มีออเดอร์ค้าง (พอร์ตว่าง 0 ไม้)")

    lines.append("")
    lines.append("👀 <b>คู่ที่กำลังเฝ้าระวังใกล้จุดเข้า (ห้ามตั้งไม้ล่วงหน้า):</b>")
    if armed_pairs:
        for s in armed_pairs:
            sym = s["symbol"]
            tk = s["planned_ticket"]
            break_word = "ปิดสูงกว่า" if s["planned_dir"] == "BUY" else "ปิดต่ำกว่า"
            lines.append(
                f"• <b>{format_pair_name(sym)}</b> — เล็งฝั่ง <b>{format_dir_short(s['planned_dir'])}</b>\n"
                f"   ↳ ราคาตอนนี้ <code>{format_price(s['latest_price'], sym)}</code> | "
                f"รอแท่ง 4 ชม. {break_word} <code>{format_price(tk['entry'], sym)}</code> บอทจะเข้าไม้ให้เอง"
            )
    else:
        lines.append("• ไม่มีคู่ที่อยู่ในโซนเฝ้าระวังตอนนี้")

    if resting_pairs:
        lines.append("")
        resting_names = ", ".join(format_pair_name(s["symbol"], short=True) for s in resting_pairs)
        lines.append(f"💤 <b>คู่ที่ยังพักตัวห่างจุดเข้า (ไม่ต้องสนใจ):</b>\n• {resting_names}")

    if ledger:
        equity = ledger.get("current_equity", 100000.0)
        init_bal = ledger.get("initial_balance", 100000.0)
        tot_pnl = round(equity - init_bal, 2)
        tot_ret = round((tot_pnl / init_bal) * 100.0, 2) if init_bal > 0 else 0.0
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"💼 <b>พอร์ต FTMO $100k:</b> <code>${equity:,.2f}</code> (<b>{tot_ret:+.2f}% / {tot_pnl:+,.2f} USD</b>)")

    return "\n".join(lines)


def format_single_pair_ticket(s, ledger=None):
    sym = s["symbol"]
    pair_lbl = format_pair_name(sym)
    tk = s["planned_ticket"]
    g = s["gates"]
    bkk_str = format_bkk_time()
    dir_full = format_dir_thai(s["planned_dir"])
    break_word = "ปิดสูงกว่า" if s["planned_dir"] == "BUY" else "ปิดต่ำกว่า"

    open_tr = None
    if ledger:
        open_tr = next((t for t in ledger.get("open_trades", []) if t.get("symbol") == sym), None)

    if open_tr:
        status_hdr = f"🔥 <b>[กำลังถือไม้อยู่] {pair_lbl}</b>"
        action_txt = "✅ <b>ไม่ต้องกดอะไรเพิ่มครับ</b> — บอทเฝ้าแบ่งปิด TP1 และตัด SL บน cTrader ให้เองอัตโนมัติ"
    elif s.get("overall_signal") in ("ENTRY_NOW", "EXECUTE_NOW"):
        status_hdr = f"🟢🚀 <b>[เข้าไม้ใหม่แล้ว!] {pair_lbl}</b>"
        action_txt = "✅ <b>บอทดำเนินการเข้าไม้ให้อัตโนมัติแล้ว</b> (เปิดแอป cTrader เช็คดูได้เลยครับ)"
    elif s.get("overall_signal") in ("SETUP_ARMED", "READY_WAIT_BOS"):
        status_hdr = f"👀 <b>[เฝ้าระวังใกล้จุดเข้า — ยังไม่ออกไม้!] {pair_lbl}</b>"
        action_txt = (
            f"✋ <b>ห้ามตั้งไม้ Pending ล่วงหน้าครับ!</b> — รอแท่ง 4 ชม. {break_word} "
            f"<code>{format_price(tk['entry'], sym)}</code> แล้วบอทจะกดเข้าไม้ให้เองอัตโนมัติ"
        )
    else:
        status_hdr = f"💤 <b>[พักตัวห่างจุดเข้า] {pair_lbl}</b>"
        action_txt = "✅ <b>ไม่ต้องทำอะไรครับ</b> — ราคายังไม่เข้าโซนย่อตัว รอบอทแจ้งเตือนเมื่อใกล้จุดเข้า"

    lines = [
        status_hdr,
        f"🕒 <code>{bkk_str} (เวลาไทย)</code>",
        "━━━━━━━━━━━━━━━━━━━━",
        "👉 <b>สิ่งที่คุณต้องทำกับคู่นี้:</b>",
        action_txt,
        "━━━━━━━━━━━━━━━━━━━━",
        f"💵 ราคาปัจจุบัน: <code>{format_price(s['latest_price'], sym)}</code> | แผนฝั่ง: <b>{dir_full}</b>",
        "📊 <b>เช็คเงื่อนไข 3 ด่าน:</b>",
        f"• ด่าน 1 (เทรนด์ใหญ่ & กองทุน COT): {'🟢 ผ่าน' if g['g1_pass'] else '⏳ ยังไม่ผ่าน'}",
        f"• ด่าน 2 (ราคาย่อพักฐานแตะ EMA50): {'🟢 ผ่านแล้ว' if g['g2_pass'] else '⏳ รอย่อตัว'}",
        f"• ด่าน 3 (แท่ง 4 ชม. ปิดเบรก + RSI): {'🟢 เบรกเข้าไม้แล้ว!' if g['g3_pass'] else f'⏳ รอ{break_word} ' + format_price(tk['entry'], sym)}",
    ]

    if open_tr:
        fl_usd = open_tr.get("floating_usd", 0.0)
        fl_r = open_tr.get("floating_r", 0.0)
        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━",
            "🔥 <b>รายละเอียดไม้ที่ถืออยู่:</b>",
            f"• ฝั่ง: <b>{format_dir_thai(open_tr['dir'])}</b> | ขนาด: <code>{open_tr.get('lots', 1.0)} Lots</code>",
            f"• ราคาที่เข้า: <code>{format_price(open_tr['entry'], sym)}</code> | กำไร/ขาดทุน: <b>{fl_usd:+,.2f} USD ({fl_r:+}R)</b>",
            f"• 🛑 SL ปัจจุบัน: <code>{format_price(open_tr['current_sl'], sym)}</code> | 🏆 TP2: <code>{format_price(open_tr['tp2'], sym)}</code>",
        ])
    else:
        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━",
            "📐 <b>ตัวเลขแผนคำนวณล่วงหน้า (บอทใช้เข้าให้อัตโนมัติ — ห้ามตั้งไม้รอ):</b>",
            f"• ขนาด Lot แผน ($100k): <code>{tk['lots_100k']} Lots</code>",
            f"• จุดเบรกที่รอ: <code>{format_price(tk['entry'], sym)}</code>",
            f"• 🛑 SL แผน: <code>{format_price(tk['sl'], sym)}</code> <i>(ความเสี่ยง 0.75% = -$750)</i>",
            f"• 💰 เป้าแบ่งปิดครึ่งไม้ (TP1): <code>{format_price(tk['tp1'], sym)}</code> <i>(+1.5R)</i>",
            f"• 🏆 เป้าปิดทั้งหมด (TP2): <code>{format_price(tk['tp2'], sym)}</code> <i>(+3.5R)</i>",
        ])
    return "\n".join(lines)


def _fetch_github_csv(filename):
    ts = int(datetime.datetime.now().timestamp())
    url = f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/{filename}?t={ts}"
    req = urllib.request.Request(url, headers={"User-Agent": "PaulFTMOBot/4.0", "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            lines = resp.read().decode("utf-8").splitlines()
            if not lines:
                return []
            import csv
            reader = csv.DictReader(lines)
            return list(reader)
    except Exception:
        return []


def format_trade_history(ledger, trades_data=None, limit=5):
    bkk_str = format_bkk_time()
    open_tr = ledger.get("open_trades", []) if ledger else []
    
    lines = [
        "📜 <b>ประวัติออเดอร์ล่าสุด (Paul FTMO Pro V4)</b>",
        f"🕒 <code>{bkk_str}</code>",
        "━━━━━━━━━━━━━━━━━━",
    ]

    # Active Open Trades
    if open_tr:
        lines.append(f"🔥 <b>ไม้ที่กำลังถืออยู่ ({len(open_tr)} ไม้):</b>")
        for t in open_tr:
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

    # Closed Trades
    if trades_data:
        closed_tail = trades_data[-limit:][::-1]
        lines.append(f"🏁 <b>ประวัติ {len(closed_tail)} ไม้ล่าสุดที่ปิดจบแล้ว:</b>\n")
        idx = 1
        for r in closed_tail:
            sym = str(r.get('symbol', ''))
            pair_lbl = format_pair_name(sym, short=True)
            dir_lbl = format_dir_short(str(r.get('dir', '')))
            try:
                pnl = float(r.get('pnl_usd', 0.0))
            except Exception:
                pnl = 0.0
            pnl_icon = "🟢" if pnl >= 0 else "🔴"
            res = str(r.get('res', ''))
            res_thai = (
                "ชน TP เต็ม 🎉" if res == 'FULL_WIN' else
                "แบ่งปิด TP1 + ล็อกทุน" if res in ('TRAIL_WIN', 'PARTIAL_WIN') else
                "ชน SL ตามแผน"
            )
            try:
                r_val = float(r.get('r_net_after_fee', 0.0))
            except Exception:
                r_val = 0.0

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
        try:
            tot_pnl = sum(float(x.get('pnl_usd', 0.0)) for x in trades_data)
        except Exception:
            tot_pnl = 0.0
            
        lines.append("📊 <b>สถิติรวมของระบบ:</b>")
        lines.append(f"• ทั้งหมด: <code>{total_cnt} ไม้</code> | Win Rate: <b>{wr:.1f}%</b>")
        lines.append(f"• กำไรสะสมสุทธิ: <b>{tot_pnl:+,.2f} USD</b>")

    return "\n".join(lines)


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

            keyboard = {
                "keyboard": [
                    [{"text": "📜 ดูประวัติออเดอร์"}, {"text": "📡 สรุปสถานะตอนนี้"}],
                    [{"text": "💼 ดูพอร์ต ($100k)"}, {"text": "🔄 สั่งสแกนกราฟสด"}],
                    [{"text": "🥇 XAUUSD (ทองคำ)"}, {"text": "🇪🇺 EURUSD"}, {"text": "🇬🇧 GBPUSD"}],
                    [{"text": "🇯🇵 USDJPY"}, {"text": "🇨🇦 USDCAD"}, {"text": "🇨🇭 USDCHF"}]
                ],
                "resize_keyboard": True
            }

            try:
                if text in ["/start", "/help", "สวัสดี", "เมนู", "hi"]:
                    welcome_text = "\n".join([
                        f"🤖 <b>สวัสดีครับคุณ {msg['chat'].get('first_name', 'Trader')}!</b>",
                        "บอทแจ้งเตือน & เทรดอัตโนมัติ (Paul FTMO Pro V4) ปรับรูปแบบให้อ่านง่ายใน 3 วินาทีแล้วครับ:",
                        "",
                        "📌 <b>วิธีอ่านสถานะง่ายๆ:</b>",
                        "• 🟢 <b>เข้าไม้ใหม่แล้ว</b> = บอทออกออเดอร์ใน cTrader ให้แล้ว (ไม่ต้องกดเอง)",
                        "• 💰 <b>แบ่งปิด / ขยับล็อก</b> = บอทแบ่งปิดกำไรครึ่งไม้ให้แล้ว",
                        "• 🏁 <b>ปิดไม้จบ 100%</b> = จบออเดอร์เรียบร้อย",
                        "• 👀 <b>เฝ้าระวังใกล้จุดเข้า</b> = ดูเฉยๆ <b>ห้ามตั้ง Pending ล่วงหน้า</b> รอแท่ง 4 ชม. ปิดเบรกบอทจะเข้าให้เอง",
                        "• ⚪ <b>ยกเลิกเฝ้าระวัง</b> = ราคาไม่เบรกตามเกณฑ์ (ยังไม่ได้ออกไม้ ไม่ต้องกดยกเลิกอะไร)",
                        "",
                        "👇 <i>กดปุ่มเมนูด้านล่างเพื่อเช็คสถานะได้ตลอด 24 ชม. ครับ</i>"
                    ])
                    send_telegram(chat_id, welcome_text, keyboard)

                elif any(w in text for w in ["history", "ประวัติ", "ขอดูประวัติ", "ออเดอร์", "orders", "trades", "ไม้", "/history", "/trades"]):
                    ledger = get_demo_ledger_data()
                    trades = _fetch_github_csv("paul_pro_trades.csv")
                    send_telegram(chat_id, format_trade_history(ledger, trades), keyboard)

                elif any(w in text for w in ["demo", "portfolio", "balance", "พอร์ต", "เดโม", "/demo"]):
                    ledger = get_demo_ledger_data()
                    send_telegram(chat_id, format_demo_portfolio(ledger), keyboard)

                elif any(w in text for w in ["update", "อัพเดท", "อัปเดต", "สรุปสถานะ", "เรดาร์", "/radar"]):
                    live_data = get_live_scanner_data()
                    ledger = get_demo_ledger_data()
                    send_telegram(chat_id, format_radar_summary(live_data, ledger), keyboard)

                elif any(w in text for w in ["scan", "สแกน", "/refresh"]):
                    send_telegram(
                        chat_id,
                        "⏳ <b>กำลังสั่งเซิร์ฟเวอร์ Cloud สแกนกราฟแท่ง 4 ชม. สดเดี๋ยวนี้...</b>\nรอประมาณ 25 วินาที บอทจะส่งสรุปสถานะล่าสุดมาให้ครับ!",
                        keyboard
                    )
                    trigger_github_cloud_scan()

                elif any(w in text for w in ["gold", "ทอง", "xau"]):
                    live_data = get_live_scanner_data()
                    ledger = get_demo_ledger_data()
                    gold = next((s for s in live_data if s["symbol"] == "GC=F"), None)
                    if gold:
                        send_telegram(chat_id, format_single_pair_ticket(gold, ledger), keyboard)

                elif "jpy" in text:
                    live_data = get_live_scanner_data()
                    ledger = get_demo_ledger_data()
                    pair = next((s for s in live_data if "JPY" in s["symbol"]), None)
                    if pair:
                        send_telegram(chat_id, format_single_pair_ticket(pair, ledger), keyboard)

                elif "cad" in text:
                    live_data = get_live_scanner_data()
                    ledger = get_demo_ledger_data()
                    pair = next((s for s in live_data if "CAD" in s["symbol"]), None)
                    if pair:
                        send_telegram(chat_id, format_single_pair_ticket(pair, ledger), keyboard)

                elif "chf" in text:
                    live_data = get_live_scanner_data()
                    ledger = get_demo_ledger_data()
                    pair = next((s for s in live_data if "CHF" in s["symbol"]), None)
                    if pair:
                        send_telegram(chat_id, format_single_pair_ticket(pair, ledger), keyboard)

                elif "gbp" in text:
                    live_data = get_live_scanner_data()
                    ledger = get_demo_ledger_data()
                    pair = next((s for s in live_data if "GBP" in s["symbol"]), None)
                    if pair:
                        send_telegram(chat_id, format_single_pair_ticket(pair, ledger), keyboard)

                elif "eur" in text:
                    live_data = get_live_scanner_data()
                    ledger = get_demo_ledger_data()
                    pair = next((s for s in live_data if "EUR" in s["symbol"]), None)
                    if pair:
                        send_telegram(chat_id, format_single_pair_ticket(pair, ledger), keyboard)

                else:
                    live_data = get_live_scanner_data()
                    ledger = get_demo_ledger_data()
                    send_telegram(chat_id, format_radar_summary(live_data, ledger), keyboard)

            except Exception as e:
                send_telegram(chat_id, f"⚠️ เกิดข้อผิดพลาด: {str(e)}")

        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")
