# ADR-0002 — Stack: Python (FastAPI) + React/TypeScript

**Estado:** Aceptada (2026-09-06) · **Reemplaza a:** D2

## Contexto
Proyecto de larga vida, un solo desarrollador. La lógica de mayor riesgo (progresión, ranking, métricas) es de cálculo, y debe existir un contrato legible por máquinas para el agente de IA.

## Decisión
- **Backend:** Python + FastAPI + SQLite. Dominio puro en Python sin dependencias de framework.
- **Frontend:** React + TypeScript + Vite, como PWA.
- **Contrato:** OpenAPI generado automáticamente por FastAPI; los tipos de TypeScript se **generan** desde ese OpenAPI (una sola fuente de verdad, sin duplicar definiciones a mano).
- **Validación:** Pydantic en el borde HTTP; el dominio trabaja con sus propios tipos, no con modelos de la API.

## Alternativas descartadas
- **Monorepo TypeScript (Fastify + React):** un solo lenguaje y esquemas Zod compartidos es una ventaja real, pero OpenAPI queda como trabajo manual y la lógica de cálculo y estadística es menos ergonómica de escribir y testear.

## Consecuencias
- OpenAPI gratuito: el agente de IA obtiene un contrato explícito sin esfuerzo adicional.
- SDK de MCP maduro en Python para la fase F6.
- Dos toolchains que mantener (`uv`/`pip` + `npm`). Se acota con un `Makefile`/scripts únicos de arranque y test.
- La duplicación de tipos front/back se elimina por generación, no por disciplina.
- El dominio puro queda aislado del framework: si algún día el transporte cambia, la lógica de negocio no se toca.

## Restricciones de dependencias
Se añade una librería solo si sustituye código que tendríamos que escribir y mantener. Sin ORM pesado obligatorio, sin frameworks de estado en el frontend hasta que la necesidad sea real.
