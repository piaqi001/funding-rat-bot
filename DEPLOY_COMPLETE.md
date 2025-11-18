# 🚀 完整代码 - 立即部署指南

## 🎉 恭喜！所有代码已完成

现在你拥有一个**100%完整**的资金费率套利系统！

### ✅ 已完成的功能

**后端 (100%)**：
- ✅ 数据采集器 - 实时监控费率
- ✅ 策略引擎 - 识别套利机会
- ✅ 订单执行器 - 自动分批建仓/平仓
- ✅ 风险管理器 - 止损止盈监控
- ✅ 持仓管理器 - 持仓追踪
- ✅ 盈亏计算器 - 完整盈亏分析
- ✅ RESTful API - 20+ 个接口
- ✅ WebSocket - 实时数据推送

**前端 (100%)**：
- ✅ 实时监控页面 - 费率差监控
- ✅ 参数配置页面 - 可视化配置
- ✅ 当前持仓页面 - 持仓详情
- ✅ 历史记录页面 - 盈亏分析
- ✅ 响应式设计 - 美观易用

---

## 📦 项目文件结构

```
funding-arbitrage-bot/
├── backend/
│   ├── app/
│   │   ├── main.py              ✅ 主应用
│   │   ├── config.py            ✅ 配置管理
│   │   ├── database.py          ✅ 数据库
│   │   ├── models.py            ✅ 数据模型
│   │   ├── api/
│   │   │   ├── routes.py        ✅ API 路由
│   │   │   └── websocket.py     ✅ WebSocket
│   │   ├── core/
│   │   │   ├── data_collector.py      ✅ 数据采集
│   │   │   ├── strategy_engine.py     ✅ 策略引擎
│   │   │   ├── order_executor.py      ✅ 订单执行
│   │   │   ├── risk_manager.py        ✅ 风险管理
│   │   │   ├── position_manager.py    ✅ 持仓管理
│   │   │   └── pnl_calculator.py      ✅ 盈亏计算
│   │   └── exchanges/
│   │       ├── lighter_client.py      ✅ Lighter 客户端
│   │       └── binance_client.py      ✅ 币安客户端
│   ├── requirements.txt         ✅
│   └── Dockerfile               ✅
│
├── frontend/
│   ├── index.html               ✅ 完整 Web 应用
│   ├── Dockerfile               ✅
│   └── package.json             ✅
│
├── docker-compose.yml           ✅
└── .env.example                 ✅
```

---

## 🚀 快速部署 (3种方式)

### 方式 1: 本地测试 (最快，5分钟) ⭐

#### 步骤 1: 安装依赖
```bash
cd funding-arbitrage-bot/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 步骤 2: 配置环境变量
```bash
# 复制配置文件
cp ../../.env.example .env

# 编辑配置
nano .env
```

填入你的 API 密钥：
```bash
# Lighter 配置
LIGHTER_ETH_PRIVATE_KEY=0x你的私钥
LIGHTER_API_KEY_PRIVATE_KEY=0x你的API私钥
LIGHTER_ACCOUNT_INDEX=0
LIGHTER_API_KEY_INDEX=2

# 币安配置
BINANCE_API_KEY=你的API_Key
BINANCE_API_SECRET=你的Secret
BINANCE_TESTNET=true  # 建议先用测试网

# 数据库（使用 SQLite 测试）
DATABASE_URL=sqlite:///./test.db
```

#### 步骤 3: 启动后端
```bash
# 初始化数据库
python -c "from app.database import init_db; init_db()"

# 启动服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 步骤 4: 启动前端
打开新终端：
```bash
cd funding-arbitrage-bot/frontend
python3 -m http.server 3000
```

#### 步骤 5: 访问界面
打开浏览器访问: **http://localhost:3000**

---

### 方式 2: Docker Compose (推荐生产) 🐳

#### 步骤 1: 配置环境变量
```bash
cd funding-arbitrage-bot
cp ../.env.example .env
nano .env  # 填入你的 API 密钥
```

#### 步骤 2: 启动所有服务
```bash
docker-compose up -d
```

#### 步骤 3: 查看日志
```bash
docker-compose logs -f backend
```

#### 步骤 4: 访问界面
打开浏览器访问: **http://localhost:3000**

#### 停止服务
```bash
docker-compose down
```

---

### 方式 3: 生产部署 (Ubuntu服务器)

#### 完整部署脚本
```bash
#!/bin/bash

# 1. 更新系统
sudo apt update && sudo apt upgrade -y

# 2. 安装依赖
sudo apt install python3 python3-pip python3-venv postgresql -y

# 3. 创建数据库
sudo -u postgres psql << EOF
CREATE DATABASE funding_arbitrage;
CREATE USER admin WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE funding_arbitrage TO admin;
\q
EOF

# 4. 克隆项目
cd /opt
sudo git clone <your-repo> funding-arbitrage-bot
cd funding-arbitrage-bot

# 5. 配置环境变量
sudo cp .env.example .env
sudo nano .env  # 填入配置

# 6. 安装后端
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 7. 初始化数据库
python -c "from app.database import init_db; init_db()"

# 8. 使用 systemd 管理服务
sudo tee /etc/systemd/system/arbitrage-bot.service << EOF
[Unit]
Description=Funding Arbitrage Bot
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/funding-arbitrage-bot/backend
Environment="PATH=/opt/funding-arbitrage-bot/backend/venv/bin"
ExecStart=/opt/funding-arbitrage-bot/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 9. 启动服务
sudo systemctl daemon-reload
sudo systemctl enable arbitrage-bot
sudo systemctl start arbitrage-bot

# 10. 配置 Nginx
sudo apt install nginx -y

sudo tee /etc/nginx/sites-available/arbitrage-bot << EOF
server {
    listen 80;
    server_name your-domain.com;

    location / {
        root /opt/funding-arbitrage-bot/frontend;
        index index.html;
        try_files \$uri \$uri/ /index.html;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/arbitrage-bot /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

echo "✅ 部署完成！"
echo "访问: http://your-server-ip"
```

---

## 📖 使用指南

### 第一次使用

#### 1. 检查系统状态
打开 **http://localhost:3000**，查看顶部状态栏：
- ✅ Lighter: 已连接 (xxx USDC)
- ✅ 币安: 已连接 (xxx USDT)

如果显示未连接，检查 API 配置。

#### 2. 配置参数
点击 **⚙️ 参数配置**，设置：
- 费率阈值: `0.01` (1%)
- 单笔建仓: `100` USDC
- 最大持仓: `1000` USDC
- 最大不平衡: `200` USDC
- 总杠杆: `3x`

点击 **💾 保存配置**

#### 3. 监控套利机会
点击 **📊 实时监控**，查看费率差：
- 绿色高亮 = 有套利机会
- 当前费率差和8h平均差都 > 1% 时，显示「建仓」按钮

#### 4. 手动建仓
点击「建仓」按钮，系统会：
- ✅ 同时在两个平台开仓
- ✅ 分批下单到目标金额
- ✅ 自动设置止损止盈
- ✅ 监控持仓不平衡

#### 5. 查看持仓
点击 **📈 当前持仓**：
- 查看 Lighter 和币安的持仓详情
- 实时未实现盈亏
- 点击「平仓」手动平仓

#### 6. 查看盈亏
点击 **📜 历史记录**：
- 总盈亏统计
- 胜率、平均ROI
- 每个订单的详细盈亏

---

## 🔧 常用操作

### 查看日志
```bash
# Docker 方式
docker-compose logs -f backend

# 本地方式
tail -f backend/logs/bot.log
```

### 重启服务
```bash
# Docker 方式
docker-compose restart backend

# Systemd 方式
sudo systemctl restart arbitrage-bot
```

### 备份数据
```bash
# 备份数据库
pg_dump funding_arbitrage > backup.sql

# 或使用 SQLite
cp backend/test.db backup/test.db.$(date +%Y%m%d)
```

### 查看系统状态
```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/status
```

---

## 🎯 API 接口文档

访问: **http://localhost:8000/docs**

主要接口：
- `GET /api/v1/funding-rates` - 获取费率数据
- `GET /api/v1/opportunities` - 获取套利机会
- `POST /api/v1/orders/open` - 建仓
- `POST /api/v1/orders/close` - 平仓
- `GET /api/v1/positions` - 获取持仓
- `GET /api/v1/pnl/history` - 获取盈亏历史
- `GET /api/v1/config` - 获取配置
- `POST /api/v1/config` - 更新配置

WebSocket:
- `ws://localhost:8000/ws` - 实时数据推送

---

## ⚠️ 重要提示

### 安全建议
1. ✅ 使用专门的测试钱包
2. ✅ 先在测试网测试
3. ✅ API Key 禁用提现权限
4. ✅ 设置 IP 白名单
5. ✅ 定期更换 API Key

### 风险提示
1. ⚠️ 加密货币交易有风险
2. ⚠️ 套利不保证盈利
3. ⚠️ 可能出现滑点、手续费等损失
4. ⚠️ 从小额开始测试
5. ⚠️ 不要使用全部资金

### 最佳实践
1. ✅ 每天检查系统状态
2. ✅ 定期查看持仓和盈亏
3. ✅ 及时处理异常告警
4. ✅ 保持足够的账户余额
5. ✅ 定期备份数据

---

## 🐛 故障排除

### 问题 1: 无法连接到 Lighter
```bash
# 检查 API 密钥
# 检查网络连接
# 查看日志
docker-compose logs backend | grep -i lighter
```

### 问题 2: 币安 API 报错
```bash
# 检查 API 权限
# 检查系统时间同步
sudo ntpdate -s time.nist.gov
```

### 问题 3: 前端无法连接后端
```bash
# 检查后端是否启动
curl http://localhost:8000/health

# 检查 CORS 配置
# 查看浏览器控制台错误
```

### 问题 4: 数据库连接失败
```bash
# 检查 PostgreSQL 是否运行
sudo systemctl status postgresql

# 检查连接字符串
echo $DATABASE_URL
```

---

## 📞 获取帮助

### 遇到问题？

1. **查看日志**
   ```bash
   docker-compose logs -f backend
   ```

2. **检查系统状态**
   ```bash
   curl http://localhost:8000/api/v1/status
   ```

3. **重启服务**
   ```bash
   docker-compose restart
   ```

4. **查看文档**
   - README.md
   - API 文档: http://localhost:8000/docs

---

## 🎉 开始使用！

**现在就开始：**

```bash
# 1. 进入项目目录
cd funding-arbitrage-bot

# 2. 配置 API 密钥
cp ../.env.example .env
nano .env

# 3. 启动服务
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -c "from app.database import init_db; init_db()"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 4. 在新终端启动前端
cd ../frontend
python3 -m http.server 3000

# 5. 打开浏览器
# http://localhost:3000
```

**祝你套利顺利！** 🚀💰
