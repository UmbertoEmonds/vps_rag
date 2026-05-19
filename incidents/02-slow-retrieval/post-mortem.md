# Post-mortem `LAT-002` — Root cause et actions

## Root cause

Modification du nœud `retrieve` (`api/src/rag/rag/agent/nodes.py`) : ajout d'un
`await asyncio.sleep(3.0)` conditionné par `random.random() < 0.4`. 40 % des
requêtes paient 3 s supplémentaires sur l'étape de recherche pgvector.

C'est une **simulation** de bug réel : en production, le même symptôme se
produirait pour cause de…

- requête pgvector mal optimisée (HNSW `ef_search` trop élevé),
- connexion DB qui slow-start parce que le pool est saturé,
- *neighbor noise* sur l'instance Docker hôte (autre conteneur qui bouffe le CPU),
- index pas reconstruit après une grosse ingestion.

## Détection

### Symptôme dans Grafana

Sur **« Simplon RAG Overview »**, panel *Latency per LangGraph node* :

| Quantile | Avant | Pendant |
|----------|-------|---------|
| p50 `retrieve` | ~30 ms | ~50 ms (inchangé) |
| p95 `retrieve` | ~80 ms | **~3 s** |
| p99 `retrieve` | ~120 ms | **~3.1 s** |

p50 reste stable parce que 60 % des requêtes sont normales. C'est exactement
le piège que p50-only cache.

### Symptôme dans l'alerte

`HighChatLatencyP95` sonne après `for: 2m` à p95 > 5 s sur `/messages`. La règle
actuelle utilise `histogram_quantile(0.95, sum by(le) (rate(...)))` — vérifie
qu'elle agrège bien sur le bon endpoint.

## Pourquoi p95 et pas p50

Une distribution bimodale (50 ms vs 3 s) avec ratio 60/40 :

- p50 ≈ 50 ms (le « bon » mode)
- p90 ≈ 3 s (le « mauvais » mode commence)
- p95 ≈ 3 s
- p99 ≈ 3.1 s

→ Une alerte sur p50 raterait totalement l'incident. Une alerte sur p95 le
capte en ~2 min. C'est l'argumentaire RED de Grafana Labs (lien dans le brief).

## Actions correctives proposées

| # | Action | Owner | Échéance |
|---|--------|-------|----------|
| 1 | Vérifier `ef_search` HNSW et le retour à 64 (valeur par défaut migration) | Backend lead | 1 jour |
| 2 | Ajouter une métrique `rag_pgvector_query_duration_seconds` séparée du nœud `retrieve` pour distinguer le coût DB du coût Python | Backend | 1 semaine |
| 3 | Alerte secondaire sur p99 (seuil plus élevé, 8 s) en cas de ralentissement extrême | SRE | 2 jours |
| 4 | Test de charge nocturne en CI : 100 questions, p95 doit rester sous 2 s | QA | 1 semaine |

## Fix

```bash
./incidents/revert.sh 02
```

Vérification : p95 sur `retrieve` retombe sous 200 ms en < 1 min.
