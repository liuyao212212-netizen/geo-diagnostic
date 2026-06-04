"""
SQLite 数据库配置与初始化
"""
import aiosqlite
from pathlib import Path
from config import settings

DB_PATH = settings.DB_PATH
db_connection: aiosqlite.Connection = None


async def get_db() -> aiosqlite.Connection:
    """获取数据库连接"""
    return db_connection


async def init_db():
    """初始化数据库，创建表结构"""
    global db_connection
    db_connection = await aiosqlite.connect(str(DB_PATH))
    db_connection.row_factory = aiosqlite.Row

    await db_connection.executescript("""
        -- 诊断任务表
        CREATE TABLE IF NOT EXISTS diagnostic_tasks (
            id TEXT PRIMARY KEY,
            brand_name TEXT NOT NULL,
            brand_aliases TEXT NOT NULL DEFAULT '[]',
            scenarios TEXT NOT NULL DEFAULT '[]',
            platforms TEXT NOT NULL DEFAULT '[]',
            competitors TEXT NOT NULL DEFAULT '[]',
            discovered_competitors TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'pending',
            review_status TEXT NOT NULL DEFAULT 'none',
            review_note TEXT DEFAULT '',
            reviewed_at TEXT,
            created_at TEXT NOT NULL,
            completed_at TEXT
        );

        -- 查询结果表
        CREATE TABLE IF NOT EXISTS query_results (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            platform_name TEXT NOT NULL,
            platform_version TEXT NOT NULL DEFAULT 'default',
            scenario_question TEXT NOT NULL,
            scenario_category TEXT NOT NULL,
            ai_response_text TEXT,
            query_duration_ms INTEGER,
            queried_at TEXT NOT NULL,
            error_message TEXT,
            FOREIGN KEY (task_id) REFERENCES diagnostic_tasks(id)
        );

        -- 品牌提及记录
        CREATE TABLE IF NOT EXISTS brand_mentions (
            id TEXT PRIMARY KEY,
            query_result_id TEXT NOT NULL,
            brand_name TEXT NOT NULL,
            mention_rank INTEGER,
            sentiment TEXT NOT NULL DEFAULT 'neutral',
            mention_context TEXT,
            is_primary_brand INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (query_result_id) REFERENCES query_results(id)
        );

        -- 引用来源记录
        CREATE TABLE IF NOT EXISTS citation_sources (
            id TEXT PRIMARY KEY,
            query_result_id TEXT NOT NULL,
            source_url TEXT,
            source_domain TEXT,
            source_type TEXT,
            source_title TEXT,
            citation_rank INTEGER,
            FOREIGN KEY (query_result_id) REFERENCES query_results(id)
        );

        -- 平台配置表
        CREATE TABLE IF NOT EXISTS platform_configs (
            id TEXT PRIMARY KEY,
            platform_name TEXT NOT NULL UNIQUE,
            platform_type TEXT NOT NULL DEFAULT 'api',
            api_base_url TEXT,
            api_key_env TEXT,
            model_name TEXT,
            is_enabled INTEGER NOT NULL DEFAULT 1
        );

        -- 插入默认平台配置
        INSERT OR IGNORE INTO platform_configs (id, platform_name, platform_type, api_base_url, api_key_env, model_name) VALUES
            ('dashscope', '千问', 'api', 'https://dashscope.aliyuncs.com/compatible-mode/v1', 'DASHSCOPE_API_KEY', 'qwen-plus'),
            ('deepseek', 'DeepSeek', 'api', 'https://api.deepseek.com/v1', 'DEEPSEEK_API_KEY', 'deepseek-chat'),
            ('volcengine', '豆包', 'api', 'https://ark.cn-beijing.volces.com/api/v3', 'VOLCENGINE_API_KEY', 'doubao-pro-4k');
    """)

    await db_connection.commit()

    # 迁移：添加 review_status 列（如果不存在）
    try:
        await db_connection.execute("ALTER TABLE diagnostic_tasks ADD COLUMN review_status TEXT NOT NULL DEFAULT 'none'")
        await db_connection.execute("ALTER TABLE diagnostic_tasks ADD COLUMN review_note TEXT DEFAULT ''")
        await db_connection.execute("ALTER TABLE diagnostic_tasks ADD COLUMN reviewed_at TEXT")
        await db_connection.commit()
    except Exception:
        pass  # 列已存在则跳过

    # 迁移：添加 discovered_competitors 列（如果不存在）
    try:
        await db_connection.execute("ALTER TABLE diagnostic_tasks ADD COLUMN discovered_competitors TEXT NOT NULL DEFAULT '[]'")
        await db_connection.commit()
    except Exception:
        pass  # 列已存在则跳过

    print(f"数据库初始化完成: {DB_PATH}")


async def close_db():
    """关闭数据库连接"""
    global db_connection
    if db_connection:
        await db_connection.close()
        print("数据库连接已关闭")
