# Contexto para Claude Code · TP Integrador NoSQL (MongoDB) · BDA · UCC

Todo el contexto del proyecto (qué es, modo de trabajo, estado, mapa del repo, decisiones, cómo verificar) está en `AGENTS.md`, que también leen Codex y otros asistentes. Está en un solo archivo para que no haya dos versiones distintas: **cualquier cambio de estado o de decisiones va en `AGENTS.md`**.

@AGENTS.md

## Reglas
- **Antes de levantar Docker o correr scripts, si no existe `.env`, crearlo con `cp .env.example .env`.** La puesta en marcha completa está en `README.md`.
- No versionar secretos ni `.env`.
- Todo tiene que poder reproducirse desde cero con: `docker compose up -d --wait --build` → `python scripts/cargar.py` → `pytest`.
- Los conteos y números que vayan al informe se verifican corriendo el script, no a ojo.
