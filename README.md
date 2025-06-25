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

- 🤖 **自动战斗脚本** - 自动执行战斗操作，解放双手
- 📹 **操作录制回放** - 录制游戏操作并自动回放
- 📊 **战斗数据统计** - 详细的战斗收益和时间统计
- ⚙️ **智能参数调节** - 长按补偿、起手时间校准等高级功能
- 🎯 **OCR奖励识别** - 自动识别战斗结算奖励

**[📁 查看AgentScript自动化工具详细文档 →](./AgentScript/README.md)**

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

项目维护者 - 邮箱地址 - 网站

项目链接: [https://github.com/MatthewHA233/modern-warship-market](https://github.com/MatthewHA233/modern-warship-market)
