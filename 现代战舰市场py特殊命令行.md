# 现代战舰市场脚本命令行功能详解

## 概述

`ModernWarshipMarket.py` 提供了丰富的命令行参数，支持灵活的市场数据采集配置。

## 命令行参数详解

### 基础执行控制

#### `--start_category <数字>`
- **功能**: 指定起始分类索引（从0开始计数）
- **默认值**: 0（第一个分类）
- **示例**: 
  ```bash
  py ModernWarshipMarket.py --start_category 2  # 从第3个分类开始
  ```

#### `--start_item <数字>`
- **功能**: 指定起始物品索引（从0开始计数）
- **默认值**: 0（分类中第一个物品）
- **示例**: 
  ```bash
  py ModernWarshipMarket.py --start_item 15  # 从第16个物品开始
  ```

#### `--preset <文件路径>`
- **功能**: 使用预设物品清单，只处理指定物品
- **文件格式**: JSON文件，包含物品名称和分类信息
- **示例**: 
  ```bash
  py ModernWarshipMarket.py --preset "presets/high_value_items.json"
  ```

### 输出文件定制

#### `--output <文件名>`
- **功能**: 自定义访问日志CSV文件名（不含扩展名）
- **默认**: `market_access_log_YYYYMMDD_HHMMSS.csv`
- **示例**: 
  ```bash
  py ModernWarshipMarket.py --output "daily_scan"  # 生成 daily_scan.csv
  ```

#### `--price_output <文件名>`
- **功能**: 自定义价格数据CSV文件名（不含扩展名）
- **默认**: `price_data_YYYYMMDD_HH.csv`
- **示例**: 
  ```bash
  py ModernWarshipMarket.py --price_output "market_prices"  # 生成 market_prices.csv
  ```

## 实用组合示例

### 场景1: 断点续传
```bash
# 从第2个分类的第10个物品开始继续采集
py ModernWarshipMarket.py --start_category 1 --start_item 9
```

### 场景2: 特定物品采集
```bash
# 只采集预设清单中的高价值物品
py ModernWarshipMarket.py --preset "valuable_items.json" --output "valuable_scan"
```

### 场景3: 完整市场扫描
```bash
# 从头扫描全市场，使用自定义文件名
py ModernWarshipMarket.py --output "full_market_20231201" --price_output "prices_20231201"
```

### 场景4: 增量更新
```bash
# 从特定位置开始，追加到现有数据
py ModernWarshipMarket.py --start_category 3 --output "incremental_update"
```

## 高级功能

### 预设文件格式
预设JSON文件应包含以下结构：
```json
{
  "items": [
    {
      "name": "物品中文名",
      "category": "分类中文名"
    }
  ]
}
```

### 分类索引对照
- 0: 舰艇
- 1: 轰炸机
- 2: 无人机
- 3: 攻击机
- 4: 战斗机
- 5: 直升机
- 6: 无人舰艇
- 7: 鱼雷发射器
- 8: 火箭炮/炸弹
- 9: 对空武器
- 10: 自动炮
- 11: 主炮
- 12: 导弹

### 断点恢复策略
1. 查看上次运行的日志文件
2. 确定最后处理的分类和物品
3. 使用 `--start_category` 和 `--start_item` 参数继续

## 注意事项

1. **索引从0开始**: 第1个分类对应 `--start_category 0`
2. **文件覆盖**: 相同文件名会覆盖已存在文件
3. **路径规则**: 所有CSV文件保存在 `./market_data/` 目录
4. **设备连接**: 确保Android设备已通过ADB连接

## 帮助信息
```bash
py ModernWarshipMarket.py --help
``` 