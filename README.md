# 现代战舰市场工具

现代战舰市场工具是一个集成了**市场分析**和**游戏自动化**的综合性平台。项目包含用于交易、查询和分析现代战舰游戏内物品和资源的Web工具，以及强大的游戏自动化脚本系统。该项目使用React构建，提供直观的用户界面和强大的功能。

## 功能特点

- 战舰市场价格实时追踪
- 历史价格走势分析
- 物品交易平台
- 用户交易记录管理
- 战舰配件和资源库
- 市场数据可视化

## 自动化工具 (AgentScript)

除了市场工具外，本项目还包含强大的游戏自动化脚本工具：

### 🚀 快速开始（新手推荐）

**📋 [傻瓜式启动指南 - ★★★傻瓜式启动指南.md](./AgentScript/★★★傻瓜式启动指南.md)**

**零基础用户推荐从这里开始**，提供完整的一站式配置流程：

- ✅ **准备工作清单** - 硬件、软件准备要求
- 💻 **环境自动安装** - 一键安装Python环境和依赖
- 📱 **设备连接检查** - 自动检测设备状态和分辨率
- 🎯 **模板配置工具** - 图形化界面配置不同分辨率适配
- 🤖 **启动自动化** - 简单几步开始代肝

### 🤖 自动战斗脚本（核心功能）

**📋 [完整自动战斗使用文档 - README_AUTO_BATTLE.md](./AgentScript/README_AUTO_BATTLE.md)**

这是本项目的**重点功能**，提供完全自动化的现代战舰战斗体验：

- 🤖 **全自动战斗** - 自动识别游戏状态，执行战斗，无需人工干预
- 📊 **详细数据统计** - 战斗场次、奖励收益、战斗时间、每小时效率统计
- 🎯 **智能状态识别** - OCR奖励识别、VIP状态检测、战斗模式判断
- ⚙️ **高级参数调节** - 起手时间校准、长按补偿等精细化设置
- 💰 **实时收益追踪** - 美元、黄金奖励自动统计，实时计算收益效率
- 🕐 **战斗时间分析** - 单次战斗时长、循环时间统计，优化效率
- 🖥️ **图形化界面** - PyQt5界面，操作简单直观

### 📹 操作录制工具

- 📹 **操作录制回放** - 录制游戏操作并自动回放，为自动战斗提供操作序列
- ⚙️ **智能参数调节** - 长按补偿、预设时长等高级功能  
- 🎮 **实时控制** - 边录制边执行ADB操作，真实控制设备

**[📁 查看AgentScript录制工具详细文档 →](./AgentScript/README.md)**

---

## 开发环境设置

### 前提条件

- Node.js (14.x 或更高版本)
- npm 或 yarn

### 安装

1. 克隆仓库
```bash
git clone https://github.com/yourusername/modern-warship-market.git
cd modern-warship-market
```

2. 安装依赖
```bash
npm install
# 或
yarn install
```

3. 启动开发服务器
```bash
npm start
# 或
yarn start
```

应用将在 [http://localhost:3000](http://localhost:3000) 运行。

## 项目构建

```bash
npm run build
# 或
yarn build
```

构建文件将生成在 `build` 目录中。

## 数据源

项目数据存储在 `market_data` 目录中（已在gitignore中忽略）。如需获取测试数据，请联系项目维护者。

## 技术栈

### 前端市场工具
- React
- Redux（状态管理）
- Chart.js（数据可视化）
- Firebase（认证与数据存储）
- Material-UI（UI组件）

### 自动化脚本工具 (AgentScript)
- Python 3.x
- PyQt5（图形界面）
- OpenCV（图像处理）
- CnOcr（OCR文字识别）
- ADB（安卓调试桥接）

## 贡献指南

1. Fork 这个仓库
2. 创建你的特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交你的更改 (`git commit -m '添加了一些惊人的特性'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建一个 Pull Request

## 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 联系方式

项目维护者 MatthewHA233
QQ 1528919811

项目链接: [https://github.com/MatthewHA233/modern-warship-market](https://github.com/MatthewHA233/modern-warship-market)
