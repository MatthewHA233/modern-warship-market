import os
import glob
import pandas as pd
from datetime import datetime, timedelta
import re
from rich.console import Console
from rich.theme import Theme

# 修改自定义主题，添加更多样式
custom_theme = Theme({
    "positive": "green",
    "negative": "red",
    "item": "purple",
    "title": "bold yellow",
    "subtitle": "bold cyan",
    "info": "blue",
    "category": "magenta",
    "epic": "bright_magenta",  # 史诗稀有度
    "rare": "bright_blue",    # 稀有稀有度
    "uncommon": "bright_green", # 改良稀有度
    "common": "white",        # 普通稀有度
    "highlight": "bold cyan",  # 高亮信息
    "warning": "yellow"        # 警告信息
})
console = Console(theme=custom_theme)

def find_latest_price_data():
    """查找最新的价格数据文件"""
    price_files = glob.glob("market_data/price_data_*.csv")
    if not price_files:
        print("未找到价格数据文件")
        return None
    return max(price_files)

def search_items(keyword, price_df):
    """根据关键词搜索物品"""
    # 使用正则表达式进行不区分大小写的搜索
    pattern = re.compile(keyword, re.IGNORECASE)
    matches = price_df[price_df['物品名称'].str.contains(pattern, na=False)]
    return matches

def display_search_results(matches):
    """显示搜索结果并让用户选择"""
    if matches.empty:
        console.print("\n[warning]未找到匹配的物品[/warning]")
        return None
    
    console.print("\n[subtitle]搜索结果:[/subtitle]")
    for i, (_, row) in enumerate(matches.iterrows()):
        rarity = row['稀有度']
        rarity_style = "common"
        if "史诗" in rarity:
            rarity_style = "epic"
        elif "稀有" in rarity:
            rarity_style = "rare"
        elif "改良" in rarity:
            rarity_style = "uncommon"
            
        console.print(
            f"{i+1}. [item]{row['物品名称']}[/item] - "
            f"[category]{row['物品分类']}[/category] - "
            f"[{rarity_style}]{rarity}[/{rarity_style}]"
        )
    
    while True:
        try:
            choice = int(input("\n请选择一个物品 (输入序号): "))
            if 1 <= choice <= len(matches):
                return matches.iloc[choice-1]
            else:
                console.print(f"[warning]请输入1到{len(matches)}之间的数字[/warning]")
        except ValueError:
            console.print("[warning]请输入有效的数字[/warning]")

def parse_prices(price_str):
    """解析价格字符串中的最低价和最高价"""
    if pd.isna(price_str):
        return None, None
    
    # 去除逗号并提取所有价格
    price_str = str(price_str).replace(',', '')
    prices = re.findall(r'\d+\.?\d*', price_str)
    
    if not prices:
        return None, None
        
    prices = [float(p) for p in prices]
    return min(prices), max(prices)  # 返回最低价和最高价

def extract_date_from_filename(filename):
    """从文件名中提取日期"""
    match = re.search(r'price_data_(\d{8})_', filename)
    if match:
        date_str = match.group(1)
        # 将YYYYMMDD转换为M月D日格式
        year = date_str[0:4]
        month = date_str[4:6].lstrip('0')
        day = date_str[6:8].lstrip('0')
        return f"{month}月{day}日"
    return "未知日期"

def get_price_input(prompt, default=None):
    """获取用户输入的价格"""
    while True:
        try:
            value = input(prompt)
            if not value and default is not None:
                return default
            return float(value)
        except ValueError:
            print("请输入有效的数字")

def calculate_date_from_offset(offset_str):
    """根据偏移值计算日期，1表示昨天，2表示前天，依此类推"""
    try:
        offset = int(offset_str)
        if offset >= 0:
            # 计算偏移日期
            target_date = datetime.now() - timedelta(days=offset)
            return target_date.strftime('%Y-%m-%d')
    except ValueError:
        # 如果不是整数，则假定是日期格式
        pass
    return offset_str

def calculate_profit_summary(profit_df):
    """计算并返回盈利总结"""
    if profit_df.empty:
        return {
            "year": 0,
            "month": 0,
            "week": 0,
            "year_count": 0,
            "month_count": 0,
            "week_count": 0,
        }
    
    # 转换日期列为datetime类型
    profit_df['日期'] = pd.to_datetime(profit_df['日期'])
    
    # 获取当前时间
    now = datetime.now()
    
    # 计算今年的开始
    year_start = datetime(now.year, 1, 1)
    
    # 计算本月的开始
    month_start = datetime(now.year, now.month, 1)
    
    # 计算本周的开始 (假设星期一是一周的开始)
    week_start = now - timedelta(days=now.weekday())
    week_start = datetime(week_start.year, week_start.month, week_start.day)
    
    # 筛选记录并计算盈利总和
    year_records = profit_df[profit_df['日期'] >= year_start]
    month_records = profit_df[profit_df['日期'] >= month_start]
    week_records = profit_df[profit_df['日期'] >= week_start]
    
    return {
        "year": year_records['盈利'].sum(),
        "month": month_records['盈利'].sum(),
        "week": week_records['盈利'].sum(),
        "year_count": len(year_records),
        "month_count": len(month_records),
        "week_count": len(week_records)
    }

def display_daily_profit(profit_df):
    """显示最近30天的每日盈利情况"""
    if profit_df.empty:
        console.print("\n[warning]最近30天没有交易记录[/warning]")
        return
    
    # 确保日期列是datetime类型
    profit_df['日期'] = pd.to_datetime(profit_df['日期'])
    
    # 计算30天前的日期
    thirty_days_ago = datetime.now() - timedelta(days=30)
    
    # 筛选最近30天的记录
    recent_records = profit_df[profit_df['日期'] >= thirty_days_ago]
    
    if recent_records.empty:
        console.print("\n[warning]最近30天没有交易记录[/warning]")
        return
    
    # 创建盈利和亏损的分类
    profit_records = recent_records[recent_records['盈利'] > 0]
    loss_records = recent_records[recent_records['盈利'] < 0]
    
    # 按日期分组
    daily_profit_sum = profit_records.groupby('日期')['盈利'].sum().to_dict() if not profit_records.empty else {}
    daily_loss_sum = loss_records.groupby('日期')['盈利'].sum().to_dict() if not loss_records.empty else {}
    
    # 按日期分组并计算每日盈利
    daily_stats = recent_records.groupby('日期').agg(
        净赚总额=('盈利', 'sum'),
        交易数量=('盈利', 'count')
    )
    
    # 添加盈利和亏损列
    daily_stats['盈利额'] = daily_stats.index.map(lambda date: daily_profit_sum.get(date, 0))
    daily_stats['亏损额'] = daily_stats.index.map(lambda date: daily_loss_sum.get(date, 0))
    
    # 按日期升序排序（最近的日期在后）
    daily_stats = daily_stats.sort_index(ascending=True)
    
    console.print("\n[title]=== 最近30天每日盈利 ===[/title]")
    
    # 打印每一行数据，使用非表格形式
    for date, row in daily_stats.iterrows():
        date_str = date.strftime('%Y-%m-%d')
        total_amount = row['净赚总额']
        trade_count = int(row['交易数量'])
        profit_sum = row['盈利额']
        loss_sum = row['亏损额']
        
        # 构建基本字符串
        base_info = f"{date_str} | "
        
        # 净赚部分
        if total_amount > 0:
            net_profit_text = f"净赚:{total_amount:.0f}"
            console.print(base_info, f"[positive]{net_profit_text}[/positive]", f" | 交易数:{trade_count}", end="")
        elif total_amount < 0:
            net_loss_text = f"亏损:{abs(total_amount):.0f}"
            console.print(base_info, f"[negative]{net_loss_text}[/negative]", f" | 交易数:{trade_count}", end="")
        else:
            console.print(base_info, f"净赚:0", f" | 交易数:{trade_count}", end="")
        
        # 盈利部分
        if profit_sum > 0:
            console.print(f" | [positive]盈利:{profit_sum:.0f}[/positive]", end="")
        else:
            console.print(f" | 盈利:0", end="")
            
        # 亏损部分
        if loss_sum < 0:
            console.print(f" | [negative]亏损:{abs(loss_sum):.0f}[/negative]")
        else:
            console.print(f" | 亏损:0")
    
    # 计算并显示汇总信息
    total_amount = daily_stats['净赚总额'].sum()
    total_trades = daily_stats['交易数量'].sum()
    total_profit_sum = daily_stats['盈利额'].sum()
    total_loss_sum = daily_stats['亏损额'].sum()
    
    console.print("─" * 45)  # 底部分隔线
    
    # 显示总计信息
    if total_amount > 0:
        console.print(f"总计: [positive]净赚:{total_amount:.0f}[/positive], 交易数:{int(total_trades)}", end="")
    elif total_amount < 0:
        console.print(f"总计: [negative]亏损:{abs(total_amount):.0f}[/negative], 交易数:{int(total_trades)}", end="")
    else:
        console.print(f"总计: 净赚:0, 交易数:{int(total_trades)}", end="")
        
    if total_profit_sum > 0:
        console.print(f", [positive]盈利:{total_profit_sum:.0f}[/positive]", end="")
    else:
        console.print(f", 盈利:0", end="")
        
    if total_loss_sum < 0:
        console.print(f", [negative]亏损:{abs(total_loss_sum):.0f}[/negative]")
    else:
        console.print(f", 亏损:0")

def display_profit_summary(profit_df):
    """显示净赚总结"""
    # 显示最近100条交易记录
    display_recent_transactions(profit_df)
    
    # 显示最近30天每日盈利
    display_daily_profit(profit_df)
    
    summary = calculate_profit_summary(profit_df)
    
    console.print("\n[title]=== 净赚总结 ===[/title]")
    
    year_profit = summary['year']
    month_profit = summary['month']
    week_profit = summary['week']
    
    year_style = "positive" if year_profit > 0 else "negative" if year_profit < 0 else "info"
    month_style = "positive" if month_profit > 0 else "negative" if month_profit < 0 else "info"
    week_style = "positive" if week_profit > 0 else "negative" if week_profit < 0 else "info"
    
    console.print(f"今年净赚: [{year_style}]{year_profit:.0f}[/{year_style}] ({summary['year_count']}笔交易)")
    console.print(f"本月净赚: [{month_style}]{month_profit:.0f}[/{month_style}] ({summary['month_count']}笔交易)")
    console.print(f"本周净赚: [{week_style}]{week_profit:.0f}[/{week_style}] ({summary['week_count']}笔交易)")
    
    console.print("\n[info]按 Enter 键退出...[/info]", end="")
    input()

def display_recent_transactions(profit_df):
    """显示最近100条交易记录"""
    if profit_df.empty:
        console.print("\n[warning]没有交易记录[/warning]")
        return
    
    # 确保日期列是datetime类型
    profit_df['日期'] = pd.to_datetime(profit_df['日期'])
    
    # 按日期升序排序并获取前100条记录
    recent_records = profit_df.sort_values('日期', ascending=True).tail(100)
    
    if recent_records.empty:
        console.print("\n[warning]没有交易记录[/warning]")
        return
    
    console.print("\n[title]=== 最近100条交易记录 ===[/title]")
    
    # 打印每条记录
    for i, (_, row) in enumerate(recent_records.iterrows()):
        profit_value = row['盈利']
        
        # 根据盈利是正还是负，显示"盈利"或"亏损"
        if profit_value > 0:
            profit_text = f"盈利:{profit_value:.0f}"
            profit_style = "positive"
        elif profit_value < 0:
            # 对于负值，取绝对值并显示为亏损
            profit_text = f"亏损:{abs(profit_value):.0f}"
            profit_style = "negative"
        else:
            profit_text = f"盈利:0"
            profit_style = ""
            
        item_name = row['物品名称']
        
        # 构建基本信息字符串，但不包含物品名称
        prefix = f"{i+1}. {row['日期'].strftime('%Y-%m-%d')} "
        suffix = f" - 买入:{row['购买价格']:.0f} 卖出:{row['出售价格']:.0f} "
        
        # 根据盈利正负使用不同颜色打印
        if profit_style:
            console.print(prefix, f"[item]{item_name}[/item]", suffix, f"[{profit_style}]{profit_text}[/{profit_style}]")
        else:
            console.print(prefix, f"[item]{item_name}[/item]", suffix, profit_text)

def add_profit_record():
    """添加新的盈利记录"""
    # 加载最新的价格数据
    latest_price_file = find_latest_price_data()
    if not latest_price_file:
        return
    
    console.print(f"使用价格数据文件: [info]{latest_price_file}[/info]")
    price_df = pd.read_csv(latest_price_file)
    date_str = extract_date_from_filename(latest_price_file)
    
    # 加载现有的盈利数据
    profit_file = "market_data/盈利.csv"
    if os.path.exists(profit_file):
        profit_df = pd.read_csv(profit_file)
    else:
        profit_df = pd.DataFrame(columns=["物品名称", "物品分类", "购买价格", "出售价格", "盈利", "日期", "稀有度"])
    
    while True:
        # 用户输入关键词
        keyword = input("\n请输入物品关键词 (q 退出): ")
        if keyword.lower() == 'q':
            display_profit_summary(profit_df)
            break
        
        # 搜索物品
        matches = search_items(keyword, price_df)
        item = display_search_results(matches)
        if item is None:
            continue
        
        # 先获取出售价格
        min_sell, max_sell = parse_prices(item.get('出售价格', ''))
        tax_adjusted_price = int(min_sell * 0.8) if min_sell else 0
        sell_hint_str = f" [{date_str}最低售价(税后): {tax_adjusted_price}，为市场价x80%]" if min_sell else ""
        sell_price = get_price_input(f"请输入出售价格{sell_hint_str}: ")
        
        # 再获取购买价格
        min_buy, max_buy = parse_prices(item.get('购买价格', ''))
        buy_hint_str = f" [{date_str}最高买价: {int(max_buy) if max_buy else 0}]" if max_buy else ""
        buy_price = get_price_input(f"请输入购买价格{buy_hint_str}: ")
        
        # 计算盈利
        profit = sell_price - buy_price
        
        # 获取日期
        today = datetime.now().strftime('%Y-%m-%d')
        date_input = input(f"请输入日期或天数 [默认:{today}, 1=昨天, 2=前天...]: ") or today
        date = calculate_date_from_offset(date_input)
        
        # 添加新记录
        new_record = {
            "物品名称": item['物品名称'],
            "物品分类": item['物品分类'],
            "购买价格": buy_price,
            "出售价格": sell_price,
            "盈利": profit,
            "日期": date,
            "稀有度": item['稀有度']
        }
        
        # 显示要添加的记录
        console.print("\n[subtitle]要添加的记录:[/subtitle]")
        console.print(f"物品名称: [item]{new_record['物品名称']}[/item]")
        console.print(f"物品分类: [category]{new_record['物品分类']}[/category]")
        console.print(f"购买价格: {new_record['购买价格']:.0f}")
        console.print(f"出售价格: {new_record['出售价格']:.0f}")
        
        profit_value = new_record['盈利']
        profit_style = "positive" if profit_value > 0 else "negative" if profit_value < 0 else "info"
        profit_sign = "+" if profit_value > 0 else ""
        console.print(f"盈利: [{profit_style}]{profit_sign}{profit_value:.0f}[/{profit_style}]")
        
        console.print(f"日期: {new_record['日期']}")
        
        # 根据稀有度选择样式
        rarity = new_record['稀有度']
        rarity_style = "common"
        if "史诗" in rarity:
            rarity_style = "epic"
        elif "稀有" in rarity:
            rarity_style = "rare"
        elif "改良" in rarity:
            rarity_style = "uncommon"
            
        console.print(f"稀有度: [{rarity_style}]{rarity}[/{rarity_style}]")
        
        confirm = input("\n确认添加? (y/n): ")
        if confirm.lower() == 'y':
            profit_df = pd.concat([profit_df, pd.DataFrame([new_record])], ignore_index=True)
            profit_df.to_csv(profit_file, index=False)
            console.print(f"[positive]记录已添加到 {profit_file}[/positive]")
        else:
            console.print("[warning]已取消添加[/warning]")

if __name__ == "__main__":
    console.print("[title]== 盈利记录工具 ==[/title]")
    add_profit_record() 