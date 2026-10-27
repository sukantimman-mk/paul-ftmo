/**
 * Paul Pro V4 - 24/7 Serverless Telegram Webhook for Vercel / Cloudflare / Node
 * Handles chat commands like /update, /radar, /scan, /gold, /ticket directly in Telegram.
 * Runs 100% FREE in the cloud while PC is completely turned off.
 */

const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || "";
const GITHUB_USER = "sukantimman-mk";
const REPO_NAME = "paul-ftmo";
const GITHUB_TOKEN = process.env.GITHUB_TOKEN || "";

async function sendTelegram(chatId, textHtml, replyMarkup = null) {
  const url = `https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`;
  const body = {
    chat_id: chatId,
    text: textHtml,
    parse_mode: "HTML",
    disable_web_page_preview: true
  };
  if (replyMarkup) body.reply_markup = replyMarkup;

  await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
}

async function getLiveScannerData() {
  const url = `https://raw.githubusercontent.com/${GITHUB_USER}/${REPO_NAME}/main/forward_live_scanner.json?t=${Date.now()}`;
  const res = await fetch(url, { headers: { "Cache-Control": "no-cache" } });
  return await res.json();
}

async function triggerGitHubCloudScan() {
  if (!GITHUB_TOKEN) return false;
  const url = `https://api.github.com/repos/${GITHUB_USER}/${REPO_NAME}/actions/workflows/paul_h4_scanner.yml/dispatches`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Authorization": `token ${GITHUB_TOKEN}`,
      "Accept": "application/vnd.github.v3+json",
      "User-Agent": "PaulFTMOBot/4.0",
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ ref: "main", inputs: { force_mode: "true" } })
  });
  return res.status === 204;
}

function formatRadarSummary(liveStates) {
  const bkkNow = new Date().toLocaleString("th-TH", { timeZone: "Asia/Bangkok" });
  let lines = [
    `📡 <b>เรดาร์สแกนสด 6 คู่เงิน (Paul Pro V4 | 1-2-3-4)</b>`,
    `🕒 เวลาไทย: <code>${bkkNow}</code>`,
    `━━━━━━━━━━━━━━━━━━━━`
  ];

  liveStates.forEach(s => {
    const g = s.gates;
    const tk = s.planned_ticket;
    const ot = s.active_open_trade;
    let icon = "🔵";
    let statusTxt = `แผน <b>${s.planned_dir}</b> | ราคา <code>${s.latest_price}</code> | รอย่อแตะ EMA50 (<code>${s.ema50}</code>)`;

    if (s.overall_signal === "ENTRY_NOW") {
      icon = "🟢🚨";
      statusTxt = `<b>สั่งเข้า ${s.planned_dir} ทันที!</b> @ <code>${s.latest_price}</code> (SL <code>${tk.sl}</code> | TP1 <code>${tk.tp1}</code> | <code>${tk.lots_100k} Lot</code>)`;
    } else if (s.overall_signal === "SETUP_ARMED") {
      icon = "⏳⚡";
      statusTxt = `<b>ย่อแตะ EMA50 แล้ว!</b> รอเบรก ${s.planned_dir} @ <code>${tk.entry}</code> (SL <code>${tk.sl}</code> | <code>${tk.lots_100k} Lot</code>)`;
    }

    const gLights = `[1:${g.g1_pass ? "🟢" : "🔴"} 2:${g.g2_pass ? "🟢" : "⏳"} 3:${g.g3_pass ? "🟢" : "⏳"}]`;
    lines.push(`${icon} <b>${s.symbol}</b> ${gLights}\n   ↳ ${statusTxt}`);

    if (ot) {
      lines.push(
        `   ⚡ <i>ถือออเดอร์ ${ot.dir} อยู่: เข้า <code>${ot.entry_price}</code> | P&L <b>${ot.floating_r >= 0 ? "+" : ""}${ot.floating_r}R</b> | ด่าน ${ot.stage}</i>`
      );
    }
  });

  lines.push("━━━━━━━━━━━━━━━━━━━━");
  lines.push(`💡 <i>พิมพ์ /scan เพื่อสั่งดึงแท่งเทียนสดเดี๋ยวนี้ | พิมพ์ /gold เพื่อดูใบสั่งเทรดทอง</i>`);
  return lines.join("\n");
}

function formatSinglePairTicket(s) {
  const tk = s.planned_ticket;
  const g = s.gates;
  return [
    `🎯 <b>ใบสั่งเทรดสด: ${s.symbol} (${s.name})</b>`,
    `🕯️ แท่ง H4: <code>${s.last_bar_utc}</code>`,
    `━━━━━━━━━━━━━━━━━━━━`,
    `• <b>สถานะ:</b> ${s.overall_badge}`,
    `• <b>ด่าน 1 (Trend+COT):</b> ${g.g1_pass ? "🟢" : "🔴"} ${g.g1_text}`,
    `• <b>ด่าน 2 (Pullback):</b> ${g.g2_pass ? "🟢" : "⏳"} ${g.g2_text}`,
    `• <b>ด่าน 3 (3-Bar BOS):</b> ${g.g3_pass ? "🟢" : "⏳"} ${g.g3_text}`,
    `━━━━━━━━━━━━━━━━━━━━`,
    `📋 <b>พารามิเตอร์สำหรับตั้งไม้ (พอร์ต $100k | Risk 0.75% = $750):</b>`,
    `• <b>ฝั่ง (Direction):</b> <b>${tk.dir}</b>`,
    `• <b>ขนาด Lot Size:</b> <code>${tk.lots_100k} Lots</code>`,
    `• <b>ราคาเข้า (Entry / BOS):</b> <code>${tk.entry}</code>`,
    `• <b>Stop Loss (-1.0R):</b> <code>${tk.sl}</code>`,
    `• <b>TP 1 (+1.5R ปิด 50%):</b> <code>${tk.tp1}</code> <i>(เลื่อน SL -> ${tk.lock1})</i>`,
    `• <b>Stage 2 (+2.5R):</b> <code>${tk.stage2}</code> <i>(เลื่อน SL -> ${tk.lock2})</i>`,
    `• <b>TP 2 (+3.5R เป้าหลัก):</b> <code>${tk.tp2}</code>`
  ].join("\n");
}

module.exports = async (req, res) => {
  if (req.method !== "POST") {
    return res.status(200).send("Paul Pro V4 Telegram Webhook is active!");
  }

  const update = req.body;
  const msg = update?.message || update?.edited_message;
  if (!msg || !msg.text) {
    return res.status(200).send("OK");
  }

  const chatId = msg.chat.id;
  const text = msg.text.trim().toLowerCase();

  try {
    if (text === "/start" || text === "/help" || text === "สวัสดี" || text === "เมนู") {
      const welcomeText = [
        `🤖 <b>สวัสดีครับคุณ ${msg.chat.first_name || "Superman"}!</b>`,
        `ระบบพร้อมรับคำสั่งสดในแชทตลอด 24 ชั่วโมง (ปิดคอมได้ 100%):`,
        ``,
        `📌 <b>คำสั่งที่พิมพ์ได้ทันที:</b>`,
        `• <code>/update</code> หรือ <code>ขออัพเดทตอนนี้</code> ➔ สรุปเรดาร์ 6 คู่เงินสด`,
        `• <code>/scan</code> ➔ สั่งให้ Cloud ปลุกขึ้นมาสแกนกราฟสดเดี๋ยวนี้`,
        `• <code>/gold</code> ➔ ดูใบสั่งเทรดทองคำ (Entry / SL / TP / Lot)`,
        `• <code>/jpy</code>, <code>/cad</code>, <code>/chf</code>, <code>/gbp</code>, <code>/eur</code> ➔ ดูโพยคู่เงินนั้นๆ`
      ].join("\n");

      const keyboard = {
        keyboard: [
          [{ text: "📡 ขออัพเดทเรดาร์สดตอนนี้" }, { text: "🥇 โพยเทรดทองคำ (GC=F)" }],
          [{ text: "🇯🇵 USDJPY" }, { text: "🇨🇦 USDCAD" }, { text: "🇨🇭 USDCHF" }],
          [{ text: "🇬🇧 GBPUSD" }, { text: "🇪🇺 EURUSD" }, { text: "🔄 สั่งสแกนสด Cloud" }]
        ],
        resize_keyboard: true
      };
      await sendTelegram(chatId, welcomeText, keyboard);
    }
    else if (text.includes("update") || text.includes("อัพเดท") || text.includes("เรดาร์") || text === "/radar") {
      const liveData = await getLiveScannerData();
      await sendTelegram(chatId, formatRadarSummary(liveData));
    }
    else if (text.includes("scan") || text.includes("สแกน") || text === "/refresh") {
      await sendTelegram(chatId, "⏳ <b>กำลังส่งคำสั่งปลุกเซิร์ฟเวอร์คลาวด์บน GitHub...</b>\nระบบกำลังดึงแท่งเทียน H4 สดเดี๋ยวนี้ ข้อความสรุปเรดาร์จะส่งมาใน ~25 วินาทีครับ!");
      await triggerGitHubCloudScan();
    }
    else if (text.includes("gold") || text.includes("ทอง") || text.includes("xau")) {
      const liveData = await getLiveScannerData();
      const gold = liveData.find(s => s.symbol === "GC=F");
      if (gold) await sendTelegram(chatId, formatSinglePairTicket(gold));
    }
    else if (text.includes("jpy")) {
      const liveData = await getLiveScannerData();
      const pair = liveData.find(s => s.symbol.includes("JPY"));
      if (pair) await sendTelegram(chatId, formatSinglePairTicket(pair));
    }
    else if (text.includes("cad")) {
      const liveData = await getLiveScannerData();
      const pair = liveData.find(s => s.symbol.includes("CAD"));
      if (pair) await sendTelegram(chatId, formatSinglePairTicket(pair));
    }
    else if (text.includes("chf")) {
      const liveData = await getLiveScannerData();
      const pair = liveData.find(s => s.symbol.includes("CHF"));
      if (pair) await sendTelegram(chatId, formatSinglePairTicket(pair));
    }
    else if (text.includes("gbp")) {
      const liveData = await getLiveScannerData();
      const pair = liveData.find(s => s.symbol.includes("GBP"));
      if (pair) await sendTelegram(chatId, formatSinglePairTicket(pair));
    }
    else if (text.includes("eur")) {
      const liveData = await getLiveScannerData();
      const pair = liveData.find(s => s.symbol.includes("EUR"));
      if (pair) await sendTelegram(chatId, formatSinglePairTicket(pair));
    }
    else {
      const liveData = await getLiveScannerData();
      await sendTelegram(chatId, formatRadarSummary(liveData));
    }
  } catch (err) {
    await sendTelegram(chatId, `⚠️ เกิดข้อผิดพลาด: ${err.message}`);
  }

  return res.status(200).send("OK");
};
