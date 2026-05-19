# Post-mortem `TOKENS-001` — Root cause et actions

## Root cause

Modification du `EVALUATOR_PROMPT` (`api/src/rag/rag/agent/prompts.py`) :
ajout d'un bloc d'instructions qui force le modèle évaluateur à noter ≤ 6
quasi-systématiquement, ce qui route 100 % des requêtes vers la branche
`rewrite` du graphe LangGraph.

Mécanique d'amplification :

```text
generate → evaluate (score=6) → rewrite → retrieve → generate → evaluate (score=6)
         → rewrite → retrieve → generate → evaluate (escalate, retry_count=2)
```

Chaque message utilisateur consomme donc :

| Composant | Appels normaux | Appels après incident | Ratio |
|-----------|----------------|----------------------|-------|
| `retrieve` | 1 | 3 | × 3 |
| `generate` (mistral-large) | 1 | 3 | × 3 |
| `evaluate` (mistral-small) | 1 | 3 | × 3 |
| Tokens facturés (estim.) | ~2 k | ~6 k | **× 3** |

Sur un trafic de pic ~5 req/s, le surcoût atteint 200-300 € / jour.

## Timeline type d'un game day

| T+ | Événement |
|----|-----------|
| 00:00 | Patch appliqué, API redémarre |
| 00:30 | Premières requêtes utilisateur produisent des chaînes longues |
| 02:00 | Alerte `HighChatLatencyP95` sonne (si seuil p95 > 5 s à 2 min) |
| 05:00 | Le binôme remarque le pic de `rag_agent_decisions_total{decision="rewrite"}` |
| 12:00 | Diagnostic : c'est l'évaluateur qui pousse au rewrite |
| 20:00 | Lecture du prompt → bloc « IMPORTANT » identifié comme étranger |
| 22:00 | Revert + redémarrage |

## Détection

### Avec Phase 2 (Prometheus seul)

- **Forte** : `rate(rag_agent_decisions_total{decision="rewrite"}[1m])` multiplié
  par 5+. Visible direct sur le panel **Agent decisions** du dashboard.
- **Forte** : `histogram_quantile(0.99, rag_agent_node_duration_seconds{node=~"retrieve|generate|evaluate"})` × 3.
- **Indirecte** : `rag_evaluator_score` histogramme glisse vers la gauche
  (médiane qui passe de ~8 à ~5).

### Avec Phase 4 (Langfuse)

- **Très forte** : chaque trace montre 3 spans `retrieve`, 3 `generate`, 3 `evaluate`
  au lieu de 1 / 1 / 1.
- **Très forte** : coût par trace × 3 dans le dashboard Langfuse cost.

## Pourquoi Prometheus seul ne suffit pas

Prometheus voit **que** les choses vont mal (rate, latence), mais ne dit pas
**pourquoi** : le contenu des prompts et la chaîne d'appels intra-requête ne sont
pas dans les métriques (et ne doivent pas l'être — cardinalité + RGPD).

Langfuse expose cette chaîne par requête, avec tokens consommés par span. C'est la
seule manière propre de localiser le problème **dans l'agent**.

## Pourquoi les logs (Phase 1) aident aussi

Le nœud `evaluate` log un warning `agent_rewrite` à chaque rewrite, avec le
`request_id`. Dans Loki :

```logql
{service="api"} | json | message="agent_rewrite"
```

Permet de compter combien de fois la même requête a bouclé.

## Actions correctives proposées

| # | Action | Owner | Échéance |
|---|--------|-------|----------|
| 1 | Mettre les prompts en **prompt registry versionné** (Langfuse Prompts ou commit signé) | Backend lead | 1 semaine |
| 2 | Ajouter un test d'intégration qui injecte 5 questions canoniques et vérifie que `decision="answer"` revient ≥ 80 % du temps | QA | 3 jours |
| 3 | Alerte Prometheus dédiée : `rate(rag_agent_decisions_total{decision="rewrite"}[5m]) > 0.5 × rate(rag_agent_decisions_total[5m])` → page on-call | SRE | 2 jours |
| 4 | Budget LLM hard-cap : circuit-breaker qui désactive le rewrite-loop au-delà d'un seuil quotidien | Backend lead | 2 semaines |

## Fix

```bash
./incidents/revert.sh 01
```

Vérification post-fix : la distribution `decision` revient à `answer` dominant
en < 1 min, latence p99 retombe sous 3 s.
