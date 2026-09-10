# Módulo `web/` — Frontend (Next.js + TypeScript + Tailwind)

Interface web do NVIDIA Startup AI Radar: consulta ao pipeline, painel de
briefing executivo e painel de nurture/CRM.

Versão 2.1.0 (alinhada com `api/main.py`).

## Estrutura

| Caminho | Papel |
|---|---|
| `app/page.tsx` | Página principal: consulta + resultados (`StartupCard`) + briefing + exportação |
| `app/pipeline/` | Visualização/fluxo do pipeline multi-agente (quando disponível) |
| `app/nurture/` | Painel de candidates e próximas ações de nurture |
| `components/AppShell.tsx` | Layout shell (barras/navegação) |
| `components/StartupCard.tsx` | Card de startup (categoria, scores, recomendações, fontes RAG) |
| `components/BriefingPanel.tsx` | Briefing executivo consolidado |
| `components/NurturePanel.tsx` | Ações de nurture e logs |
| `lib/api.ts` | Cliente HTTP da API (usa `NEXT_PUBLIC_API_URL`) |
| `app/globals.css` | Tema dark com accents NVIDIA-green |

## Configuração

Variável de ambiente do lado do cliente:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

(em `web/.env.local`; a API precisa estar no ar — ver `api/README.md`.)

## Uso

```bash
cd web
npm install
npm run dev        # Next.js em http://localhost:3000
```

Outros scripts: `npm run build`, `npm run start`, `npm run lint`.

## Exportação de briefing

O botão **"Exportar briefing"** na barra de resultados chama `POST /query/export`
e faz o download de `briefing_nvidia_radar.json` (payload idêntico ao de `/query`,
com startups + briefing + fontes RAG). Para PDF, use impressor do navegador
(Ctrl+P) sobre a página de resultados — o layout é preparado para impressão.
`/query/export` reutiliza o mesmo pipeline de `/query` (`lib/api.ts::exportBriefing`).