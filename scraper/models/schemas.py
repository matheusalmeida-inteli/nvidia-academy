"""Pydantic models for scraped data."""
from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EstagioEnum(StrEnum):
    PRE_SEED = "pre-seed"
    SEED = "seed"
    SERIE_A = "serie_a"
    SERIE_B = "serie_b"
    SERIE_C = "serie_c"
    SERIE_D = "serie_d"
    SERIE_LATER = "serie_later"
    DESCONHECIDO = "desconhecido"


class DocumentoTipoEnum(StrEnum):
    SITE_INSTITUCIONAL = "site_institucional"
    BLOG = "blog"
    NOTICIA = "noticia"
    VAGA = "vaga"
    PERFIL_FOUNDER = "perfil_founder"
    RELEASE = "release"
    CAREERS = "careers"
    LINKEDIN = "linkedin"
    OUTRO = "outro"


class StartupCreate(BaseModel):
    """Schema for inserting a new startup."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    nome: str = Field(..., min_length=1, max_length=500)
    site: str | None = None
    setor: str | None = None
    estagio: EstagioEnum = EstagioEnum.DESCONHECIDO
    localizacao: str | None = None
    descricao_curta: str | None = None
    ano_fundacao: int | None = Field(default=None, ge=1900, le=2030)
    tamanho_time: int | None = Field(default=None, ge=1)
    fontes_scraping: list[str] = Field(default_factory=list)

    @field_validator("site")
    @classmethod
    def normalize_url(cls, v: str | None) -> str | None:
        if not v:
            return None
        v = v.strip()
        if not v:
            return None
        if not v.startswith(("http://", "https://")):
            v = "https://" + v
        return v


class StartupRecord(StartupCreate):
    """Startup as returned from database (with id and timestamps)."""

    id: int
    uuid: UUID
    created_at: datetime
    updated_at: datetime


class DocumentoCreate(BaseModel):
    """Schema for inserting a new document."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    startup_nome: str = Field(..., min_length=1)
    tipo: DocumentoTipoEnum = DocumentoTipoEnum.OUTRO
    titulo: str | None = None
    conteudo_texto: str = Field(..., min_length=20)
    url_fonte: str = Field(..., min_length=8)
    data_publicacao: date | None = None
    source_meta: dict = Field(default_factory=dict)

    @field_validator("url_fonte")
    @classmethod
    def require_url_scheme(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("url_fonte must include scheme")
        return v


class DocumentoRecord(DocumentoCreate):
    """Document as returned from database."""

    id: int
    uuid: UUID
    startup_id: int
    created_at: datetime
