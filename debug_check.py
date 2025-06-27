#!/usr/bin/env python3
import pandas as pd

# 读取CSV文件
df = pd.read_csv('./market_data/报价追踪.csv')

print("=== CSV文件检查 ===")
print("列名:", list(df.columns))
print("数据形状:", df.shape)

print("\n=== 第4行数据检查 ===")
row = df.iloc[3]  # 第4行（索引3）
print("物品名称:", row['物品名称'])
print("本人购买价格原始值:", repr(row['本人购买价格']))
print("本人购买价格类型:", type(row['本人购买价格']))
print("是否为NaN:", pd.isna(row['本人购买价格']))

# 模拟AutoTradeGUI中的parse_price_record逻辑
print("\n=== 模拟解析逻辑 ===")
own_buying_price = row.get('本人购买价格', '')
print("get()获取到的值:", repr(own_buying_price))

# 检查条件判断
print("条件 pd.notna(own_buying_price):", pd.notna(own_buying_price))
print("条件 own_buying_price:", bool(own_buying_price))
print("条件 str(own_buying_price).strip():", repr(str(own_buying_price).strip()))

# 模拟完整的处理流程
if pd.notna(own_buying_price) and own_buying_price and str(own_buying_price).strip():
    print("✓ 通过了所有条件检查")
    try:
        own_price_clean = str(own_buying_price).replace(',', '').strip()
        if own_price_clean:
            own_price_num = int(own_price_clean)
            print("✓ 成功转换为数字:", own_price_num)
        else:
            print("✗ 清理后为空字符串")
    except Exception as e:
        print("✗ 转换数字时出错:", str(e))
else:
    print("✗ 未通过条件检查")

print("\n=== 所有行的本人价格检查 ===")
for i, row in df.iterrows():
    own_buy = row.get('本人购买价格', '')
    own_sell = row.get('本人售出价格', '')
    print(f"行{i+1}: 本人购买={repr(own_buy)}, 本人售出={repr(own_sell)}") 