import time
import random
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 配置项
MAX_PAGE = 100  # 可修改最大爬取页数
SAVE_PATH = "lianjia_ershoufang_beijing.csv"
BASE_URL = "https://bj.lianjia.com/ershoufang/pg{}/"

# -------------------------- 填入核心登录Cookies --------------------------
LOGIN_COOKIES = {
    #f12去application里找
}


def setup_driver():
    """配置并返回浏览器驱动"""
    try:
        options = Options()
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument(
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36')

        driver = webdriver.Chrome(options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # 先访问首页添加cookies
        print("初始化浏览器并设置cookies...")
        driver.get("https://bj.lianjia.com/")
        time.sleep(2)

        # 添加cookies
        for name, value in LOGIN_COOKIES.items():
            try:
                driver.add_cookie({
                    'name': name,
                    'value': value,
                    'domain': '.lianjia.com'
                })
            except Exception as e:
                print(f"添加cookie {name} 失败: {e}")

        print("浏览器初始化完成")
        return driver

    except Exception as e:
        print(f"浏览器驱动初始化失败: {str(e)}")
        return None


def detect_captcha_in_selenium(driver):
    """在Selenium中检测验证码"""
    captcha_indicators = [
        "人机验证",
        "geetest_captcha",
        "点击按钮开始验证",
        "请按语序依次点击"
    ]
    page_source = driver.page_source
    return any(indicator in page_source for indicator in captcha_indicators)


def fetch_page_selenium(driver, url):
    """完全使用Selenium获取页面，超时后停止加载"""
    try:
        print(f"访问: {url}")

        # 设置页面加载超时
        driver.set_page_load_timeout(5)

        try:
            driver.get(url)
        except:
            print("页面加载超时，但可能主要内容已加载")

        try:
            # 等待页面加载完成（等待房源列表或验证码出现）
            WebDriverWait(driver, 2.5).until(
                lambda d: d.find_elements(By.CLASS_NAME, "sellListContent") or
                          "点击按钮" in d.page_source or
                          d.find_elements(By.CLASS_NAME, "geetest_captcha")
            )
        except:
            print("等待超时，尝试停止加载并检查当前内容...")
            # 按ESC键停止加载
            from selenium.webdriver.common.keys import Keys
            from selenium.webdriver.common.action_chains import ActionChains

            actions = ActionChains(driver)
            actions.send_keys(Keys.ESCAPE).perform()
            time.sleep(1)  # 等待停止生效

        # 检查是否有验证码
        if detect_captcha_in_selenium(driver):
            print("=" * 50)
            print("检测到验证码，需要手动处理...")
            print("请按照以下步骤操作：")
            print("1. 在浏览器中完成人机验证")
            print("2. 验证成功后页面会显示二手房列表")
            print("3. 完成后回到控制台按回车键继续")
            print("=" * 50)

            input("请在浏览器中完成验证，然后按回车继续...")

            try:
                # 重新等待页面加载完成
                WebDriverWait(driver, 2.5).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "sellListContent"))
                )
                print("验证完成，继续解析页面...")
            except:
                print("验证后等待超时，使用当前页面内容...")

        # 获取页面源码
        html = driver.page_source

        # 检查是否获取到有效内容
        if "sellListContent" not in html:
            print("警告：页面可能未完全加载")

        return html

    except Exception as e:
        print(f"Selenium获取页面失败: {str(e)}")
        return None


def parse_page(html):
    """解析二手房列表页面，提取详细信息"""
    soup = BeautifulSoup(html, "lxml")
    house_list = soup.find_all("li", class_="clear LOGVIEWDATA LOGCLICKDATA")

    if not house_list:
        print("未找到二手房列表数据")
        return []

    data = []
    for house in house_list:
        item = {}
        try:
            # 1. 房源标题和链接
            title_tag = house.find("div", class_="title").find("a") if house.find("div", class_="title") else None
            item["房源标题"] = title_tag.get_text(strip=True) if title_tag else "未知"
            item["房源链接"] = title_tag.get("href", "") if title_tag else ""

            # 2. 小区名称和区域信息
            position_info = house.find("div", class_="positionInfo")
            if position_info:
                xiaoqu_tag = position_info.find("a")
                item["小区名称"] = xiaoqu_tag.get_text(strip=True) if xiaoqu_tag else "未知"
                region_tags = position_info.find_all("a")
                if len(region_tags) > 1:
                    item["商圈"] = region_tags[1].get_text(strip=True) if len(region_tags) > 1 else "未知"
                else:
                    item["商圈"] = "未知"
            else:
                item["小区名称"] = "未知"
                item["商圈"] = "未知"

            # 3. 房屋基本信息
            house_info = house.find("div", class_="houseInfo")
            if house_info:
                house_text = house_info.get_text(strip=True)
                parts = house_text.split("|")
                if len(parts) >= 1: item["户型"] = parts[0].strip()
                if len(parts) >= 2: item["面积"] = parts[1].strip()
                if len(parts) >= 3: item["朝向"] = parts[2].strip()
                if len(parts) >= 4: item["装修"] = parts[3].strip()
                if len(parts) >= 5: item["楼层"] = parts[4].strip()
                if len(parts) >= 6: item["建筑信息"] = parts[5].strip()
            else:
                item["户型"] = "未知"
                item["面积"] = "未知"
                item["朝向"] = "未知"
                item["装修"] = "未知"
                item["楼层"] = "未知"
                item["建筑信息"] = "未知"

            # 4. 关注信息
            follow_info = house.find("div", class_="followInfo")
            item["关注信息"] = follow_info.get_text(strip=True) if follow_info else "未知"

            # 5. 标签信息
            tag_div = house.find("div", class_="tag")
            if tag_div:
                tags = [span.get_text(strip=True) for span in tag_div.find_all("span")]
                item["标签"] = "|".join(tags)
            else:
                item["标签"] = ""

            # 6. 价格信息
            total_price_div = house.find("div", class_="totalPrice")
            item["总价"] = total_price_div.get_text(strip=True) if total_price_div else "未知"

            unit_price_div = house.find("div", class_="unitPrice")
            item["单价"] = unit_price_div.get_text(strip=True) if unit_price_div else "未知"

            # 7. 房源ID
            house_code = title_tag.get("data-housecode", "") if title_tag else ""
            item["房源ID"] = house_code

            data.append(item)

        except Exception as e:
            print(f"解析单个房源信息时出错：{str(e)}")
            continue

    return data


def main():
    all_data = []

    # 初始化浏览器驱动
    driver = setup_driver()
    if not driver:
        print("浏览器初始化失败，程序退出")
        return

    print(f"开始爬取链家北京二手房数据（1-{MAX_PAGE}页）...")

    try:
        for page in range(20, MAX_PAGE + 1):
            url = BASE_URL.format(page)
            print(f"\n正在爬取第{page}页：{url}")

            # 使用Selenium获取页面
            html = fetch_page_selenium(driver, url)

            if not html:
                print(f"第{page}页爬取失败，跳过")
                continue

            page_data = parse_page(html)
            if not page_data:
                print(f"第{page}页无房源数据，停止爬取")
                break

            all_data.extend(page_data)
            print(f"第{page}页爬取成功，新增{len(page_data)}条房源")

            # 显示第一条数据作为示例
            if page_data:
                print(f"示例：{page_data[0]['房源标题'][:20]}... - {page_data[0]['总价']}")

            # 控制爬取频率
            sleep_time = random.uniform(3, 6)
            print(f"等待 {sleep_time:.1f} 秒后继续...")
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n用户中断爬取")
    except Exception as e:
        print(f"爬取过程发生错误: {str(e)}")
    finally:
        if driver:
            driver.quit()
            print("浏览器已关闭")

    # 保存数据到CSV
    if all_data:
        df = pd.DataFrame(all_data)
        # 重新排列列的顺序，让重要信息在前
        columns_order = ['房源标题', '小区名称', '商圈', '总价', '单价', '户型', '面积', '朝向',
                         '装修', '楼层', '建筑信息', '关注信息', '标签', '房源ID', '房源链接']
        # 只保留实际存在的列
        existing_columns = [col for col in columns_order if col in df.columns]
        df = df[existing_columns + [col for col in df.columns if col not in existing_columns]]

        df.to_csv(SAVE_PATH, index=False, encoding="utf-8-sig")
        print(f"\n爬取完成！共获取{len(all_data)}条二手房数据，已保存至{SAVE_PATH}")

        # 显示统计信息
        print(f"\n数据统计：")
        print(f"- 总房源数：{len(all_data)}")
        if all_data:
            valid_prices = []
            for d in all_data:
                if d['总价'] != '未知':
                    try:
                        price = float(d['总价'].replace('万', '').strip())
                        valid_prices.append(price)
                    except:
                        pass
            if valid_prices:
                print(f"- 价格范围：{min(valid_prices)}万 - {max(valid_prices)}万")
                print(f"- 平均价格：{sum(valid_prices) / len(valid_prices):.1f}万")
    else:
        print("未爬取到任何二手房数据")


if __name__ == "__main__":
    main()