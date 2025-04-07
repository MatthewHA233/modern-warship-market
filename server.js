const express = require('express');
const fs = require('fs');
const path = require('path');
const csv = require('csv-parser');
const { exec, spawn } = require('child_process');
const app = express();
const port = 3001;

// 添加JSON解析中间件
app.use(express.json());

// 静态文件服务
app.use(express.static('build'));

// SSE客户端列表
const clients = [];

// 获取最近的CSV文件列表（最多5个）
app.get('/api/getRecentPriceFiles', (req, res) => {
  const dataDir = path.join(__dirname, 'market_data');
  
    if (!fs.existsSync(dataDir)) {
      fs.mkdirSync(dataDir, { recursive: true });
    return res.json({ files: [] });
    }
    
  try {
    const files = fs.readdirSync(dataDir)
      .filter(file => file.startsWith('price_data_') && file.endsWith('.csv'))
      .sort((a, b) => b.localeCompare(a))
      .slice(0, 5);
    
    res.json({ files });
  } catch (error) {
    console.error('获取文件列表失败:', error);
    res.status(500).json({ error: '服务器内部错误' });
  }
});

// 获取最新的CSV文件
app.get('/api/getLatestPriceFile', (req, res) => {
  const dataDir = path.join(__dirname, 'market_data');
  
  if (!fs.existsSync(dataDir)) {
    return res.json({ fileName: null });
  }
  
  try {
    const files = fs.readdirSync(dataDir)
      .filter(file => file.startsWith('price_data_') && file.endsWith('.csv'))
      .sort((a, b) => b.localeCompare(a));
    
    res.json({ fileName: files.length > 0 ? files[0] : null });
  } catch (error) {
    console.error('获取最新文件失败:', error);
    res.status(500).json({ error: '服务器内部错误' });
  }
});

// 读取CSV文件内容
app.get('/api/getPriceData', (req, res) => {
  const fileName = req.query.file;
  
  if (!fileName) {
    return res.status(400).json({ error: '未指定文件名' });
  }
  
  const filePath = path.join(__dirname, 'market_data', fileName);
  
  if (!fs.existsSync(filePath)) {
    return res.status(404).json({ error: '文件不存在' });
  }
  
  const results = [];
  
  fs.createReadStream(filePath)
    .pipe(csv())
    .on('data', (data) => {
      results.push({
        name: data['物品名称'],
        category: data['物品分类'],
        buyingPrices: data['购买价格'],
        sellingPrices: data['出售价格'],
        spread: data['低买低卖溢价'],
        timestamp: data['时间戳'],
        bidCount: data['出价数量'] || '0',
        listingCount: data['上架数量'] || '0',
        rarity: data['稀有度']
      });
    })
    .on('end', () => {
      res.json(results);
    })
    .on('error', (error) => {
      console.error('读取CSV文件失败:', error);
      res.status(500).json({ error: '读取文件失败' });
    });
});

// 新增API: 脚本状态监听 (SSE)
app.get('/api/scriptStatus', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  
  res.write('data: {"status":"connected"}\n\n');
  
  const clientId = Date.now();
  clients.push({
    id: clientId,
    res
  });
  
  req.on('close', () => {
    const index = clients.findIndex(client => client.id === clientId);
    if (index !== -1) {
      clients.splice(index, 1);
    }
  });
});

// 向所有SSE客户端发送更新
function sendUpdate(message) {
  clients.forEach(client => {
    client.res.write(`data: ${JSON.stringify({message})}\n\n`);
  });
}

// 新增API: 保存预设
app.post('/api/savePreset', (req, res) => {
  const { name, items } = req.body;
  
  if (!name || !items || !Array.isArray(items)) {
    return res.status(400).json({ success: false, error: '无效数据' });
  }
  
  try {
    const presetsDir = path.join(__dirname, 'presets');
    if (!fs.existsSync(presetsDir)) {
      fs.mkdirSync(presetsDir, { recursive: true });
    }
    
    const presetPath = path.join(presetsDir, `preset_${Date.now()}.json`);
    const presetData = {
      name,
      timestamp: new Date().toISOString(),
      items: items.map(item => ({
        name: item.name,
        category: item.category
      }))
    };
    
    fs.writeFileSync(presetPath, JSON.stringify(presetData, null, 2));
    res.json({ success: true });
  } catch (error) {
    console.error('保存预设失败:', error);
    res.status(500).json({ success: false, error: '保存预设失败' });
  }
});

// 新增API: 获取预设列表
app.get('/api/getPresets', (req, res) => {
  try {
    const presetsDir = path.join(__dirname, 'presets');
    if (!fs.existsSync(presetsDir)) {
      fs.mkdirSync(presetsDir, { recursive: true });
      return res.json({ success: true, presets: [] });
    }
    
    const files = fs.readdirSync(presetsDir)
      .filter(file => file.startsWith('preset_') && file.endsWith('.json'));
    
    const presets = files.map(file => {
      try {
        return JSON.parse(fs.readFileSync(path.join(presetsDir, file), 'utf8'));
      } catch (e) {
        return null;
      }
    }).filter(Boolean);
    
    res.json({ success: true, presets });
  } catch (error) {
    console.error('获取预设失败:', error);
    res.status(500).json({ success: false, error: '获取预设失败' });
  }
});

// 生成命令并复制到剪贴板
app.post('/api/getScriptCommand', (req, res) => {
  const { startCategory, startItem, selectedItems } = req.body;
  let presetFilePath = null;
  
  try {
    // 如果有选定物品，创建预设文件
    if (selectedItems && selectedItems.length > 0) {
      // 确保presets目录存在
      const presetsDir = path.join(__dirname, 'presets');
      if (!fs.existsSync(presetsDir)) {
        fs.mkdirSync(presetsDir, { recursive: true });
      }
      
      // 创建预设文件
      const presetFileName = `temp_preset_${Date.now()}.json`;
      presetFilePath = path.join(presetsDir, presetFileName);
      
      console.log('预设物品列表:', selectedItems);
      
      fs.writeFileSync(presetFilePath, JSON.stringify({
        name: "临时预设",
        timestamp: new Date().toISOString(),
        items: selectedItems.map(item => ({
          name: item.name,
          category: item.category,
          original_name: item.name,
          is_display_name: true
        }))
      }, null, 2));
      
      console.log(`已创建预设文件: ${presetFilePath}`);
    }
    
    // 构建完整的命令行命令
    let command = `cd "${__dirname}" && py ModernWarshipMarket.py`;
    
    // 添加参数
    command += ` --start_category ${startCategory || 0} --start_item ${startItem || 0}`;
    
    // 如果有预设，添加预设参数
    if (presetFilePath) {
      command += ` --preset "${presetFilePath}"`;
    }
    
    // 返回命令给前端
    res.json({ 
      success: true, 
      command: command,
      presetFile: presetFilePath,
      absolutePath: __dirname
    });
    
  } catch (error) {
    console.error('创建命令失败:', error);
    res.status(500).json({ 
      success: false, 
      error: '创建命令失败: ' + error.message 
    });
  }
});

// 原有的通配符路由
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'build', 'index.html'));
});

app.listen(port, () => {
  console.log(`服务器运行在 http://localhost:${port}`);
}); 