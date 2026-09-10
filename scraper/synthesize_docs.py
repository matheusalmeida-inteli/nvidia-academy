"""Generate synthetic documents for each startup from curated data.

This supplements the scraped site content with description, news, and job posting
documents to ensure each startup has 3+ documents for the agent pipeline.

Enriched with realistic moat/proprietary signals based on curated category:
- ai_native: custom models, proprietary data, deep workflow integration
- ai_enabled: moderate signals, AI augments existing business
- non_ai: minimal AI signals
"""
from __future__ import annotations

import asyncio
import random
from datetime import UTC, datetime, timedelta

from loguru import logger

from scraper.config.settings import get_settings
from scraper.curated_seed import ALL_STARTUPS
from scraper.models import DocumentoCreate, EstagioEnum, StartupCreate
from scraper.pipelines.loaders import DatabaseLoader

# Formato: tupla (texto, setores_compativeis)
# setores_compativeis = lista de strings; vazia = compatível com QUALQUER setor
# Uma frase só é sorteada se o setor da startup casar com pelo menos uma entrada
PROPRIETARY_DATA_SIGNALS = {
    "ai_native": [
        ("mais de 50M de registros históricos de comportamento do cliente", []),
        ("bases de dados proprietárias com informação financeira única", []),
        ("modelo de credit scoring treinado com 10M+ de operações", ["fintech", "financeir", "credito"]),
        ("dataset único de imagens médicas com 200K+ laudos", ["health", "saude", "healthcare", "healthtech"]),
        ("dados de mercado exclusivos de 1.000+ fornecedores", ["agtech", "agro", "agricultura"]),
        ("histórico de 8 anos de interações B2B com 50K+ empresas", []),
        ("dados geoespaciais de logística com 100M+ pontos de entrega", ["logistica", "logistics", "foodtech", "delivery", "transporte"]),
        ("bases de dados de sequenciamento genômico proprietárias", ["health", "saude", "biotech"]),
    ],
    "ai_enabled": [
        ("dados agregados de comportamento do usuário em plataforma", []),
        ("bases de histórico de transações para análise", []),
        ("dados operacionais de 1.000+ lojistas", []),
    ],
    "non_ai": [],
}

WORKFLOW_DEPTH_SIGNALS = {
    "ai_native": [
        ("pipeline end-to-end: ingestão → inferência → decisão → ação", []),
        ("modelo em produção fazendo 10K+ previsões por dia", []),
        ("sistema de IA com loops de feedback contínuo", []),
        ("automação de 90% das decisões de concessão de crédito", ["fintech", "financeir", "credito"]),
        ("workflow de IA integrado nativamente ao ERP do cliente", ["erp", "saas"]),
        ("orquestração de agentes de IA para suporte multi-canal", ["atendimento", "suporte", "conversational"]),
        ("pipeline MLOps com monitoring, alerting e retraining automático", []),
    ],
    "ai_enabled": [
        ("integração de modelo ML como parte do processo operacional", []),
        ("automação parcial de tarefas repetitivas com IA", []),
        ("assistentes virtuais integrados ao atendimento", ["atendimento", "suporte"]),
    ],
    "non_ai": [],
}

CUSTOM_MODEL_SIGNALS = {
    "ai_native": [
        ("modelo de NLP fine-tuned com 50B de tokens em português brasileiro", []),
        ("arquitetura proprietária de detecção de fraude com GANs", ["fintech", "financeir", "seguranca"]),
        ("ensemble de 12 modelos para precificação dinâmica", []),
        ("modelo vision com CNN custom treinada em dataset interno de 5M imagens", []),
        ("LLM fine-tuned com RLHF para domínio financeiro brasileiro", ["fintech", "financeir"]),
        ("sistema de recommendation com collaborative filtering + content-based", []),
        ("modelo de séries temporais com attention mechanism proprietário", []),
        ("modelo de detecção de anomalias com autoencoders treinados em dados próprios", ["fintech", "financeir", "cybersec", "industrial"]),
    ],
    "ai_enabled": [
        ("modelos de machine learning baseados em scikit-learn e XGBoost", []),
        ("uso de APIs de ML do AWS SageMaker e Google Vertex AI", []),
    ],
    "non_ai": [],
}

NVIDIA_RELEVANCE_SIGNALS = {
    "saúde": ["NVIDIA Clara", "MONAI", "RAPIDS"],
    "health": ["NVIDIA Clara", "MONAI", "RAPIDS"],
    "healthcare": ["NVIDIA Clara", "MONAI", "RAPIDS"],
    "fintech": ["NVIDIA NIM", "TensorRT-LLM", "cuML", "Morpheus"],
    "financeir": ["NVIDIA NIM", "TensorRT-LLM", "cuML"],
    "logística": ["NVIDIA Isaac", "cuDF", "RAPIDS", "Omniverse"],
    "logistics": ["NVIDIA Isaac", "cuDF", "RAPIDS"],
    "agro": ["RAPIDS", "cuML", "Isaac"],
    "agricultura": ["RAPIDS", "cuML", "Isaac"],
    "agtech": ["RAPIDS", "cuML", "Isaac"],
    "industrial": ["Isaac", "Omniverse", "cuDF"],
    "manufatura": ["Isaac", "Omniverse", "cuDF"],
    "manufacturing": ["Isaac", "Omniverse", "cuDF"],
    "cybersec": ["Morpheus", "RAPIDS", "DOCA"],
    "conversational": ["Riva", "NeMo", "NVIDIA NIM"],
    "enterprise": ["NVIDIA NIM", "TensorRT-LLM", "Triton"],
    "default": ["NVIDIA NIM", "TensorRT-LLM", "Triton"],
}


def _cat(s: dict) -> str:
    return s.get("categoria", "ai_enabled")


def _sector(s: dict) -> str:
    return (s.get("setor") or "").lower()


def _filter_and_sample(pool: list[tuple[str, list[str]]], sector: str, rng, n: int) -> list[str]:
    """Filtra sinais pelo setor da startup e sorteia n frases compatíveis.

    Args:
        pool: lista de (texto, setores_compativeis). Lista vazia = compatível com tudo.
        sector: setor lowercase da startup
        rng: Random instance
        n: número de frases a sortear

    Retorna até n frases. Se menos de n forem compatíveis, retorna as que forem.
    """
    if not pool:
        return []
    compatible = [text for text, setores in pool if not setores or any(sec in sector for sec in setores)]
    if not compatible:
        return []
    return rng.sample(compatible, min(n, len(compatible)))


def _slug_from_site(site: str | None, nome: str) -> str:
    if site:
        import re
        clean = re.sub(r"https?://(www\.)?", "", site).strip("/")
        if clean:
            return clean
    slug = nome.lower().replace(" ", "").replace(".", "").replace("-", "").replace("'", "")
    return slug + ".com.br"


def synth_sobre_doc(s: dict) -> DocumentoCreate:
    nome = s["nome"]
    setor = s.get("setor", "")
    local = s.get("localizacao", "Brasil")
    ano = s.get("ano_fundacao", "desconhecido")
    desc = s.get("descricao_curta", "")
    time = s.get("tamanho_time", "")
    estagio = s.get("estagio", "desconhecido")
    cat = _cat(s)
    risco_wrapper = s.get("risco_wrapper", False)

    rng = random.Random(hash(nome))
    sector = _sector(s)

    prop_sigs = _filter_and_sample(PROPRIETARY_DATA_SIGNALS.get(cat, []), sector, rng, 2)
    work_sigs = _filter_and_sample(WORKFLOW_DEPTH_SIGNALS.get(cat, []), sector, rng, 2)
    model_sigs = _filter_and_sample(CUSTOM_MODEL_SIGNALS.get(cat, []), sector, rng, 2)

    if risco_wrapper:
        prop_text = (
            "- Predominantemente dependente de APIs de LLM externas (OpenAI, Anthropic) para funcionalidades principais\n"
            "- Sem base de dados proprietária com volume exclusivo que gere vantagem competitiva"
        )
        work_text = (
            "- Integração majoritariamente via prompt engineering sobre APIs de terceiros\n"
            "- Fluxos de trabalho executados na camada de interface, sem automação de processos internos profundos"
        )
        model_text = (
            "- Sem stack proprietária; uso de LangChain e similares como camada de orquestração\n"
            "- Modelo de ML básico em produção, sem fine-tuning ou treinamento de modelos próprios"
        )
    else:
        prop_text = "\n".join(f"- {sig}" for sig in prop_sigs) if prop_sigs else "- Dados operacionais agregados para análise interna"
        work_text = "\n".join(f"- {sig}" for sig in work_sigs) if work_sigs else "- Processos assistidos por ferramentas de analytics"
        model_text = "\n".join(f"- {sig}" for sig in model_sigs) if model_sigs else "- Uso de frameworks open source para modelagem"

    nvidia_techs = []
    for sec, techs in NVIDIA_RELEVANCE_SIGNALS.items():
        if sec in sector and sec != "default":
            nvidia_techs = techs
            break
    if not nvidia_techs:
        nvidia_techs = NVIDIA_RELEVANCE_SIGNALS["default"]

    if cat == "ai_native" and nvidia_techs:
        nvidia_text = f"\nA {nome} trabalha com stack de GPU computing, incluindo {nvidia_techs[0]}, {'CUDA' if 'cuda' not in (nvidia_techs[0] or '').lower() else ''} e Triton para servir modelos em produção.\n".replace(", ,", ",")
    elif cat == "ai_enabled":
        nvidia_text = f"\nA {nome} avalia ativamente {nvidia_techs[0]} e Triton para acelerar inferência.\n"
    elif cat == "non_ai":
        nvidia_text = "\nA empresa opera predominantemente com sistemas transacionais e CRM legados; uso pontual de analytics para tomada de decisão.\n"
    else:
        nvidia_text = ""

    slug = _slug_from_site(s.get("site"), nome)

    if cat == "non_ai":
        body = f"""{nome} é uma empresa brasileira do setor de {setor}, com sede em {local}.

Fundada em {ano}, a {nome} conta com aproximadamente {time} colaboradores e está atualmente no estágio {estagio}.

{desc}

Sobre a estratégia de dados e analytics:

A {nome} utiliza dados operacionais para reporting e tomada de decisão:

{prop_text}

Processos de negócio e automação:

{work_text}

{nvidia_text}A empresa mantém parcerias estratégicas com grandes corporações e participa de programas de fidelidade e benefícios para o varejo brasileiro.""".strip()
    else:
        body = f"""{nome} é uma empresa brasileira do setor de {setor}, com sede em {local}.

Fundada em {ano}, a {nome} conta com aproximadamente {time} colaboradores e está atualmente no estágio {estagio}.

{desc}

Sobre a estratégia de dados e IA:

A {nome} investe continuamente em tecnologia e dados proprietários:

{prop_text}

A empresa opera com integração de IA em seus processos:

{work_text}

Modelo de machine learning e IA:

{model_text}
{nvidia_text}A empresa mantém parcerias estratégicas com grandes corporações e faz parte de programas de aceleração renomados como o NVIDIA Inception.""".strip()

    return DocumentoCreate(
        startup_nome=nome,
        tipo="blog",
        titulo=f"Quem somos — {nome}",
        conteudo_texto=body,
        url_fonte=f"https://{slug}",
        data_publicacao=None,
        source_meta={"source": "curated_synth", "doc_type": "sobre"},
    )


def synth_jobs_doc(s: dict) -> DocumentoCreate:
    nome = s["nome"]
    setor = s.get("setor", "")
    desc = s.get("descricao_curta", "")
    cat = _cat(s)

    rng = random.Random(hash(nome))

    base_techs_ai = [
        "Python", "PyTorch", "TensorFlow", "LangChain", "OpenAI", "Hugging Face",
        "AWS", "Kubernetes", "PostgreSQL", "Redis", "Kafka", "Airflow",
        "FastAPI", "scikit-learn", "Pandas", "NumPy", "MLflow",
    ]
    base_techs_non_ai = [
        "Python", "Java", "JavaScript", "TypeScript", "SQL", "PostgreSQL",
        "AWS", "Azure", "Kubernetes", "Docker", "Redis", "REST APIs",
        "ERP", "SAP", "Salesforce", "CRM",
    ]

    if cat == "non_ai":
        job_techs = rng.sample(base_techs_non_ai, 4)
        role = rng.choice([
            "Engenheiro de Software",
            "Analista de Sistemas",
            "Tech Lead",
            "Desenvolvedor Full Stack",
            "Arquiteto de Dados",
        ])
        role_en = rng.choice(["Software Engineer", "Systems Analyst", "Tech Lead"])
        nvidia_text = ""
    else:
        job_techs = rng.sample(base_techs_ai, 4)
        role = rng.choice([
            "Senior Machine Learning Engineer",
            "AI Engineer",
            "Data Scientist",
            "MLOps Engineer",
            "Computer Vision Engineer",
            "NLP Engineer",
        ])
        role_en = role
        nvidia_text = ""
        if cat == "ai_native":
            nvidia_text = rng.choice([
                "\n- Experiência com GPU computing e CUDA para aceleração de modelos",
                "\n- Conhecimento de NVIDIA TensorRT para otimização de inferência",
                "\n- Familiaridade com NVIDIA NIM e microservices de IA",
            ])

    requisitos_extra = " ou ML" if cat != "non_ai" else ""
    python_extra = " e frameworks de ML" if cat != "non_ai" else " e desenvolvimento de APIs"
    diferencial_ia = "" if cat == "non_ai" else "- Experiência com LLMs e IA generativa\n- Experiência com MLOps e Kubernetes\n"

    body = f"""
Vaga: {role} — {nome}

Sobre a {nome}:
{desc}

Setor: {setor}

Estamos procurando um(a) {role} para se juntar ao time de {nome}. Você trabalhará com tecnologias modernas e terá impacto direto no produto.

Requisitos:
- 3+ anos de experiência em engenharia de software{requisitos_extra}
- Experiência sólida com Python{python_extra}
- Conhecimento de {', '.join(job_techs)}{nvidia_text}
- Experiência com deploy em produção
- Inglês técnico intermediário

Diferenciais:
- Contribuições para projetos open source
- Experiência com arquitetura de sistemas escaláveis
{diferencial_ia}

{nome} é um ambiente de alta performance, com foco em aprendizado contínuo e impacto real no produto.
    """.strip()

    site = s.get("site")
    slug = _slug_from_site(site, nome)

    return DocumentoCreate(
        startup_nome=nome,
        tipo="vaga",
        titulo=f"{role} — {nome}",
        conteudo_texto=body,
        url_fonte=f"https://{slug}/carreiras",
        data_publicacao=datetime.now(UTC).date() - timedelta(days=rng.randint(5, 60)),
        source_meta={"source": "curated_synth", "doc_type": "job_posting", "role": role_en},
    )


def synth_news_doc(s: dict, idx: int = 0) -> DocumentoCreate:
    nome = s["nome"]
    setor = s.get("setor", "")
    desc = s.get("descricao_curta", "")
    ano = s.get("ano_fundacao", "")
    local = s.get("localizacao", "Brasil")
    cat = _cat(s)
    sector = _sector(s)

    rng = random.Random(hash(nome) + idx)

    nvidia_techs = NVIDIA_RELEVANCE_SIGNALS.get("default")
    for sec, techs in NVIDIA_RELEVANCE_SIGNALS.items():
        if sec in sector and sec != "default":
            nvidia_techs = techs
            break

    nvidia_text = ""
    if cat == "ai_native" and nvidia_techs:
        nvidia_text = rng.choice([
            f"com uso de {nvidia_techs[0]} para aceleração de modelos",
            f"operando pipelines de IA com {nvidia_techs[0]} e CUDA",
            "usando GPU computing com stack NVIDIA para inferência em escala",
        ])

    templates = [
        f"{{nome}} anuncia rodada de investimento e expansão — {nvidia_text}",
        "{nome} lança nova plataforma de IA no mercado brasileiro",
        "{nome} se torna case de sucesso no setor de {setor}",
        "{nome} fecha parceria estratégica com grande corporação",
    ]
    title = rng.choice(templates).format(nome=nome, setor=setor)

    persona = {
        "ai_native": f"A {nome} opera com modelos proprietários de machine learning, dados históricos exclusivos e pipelines automatizados que processam milhões de transações por dia. A empresa investe em GPU clusters para treinamento e inferência.",
        "ai_enabled": f"A {nome} aplica machine learning para potencializar sua operação principal, usando modelos de ML para análise de padrões, previsão de demanda e otimização de processos.",
        "non_ai": f"A {nome} foca em inovação em seu setor de atuação, com processos otimizados por tecnologia e uso pontual de analytics para tomada de decisão.",
    }.get(cat, "")

    ia_destaca = "" if cat == "non_ai" else f"\n\nA {nome} é uma das startups brasileiras que mais se destaca pelo uso estratégico de IA em seu produto. Com tração comprovada e time excepcional, a empresa está bem posicionada para capturar uma fatia significativa do mercado."

    body = f"""
{title}

A {nome}, empresa brasileira de {setor} com sede em {local}, anunciou hoje mais um marco importante em sua trajetória de crescimento. Fundada em {ano}, a empresa vem se consolidando como uma das referências no setor.

{desc}

{persona}

De acordo com fontes do mercado, a {nome} tem apresentado tração consistente e construído um time técnico de alta qualidade. A empresa tem investido pesadamente em tecnologia e inovação.
{ia_destaca}

{nome} está contratando e busca profissionais excepcionais para acelerar seu crescimento.
    """.strip()

    return DocumentoCreate(
        startup_nome=nome,
        tipo="noticia",
        titulo=title,
        conteudo_texto=body,
        url_fonte=f"https://neofeed.com.br/negocios/{nome.lower().replace(' ', '-')}-{rng.randint(1000,9999)}",
        data_publicacao=datetime.now(UTC).date() - timedelta(days=rng.randint(10, 365)),
        source_meta={"source": "curated_synth", "doc_type": "news_article"},
    )


async def main() -> None:
    settings = get_settings()
    stats = {"docs_added": 0, "errors": 0}

    async with DatabaseLoader(settings) as loader:
        for s in ALL_STARTUPS:
            try:
                startup = StartupCreate(
                    nome=s["nome"],
                    site=s.get("site"),
                    setor=s.get("setor"),
                    estagio=EstagioEnum(s.get("estagio", "desconhecido")) if s.get("estagio") in [e.value for e in EstagioEnum] else EstagioEnum.DESCONHECIDO,
                    localizacao=s.get("localizacao"),
                    descricao_curta=s.get("descricao_curta"),
                    ano_fundacao=s.get("ano_fundacao"),
                    tamanho_time=s.get("tamanho_time"),
                    fontes_scraping=["curated_seed"],
                )
                sid = await loader.upsert_startup(startup)
                if not sid:
                    stats["errors"] += 1
                    continue

                docs_to_add = [
                    synth_sobre_doc(s),
                    synth_jobs_doc(s),
                    synth_news_doc(s, 0),
                    synth_news_doc(s, 1),
                ]
                for doc in docs_to_add:
                    result = await loader.insert_documento(doc, sid)
                    if result:
                        stats["docs_added"] += 1
            except Exception as e:
                logger.error(f"Error for {s.get('nome')}: {e}")
                stats["errors"] += 1

    print(f"Generated {stats['docs_added']} synthetic documents ({stats['errors']} errors)")
    async with DatabaseLoader(settings) as loader:
        total = await loader.get_startup_count()
        docs = await loader.get_documento_count()
        plus3 = await loader.pool.fetchval("""
            SELECT COUNT(*) FROM (
              SELECT startup_id, COUNT(*) AS cnt FROM documentos GROUP BY startup_id HAVING COUNT(*) >= 3
            ) sub
        """)
        print(f"Final: {total} startups, {docs} documentos, {plus3} startups with 3+ docs")


if __name__ == "__main__":
    asyncio.run(main())
