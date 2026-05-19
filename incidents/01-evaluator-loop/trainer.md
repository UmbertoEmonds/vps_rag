# Incident `TOKENS-001` — Évaluateur boucle, tokens × N

## Code apprenant

> « Incident **TOKENS-001** en cours. Symptôme : la facture Mistral monte vite
> ce matin. À vous. »

Ne mentionne **pas** le mot « evaluator », « rewrite », « prompt ». Reste sur
le symptôme financier — c'est ce que la direction remonterait IRL.

## Catégorie

**LLM-specific.** C'est l'incident phare du game day pour valider C11 niveau 3.

## Injection

```bash
cd <leur-clone>
./incidents/apply.sh 01            # patch + skip-worktree + rebuild (~30-60 s)
```

Une fois l'API redémarrée, **envoie 3 ou 4 questions** via le frontend Streamlit
(ou `curl`) pour que les métriques bougent visiblement. Sinon le binôme regardera
un graphique plat.

## Revert

```bash
./incidents/revert.sh 01
```

## Ce qui se passe sous le capot

Le prompt `EVALUATOR_PROMPT` est durci par un nouveau bloc « IMPORTANT — exigence
renforcée » qui demande au LLM de noter au maximum 6 quasi-systématiquement. Tous
les passages dans le nœud `evaluate` retournent `decision="rewrite"`, ce qui :

1. relance `retrieve` avec un `rewrite_suggestion`,
2. relance `generate`,
3. relance `evaluate` (lui aussi durci → re-rewrite),

…jusqu'à `agent_max_retries` (= 2 par défaut). Chaque requête `/messages`
consomme donc **3× le nombre de tokens** d'une requête normale (retrieve +
generate + evaluate × 3 boucles), et la latence p99 explose en proportion.

## Signaux attendus

| Source | Signal | Fenêtre |
|--------|--------|---------|
| Grafana panel **Agent decisions** | `rag_agent_decisions_total{decision="rewrite"}` rate × 5 | < 2 min après 3 requêtes |
| Grafana panel **Latency p99 /messages** | p99 multiplié par ~3 | < 2 min |
| Grafana panel **Evaluator score** | histogramme glisse vers 5-6 | < 2 min |
| Alertmanager | `HighChatLatencyP95` finit par sonner (p95 > 5 s) | 2-3 min |
| Logs Loki | nombreuses lignes `agent_rewrite` (level=warning) avec même `request_id` | immédiat |
| Langfuse (Phase 4) | trace longue : `retrieve → generate → evaluate → retrieve → …` | immédiat |

## Indices à donner si le binôme sèche

- **5 min** : « Regardez les décisions de l'agent dans Grafana. Toutes les requêtes
  produisent-elles bien `decision=answer` ? »
- **10 min** : « Cherchez une métrique qui compte la distribution `answer/rewrite/escalate`. »
- **15 min** : « Si l'évaluateur juge la réponse trop sévèrement, que se passe-t-il
  dans le graphe ? »

## Anti-spoilers

- Ne jamais dire « prompt cassé » ou « evaluator » avant que le binôme ait
  identifié que c'est la décision `rewrite` qui dérape.
- Si tu veux les pousser vers Langfuse (Phase 4 faite), demande : « combien de spans
  par trace en moyenne en ce moment, vs ce matin ? »

## Critères de validation (RNCP)

- C11.3 — Détecte la dérive métier RAG via une métrique business
- C20.3 — Le `request_id` permet de relier les warnings `agent_rewrite` à une seule
  requête utilisateur dans Loki / Grafana Explore
- C21.2 — Le post-mortem identifie le prompt comme root cause
