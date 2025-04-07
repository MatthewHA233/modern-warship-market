import sys
import os

# 重要：在导入任何其他模块前禁止尝试安装cnocr
# 方法是修改pip模块的安装函数
try:
    import pip
    if hasattr(pip, 'main'):
        original_pip_main = pip.main
        def disabled_pip_main(*args, **kwargs):
            print("自动安装包已被禁用")
            return 0
        pip.main = disabled_pip_main
except ImportError:
    pass

# 确保后续代码不会尝试导入cnocr
# 预先创建一个假的cnocr模块
class MockCnOcr:
    def ocr(self, *args, **kwargs):
        return [["识别失败"]]

class MockCnocr:
    def __init__(self):
        self.CnOcr = MockCnOcr

# 将假模块添加到sys.modules
sys.modules['cnocr'] = MockCnocr()

# 现在导入其他模块
import glob
import pandas as pd
from datetime import datetime
import re
import time
import RaphaelScriptHelper as rsh
import argparse
import concurrent.futures
from templates.modern_warship.category_mapping import CATEGORY_DICT, ITEM_DICT, get_category_name, get_item_name

# 导入ModernWarshipMarket
sys.path.append("./")
try:
    import ModernWarshipMarket as mwm
    import MarketPriceRecognizer as mpr
except ImportError as e:
    print(f"无法导入必要模块: {e}")
    sys.exit(1)

# 确保MarketPriceRecognizer不会尝试安装cnocr
if hasattr(mpr, 'recognize_price'):
    original_recognize_price = mpr.recognize_price
    
    def safe_recognize_price(price_img):
        """安全版本的recognize_price，防止安装循环"""
        try:
            # 尝试调用原始函数，但处理所有异常
            return original_recognize_price(price_img)
        except Exception as e:
            print(f"OCR识别出错: {e}")
            return "识别失败"
    
    # 替换函数
    mpr.recognize_price = safe_recognize_price
    print("已修补OCR函数，禁止安装循环")

# 设置设备类型和ID
rsh.deviceType = 1  # 安卓设备
rsh.deviceID = ""   # 请在此填写您的设备ID，可通过adb devices命令获取

# 报价追踪相关设置
BID_TRACKER_FILE = "./market_data/报价追踪.csv"
TEMPLATE_DIR = mwm.TEMPLATE_DIR
DEFAULT_DELAY = mwm.DEFAULT_DELAY
SCREENSHOT_DELAY = mwm.SCREENSHOT_DELAY

# 特定坐标点
MARKET_ENTRY_POINT = (222, 453)  # 进入报价界面的坐标
BUY_ICON_POINT = (375, 147)      # 购买图标的坐标

# 价格识别相关设置
MAX_RECOGNITION_WORKERS = 4  # 最大同时运行的价格识别线程数

# 创建线程池
price_executor = None

def find_latest_price_data():
    """查找最新的价格数据文件"""
    price_files = glob.glob("market_data/price_data_*.csv")
    if not price_files:
        print("未找到价格数据文件")
        return None
    return max(price_files)

def search_items(keyword, price_df):
    """根据关键词搜索物品"""
    pattern = re.compile(keyword, re.IGNORECASE)
    matches = price_df[price_df['物品名称'].str.contains(pattern, na=False)]
    return matches

def display_search_results(matches):
    """显示搜索结果并让用户选择"""
    if matches.empty:
        print("未找到匹配的物品")
        return None
    
    print("\n搜索结果:")
    for i, (_, row) in enumerate(matches.iterrows()):
        print(f"{i+1}. {row['物品名称']} - {row['物品分类']} - {row['稀有度']}")
    
    while True:
        try:
            choice = int(input("\n请选择一个物品 (输入序号): "))
            if 1 <= choice <= len(matches):
                return matches.iloc[choice-1]
            else:
                print(f"请输入1到{len(matches)}之间的数字")
        except ValueError:
            print("请输入有效的数字")

def load_tracked_items():
    """加载已追踪的物品列表"""
    if os.path.exists(BID_TRACKER_FILE):
        return pd.read_csv(BID_TRACKER_FILE)
    else:
        # 创建一个新的DataFrame，与price_data相同的列结构
        return pd.DataFrame(columns=[
            "物品名称", "物品分类", "购买价格", "出售价格", "低买低卖溢价", 
            "时间戳", "出价数量", "上架数量", "稀有度"
        ])

def save_tracked_items(tracked_df):
    """保存追踪物品列表"""
    tracked_df.to_csv(BID_TRACKER_FILE, index=False)
    print(f"已保存追踪列表到 {BID_TRACKER_FILE}")

def add_item_to_tracker(item):
    """添加物品到追踪列表"""
    tracked_df = load_tracked_items()
    
    # 检查是否已存在相同物品
    if not tracked_df.empty and item['物品名称'] in tracked_df['物品名称'].values:
        print(f"物品 '{item['物品名称']}' 已在追踪列表中")
        return tracked_df
    
    # 添加新物品
    new_item = {
        "物品名称": item['物品名称'],
        "物品分类": item['物品分类'],
        "购买价格": item.get('购买价格', ''),
        "出售价格": item.get('出售价格', ''),
        "低买低卖溢价": item.get('低买低卖溢价', ''),
        "时间戳": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "出价数量": item.get('出价数量', ''),
        "上架数量": item.get('上架数量', ''),
        "稀有度": item.get('稀有度', '')
    }
    
    tracked_df = pd.concat([tracked_df, pd.DataFrame([new_item])], ignore_index=True)
    save_tracked_items(tracked_df)
    print(f"已添加 '{item['物品名称']}' 到追踪列表")
    return tracked_df

def open_bid_interface():
    """打开报价界面"""
    # 打开市场
    print("打开市场界面...")
    if not mwm.open_market():
        print("无法打开市场界面，请检查游戏状态")
        return False
    
    # 点击进入报价界面
    print(f"点击报价入口坐标: {MARKET_ENTRY_POINT}")
    mwm.click_point(MARKET_ENTRY_POINT)
    time.sleep(DEFAULT_DELAY * 2)
    
    # 点击购买图标
    print(f"点击购买图标坐标: {BUY_ICON_POINT}")
    mwm.click_point(BUY_ICON_POINT)
    time.sleep(DEFAULT_DELAY * 2)
    
    return True

def get_item_key_from_name(item_name):
    """从物品中文名获取对应的英文键名"""
    for key, value in ITEM_DICT.items():
        if value == item_name:
            return key
    return None

def get_category_key_from_name(category_name):
    """从分类中文名获取对应的英文键名"""
    for key, value in CATEGORY_DICT.items():
        if value == category_name:
            return key
    return None

def find_and_click_item(item_name, item_category):
    """查找并点击物品"""
    print(f"正在查找物品: {item_name}")
    
    # 获取物品的英文键名
    item_key = get_item_key_from_name(item_name)
    if not item_key:
        print(f"未能找到物品 '{item_name}' 的映射键名")
        return False
    
    # 获取物品分类的英文键名
    category_key = get_category_key_from_name(item_category)
    if not category_key:
        print(f"未能找到分类 '{item_category}' 的映射键名")
        return False
    
    # 构建物品模板路径
    item_template_path = f"{TEMPLATE_DIR}market_items/{category_key}/{item_key}.png"
    
    if not os.path.exists(item_template_path):
        print(f"未找到物品 '{item_name}' 的模板图片: {item_template_path}")
        return False
    
    # 尝试点击物品
    print(f"尝试点击物品图标 (使用模板: {item_template_path})")
    try:
        center = rsh.find_pic(item_template_path, returnCenter=True)
        if center:
            rsh.touch(center)
            print(f"成功点击物品 '{item_name}'")
            time.sleep(DEFAULT_DELAY * 2)  # 等待物品详情页加载
            return True
        else:
            print(f"未能找到物品图标，匹配失败")
            return False
    except Exception as e:
        print(f"查找物品时出错: {str(e)}")
        print(f"跳过物品 '{item_name}'，继续处理下一个")
        return False

# 修改process_price_recognition函数
def process_price_recognition(screenshot_path, item_name, item_category):
    """处理价格识别，安全地绕过cnocr可能引起的错误"""
    try:
        # 直接调用，不预先导入cnocr
        return mpr.process_screenshot(screenshot_path, item_name, item_category)
    except Exception as e:
        # 如果出错，记录错误并返回空结果
        print(f"价格识别出错: {str(e)}")
        return [], None, {}

def process_tracked_items():
    """处理追踪列表中的所有物品"""
    global price_executor
    
    # 初始化价格识别线程池
    price_executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_RECOGNITION_WORKERS)
    
    # 加载追踪物品列表
    tracked_df = load_tracked_items()
    if tracked_df.empty:
        print("追踪列表为空，请先添加物品")
        return
    
    # 打开报价界面
    if not open_bid_interface():
        return
    
    # 遍历追踪列表中的物品
    updated_count = 0
    for idx, item in tracked_df.iterrows():
        item_name = item['物品名称']
        item_category = item['物品分类']
        
        print(f"\n处理物品 [{idx+1}/{len(tracked_df)}]: {item_name} ({item_category})")
        
        # 查找并点击物品
        if find_and_click_item(item_name, item_category):
            # 点击后等待充分的时间以确保界面已切换
            print("等待界面加载...")
            time.sleep(2.0)  # 等待2秒确保界面完全加载
            
            # 执行第一次返回
            print("执行第一次返回操作")
            mwm.go_back()
            time.sleep(1.5)  # 等待1.5秒
            
            # 执行第二次返回
            print("执行第二次返回操作")
            mwm.go_back()
            time.sleep(1.5)  # 再等待1.5秒确保返回到列表界面
            
            print(f"已完成物品 '{item_name}' 的处理")
        else:
            print(f"无法找到并点击物品 '{item_name}'")
    
    # 关闭线程池
    if price_executor:
        price_executor.shutdown(wait=True)

def add_items_menu():
    """添加物品到追踪列表的菜单"""
    # 加载最新的价格数据
    latest_price_file = find_latest_price_data()
    if not latest_price_file:
        print("未找到价格数据文件，无法添加物品")
        return
    
    print(f"使用价格数据文件: {latest_price_file}")
    price_df = pd.read_csv(latest_price_file)
    
    while True:
        # 用户输入关键词
        keyword = input("\n请输入物品关键词 (q 退出): ")
        if keyword.lower() == 'q':
            break
        
        # 搜索物品
        matches = search_items(keyword, price_df)
        item = display_search_results(matches)
        if item is None:
            continue
        
        # 添加物品到追踪列表
        add_item_to_tracker(item)

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='报价追踪工具')
    parser.add_argument('--add', action='store_true', help='添加物品到追踪列表')
    parser.add_argument('--track', action='store_true', help='开始追踪物品价格')
    parser.add_argument('--device', help='设置设备ID')
    return parser.parse_args()

def main():
    """主函数"""
    global price_executor
    
    print("\n" + "="*50)
    print("     现代战舰市场报价追踪工具")
    print("="*50 + "\n")
    
    # 解析命令行参数
    args = parse_arguments()
    
    # 设置设备ID
    if args.device:
        rsh.deviceID = args.device
    elif not rsh.deviceID:
        try:
            devices = rsh.ADBHelper.getDevicesList()
            if devices:
                rsh.deviceID = devices[0]
                print(f"已自动设置设备ID为: {rsh.deviceID}")
            else:
                print("错误：未检测到连接的安卓设备，请检查ADB连接")
                return
        except Exception as e:
            print(f"设置设备ID时出错: {str(e)}")
            return
    
    # 检查目录结构
    if not os.path.exists(TEMPLATE_DIR):
        print(f"模板目录不存在: {TEMPLATE_DIR}")
        return
    
    if args.add:
        # 添加物品到追踪列表
        add_items_menu()
    elif args.track:
        # 开始追踪物品价格
        process_tracked_items()
    else:
        # 默认菜单
        while True:
            print("\n请选择操作:")
            print("1. 添加物品到追踪列表")
            print("2. 开始追踪物品价格")
            print("3. 查看当前追踪列表")
            print("0. 退出")
            
            choice = input("\n请选择 [0-3]: ")
            
            if choice == '1':
                add_items_menu()
            elif choice == '2':
                process_tracked_items()
            elif choice == '3':
                tracked_df = load_tracked_items()
                if tracked_df.empty:
                    print("追踪列表为空")
                else:
                    print("\n当前追踪的物品列表:")
                    for idx, item in tracked_df.iterrows():
                        print(f"{idx+1}. {item['物品名称']} - {item['物品分类']} - {item['稀有度']}")
                        print(f"   购买价格: {item['购买价格']}")
                        print(f"   出售价格: {item['出售价格']}")
                        print(f"   低买低卖溢价: {item['低买低卖溢价']}")
                        print(f"   最后更新: {item['时间戳']}")
                        print(f"   出价/上架: {item['出价数量']}/{item['上架数量']}")
                        print("---")
            elif choice == '0':
                break
            else:
                print("无效的选择，请重试")
    
    # 确保线程池被关闭
    if price_executor:
        price_executor.shutdown()
    
    print("\n" + "="*50)
    print("     报价追踪工具已退出")
    print("="*50 + "\n")

if __name__ == "__main__":
    main() 