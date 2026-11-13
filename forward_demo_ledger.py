"""
Paul FTMO Pro V4 - Autonomous Cloud Forward Demo Ledger (forward_demo_ledger.py)
Automated $100,000 Portfolio & cTrader Live Execution Bridge running on 100% Free Cloud:
- Tracks all forward signals strictly following the 1-2-3-4 Paul Pro rules
- Fixed Risk: 0.75% ($750 per 1.0R) on $100k account
- Real 0.04R broker fee & slippage deduction per trade
- Strict 3-Stage Trade Management (TP1 +1.5R 50% scale-out, Lock +0.3R, Stage 2 Lock +1.5R, TP2 +3.5R)
- Crystal-clear human-readable Thai Telegram notifications (3-second comprehension).
"""

import os
import sys
import json
import copy
from datetime import datetime, timezone, timedelta

if sys.stdout and getattr(sys.stdout, 'encoding', None) != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LEDGER_PATH = os.path.join(BASE_DIR, 'forward_demo_ledger.json')

INITIAL_BALANCE = 100000.0
RISK_PER_TRADE_USD = 750.0  # 0.75% of $100k
FEE_PER_TRADE_R = 0.04      # 0.04R fee ($30)

PAIR_DISPLAY_MAP = {
    'GC=F': ('🥇 XAUUSD (ทองคำ)', '🥇 XAUUSD'),
    'EURUSD=X': ('🇪🇺 EURUSD', '🇪🇺 EURUSD'),
    'GBPUSD=X': ('🇬🇧 GBPUSD', '🇬🇧 GBPUSD'),
    'USDJPY=X': ('🇯🇵 USDJPY', '🇯🇵 USDJPY'),
    'USDCAD=X': ('🇨🇦 USDCAD', '🇨🇦 USDCAD'),
    'USDCHF=X': ('🇨🇭 USDCHF', '🇨🇭 USDCHF'),
}

THAI_MONTHS = [
    "", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
    "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."
]

CLOSE_REASON_THAI = {
    'TP2_HIT': 'ชนเป้าใหญ่ TP2 ครบ 100% (+3.5R)',
    'LOCK2_HIT': 'ราคาย่อชนจุดล็อกกำไร Stage 2 (เก็บกำไรเข้าพอร์ต)',
    'LOCK1_HIT': 'ราคาย่อชนจุดบังหน้าทุน หลังแบ่งปิด TP1 ไปแล้ว (จบไม้นี้กำไร)',
    'SL_HIT': 'ราคาชนจุดตัดขาดทุน SL ตามแผน (คุมความเสี่ยง 0.75%)',
}

STAGE_THAI = {
    'OPEN': 'ถือเต็มไม้ (รอลุ้นเป้าแรก TP1)',
    'STAGE_1': 'แบ่งปิดกำไร 50% แล้ว + บังหน้าทุนแล้ว (ไร้ความเสี่ยง)',
    'STAGE_2': 'แบ่งปิด 50% แล้ว + ล็อกกำไรเพิ่มที่ +1.5R (รอลุ้น TP2)',
}


def escape_html(val):
    if not isinstance(val, str):
        val = str(val)
    return val.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def format_pair_name(sym, short=False):
    info = PAIR_DISPLAY_MAP.get(sym)
    if info:
        return info[1] if short else info[0]
    return str(sym).replace('=X', '')


def format_dir_thai(direction):
    return "🟢 BUY (ขาขึ้น)" if direction == "BUY" else "🔴 SELL (ขาลง)"


def format_dir_short(direction):
    return "🟢 BUY" if direction == "BUY" else "🔴 SELL"


def format_bkk_time(dt_utc=None):
    if dt_utc is None:
        dt_utc = datetime.now(timezone.utc)
    bkk = dt_utc + timedelta(hours=7)
    return f"{bkk.day:02d} {THAI_MONTHS[bkk.month]} {bkk.year} | {bkk.strftime('%H:%M')} น."


def format_price(val, sym):
    try:
        v = float(val)
    except Exception:
        return str(val)
    if sym == 'GC=F':
        return f"{v:.2f}"
    if 'JPY' in str(sym):
        return f"{v:.3f}"
    return f"{v:.4f}"


def format_close_reason_thai(reason):
    return CLOSE_REASON_THAI.get(reason, str(reason))


def format_stage_thai(stage):
    return STAGE_THAI.get(stage, str(stage))


def get_default_ledger():
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "account_name": "Paul FTMO Pro V4 - Cloud Autonomous Demo",
        "currency": "USD",
        "initial_balance": INITIAL_BALANCE,
        "current_balance": INITIAL_BALANCE,
        "current_equity": INITIAL_BALANCE,
        "floating_pnl_usd": 0.0,
        "net_profit_usd": 0.0,
        "net_return_pct": 0.0,
        "high_water_mark": INITIAL_BALANCE,
        "max_drawdown_pct": 0.0,
        "risk_per_trade_pct": 0.75,
        "risk_per_trade_usd": RISK_PER_TRADE_USD,
        "fee_per_trade_r": FEE_PER_TRADE_R,
        "started_at_utc": now_iso,
        "last_updated_utc": now_iso,
        "ftmo_rules": {
            "max_daily_loss_pct": 5.0,
            "max_total_loss_pct": 10.0,
            "profit_target_step1_pct": 10.0,
            "current_daily_drawdown_pct": 0.0,
            "current_total_drawdown_pct": 0.0,
            "status": "PASSING_HEALTHY"
        },
        "stats": {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "breakeven_trades": 0,
            "win_rate_pct": 0.0,
            "avg_win_r": 0.0,
            "avg_loss_r": 0.0,
            "profit_factor": 0.0,
            "total_realized_r": 0.0
        },
        "open_trades": [],
        "closed_trades": []
    }


def load_ledger():
    if os.path.exists(LEDGER_PATH):
        try:
            with open(LEDGER_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return get_default_ledger()


def save_ledger(ledger):
    ledger["last_updated_utc"] = datetime.now(timezone.utc).isoformat()
    with open(LEDGER_PATH, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(ledger, f, indent=2, ensure_ascii=False)
    return ledger


def _build_tp1_message(sym, direction, tp1_price, lock1_price, tp2_price, action_html, ctrader_line=""):
    pair_lbl = format_pair_name(sym)
    bkk_str = format_bkk_time()
    lines = [
        f"💰 <b>[ชนเป้าแรก TP1 แบ่งปิด 50%] {pair_lbl}</b>",
        "━━━━━━━━━━━━━━━━━━",
        f"• ราคาชนเป้า: <code>{format_price(tp1_price, sym)}</code> <i>(ล็อกกำไร +0.75R)</i>",
        f"• 🛡️ เลื่อน SL บังทุนแล้วที่: <code>{format_price(lock1_price, sym)}</code> <i>(ไร้ความเสี่ยง 100%)</i>",
        f"• 🏆 เป้าหมาย TP2 ที่เหลือ: <code>{format_price(tp2_price, sym)}</code> <i>(+3.5R)</i>",
        "━━━━━━━━━━━━━━━━━━",
        action_html,
        f"🕒 <code>{bkk_str}</code>",
    ]
    if ctrader_line:
        lines.append(ctrader_line)
    return "\n".join(lines)


def _build_stage2_message(sym, direction, lock2_price, tp2_price):
    pair_lbl = format_pair_name(sym)
    bkk_str = format_bkk_time()
    lines = [
        f"🔒 <b>[ล็อกกำไรเพิ่ม +1.5R] {pair_lbl}</b>",
        "━━━━━━━━━━━━━━━━━━",
        f"• ราคาพุ่งทะลุ +2.5R ขยับ SL ตามหลังราคา",
        f"• 🛡️ SL ล่าสุดล็อกที่: <code>{format_price(lock2_price, sym)}</code> <i>(การันตีกำไร +1.5R แน่นอน)</i>",
        f"• 🏆 เป้าหมายใหญ่ TP2: <code>{format_price(tp2_price, sym)}</code> <i>(+3.5R)</i>",
        "━━━━━━━━━━━━━━━━━━",
        "✅ ถือรันกำไรต่ออัตโนมัติ (ไม่ต้องกดอะไร)",
        f"🕒 <code>{bkk_str}</code>",
    ]
    return "\n".join(lines)


def _build_close_message(sym, direction, entry_price, close_price, close_reason, net_r, pnl_usd, new_balance, action_html, ctrader_line=""):
    pair_lbl = format_pair_name(sym)
    dir_lbl = format_dir_short(direction)
    bkk_str = format_bkk_time()
    is_win = pnl_usd >= 0
    header = (
        f"🏁🎉 <b>[ปิดไม้สำเร็จ — กำไร!] {pair_lbl} ({dir_lbl})</b>"
        if is_win else
        f"🏁🛡️ <b>[ปิดไม้ — ตัดขาดทุนตามแผน] {pair_lbl} ({dir_lbl})</b>"
    )
    pnl_sign = "+" if pnl_usd >= 0 else ""
    lines = [
        header,
        "━━━━━━━━━━━━━━━━━━",
        f"• ผลลัพธ์: <b>{pnl_sign}{pnl_usd:,.2f} USD ({net_r:+}R)</b>",
        f"• สาเหตุ: {format_close_reason_thai(close_reason)}",
        f"• จุดเข้า: <code>{format_price(entry_price, sym)}</code> ➔ ปิด: <code>{format_price(close_price, sym)}</code>",
        f"• พอร์ตล่าสุด: <code>${new_balance:,.2f}</code>",
        "━━━━━━━━━━━━━━━━━━",
        action_html,
        f"🕒 <code>{bkk_str}</code>",
    ]
    if ctrader_line:
        lines.append(ctrader_line)
    return "\n".join(lines)


def _build_entry_message(sym, tk, action_html, ctrader_line=""):
    pair_lbl = format_pair_name(sym)
    dir_short = format_dir_short(tk['dir'])
    bkk_str = format_bkk_time()
    lines = [
        f"🚀 <b>[เปิดไม้ใหม่] {pair_lbl}</b>",
        "━━━━━━━━━━━━━━━━━━",
        f"• ฝั่ง: <b>{dir_short}</b> | ขนาด: <code>{tk['lots_100k']} Lot</code>",
        f"• จุดเข้า: <code>{format_price(tk['entry'], sym)}</code>",
        f"• 🛑 SL: <code>{format_price(tk['sl'], sym)}</code> <i>(-0.75R)</i>",
        f"• 💰 TP1: <code>{format_price(tk['tp1'], sym)}</code> <i>(+1.5R)</i> | 🏆 TP2: <code>{format_price(tk['tp2'], sym)}</code> <i>(+3.5R)</i>",
        "━━━━━━━━━━━━━━━━━━",
        action_html,
        f"🕒 <code>{bkk_str}</code>",
    ]
    if ctrader_line:
        lines.append(ctrader_line)
    return "\n".join(lines)


def update_forward_demo_ledger(live_states, execute_live_fix=True, dry_run=False, initial_ledger=None):
    """
    Called every H4 cycle by telegram_notifier.py or GitHub Actions.
    1. Checks all open trades against latest H4 candle high/low (executes TP1 50% & TP2/SL 100% on cTrader FIX).
    2. Opens new trades if overall_signal == 'ENTRY_NOW' and symbol has no open trade (executes Market Order on cTrader FIX).
    3. Emits single unified, human-friendly Thai Telegram messages for every real trade lifecycle event.
    Returns: (updated_ledger, list_of_events)
    """
    ledger = copy.deepcopy(initial_ledger) if initial_ledger is not None else load_ledger()
    now_iso = datetime.now(timezone.utc).isoformat()
    events = []

    open_trades = ledger.get("open_trades", [])
    closed_trades = ledger.get("closed_trades", [])
    remaining_open_trades = []

    states_by_sym = {s['symbol']: s for s in live_states}

    # -------------------------------------------------------------
    # 1. PROCESS EXISTING OPEN POSITIONS
    # -------------------------------------------------------------
    for tr in open_trades:
        sym = tr['symbol']
        s = states_by_sym.get(sym)
        if not s:
            remaining_open_trades.append(tr)
            continue

        c_now = float(s['latest_price'])
        bar_high = float(s['live_candles'][-1][2]) if s.get('live_candles') else c_now
        bar_low = float(s['live_candles'][-1][3]) if s.get('live_candles') else c_now
        entry = float(tr['entry'])
        risk_dist = float(tr['risk_dist'])
        direction = tr['dir']
        stage = tr['stage']  # 'OPEN', 'STAGE_1', 'STAGE_2'
        current_sl = float(tr['current_sl'])

        is_buy = direction == 'BUY'
        trade_closed = False
        close_reason = None
        close_price = None

        # Match paul_engine.py exact causal order:
        # 1) Check SL active at start of this H4 candle first
        # 2) Otherwise check TP1 -> Stage 2 -> TP2 upgrades (new locked SL applies from next candle onward)
        sl_triggered = (bar_low <= current_sl) if is_buy else (bar_high >= current_sl)

        if sl_triggered:
            trade_closed = True
            close_price = current_sl
            if stage == 'OPEN':
                close_reason = 'SL_HIT'
                raw_r = -1.0
            elif stage == 'STAGE_1':
                close_reason = 'LOCK1_HIT'
                raw_r = tr.get('realized_r_tp1', 0.0) + (0.3 * 0.5)
            else:
                close_reason = 'LOCK2_HIT'
                raw_r = tr.get('realized_r_tp1', 0.0) + (1.5 * 0.5)
            net_r = round(raw_r - FEE_PER_TRADE_R, 2)
            pnl_usd = round(net_r * RISK_PER_TRADE_USD, 2)
        else:
            # --- Check TP1 (+1.5R) ---
            tp1_triggered = (
                (stage == 'OPEN' and bar_high >= float(tr['tp1']))
                if is_buy else
                (stage == 'OPEN' and bar_low <= float(tr['tp1']))
            )
            if tp1_triggered:
                tr['stage'] = 'STAGE_1'
                tr['current_sl'] = float(tr['lock1'])  # Move SL to +0.3R
                tr['units_remaining'] = 0.5
                tr['tp1_hit_time'] = now_iso
                tr['realized_r_tp1'] = 1.5 * 0.5  # +0.75R realized

                tp1_action = "✅ <b>ไม่ต้องกดอะไรครับ</b> — บอทแบ่งปิดกำไร 50% และขยับจุดกันหน้าทุนให้อัตโนมัติแล้ว (ไม้นี้ไม่ขาดทุน 100% แล้ว!)"
                tp1_ctrader = ""
                if tr.get('fix_position_id') and execute_live_fix and not dry_run:
                    try:
                        import ftmo_fix_trader
                        fcfg = ftmo_fix_trader.load_fix_config()
                        if fcfg.get('password'):
                            fclient = ftmo_fix_trader.FtmoFixClient(fcfg)
                            fclient.send_logon()
                            half_u = int(round(float(tr.get('volume_units', 100000)) * 0.5))
                            s_id = tr.get('symbol_id', ftmo_fix_trader.FTMO_SYMBOLS.get(sym, {}).get('id', '1'))
                            c_ok, c_res = fclient.close_position(tr['fix_position_id'], s_id, direction, half_u)
                            fclient.close()
                            if c_ok:
                                tp1_action = "✅ <b>ไม่ต้องกดอะไรครับ</b> — บอทแบ่งปิดกำไรครึ่งไม้บน cTrader ให้แล้ว และขยับจุดเฝ้ากันหน้าทุนให้อัตโนมัติ (ไม้นี้ไม่ขาดทุน 100% แล้ว!)"
                                tp1_ctrader = f"⚡ สถานะ cTrader: แบ่งปิด 50% (<code>{half_u:,} units</code>) สำเร็จ 🟢"
                            else:
                                tp1_action = f"⚠️ <b>บอทแบ่งปิดบน cTrader ไม่สำเร็จ</b> — กรุณาเปิดแอปแบ่งปิด 50% และเลื่อน SL มาที่ <code>{format_price(tr['lock1'], sym)}</code> ครับ"
                                tp1_ctrader = f"⚠️ สาเหตุ cTrader: <code>{escape_html(str(c_res))}</code>"
                    except Exception as ex:
                        tp1_action = "⚠️ <b>บอทแบ่งปิดบน cTrader ขัดข้อง</b> — กรุณาเปิดแอปเช็คและแบ่งปิด 50% ครับ"
                        tp1_ctrader = f"⚠️ สาเหตุ cTrader: <code>{escape_html(str(ex))}</code>"

                tp1_msg = _build_tp1_message(
                    sym, direction, tr['tp1'], tr['lock1'], tr['tp2'], tp1_action, tp1_ctrader
                )
                events.append({
                    'type': 'TP1_HIT',
                    'symbol': sym,
                    'direction': direction,
                    'entry': entry,
                    'hit_price': float(tr['tp1']),
                    'locked_sl': float(tr['lock1']),
                    'message': tp1_msg
                })
                stage = 'STAGE_1'
                current_sl = float(tr['lock1'])

            # --- Check Stage 2 (+2.5R) ---
            stage2_triggered = (
                (stage == 'STAGE_1' and bar_high >= float(tr['stage2']))
                if is_buy else
                (stage == 'STAGE_1' and bar_low <= float(tr['stage2']))
            )
            if stage2_triggered:
                tr['stage'] = 'STAGE_2'
                tr['current_sl'] = float(tr['lock2'])  # Move SL to +1.5R
                events.append({
                    'type': 'STAGE2_HIT',
                    'symbol': sym,
                    'direction': direction,
                    'entry': entry,
                    'hit_price': float(tr['stage2']),
                    'locked_sl': float(tr['lock2']),
                    'message': _build_stage2_message(sym, direction, tr['lock2'], tr['tp2'])
                })
                stage = 'STAGE_2'
                current_sl = float(tr['lock2'])

            # --- Check TP2 (+3.5R) ---
            tp2_triggered = (
                (stage in ('STAGE_1', 'STAGE_2') and bar_high >= float(tr['tp2']))
                if is_buy else
                (stage in ('STAGE_1', 'STAGE_2') and bar_low <= float(tr['tp2']))
            )
            if tp2_triggered:
                trade_closed = True
                close_reason = 'TP2_HIT'
                close_price = float(tr['tp2'])
                r_remaining = 3.5 * 0.5
                raw_r = tr.get('realized_r_tp1', 0.0) + r_remaining
                net_r = round(raw_r - FEE_PER_TRADE_R, 2)
                pnl_usd = round(net_r * RISK_PER_TRADE_USD, 2)

        if trade_closed:
            tr['exit_time'] = now_iso
            tr['exit_price'] = close_price
            tr['close_reason'] = close_reason
            tr['net_r'] = net_r
            tr['pnl_usd'] = pnl_usd
            ledger['current_balance'] = round(ledger['current_balance'] + pnl_usd, 2)
            closed_trades.append(tr)

            close_action = "✅ <b>ไม่ต้องทำอะไรครับ (จบไม้นี้เรียบร้อย)</b> — บอทบันทึกปิดออเดอร์ครบ 100% แล้ว"
            close_ctrader = ""
            if tr.get('fix_position_id') and execute_live_fix and not dry_run:
                try:
                    import ftmo_fix_trader
                    fcfg = ftmo_fix_trader.load_fix_config()
                    if fcfg.get('password'):
                        fclient = ftmo_fix_trader.FtmoFixClient(fcfg)
                        fclient.send_logon()
                        rem_u = int(round(float(tr.get('volume_units', 100000)) * float(tr.get('units_remaining', 1.0))))
                        s_id = tr.get('symbol_id', ftmo_fix_trader.FTMO_SYMBOLS.get(sym, {}).get('id', '1'))
                        c_ok, c_res = fclient.close_position(tr['fix_position_id'], s_id, direction, rem_u)
                        fclient.close()
                        if c_ok:
                            close_action = "✅ <b>ไม่ต้องทำอะไรครับ (จบไม้นี้เรียบร้อย)</b> — บอทปิดออเดอร์บน cTrader ครบ 100% ให้แล้ว"
                            close_ctrader = "⚡ สถานะ cTrader: ปิดออเดอร์ครบ 100% สำเร็จ 🟢"
                        else:
                            close_action = "⚠️ <b>บอทสั่งปิดบน cTrader ไม่สำเร็จ</b> — กรุณาเปิดแอปเช็คและกดปิดออเดอร์คู่นี้ครับ"
                            close_ctrader = f"⚠️ สาเหตุ cTrader: <code>{escape_html(str(c_res))}</code>"
                except Exception as ex:
                    close_action = "⚠️ <b>บอทสั่งปิดบน cTrader ขัดข้อง</b> — กรุณาเปิดแอปเช็คสถานะออเดอร์คู่นี้ครับ"
                    close_ctrader = f"⚠️ สาเหตุ cTrader: <code>{escape_html(str(ex))}</code>"

            close_msg = _build_close_message(
                sym, direction, entry, close_price, close_reason,
                net_r, pnl_usd, ledger['current_balance'], close_action, close_ctrader
            )
            events.append({
                'type': 'TRADE_CLOSED',
                'symbol': sym,
                'direction': direction,
                'reason': close_reason,
                'pnl_usd': pnl_usd,
                'net_r': net_r,
                'message': close_msg
            })
        else:
            fl_r_full = ((c_now - entry) / risk_dist) if is_buy else ((entry - c_now) / risk_dist)
            if stage == 'OPEN':
                fl_r = fl_r_full
            else:
                fl_r = tr.get('realized_r_tp1', 0.0) + (fl_r_full * 0.5)
            tr['current_price'] = c_now
            tr['floating_r'] = round(fl_r, 2)
            tr['floating_usd'] = round(fl_r * RISK_PER_TRADE_USD, 2)
            remaining_open_trades.append(tr)

    # -------------------------------------------------------------
    # 2. CHECK FOR NEW ENTRY_NOW SIGNALS & EXECUTE ON CTRADER ATOMICALLY
    # -------------------------------------------------------------
    existing_open_syms = {t['symbol'] for t in remaining_open_trades}
    for s in live_states:
        sym = s['symbol']
        sig = s['overall_signal']
        tk = s['planned_ticket']

        if sym not in existing_open_syms and sig in ('ENTRY_NOW', 'EXECUTE_NOW'):
            new_ticket_id = f"DEMO-{len(closed_trades) + len(remaining_open_trades) + 1001}"
            new_trade = {
                'ticket_id': new_ticket_id,
                'symbol': sym,
                'name': s.get('name', sym),
                'dir': tk['dir'],
                'entry_time': now_iso,
                'entry': float(tk['entry']),
                'lots': float(tk['lots_100k']),
                'sl': float(tk['sl']),
                'current_sl': float(tk['sl']),
                'initial_sl': float(tk['sl']),
                'tp1': float(tk['tp1']),
                'lock1': float(tk['lock1']),
                'stage2': float(tk['stage2']),
                'lock2': float(tk['lock2']),
                'tp2': float(tk['tp2']),
                'risk_dist': abs(float(tk['entry']) - float(tk['sl'])),
                'atr_mult': float(tk.get('atr_mult', 1.0)),
                'stage': 'OPEN',
                'units_remaining': 1.0,
                'current_price': float(s['latest_price']),
                'floating_r': 0.0,
                'floating_usd': 0.0
            }

            entry_action = "✅ <b>บันทึกเข้าพอร์ตจำลอง $100k อัตโนมัติแล้ว</b> (หากเทรดพอร์ตแยก ให้กดเข้า Market ตามตัวเลขด้านล่างครับ)"
            entry_ctrader = ""

            if execute_live_fix and not dry_run:
                try:
                    import ftmo_fix_trader
                    cfg = ftmo_fix_trader.load_fix_config()
                    if cfg.get('password'):
                        fix_res = ftmo_fix_trader.execute_signal(s)
                        print(f"[FTMO FIX] execute_signal result for {sym}: {fix_res}")
                        acct_id = cfg.get('account_id', '17235426')
                        if fix_res.get('ok'):
                            order_id = str(fix_res.get('res', {}).get('order_id', 'SUCCESS'))
                            pos_id = str(fix_res.get('res', {}).get('position_id', 'N/A'))
                            lots = fix_res.get('lots', tk.get('lots_100k', 1.0))
                            units = int(fix_res.get('units', 100000))
                            sym_id = str(fix_res.get('symbol_id', '1'))
                            new_trade['fix_position_id'] = pos_id
                            new_trade['fix_order_id'] = order_id
                            new_trade['volume_units'] = units
                            new_trade['symbol_id'] = sym_id
                            entry_action = (
                                f"✅ <b>ไม่ต้องกดเข้าไม้เองครับ</b> — บอทออกออเดอร์ให้ใน cTrader "
                                f"(<code>#{acct_id}</code>) เรียบร้อยแล้ว! (เปิดแอปเช็คดูได้เลย)"
                            )
                            entry_ctrader = (
                                f"⚡ สถานะ cTrader: เปิดไม้สำเร็จ (PosID <code>{pos_id}</code> | "
                                f"<code>{lots} Lots</code> / <code>{units:,} Units</code>) 🟢"
                            )
                        else:
                            err_txt = escape_html(str(fix_res.get('error', 'เชื่อมต่อไม่สำเร็จ')))
                            entry_action = (
                                "⚠️ <b>บอทยิงออเดอร์เข้า cTrader ไม่สำเร็จ</b> — หากต้องการเทรดไม้นี้ "
                                "ให้กดเปิดออเดอร์ (Market) ในแอปตามตัวเลขด้านล่างครับ"
                            )
                            entry_ctrader = f"⚠️ สาเหตุ cTrader: <code>{err_txt}</code>"
                except Exception as ex:
                    entry_action = (
                        "⚠️ <b>การเชื่อมต่อ cTrader ขัดข้อง</b> — หากต้องการเทรดไม้นี้ "
                        "ให้กดเปิดออเดอร์ (Market) ในแอปตามตัวเลขด้านล่างครับ"
                    )
                    entry_ctrader = f"⚠️ สาเหตุ cTrader: <code>{escape_html(str(ex))}</code>"

            remaining_open_trades.append(new_trade)
            existing_open_syms.add(sym)

            events.append({
                'type': 'TRADE_OPENED',
                'symbol': sym,
                'direction': tk['dir'],
                'ticket_id': new_ticket_id,
                'entry': float(tk['entry']),
                'lots': float(tk['lots_100k']),
                'sl': float(tk['sl']),
                'tp1': float(tk['tp1']),
                'tp2': float(tk['tp2']),
                'message': _build_entry_message(sym, tk, entry_action, entry_ctrader)
            })

    # -------------------------------------------------------------
    # 3. RECALCULATE OVERALL PORTFOLIO METRICS
    # -------------------------------------------------------------
    ledger['open_trades'] = remaining_open_trades
    ledger['closed_trades'] = closed_trades

    total_floating_usd = sum(t.get('floating_usd', 0.0) for t in remaining_open_trades)
    current_equity = round(ledger['current_balance'] + total_floating_usd, 2)
    ledger['floating_pnl_usd'] = round(total_floating_usd, 2)
    ledger['current_equity'] = current_equity

    net_profit_usd = round(current_equity - INITIAL_BALANCE, 2)
    ledger['net_profit_usd'] = net_profit_usd
    ledger['net_return_pct'] = round((net_profit_usd / INITIAL_BALANCE) * 100.0, 2)

    if current_equity > ledger.get('high_water_mark', INITIAL_BALANCE):
        ledger['high_water_mark'] = current_equity
    hwm = ledger['high_water_mark']
    dd_pct = round(((hwm - current_equity) / hwm) * 100.0, 2) if hwm > 0 else 0.0
    if dd_pct > ledger.get('max_drawdown_pct', 0.0):
        ledger['max_drawdown_pct'] = dd_pct

    total_closed = len(closed_trades)
    wins = [t for t in closed_trades if t.get('pnl_usd', 0.0) > 0]
    losses = [t for t in closed_trades if t.get('pnl_usd', 0.0) < 0]
    be = [t for t in closed_trades if t.get('pnl_usd', 0.0) == 0]

    win_rate = round((len(wins) / total_closed) * 100.0, 1) if total_closed > 0 else 0.0
    total_realized_r = round(sum(t.get('net_r', 0.0) for t in closed_trades), 2)
    avg_win_r = round(sum(t.get('net_r', 0.0) for t in wins) / len(wins), 2) if wins else 0.0
    avg_loss_r = round(sum(t.get('net_r', 0.0) for t in losses) / len(losses), 2) if losses else 0.0
    total_win_usd = sum(t.get('pnl_usd', 0.0) for t in wins)
    total_loss_usd = abs(sum(t.get('pnl_usd', 0.0) for t in losses))
    pf = round(total_win_usd / total_loss_usd, 2) if total_loss_usd > 0 else (99.0 if total_win_usd > 0 else 0.0)

    ledger['stats'] = {
        'total_trades': total_closed,
        'winning_trades': len(wins),
        'losing_trades': len(losses),
        'breakeven_trades': len(be),
        'win_rate_pct': win_rate,
        'avg_win_r': avg_win_r,
        'avg_loss_r': avg_loss_r,
        'profit_factor': pf,
        'total_realized_r': total_realized_r
    }

    daily_dd = round(max(0.0, (ledger['current_balance'] - current_equity) / ledger['current_balance'] * 100.0), 2)
    tot_dd = dd_pct
    ledger['ftmo_rules']['current_daily_drawdown_pct'] = daily_dd
    ledger['ftmo_rules']['current_total_drawdown_pct'] = tot_dd
    if daily_dd >= 4.5 or tot_dd >= 9.5:
        ledger['ftmo_rules']['status'] = 'WARNING_NEAR_LIMIT'
    else:
        ledger['ftmo_rules']['status'] = 'PASSING_HEALTHY'

    if not dry_run:
        save_ledger(ledger)
    return ledger, events


def format_demo_portfolio_summary(ledger):
    """Formats a crystal-clear portfolio status card for Telegram."""
    bal = ledger.get('current_balance', INITIAL_BALANCE)
    eq = ledger.get('current_equity', INITIAL_BALANCE)
    pnl = ledger.get('net_profit_usd', 0.0)
    ret = ledger.get('net_return_pct', 0.0)
    stats = ledger.get('stats', {})
    open_tr = ledger.get('open_trades', [])
    ftmo = ledger.get('ftmo_rules', {})

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
            sym = t['symbol']
            pair_lbl = format_pair_name(sym)
            dir_lbl = format_dir_short(t['dir'])
            fl_usd = t.get('floating_usd', 0.0)
            fl_r = t.get('floating_r', 0.0)
            fl_icon = "🟢" if fl_usd >= 0 else "🔴"
            lines.append(
                f"• <b>{pair_lbl}</b> ({dir_lbl} <code>{t.get('lots', 1.0)} Lot</code>)\n"
                f"   ↳ เข้าที่ <code>{format_price(t['entry'], sym)}</code> | {fl_icon} <b>{fl_usd:+,.2f} USD ({fl_r:+}R)</b>\n"
                f"   ↳ SL ปัจจุบัน: <code>{format_price(t['current_sl'], sym)}</code> | สถานะ: <i>{format_stage_thai(t.get('stage', 'OPEN'))}</i>"
            )
    else:
        lines.append("🔥 <b>ไม้ที่กำลังถืออยู่ตอนนี้:</b>\n• ไม่มีออเดอร์ค้าง (พอร์ตว่าง 0 ไม้)")

    return "\n".join(lines)


def reset_ledger():
    """Resets the demo portfolio to initial clean $100,000.00 state with 0 trades."""
    clean = get_default_ledger()
    save_ledger(clean)
    print("✅ Forward Demo Ledger successfully reset to initial state ($100,000.00 USD, 0 trades).")
    return clean


def bind_fix_execution_to_trade(symbol, position_id, order_id, units, symbol_id):
    """Binds cTrader FIX live execution IDs to the forward ledger open trade."""
    try:
        ledger = load_ledger()
        for tr in ledger.get('open_trades', []):
            if tr.get('symbol') == symbol:
                tr['fix_position_id'] = str(position_id)
                tr['fix_order_id'] = str(order_id)
                tr['volume_units'] = int(units)
                tr['symbol_id'] = str(symbol_id)
                save_ledger(ledger)
                print(f"[Ledger] Bound cTrader FIX PosID {position_id} to open trade {symbol}")
                break
    except Exception as e:
        print(f"[Ledger] Error binding FIX execution: {e}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Paul Pro V4 Forward Demo Ledger')
    parser.add_argument('--reset', action='store_true', help='Reset ledger to initial $100,000 state')
    args = parser.parse_args()

    if args.reset:
        reset_ledger()
    else:
        l = load_ledger()
        print(f"Current Balance: ${l['current_balance']:,.2f} | Open Trades: {len(l['open_trades'])} | Closed: {len(l['closed_trades'])}")
