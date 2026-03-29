from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    siliconflow_api_key: SecretStr = SecretStr("")
    siliconflow_base_url: str = "https://api.siliconflow.com/v1"
    embedding_model: str = "Qwen/Qwen3-Embedding-8B"
    llm_model: str = "Qwen/Qwen3-30B-A3B-Instruct-2507"
    reranker_model: str = "Qwen/Qwen3-Reranker-8B"
    vlm_model: str = "Qwen/Qwen2.5-VL-72B-Instruct"
    embedding_dimensions: int = 1024
    embedding_query_instruction: str = (
        "Instruct: Retrieve English accounting textbook passages "
        "relevant to the Indonesian accounting query\nQuery: "
    )
    qdrant_url: str = ""
    qdrant_api_key: SecretStr = SecretStr("")
    qdrant_collection_name: str = "trusty_rag_akmen"
    reranker_top_k_input: int = 20
    reranker_top_k_output: int = 5
    graphrag_working_dir: str = "./graphrag_storage"
    langfuse_public_key: str = ""
    langfuse_secret_key: SecretStr = SecretStr("")
    langfuse_base_url: str = "https://cloud.langfuse.com"
    langfuse_enabled: bool = True
    deepseek_api_key: SecretStr = SecretStr("")
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    graphrag_llm_model: str = "deepseek-chat"


settings = Settings()
