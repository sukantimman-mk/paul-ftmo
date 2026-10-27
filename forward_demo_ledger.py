"""
Paul FTMO Pro V4 - Autonomous Cloud Forward Demo Ledger (forward_demo_ledger.py)
Automated $100,000 Paper-Trading Portfolio running on 100% Free Cloud:
- Tracks all forward signals strictly following the 1-2-3-4 Paul Pro rules
- Fixed Risk: 0.75% ($750 per 1.0R) on $100k account
- Real 0.04R broker fee & slippage deduction per trade
- Strict 3-Stage Trade Management (TP1 +1.5R 50% scale-out, Lock +0.3R, Stage 2 Lock +1.5R, TP2 +3.5R)
- Zero PC dependency: 100% Cloud-native, updates every H4 candle.
"""

import os
import sys
import json
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
    with open(LEDGER_PATH, 'w', encoding='utf-8') as f:
        json.dump(ledger, f, indent=2, ensure_ascii=False)
    return ledger


def update_forward_demo_ledger(live_states):
    """
    Called every H4 cycle by telegram_notifier.py or GitHub Actions.
    1. Checks all open trades against latest H4 candle high/low.
    2. Opens new trades if overall_signal == 'ENTRY_NOW' and symbol has no open trade.
    3. Calculates floating P&L, equity, win rate, and returns.
    Returns: (updated_ledger, list_of_events)
    """
    ledger = load_ledger()
    now_iso = datetime.now(timezone.utc).isoformat()
    events = []

    open_trades = ledger.get("open_trades", [])
    closed_trades = ledger.get("closed_trades", [])
    remaining_open_trades = []

    # Map current live states by symbol
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

        if is_buy:
            # Check TP1 (+1.5R) if still in OPEN stage
            if stage == 'OPEN' and bar_high >= float(tr['tp1']):
                tr['stage'] = 'STAGE_1'
                tr['current_sl'] = float(tr['lock1'])  # Move SL to +0.3R
                tr['units_remaining'] = 0.5
                tr['tp1_hit_time'] = now_iso
                tr['realized_r_tp1'] = 1.5 * 0.5  # +0.75R realized
                events.append({
                    'type': 'TP1_HIT',
                    'symbol': sym,
                    'direction': direction,
                    'entry': entry,
                    'hit_price': float(tr['tp1']),
                    'locked_sl': float(tr['lock1']),
                    'message': f"🎯 <b>[DEMO TP1 (+1.5R)] {sym} ({direction})</b> ชนเป้าแรก! แบ่งปิด 50% ล็อกกำไร +$562.50 และเลื่อน SL -> <code>{tr['lock1']}</code> (+0.3R) กลายเป็น Risk-Free 100%!"
                })
                stage = 'STAGE_1'
                current_sl = float(tr['lock1'])

            # Check Stage 2 (+2.5R) if in STAGE_1
            if stage == 'STAGE_1' and bar_high >= float(tr['stage2']):
                tr['stage'] = 'STAGE_2'
                tr['current_sl'] = float(tr['lock2'])  # Move SL to +1.5R
                events.append({
                    'type': 'STAGE2_HIT',
                    'symbol': sym,
                    'direction': direction,
                    'entry': entry,
                    'hit_price': float(tr['stage2']),
                    'locked_sl': float(tr['lock2']),
                    'message': f"🚀 <b>[DEMO STAGE 2 (+2.5R)] {sym} ({direction})</b> ถึงจุดยก SL! เลื่อน Stop Loss ล็อกกำไรขึ้นมาที่ <code>{tr['lock2']}</code> (+1.5R)!"
                })
                stage = 'STAGE_2'
                current_sl = float(tr['lock2'])

            # Check TP2 (+3.5R) if in STAGE_1 or STAGE_2
            if stage in ('STAGE_1', 'STAGE_2') and bar_high >= float(tr['tp2']):
                trade_closed = True
                close_reason = 'TP2_HIT'
                close_price = float(tr['tp2'])
                r_remaining = 3.5 * 0.5  # +1.75R
                raw_r = tr.get('realized_r_tp1', 0.0) + r_remaining
                net_r = round(raw_r - FEE_PER_TRADE_R, 2)
                pnl_usd = round(net_r * RISK_PER_TRADE_USD, 2)

            # Check SL
            elif bar_low <= current_sl:
                trade_closed = True
                close_price = current_sl
                if stage == 'OPEN':
                    close_reason = 'SL_HIT'
                    raw_r = -1.0
                    net_r = round(raw_r - FEE_PER_TRADE_R, 2)  # -1.04R
                    pnl_usd = round(net_r * RISK_PER_TRADE_USD, 2)
                elif stage == 'STAGE_1':
                    close_reason = 'LOCK1_HIT'
                    raw_r = tr.get('realized_r_tp1', 0.0) + (0.3 * 0.5)  # +0.75 + 0.15 = +0.90R
                    net_r = round(raw_r - FEE_PER_TRADE_R, 2)
                    pnl_usd = round(net_r * RISK_PER_TRADE_USD, 2)
                elif stage == 'STAGE_2':
                    close_reason = 'LOCK2_HIT'
                    raw_r = tr.get('realized_r_tp1', 0.0) + (1.5 * 0.5)  # +0.75 + 0.75 = +1.50R
                    net_r = round(raw_r - FEE_PER_TRADE_R, 2)
                    pnl_usd = round(net_r * RISK_PER_TRADE_USD, 2)

        else:  # SELL
            # Check TP1 (+1.5R) if still in OPEN stage
            if stage == 'OPEN' and bar_low <= float(tr['tp1']):
                tr['stage'] = 'STAGE_1'
                tr['current_sl'] = float(tr['lock1'])  # Move SL to +0.3R
                tr['units_remaining'] = 0.5
                tr['tp1_hit_time'] = now_iso
                tr['realized_r_tp1'] = 1.5 * 0.5
                events.append({
                    'type': 'TP1_HIT',
                    'symbol': sym,
                    'direction': direction,
                    'entry': entry,
                    'hit_price': float(tr['tp1']),
                    'locked_sl': float(tr['lock1']),
                    'message': f"🎯 <b>[DEMO TP1 (+1.5R)] {sym} ({direction})</b> ชนเป้าแรก! แบ่งปิด 50% ล็อกกำไร +$562.50 และเลื่อน SL -> <code>{tr['lock1']}</code> (+0.3R) กลายเป็น Risk-Free 100%!"
                })
                stage = 'STAGE_1'
                current_sl = float(tr['lock1'])

            # Check Stage 2 (+2.5R) if in STAGE_1
            if stage == 'STAGE_1' and bar_low <= float(tr['stage2']):
                tr['stage'] = 'STAGE_2'
                tr['current_sl'] = float(tr['lock2'])  # Move SL to +1.5R
                events.append({
                    'type': 'STAGE2_HIT',
                    'symbol': sym,
                    'direction': direction,
                    'entry': entry,
                    'hit_price': float(tr['stage2']),
                    'locked_sl': float(tr['lock2']),
                    'message': f"🚀 <b>[DEMO STAGE 2 (+2.5R)] {sym} ({direction})</b> ถึงจุดยก SL! เลื่อน Stop Loss ล็อกกำไรลงมาที่ <code>{tr['lock2']}</code> (+1.5R)!"
                })
                stage = 'STAGE_2'
                current_sl = float(tr['lock2'])

            # Check TP2 (+3.5R) if in STAGE_1 or STAGE_2
            if stage in ('STAGE_1', 'STAGE_2') and bar_low <= float(tr['tp2']):
                trade_closed = True
                close_reason = 'TP2_HIT'
                close_price = float(tr['tp2'])
                r_remaining = 3.5 * 0.5
                raw_r = tr.get('realized_r_tp1', 0.0) + r_remaining
                net_r = round(raw_r - FEE_PER_TRADE_R, 2)
                pnl_usd = round(net_r * RISK_PER_TRADE_USD, 2)

            # Check SL
            elif bar_high >= current_sl:
                trade_closed = True
                close_price = current_sl
                if stage == 'OPEN':
                    close_reason = 'SL_HIT'
                    raw_r = -1.0
                    net_r = round(raw_r - FEE_PER_TRADE_R, 2)
                    pnl_usd = round(net_r * RISK_PER_TRADE_USD, 2)
                elif stage == 'STAGE_1':
                    close_reason = 'LOCK1_HIT'
                    raw_r = tr.get('realized_r_tp1', 0.0) + (0.3 * 0.5)
                    net_r = round(raw_r - FEE_PER_TRADE_R, 2)
                    pnl_usd = round(net_r * RISK_PER_TRADE_USD, 2)
                elif stage == 'STAGE_2':
                    close_reason = 'LOCK2_HIT'
                    raw_r = tr.get('realized_r_tp1', 0.0) + (1.5 * 0.5)
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

            outcome_txt = "กำไร 🎉" if pnl_usd > 0 else "ตัดขาดทุนตามแผน 🛡️"
            events.append({
                'type': 'TRADE_CLOSED',
                'symbol': sym,
                'direction': direction,
                'reason': close_reason,
                'pnl_usd': pnl_usd,
                'net_r': net_r,
                'message': f"🏁 <b>[DEMO ปิดออเดอร์] {sym} ({direction})</b>\n• ผลลัพธ์: <b>{outcome_txt}</b>\n• เหตุผล: <code>{close_reason}</code>\n• P&L สุทธิ: <b>{net_r:+}R ({pnl_usd:+,.2f} USD)</b>\n• พอร์ตคงเหลือ: <code>${ledger['current_balance']:,.2f}</code>"
            })
        else:
            # Mark-to-market floating P&L
            fl_r_full = ((c_now - entry) / risk_dist) if is_buy else ((entry - c_now) / risk_dist)
            if stage == 'OPEN':
                fl_r = fl_r_full
            else:
                # 50% locked from TP1 (+0.75R) + 50% floating on remaining position
                fl_r = tr.get('realized_r_tp1', 0.0) + (fl_r_full * 0.5)
            tr['current_price'] = c_now
            tr['floating_r'] = round(fl_r, 2)
            tr['floating_usd'] = round(fl_r * RISK_PER_TRADE_USD, 2)
            remaining_open_trades.append(tr)

    # -------------------------------------------------------------
    # 2. CHECK FOR NEW ENTRY_NOW SIGNALS & SYNC ACTIVE TRADES
    # -------------------------------------------------------------
    existing_open_syms = {t['symbol'] for t in remaining_open_trades}
    for s in live_states:
        sym = s['symbol']
        sig = s['overall_signal']
        tk = s['planned_ticket']
        ot = s.get('active_open_trade')

        if sym not in existing_open_syms:
            if sig == 'ENTRY_NOW':
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
                    'message': (
                        f"🟢🚨 <b>[DEMO AUTO-ENTRY] เปิดออเดอร์ใหม่!</b>\n"
                        f"• <b>คู่เงิน:</b> <b>{sym} ({tk['dir']})</b>\n"
                        f"• <b>ราคาเข้า (Entry):</b> <code>{tk['entry']}</code> | <b>ขนาด Lot:</b> <code>{tk['lots_100k']} Lots</code>\n"
                        f"• <b>Stop Loss:</b> <code>{tk['sl']}</code> (-1.0R)\n"
                        f"• <b>TP 1:</b> <code>{tk['tp1']}</code> (+1.5R ปิด 50%)\n"
                        f"• <b>TP 2:</b> <code>{tk['tp2']}</code> (+3.5R เป้าหลัก)\n"
                        f"• <i>ระบบจัดการเลื่อน SL และปิดกำไรอัตโนมัติตามกฎ 1-2-3-4</i>"
                    )
                })
            elif ot:
                # Synchronize existing active trade from live scanner engine
                stg_map = {0: 'OPEN', 1: 'STAGE_1', 2: 'STAGE_2'}
                ot_stage_num = ot.get('stage', 0)
                ot_stage_str = stg_map.get(ot_stage_num, 'OPEN')
                new_ticket_id = f"DEMO-{len(closed_trades) + len(remaining_open_trades) + 1001}"
                r_dist = abs(float(ot['entry']) - float(ot.get('initial_sl', ot['current_sl'])))
                if r_dist <= 0:
                    r_dist = abs(float(ot['entry']) - float(ot['current_sl']))
                if r_dist <= 0:
                    r_dist = 0.001

                new_trade = {
                    'ticket_id': new_ticket_id,
                    'symbol': sym,
                    'name': s.get('name', sym),
                    'dir': ot['dir'],
                    'entry_time': ot.get('entry_time', now_iso),
                    'entry': float(ot['entry']),
                    'lots': float(ot.get('lots_100k', tk.get('lots_100k', 1.0))),
                    'sl': float(ot.get('initial_sl', ot['current_sl'])),
                    'current_sl': float(ot['current_sl']),
                    'initial_sl': float(ot.get('initial_sl', ot['current_sl'])),
                    'tp1': float(ot['tp1']),
                    'lock1': float(tk.get('lock1', ot['tp1'])),
                    'stage2': float(ot['stage2']),
                    'lock2': float(tk.get('lock2', ot['stage2'])),
                    'tp2': float(ot.get('tp', tk.get('tp2', 0.0))),
                    'risk_dist': r_dist,
                    'atr_mult': float(tk.get('atr_mult', 1.0)),
                    'stage': ot_stage_str,
                    'units_remaining': 0.5 if ot_stage_num >= 1 else 1.0,
                    'current_price': float(s['latest_price']),
                    'floating_r': float(ot.get('floating_r', 0.0)),
                    'floating_usd': float(ot.get('floating_usd', 0.0))
                }
                remaining_open_trades.append(new_trade)
                existing_open_syms.add(sym)

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

    # High Water Mark & Drawdown
    if current_equity > ledger.get('high_water_mark', INITIAL_BALANCE):
        ledger['high_water_mark'] = current_equity
    hwm = ledger['high_water_mark']
    dd_pct = round(((hwm - current_equity) / hwm) * 100.0, 2) if hwm > 0 else 0.0
    if dd_pct > ledger.get('max_drawdown_pct', 0.0):
        ledger['max_drawdown_pct'] = dd_pct

    # Performance Stats
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

    # FTMO Rules Compliance
    daily_dd = round(max(0.0, (ledger['current_balance'] - current_equity) / ledger['current_balance'] * 100.0), 2)
    tot_dd = dd_pct
    ledger['ftmo_rules']['current_daily_drawdown_pct'] = daily_dd
    ledger['ftmo_rules']['current_total_drawdown_pct'] = tot_dd
    if daily_dd >= 4.5 or tot_dd >= 9.5:
        ledger['ftmo_rules']['status'] = 'WARNING_NEAR_LIMIT'
    else:
        ledger['ftmo_rules']['status'] = 'PASSING_HEALTHY'

    save_ledger(ledger)
    return ledger, events


def format_demo_portfolio_summary(ledger):
    """Formats a crystal-clear portfolio status text for Telegram & Chat."""
    bal = ledger['current_balance']
    eq = ledger['current_equity']
    pnl = ledger['net_profit_usd']
    ret = ledger['net_return_pct']
    stats = ledger['stats']
    open_tr = ledger['open_trades']
    ftmo = ledger['ftmo_rules']

    ret_icon = "🟢" if pnl >= 0 else "🔴"
    bkk_now = (datetime.now(timezone.utc) + timedelta(hours=7)).strftime('%Y-%m-%d %H:%M น.')

    lines = [
        "💼 <b>พอร์ตจำลอง Forward Demo (Paul FTMO Pro V4)</b>",
        f"🕒 เวลาไทย: <code>{bkk_now}</code>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"💰 <b>ยอดเงินคงเหลือ (Balance):</b> <code>${bal:,.2f}</code>",
        f"📊 <b>มูลค่าสุทธิ (Equity):</b> <code>${eq:,.2f}</code>",
        f"{ret_icon} <b>กำไรสุทธิรวม (P&L):</b> <b>{ret:+.2f}% (${pnl:+,.2f})</b>",
        f"🛡️ <b>Max Drawdown:</b> <code>{ledger['max_drawdown_pct']:.2f}%</code> (เกณฑ์ FTMO ห้ามเกิน 10%)",
        f"🏆 <b>สถานะกฎ FTMO:</b> <b>{'✅ ผ่านเกณฑ์ปกติ (PASSING)' if ftmo['status'] == 'PASSING_HEALTHY' else '⚠️ ระวังความเสี่ยง'}</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"📈 <b>สถิติออเดอร์ (Forward Stats):</b>",
        f"• ปิดไปแล้ว: <code>{stats['total_trades']} ไม้</code> (ชนะ {stats['winning_trades']} / แพ้ {stats['losing_trades']})",
        f"• Win Rate: <b>{stats['win_rate_pct']:.1f}%</b> | Profit Factor: <b>{stats['profit_factor']}</b>",
        f"• ผลตอบแทนสะสม: <b>{stats['total_realized_r']:+}R</b>",
        "━━━━━━━━━━━━━━━━━━━━",
    ]

    if open_tr:
        lines.append(f"⚡ <b>ออเดอร์ที่กำลังถืออยู่ ({len(open_tr)} ไม้):</b>")
        for t in open_tr:
            fl_color = "🟢" if t['floating_usd'] >= 0 else "🔴"
            lines.append(
                f"{fl_color} <b>{t['symbol']} ({t['dir']})</b> @ <code>{t['entry']}</code> ({t['lots']} Lots)\n"
                f"   ↳ P&L: <b>{t['floating_r']:+}R (${t['floating_usd']:+,.2f})</b> | ด่าน: <code>{t['stage']}</code> (SL <code>{t['current_sl']}</code>)"
            )
    else:
        lines.append("💤 <i>ขณะนี้ไม่มีออเดอร์ค้าง — ระบบอยู่ในโหมดสแตนด์บายรอสัญญาณครบ 1-2-3</i>")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("💡 <i>ระบบบันทึกและจัดการออเดอร์อัตโนมัติบน Cloud 100% ไม่ต้องเปิดคอม</i>")
    return "\n".join(lines)
