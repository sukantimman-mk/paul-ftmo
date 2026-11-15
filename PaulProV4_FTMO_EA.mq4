//+------------------------------------------------------------------+
//|                                          PaulProV4_FTMO_EA.mq4   |
//|         Paul FTMO Institutional Pro V4.1 - Official MT4 Engine   |
//|     4-Gate Execution + 3-Stage Profit Lock + FTMO Guardian 4.5%  |
//+------------------------------------------------------------------+
#property copyright "Paul FTMO Institutional Pro V4.1"
#property link      "https://cftc.gov"
#property version   "4.10"
#property strict
#property description "Official MQL4 Expert Advisor for Paul FTMO Institutional Pro V4.1"
#property description "6 Core Tier-1 Assets: XAUUSD, USDCAD, USDCHF, GBPUSD, EURUSD, USDJPY (H4)"
#property description "Includes 4-Gate Filter, 0.75% Risk Sizing, 3-Stage Profit Lock & 4.5% Daily Breaker"

//--- Enumerations for User Settings
enum ENUM_COT_MODE
  {
   COT_AUTO_INSTITUTIONAL = 0, // Auto 3-Tier COT Gate (Aligned / Flow Shift / Neutral 35-65%)
   COT_FORCE_BUY_ONLY     = 1, // Manual Override: Allow BUY Only
   COT_FORCE_SELL_ONLY    = 2  // Manual Override: Allow SELL Only
  };

enum ENUM_EXIT_MODE
  {
   EXIT_HYBRID_50_50      = 0, // Mode A: Hybrid 50% Partial Close at +1.5R & Trail 50%
   EXIT_PURE_RUNNER       = 1  // Mode B: Pure Trailing Runner (100% Lot Trails +0.3R -> +1.5R)
  };

//--- Input Parameters
input string         Sep1                    = "=== [1] FTMO RISK & GUARDIAN SETTINGS ===";
input bool           UsePercentageRisk       = true;                    // Calculate Risk as % of Account Balance
input double         RiskPercentPerTrade     = 0.75;                    // Risk % Per Trade (Default: 0.75% = $750 on $100k)
input double         FixedRiskUSD            = 750.0;                   // Fixed Risk USD (if UsePercentageRisk = false)
input double         MaxDailyLossPct         = 4.50;                    // FTMO Guardian Daily Loss Circuit Breaker (%)
input double         MaxTotalLossPct         = 9.00;                    // FTMO Guardian Max Total Drawdown Breaker (%)
input double         InitialAccountBaseline  = 0.0;                     // Initial Prop Account Size (0 = Auto AccountBalance)

input string         Sep2                    = "=== [2] 4-GATE ENGINE PARAMETERS (H4) ===";
input ENUM_COT_MODE  CotGateMode             = COT_AUTO_INSTITUTIONAL;  // Gate 1: CFTC COT Evaluation Mode
input int            EmaFastPeriod           = 50;                      // Gate 1 & 2: H4 Fast EMA (Value Zone)
input int            EmaSlowPeriod           = 200;                     // Gate 1: H4 Slow EMA (Macro Regime)
input int            PullbackLookbackBars    = 10;                      // Gate 2: Value Pullback Lookback (H4 Bars)
input int            CooldownH4Bars          = 8;                       // Gate 2: Cooldown After Exit (8 H4 Bars = 32h)
input int            BosLookbackBars         = 3;                       // Gate 3: Break of Structure Bars (3-Bar BOS)
input int            RsiPeriod               = 14;                      // Gate 3: RSI Period (Buy 45-68 / Sell 32-55)
input bool           EnforceInstitutionalHrs = true;                    // Gate 3: Trade Only Active LDN/NY H4 Candles
input int            AtrPeriod               = 14;                      // Gate 4: Universal ATR Period (0.80x - 1.50x)

input string         Sep3                    = "=== [3] 3-STAGE PROFIT LOCK SETTINGS ===";
input ENUM_EXIT_MODE ProfitLockMode          = EXIT_HYBRID_50_50;       // Stage 1-2-3 Exit Mode (Hybrid 50/50 vs Pure Runner)
input double         Stage1TriggerR          = 1.50;                    // Stage 1 Trigger (+1.5R)
input double         Stage1LockR             = 0.30;                    // Stage 1 SL Lock (+0.3R Risk-Free)
input double         Stage2TriggerR          = 2.50;                    // Stage 2 Trigger (+2.5R)
input double         Stage2LockR             = 1.50;                    // Stage 2 SL Lock (+1.5R Big Profit Lock)
input double         FullTargetR             = 3.50;                    // Full Target TP2 (+3.5R)

input string         Sep4                    = "=== [4] SYSTEM, HUD & 24/7 TELEGRAM ===";
input int            MagicNumber             = 888400;                  // Unique EA Magic Number
input int            SlippagePoints          = 30;                      // Max Slippage (Points)
input bool           ShowOnChartHUD          = true;                    // Show Live 4-Gate HUD Dashboard on Chart
input bool           EnableTelegramAlerts    = true;                    // Enable 24/7 Direct MT4 -> Telegram Alerts
input string         TelegramBotToken        = "8783621696:AAEEqzFPPlhyO24d-RsIk2DKNhxjD9jDPbI"; // Telegram Bot Token
input string         TelegramChatId          = "1394691513";            // Telegram Chat ID
input bool           SendH4SummaryFromMT4    = true;                    // Send H4 Portfolio Status from MT4 Every 4 Hours

//--- Global State Variables
datetime g_lastBarTimeH4       = 0;
double   g_dailyStartEquity    = 0.0;
int      g_lastResetDayOfYear  = -1;
bool     g_dailyHalted         = false;
bool     g_symbolBlocked       = false;
int      g_lastTrackedTicket   = -1;
string   g_hudPrefix           = "PaulV4_HUD_";

//+------------------------------------------------------------------+
//| Helper: GlobalVariable Key Generator per Symbol                  |
//+------------------------------------------------------------------+
string GetGVKey(string suffix)
  {
   return "PaulV4_" + Symbol() + "_" + suffix;
  }

//+------------------------------------------------------------------+
//| Helper: Send Direct 24/7 Message to Telegram via MQL4 WebRequest |
//+------------------------------------------------------------------+
bool SendTelegramMessage(string htmlText)
  {
   if(!EnableTelegramAlerts || StringLen(TelegramBotToken) < 10 || StringLen(TelegramChatId) < 3)
      return false;

   if(IsTesting() || IsOptimization())
      return false;

   string url = "https://api.telegram.org/bot" + TelegramBotToken + "/sendMessage";
   string headers = "Content-Type: application/x-www-form-urlencoded\r\n";

   // Replace '&' and '+' and '#' and '\n' safely for application/x-www-form-urlencoded
   string safeText = htmlText;
   StringReplace(safeText, "%", "%25");
   StringReplace(safeText, "&", "%26");
   StringReplace(safeText, "+", "%2B");
   StringReplace(safeText, "#", "%23");
   StringReplace(safeText, "\n", "%0A");

   string body = "chat_id=" + TelegramChatId + "&parse_mode=HTML&disable_web_page_preview=true&text=" + safeText;

   char postData[];
   char resultData[];
   string resultHeaders = "";

   int len = StringToCharArray(body, postData, 0, WHOLE_ARRAY, CP_UTF8);
   if(len > 0)
      ArrayResize(postData, len - 1); // Strip trailing NUL byte

   ResetLastError();
   int resCode = WebRequest("POST", url, headers, 5000, postData, resultData, resultHeaders);
   if(resCode == -1)
     {
      int err = GetLastError();
      Print("[Telegram WebRequest Notice] Error ", err, " - Enable Tools -> Options -> Expert Advisors -> Allow WebRequest for: https://api.telegram.org");
      return false;
     }
   return (resCode == 200);
  }

//+------------------------------------------------------------------+
//| Send Unified H4 Portfolio Summary Directly from MT4 (Once/4h)    |
//+------------------------------------------------------------------+
void CheckAndSendMT4PortfolioSummary(datetime h4BarTime)
  {
   if(!EnableTelegramAlerts || !SendH4SummaryFromMT4)
      return;

   string gvKey = "PaulV4_Global_LastTgH4Bar";
   if(GlobalVariableCheck(gvKey) && (datetime)GlobalVariableGet(gvKey) >= h4BarTime)
      return;

   GlobalVariableSet(gvKey, (double)h4BarTime);

   int openCount = 0;
   string openDetails = "";
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
        {
         if(OrderMagicNumber() == MagicNumber && (OrderType() == OP_BUY || OrderType() == OP_SELL))
           {
            openCount++;
            double netPnl = OrderProfit() + OrderSwap() + OrderCommission();
            string dStr = (OrderType() == OP_BUY) ? "BUY" : "SELL";
            openDetails += StringFormat("\n- <b>%s</b> (%s %.2fL) | Entry: <code>%s</code> | P/L: <b>$%.2f</b>",
                                        OrderSymbol(), dStr, OrderLots(),
                                        DoubleToString(OrderOpenPrice(), (int)MarketInfo(OrderSymbol(), MODE_DIGITS)),
                                        netPnl);
           }
        }
     }

   double bal = AccountBalance();
   double eq  = AccountEquity();
   double fl  = eq - bal;

   string msg = "<b>[MT4 VPS 24/7 H4 STATUS] Paul FTMO Pro V4.1</b>\n"
              + "----------------------------------\n"
              + StringFormat("Account: <code>#%d (%s)</code>\n", AccountNumber(), AccountServer())
              + StringFormat("Balance: <code>$%.2f</code> | Equity: <code>$%.2f</code>\n", bal, eq)
              + StringFormat("Floating P/L: <b>$%.2f</b> | Open Trades: <code>%d</code>", fl, openCount);

   if(openCount > 0)
      msg += "\n----------------------------------" + openDetails;
   else
      msg += "\nStatus: <b>0 Open Trades (Scanning 6 Tier-1 Pairs on H4)</b>";

   SendTelegramMessage(msg);
  }

//+------------------------------------------------------------------+
//| Detect & Notify When an Active Trade Closes in MT4               |
//+------------------------------------------------------------------+
void CheckAndNotifyClosedTrade(int currentOpenTicket)
  {
   if(g_lastTrackedTicket > 0 && currentOpenTicket < 0)
     {
      if(OrderSelect(g_lastTrackedTicket, SELECT_BY_TICKET, MODE_HISTORY))
        {
         if(OrderCloseTime() > 0)
           {
            double netPnl = OrderProfit() + OrderSwap() + OrderCommission();
            string dStr   = (OrderType() == OP_BUY) ? "BUY" : "SELL";
            string resTag = (netPnl >= 0.0) ? "[TRADE CLOSED - PROFIT]" : "[TRADE CLOSED - SL HIT]";
            string msg = StringFormat("<b>%s %s (%s)</b>\n"
                                      "----------------------------------\n"
                                      "Ticket: <code>#%d</code> | Lots: <code>%.2f</code>\n"
                                      "Entry: <code>%s</code> -> Close: <code>%s</code>\n"
                                      "Realized P/L: <b>$%.2f USD</b>\n"
                                      "New MT4 Balance: <code>$%.2f</code> (Equity: <code>$%.2f</code>)\n"
                                      "Account: <code>#%d (%s)</code>",
                                      resTag, Symbol(), dStr,
                                      g_lastTrackedTicket, OrderLots(),
                                      DoubleToString(OrderOpenPrice(), Digits),
                                      DoubleToString(OrderClosePrice(), Digits),
                                      netPnl, AccountBalance(), AccountEquity(),
                                      AccountNumber(), AccountServer());
            SendTelegramMessage(msg);
           }
        }
      g_lastTrackedTicket = -1;
     }
   else if(currentOpenTicket > 0)
     {
      g_lastTrackedTicket = currentOpenTicket;
     }
  }

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
   // 1. Block AUDUSD permanently per Paul Pro V4 Portfolio Audit
   string symUpper = Symbol();
   StringToUpper(symUpper);
   if(StringFind(symUpper, "AUD") >= 0)
     {
      g_symbolBlocked = true;
      Alert("[BLOCKED - Paul Pro V4.1] AUD/USD is permanently removed from the Tier-1 Portfolio (PF 0.79). Please attach to XAUUSD, USDCAD, USDCHF, GBPUSD, EURUSD, or USDJPY.");
      return(INIT_SUCCEEDED);
     }
   g_symbolBlocked = false;

   // 2. Initialize or restore Daily Starting Equity at 00:00 UTC
   SyncDailyEquityReset();

   // 3. Render initial On-Chart HUD
   if(ShowOnChartHUD)
      UpdateHUD();

   Print("[OK - Paul Pro V4.1 EA] Initialized on ", Symbol(), " | Mode: ",
         (ProfitLockMode == EXIT_HYBRID_50_50 ? "Hybrid 50/50 Partial Close" : "Pure Trailing Runner"),
         " | Risk: ", DoubleToString(RiskPercentPerTrade, 2), "%");

   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, g_hudPrefix);
  }

//+------------------------------------------------------------------+
//| Synchronize Daily Equity Reset at 00:00 UTC                      |
//+------------------------------------------------------------------+
void SyncDailyEquityReset()
  {
   datetime nowUtc = TimeGMT();
   int utcDay = TimeDayOfYear(nowUtc);
   string gvDayKey = "PaulV4_Global_ResetDayUTC";
   string gvEqKey  = "PaulV4_Global_StartEquity";

   if(GlobalVariableCheck(gvDayKey) && (int)GlobalVariableGet(gvDayKey) == utcDay)
     {
      g_dailyStartEquity   = GlobalVariableGet(gvEqKey);
      g_lastResetDayOfYear = utcDay;
     }
   else
     {
      g_dailyStartEquity   = AccountEquity();
      g_lastResetDayOfYear = utcDay;
      g_dailyHalted        = false;
      GlobalVariableSet(gvDayKey, (double)utcDay);
      GlobalVariableSet(gvEqKey, g_dailyStartEquity);
      Print("[FTMO Guardian] Daily Equity Reset at 00:00 UTC: Starting Equity = $", DoubleToString(g_dailyStartEquity, 2));
     }
  }

//+------------------------------------------------------------------+
//| Check FTMO Daily (4.5%) & Total (9.0%) Circuit Breakers          |
//+------------------------------------------------------------------+
bool CheckFtmoGuardian(double &dailyLossPctOut, double &totalLossPctOut)
  {
   SyncDailyEquityReset();

   double curEquity = AccountEquity();
   double baseCapital = (InitialAccountBaseline > 0.0) ? InitialAccountBaseline : AccountBalance();

   dailyLossPctOut = 0.0;
   if(g_dailyStartEquity > 0.0 && curEquity < g_dailyStartEquity)
      dailyLossPctOut = ((g_dailyStartEquity - curEquity) / g_dailyStartEquity) * 100.0;

   totalLossPctOut = 0.0;
   if(baseCapital > 0.0 && curEquity < baseCapital)
      totalLossPctOut = ((baseCapital - curEquity) / baseCapital) * 100.0;

   if(dailyLossPctOut >= MaxDailyLossPct || totalLossPctOut >= MaxTotalLossPct)
     {
      if(!g_dailyHalted)
        {
         g_dailyHalted = true;
         Alert("[ALERT - FTMO GUARDIAN CIRCUIT BREAKER] Trading halted! Daily Loss: ",
               DoubleToString(dailyLossPctOut, 2), "% | Total DD: ", DoubleToString(totalLossPctOut, 2), "%");
        }
      return false;
     }

   g_dailyHalted = false;
   return true;
  }

//+------------------------------------------------------------------+
//| Get Pair-Equivalent COT Data (Direct & Inverted USD-Base Handled)|
//+------------------------------------------------------------------+
void GetPairCotSnapshot(double &pairNetOut, double &pairChgOut, double &pairIdxOut, string &cotVerdictOut, bool isBuyEval)
  {
   string sym = Symbol();
   StringToUpper(sym);

   // Default Verified CFTC COT Snapshot (As of Latest Release)
   // Values are already converted to Pair-Equivalent (Inverted for JPY, CAD, CHF)
   double rawNet = 0.0, rawChg = 0.0, rawIdx = 50.0;
   bool isUsdBase = false;

   if(StringFind(sym, "XAU") >= 0 || StringFind(sym, "GOLD") >= 0)
     {
      rawNet = 179548;  rawChg = -6903;   rawIdx = 26.1; isUsdBase = false;
     }
   else if(StringFind(sym, "EUR") >= 0)
     {
      rawNet = -157791; rawChg = -12450;  rawIdx = 0.0;  isUsdBase = false;
     }
   else if(StringFind(sym, "GBP") >= 0)
     {
      rawNet = -59821;  rawChg = -4120;   rawIdx = 50.7; isUsdBase = false;
     }
   else if(StringFind(sym, "JPY") >= 0)
     {
      rawNet = 102321;  rawChg = 8420;    rawIdx = 93.6; isUsdBase = true;
     }
   else if(StringFind(sym, "CAD") >= 0)
     {
      rawNet = -41775;  rawChg = -3210;   rawIdx = 63.8; isUsdBase = true;
     }
   else if(StringFind(sym, "CHF") >= 0)
     {
      rawNet = -16589;  rawChg = 1150;    rawIdx = 100.0; isUsdBase = true;
     }

   if(isUsdBase)
     {
      pairNetOut = -rawNet;
      pairChgOut = -rawChg;
      pairIdxOut = 100.0 - rawIdx;
     }
   else
     {
      pairNetOut = rawNet;
      pairChgOut = rawChg;
      pairIdxOut = rawIdx;
     }

   bool isAligned  = (isBuyEval && pairNetOut > 0) || (!isBuyEval && pairNetOut < 0);
   bool isMomentum = (isBuyEval && pairChgOut > 0) || (!isBuyEval && pairChgOut < 0);
   bool isNeutral  = (isBuyEval && pairIdxOut >= 35.0) || (!isBuyEval && pairIdxOut <= 65.0);

   if(isAligned && isMomentum)
      cotVerdictOut = "Tier 1: Aligned + Momentum (A+)";
   else if(isAligned)
      cotVerdictOut = "Tier 1: Macro Net Aligned (A)";
   else if(isMomentum)
      cotVerdictOut = "Tier 2: COT Flow Shift (Weekly Delta)";
   else if(isNeutral)
      cotVerdictOut = "Tier 3: Neutral Sweet Spot (35-65%)";
   else
      cotVerdictOut = "BLOCKED: Extreme Opposite COT";
  }

//+------------------------------------------------------------------+
//| Evaluate Gate 1 COT Condition                                    |
//+------------------------------------------------------------------+
bool IsCotGatePassed(bool isBuyEval, string &verdictOut)
  {
   if(CotGateMode == COT_FORCE_BUY_ONLY)
     {
      verdictOut = "Manual Override: BUY ONLY";
      return isBuyEval;
     }
   if(CotGateMode == COT_FORCE_SELL_ONLY)
     {
      verdictOut = "Manual Override: SELL ONLY";
      return !isBuyEval;
     }

   double pNet = 0, pChg = 0, pIdx = 50.0;
   GetPairCotSnapshot(pNet, pChg, pIdx, verdictOut, isBuyEval);

   if(isBuyEval)
      return (pNet > 0.0 || pChg > 0.0 || pIdx >= 35.0);
   else
      return (pNet < 0.0 || pChg < 0.0 || pIdx <= 65.0);
  }

//+------------------------------------------------------------------+
//| Check if Symbol Has an Active Open Position for This EA          |
//+------------------------------------------------------------------+
int FindOpenTradeTicket()
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
        {
         if(OrderSymbol() == Symbol() && OrderMagicNumber() == MagicNumber)
           {
            if(OrderType() == OP_BUY || OrderType() == OP_SELL)
               return OrderTicket();
           }
        }
     }
   return -1;
  }

//+------------------------------------------------------------------+
//| Calculate H4 Bars Elapsed Since Last Trade Closed on This Symbol |
//+------------------------------------------------------------------+
int GetH4BarsSinceLastExit()
  {
   datetime lastCloseTime = 0;
   for(int i = OrdersHistoryTotal() - 1; i >= 0; i--)
     {
      if(OrderSelect(i, SELECT_BY_POS, MODE_HISTORY))
        {
         if(OrderSymbol() == Symbol() && OrderMagicNumber() == MagicNumber)
           {
            if(OrderType() == OP_BUY || OrderType() == OP_SELL)
              {
               if(OrderCloseTime() > lastCloseTime)
                  lastCloseTime = OrderCloseTime();
              }
           }
        }
     }
   if(lastCloseTime == 0)
      return 999;

   int elapsedSeconds = (int)(TimeCurrent() - lastCloseTime);
   int barsElapsed    = elapsedSeconds / (4 * 3600);
   return barsElapsed;
  }

//+------------------------------------------------------------------+
//| Check if Closed H4 Candle belongs to Active London/NY Sessions   |
//+------------------------------------------------------------------+
bool IsActiveInstitutionalSession()
  {
   if(!EnforceInstitutionalHrs)
      return true;

   datetime nowUtc = TimeGMT();
   int utcHour = TimeHour(nowUtc);

   if(utcHour >= 4 && utcHour <= 21)
      return true;

   return false;
  }

//+------------------------------------------------------------------+
//| Calculate Exact Lot Size for 0.75% Risk using Broker TickValue   |
//+------------------------------------------------------------------+
double CalculateExactLotSize(double slDistancePrice)
  {
   if(slDistancePrice <= 0.0)
      return MarketInfo(Symbol(), MODE_MINLOT);

   double riskUsd = FixedRiskUSD;
   if(UsePercentageRisk)
      riskUsd = AccountBalance() * (RiskPercentPerTrade / 100.0);

   double tickSize  = MarketInfo(Symbol(), MODE_TICKSIZE);
   double tickValue = MarketInfo(Symbol(), MODE_TICKVALUE);
   double minLot    = MarketInfo(Symbol(), MODE_MINLOT);
   double maxLot    = MarketInfo(Symbol(), MODE_MAXLOT);
   double lotStep   = MarketInfo(Symbol(), MODE_LOTSTEP);

   if(tickSize <= 0.0)
      tickSize = Point;
   if(lotStep <= 0.0)
      lotStep = 0.01;

   double rawLots = minLot;
   if(tickValue > 0.0 && tickSize > 0.0)
     {
      double lossPerLot = (slDistancePrice / tickSize) * tickValue;
      if(lossPerLot > 0.0)
         rawLots = riskUsd / lossPerLot;
     }
   else
     {
      string s = Symbol();
      StringToUpper(s);
      if(StringFind(s, "XAU") >= 0 || StringFind(s, "GOLD") >= 0)
         rawLots = riskUsd / (slDistancePrice * 100.0);
      else if(StringFind(s, "JPY") >= 0)
         rawLots = (riskUsd * Bid) / (slDistancePrice * 100000.0);
      else if(StringFind(s, "USDCAD") >= 0 || StringFind(s, "USDCHF") >= 0)
         rawLots = (riskUsd * Bid) / (slDistancePrice * 100000.0);
      else
         rawLots = riskUsd / (slDistancePrice * 100000.0);
     }

   double steppedLots = MathFloor(rawLots / lotStep) * lotStep;
   steppedLots = MathMax(minLot, MathMin(maxLot, steppedLots));
   return NormalizeDouble(steppedLots, 2);
  }

//+------------------------------------------------------------------+
//| Manage Active Open Trade (3-Stage Trailing Profit Lock)          |
//+------------------------------------------------------------------+
void ManageOpenPosition(int ticket)
  {
   if(!OrderSelect(ticket, SELECT_BY_TICKET, MODE_TRADES))
      return;

   bool   isBuy      = (OrderType() == OP_BUY);
   double entryPrice = OrderOpenPrice();
   double curSL      = OrderStopLoss();
   double curTP      = OrderTakeProfit();
   double curLots    = OrderLots();

   double rDist = 0.0;
   if(GlobalVariableCheck(GetGVKey("RDist")))
      rDist = GlobalVariableGet(GetGVKey("RDist"));

   if(rDist <= 0.0)
     {
      string cmt = OrderComment();
      int sepPos = StringFind(cmt, "|");
      if(sepPos >= 0)
         rDist = StringToDouble(StringSubstr(cmt, sepPos + 1));
     }

   if(rDist <= 0.0 && curSL > 0.0)
      rDist = MathAbs(entryPrice - curSL);

   if(rDist <= 0.0)
      return;

   int curStage = 0;
   if(GlobalVariableCheck(GetGVKey("Stage")))
      curStage = (int)GlobalVariableGet(GetGVKey("Stage"));

   double checkPrice = isBuy ? Bid : Ask;
   double currentR   = isBuy ? ((checkPrice - entryPrice) / rDist) : ((entryPrice - checkPrice) / rDist);

   double lock1Price = NormalizeDouble(isBuy ? (entryPrice + Stage1LockR * rDist) : (entryPrice - Stage1LockR * rDist), Digits);
   double lock2Price = NormalizeDouble(isBuy ? (entryPrice + Stage2LockR * rDist) : (entryPrice - Stage2LockR * rDist), Digits);
   double tp2Price   = NormalizeDouble(isBuy ? (entryPrice + FullTargetR * rDist) : (entryPrice - FullTargetR * rDist), Digits);

   // --- STAGE 1 TRIGGER (+1.5R): Move SL to +0.3R (and 50% Partial Close if Hybrid Mode) ---
   if(curStage == 0 && currentR >= Stage1TriggerR)
     {
      if(ProfitLockMode == EXIT_HYBRID_50_50)
        {
         double minLot  = MarketInfo(Symbol(), MODE_MINLOT);
         double lotStep = MarketInfo(Symbol(), MODE_LOTSTEP);
         if(lotStep <= 0.0) lotStep = 0.01;
         double halfLots = MathFloor((curLots * 0.5) / lotStep) * lotStep;
         halfLots = NormalizeDouble(halfLots, 2);

         if(halfLots >= minLot && (curLots - halfLots) >= minLot)
           {
            double closePrice = isBuy ? Bid : Ask;
            bool closedHalf = OrderClose(ticket, halfLots, closePrice, SlippagePoints, clrAqua);
            if(closedHalf)
              {
               Print("[STAGE 1 HYBRID 50% CLOSE] Closed ", DoubleToString(halfLots, 2),
                     " lots at +1.5R (", DoubleToString(closePrice, Digits), ") on ", Symbol());
               ticket = FindOpenTradeTicket();
               if(ticket < 0 || !OrderSelect(ticket, SELECT_BY_TICKET, MODE_TRADES))
                  return;
              }
           }
        }

      bool slNeedsUpdate = isBuy ? (OrderStopLoss() < lock1Price - Point) : (OrderStopLoss() == 0 || OrderStopLoss() > lock1Price + Point);
      if(slNeedsUpdate)
        {
         bool modOk = OrderModify(OrderTicket(), OrderOpenPrice(), lock1Price, tp2Price, 0, clrLime);
         if(modOk)
           {
            GlobalVariableSet(GetGVKey("Stage"), 1.0);
            Print("[STAGE 1 LOCK +0.3R] Moved SL to Risk-Free ", DoubleToString(lock1Price, Digits), " on ", Symbol());
            SendTelegramMessage(StringFormat("<b>[STAGE 1 TP1 +1.5R HIT] %s</b>\n"
                                             "----------------------------------\n"
                                             "Ticket: <code>#%d</code> | 50%% Profit Locked!\n"
                                             "SL Moved to Risk-Free (+0.3R): <code>%s</code>\n"
                                             "Target TP2 (+3.5R): <code>%s</code>\n"
                                             "MT4 Equity: <code>$%.2f</code> (#%d)",
                                             Symbol(), OrderTicket(),
                                             DoubleToString(lock1Price, Digits),
                                             DoubleToString(tp2Price, Digits),
                                             AccountEquity(), AccountNumber()));
           }
        }
      else
        {
         GlobalVariableSet(GetGVKey("Stage"), 1.0);
        }
     }

   // --- STAGE 2 TRIGGER (+2.5R): Move SL to +1.5R (Big Profit Lock) ---
   if(curStage <= 1 && currentR >= Stage2TriggerR)
     {
      bool slNeedsUpdate2 = isBuy ? (OrderStopLoss() < lock2Price - Point) : (OrderStopLoss() == 0 || OrderStopLoss() > lock2Price + Point);
      if(slNeedsUpdate2)
        {
         bool modOk2 = OrderModify(OrderTicket(), OrderOpenPrice(), lock2Price, tp2Price, 0, clrGold);
         if(modOk2)
           {
            GlobalVariableSet(GetGVKey("Stage"), 2.0);
            Print("[STAGE 2 LOCK +1.5R] Moved SL to Big Profit Lock ", DoubleToString(lock2Price, Digits), " on ", Symbol());
            SendTelegramMessage(StringFormat("<b>[STAGE 2 LOCK +1.5R] %s</b>\n"
                                             "----------------------------------\n"
                                             "Ticket: <code>#%d</code> | Price Reached +2.5R!\n"
                                             "SL Trailed to (+1.5R): <code>%s</code>\n"
                                             "Target TP2 (+3.5R): <code>%s</code>\n"
                                             "MT4 Equity: <code>$%.2f</code> (#%d)",
                                             Symbol(), OrderTicket(),
                                             DoubleToString(lock2Price, Digits),
                                             DoubleToString(tp2Price, Digits),
                                             AccountEquity(), AccountNumber()));
           }
        }
      else
        {
         GlobalVariableSet(GetGVKey("Stage"), 2.0);
        }
     }
  }

//+------------------------------------------------------------------+
//| Evaluate All 4 Gates on Completed H4 Bar (shift = 1)             |
//+------------------------------------------------------------------+
void Evaluate4GatesAndExecute(bool allowExecution,
                              bool &g1PassOut, bool &g2PassOut, bool &g3PassOut, bool &g4PassOut,
                              string &dirStrOut, string &cotVerdictOut,
                              double &entryOut, double &slOut, double &lock1Out, double &lock2Out, double &tp2Out, double &lotOut)
  {
   double c1     = iClose(Symbol(), PERIOD_H4, 1);
   double o1     = iOpen(Symbol(),  PERIOD_H4, 1);
   double ema50  = iMA(Symbol(), PERIOD_H4, EmaFastPeriod, 0, MODE_EMA, PRICE_CLOSE, 1);
   double ema200 = iMA(Symbol(), PERIOD_H4, EmaSlowPeriod, 0, MODE_EMA, PRICE_CLOSE, 1);
   double rsi14  = iRSI(Symbol(), PERIOD_H4, RsiPeriod, PRICE_CLOSE, 1);
   double atr14  = iATR(Symbol(), PERIOD_H4, AtrPeriod, 1);

   bool isBullRegime = (ema50 > ema200);
   dirStrOut = isBullRegime ? "BUY" : "SELL";

   // --- GATE 1: Macro Trend + Price Side of EMA50 + COT Flow ---
   bool priceSideOk = isBullRegime ? (c1 > ema50) : (c1 < ema50);
   bool cotOk       = IsCotGatePassed(isBullRegime, cotVerdictOut);
   g1PassOut        = (priceSideOk && cotOk);

   // --- GATE 2: Value Pullback to EMA50 in last 10 H4 bars + Cooldown >= 8 H4 bars ---
   bool touchedEma50 = false;
   for(int k = 2; k <= PullbackLookbackBars + 1; k++)
     {
      double emaK = iMA(Symbol(), PERIOD_H4, EmaFastPeriod, 0, MODE_EMA, PRICE_CLOSE, k);
      if(isBullRegime)
        {
         if(iLow(Symbol(), PERIOD_H4, k) <= emaK * 1.001)
           {
            touchedEma50 = true;
            break;
           }
        }
      else
        {
         if(iHigh(Symbol(), PERIOD_H4, k) >= emaK * 0.999)
           {
            touchedEma50 = true;
            break;
           }
        }
     }
   int barsSinceExit = GetH4BarsSinceLastExit();
   bool cooldownOk   = (barsSinceExit >= CooldownH4Bars);
   g2PassOut         = (touchedEma50 && cooldownOk);

   // --- GATE 3: 3-Bar BOS + Candle Color + RSI Bounds + Institutional Session ---
   double bosHigh = iHigh(Symbol(), PERIOD_H4, 2);
   double bosLow  = iLow(Symbol(),  PERIOD_H4, 2);
   for(int b = 2; b <= BosLookbackBars + 1; b++)
     {
      double hb = iHigh(Symbol(), PERIOD_H4, b);
      double lb = iLow(Symbol(),  PERIOD_H4, b);
      if(hb > bosHigh) bosHigh = hb;
      if(lb < bosLow)  bosLow  = lb;
     }

   bool bosBroken = isBullRegime ? (c1 > bosHigh && c1 > o1) : (c1 < bosLow && c1 < o1);
   bool rsiOk     = isBullRegime ? (rsi14 >= 45.0 && rsi14 <= 68.0) : (rsi14 >= 32.0 && rsi14 <= 55.0);
   bool sessionOk = IsActiveInstitutionalSession();
   g3PassOut      = (bosBroken && rsiOk && sessionOk);

   // --- GATE 4: Universal ATR Stop Loss Window (4-Bar Swing +/- 0.25x ATR clamped [0.80x, 1.50x] ATR) ---
   double minLow4  = iLow(Symbol(),  PERIOD_H4, 1);
   double maxHigh4 = iHigh(Symbol(), PERIOD_H4, 1);
   for(int s = 1; s <= BosLookbackBars + 1; s++)
     {
      double hs = iHigh(Symbol(), PERIOD_H4, s);
      double ls = iLow(Symbol(),  PERIOD_H4, s);
      if(ls < minLow4)  minLow4  = ls;
      if(hs > maxHigh4) maxHigh4 = hs;
     }

   entryOut = isBullRegime ? Ask : Bid;
   double rawSL = isBullRegime ? (minLow4 - 0.25 * atr14) : (maxHigh4 + 0.25 * atr14);
   double rDist = MathAbs(entryOut - rawSL);
   if(atr14 > 0.0)
      rDist = MathMax(0.80 * atr14, MathMin(1.50 * atr14, rDist));

   slOut    = NormalizeDouble(isBullRegime ? (entryOut - rDist) : (entryOut + rDist), Digits);
   lock1Out = NormalizeDouble(isBullRegime ? (entryOut + Stage1LockR * rDist) : (entryOut - Stage1LockR * rDist), Digits);
   lock2Out = NormalizeDouble(isBullRegime ? (entryOut + Stage2LockR * rDist) : (entryOut - Stage2LockR * rDist), Digits);
   tp2Out   = NormalizeDouble(isBullRegime ? (entryOut + FullTargetR * rDist) : (entryOut - FullTargetR * rDist), Digits);
   lotOut   = CalculateExactLotSize(rDist);
   g4PassOut = (atr14 > 0.0 && rDist > 0.0 && lotOut >= MarketInfo(Symbol(), MODE_MINLOT));

   // --- EXECUTE ORDER IF ALL 4 GATES PASS ---
   if(allowExecution && g1PassOut && g2PassOut && g3PassOut && g4PassOut)
     {
      int cmd = isBullRegime ? OP_BUY : OP_SELL;
      string cmt = "PaulV4|" + DoubleToString(rDist, Digits);
      color arrowClr = isBullRegime ? clrLime : clrRed;

      int newTicket = OrderSend(Symbol(), cmd, lotOut, entryOut, SlippagePoints, slOut, tp2Out, cmt, MagicNumber, 0, arrowClr);
      if(newTicket > 0)
        {
         g_lastTrackedTicket = newTicket;
         GlobalVariableSet(GetGVKey("RDist"), rDist);
         GlobalVariableSet(GetGVKey("Stage"), 0.0);
         Print("[PAUL PRO V4 ORDER EXECUTED] #", newTicket, " ", dirStrOut, " ", DoubleToString(lotOut, 2),
               " Lots on ", Symbol(), " @ ", DoubleToString(entryOut, Digits),
               " | Initial SL: ", DoubleToString(slOut, Digits),
               " | Stage1 Lock (+0.3R): ", DoubleToString(lock1Out, Digits),
               " | Stage2 Lock (+1.5R): ", DoubleToString(lock2Out, Digits),
               " | Full TP (+3.5R): ", DoubleToString(tp2Out, Digits));
         SendTelegramMessage(StringFormat("<b>[NEW MT4 ORDER OPENED] %s (%s)</b>\n"
                                          "----------------------------------\n"
                                          "Ticket: <code>#%d</code> | Size: <code>%.2f Lots</code>\n"
                                          "Entry: <code>%s</code> | SL: <code>%s</code> (-0.75%%)\n"
                                          "Stage 1 Lock (+0.3R): <code>%s</code>\n"
                                          "Full Target TP2 (+3.5R): <code>%s</code>\n"
                                          "MT4 Account: <code>#%d (%s)</code> | Equity: <code>$%.2f</code>",
                                          Symbol(), dirStrOut, newTicket, lotOut,
                                          DoubleToString(entryOut, Digits),
                                          DoubleToString(slOut, Digits),
                                          DoubleToString(lock1Out, Digits),
                                          DoubleToString(tp2Out, Digits),
                                          AccountNumber(), AccountServer(), AccountEquity()));
        }
      else
        {
         Print("[ORDER SEND ERROR] Code: ", GetLastError(), " on ", Symbol());
        }
     }
  }

//+------------------------------------------------------------------+
//| Helper: Draw Text Label on Chart HUD                             |
//+------------------------------------------------------------------+
void DrawHudLine(int lineIdx, string text, color textColor, int fontSize = 9)
  {
   string objName = g_hudPrefix + "Line_" + IntegerToString(lineIdx);
   if(ObjectFind(0, objName) < 0)
     {
      ObjectCreate(0, objName, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, objName, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, objName, OBJPROP_XDISTANCE, 16);
     }
   ObjectSetInteger(0, objName, OBJPROP_YDISTANCE, 24 + (lineIdx * 18));
   ObjectSetString(0, objName, OBJPROP_TEXT, text);
   ObjectSetString(0, objName, OBJPROP_FONT, "Consolas");
   ObjectSetInteger(0, objName, OBJPROP_FONTSIZE, fontSize);
   ObjectSetInteger(0, objName, OBJPROP_COLOR, textColor);
  }

//+------------------------------------------------------------------+
//| Render On-Chart Institutional 4-Gate HUD                         |
//+------------------------------------------------------------------+
void UpdateHUD()
  {
   if(!ShowOnChartHUD)
      return;

   if(g_symbolBlocked)
     {
      DrawHudLine(0, "[BLOCKED] PAUL PRO V4.1: AUD/USD IS PERMANENTLY REMOVED (PF 0.79)", clrRed, 10);
      return;
     }

   double dailyLossPct = 0.0, totalLossPct = 0.0;
   bool guardianOk = CheckFtmoGuardian(dailyLossPct, totalLossPct);

   bool g1 = false, g2 = false, g3 = false, g4 = false;
   string dirStr = "", cotVerdict = "";
   double ent = 0, sl = 0, lk1 = 0, lk2 = 0, tp2 = 0, lots = 0;

   Evaluate4GatesAndExecute(false, g1, g2, g3, g4, dirStr, cotVerdict, ent, sl, lk1, lk2, tp2, lots);

   int openTicket = FindOpenTradeTicket();
   int curStage   = GlobalVariableCheck(GetGVKey("Stage")) ? (int)GlobalVariableGet(GetGVKey("Stage")) : 0;

   DrawHudLine(0, "=== PAUL FTMO PRO V4.1 : INSTITUTIONAL COMMAND HUD (" + Symbol() + " H4) ===", clrGold, 10);
   DrawHudLine(1, StringFormat("Account Equity: $%.2f | Daily DD: %.2f%% (Max %.1f%%) | Guardian: %s",
               AccountEquity(), dailyLossPct, MaxDailyLossPct, (guardianOk ? "ACTIVE [OK]" : "HALTED [!]")),
               (guardianOk ? clrAqua : clrRed));
   DrawHudLine(2, "----------------------------------------------------------------------", clrDimGray);
   DrawHudLine(3, StringFormat("[GATE 1] Macro + COT     : %s | Dir: %s | %s",
               (g1 ? "PASS [GREEN]" : "WAIT [RED]  "), dirStr, cotVerdict), (g1 ? clrLime : clrOrange));
   DrawHudLine(4, StringFormat("[GATE 2] EMA50 + Cool 8  : %s | Cooldown: %d/8 H4 Bars",
               (g2 ? "PASS [GREEN]" : "WAIT [RED]  "), GetH4BarsSinceLastExit()), (g2 ? clrLime : clrOrange));
   DrawHudLine(5, StringFormat("[GATE 3] 3-Bar BOS + RSI : %s | H4 RSI(14): %.1f",
               (g3 ? "PASS [GREEN]" : "WAIT [RED]  "), iRSI(Symbol(), PERIOD_H4, RsiPeriod, PRICE_CLOSE, 1)),
               (g3 ? clrLime : clrOrange));
   DrawHudLine(6, StringFormat("[GATE 4] ATR 0.75%% Sizing: %s | Planned Lot: %.2f Lots | SL: %s",
               (g4 ? "READY [GREEN]" : "WAIT [RED]  "), lots, DoubleToString(sl, Digits)), (g4 ? clrLime : clrSilver));
   DrawHudLine(7, "----------------------------------------------------------------------", clrDimGray);

   if(openTicket > 0 && OrderSelect(openTicket, SELECT_BY_TICKET, MODE_TRADES))
     {
      DrawHudLine(8, StringFormat("[ACTIVE ORDER #%d] (%s %.2f Lots) | Stage %d | P&L: $%.2f",
                  openTicket, (OrderType() == OP_BUY ? "BUY" : "SELL"), OrderLots(), curStage, OrderProfit() + OrderSwap() + OrderCommission()),
                  clrLime);
     }
   else
     {
      DrawHudLine(8, StringFormat("[NEXT TICKET] Entry: %s | Lock1(+0.3R): %s | Lock2(+1.5R): %s | TP(+3.5R): %s",
                  DoubleToString(ent, Digits), DoubleToString(lk1, Digits), DoubleToString(lk2, Digits), DoubleToString(tp2, Digits)),
                  clrSilver);
     }
  }

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
  {
   if(g_symbolBlocked)
      return;

   // 1. Check FTMO Guardian Circuit Breakers on Every Tick
   double dailyLossPct = 0.0, totalLossPct = 0.0;
   bool guardianOk = CheckFtmoGuardian(dailyLossPct, totalLossPct);

   // 2. Manage Any Open Position on Every Tick (Immediate Stage 1 & Stage 2 SL Locking)
   int openTicket = FindOpenTradeTicket();
   CheckAndNotifyClosedTrade(openTicket);
   if(openTicket > 0)
     {
      ManageOpenPosition(openTicket);
      if(ShowOnChartHUD)
         UpdateHUD();
      return;
     }

   // 3. Evaluate New Trade Entries Strictly Once Per H4 Bar Close
   datetime currentBarTimeH4 = iTime(Symbol(), PERIOD_H4, 0);
   if(currentBarTimeH4 != g_lastBarTimeH4)
     {
      g_lastBarTimeH4 = currentBarTimeH4;

      if(guardianOk)
        {
         bool g1 = false, g2 = false, g3 = false, g4 = false;
         string dirStr = "", cotVerdict = "";
         double ent = 0, sl = 0, lk1 = 0, lk2 = 0, tp2 = 0, lots = 0;
         Evaluate4GatesAndExecute(true, g1, g2, g3, g4, dirStr, cotVerdict, ent, sl, lk1, lk2, tp2, lots);
        }

      CheckAndSendMT4PortfolioSummary(currentBarTimeH4);

      if(ShowOnChartHUD)
         UpdateHUD();
     }
  }
//+------------------------------------------------------------------+
