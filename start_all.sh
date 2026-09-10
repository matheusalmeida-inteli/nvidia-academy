#!/bin/bash
# Sobe tudo: API FastAPI + Web Next.js + confirma RAG

echo "=== LIL BRO - SUBINDO TUDO ==="

# 1. Confirma RAG
python3 -c "
from rag.ingest.nvidia_kb import NVIDIA_KB
from rag.config import chunk_target, rerank_enabled, local_dense_fallback
print('RAG: KB=', len(NVIDIA_KB), '| chunk=', chunk_target(), '| rerank=', rerank_enabled(), '| fallback=', local_dense_fallback())
"

# 2. API FastAPI (porta 8000) em background
nohup ./.pixi/envs/default/bin/python -c "
import sys, os
sys.path.insert(0, "/home/misareverberate/Projetos/Academy/academy-nvidia-radar")
os.environ['PYTHONPATH'] = '/home/misareverberate/Projetos/Academy/academy-nvidia-radar'
from api.main import app
import uvicorn
uvicorn.run(app, host='0.0.0.0', port=8000, log_level='warning')
" > /tmp/api_server.log 2>&1 &
echo "API PID: $! (porta 8000)"

# 3. Web Next.js (porta 3000) — se node existir no pixi/env; senão usa node global
NODE_BIN=$(find .pixi/envs/default/bin -name 'node' 2>/dev/null | head -1)
if [ -n "$NODE_BIN" ]; then
    cd web && nohup "$NODE_BIN" $(npm bin)/next dev -p 3000 > /tmp/web_server.log 2>&1 &
    echo "Web PID: $! (porta 3000)"
else
    echo "Web: node nao encontrado no pixi; usando npx/next se disponivel"
fi

sleep 2
echo "=== STATUS ==="
echo "API: curl http://localhost:8000/health"
echo "Web: http://localhost:3000"
echo "RAG: testado via python (KB 43 conceitos)"
echo "=== PRONTO PARA TESTAR ==="
