# GEO 品牌诊断系统

## 项目结构
```
geo-diagnostic/
├── backend/          # FastAPI 后端
│   ├── main.py       # 入口
│   ├── config.py     # 配置
│   ├── database.py   # SQLite 数据库
│   ├── models/       # 数据模型
│   ├── routers/      # API 路由
│   ├── services/     # 业务逻辑
│   │   ├── query_engine.py    # AI 平台查询引擎
│   │   ├── parser.py          # 结果解析引擎
│   │   ├── analyzer.py        # 分析计算引擎
│   │   ├── report_generator.py # 报告生成
│   │   └── report_template.html # HTML 报告模板
│   ├── .env.example  # 环境变量模板
│   └── geo_diagnostic.db  # SQLite 数据库（自动创建）
└── frontend/         # React + Vite + TS + Tailwind
    └── src/
        ├── api/       # API 接口层
        ├── pages/     # 页面组件
        └── components/ # 公共组件
```

## 技术栈
- **后端**: Python 3.9 (系统) + FastAPI + aiosqlite
- **前端**: React 18 + Vite 8 + TypeScript + Tailwind CSS v4
- **数据库**: SQLite（MVP 阶段）
- **图表**: ECharts（报告内嵌）

## Python 虚拟环境
- 路径: `/Users/rose/.workbuddy/binaries/python/envs/geo-diagnostic-sys`
- Python: 系统 3.9.6（Apple 平台二进制，无 Team ID 签名限制）
- 注意：managed Python 3.13 有 pydantic-core 签名冲突，不能用

## 启动命令

### 后端
```bash
/Users/rose/.workbuddy/binaries/python/envs/geo-diagnostic-sys/bin/uvicorn main:app \
  --app-dir /Users/rose/WorkBuddy/2026-06-04-09-52-36/geo-diagnostic/backend \
  --host 0.0.0.0 --port 8900
```

### 前端 Dev
```bash
cd geo-diagnostic/frontend && unset NODE_OPTIONS && node_modules/.bin/vite
```

### 前端 Build
```bash
bash build-frontend.sh
```

## API 端点
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/health | 健康检查 |
| GET | /api/tasks/platforms | 获取可用 AI 平台 |
| POST | /api/tasks | 创建诊断任务 |
| GET | /api/tasks | 任务列表 |
| GET | /api/tasks/{id} | 任务详情 |
| DELETE | /api/tasks/{id} | 删除任务 |
| POST | /api/queries/{id}/run | 执行查询 |
| GET | /api/queries/{id}/results | 查询结果 |
| GET | /api/queries/{id}/status | 执行状态 |
| GET | /api/analysis/{id} | 分析结果 |
| GET | /api/reports/{id}/html | HTML 报告 |

## 待配置 API Keys
- DASHSCOPE_API_KEY (千问)
- DEEPSEEK_API_KEY (DeepSeek)
- VOLCENGINE_API_KEY + VOLCENGINE_ENDPOINT_ID (豆包)

## 部署
- 前端预览: https://19adcc4b31824fc5b7d6ffc6b502e4e8.app.codebuddy.work
- 后端: 本地 8900 端口（MVP 阶段）
