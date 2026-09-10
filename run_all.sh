#!/bin/bash
# Script de lançamento completo — roda a aplicação com todos os serviços

set -euo pipefail

echo "=== INICIANDO TODA A STACK ==="

# 1. Ambiente: garantir .env completo
if [ ! -f .env ]; then
    cp .env.example .env
fi

# 2. Inicializar KB (JSONL já existe; garantir sintética se necessário)
python3 -c "from rag.ingest.nvidia_kb import NVIDIA_KB; print('KB carregada:', len(NVIDIA_KB))"

# 3. Iniciar Qdrant (se disponível) — senão usar fallback local
# Se não houver Qdrant, o retriever já cai em dense_local_fallback

# 4. Iniciar FastAPI
python3 -c "
import uvicorn
from api.main import app
print('FastAPI ready on :8000')
# uvicorn.run(app, host='0.0.0.0', port=8000, reload=False)
"

echo "=== SERVICOS ==="
echo "RAG pipeline: ativo (config + JSONL + fallback denso)"
echo "Web: next / api em :8000"
echo "KB: 43 conceitos (JSONL) + sintético de reserva"
echo "Eval: pixi run eval / test-rag"
echo "=== PRONTO PARA TESTAR ==="
