import urllib.request
import urllib.parse
import json
import os
import re
import sys
import datetime

# Fix Windows console UTF-8 output
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Expanded Master Contracts: Majors, Emerging Markets, Precious Metals, Crypto
ASSET_CONFIG = [
    # 8 Major G8 Currencies
    {"code": "USD", "name": "US Dollar Index", "contract": "USD INDEX", "flag": "🇺🇸", "category": "Major FX"},
    {"code": "EUR", "name": "Euro FX", "contract": "EURO FX", "flag": "🇪🇺", "category": "Major FX"},
    {"code": "JPY", "name": "Japanese Yen", "contract": "JAPANESE YEN", "flag": "🇯🇵", "category": "Major FX"},
    {"code": "GBP", "name": "British Pound", "contract": "BRITISH POUND", "flag": "🇬🇧", "category": "Major FX"},
    {"code": "AUD", "name": "Australian Dollar", "contract": "AUSTRALIAN DOLLAR", "flag": "🇦🇺", "category": "Major FX"},
    {"code": "CAD", "name": "Canadian Dollar", "contract": "CANADIAN DOLLAR", "flag": "🇨🇦", "category": "Major FX"},
    {"code": "CHF", "name": "Swiss Franc", "contract": "SWISS FRANC", "flag": "🇨🇭", "category": "Major FX"},
    {"code": "NZD", "name": "New Zealand Dollar", "contract": "NZ DOLLAR", "flag": "🇳🇿", "category": "Major FX"},

    # Emerging Market Currencies
    {"code": "MXN", "name": "Mexican Peso", "contract": "MEXICAN PESO", "flag": "🇲🇽", "category": "Emerging FX"},
    {"code": "BRL", "name": "Brazilian Real", "contract": "BRAZILIAN REAL", "flag": "🇧🇷", "category": "Emerging FX"},
    {"code": "ZAR", "name": "South African Rand", "contract": "SO AFRICAN RAND", "flag": "🇿🇦", "category": "Emerging FX"},

    # Precious Metals (Extremely popular in FTMO / Prop Trading)
    {"code": "XAU", "name": "Gold Futures", "contract": "GOLD", "flag": "🥇", "category": "Commodities"},
    {"code": "XAG", "name": "Silver Futures", "contract": "SILVER", "flag": "🥈", "category": "Commodities"},

    # Crypto Futures
    {"code": "BTC", "name": "Bitcoin CME", "contract": "BITCOIN", "flag": "₿", "category": "Crypto"},
    {"code": "ETH", "name": "Ether Cash Settled", "contract": "ETHER CASH SETTLED", "flag": "Ξ", "category": "Crypto"}
]


def fetch_cot_data():
    base_url = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
    contracts_clause = " or ".join([f"contract_market_name='{c['contract']}'" for c in ASSET_CONFIG])
    where_clause = f"({contracts_clause})"

    params = {
        "$where": where_clause,
        "$select": (
            "report_date_as_yyyy_mm_dd,contract_market_name,market_and_exchange_names,"
            "cftc_contract_market_code,commodity_group_name,"
            "noncomm_positions_long_all,noncomm_positions_short_all,noncomm_postions_spread_all,"
            "comm_positions_long_all,comm_positions_short_all,"
            "nonrept_positions_long_all,nonrept_positions_short_all,"
            "change_in_noncomm_long_all,change_in_noncomm_short_all,"
            "change_in_comm_long_all,change_in_comm_short_all,"
            "change_in_open_interest_all,open_interest_all"
        ),
        "$order": "report_date_as_yyyy_mm_dd DESC",
        "$limit": 1650
    }

    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    print(f"[*] Querying CFTC Socrata API for {len(ASSET_CONFIG)} total assets (52+ weeks history)...")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

    with urllib.request.urlopen(req, timeout=25) as resp:
        raw_data = json.loads(resp.read().decode('utf-8'))

    print(f"[+] Successfully retrieved {len(raw_data)} raw records across multiple asset classes.")
    return raw_data


def process_data(raw_data):
    all_dates = sorted(list(set(r['report_date_as_yyyy_mm_dd'][:10] for r in raw_data if r.get('report_date_as_yyyy_mm_dd'))), reverse=True)
    recent_dates_52 = all_dates[:53]

    asset_map = {c['contract']: c for c in ASSET_CONFIG}

    records = {}
    for r in raw_data:
        contract = r.get('contract_market_name')
        if contract not in asset_map:
            continue
        d_raw = r.get('report_date_as_yyyy_mm_dd')
        if not d_raw:
            continue
        d = d_raw[:10]

        cfg = asset_map[contract]
        code = cfg['code']

        long_pos = int(float(r.get('noncomm_positions_long_all', 0) or 0))
        short_pos = int(float(r.get('noncomm_positions_short_all', 0) or 0))
        spread_pos = int(float(r.get('noncomm_postions_spread_all', 0) or 0))
        comm_long = int(float(r.get('comm_positions_long_all', 0) or 0))
        comm_short = int(float(r.get('comm_positions_short_all', 0) or 0))
        nonrept_long = int(float(r.get('nonrept_positions_long_all', 0) or 0))
        nonrept_short = int(float(r.get('nonrept_positions_short_all', 0) or 0))
        oi = int(float(r.get('open_interest_all', 0) or 0))

        chg_noncomm_l = int(float(r.get('change_in_noncomm_long_all', 0) or 0))
        chg_noncomm_s = int(float(r.get('change_in_noncomm_short_all', 0) or 0))
        chg_comm_l = int(float(r.get('change_in_comm_long_all', 0) or 0))
        chg_comm_s = int(float(r.get('change_in_comm_short_all', 0) or 0))
        chg_oi = int(float(r.get('change_in_open_interest_all', 0) or 0))

        net_pos = long_pos - short_pos
        comm_net = comm_long - comm_short
        nonrept_net = nonrept_long - nonrept_short

        if code not in records:
            records[code] = {
                "info": cfg,
                "raw_market_name": r.get('market_and_exchange_names'),
                "cftc_code": r.get('cftc_contract_market_code'),
                "commodity_group": r.get('commodity_group_name'),
                "history": {}
            }
        records[code]["history"][d] = {
            "date": d,
            "open_interest": oi,
            "change_open_interest": chg_oi,
            "noncomm_long": long_pos,
            "noncomm_short": short_pos,
            "noncomm_spread": spread_pos,
            "noncomm_net": net_pos,
            "change_noncomm_long": chg_noncomm_l,
            "change_noncomm_short": chg_noncomm_s,
            "comm_long": comm_long,
            "comm_short": comm_short,
            "comm_net": comm_net,
            "change_comm_long": chg_comm_l,
            "change_comm_short": chg_comm_s,
            "nonrept_long": nonrept_long,
            "nonrept_short": nonrept_short,
            "nonrept_net": nonrept_net
        }

    global_latest_date = all_dates[0] if all_dates else ""

    summary_list = []
    cot_indices = {}

    for code, data in records.items():
        hist = data["history"]
        asset_dates = sorted(hist.keys(), reverse=True)
        if not asset_dates:
            continue

        a_latest = asset_dates[0]
        a_prev = asset_dates[1] if len(asset_dates) > 1 else a_latest

        latest_rec = hist.get(a_latest, {})
        prev_rec = hist.get(a_prev, {})

        curr_net = latest_rec.get("noncomm_net", 0)
        prev_net = prev_rec.get("noncomm_net", 0)
        chg_week = curr_net - prev_net
        chg_long = latest_rec.get("change_noncomm_long", 0)
        chg_short = latest_rec.get("change_noncomm_short", 0)

        # Compute exact 52-week COT Index
        nets_all = [hist[d]["noncomm_net"] for d in asset_dates]
        nets_52 = nets_all[:52]
        min52 = min(nets_52) if nets_52 else curr_net
        max52 = max(nets_52) if nets_52 else curr_net
        idx52 = round(((curr_net - min52) / (max52 - min52)) * 100.0, 1) if max52 != min52 else 50.0

        min3y = min(nets_all) if nets_all else curr_net
        max3y = max(nets_all) if nets_all else curr_net
        idx3y = round(((curr_net - min3y) / (max3y - min3y)) * 100.0, 1) if max3y != min3y else 50.0

        contract_name = data["info"]["contract"]
        cot_indices[contract_name] = {
            "net": curr_net,
            "min52": min52,
            "max52": max52,
            "idx52": idx52,
            "min3y": min3y,
            "max3y": max3y,
            "idx3y": idx3y,
            "weeks": len(nets_all)
        }

        bias = "BULLISH" if curr_net > 0 else "BEARISH"
        intensity = "STRONG" if abs(curr_net) > 50000 else "MODERATE" if abs(curr_net) > 20000 else "NEUTRAL"

        if curr_net > 0 and chg_long < -3000:
            flow = "PROFIT-TAKING (สถาบันเริ่มรินปิดทำกำไร)"
            tactical_state = "PULLBACK RISK"
        elif curr_net > 0 and chg_week > 0:
            flow = "ACCUMULATING LONG (สถาบันเร่งซื้อสะสม)"
            tactical_state = "TREND CONTINUATION"
        elif curr_net < 0 and chg_short < -3000:
            flow = "SHORT-COVERING (สถาบันปิดชอร์ตทำกำไร)"
            tactical_state = "RALLY RISK"
        elif curr_net < 0 and chg_week < 0:
            flow = "ACCUMULATING SHORT (สถาบันเทขายเพิ่ม)"
            tactical_state = "DOWNSIDE PRESSURE"
        else:
            flow = "NEUTRAL FLOW (สถาบันดูเชิง)"
            tactical_state = "RANGING"

        # 52-week series (12 months chronological) for trend chart
        series = []
        for d in reversed(asset_dates[:52]):
            series.append({
                "date": d,
                "net": hist[d]["noncomm_net"],
                "long": hist[d]["noncomm_long"],
                "short": hist[d]["noncomm_short"]
            })

        # Calculate 52-week (12-month) historical progression for all 3 groups + rolling COT Index
        weekly_changes_52w = []
        max_rows = min(52, len(asset_dates) - 1)
        for i in range(max_rows):
            curr_d = asset_dates[i]
            prev_d = asset_dates[i + 1]
            c_rec = hist.get(curr_d, {})
            p_rec = hist.get(prev_d, {})
            if c_rec and p_rec:
                nc_net = c_rec.get("noncomm_net", 0)
                nc_chg = nc_net - p_rec.get("noncomm_net", 0)
                comm_net = c_rec.get("comm_net", 0)
                comm_chg = comm_net - p_rec.get("comm_net", 0)
                nr_net = c_rec.get("nonrept_net", 0)
                nr_chg = nr_net - p_rec.get("nonrept_net", 0)

                window_slice = nets_all[i:i + 52]
                w_min = min(window_slice) if window_slice else nc_net
                w_max = max(window_slice) if window_slice else nc_net
                w_idx = round(((nc_net - w_min) / (w_max - w_min)) * 100.0, 1) if w_max != w_min else 50.0

                weekly_changes_52w.append({
                    "date": curr_d,
                    "noncomm_net": nc_net,
                    "noncomm_chg": nc_chg,
                    "comm_net": comm_net,
                    "comm_chg": comm_chg,
                    "nonrept_net": nr_net,
                    "nonrept_chg": nr_chg,
                    "cot_idx": w_idx
                })

        summary_list.append({
            "code": code,
            "name": data["info"]["name"],
            "flag": data["info"]["flag"],
            "contract": contract_name,
            "category": data["info"]["category"],
            "market_name": data["raw_market_name"],
            "cftc_code": data["cftc_code"],
            "commodity_group": data["commodity_group"],
            "latest_date": a_latest,
            "net_position": curr_net,
            "prev_net_position": prev_net,
            "weekly_change": chg_week,
            "change_noncomm_long": chg_long,
            "change_noncomm_short": chg_short,
            "min_52w": min52,
            "max_52w": max52,
            "cot_index_52w": idx52,
            "cot_index_3y": idx3y,
            "bias": bias,
            "intensity": intensity,
            "flow": flow,
            "tactical_state": tactical_state,
            "latest_long": latest_rec.get("noncomm_long", 0),
            "latest_short": latest_rec.get("noncomm_short", 0),
            "open_interest": latest_rec.get("open_interest", 0),
            "raw_record": latest_rec,
            "prev_raw_record": prev_rec,
            "series": series,
            "weekly_changes_4w": weekly_changes_52w[:4],
            "weekly_changes_52w": weekly_changes_52w
        })

    summary_list.sort(key=lambda x: x["net_position"], reverse=True)
    for idx, item in enumerate(summary_list):
        item["rank"] = idx + 1

    setups = generate_paul_trade_setups(summary_list)

    pub_at = ""
    iso_week = 0
    if global_latest_date:
        dt_obj = datetime.datetime.strptime(global_latest_date, "%Y-%m-%d")
        pub_at = (dt_obj + datetime.timedelta(days=3)).strftime("%Y-%m-%d")
        iso_week = dt_obj.isocalendar()[1]

    output = {
        "metadata": {
            "title": "CFTC COT Institutional Money Flow Matrix (Paul FTMO Pro Edition)",
            "source": "U.S. Commodity Futures Trading Commission (CFTC) - Legacy Futures Only",
            "cftc_api_endpoint": "https://publicreporting.cftc.gov/resource/6dca-aqww.json",
            "cftc_web_url": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
            "report_date": global_latest_date,
            "iso_week": iso_week,
            "published_at": pub_at,
            "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "weeks_tracked": recent_dates_52,
            "total_assets_tracked": len(summary_list)
        },
        "cot_indices": cot_indices,
        "currencies": summary_list,
        "trade_setups": setups
    }

    return output


def generate_paul_trade_setups(all_assets):
    setups = []
    curr_dict = {c["code"]: c for c in all_assets}

    # 1. SPECIAL ASSET: GOLD (XAU/USD) - PAUL'S EXACT PLAYBOOK (4-GATE ALIGNED)
    gold = curr_dict.get("XAU")
    usd = curr_dict.get("USD")
    if gold and usd:
        g_net = gold["net_position"]
        g_chg_long = gold["change_noncomm_long"]
        g_comm_net = gold["raw_record"].get("comm_net", 0)
        g_nonrept_net = gold["raw_record"].get("nonrept_net", 0)
        g_idx52 = gold.get("cot_index_52w", 50.0)
        g_wk_chg = gold.get("weekly_changes_52w", [{}])[0].get("noncomm_chg", gold.get("weekly_change", 0))
        idx_zone_txt = (
            "Neutral Zone สมดุล 35%–65%" if 35 <= g_idx52 <= 65
            else ("Extreme Bullish >65%" if g_idx52 > 65 else "Low / Unwinding Zone <35%")
        )

        if g_chg_long < -3000 or g_wk_chg < 0:
            rec = "⚠️ พักดูเชิง / สัญญาณขัดแย้ง (STAND ASIDE / CONFLICT)"
            phase = "INSTITUTIONAL UNWINDING & CONFLICT (ชะลอตัว / รอจังหวะคอนเฟิร์ม)"
            badge_color = "amber"
            rationale = (
                f"⚠️ แจ้งเตือนความขัดแย้งตามระบบ Paul 4-Gate: สถาบันมียอดสะสม Net Long ({g_net:+,d} สัญญา) "
                f"แต่สัปดาห์ล่าสุดสถาบันได้ 'เทขายลดพอร์ตออกไป {g_wk_chg:+,d} สัญญา' "
                f"และดัชนี COT 52W Index อยู่ที่ระดับ {g_idx52}% ({idx_zone_txt}) "
                f"ขณะที่ต้องรอโครงสร้างราคา H4 ยืนยันทิศทางชัดเจน "
                f"กฎเหล็กของ Paul: 'ห้ามเปิด BUY สวนเทรนด์ขาลง และห้ามไล่ราคาโดยไม่รอ 3-Bar BOS ผ่านครบทั้ง 4 ด่าน'"
            )
            confidence = "STAND ASIDE (Wait for Confirmation)"
            paul_rule = "งดเปิด BUY สวนเทรนด์ขาลง! รอราคายืนยัน BOS และผ่านครบ 4 ด่านก่อนพิจารณา"
        elif g_net > 0:
            rec = "🟢 โฟกัสหน้า BUY : 🎯 ย่อซื้อตามเทรนด์ (BUY ON DIPS)"
            phase = "TREND CONTINUATION (ขาขึ้นแข็งแกร่ง)"
            badge_color = "green"
            confidence = "HIGH (Paul's Confluent)"
            rationale = f"สถาบันกำลังเติมเงิน Long อย่างต่อเนื่อง ({g_wk_chg:+,d} สัญญา, COT Index {g_idx52}%) โฟกัสเปิดหน้า BUY เมื่อราคาย่อตัวแตะ EMA50"
            paul_rule = "รอราคาย่อแตะ EMA50 + ยืนยัน 3-Bar BOS ก่อนเปิดออเดอร์"
        else:
            rec = "⚪ เป็นกลาง (NEUTRAL)"
            phase = "NO BIAS (ยังไม่มีทิศทาง)"
            badge_color = "gray"
            confidence = "MODERATE"
            rationale = "สถาบันยังไม่มีทิศทางที่ชัดเจน"
            paul_rule = "หลีกเลี่ยง หรือรอสัญญาณ 4 ด่านครบถ้วน"

        setups.append({
            "pair": "XAU/USD (Gold)",
            "base": "XAU",
            "quote": "USD",
            "macro_bias": "NEUTRAL / CONFLICT (Macro Caution)" if badge_color == "amber" else ("BULLISH" if g_net > 0 else "NEUTRAL"),
            "recommendation": rec,
            "phase": phase,
            "badge_color": badge_color,
            "confidence": confidence,
            "net_diff": g_net,
            "cot_index_52w": g_idx52,
            "noncomm_net": g_net,
            "comm_net": g_comm_net,
            "nonrept_net": g_nonrept_net,
            "noncomm_chg": g_wk_chg,
            "comm_chg": gold.get("weekly_changes_52w", [{}])[0].get("comm_chg", 0),
            "nonrept_chg": gold.get("weekly_changes_52w", [{}])[0].get("nonrept_chg", 0),
            "weekly_changes_4w": gold.get("weekly_changes_4w", []),
            "weekly_changes_52w": gold.get("weekly_changes_52w", []),
            "quote_weekly_changes_52w": usd.get("weekly_changes_52w", []),
            "rationale": rationale,
            "paul_rule": paul_rule,
            "base_flag": "🥇",
            "quote_flag": "🇺🇸"
        })

    # 2. FOREX PAIRS
    pair_candidates = [
        ("EUR", "JPY"), ("AUD", "JPY"), ("GBP", "JPY"),
        ("EUR", "USD"), ("AUD", "USD"), ("NZD", "USD"),
        ("USD", "CAD"), ("USD", "CHF")
    ]

    for base, quote in pair_candidates:
        if base not in curr_dict or quote not in curr_dict:
            continue
        b = curr_dict[base]
        q = curr_dict[quote]
        b_net = b["net_position"]
        q_net = q["net_position"]
        net_diff = b_net - q_net

        b_comm_net = b["raw_record"].get("comm_net", 0)
        b_nonrept_net = b["raw_record"].get("nonrept_net", 0)
        q_comm_net = q["raw_record"].get("comm_net", 0)
        q_nonrept_net = q["raw_record"].get("nonrept_net", 0)

        b_chg = b["weekly_change"]
        q_chg = q["weekly_change"]
        flow_velocity = b_chg - q_chg

        if b_net < 0 and q_net > 0:
            if b_chg > 10000 and flow_velocity > 5000:
                rec = "⛔ งดเข้าเทรด / หลีกเลี่ยง (BASE SHORT SQUEEZE)"
                phase = "SHORT-COVERING PULLBACK"
                badge_color = "amber"
                rationale = (
                    f"แม้ภาพรวม {base} จะ Net Short ({b_net:+,d}) แต่สัปดาห์นี้สถาบันได้ปิด Short หนีตายใน {base} ถึง {b_chg:+,d} สัญญา "
                    f"ราคากำลังดีดตัวขึ้นแรง กฎของ Paul: 'หลีกเลี่ยงการเปิด Sell ในช่วงที่ตัวหน้ากำลังเกิด Short Squeeze'"
                )
                confidence = "LOW (High Squeeze Risk)"
                paul_rule = "งดเปิดสถานะ! รอจนกว่าการปิด Short ของตัวหน้าจะจบลงและเกิด Rejection ที่แนวต้านใหญ่"
            elif b["change_noncomm_short"] > 0 or flow_velocity <= 0:
                rec = "🔴 โฟกัสหน้า SELL : ⏳ รอเด้งชนแนวต้าน (SELL ON RALLIES)"
                phase = "DOWNSIDE EXPANSION (ขาลงได้เปรียบ)"
                badge_color = "red"
                rationale = (
                    f"ภาพรวม {base} สถาบัน Net Short หนาแน่น ({b_net:+,d}) สวนทางกับ {quote} ที่สถาบัน Net Long ({q_net:+,d}) "
                    f"เม็ดเงินสถาบันหนุนทิศทางขาลงชัดเจน กฎของ Paul: 'มองหน้า SELL แน่นอน แต่ให้รอราคาเด้งขึ้นไปทดสอบแนวต้านก่อน แล้วค่อยกด Sell'"
                )
                confidence = "HIGH (Confluent 100%)"
                paul_rule = "หาจังหวะ Sell เมื่อราคาเด้งขึ้นมาแตะ EMA50 + ยืนยัน 3-Bar Bearish BOS"
            else:
                rec = "🔴 โฟกัสหน้า SELL : ⏳ รอราคาพักฐาน (WAIT FOR RETRACEMENT)"
                phase = "SHORT-COVERING PULLBACK"
                badge_color = "amber"
                rationale = f"{base} สถาบันยัง Net Short แต่เริ่มมีการปิดทำกำไรบางส่วน ให้รอราคาเด้งขึ้นไปชนแนวต้านก่อน"
                confidence = "MODERATE"
                paul_rule = "รอราคากระตุกขึ้นทดสอบแนวต้านแล้วดูสัญญาณหมดแรง"

        elif b_net > 0 and q_net < 0:
            if q_chg > 10000 and flow_velocity < -5000:
                rec = "⛔ งดเข้าเทรด / หลีกเลี่ยง (QUOTE SHORT SQUEEZE)"
                phase = "AGGRESSIVE SELLOFF (เงินตัวหลังกระชากขึ้น)"
                badge_color = "amber"
                rationale = (
                    f"⚠️ สภาวะเงินปะทะกัน: แม้ภาพรวม {base} จะ Net Long ({b_net:+,d}) และ {quote} จะ Net Short ({q_net:+,d}) "
                    f"แต่ในสัปดาห์นี้สถาบันได้ปิด Short และอัดเงินเข้า {quote} ถึง {q_chg:+,d} สัญญา ซึ่งแรงกว่า {base} ({b_chg:+,d})! "
                    f"ทำให้ค่าเงิน {quote} แข็งค่ากระชาก กฎของ Paul: 'หลีกเลี่ยงการเทรดคู่ที่เงินกำลังปะทะกันรุนแรง'"
                )
                confidence = "DANGER (Short Squeeze In Progress)"
                paul_rule = "งดเข้าเทรดคู่นี้! ปล่อยให้แรงซื้อคืนของตัวหลังหมดก่อน"
            elif flow_velocity > 0:
                rec = "🟢 โฟกัสหน้า BUY : ⏳ รอย่อแตะแนวรับ (BUY ON DIPS)"
                phase = "UPSIDE EXPANSION (ขาขึ้นได้เปรียบ)"
                badge_color = "green"
                rationale = (
                    f"ภาพรวม {base} สถาบัน Net Long ({b_net:+,d}) สวนทางกับ {quote} ที่ Net Short ({q_net:+,d}) "
                    f"เม็ดเงินสถาบันหนุนทิศทางขาขึ้น กฎของ Paul: 'มองหน้า BUY แน่นอน แต่ให้รอราคาย่อตัวลงมาแตะแนวรับก่อน แล้วค่อยกด Buy'"
                )
                confidence = "HIGH (Confluent 100%)"
                paul_rule = "รอราคาย่อตัวลงมาแตะ EMA50 + ยืนยัน 3-Bar Bullish BOS แล้วค่อย Buy"
            else:
                rec = "🟢 โฟกัสหน้า BUY : ⏳ รอจังหวะย่อตัว (WAIT FOR PULLBACK)"
                phase = "MOMENTUM CHOP (กำลังสะสมพลัง)"
                badge_color = "amber"
                rationale = f"โมเมนตัมของทั้งสองฝั่งยังสูสีกัน แม้เทรนด์ใหญ่จะได้เปรียบแต่ต้องรอการย่อตัวที่ชัดเจน"
                confidence = "MODERATE"
                paul_rule = "รอสัญญาณ Price Action กลับตัวที่แนวรับ"
        else:
            rec = "⚪ พักดูเชิง / ไม่ชัดเจน (HOLD / CAUTION)"
            phase = "MIXED FLOW"
            badge_color = "gray"
            rationale = f"ทั้งสองสกุลเงินมีทิศทางสถาบันที่ยังไม่ขัดแย้งกันอย่างรุนแรง ควรหลีกเลี่ยง"
            confidence = "MODERATE"
            paul_rule = "หลีกเลี่ยง หรือรอโครงสร้าง 4 ด่านครบถ้วน"

        b_wk0 = b.get("weekly_changes_52w", [{}])[0] if b.get("weekly_changes_52w") else {}
        q_wk0 = q.get("weekly_changes_52w", [{}])[0] if q.get("weekly_changes_52w") else {}

        setups.append({
            "pair": f"{base}/{quote}",
            "base": base,
            "quote": quote,
            "macro_bias": "BEARISH" if "SELL" in rec else "BULLISH" if "BUY" in rec else "NEUTRAL",
            "recommendation": rec,
            "phase": phase,
            "badge_color": badge_color,
            "confidence": confidence,
            "net_diff": net_diff,
            "base_cot_idx": b.get("cot_index_52w", 50.0),
            "quote_cot_idx": q.get("cot_index_52w", 50.0),
            "noncomm_net": b_net,
            "comm_net": b_comm_net,
            "nonrept_net": b_nonrept_net,
            "noncomm_chg": b_wk0.get("noncomm_chg", 0),
            "comm_chg": b_wk0.get("comm_chg", 0),
            "nonrept_chg": b_wk0.get("nonrept_chg", 0),
            "base_noncomm_net": b_net,
            "base_comm_net": b_comm_net,
            "base_nonrept_net": b_nonrept_net,
            "base_noncomm_chg": b_wk0.get("noncomm_chg", 0),
            "base_comm_chg": b_wk0.get("comm_chg", 0),
            "base_nonrept_chg": b_wk0.get("nonrept_chg", 0),
            "quote_noncomm_net": q_net,
            "quote_comm_net": q_comm_net,
            "quote_nonrept_net": q_nonrept_net,
            "quote_noncomm_chg": q_wk0.get("noncomm_chg", 0),
            "quote_comm_chg": q_wk0.get("comm_chg", 0),
            "quote_nonrept_chg": q_wk0.get("nonrept_chg", 0),
            "base_weekly_changes_4w": b.get("weekly_changes_4w", []),
            "quote_weekly_changes_4w": q.get("weekly_changes_4w", []),
            "base_weekly_changes_52w": b.get("weekly_changes_52w", []),
            "quote_weekly_changes_52w": q.get("weekly_changes_52w", []),
            "rationale": rationale,
            "paul_rule": paul_rule,
            "base_flag": b["flag"],
            "quote_flag": q["flag"]
        })

    return setups


def sync_embedded_html(target_dir, processed):
    html_path = os.path.join(target_dir, "cot_legacy_report.html")
    if not os.path.exists(html_path):
        return
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    indices_json = json.dumps(processed.get("cot_indices", {}), ensure_ascii=False)
    embedded_json = json.dumps(processed, indent=2, ensure_ascii=False)

    html_new = re.sub(
        r"window\.COT_INDICES\s*=\s*\{.*?\};",
        lambda _: f"window.COT_INDICES = {indices_json};",
        html,
        count=1,
        flags=re.DOTALL
    )

    marker_start = "const EMBEDDED_COT_DATA = "
    marker_end = "\n    let cotData = EMBEDDED_COT_DATA;"
    s_idx = html_new.find(marker_start)
    e_idx = html_new.find(marker_end)
    if s_idx != -1 and e_idx != -1 and e_idx > s_idx:
        html_new = html_new[:s_idx] + marker_start + embedded_json + ";" + html_new[e_idx:]

    if html_new != html:
        with open(html_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(html_new)
        print(f"[+] Updated embedded snapshot inside: {html_path}")


def main():
    target_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(target_dir, exist_ok=True)

    raw = fetch_cot_data()
    processed = process_data(raw)

    out_path = os.path.join(target_dir, "cot_data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(processed, f, indent=2, ensure_ascii=False)

    indices_path = os.path.join(target_dir, "cot_indices_all.json")
    with open(indices_path, "w", encoding="utf-8") as f:
        json.dump(processed.get("cot_indices", {}), f, indent=2, ensure_ascii=False)

    js_path = os.path.join(target_dir, "cot_data.js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("// CFTC COT Institutional Data (Paul FTMO Pro Edition - 52-Week History)\n")
        f.write("window.COT_INDICES = " + json.dumps(processed.get("cot_indices", {}), ensure_ascii=False) + ";\n")
        f.write("window.COT_DATA = " + json.dumps(processed, indent=2, ensure_ascii=False) + ";\n")

    sync_embedded_html(target_dir, processed)
    print(f"\n[+] Successfully generated 52-Week COT Data & embedded HTML at: {out_path}")


if __name__ == "__main__":
    main()
