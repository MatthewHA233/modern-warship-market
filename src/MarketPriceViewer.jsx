import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Table, Slider, Row, Col, Input, Select, Card, Typography, Statistic, Tabs, Switch, Tag, Button, Empty, InputNumber, notification, Popconfirm, Space, Modal, Checkbox, List } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined, ReloadOutlined, DatabaseOutlined, DollarOutlined, PlayCircleOutlined, SettingOutlined, SaveOutlined, FilterOutlined, CopyOutlined, StopOutlined, CameraOutlined } from '@ant-design/icons';
import html2canvas from 'html2canvas';
import './MarketPriceViewer.css';

const { Title, Text } = Typography;
const { Option } = Select;
const { TabPane } = Tabs;

// 稀有度对应的颜色
const rarityColors = {
  '普通': '#9ca3af',
  '改良': '#10b981',
  '稀有': '#3b82f6',
  '史诗': '#f97316',
  '传说': '#8b5cf6'
};

const MarketPriceViewer = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [priceRange, setPriceRange] = useState([0, 200000]);
  const [maxPrice, setMaxPrice] = useState(200000);
  const [searchText, setSearchText] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('全部');
  const [categories, setCategories] = useState(['全部']);
  const [filteredData, setFilteredData] = useState([]);
  const [recentFiles, setRecentFiles] = useState([]);
  const [includeSpecialItems, setIncludeSpecialItems] = useState(false);
  const [sliderRange, setSliderRange] = useState([0, 100]);
  const [expandedRowKeys, setExpandedRowKeys] = useState([]);
  const [activeFileIndex, setActiveFileIndex] = useState(0);
  
  // 脚本控制相关状态
  const [startCategory, setStartCategory] = useState(1);
  const [startItem, setStartItem] = useState(1);
  const [scriptRunning, setScriptRunning] = useState(false);
  const [scriptLog, setScriptLog] = useState('');
  const [showScriptSettings, setShowScriptSettings] = useState(false);
  const [presetModalVisible, setPresetModalVisible] = useState(false);
  const [selectedItems, setSelectedItems] = useState([]);
  const [presetName, setPresetName] = useState('');
  const [presets, setPresets] = useState([]);
  const [exportLoading, setExportLoading] = useState(false);
  const selectedRowsRef = useRef(null);

  // 添加防抖相关状态和引用
  const [debouncedSearchText, setDebouncedSearchText] = useState('');
  const searchTimeoutRef = useRef(null);
  
  // 修改选中项的状态管理
  const [selectedRowKeys, setSelectedRowKeys] = useState([]);

  // 添加文件数据缓存
  const [dataCache, setDataCache] = useState({});

  // 获取最近的CSV文件列表
  const loadRecentFiles = async () => {
    try {
      const response = await fetch('/api/getRecentPriceFiles');
      const { files } = await response.json();
      setRecentFiles(files);
      
      // 如果有文件，加载第一个文件
      if (files && files.length > 0) {
        loadCsvData(files[0]);
      }
    } catch (error) {
      console.error('加载文件列表失败', error);
      notification.error({
        message: '加载失败',
        description: '无法获取最近的数据文件列表'
      });
    }
  };

  // 添加防抖搜索处理函数
  const handleSearchChange = useCallback((e) => {
    const value = e.target.value;
    setSearchText(value);
    
    // 清除之前的定时器
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }
    
    // 设置新的定时器，300ms 后更新实际搜索值
    searchTimeoutRef.current = setTimeout(() => {
      setDebouncedSearchText(value);
    }, 300);
  }, []);
  
  // 清理定时器
  useEffect(() => {
    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
      }
    };
  }, []);

  // 修改过滤数据的 useEffect，使用防抖后的搜索文本
  useEffect(() => {
    const filtered = data.filter(item => {
      // 特殊物品过滤
      if (!includeSpecialItems && item.isSpecial) {
        return false;
      }
      
      // 价格范围过滤 - 特殊物品不受价格区间限制
      const priceInRange = item.isSpecial && includeSpecialItems ? 
        true : // 特殊物品且已启用特殊物品显示，忽略价格区间
        (item.maxBuying >= priceRange[0] && item.maxBuying <= priceRange[1]);
      
      // 名称搜索过滤 - 使用防抖后的搜索文本
      const nameMatch = debouncedSearchText === '' || 
        item.name.toLowerCase().includes(debouncedSearchText.toLowerCase());
      
      // 分类过滤
      const categoryMatch = categoryFilter === '全部' || item.category === categoryFilter;
      
      return priceInRange && nameMatch && categoryMatch;
    });
    
    setFilteredData(filtered);
  }, [data, priceRange, debouncedSearchText, categoryFilter, includeSpecialItems]);

  // 添加选择行变化的处理函数
  const handleSelectChange = (selectedKeys, selectedRows) => {
    // 使用 Set 防止重复
    const uniqueKeys = [...new Set(selectedKeys)];
    setSelectedRowKeys(uniqueKeys);
    
    // 合并新旧选中项，确保不会丢失已选择的物品
    const existingItems = selectedItems.filter(item => 
      !selectedRows.some(selected => selected.key === item.key)
    );
    
    setSelectedItems([...existingItems, ...selectedRows]);
  };

  // 加载特定CSV文件的数据
  const loadCsvData = async (fileName, fileIndex = 0) => {
    setLoading(true);
    try {
      // 先检查缓存中是否有数据
      if (dataCache[fileName]) {
        console.log('使用缓存数据:', fileName);
        
        // 使用缓存的数据
        const cachedData = dataCache[fileName];
        setData(cachedData.data);
        setCategories(cachedData.categories);
        setMaxPrice(cachedData.maxPrice);
        setPriceRange([0, cachedData.maxPrice]);
        setFilteredData(cachedData.data);
        
        // 更新滑块范围
        setSliderRange([0, 100]);
        
        // 保持选中的物品
        if (selectedItems.length > 0) {
          const selectedNames = selectedItems.map(item => item.name);
          const newSelectedItems = cachedData.data.filter(item => selectedNames.includes(item.name));
          const newSelectedKeys = newSelectedItems.map(item => item.key);
          
          // 确保不清除原有选择
          setSelectedItems(prevItems => {
            const combinedItems = [...prevItems];
            newSelectedItems.forEach(item => {
              if (!combinedItems.some(existing => existing.name === item.name)) {
                combinedItems.push(item);
              }
            });
            return combinedItems;
          });
          
          setSelectedRowKeys(prevKeys => [...new Set([...prevKeys, ...newSelectedKeys])]);
        }
        
        setActiveFileIndex(fileIndex);
        setLoading(false);
        return;
      }
      
      // 如果缓存中没有，则从服务器获取
      const csvResponse = await fetch(`/api/getPriceData?file=${fileName}`);
      const csvData = await csvResponse.json();
      
      // 处理数据
      const processedData = csvData.map((item, index) => {
        // 确保所有字段都被正确解析和处理
        const bidCount = parseInt(item.bidCount) || 0;
        const listingCount = parseInt(item.listingCount) || 0;
        const rarity = item.rarity || '普通';
        
        // 分析购买价格和出售价格字符串，提取数值
        const buyingPrices = item.buyingPrices.split(';').map(p => 
          parseInt(p.replace(/,/g, '').trim(), 10)).filter(p => !isNaN(p));
        const sellingPrices = item.sellingPrices.split(';').map(p => 
          parseInt(p.replace(/,/g, '').trim(), 10)).filter(p => !isNaN(p));
        
        // 计算最大最小值
        const maxBuying = buyingPrices.length ? Math.max(...buyingPrices) : 0;
        const minSelling = sellingPrices.length ? Math.min(...sellingPrices) : 0;
        
        // 判断特殊物品
        const isSpecial = item.name.includes('[美]武库舰');
        
        // 确保数值类型的字段被正确解析
        const spread = item.spread !== 'N/A' ? parseInt(item.spread) : null;
        const timestamp = item.timestamp;
        
        // 修正利润率计算公式：使用已有的低买低卖溢价(spread)/(最高求购价+1)*100%
        const profitRatio = maxBuying > 0 && spread !== null ? 
          ((spread) / (maxBuying + 1) * 100).toFixed(1) + '%' : 'N/A';
        
        return {
          key: index,
          name: item.name,
          category: item.category,
          buyingPrices: item.buyingPrices,
          sellingPrices: item.sellingPrices,
          spread: spread,
          timestamp: timestamp,
          maxBuying: maxBuying,
          minSelling: minSelling,
          profitRatio: profitRatio,
          isSpecial: isSpecial,
          bidCount: bidCount,
          listingCount: listingCount,
          rarity: rarity
        };
      });
      
      // 数据排序（默认按溢价从高到低）
      const sortedData = processedData
        .filter(item => item.spread !== null)
        .sort((a, b) => b.spread - a.spread);
      
      // 修改提取所有分类的逻辑
      const allCategories = ['全部'];
      const uniqueCategories = [...new Set(csvData.map(item => item.category))].sort();
      const categories = [...allCategories, ...uniqueCategories];
      
      // 计算最大价格（用于滑块）- 排除特殊物品
      const regularItems = processedData.filter(item => !item.isSpecial);
      const highestRegularPrice = Math.max(...regularItems.map(item => item.maxBuying || 0)) * 1.2;
      
      // 保存到本地状态
      setData(sortedData);
      setCategories(categories);
      setMaxPrice(highestRegularPrice);
      setPriceRange([0, highestRegularPrice]);
      setFilteredData(sortedData);
      
      // 保持选中的物品（改进版本）
      if (selectedItems.length > 0) {
        const selectedNames = selectedItems.map(item => item.name);
        const newSelectedItems = sortedData.filter(item => selectedNames.includes(item.name));
        const newSelectedKeys = newSelectedItems.map(item => item.key);
        
        // 确保不清除原有选择
        setSelectedItems(prevItems => {
          const combinedItems = [...prevItems];
          newSelectedItems.forEach(item => {
            if (!combinedItems.some(existing => existing.name === item.name)) {
              combinedItems.push(item);
            }
          });
          return combinedItems;
        });
        
        setSelectedRowKeys(prevKeys => [...new Set([...prevKeys, ...newSelectedKeys])]);
      }
      
      // 保存到缓存
      setDataCache(prev => ({
        ...prev,
        [fileName]: {
          data: sortedData,
          categories: categories,
          maxPrice: highestRegularPrice,
          timestamp: new Date().getTime()
        }
      }));
      
      setActiveFileIndex(fileIndex);
    } catch (error) {
      console.error('加载数据失败', error);
      notification.error({
        message: '加载失败',
        description: `无法加载文件 ${fileName}`
      });
    } finally {
      setLoading(false);
    }
  };

  // 监听脚本状态更新
  const listenForScriptUpdates = () => {
    // 创建EventSource来接收服务器发送的事件
    const eventSource = new EventSource('/api/scriptStatus');
    
    // 监听消息事件
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.message) {
          // 追加新的日志消息
          setScriptLog(prevLog => prevLog + data.message + '\n');
        }
        
        // 如果消息表明脚本已结束，关闭事件源
        if (data.message && data.message.includes('脚本已结束')) {
          eventSource.close();
          // 刷新数据（延迟几秒，确保文件已生成）
          setTimeout(() => {
            loadRecentFiles();
          }, 3000);
        }
      } catch (error) {
        console.error('解析脚本状态更新失败', error);
      }
    };
    
    // 处理错误
    eventSource.onerror = () => {
      console.error('脚本状态更新连接出错');
      eventSource.close();
    };
  };

  // 在runScript函数之前添加一个新函数
  const getAndCopyScriptCommand = async () => {
    try {
      setScriptRunning(true);
      setScriptLog('正在准备命令...\n');
      
      // 向服务器发送请求获取命令
      const response = await fetch('/api/getScriptCommand', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          startCategory: startCategory - 1, // 转换为0起始的索引
          startItem: startItem - 1, // 转换为0起始的索引
          selectedItems // 选中的物品列表
        }),
      });
      
      const data = await response.json();
      
      if (data.success) {
        // 显示命令
        setScriptLog(`命令已生成:\n\n${data.command}\n\n请复制上面的命令并粘贴到命令行中执行`);
        
        // 创建一个临时输入框，用于复制命令
        const tempInput = document.createElement('input');
        tempInput.value = data.command;
        document.body.appendChild(tempInput);
        tempInput.select();
        document.execCommand('copy');
        document.body.removeChild(tempInput);
        
        // 通知用户命令已复制
        notification.success({
          message: '命令已复制到剪贴板',
          description: '请在命令行中粘贴并执行'
        });
        
        // 显示额外信息
        setScriptLog(prev => prev + `\n\n预设文件路径: ${data.presetFile || '无'}\n工作目录: ${data.absolutePath}`);
        
      } else {
        notification.error({
          message: '生成命令失败',
          description: data.error || '无法生成命令'
        });
      }
    } catch (error) {
      console.error('获取命令失败', error);
      notification.error({
        message: '获取命令失败',
        description: '网络错误，无法获取命令'
      });
      setScriptLog(prev => prev + '\n获取命令失败: ' + error.message);
    } finally {
      // 不要设置scriptRunning为false，让用户可以看到命令
    }
  };

  // 运行脚本函数
  const runScript = async () => {
    try {
      // 显示脚本日志模态框并清空日志
      setScriptRunning(true);
      setScriptLog('正在启动脚本...\n');
      
      // 向服务器发送请求启动脚本
      const response = await fetch('/api/runScript', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          startCategory: startCategory - 1, // 转换为0起始的索引
          startItem: startItem - 1, // 转换为0起始的索引
          selectedItems // 选中的物品列表
        }),
      });

      const data = await response.json();
      
      if (data.success) {
        // 启动成功，开始监听脚本状态
        listenForScriptUpdates();
      } else {
        notification.error({
          message: '启动失败',
          description: data.error || '无法启动脚本'
        });
        setScriptRunning(false);
      }
    } catch (error) {
      console.error('启动脚本失败', error);
      notification.error({
        message: '启动失败',
        description: '网络错误，无法启动脚本'
      });
      setScriptRunning(false);
    }
  };

  // 停止脚本
  const stopScript = async () => {
    try {
      const response = await fetch('/api/stopMarketScript', {
        method: 'POST'
      });
      
      if (response.ok) {
        notification.success({
          message: '停止成功',
          description: '已发送停止命令到脚本'
        });
      } else {
        throw new Error(`HTTP error ${response.status}`);
      }
    } catch (error) {
      console.error('停止脚本失败', error);
      notification.error({
        message: '停止失败',
        description: '无法停止市场脚本: ' + error.message
      });
    } finally {
      setScriptRunning(false);
    }
  };

  // 保存当前过滤项为预设
  const saveCurrentFilterAsPreset = () => {
    // 显示预设名称输入模态框
    setSelectedItems(filteredData.map(item => ({
      name: item.name,
      category: item.category
    })));
    setPresetModalVisible(true);
  };

  // 确认保存预设
  const confirmSavePreset = () => {
    if (!presetName.trim()) {
      notification.warning({
        message: '无法保存',
        description: '请输入预设名称'
      });
      return;
    }
    
    const newPreset = {
      name: presetName,
      items: selectedItems,
      createdAt: new Date().toISOString()
    };
    
    // 保存到本地存储
    const updatedPresets = [...presets, newPreset];
    setPresets(updatedPresets);
    localStorage.setItem('marketPresets', JSON.stringify(updatedPresets));
    
    notification.success({
      message: '保存成功',
      description: `已保存预设"${presetName}"，包含${selectedItems.length}个物品`
    });
    
    // 关闭模态框并重置
    setPresetModalVisible(false);
    setPresetName('');
  };

  // 加载预设
  const loadPreset = (index) => {
    const preset = presets[index];
    if (!preset) return;
    
    setSelectedItems(preset.items);
    notification.success({
      message: '加载成功',
      description: `已加载预设"${preset.name}" (${preset.items.length}个物品)`
    });
    setPresetModalVisible(false);
  };

  // 删除预设
  const deletePreset = (index) => {
    const newPresets = [...presets];
    newPresets.splice(index, 1);
    setPresets(newPresets);
  };

  // 在组件挂载时加载数据
  useEffect(() => {
    loadRecentFiles();
    
    // 加载保存的预设
    const loadSavedPresets = async () => {
      try {
        const response = await fetch('/api/getPresets');
        const data = await response.json();
        if (data.success && data.presets) {
          setPresets(data.presets);
        }
      } catch (error) {
        console.error('加载预设失败', error);
      }
    };
    
    loadSavedPresets();
  }, []);

  // 获取利润率状态样式
  const getProfitRatioStyle = (text) => {
    if (text === 'N/A') return null;
    const value = parseFloat(text);
    if (value > 0) return { className: 'profit-tag profit-tag-positive' };
    if (value < 0) return { className: 'profit-tag profit-tag-negative' };
    return null;
  };

  // 添加一个辅助函数，将稀有度中文名映射到CSS类名
  function getRarityClass(rarity) {
    switch(rarity) {
      case '普通': return 'rarity-normal';
      case '改良': return 'rarity-improved';
      case '稀有': return 'rarity-rare';
      case '史诗': return 'rarity-epic';
      case '传说': return 'rarity-legendary';
      default: return 'rarity-normal';
    }
  }

  // 添加一个价格详情组件
  const PriceDetailPanel = ({ record }) => {
    // 解析价格字符串到数组
    const buyingPrices = record.buyingPrices
      .split(';')
      .map(p => parseInt(p.replace(/,/g, '').trim(), 10))
      .filter(p => !isNaN(p))
      .sort((a, b) => b - a); // 从高到低排序
      
    const sellingPrices = record.sellingPrices 
      .split(';')
      .map(p => parseInt(p.replace(/,/g, '').trim(), 10))
      .filter(p => !isNaN(p))
      .sort((a, b) => a - b); // 从低到高排序
    
    return (
      <div className="price-detail-panel">
        <Row gutter={24}>
          <Col span={12}>
            <Card 
              title={<span style={{color: '#e2e8f0'}}>求购价格列表</span>} 
              className="price-detail-card"
              size="small"
            >
              {buyingPrices.length > 0 ? (
                <ul className="price-list">
                  {buyingPrices.map((price, index) => (
                    <li key={`buy-${index}`} className="price-item price-item-buy">
                      <span>{price.toLocaleString()}</span>
                      {index === 0 && <Tag color="#f97316">最高价</Tag>}
                    </li>
                  ))}
                </ul>
              ) : (
                <Empty description="无求购价格数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              )}
            </Card>
          </Col>
          <Col span={12}>
            <Card 
              title={<span style={{color: '#e2e8f0'}}>售出价格列表</span>} 
              className="price-detail-card"
              size="small"
            >
              {sellingPrices.length > 0 ? (
                <ul className="price-list">
                  {sellingPrices.map((price, index) => (
                    <li key={`sell-${index}`} className="price-item price-item-sell">
                      <span>{price.toLocaleString()}</span>
                      {index === 0 && <Tag color="#3b82f6">最低价</Tag>}
                    </li>
                  ))}
                </ul>
              ) : (
                <Empty description="无售出价格数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              )}
            </Card>
          </Col>
        </Row>
      </div>
    );
  };

  // 脚本控制面板组件
  const ScriptControlPanel = () => (
    <Card className="script-control-card">
      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Space>
            <Button 
              type="primary" 
              icon={<PlayCircleOutlined />} 
              onClick={getAndCopyScriptCommand}
              loading={scriptRunning}
              disabled={scriptRunning}
            >
              启动脚本
            </Button>
            
            <Button 
              type="default" 
              onClick={() => setPresetModalVisible(true)}
              icon={<FilterOutlined />}
            >
              预设物品
            </Button>
            
            <Button 
              type="danger" 
              onClick={stopScript}
              disabled={!scriptRunning}
              icon={<StopOutlined />}
            >
              停止脚本
            </Button>
            
            <Button 
              icon={<SettingOutlined />} 
              onClick={() => setShowScriptSettings(!showScriptSettings)}
            >
              {showScriptSettings ? '隐藏设置' : '显示设置'}
            </Button>

            <Button 
              type="primary"
              icon={<CameraOutlined />}
              onClick={exportSelectedRowsAsImage}
              loading={exportLoading}
              disabled={selectedItems.length === 0}
            >
              导出选中行为图片
            </Button>
            
            <Tag color="#3b82f6">
              当前过滤: {filteredData.length} 个物品
            </Tag>
          </Space>
        </Col>
        
        {showScriptSettings && (
          <>
            <Col span={24}>
              <Row gutter={16}>
                <Col span={12}>
                  <Text style={{color: '#e2e8f0', display: 'block', marginBottom: '8px'}}>
                    起始分类索引 (从1开始)
                  </Text>
                  <InputNumber 
                    min={1} 
                    value={startCategory} 
                    onChange={value => setStartCategory(value)} 
                    style={{width: '100%'}}
                  />
                </Col>
                <Col span={12}>
                  <Text style={{color: '#e2e8f0', display: 'block', marginBottom: '8px'}}>
                    起始物品索引 (从1开始)
                  </Text>
                  <InputNumber 
                    min={1} 
                    value={startItem} 
                    onChange={value => setStartItem(value)} 
                    style={{width: '100%'}}
                  />
                </Col>
              </Row>
            </Col>
            
            <Col span={24}>
              <Card title="已保存的预设" size="small">
                {presets.length > 0 ? (
                  <List
                    size="small"
                    dataSource={presets}
                    renderItem={(preset, index) => (
                      <List.Item
                        actions={[
                          <Button size="small" onClick={() => loadPreset(index)}>加载</Button>,
                          <Popconfirm
                            title="确定要删除这个预设吗?"
                            onConfirm={() => deletePreset(index)}
                            okText="是"
                            cancelText="否"
                          >
                            <Button size="small" danger>删除</Button>
                          </Popconfirm>
                        ]}
                      >
                        <List.Item.Meta
                          title={preset.name}
                          description={`${preset.items.length}个物品 · ${new Date(preset.createdAt).toLocaleString()}`}
                        />
                      </List.Item>
                    )}
                  />
                ) : (
                  <Empty description="没有保存的预设" />
                )}
              </Card>
            </Col>
          </>
        )}
        
        {scriptRunning && (
          <Col span={24}>
            <Card title="脚本日志" size="small">
              <div className="script-log">
                {scriptLog.split('\n').map((line, index) => (
                  <div key={index} className="log-line">{line}</div>
                ))}
              </div>
            </Card>
          </Col>
        )}
      </Row>
    </Card>
  );

  // 列定义
  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      fixed: 'left',
      width: 220,
      render: (text, record) => {
        return (
          <span className={`item-name ${getRarityClass(record.rarity)}`}>
            {text}
            {record.isSpecial && <Tag color="#f97316" style={{marginLeft: '8px'}}>特殊</Tag>}
          </span>
        );
      }
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 120
    },
    {
      title: '最高求购价',
      dataIndex: 'maxBuying',
      key: 'maxBuying',
      width: 140,
      render: value => value.toLocaleString(),
      sorter: (a, b) => a.maxBuying - b.maxBuying
    },
    {
      title: '最低售出价',
      dataIndex: 'minSelling',
      key: 'minSelling',
      width: 140,
      render: value => value.toLocaleString(),
      sorter: (a, b) => a.minSelling - b.minSelling
    },
    {
      title: '低买低卖溢价',
      dataIndex: 'spread',
      key: 'spread',
      sorter: (a, b) => {
        // 处理null值和NaN情况
        if (a.spread === null && b.spread === null) return 0;
        if (a.spread === null) return 1; // null值排在后面
        if (b.spread === null) return -1;
        
        // 正常数值比较 - 从低到高排序
        return a.spread - b.spread;
      },
      sortDirections: ['ascend', 'descend'],
      defaultSortOrder: 'descend', // 默认降序（从高到低）
      render: (spread) => {
        if (spread === null) return <span>N/A</span>;
        const isPositive = spread > 0;
        return (
          <span className={`profit-tag ${isPositive ? 'profit-tag-positive' : 'profit-tag-negative'}`}>
            {spread.toLocaleString()}
          </span>
        );
      }
    },
    {
      title: '利润率',
      dataIndex: 'profitRatio',
      key: 'profitRatio',
      width: 100,
      render: (text) => {
        if (text === 'N/A') return <span>N/A</span>;
        // 正确解析利润率百分比字符串，转换为数字
        const percentage = parseFloat(text);
        return (
          <span className={`profit-tag ${percentage > 0 ? 'profit-tag-positive' : 'profit-tag-negative'}`}>
            {text}
          </span>
        );
      },
      sorter: (a, b) => {
        if (a.profitRatio === 'N/A' && b.profitRatio === 'N/A') return 0;
        if (a.profitRatio === 'N/A') return 1;
        if (b.profitRatio === 'N/A') return -1;
        // 正确解析百分比字符串进行排序
        return parseFloat(a.profitRatio) - parseFloat(b.profitRatio);
      },
      defaultSortOrder: 'descend'
    },
    {
      title: '出价数量',
      dataIndex: 'bidCount',
      key: 'bidCount',
      width: 100,
      render: (value, record) => {
        const count = parseInt(value) || 0;
        return (
          <span 
            className="clickable-cell" 
            onClick={() => {
              // 点击时展开此行
              const newExpandedRows = [...expandedRowKeys];
              const index = newExpandedRows.indexOf(record.key);
              if (index > -1) {
                newExpandedRows.splice(index, 1);
              } else {
                newExpandedRows.push(record.key);
              }
              setExpandedRowKeys(newExpandedRows);
            }}
          >
            {count} <span className="expand-hint">点击查看价格</span>
          </span>
        );
      },
      sorter: (a, b) => (parseInt(a.bidCount) || 0) - (parseInt(b.bidCount) || 0)
    },
    {
      title: '上架数量',
      dataIndex: 'listingCount',
      key: 'listingCount',
      width: 100,
      render: (value, record) => {
        const count = parseInt(value) || 0;
        return (
          <span 
            className="clickable-cell" 
            onClick={() => {
              // 点击时展开此行
              const newExpandedRows = [...expandedRowKeys];
              const index = newExpandedRows.indexOf(record.key);
              if (index > -1) {
                newExpandedRows.splice(index, 1);
              } else {
                newExpandedRows.push(record.key);
              }
              setExpandedRowKeys(newExpandedRows);
            }}
          >
            {count} <span className="expand-hint">点击查看价格</span>
          </span>
        );
      },
      sorter: (a, b) => (parseInt(a.listingCount) || 0) - (parseInt(b.listingCount) || 0)
    },
    {
      title: '更新时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 180
    }
  ];

  // 统计信息
  const stats = {
    totalItems: filteredData.length,
    profitableItems: filteredData.filter(item => item.spread > 0).length,
    highestProfit: filteredData.length > 0 ? 
      filteredData.reduce((max, item) => Math.max(max, item.spread || 0), 0) : 0,
    averageProfit: filteredData.length > 0 ? 
      Math.round(filteredData.reduce((sum, item) => sum + (item.spread || 0), 0) / filteredData.length) : 0
  };

  // 将UI值(0-100)映射到实际价格值
  const mapToPrice = (value) => {
    // 使用指数映射函数，使低价区域(0-2000)占据滑块前50%空间
    // 0-50的UI值映射到0-2000的价格
    // 50-100的UI值映射到2000-maxPrice的价格
    if (value <= 50) {
      // 线性映射0-50到0-2000
      return (value / 50) * 2000;
    } else {
      // 线性映射50-100到2000-maxPrice
      return 2000 + ((value - 50) / 50) * (maxPrice - 2000);
    }
  };

  // 将实际价格值映射回UI值(0-100)
  const mapFromPrice = (price) => {
    if (price <= 2000) {
      // 线性映射0-2000到0-50
      return (price / 2000) * 50;
    } else {
      // 线性映射2000-maxPrice到50-100
      return 50 + ((price - 2000) / (maxPrice - 2000)) * 50;
    }
  };

  // 修改价格区间滑块的onChange处理函数
  const handleSliderChange = (values) => {
    // 将滑块值映射到价格
    const priceLow = mapToPrice(values[0]);
    const priceHigh = mapToPrice(values[1]);
    setPriceRange([priceLow, priceHigh]);
    setSliderRange(values);
  };

  // 修改价格输入框的onChange处理函数
  const handleMinPriceChange = (e) => {
    const value = Number(e.target.value);
    if (!isNaN(value) && value >= 0 && value <= priceRange[1]) {
      setPriceRange([value, priceRange[1]]);
      // 更新滑块值
      setSliderRange([mapFromPrice(value), sliderRange[1]]);
    }
  };

  const handleMaxPriceChange = (e) => {
    const value = Number(e.target.value);
    if (!isNaN(value) && value >= priceRange[0] && value <= maxPrice) {
      setPriceRange([priceRange[0], value]);
      // 更新滑块值
      setSliderRange([sliderRange[0], mapFromPrice(value)]);
    }
  };

  // 生成滑块标记点 - 在UI值域(0-100)上均匀分布
  const generateSliderMarks = () => {
    const marks = {};
    
    // 0-50区间(对应0-2000价格)，每10个单位一个标记
    for (let i = 0; i <= 50; i += 10) {
      marks[i] = mapToPrice(i).toLocaleString();
    }
    
    // 50-100区间(对应2000-maxPrice价格)，每10个单位一个标记
    for (let i = 60; i <= 100; i += 10) {
      marks[i] = mapToPrice(i).toLocaleString();
    }
    
    return marks;
  };

  // 获取文件名的显示版本（提取日期和时间）
  const getDisplayFileName = (fileName) => {
    // 示例: price_data_20250402_17.csv -> 2025-04-02 17:00
    const matches = fileName.match(/price_data_(\d{4})(\d{2})(\d{2})_(\d{2})\.csv/);
    if (matches && matches.length >= 5) {
      return `${matches[1]}-${matches[2]}-${matches[3]} ${matches[4]}:00`;
    }
    return fileName;
  };

  // 在useEffect中初始化sliderRange
  useEffect(() => {
    if (priceRange[0] === 0 && priceRange[1] === maxPrice) {
      setSliderRange([0, 100]);
    }
  }, [maxPrice, priceRange]);

  // 保存当前预设
  const saveCurrentPreset = async () => {
    if (!presetName.trim()) {
      notification.error({
        message: '保存失败',
        description: '请输入预设名称'
      });
      return;
    }
    
    try {
      const response = await fetch('/api/savePreset', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: presetName,
          priceRange,
          categoryFilter,
          searchText,
          includeSpecialItems,
          items: selectedItems
        }),
      });

      const data = await response.json();
      
      if (data.success) {
        setPresets([...presets, {
          name: presetName,
          items: selectedItems
        }]);
        
        notification.success({
          message: '保存成功',
          description: `预设"${presetName}"已保存`
        });
        
        setPresetModalVisible(false);
        setPresetName('');
      } else {
        notification.error({
          message: '保存失败',
          description: data.error || '无法保存预设'
        });
      }
    } catch (error) {
      console.error('保存预设失败', error);
      notification.error({
        message: '保存失败',
        description: '网络错误，无法保存预设'
      });
    }
  };

  // 添加导出选中行为图片的函数
  const exportSelectedRowsAsImage = async () => {
    if (selectedItems.length === 0) {
      notification.warning({
        message: '未选择物品',
        description: '请先选择要导出的物品行'
      });
      return;
    }
    
    setExportLoading(true);
    
    try {
      // 获取当前活跃文件的时间信息
      const currentFile = recentFiles[activeFileIndex] || '';
      let timePrefix = '';
      
      // 从文件名中提取时间信息 (例如 price_data_20250408_19.csv)
      const matches = currentFile.match(/price_data_(\d{4})(\d{2})(\d{2})_(\d{2})\.csv/);
      if (matches && matches.length >= 5) {
        const hour = matches[4];
        timePrefix = `[${hour}时]`;
      }
      
      // 从选中的数据项中找出最早和最晚的更新时间
      let earliestTimestamp = null;
      let latestTimestamp = null;
      
      selectedItems.forEach(item => {
        if (item.timestamp) {
          const timestamp = item.timestamp;
          if (!earliestTimestamp || timestamp < earliestTimestamp) {
            earliestTimestamp = timestamp;
          }
          if (!latestTimestamp || timestamp > latestTimestamp) {
            latestTimestamp = timestamp;
          }
        }
      });
      
      // 构建时间范围字符串
      let timeRangeDisplay = '';
      if (earliestTimestamp && latestTimestamp) {
        if (earliestTimestamp === latestTimestamp) {
          timeRangeDisplay = `数据更新时间: ${earliestTimestamp}`;
        } else {
          timeRangeDisplay = `数据更新时间范围: ${earliestTimestamp} ~ ${latestTimestamp}`;
        }
      }
      
      // 创建一个临时容器来放置要导出的表格
      const container = document.createElement('div');
      container.className = 'export-container';
      // 设置样式以保持与应用相同的外观
      container.style.background = '#1e293b';
      container.style.padding = '20px';
      container.style.borderRadius = '8px';
      container.style.maxWidth = '1200px';
      container.style.margin = '0 auto';
      document.body.appendChild(container);
      
      // 添加标题
      const header = document.createElement('div');
      header.innerHTML = `
        <h2 style="text-align: center; color: #f8fafc; margin-bottom: 8px;">现代战舰市场物品价格数据</h2>
        ${timeRangeDisplay ? `<p style="text-align: center; color: #e2e8f0; margin-bottom: 16px;">${timeRangeDisplay}</p>` : ''}
      `;
      container.appendChild(header);
      
      // 创建表格
      const table = document.createElement('table');
      table.className = 'image-export-table';
      table.style.width = '100%';
      table.style.borderCollapse = 'collapse';
      table.style.color = '#f8fafc';
      table.style.border = '1px solid #334155';
      
      // 创建表头
      const thead = document.createElement('thead');
      thead.innerHTML = `
        <tr>
          <th style="padding: 8px; border: 1px solid #334155; background: #0f172a;">名称</th>
          <th style="padding: 8px; border: 1px solid #334155; background: #0f172a;">分类</th>
          <th style="padding: 8px; border: 1px solid #334155; background: #0f172a;">最高求购价</th>
          <th style="padding: 8px; border: 1px solid #334155; background: #0f172a;">最低售出价</th>
          <th style="padding: 8px; border: 1px solid #334155; background: #0f172a;">低买低卖溢价</th>
          <th style="padding: 8px; border: 1px solid #334155; background: #0f172a;">利润率</th>
          <th style="padding: 8px; border: 1px solid #334155; background: #0f172a;">出价数量</th>
          <th style="padding: 8px; border: 1px solid #334155; background: #0f172a;">上架数量</th>
        </tr>
      `;
      table.appendChild(thead);
      
      // 创建表体
      const tbody = document.createElement('tbody');
      
      // 添加选中的行
      selectedItems.forEach((item, index) => {
        const tr = document.createElement('tr');
        tr.style.background = index % 2 === 0 ? '#1e293b' : '#0f172a';
        
        // 获取稀有度对应的颜色
        const rarityColor = rarityColors[item.rarity] || '#9ca3af';
        
        // 添加单元格
        tr.innerHTML = `
          <td style="padding: 8px; border: 1px solid #334155; color: ${rarityColor};">
            ${item.name}
            ${item.isSpecial ? '<span style="margin-left: 8px; background: #f97316; color: white; padding: 2px 6px; border-radius: 4px; font-size: 12px;">特殊</span>' : ''}
          </td>
          <td style="padding: 8px; border: 1px solid #334155;">${item.category}</td>
          <td style="padding: 8px; border: 1px solid #334155;">${item.maxBuying.toLocaleString()}</td>
          <td style="padding: 8px; border: 1px solid #334155;">${item.minSelling.toLocaleString()}</td>
          <td style="padding: 8px; border: 1px solid #334155; ${item.spread > 0 ? 'color: #4ade80;' : 'color: #f87171;'}">${item.spread !== null ? item.spread.toLocaleString() : 'N/A'}</td>
          <td style="padding: 8px; border: 1px solid #334155; ${parseFloat(item.profitRatio) > 0 ? 'color: #4ade80;' : 'color: #f87171;'}">${item.profitRatio}</td>
          <td style="padding: 8px; border: 1px solid #334155;">${item.bidCount || 0}</td>
          <td style="padding: 8px; border: 1px solid #334155;">${item.listingCount || 0}</td>
        `;
        
        tbody.appendChild(tr);
      });
      
      table.appendChild(tbody);
      container.appendChild(table);
      
      // 添加水印
      const watermark = document.createElement('div');
      watermark.innerHTML = '<p style="text-align: center; color: #64748b; margin-top: 16px; font-size: 12px;">Generated by 现代战舰市场价格查看器</p>';
      container.appendChild(watermark);
      
      // 使用 html2canvas 将容器转换为图片
      const canvas = await html2canvas(container, {
        backgroundColor: '#1e293b',
        scale: 2, // 提高图片质量
        logging: false,
        useCORS: true
      });
      
      // 移除临时容器
      document.body.removeChild(container);
      
      // 获取图像数据并创建下载链接
      const imageData = canvas.toDataURL('image/png');
      const link = document.createElement('a');
      link.download = `${timePrefix}现代战舰市场数据_${new Date().toISOString().split('T')[0]}.png`;
      link.href = imageData;
      link.click();
      
      notification.success({
        message: '导出成功',
        description: `已导出 ${selectedItems.length} 个物品数据为图片`
      });
    } catch (error) {
      console.error('导出图片失败', error);
      notification.error({
        message: '导出失败',
        description: '生成图片时发生错误: ' + error.message
      });
    } finally {
      setExportLoading(false);
    }
  };

  // 优化搜索性能的函数 - 使用索引加速搜索
  const buildSearchIndex = (data) => {
    // 将数据添加到索引
    const index = {};
    data.forEach(item => {
      const words = item.name.toLowerCase().split(/\s+/);
      words.forEach(word => {
        if (!index[word]) {
          index[word] = [];
        }
        if (!index[word].includes(item.key)) {
          index[word].push(item.key);
        }
      });
    });
    return index;
  };

  // 修改过滤函数提高效率
  useEffect(() => {
    // 特殊过滤逻辑的优化
    const filterByPrice = (item) => {
      if (!includeSpecialItems && item.isSpecial) {
        return false;
      }
      
      return item.isSpecial && includeSpecialItems ? 
        true : 
        (item.maxBuying >= priceRange[0] && item.maxBuying <= priceRange[1]);
    };
    
    const filterByCategory = (item) => {
      return categoryFilter === '全部' || item.category === categoryFilter;
    };
    
    // 使用防抖后的文本创建搜索条件
    const searchTerms = debouncedSearchText.toLowerCase().trim().split(/\s+/).filter(term => term.length > 0);
    
    // 如果没有任何搜索词，使用简单的过滤
    if (searchTerms.length === 0) {
      const filtered = data.filter(item => filterByPrice(item) && filterByCategory(item));
      setFilteredData(filtered);
      return;
    }
    
    // 使用搜索索引优化
    const matchItems = data.filter(item => {
      if (!filterByPrice(item) || !filterByCategory(item)) {
        return false;
      }
      
      const itemName = item.name.toLowerCase();
      return searchTerms.every(term => itemName.includes(term));
    });
    
    setFilteredData(matchItems);
  }, [data, priceRange, debouncedSearchText, categoryFilter, includeSpecialItems]);

  return (
    <div className="market-viewer-container">
      <div className="app-header">
        <div className="app-title">现代战舰市场价格查看器</div>
        <div className="app-subtitle">实时追踪市场物品价格走势，优化交易决策</div>
        <div className="data-source">
          <DatabaseOutlined /> 数据来源: {recentFiles.length > 0 ? getDisplayFileName(recentFiles[activeFileIndex]) : '加载中...'}
          <Button 
            type="primary" 
            icon={<ReloadOutlined />} 
            onClick={loadRecentFiles} 
            loading={loading}
            style={{marginLeft: '10px'}}
          >
            刷新数据
          </Button>
        </div>
      </div>

      <Row gutter={[16, 16]} className="stats-row">
        <Col xs={24} sm={12} md={6}>
          <Card className="stat-card">
            <Statistic 
              title="物品总数" 
              value={stats.totalItems} 
              prefix={<DollarOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card className="stat-card">
            <Statistic 
              title="可盈利物品" 
              value={stats.profitableItems} 
              suffix={`/ ${stats.totalItems}`}
              valueStyle={{ color: '#4ade80' }}
              prefix={<ArrowUpOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card className="stat-card">
            <Statistic 
              title="最高溢价" 
              value={stats.highestProfit.toLocaleString()} 
              valueStyle={{ color: '#4ade80' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card className="stat-card">
            <Statistic 
              title="平均溢价" 
              value={stats.averageProfit.toLocaleString()}
              valueStyle={{ color: stats.averageProfit > 0 ? '#4ade80' : '#f87171' }}
              prefix={stats.averageProfit > 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* 脚本控制面板 */}
      <ScriptControlPanel />

      <Tabs 
        activeKey={activeFileIndex.toString()} 
        onChange={(key) => {
          const index = parseInt(key);
          if (recentFiles[index]) {
            loadCsvData(recentFiles[index], index);
          }
        }}
        type="card"
      >
        {recentFiles.map((file, index) => (
          <TabPane 
            tab={getDisplayFileName(file)} 
            key={index.toString()}
          >
          <Card className="filter-card">
            <Row gutter={[24, 16]}>
              {/* 第一行 - 价格区间过滤和分类过滤 */}
              <Col xs={24} lg={14}>
                <Title level={5} style={{color: '#e2e8f0', marginBottom: '16px'}}>价格区间过滤</Title>
                <Row gutter={[8, 8]} align="middle">
                  <Col span={24}>
                <Slider
                  range
                  min={0}
                      max={100}
                      value={sliderRange}
                      onChange={handleSliderChange}
                      tipFormatter={value => mapToPrice(value).toLocaleString()}
                      marks={generateSliderMarks()}
                    />
                  </Col>
                  <Col span={5}>
                    <Input
                      addonBefore="最小"
                      value={priceRange[0]}
                      onChange={handleMinPriceChange}
                      style={{width: '100%'}}
                    />
                  </Col>
                  <Col span={19}>
                    <Input
                      addonBefore="最大"
                      value={priceRange[1]}
                      onChange={handleMaxPriceChange}
                      style={{width: '100%'}}
                    />
                  </Col>
                </Row>
              </Col>
              
              {/* 分类过滤 */}
              <Col xs={24} lg={10}>
                <Title level={5} style={{color: '#e2e8f0', marginBottom: '16px'}}>分类过滤</Title>
                <Select 
                  style={{ width: '100%' }} 
                  value={categoryFilter}
                  onChange={setCategoryFilter}
                  dropdownStyle={{ background: '#1e293b', borderRadius: '8px' }}
                >
                  {categories.map(cat => (
                    <Option key={cat} value={cat}>{cat}</Option>
                  ))}
                </Select>
              </Col>
              
              {/* 第二行 - 名称搜索和超贵物品过滤 */}
              <Col xs={24} lg={14}>
                <Title level={5} style={{color: '#e2e8f0', marginBottom: '16px'}}>名称搜索</Title>
                <Input 
                  placeholder="输入物品名称" 
                  value={searchText}
                  onChange={handleSearchChange}
                  allowClear
                />
              </Col>
              
              <Col xs={24} lg={10}>
                <Title level={5} style={{color: '#e2e8f0', marginBottom: '16px'}}>包含超贵物品</Title>
                <div style={{ paddingTop: '8px' }}>
                <Switch 
                  checked={includeSpecialItems}
                  onChange={setIncludeSpecialItems}
                    style={{ marginLeft: '8px' }}
                />
                    <Button 
                      type="primary" 
                      icon={<SaveOutlined />} 
                      style={{ marginLeft: '16px' }}
                      onClick={() => setPresetModalVisible(true)}
                    >
                      保存当前筛选为预设
                    </Button>
                </div>
              </Col>
            </Row>
              
              {/* 脚本控制区 */}
              <Row style={{ marginTop: '16px' }}>
                <Col span={24}>
                  <Card className="script-control-card">
                    <Row gutter={16} align="middle">
                      <Col xs={24} md={8}>
                        <Space direction="horizontal" align="center">
                          <Text style={{color: '#e2e8f0'}}>起始分类</Text>
                          <InputNumber 
                            min={1} 
                            value={startCategory} 
                            onChange={value => setStartCategory(value)} 
                            style={{ width: '80px' }}
                          />
                          <Text style={{color: '#e2e8f0'}}>起始物品</Text>
                          <InputNumber 
                            min={1} 
                            value={startItem} 
                            onChange={value => setStartItem(value)} 
                            style={{ width: '80px' }}
                          />
                        </Space>
                      </Col>
                      <Col xs={24} md={16}>
                        <Space>
                          <Button 
                            type="primary" 
                            icon={<PlayCircleOutlined />} 
                            onClick={getAndCopyScriptCommand}
                            loading={scriptRunning}
                            disabled={scriptRunning}
                          >
                            启动脚本
                          </Button>
                          <Button 
                            type="default" 
                            icon={<FilterOutlined />} 
                            onClick={() => setPresetModalVisible(true)}
                          >
                            预设物品
                          </Button>
                          <Button 
                            type="primary"
                            icon={<CameraOutlined />}
                            onClick={exportSelectedRowsAsImage}
                            loading={exportLoading}
                            disabled={selectedItems.length === 0}
                          >
                            导出图片
                          </Button>
                          <Text type={selectedItems.length > 0 ? "success" : "secondary"}>
                            {selectedItems.length > 0 
                              ? `已选择${selectedItems.length}个物品` 
                              : '未选择预设物品（将处理全部物品）'}
                          </Text>
                        </Space>
                      </Col>
                    </Row>
                  </Card>
                </Col>
              </Row>
          </Card>

          <Card className="table-card">
            <Table 
              columns={columns} 
              dataSource={filteredData} 
              loading={loading}
              scroll={{ x: 1300 }}
              pagination={{ 
                defaultPageSize: 20, 
                showSizeChanger: true, 
                pageSizeOptions: ['10', '20', '50', '100'],
                showTotal: (total, range) => `${range[0]}-${range[1]} / ${total} 个物品` 
              }}
              expandable={{
                expandedRowKeys,
                onExpandedRowsChange: setExpandedRowKeys,
                expandedRowRender: record => <PriceDetailPanel record={record} />,
              }}
              rowSelection={{
                type: 'checkbox',
                selectedRowKeys: selectedRowKeys,
                onChange: handleSelectChange,
                preserveSelectedRowKeys: true, // 保持选中行即使它们不在当前过滤结果中
              }}
            />
          </Card>
        </TabPane>
        ))}
      </Tabs>

      {/* 脚本日志模态框 */}
      <Modal
        title="脚本运行状态"
        open={scriptRunning}
        onCancel={() => setScriptRunning(false)}
        footer={[
          <Button key="close" onClick={() => setScriptRunning(false)}>
            关闭
          </Button>
        ]}
        width={800}
      >
        <div className="script-log">
          <pre>{scriptLog}</pre>
        </div>
      </Modal>

      {/* 预设保存模态框 */}
      <Modal
        title="保存筛选预设"
        open={presetModalVisible}
        onCancel={() => setPresetModalVisible(false)}
        onOk={saveCurrentPreset}
      >
        <Input
          placeholder="预设名称"
          value={presetName}
          onChange={e => setPresetName(e.target.value)}
          style={{ marginBottom: '16px' }}
        />
        
        <div>
          <Text strong>当前筛选条件:</Text>
          <ul>
            <li>价格范围: {priceRange[0].toLocaleString()} - {priceRange[1].toLocaleString()}</li>
            <li>分类: {categoryFilter}</li>
            {searchText && <li>搜索关键词: {searchText}</li>}
            <li>包含超贵物品: {includeSpecialItems ? '是' : '否'}</li>
            <li>物品数量: {filteredData.length}</li>
          </ul>
        </div>

        {presets.length > 0 && (
          <div style={{ marginTop: '16px' }}>
            <Text strong>现有预设:</Text>
            <List
              size="small"
              bordered
              dataSource={presets}
              renderItem={(item, index) => (
                <List.Item
                  actions={[
                    <Button 
                      size="small" 
                      onClick={() => loadPreset(index)}
                    >
                      加载
                    </Button>,
                    <Button 
                      size="small" 
                      danger 
                      onClick={() => deletePreset(index)}
                    >
                      删除
                    </Button>
                  ]}
                >
                  {item.name} ({item.items.length}个物品)
                </List.Item>
              )}
            />
          </div>
        )}
      </Modal>
    </div>
  );
};

export default MarketPriceViewer; 