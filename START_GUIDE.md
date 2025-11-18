# 🎉 欢迎使用资金费率套利机器人！

## 📦 你已下载了什么

这个 ZIP 包包含了一个**完整可用**的资金费率套利系统：

- ✅ 完整的后端代码（Python）
- ✅ 完整的前端界面（Web）
- ✅ 所有配置文件
- ✅ 详细的文档
- ✅ 部署脚本

---

## 🚀 快速开始（5分钟）

### 1️⃣ 解压文件
```bash
unzip funding-arbitrage-bot-complete.zip
cd funding-arbitrage-bot
```

### 2️⃣ 阅读文档
**首先阅读这两个文件（必读）：**
- `FINAL_SUMMARY.md` - 项目总结
- `DEPLOY_COMPLETE.md` - 完整部署指南

### 3️⃣ 配置 API 密钥
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置文件（填入你的 API 密钥）
nano .env
```

需要填入：
- Lighter 的 ETH 私钥和 API 私钥
- 币安的 API Key 和 Secret

### 4️⃣ 启动系统

**方式A：本地快速测试（推荐新手）**
```bash
# 进入后端目录
cd backend

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python -c "from app.database import init_db; init_db()"

# 启动后端服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**打开新终端启动前端：**
```bash
cd frontend
python3 -m http.server 3000
```

**方式B：Docker（推荐生产）**
```bash
docker-compose up -d
```

### 5️⃣ 访问界面
打开浏览器访问：**http://localhost:3000**

---

## 📖 文件说明

### 📚 必读文档
1. **FINAL_SUMMARY.md** ⭐ - 从这里开始！
2. **DEPLOY_COMPLETE.md** ⭐ - 详细部署指南
3. **README.md** - 完整项目文档

### 💻 项目代码
- **funding-arbitrage-bot/** - 主项目文件夹
  - **backend/** - Python 后端代码
  - **frontend/** - Web 前端界面

### ⚙️ 配置文件
- **.env.example** - 环境变量模板
- **docker-compose.yml** - Docker 配置

### 🔧 脚本工具
- **check_env.sh** - 环境检查
- **test_deploy.sh** - 测试部署
- **deploy.sh** - 完整部署

---

## 🎯 核心功能

### Web 界面功能
1. **📊 实时监控** - 查看所有交易对的费率差
2. **⚙️ 参数配置** - 设置交易参数（费率阈值、建仓金额等）
3. **📈 当前持仓** - 实时查看持仓和盈亏
4. **📜 历史记录** - 完整的盈亏分析

### 自动化功能
- ✅ 实时监控费率
- ✅ 自动识别套利机会
- ✅ 分批建仓/平仓
- ✅ 自动止损止盈
- ✅ 持仓不平衡监控

---

## 📁 目录结构

```
funding-arbitrage-bot/
├── backend/                    # 后端代码
│   ├── app/
│   │   ├── main.py            # 主应用
│   │   ├── api/               # API 接口
│   │   ├── core/              # 核心模块
│   │   │   ├── data_collector.py      # 数据采集
│   │   │   ├── strategy_engine.py     # 策略引擎
│   │   │   ├── order_executor.py      # 订单执行
│   │   │   ├── risk_manager.py        # 风险管理
│   │   │   ├── position_manager.py    # 持仓管理
│   │   │   └── pnl_calculator.py      # 盈亏计算
│   │   └── exchanges/         # 交易所客户端
│   │       ├── lighter_client.py
│   │       └── binance_client.py
│   ├── requirements.txt        # Python 依赖
│   └── Dockerfile
│
├── frontend/                   # 前端界面
│   ├── index.html             # 完整 Web 应用
│   └── Dockerfile
│
├── FINAL_SUMMARY.md           ⭐ 必读！
├── DEPLOY_COMPLETE.md         ⭐ 必读！
├── README.md                   完整文档
├── docker-compose.yml          Docker 配置
└── .env.example                环境变量模板
```

---

## ⚠️ 重要提示

### 安全建议
1. ✅ 先在测试网测试
2. ✅ 使用专门的测试钱包
3. ✅ 从小额开始
4. ✅ 禁用 API 的提现权限
5. ✅ 设置 IP 白名单

### 风险提示
1. ⚠️ 加密货币交易有风险
2. ⚠️ 套利不保证盈利
3. ⚠️ 可能有滑点和手续费
4. ⚠️ 谨慎使用杠杆

---

## 🔧 常见问题

### Q: 如何获取 Lighter API 密钥？
A: 访问 https://app.lighter.xyz，连接钱包后生成 API Key

### Q: 如何获取币安 API 密钥？
A: 登录币安 → API 管理 → 创建 API → 启用合约交易权限

### Q: 启动后无法访问？
A: 
1. 检查后端是否运行：`curl http://localhost:8000/health`
2. 检查端口是否被占用：`lsof -i :8000`
3. 查看日志：`tail -f backend/logs/bot.log`

### Q: 依赖安装失败？
A: 
```bash
pip install --upgrade pip
pip install -r requirements.txt --no-cache-dir
```

---

## 📞 需要帮助？

### 1. 查看文档
- **DEPLOY_COMPLETE.md** - 详细部署步骤
- **FINAL_SUMMARY.md** - 项目说明
- **README.md** - 完整文档

### 2. 查看日志
```bash
# 本地部署
tail -f backend/logs/bot.log

# Docker 部署
docker-compose logs -f backend
```

### 3. 检查状态
```bash
# 检查后端
curl http://localhost:8000/health

# 检查 API
curl http://localhost:8000/api/v1/status
```

---

## 🎉 开始使用

**现在就开始：**

```bash
# 1. 解压文件
unzip funding-arbitrage-bot-complete.zip
cd funding-arbitrage-bot

# 2. 阅读文档
cat FINAL_SUMMARY.md

# 3. 配置并启动
cp .env.example .env
nano .env  # 填入 API 密钥

cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -c "from app.database import init_db; init_db()"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 4. 新终端启动前端
cd frontend
python3 -m http.server 3000

# 5. 打开浏览器
# http://localhost:3000
```

**祝你套利成功！** 🚀💰
