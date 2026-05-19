# Incident `LAT-002` — Retrieval lent intermittent

## Code apprenant

> « Incident **LAT-002**. Symptôme : certaines questions mettent du temps à
> répondre, d'autres pas. Allez-y. »

## Catégorie

**App-side.** Mise en jambes du game day — l'alerte `HighChatLatencyP95`
doit normalement sonner toute seule.

## Injection

```bash
cd <leur-clone>
./incidents/apply.sh 02
```

Pour faire bouger les métriques rapidement, **envoie 8-10 questions**
successives via le frontend ou `curl` — la latence injectée n'apparaît
qu'environ 1 fois sur 2,5 (40 %).

## Revert

```bash
./incidents/revert.sh 02
```

## Ce qui se passe sous le capot

Dans le nœud `retrieve` (graphe LangGraph), un `await asyncio.sleep(3.0)` est
injecté conditionnellement (`random.random() < 0.4`). 40 % des requêtes
prennent donc **+3 s** sur la seule étape de retrieval. Le reste de l'agent
n'est pas affecté.

C'est volontairement intermittent pour générer une **distribution bimodale**
de la latence — illustrant pourquoi p50 ≠ p99 et pourquoi observer la médiane
seule cache le problème.

## Signaux attendus

| Source | Signal | Fenêtre |
|--------|--------|---------|
| Alertmanager → Discord | `HighChatLatencyP95` sonne (p95 > 5 s sur `/messages`) | 1-2 min |
| Grafana panel **Latency per LangGraph node** | `rag_agent_node_duration_seconds{node="retrieve"}` p95 ≈ 3-4 s, p50 stable | < 1 min |
| Grafana panel **HTTP RED /messages** | p95 ≈ 3-4 s, p50 stable, error rate inchangé | < 1 min |
| Histogramme retrieve (heatmap) | deux modes : ~50 ms et ~3 s | < 1 min |

## Pédagogiquement

Ce que le binôme doit verbaliser :

1. **« La latence est bimodale »** → leur dashboard doit le montrer.
2. **« Le pic est localisé sur `retrieve`, pas sur `generate` »** → leur
   décomposition par nœud doit l'isoler.
3. **« Pas d'erreur 5xx, juste de la latence »** → leur alerte est sur le
   bon symptôme (latence p95) plutôt que sur la cause (CPU, 5xx).

Si le binôme dit « tout va lent », c'est un échec partiel : leur dashboard ne
distingue pas p50 / p99 ou ne décompose pas par nœud. Note-le pour le debrief.

## Indices à donner si le binôme sèche

- **3 min** : « Si vous comparez p50 et p99 sur /messages, vous voyez la
  même chose ou pas ? »
- **8 min** : « Le ralentissement est-il sur tous les nœuds du graphe ou
  un seul ? »

## Anti-spoilers

- Ne pas dire « sleep » ni « retrieve » avant qu'ils aient lu leur dashboard.

## Critères de validation (RNCP)

- C20.3 — Les histogrammes Prometheus sont configurés avec des buckets
  pertinents (sinon on ne voit pas la bimodalité)
- C20.3 — L'alerte Discord se déclenche sur un symptôme (latence ressentie)
  et non sur une cause (CPU)
- C21.2 — Le post-mortem note explicitement la distinction p50/p99
