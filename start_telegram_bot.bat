@echo off
chcp 65001 >nul
cd /d "D:\cot_dashboard"
title Paul FTMO Interactive Telegram Command Bot
echo ======================================================================
echo   🤖 PAUL FTMO V4 - INTERACTIVE TELEGRAM COMMAND LISTENER
echo ======================================================================
echo.
echo กำลังเปิดระบบรับคำสั่ง Telegram ตลอด 24 ชม....
echo คุณสามารถพิมพ์คำสั่งใน Telegram ได้ทันที:
echo   - พิมพ์ "/history" หรือ "ประวัติ" เพื่อขอดูประวัติออเดอร์
echo   - พิมพ์ "/status" หรือ "สถานะ" เพื่อดูผลการสแกน H4
echo   - พิมพ์ "/portfolio" หรือ "พอร์ต" เพื่อเช็คยอดเงิน FTMO $100k
echo   - หรือแตะปุ่มเมนูด้านล่างบนมือถือ
echo.
python telegram_bot_service.py
pause
