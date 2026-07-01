#!/usr/bin/env python3
"""
Market Dashboard Auto-Refresh Script
Fetches real-time index + sector data from qt.gtimg.cn and updates index.html
Run: python scripts/refresh.py          (from repo root)
Output: updates index.html in repo root
Timezone: Beijing time (UTC+8), independent of server clock
"""
import urllib.request
import re
import os
from datetime import datetime, timezone, timedelta

# Force Beijing timezone
TZ = timezone(timedelta(hours=8))

CODES = [
    'sh000001','sz399001','sz399006','sh000688','hkHSI','hkHSTECH',
    'pt01801010','pt01801030','pt01801040','pt01801050','pt01801080',
    'pt01801110','pt01801120','pt01801130','pt01801140','pt01801150',
    'pt01801160','pt01801170','pt01801180','pt01801200','pt01801210',
    'pt01801230','pt01801710','pt01801720','pt01801730','pt01801740',
    'pt01801750','pt01801760','pt01801770','pt01801780','pt01801790',
    'pt01801880','pt01801890','pt01801950','pt01801960','pt01801980',
]

INDEX_NAMES = {
    'sh000001':'上证指数','sz399001':'深证成指','sz399006':'创业板指','sh000688':'科创50',
    'hkHSI':'恒生指数','hkHSTECH':'恒生科技',
}

SECTOR_NAMES = {
    'pt01801010':'农林牧渔','pt01801030':'基础化工','pt01801040':'钢铁',
    'pt01801050':'有色金属','pt01801080':'电子','pt01801110':'家用电器',
    'pt01801120':'食品饮料','pt01801130':'纺织服饰','pt01801140':'轻工制造',
    'pt01801150':'医药生物','pt01801160':'公用事业','pt01801170':'交通运输',
    'pt01801180':'房地产','pt01801200':'商贸零售','pt01801210':'社会服务',
    'pt01801230':'综合','pt01801710':'建筑材料','pt01801720':'建筑装饰',
    'pt01801730':'电力设备','pt01801740':'国防军工','pt01801750':'计算机',
    'pt01801760':'传媒','pt01801770':'通信','pt01801780':'银行',
    'pt01801790':'非银金融','pt01801880':'汽车','pt01801890':'机械设备',
    'pt01801950':'煤炭','pt01801960':'石油石化','pt01801980':'美容护理',
}

def fetch_data():
    """Fetch all index + sector data from qt.gtimg.cn"""
    url = f"https://qt.gtimg.cn/q={','.join(CODES)}"
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://gu.qq.com/'
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        text = resp.read().decode('gbk', errors='replace')

    data = {}
    for line in text.split('\n'):
        m = re.match(r'v_(\w+)="(.+)"', line.strip())
        if not m:
            continue
        code, content = m.groups()
        fields = content.split('~')
        if len(fields) < 35:
            continue
        try:
            price = float(fields[3])
            pct = float(fields[32])
        except (ValueError, IndexError):
            continue
        data[code] = {
            'price': price,
            'pct': pct,
            'time': fields[30] if len(fields) > 30 else '',
        }
    return data

def fmt_price(val, decimals=2):
    """Format price with commas"""
    if val is None:
        return '—'
    if decimals == 2:
        return f"{val:,.2f}"
    if decimals == 0:
        return f"{val:,.0f}"
    fmt = "{:,." + str(decimals) + "f}"
    return fmt.format(val)

def fmt_pct(val):
    """Format percentage"""
    if val is None:
        return '—'
    sign = '+' if val >= 0 else ''
    return f"{sign}{val:.2f}%"

def update_html(html_path, data):
    """Update index.html with fetched data"""
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    now = datetime.now(TZ)
    ts = now.strftime('%H:%M')
    weekday = ['一','二','三','四','五','六','日'][now.weekday()]
    date_cn = now.strftime(f'%Y年%m月%d日（星期{weekday}）')
    date_en = now.strftime('%Y-%m-%d')

    # Update header date
    html = re.sub(r'📅 \d{4}年\d{1,2}月\d{1,2}日（星期[一二三四五六日]）', f'📅 {date_cn}', html)
    # Update title
    html = re.sub(r'<title>.*?市场数据看板', f'<title>{now.strftime("%Y年%m月%d日")} 市场数据看板', html)

    # Update index cards in fullday tab (f-price-CODE, f-pct-CODE)
    for code, name in INDEX_NAMES.items():
        item = data.get(code, {})
        price = item.get('price')
        pct = item.get('pct')

        price_str = fmt_price(price, 2) if price else '—'

        # Update price
        price_re = re.compile(r'(<div class="index-price" id="f-price-' + code + r'">)[^<]*(</div>)')
        html = price_re.sub(lambda m: m.group(1) + price_str + m.group(2), html)

        # Update pct and its class
        if pct is not None:
            pct_str = fmt_pct(pct)
            cls = 'up' if pct > 0 else ('down' if pct < 0 else 'neutral')
            pct_re = re.compile(r'(<div class="index-change )[^"]*(" id="f-pct-' + code + r'">)[^<]*(</div>)')
            html = pct_re.sub(lambda m: m.group(1) + cls + m.group(2) + pct_str + m.group(3), html)

        # Update time
        time_re = re.compile(r'(<div class="index-time" id="f-time-' + code + r'">)[^<]*(</div>)')
        html = time_re.sub(lambda m: m.group(1) + '更新 ' + ts + m.group(2), html)

    # Update sector rankings
    sectors = []
    for code, name in SECTOR_NAMES.items():
        item = data.get(code, {})
        if item.get('pct') is not None:
            sectors.append({'name': name, 'pct': item['pct']})

    if sectors:
        sectors.sort(key=lambda x: x['pct'], reverse=True)

        # Build TOP5 table
        top5_rows = '<tr><th>排名</th><th>行业</th><th>涨跌幅</th></tr>\n'
        for i, s in enumerate(sectors[:5]):
            cls = 'sector-up' if s['pct'] >= 0 else 'sector-down'
            sign = '+' if s['pct'] >= 0 else ''
            top5_rows += f'          <tr><td>{i+1}</td><td>{s["name"]}</td><td class="{cls}">{sign}{s["pct"]:.2f}%</td></tr>\n'

        # Replace TOP5 table body
        html = re.sub(
            r'(<table id="fullday-top5-body">)[\s\S]*?(</table>)',
            lambda m: m.group(1) + '\n' + top5_rows.rstrip() + '\n        ' + m.group(2),
            html
        )

        # Build BOTTOM5 table
        bot5_rows = '<tr><th>排名</th><th>行业</th><th>涨跌幅</th></tr>\n'
        for i, s in enumerate(reversed(sectors[-5:])):
            cls = 'sector-up' if s['pct'] >= 0 else 'sector-down'
            sign = '+' if s['pct'] >= 0 else ''
            bot5_rows += f'          <tr><td>{i+1}</td><td>{s["name"]}</td><td class="{cls}">{sign}{s["pct"]:.2f}%</td></tr>\n'

        html = re.sub(
            r'(<table id="fullday-bot5-body">)[\s\S]*?(</table>)',
            lambda m: m.group(1) + '\n' + bot5_rows.rstrip() + '\n        ' + m.group(2),
            html
        )

    # Update title timestamps
    html = re.sub(r'🔺 行业涨幅 TOP 5（实时 · \d{2}:\d{2}）', f'🔺 行业涨幅 TOP 5（实时 · {ts}）', html)
    html = re.sub(r'🔻 行业跌幅 BOTTOM 5（实时 · \d{2}:\d{2}）', f'🔻 行业跌幅 BOTTOM 5（实时 · {ts}）', html)

    # Update summary banner: generate a fresh one-liner based on data
    sh_data = data.get('sh000001', {})
    sz_data = data.get('sz399001', {})
    cy_data = data.get('sz399006', {})
    kc_data = data.get('sh000688', {})
    sh_pct = sh_data.get('pct', 0)
    sz_pct = sz_data.get('pct', 0)
    kc_pct = kc_data.get('pct', 0)
    market_mood = '📉 午后跳水' if (sh_pct < 0.5 and kc_pct < -1) else ('📈 延续强势' if sh_pct > 1 else '📊 震荡收盘')
    top_name = sectors[0]['name'] if sectors else '—'
    top_pct = sectors[0]['pct'] if sectors else 0
    bot_name = sectors[-1]['name'] if sectors else '—'
    bot_pct = sectors[-1]['pct'] if sectors else 0

    summary_line = (
        f'{market_mood}：上证{sh_pct:+.2f}%、深证{sz_pct:+.2f}%、科创50{kc_pct:+.2f}%。'
        f'{top_name}{top_pct:+.2f}%全天领涨，{bot_name}{bot_pct:+.2f}%垫底。'
        f'数据更新：{date_cn} {ts}'
    )
    # Replace the summary-text span content
    html = re.sub(
        r'(<span class="summary-text">)[^<]*(</span>)',
        lambda m: m.group(1) + summary_line + m.group(2),
        html
    )
    # Clear the detail-text (was specific to morning)
    html = re.sub(
        r'(<div class="detail-text">)[\s\S]*?(</div>)',
        lambda m: m.group(1) + '全日收盘数据已刷新。行业排名为收盘时刻快照，完整分析由自动化在15:10/16:10产出。' + m.group(2),
        html
    )

    # Update footer date
    html = re.sub(r'Generated by 呆呆 · .*', f'Generated by 呆呆 · 徐浩男的智能助理 · {date_en} {ts}', html)

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return True

if __name__ == '__main__':
    import os
    # Find index.html relative to script dir (scripts/../index.html)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    html_path = os.path.join(repo_root, 'index.html')

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始刷新市场数据...")
    try:
        data = fetch_data()
        print(f"  获取到 {len(data)} 个标的行情数据")
        update_html(html_path, data)
        print(f"  {html_path} 更新完成")
    except Exception as e:
        print(f"  错误: {e}")
        exit(1)
