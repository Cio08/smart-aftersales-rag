import os
from pathlib import Path
from dotenv import load_dotenv

# 1. 自动定位到项目的根目录 (smart-aftersales-rag)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 2. 从项目根目录加载 .env 文件到系统环境变量中
load_dotenv(BASE_DIR / ".env")


class Settings:
    """系统全局配置类"""
    PROJECT_NAME: str = "智能家电售后 RAG 知识库系统"
    VERSION: str = "1.0.0"

    # 大模型接口配置
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "deepseek-chat")

    # 服务网络配置
    APP_HOST: str = os.getenv("APP_HOST", "127.0.0.1")
    APP_PORT: int = int(os.getenv("APP_PORT", 8000))


# 3. 实例化为单例对象，供全项目其他模块直接调用
settings = Settings()

# 本地自测验证逻辑
if __name__ == "__main__":
    print("=" * 40)
    print(f"项目名称: {settings.PROJECT_NAME}")
    print(f"服务地址: {settings.APP_HOST}:{settings.APP_PORT}")
    print(f"大模型底模: {settings.LLM_MODEL}")
    print(f"API Base URL: {settings.LLM_BASE_URL}")
    print("=" * 40)
    print("✅ 配置中心加载成功！")