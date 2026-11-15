# NASA Space Apps 2026 – Sprinklers

Calendário harmonizado de queimadas (MODIS + VIIRS FIRMS).

## Arquitetura
Colab (processa, via Drive) → `metrics/` na Drive → backend (Flask) → frontend.
Os dados não estão no Git: ver [data/README.md](data/README.md).

## Arranque rápido
Dois terminais:

```bash
# 1. backend (Flask, 127.0.0.1:8080) — com dados simulados
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python test/generate_mock_data.py
.venv/bin/python main.py --data test/mock_hotspots.csv

# 2. frontend (Vite, http://localhost:5173) — encaminha /api para o backend
cd frontend
npm install
npm run dev
```

Contrato da API: [spec/api/frontend-backend.md](spec/api/frontend-backend.md).
Dados reais da Drive: ver [data/README.md](data/README.md).
