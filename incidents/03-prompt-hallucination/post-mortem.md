# Post-mortem `HALL-003` — Root cause et actions

## Root cause

Régression de prompt dans `RAG_SYSTEM_PROMPT` (`api/src/rag/rag/agent/prompts.py`).
Les garde-fous stricts (« EXCLUSIVEMENT », « UNIQUEMENT », « ne jamais inventer »)
sont remplacés par des consignes plus souples qui **invitent** explicitement le
modèle à compléter le contexte avec ses connaissances générales.

En production réelle, ce diff aurait pu provenir de :

- une PR pour « rendre le bot moins frustrant quand il ne sait pas »,
- une expérimentation A/B mal terminée,
- un rebase malheureux où le strict prompt a été perdu.

## Impact réel

| Dimension | Avant | Pendant |
|-----------|-------|---------|
| Faithfulness Ragas | ~0.92 | ~0.55 |
| Réponses citant une source | ~85 % | ~30 % |
| Réponses « je n'ai pas trouvé » | ~12 % | ~2 % |
| Risque RGPD / leak | nul | élevé (réponses inventant des dossiers / chiffres) |

L'incident est **invisible** dans Prometheus : latence inchangée, 0 erreur HTTP,
volumes nominaux.

## Détection

### Ce qui le voit

- **Langfuse + Ragas** : faithfulness chute en quelques requêtes (visible dans
  le dashboard de scores). C'est *la* preuve par l'observabilité LLM.
- **Endpoint `/feedback`** : si exposé et qu'un panel Grafana track le ratio
  👍/👎 par tranche, la chute est lisible en quelques minutes.
- **L'humain** : un utilisateur ou un formateur qui *lit* les réponses, et
  signale.

### Ce qui ne le voit pas

- Prometheus HTTP RED — aucune anomalie.
- Latence — aucune anomalie.
- Logs Loki — aucune anomalie (rien d'inhabituel à logger côté HTTP).
- Healthcheck `/health` — vert.

## Le piège conceptuel

C'est l'archétype du **bug silencieux** dans un système LLM. Toutes les
métriques d'« infra observability » disent que ça marche. Toutes les métriques
de « LLM observability » disent que c'est cassé.

Sans Langfuse (ou équivalent), la seule façon de détecter `HALL-003` est de :

- lancer Ragas en continu sur un corpus de référence (`POST /eval/run`),
- exposer `faithfulness_score` comme une Gauge Prometheus → tableau de bord
  + alerte si la moyenne tombe sous un seuil.

C'est exactement l'esprit de la Phase 4 du brief.

## Actions correctives proposées

| # | Action | Owner | Échéance |
|---|--------|-------|----------|
| 1 | **Prompt registry versionné** : sortir les prompts du code source vers Langfuse Prompts (ou table DB versionnée). Toute modification passe par PR + review | Backend lead | 2 semaines |
| 2 | **Ragas en CI** : lancer `rag.cli.eval` sur un corpus de 20 questions canoniques à chaque PR touchant `prompts.py` ou `nodes.py`. Bloquer le merge si faithfulness < 0.85 | QA | 1 semaine |
| 3 | **Ragas en run-time** : un cron interne (`jobs/`) qui exécute `/eval/run` toutes les 30 min et pousse `faithfulness_score` dans Prometheus | SRE | 1 semaine |
| 4 | **Alerte qualité** : `faithfulness_score < 0.75 for 15m` → Discord `#alerts-quality` | SRE | 1 semaine |
| 5 | **Endpoint feedback** instrumenté : panel Grafana « ratio 👍/👎 sur 24 h » + alerte si ratio 👎 > 30 % | Backend | 2 semaines |

## Fix

```bash
./incidents/revert.sh 03
```

Vérification : reposer les mêmes questions limites — l'agent doit maintenant
répondre « je n'ai pas trouvé ce point dans la documentation fournie, je vous
recommande de contacter l'équipe pédagogique ».
