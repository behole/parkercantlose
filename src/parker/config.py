from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    hf_token: str = ""
    deepgram_api_key: str = ""
    data_dir: Path = Path("data")
    audio_dir: Path = Path("data/audio")
    transcript_dir: Path = Path("data/transcripts")
    db_path: Path = Path("data/db/debates.db")
    whisper_model: str = "large-v2"
    whisper_device: str = "auto"
    whisper_compute_type: str = "auto"
    whisper_batch_size: int = 16
    whisper_language: str = "en"
    web_host: str = "127.0.0.1"
    web_port: int = 8000
    llm_provider: str = "openai"  # "openai" or "anthropic"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_max_tokens: int = 4096
    embedding_model: str = "all-MiniLM-L6-v2"
    topic_similarity_threshold: float = 0.7

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def ensure_dirs(self) -> None:
        for d in [self.data_dir, self.audio_dir, self.transcript_dir, self.db_path.parent]:
            d.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    return Settings()
