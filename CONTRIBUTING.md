# Contributing

Projeto do processo seletivo **Inteli Academy — NVIDIA Startup AI Radar**.

## Como contribuir

1. Clone o repo e crie uma branch (`feature/nome` ou `fix/nome`).
2. Instale o ambiente: `pixi install` (ver `docs/INSTALL.md`).
3. Faça as alterações com testes (`pixi run test`) e lint (`pixi run lint`).
4. Atualize a documentação (`docs/`) se a mudança afeta API, deploy ou comportamento.
5. Abra PR. Mínimo: descrição + verificação de testes verdes + 0 erros de lint.

## Regras

- Nunca commitar `.env`, `logs/`, `snapshots/`, `.next/`, `node_modules/` (já ignorados).
- Mantenha a versão unificada entre `api/main.py` (`2.1.0`) e `web/package.json`.
- Documente novas variáveis de ambiente em `docs/ENV.md`.
- Se alterar endpoints, atualize `docs/API.md`.
- Se alterar pipeline (agentes), documente em `docs/ARQUITETURA.md` e `docs/AGENTES.md`.

## Testes

```bash
pixi run test        # todos (110 passing esperado)
pixi run test-rag    # RAG (16 passing)
pixi run lint        # 0 erros
```

## Código de conduta

Seja direto, respeite o contexto acadêmico (Inteli Academy), e não exponha secrets (chaves API, senhas) no código ou docs.
