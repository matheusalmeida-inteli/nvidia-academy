# Como Criar um Novo Agente

Guia prático de extensão da pipeline LangGraph. Segue o padrão dos 9 agentes
existentes (ver `docs/AGENTES.md` e `agents/graph.py`).

## 1. Visão geral do padrão

Cada agente é uma **função de nó** em `agents/nodes/*.py` que:
1. Recebe `state: AgentState` (o estado completo da execução);
2. Lê os canais de entrada que precisa;
3. Produz um **novo** valor de estado (retorna `AgentState` ou um dict com
   os campos alterados);
4. Atualiza `state.next_agent` quando o próximo passo não é determinístico
   pelo grafo (padrão opcional; as arestas fixas dispensam isso).

O nó é registrado em `build_graph()` e envolto por `_instrument_node`, que
mede tempo/contagem automaticamente (telemetria NDJSON).

## 2. Passo a passo

### 2.1. Criar o arquivo do nó

`agents/nodes/novo_agente.py`:

```python
"""Descrição formal do agente: propósito, entradas, saídas."""
from __future__ import annotations

from agents.state import AgentState
from agents.observability import instrument  # (se existir helper por nó)

async def novo_agente(state: AgentState) -> AgentState:
    # 1. Ler entradas
    perfis = state.extracted_profiles or []
    # 2. Processar (heurísticas ou LLM via agents.llm.LLMClient)
    resultado = [{"name": p.get("nome"), ...} for p in perfis]
    # 3. Escrever no estado (retornar dict com os canais alterados)
    return {
        "novo_resultado": resultado,
        "next_agent": "proximo_no",  # opcional, se houver roteamento
    }
```

> Se o nó tocar `state.telemetry` (ex.: `node_token_usage`), use os helpers
> existentes em `agents/llm.py` (`last_call_stats()`).

### 2.2. Adicionar o canal de estado

Em `agents/state.py`, crie a dataclass de saída (se complexa) e o campo em
`AgentState`:

```python
@dataclass
class NovoResultado:
    campo_a: str
    campo_b: list[str] = field(default_factory=list)

# em AgentState:
novo_resultado: list[dict] = field(default_factory=list)
```

`langgraph` irá propagar o canal automaticamente no estado final
(`result["novo_resultado"]`).

### 2.3. Registrar no grafo (`agents/graph.py`)

1. Importe o nó no topo do módulo.
2. Adicione à lista de `for node_name, node_fn in [...]`:
   ```python
   ("novo_agente", novo_agente),
   ```
3. Conecte as arestas, posicionando onde o novo agente entra:

   **Caso A — no meio do fluxo linear (ex.: após o classifier):**
   ```python
   g.add_edge("classifier", "novo_agente")
   g.add_edge("novo_agente", "evidence_validator")
   ```

   **Caso B — antes do nó final:**
   ```python
   g.add_edge("briefing", "novo_agente")
   g.add_edge("novo_agente", END)
   ```

   **Caso C — com roteamento condicional novo:**
   ```python
   def decide_novo(state: AgentState):
       if state.some_flag:
           return "novo_agente"
       return "nvidia_rag"

   g.add_conditional_edges(
       "recommendation",
       decide_novo,
       {"novo_agente": "novo_agente", "nvidia_rag": "nvidia_rag"},
   )
   g.add_edge("novo_agente", "briefing")
   ```

> **Regra:** toda função de roteamento deve retornar exatamente uma das chaves
> do mapeamento. Use `Literal["a", "b"]` como tipo de retorno para segurança.

### 2.4. Telemetria

- O timing/counting é automático (`_instrument_node`).
- Se o agente chamar LLM ou RAG, registre tokens/scores no `state.telemetry`
  (ex.: `node_token_usage["novo_agente"] = client.last_call_stats()`).
- A telemetria é persistida em `logs/telemetry-<data>.ndjson` ao final
  (`run_pipeline` → `submit_result`).

## 3. Integração com a API/Web

Se o novo agente produz informação destinada ao usuário:

1. **API** (`api/main.py`): inclua o campo em `QueryResponse` e no mapeamento
   `_dict()`/`build_startup_payload` para expor no JSON.
2. **Web** (`web/lib/api.ts`): adicione o campo às interfaces TypeScript; no
   componente relevante (ex.: `BriefingPanel`, `StartupCard`), renderize.

## 4. Testes

1. **Unit tests** (`tests/`): funções puras do nó — mesmos padrões de
   `tests/test_recommendation_scoring.py` (fixtures de perfil/classificação).
2. **Regression** (`rag_audit/`): se mexer no RAG, adicione classe seguindo o
   estilo das existentes.

Exemplo mínimo:

```python
# tests/test_novo_agente.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agents.nodes.novo_agente import novo_agente
from agents.state import AgentState

def test_novo_agente_produz_saida():
    state = AgentState(user_query="fintech AI")
    state.extracted_profiles = [{"nome": "X", "setor": "fintech"}]
    out = await novo_agente(state)  # ou loop.run_until_complete
    assert out["novo_resultado"]
```

Rode: `pixi run pytest tests/ -q`.

## 5. Boas práticas

- **Determinismo:** sempre tenha caminho determinístico quando não houver
  LLM (sem `OPENROUTER_API_KEY`). O sistema deve rodar offline.
- **Não quebre o grafo:** nenhum nó deve levantar exceção fatal — registre em
  `state.errors` e retorne o estado adiante (como `retriever` faz ao falhar
  o banco).
- **Rotule origens:** se seu agente deriva informação, exponha a origem
  (ex.: `origem=rag`, `score_breakdown`) para auditoria, como o motor de
  recomendação faz.
- **Docstrings:** documente entrada/saída/saída do agente e mantenha a
  documentação do grafo (`docs/ARQUITETURA.md`, `docs/AGENTES.md`) em
  sincronia.

## 6. Checklist

- [ ] `agents/nodes/novo_agente.py` criado com docstring (propósito, inputs,
      outputs, decisões);
- [ ] campos novos em `agents/state.py` (dataclass + canal em `AgentState`);
- [ ] import + registro em `agents/graph.py` (nó na lista e arestas corretas);
- [ ] roteamento condicional (se aplicável) com `Literal` no tipo de retorno;
- [ ] telemetria (timing automático + uso de tokens/RAG se aplicável);
- [ ] exposição na API (`api/main.py`) e no front (`web/lib/api.ts`);
- [ ] testes unitários em `tests/` passando (`pixi run pytest -q`);
- [ ] documentação atualizada (`docs/AGENTES.md`).