"""
GEO 品牌诊断系统 - FastAPI 主入口
"""
import os
from dotenv import load_dotenv
load_dotenv()  # 加载 .env 环境变量

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database import init_db, close_db
from routers import tasks, queries, analysis, reports

# 静态文件目录（前端构建产物）
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化数据库
    await init_db()
    yield
    # 关闭时清理
    await close_db()


app = FastAPI(
    title="GEO 品牌诊断系统",
    description="AI 平台品牌可见度诊断与竞争分析工具",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 配置 - 生产环境允许所有来源（Railway 部署）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(tasks.router, prefix="/api/tasks", tags=["任务管理"])
app.include_router(queries.router, prefix="/api/queries", tags=["查询管理"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["数据分析"])
app.include_router(reports.router, prefix="/api/reports", tags=["报告生成"])


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}


# 托管前端静态文件（Railway 单服务部署）
if os.path.isdir(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA fallback: 非 API 路径返回 index.html"""
        file_path = os.path.join(STATIC_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
