# Post-mortem `INGEST-005` — Root cause et actions

## Root cause

Modification de `api/src/rag/rag/ingestion/chunker.py` : la
`RecursiveCharacterTextSplitter` reçoit `chunk_size=32`, `chunk_overlap=0`
en dur, en bypassant les valeurs configurables (`settings.chunk_size=512`,
`settings.chunk_overlap=64`).

En production réelle, ce diff aurait pu venir de :

- une expérimentation locale **« et si on faisait des chunks plus petits
  pour des réponses plus précises ? »** non revertée avant merge,
- une PR pour fixer un edge case (chunk_size trop grand pour un modèle
  d'embeddings particulier) appliquée trop largement,
- un bug de migration de config : la lecture des settings tombe en panne
  silencieusement et un fallback hardcodé prend le relais.

## Impact en cascade

C'est un incident à **deux temps** :

### Temps 1 : pendant l'ingestion

- Coût Mistral embeddings × 15 par document
- Latence `/documents/ingest-pdf` × 10-20
- Risque de rate-limit Mistral si batch important (50 PDF d'un coup → ça passe
  d'une vague raisonnable à une vague de **15 000+ embeddings** à enchaîner)

### Temps 2 : pendant le chat (après ingestion)

- Top-K chunks remontés par pgvector = 5 chunks de 32 chars = **160 chars
  de contexte total** au lieu de 2 500
- Le LLM ne peut pas générer de réponse correctement fondée → faithfulness ↓
- L'évaluateur (`evaluate` node) note plus sévèrement → branche `rewrite`
  ou `escalate` activée plus souvent
- Effet de bord : combiné à `TOKENS-001`, l'incident est catastrophique
  (rewrite-loop sur du contexte de 32 chars qui ne s'améliore jamais)

## Détection

### Avec Phase 2 (Prometheus seul)

- **Forte** : `histogram_quantile(0.95, sum by(le) (rate(http_request_duration_seconds_bucket{endpoint=~"/api/v1/documents/ingest.*"}[5m])))` × 10-20.
- **Forte** : si une métrique business `rag_chunks_per_document` existe
  (à ajouter — c'est une des actions correctives), elle passe de ~20 à 300+.
- **Indirecte** : sur le chat, `rag_evaluator_score` glisse vers 5-6.

### Avec Phase 1 (logs JSON)

- Si l'ingestion log un événement « X chunks created » par document, le `X`
  explose. Détectable via Loki :

  ```logql
  {service="api"} | json | message=~".*chunks_created.*" | __error__=""
  ```

### Avec Phase 4 (Langfuse)

- **Très forte** : la trace d'ingestion (si instrumentée via Langfuse
  callback sur l'ingestion comme sur l'agent) montre un nombre d'appels
  d'embeddings par batch très anormal.
- **Très forte** : le dashboard de coût Langfuse fait apparaître l'ingestion
  comme la **première** source de dépense LLM journalière, alors que le
  chat devrait dominer.

## Pourquoi c'est un incident « insidieux »

Les apprenants instrumentent souvent le chat et négligent l'ingestion parce
que :

- ingestion = trafic faible (quelques pics par semaine),
- ingestion = pas critique pour l'utilisateur final (asynchrone),
- ingestion = pas dans les SLA RED prioritaires.

Mais le coût *par requête* d'ingestion est >> du chat (un PDF de 50 pages =
plusieurs centaines d'embeddings). Quand ça dérape, ça dérape vite et fort,
et l'impact sur la qualité du chat n'est visible qu'a posteriori.

## Actions correctives proposées

| # | Action | Owner | Échéance |
|---|--------|-------|----------|
| 1 | Métriques RAG **ingestion-side** : `rag_ingestion_chunks_per_document` (Histogram, label `mime_type`), `rag_ingestion_embedding_tokens_total` (Counter) | Backend | 1 semaine |
| 2 | Alerte Prometheus : `rag_ingestion_chunks_per_document` p95 > 100 → page le backend lead | SRE | 2 jours |
| 3 | Test d'intégration : un PDF de référence est ingéré en CI, assert que `chunks_created ∈ [15, 30]` | QA | 3 jours |
| 4 | Re-ingestion automatique des documents ingérés pendant l'incident (job one-off) — supprimer les doc avec `chunks_count > seuil` puis ré-ingérer | Backend | dès résolution |
| 5 | Sortir `chunk_size`/`chunk_overlap` du code vers `Settings` strict (un set de valeurs hardcodées doit lever une exception au boot) | Backend lead | 1 semaine |

## Fix

```bash
./incidents/revert.sh 05
```

**Important** : après revert, les documents ingérés *pendant* l'incident
gardent leurs chunks pourris. Pour rétablir la qualité de retrieval :

```bash
# Identifier les docs incriminés (heuristique : chunks_count anormalement élevé)
docker compose exec postgres psql -U rag_user -d rag -c "
  SELECT d.filename, COUNT(c.id) as chunk_count
  FROM rag.documents d
  JOIN rag.document_chunks c ON c.document_id = d.id
  GROUP BY d.id, d.filename
  HAVING COUNT(c.id) > 100
  ORDER BY chunk_count DESC;
"

# Supprimer (CASCADE supprime les chunks) puis ré-ingérer
docker compose exec postgres psql -U rag_user -d rag -c "
  DELETE FROM rag.documents WHERE id = '<id>';
"
# Puis re-curl l'ingestion
```

Vérification post-fix : nouvelle ingestion du même PDF produit le bon
nombre de chunks (~20 pour 5 pages), latence retombe à 3-5 s.
