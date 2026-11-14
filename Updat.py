import urllib.request
import json
import datetime
import math

# 1. 你的實際持倉配置 (已依截圖數據校準，未來加減倉只需修改這裡的 shares 與 cost)
PORTFOLIO = [
    {"code": "021277", "name": "廣發全球精選股票(QDII)C", "shares": 771.17, "cost": 5241.42, "fallback_nav": 5.2508, "tag": "全球科技QDII"},
    {"code": "012733", "name": "易方達人工智能ETF聯接A", "shares": 4388.79, "cost": 10000.00, "fallback_nav": 1.6354, "tag": "A股AI算力"},
    {"code": "020722", "name": "國壽安保數字經濟股票A", "shares": 3447.09, "cost": 10243.72, "fallback_nav": 1.8405, "tag": "硬科技動能"}
]

# 2. 看板同步追蹤的防禦型候選標的 (供7.5萬剩餘資金配置參考)
WATCHLIST = [
    {"code": "007721", "name": "天弘中證紅利低波動100聯接A", "role": "高股息防禦壓艙石"},
    {"code": "000216", "name": "華安黃金易ETF聯接A", "role": "宏觀避險對沖"},
    {"code": "110020", "name": "易方達滬深300ETF聯接A", "role": "核心寬基均衡"}
]

TOTAL_CAPITAL = 100000.00   # 總資金 10 萬
TARGET_CAPITAL = 120000.00  # 目標 12 萬 (年營利 20%)
CASH_REMAINING = round(TOTAL_CAPITAL - sum(x["cost"] for x in PORTFOLIO), 2)

def fetch_fund_history(code, fallback=1.0):
    url = f"https://api.fund.eastmoney.com/f10/lsjz?fundCode={code}&pageIndex=1&pageSize=20"
    req = urllib.request.Request(url, headers={"Referer": "https://fundf10.eastmoney.com/", "User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
            items = raw.get("Data", {}).get("LSJZList", [])
            if items:
                navs = [float(i["DWJZ"]) for i in items if i.get("DWJZ")]
                latest_date = items[0]["FSRQ"]
                daily_pct = float(items[0]["JZZZL"] or 0)
                return navs, daily_pct, latest_date
    except Exception as e:
        print(f"Fetch error for {code}: {e}")
    return [fallback] * 15, 0.0, datetime.date.today().strftime("%Y-%m-%d")

def calc_rsi(navs, period=14):
    # navs 由新到舊排列，反轉為由舊到新
    prices = list(reversed(navs))
    if len(prices) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)

def main():
    now_str = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
    holdings_data = []
    total_fund_value = 0.0
    total_cost = 0.0
    today_pnl = 0.0

    for item in PORTFOLIO:
        navs, daily_pct, nav_date = fetch_fund_history(item["code"], item["fallback_nav"])
        latest_nav = navs[0]
        val = round(item["shares"] * latest_nav, 2)
        pnl = round(val - item["cost"], 2)
        pnl_pct = round((pnl / item["cost"]) * 100, 2)
        day_earn = round(val - (val / (1 + daily_pct / 100)), 2) if daily_pct != -100 else 0.0
        rsi = calc_rsi(navs)

        if rsi > 75:
            signal = "⚠️ 超買示警 (建議減碼鎖利)"
        elif rsi < 32:
            signal = "🟢 超賣區間 (觀察分批補倉)"
        else:
            signal = "🟡 震盪持有 (嚴控倉位)"

        total_fund_value += val
        total_cost += item["cost"]
        today_pnl += day_earn

        holdings_data.append({
            "code": item["code"],
            "name": item["name"],
            "tag": item["tag"],
            "nav": latest_nav,
            "nav_date": nav_date,
            "daily_pct": daily_pct,
            "value": val,
            "cost": item["cost"],
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "rsi": rsi,
            "signal": signal
        })

    watch_data = []
    for w in WATCHLIST:
        navs, daily_pct, nav_date = fetch_fund_history(w["code"], 1.0)
        watch_data.append({
            "code": w["code"],
            "name": w["name"],
            "role": w["role"],
            "nav": navs[0],
            "daily_pct": daily_pct,
            "rsi": calc_rsi(navs)
        })

    net_worth = round(total_fund_value + CASH_REMAINING, 2)
    total_pnl = round(total_fund_value - total_cost, 2)
    gap_to_target = round(TARGET_CAPITAL - net_worth, 2)
    req_return_pct = round((gap_to_target / net_worth) * 100, 2)

    summary = {
        "updated_at": now_str,
        "total_capital_initial": TOTAL_CAPITAL,
        "target_capital": TARGET_CAPITAL,
        "current_net_worth": net_worth,
        "fund_market_value": round(total_fund_value, 2),
        "cash_remaining": CASH_REMAINING,
        "cumulative_pnl": total_pnl,
        "today_estimated_pnl": round(today_pnl, 2),
        "gap_to_120k": gap_to_target,
        "required_return_pct": req_return_pct,
        "holdings": holdings_data,
        "defensive_watchlist": watch_data
    }

    # 輸出給 Google Gemini 讀取的標準 JSON
    with open("portfolio_data.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # 輸出給 iPad 直接瀏覽的機構級看板網頁
    rows_html = ""
    for h in holdings_data:
        color = "#10b981" if h["pnl"] >= 0 else "#ef4444"
        d_color = "#10b981" if h["daily_pct"] >= 0 else "#ef4444"
        rows_html += f"""
        <div class="card">
            <div class="row-between">
                <div><span class="badge">{h['code']}</span> <strong>{h['name']}</strong></div>
                <span style="color:{d_color};font-weight:bold;">{h['daily_pct']:+.2f}%</span>
            </div>
            <div class="grid-3">
                <div><small>最新淨值 ({h['nav_date']})</small><div>{h['nav']:.4f}</div></div>
                <div><small>持倉市值</small><div>¥{h['value']:,.2f}</div></div>
                <div><small>累計盈虧</small><div style="color:{color};font-weight:bold;">{h['pnl']:+.2f} ({h['pnl_pct']:+.1f}%)</div></div>
            </div>
            <div class="signal-bar">RSI(14): <b>{h['rsi']}</b> ｜ 機構信號：<b>{h['signal']}</b></div>
        </div>"""

    watch_html = ""
    for w in watch_data:
        d_color = "#10b981" if w["daily_pct"] >= 0 else "#ef4444"
        watch_html += f"""
        <div class="watch-item">
            <div><strong>{w['name']}</strong> ({w['code']})<br><small style="color:#94a3b8">{w['role']}</small></div>
            <div style="text-align:right">淨值 {w['nav']:.4f}<br><span style="color:{d_color}">{w['daily_pct']:+.2f}%</span> · RSI {w['rsi']}</div>
        </div>"""

    json_escaped = json.dumps(summary, ensure_ascii=False)
    html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Blackstone Style 量化投資看板</title>
<style>
  body {{ background:#0b0f19; color:#f1f5f9; font-family:-apple-system,BlinkMacSystemFont,sans-serif; margin:0; padding:16px; }}
  .container {{ max-width:820px; margin:0 auto; }}
  .header {{ display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1e293b; padding-bottom:12px; margin-bottom:16px; }}
  .kpi-grid {{ display:grid; grid-template-columns:repeat(2,1fr); gap:12px; margin-bottom:16px; }}
  @media(min-width:640px){{ .kpi-grid {{ grid-template-columns:repeat(4,1fr); }} }}
  .kpi {{ background:#111827; border:1px solid #1f2937; border-radius:12px; padding:14px; }}
  .kpi small {{ color:#94a3b8; font-size:12px; }}
  .kpi .val {{ font-size:20px; font-weight:700; margin-top:4px; }}
  .card {{ background:#111827; border:1px solid #1f2937; border-radius:12px; padding:14px; margin-bottom:12px; }}
  .row-between {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; }}
  .badge {{ background:#1e293b; color:#38bdf8; padding:2px 6px; border-radius:4px; font-size:12px; }}
  .grid-3 {{ display:grid; grid-template-columns:repeat(3,1fr); gap:8px; font-size:14px; }}
  .grid-3 small {{ color:#94a3b8; font-size:11px; }}
  .signal-bar {{ margin-top:10px; padding-top:8px; border-top:1px dashed #1f2937; font-size:12px; color:#cbd5e1; }}
  .alert-box {{ background:rgba(239,68,68,0.12); border:1px solid rgba(239,68,68,0.4); color:#fca5a5; padding:12px; border-radius:10px; font-size:13px; margin-bottom:16px; }}
  .watch-item {{ display:flex; justify-content:space-between; padding:10px 0; border-bottom:1px solid #1f2937; font-size:13px; }}
  .btn {{ width:100%; background:#2563eb; color:white; border:none; padding:14px; border-radius:10px; font-size:15px; font-weight:600; cursor:pointer; margin-top:8px; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div><h2 style="margin:0;font-size:18px;">🏛️ 機構級量化資產評估看板</h2><small style="color:#64748b">自動更新時間 (UTC+8)：{now_str}</small></div>
  </div>
  <div class="kpi-grid">
    <div class="kpi"><small>實際總資產淨值</small><div class="val">¥{net_worth:,.2f}</div></div>
    <div class="kpi"><small>基金持倉市值</small><div class="val">¥{total_fund_value:,.2f}</div></div>
    <div class="kpi"><small>累計持倉盈虧</small><div class="val" style="color:{'#10b981' if total_pnl>=0 else '#ef4444'}">{total_pnl:+,.2f}</div></div>
    <div class="kpi"><small>距12萬目標所需回報</small><div class="val" style="color:#f59e0b">{req_return_pct}%</div></div>
  </div>
  <div class="alert-box">
    <b>⚠️ 機構風控示警：</b>目前三檔持倉 100% 集中於 AI 與科技賽道，波動極高。剩餘現金 <b>¥{CASH_REMAINING:,.2f}</b> 建議分批配置下方「防禦型候選標的」以降低單一產業風險。
  </div>
  <h3 style="font-size:15px;color:#94a3b8;">📊 核心持倉動態與擇時信號</h3>
  {rows_html}
  <h3 style="font-size:15px;color:#94a3b8;margin-top:20px;">🛡️ 7.5萬剩餘資金配置雷達（低相關性防禦標的）</h3>
  <div class="card">{watch_html}</div>
  <button class="btn" onclick="copyForGemini()">📋 一鍵複製今日最新數據（貼給 Gemini 分析）</button>
</div>
<script>
const latestData = {json_escaped};
function copyForGemini() {{
  const prompt = "這是我今日自動更新的基金持倉與市場數據，請以專業投資經理人角度幫我評估今日變化與下一步調倉建議：\\n" + JSON.stringify(latestData, null, 2);
  navigator.clipboard.writeText(prompt).then(() => alert("✅ 已複製今日最新持倉數據！請切換到 Gemini 貼上即可。"));
}}
</script>
</body>
</html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Dashboard updated successfully!")

if __name__ == "__main__":
    main()
