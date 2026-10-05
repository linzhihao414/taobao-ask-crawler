"""
淘宝"问大家"采集工具 v2
功能：搜索关键词 → 获取商品列表 → 采集每个商品的问大家问题+回答+日期 → 导出Excel
"""
import asyncio
import csv
import os
import re
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, Page, BrowserContext

# ============ 配置区 ============
KEYWORDS_FILE = Path(__file__).parent / "关键词.txt"
MAX_PRODUCTS = 50                   # 每个关键词最多采多少个商品
MAX_QUESTIONS_PER_PRODUCT = 30
OUTPUT_DIR = Path(__file__).parent / "导出结果"
HEADLESS = False
# ============================================


def load_keywords():
    """从关键词.txt读取关键词"""
    if KEYWORDS_FILE.exists():
        text = KEYWORDS_FILE.read_text(encoding='utf-8').strip()
        return [k.strip() for k in re.split(r'[,，\n]', text) if k.strip()]
    return ["皮革"]


async def wait_for_login(page: Page, keyword: str):
    """打开搜索页，等待用户扫码登录"""
    search_url = f"https://s.taobao.com/search?q={keyword}&ie=utf8"
    await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(3)

    # 检查是否有商品
    has_items = await page.evaluate("""
        () => {
            const links = document.querySelectorAll('a[href*="item.taobao.com"], a[href*="detail.tmall.com"]');
            return links.length > 3;
        }
    """)

    if has_items:
        print("✅ 已登录，直接开始采集")
        return True

    print("\n" + "=" * 50)
    print("  请在浏览器中扫码登录淘宝")
    print("  登录后会自动继续采集")
    print("=" * 50 + "\n")

    # 等待商品出现
    for i in range(180):
        await asyncio.sleep(1)
        has_items = await page.evaluate("""
            () => {
                const links = document.querySelectorAll('a[href*="item.taobao.com"], a[href*="detail.tmall.com"]');
                return links.length > 3;
            }
        """)
        if has_items:
            print("✅ 登录成功！开始采集...")
            await asyncio.sleep(2)
            return True
        if i % 30 == 0 and i > 0:
            print(f"  等待登录中... ({i}秒)")

    print("❌ 登录超时（3分钟）")
    return False


async def search_products(page: Page, keyword: str):
    """搜索关键词，返回商品列表 [{id, title, url}]"""
    print(f"\n🔍 搜索关键词: {keyword}")

    products = []
    seen_ids = set()

    # 翻页采集
    for page_num in range(1, 4):
        print(f"  Page {page_num}...")
        await asyncio.sleep(1)

        items = await page.evaluate("""
            () => {
                const links = document.querySelectorAll('a[href*="item.taobao.com"], a[href*="detail.tmall.com"], a[href*="item.tmall.com"]');
                const results = [];
                const seen = new Set();
                links.forEach(a => {
                    const href = a.href;
                    const m = href.match(/[?&]id=(\\d+)/);
                    if (m && !seen.has(m[1])) {
                        seen.add(m[1]);
                        let title = '';
                        const card = a.closest('div[class*="item"], div[class*="Content"], div[class*="card"]');
                        if (card) {
                            const t = card.querySelector('[class*="title"], [class*="Title"], [class*="name"]');
                            if (t) title = t.innerText.trim().substring(0, 80);
                        }
                        results.push({id: m[1], title: title, url: 'https://item.taobao.com/item.htm?id=' + m[1]});
                    }
                });
                return results;
            }
        """)

        for item in items:
            if item['id'] not in seen_ids:
                seen_ids.add(item['id'])
                products.append(item)
                if len(products) >= MAX_PRODUCTS:
                    break

        if len(products) >= MAX_PRODUCTS:
            break

        # 下一页
        try:
            next_btn = await page.query_selector('button[class*="next-pagination-item"][title="下一页"], a[class*="next-pagination"]:has-text("下一页")')
            if next_btn:
                await next_btn.click()
                await asyncio.sleep(3)
            else:
                break
        except:
            break

    print(f"  找到 {len(products)} 个商品")
    return products


async def scrape_ask_questions(context: BrowserContext, product):
    """采集单个商品的问大家"""
    product_id = product['id']
    product_title = product.get('title', '')
    product_url = product['url']

    ask_url = f"https://web.m.taobao.com/app/mtb/ask-everyone/list?refId={product_id}&sourceType=other"

    page = await context.new_page()
    questions = []

    try:
        await page.goto(ask_url, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(3)

        # 检测滑块验证，等待用户手动过
        for i in range(60):
            url = page.url
            content = await page.content()
            if 'slider' in content.lower() or 'verify' in url.lower() or 'nocaptcha' in url.lower():
                print("  ⚠️ 出现滑块验证，请在浏览器中手动完成...")
                for j in range(60):
                    await asyncio.sleep(2)
                    if 'verify' not in page.url.lower() and 'nocaptcha' not in page.url.lower():
                        print("  ✅ 验证完成，继续...")
                        await asyncio.sleep(2)
                        break
            else:
                break

        # 滚动加载更多
        for _ in range(5):
            await page.mouse.wheel(0, 1500)
            await asyncio.sleep(0.5)

        # 获取页面所有文本
        all_text = await page.evaluate("() => document.body.innerText")

        # 解析问题和回答
        lines = [l.strip() for l in all_text.split('\n') if l.strip()]
        current_q = None

        for line in lines:
            # 跳过无关行
            if any(skip in line for skip in ['问大家', '淘宝', '登录', '注册', '全部', '图/视频', '好用', '不好用', '效果一般', '共', '问问买过的人', '反馈', '下一个']):
                if current_q and ('？' in line or '?' in line):
                    # 可能是新问题
                    questions.append(current_q)
                    current_q = None
                continue

            # 问题行
            if ('？' in line or '?' in line) and len(line) > 5 and len(line) < 200:
                if current_q:
                    questions.append(current_q)
                current_q = {
                    '问题': line,
                    '回答列表': [],
                    '商品ID': product_id,
                    '商品标题': product_title,
                    '商品链接': product_url,
                    '采集时间': datetime.now().strftime('%Y-%m-%d %H:%M')
                }
            elif current_q and line and len(line) < 300:
                current_q['回答列表'].append(line)

        if current_q:
            questions.append(current_q)

    except Exception as e:
        print(f"  ⚠️ 商品 {product_id} 失败: {e}")
    finally:
        await page.close()

    print(f"  ✅ 商品 {product_id}: {len(questions)} 个问题")
    return questions


def save_to_excel(all_data, keyword):
    """保存为 Excel"""
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "问大家采集"

        headers = ['关键词', '商品ID', '商品标题', '商品链接', '问题', '回答', '回答序号', '采集时间']
        ws.append(headers)

        for item in all_data:
            q = item['问题']
            product_id = item['商品ID']
            product_title = item['商品标题']
            product_url = item['商品链接']
            collect_time = item['采集时间']
            answers = item['回答列表']

            if not answers:
                ws.append([keyword, product_id, product_title, product_url, q, '', '', collect_time])
            else:
                for i, ans in enumerate(answers, 1):
                    ws.append([keyword, product_id, product_title, product_url, q, ans, i, collect_time])

        ws.column_dimensions['A'].width = 12
        ws.column_dimensions['B'].width = 15
        ws.column_dimensions['C'].width = 30
        ws.column_dimensions['D'].width = 45
        ws.column_dimensions['E'].width = 40
        ws.column_dimensions['F'].width = 50
        ws.column_dimensions['G'].width = 8
        ws.column_dimensions['H'].width = 18

        OUTPUT_DIR.mkdir(exist_ok=True)
        filename = OUTPUT_DIR / f"淘宝问大家_{keyword}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        wb.save(str(filename))
        print(f"\n📁 已保存: {filename}")
        return str(filename)
    except Exception as e:
        print(f"Excel保存失败: {e}")
        return None


async def main():
    keywords = load_keywords()
    print("=" * 50)
    print("  淘宝问大家采集工具")
    print("=" * 50)
    print(f"关键词: {', '.join(keywords)}")
    print(f"每个关键词最多 {MAX_PRODUCTS} 个商品")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=HEADLESS,
            channel="chrome",  # 使用本机安装的真实Chrome
            args=[
                '--disable-blink-features=AutomationControlled',
                '--start-maximized',
            ]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = await context.new_page()

        total = 0
        for keyword in keywords:
            # 打开搜索页并等待登录
            logged = await wait_for_login(page, keyword)
            if not logged:
                continue

            products = await search_products(page, keyword)
            if not products:
                print(f"⚠️ {keyword} 未找到商品")
                continue

            all_data = []
            for i, product in enumerate(products[:MAX_PRODUCTS], 1):
                print(f"\n[{i}/{min(len(products), MAX_PRODUCTS)}] {product.get('title','')[:30]}")
                try:
                    questions = await scrape_ask_questions(context, product)
                    all_data.extend(questions)
                except Exception as e:
                    print(f"  SKIP: {e}")
                await asyncio.sleep(0.5)

            save_to_excel(all_data, keyword)
            total += len(all_data)

        print(f"\n🎉 全部完成！共 {total} 条问题")
        print(f"📁 结果在: {OUTPUT_DIR.resolve()}")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
