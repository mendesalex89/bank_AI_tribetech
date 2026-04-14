# bank_AI_tribetech — Instruções para o Agente

## Regra #1 — Início de Toda Sessão

**Antes de qualquer ação, leia:**
1. `memory/INDEX.md` — índice e regras de memória
2. `memory/progress-log.md` — o que já foi feito
3. `memory/open-questions.md` — questões em aberto

## Regra #2 — Fluxo SDD Obrigatório

Toda nova feature segue este fluxo. **Sem exceções:**

```
/speckit-constitution → /speckit-specify → /speckit-plan → /speckit-tasks → /speckit-implement
```

Specs ficam em `.speckit/features/<nome>/`. Guia completo: `specs/SPEC-GUIDE.md`

## Regra #3 — Atualização de Memória

Ao final de cada sessão, atualize `memory/progress-log.md` com o que foi feito.

## Regra #4 — MCPs Disponíveis

| MCP | Uso |
|---|---|
| `mcp__sqlite` | Consultas ao banco de dados |
| `mcp__filesystem` | Operações de arquivos avançadas |
| `mcp__sequential-thinking` | Raciocínio passo a passo em problemas complexos |
| `mcp__mermaidchart` | Criação de diagramas de arquitetura |
| `mcp__memory` | Memória persistente do agente |

## Regra #5 — Sem Código Especulativo

- Não crie arquivos sem necessidade real
- Não adicione features além do que foi pedido
- Não abstraia prematuramente

## Contexto Técnico

Ver `memory/architecture.md` para stack e decisões técnicas.
Ver `memory/conventions.md` para padrões de código.
