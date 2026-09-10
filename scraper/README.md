# Módulo `scraper/` — Coleta de fontes

Coleta opcional de conteúdo das 22 fontes listadas no TAPI §7, com pipelines
de limpeza e exportação. O seed principal do projeto é curado
(`scraper/curated_seed.py`); o scraper atende à seção de coleta do TAPI.

## Estrutura

| Caminho | Papel |
|---|---|
| `config/settings.py` | Configurações via Pydantic (`Settings`, `get_settings`) |
| `config/sources.py` | Catálogo das fontes do TAPI (22), prioridades e categorias |
| `spiders/` | Um spider por fonte (wow, latitud, distrito, neofeed, startse, valor, ...) + `_base_news.py`/`_base_aggregator.py` |
| `pipelines/` | Infra: HTTP (`http_client.py`), limpeza (`html_cleaner.py`), export (`jsonl_exporter.py`), carga no Postgres (`loaders.py`), spider base |
| `models/schemas.py` | Schemas `StartupCreate`/`DocumentoCreate` |
| `data/` | Pastas de export (`exports`, `processed`, `raw`) |
| `curated_seed.py` | Seed curado com 56 startups (principal fonte de dados do sistema) |
| `curate.py` | Curadoria/refinamento de dados coletados |
| `synthesize_docs.py` | Gera 4 documentos textuais por startup (para o RAG) |
| `run.py` | CLI do scraper |
| `setup.sh` | Instalação (playwright, etc.) |

## CLI (`python -m scraper.run`)

```bash
pixi run python -m scraper.run --all            # roda todas as fontes habilitadas
pixi run python -m scraper.run --source wow --limit 5
pixi run python -m scraper.run --source distrito --output jsonl
pixi run python -m scraper.run --enrich         # enriquecimento (ex. categorização)
pixi run python -m scraper.run --stats
```

## Seed e documentos sintéticos

```bash
# Cria a base (56 startups) no PostgreSQL via synthesize_docs
pixi run python -m scraper.synthesize_docs

# Curadoria manual (opcional)
pixi run python -m scraper.curate
```

Detalhes do schema e do seed: [`docs/BASE_DADOS.md`](../docs/BASE_DADOS.md).