from functools import lru_cache
from ipaddress import ip_address
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT / ".env", ROOT / "backend/.env"), extra="ignore"
    )
    database_url: SecretStr = SecretStr(
        "postgresql://fabrica:fabrica_local@127.0.0.1:5543/fabrica?connect_timeout=5"
    )
    llm_provider: Literal["openai_compatible"] = "openai_compatible"
    llm_base_url: str = ""
    llm_model: str = ""
    llm_api_style: Literal["chat_completions", "responses"] = "responses"
    llm_auth_style: Literal["bearer", "api-key"] = "bearer"
    llm_api_key: SecretStr = SecretStr("")
    llm_temperature: float = Field(default=0.2, ge=0, le=2)
    llm_max_tokens: int = Field(default=2048, ge=256, le=32768)
    mockup_max_tokens: int = Field(default=6144, ge=1024, le=32768)
    backlog_max_tokens: int = Field(default=4096, ge=1024, le=32768)
    architecture_max_tokens: int = Field(default=6144, ge=1024, le=32768)
    construction_max_tokens: int = Field(default=12000, ge=2048, le=32768)
    # Modelo específico para la fase de construcción (vacío = usa llm_model).
    # Permite usar un modelo más robusto solo donde se genera código real.
    construction_model: str = ""
    # Timeout por intento específico para construcción (Sol tarda más que el modelo mini
    # en la etapa de pruebas; con el timeout general de 180s fallaba sistemáticamente).
    construction_timeout: float = Field(default=420, gt=0)
    workspace_dir: Path = ROOT / "workspace"
    # Catálogo de tecnologías que los arquitectos pueden proponer (ARCHITECTURE_TECHNOLOGIES en .env).
    architecture_technologies: list[str] = [
        "Angular",
        "Nginx",
        "Python",
        "FastAPI",
        "PostgreSQL",
        "Docker",
        "Docker Compose",
        "Kubernetes",
        "AWS EKS",
        "AWS ECR",
        "AWS RDS PostgreSQL",
        "AWS ALB",
        "AWS Secrets Manager",
        "AWS CloudWatch",
        "SMTP",
    ]
    llm_timeout: float = Field(default=180, gt=0)
    rewrite_provider: Literal["openai_compatible"] = "openai_compatible"
    rewrite_base_url: str = ""
    rewrite_model: str = ""
    rewrite_api_style: Literal["chat_completions", "responses"] | None = None
    rewrite_auth_style: Literal["bearer", "api-key"] | None = None
    rewrite_api_key: SecretStr = SecretStr("")
    embedding_provider: Literal["openai_compatible"] = "openai_compatible"
    embedding_base_url: str = ""
    embedding_model: str = ""
    embedding_auth_style: Literal["bearer", "api-key"] | None = None
    embedding_dimensions: int = Field(default=1536, gt=0)
    embedding_api_key: SecretStr = SecretStr("")
    retrieval_k: int = Field(default=12, ge=1, le=100)
    final_k: int = Field(default=5, ge=1, le=30)
    chunk_size: int = Field(default=1100, ge=200, le=6000)
    chunk_overlap: int = Field(default=180, ge=0)
    api_token: SecretStr = SecretStr("")
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: list[str] = ["http://localhost:4200", "http://127.0.0.1:4200"]
    storage_dir: Path = ROOT / "storage"
    max_upload_mb: int = 20
    # Despliegue remoto automático tras aprobar una construcción (opcional).
    # Si deploy_remote_enabled es false, esta función no hace nada (no-op seguro).
    deploy_remote_enabled: bool = False
    deploy_remote_host: str = ""
    deploy_remote_user: str = "ubuntu"
    deploy_remote_key_path: str = ""
    deploy_remote_base_dir: str = "~/despliegues"
    deploy_remote_base_port: int = Field(default=8200, ge=1, le=65000)

    @model_validator(mode="after")
    def validate_chunking(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP debe ser menor que CHUNK_SIZE")
        if self.final_k > self.retrieval_k * 2:
            raise ValueError("FINAL_K excede los candidatos disponibles")
        if not self._is_loopback(self.api_host):
            if not self.api_token.get_secret_value():
                raise ValueError("API_TOKEN es obligatorio si API_HOST no es loopback")
            for origin in self.cors_origins:
                parsed = urlsplit(origin)
                if origin == "*" or (parsed.scheme != "https" and not self._is_loopback(parsed.hostname or "")):
                    raise ValueError(
                        "CORS_ORIGINS debe usar HTTPS cuando API_HOST se expone a la red"
                    )
        return self

    @staticmethod
    def _is_loopback(host: str) -> bool:
        normalized = host.strip().strip("[]").lower()
        if normalized == "localhost":
            return True
        try:
            return ip_address(normalized).is_loopback
        except ValueError:
            return False

    @property
    def embedding_signature(self) -> str:
        return f"{self.embedding_provider}:{self.embedding_model}:{self.embedding_dimensions}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
