# Post-mortem `INFRA-004` — Root cause et actions

## Root cause

Injection de latence réseau via `pumba netem delay --time 500 --jitter 100` sur
le conteneur `simplon_rag_postgres_pgvector`. Tous les paquets TCP destinés à
Postgres subissent un délai de 400-600 ms.

Mécanique : `pumba` invoque `tc qdisc add dev <iface> root netem delay …` à
l'intérieur du conteneur cible (via le socket Docker), puis maintient la règle
active tant que le conteneur pumba tourne. À l'arrêt, la règle est retirée et
la latence disparaît instantanément.

En production réelle, ce profil correspond à :

- bascule d'AZ pendant un incident cloud (la nouvelle AZ a +400 ms de RTT),
- saturation du switch entre nœuds Kubernetes,
- problème de routing chez le fournisseur cloud (déjà arrivé à GCP, AWS, OVH),
- *noisy neighbour* sur l'hôte Docker (un autre conteneur sature l'interface).

## Détection

### Symptôme global

Tous les endpoints qui exécutent **au moins une requête SQL** sont touchés.
Vu côté `/messages` : p95 passe de ~600 ms à ~5-6 s.

Vu nœud par nœud (panel **Latency per LangGraph node**) :

| Nœud | Requêtes DB ? | Latence avant | Latence pendant |
|------|---------------|---------------|-----------------|
| `load_history` | 1 SELECT | ~10 ms | ~600 ms |
| `guard_route` | 0 | ~400 ms | ~400 ms (inchangé) |
| `retrieve` | 1 SELECT pgvector | ~80 ms | ~600 ms |
| `generate` | 0 | ~1.2 s | ~1.2 s (inchangé) |
| `evaluate` | 0 | ~300 ms | ~300 ms (inchangé) |
| `save_turn` | 1 INSERT + 1 SELECT + 1 UPDATE | ~30 ms | ~1.6 s |

Le pattern caractéristique : **tous les nœuds DB ralentissent uniformément
d'un facteur ~500 ms**, les nœuds LLM (`guard_route`, `generate`, `evaluate`)
sont inchangés.

### Distinguer `INFRA-004` de `LAT-002`

| Critère | `LAT-002` (sleep dans `retrieve`) | `INFRA-004` (latence réseau DB) |
|---------|----------------------------------|--------------------------------|
| Nœuds affectés | `retrieve` seul | `load_history`, `retrieve`, `save_turn` |
| Distribution | Bimodale (60 % normal, 40 % +3 s) | Unimodale (tout est +500 ms) |
| Healthcheck DB | Vert (sleep côté Python pur) | Latence sur `pg_isready` aussi |

C'est le panel par-nœud du dashboard qui permet de trancher en 30 secondes.

## Pourquoi le binôme doit avoir cette finesse

Le brief impose une instrumentation **par nœud du graphe LangGraph** :

> Latence décomposée par nœud du graphe LangGraph (`retrieve`, `generate`,
> `evaluate`) — *Critères de performance C11*

Sans cette décomposition, on voit que « les conversations rament » et c'est
tout. On ne peut pas distinguer un bug applicatif ciblé d'une dégradation
infra horizontale. C'est exactement la limite que la Phase 2 doit lever.

## Actions correctives proposées

| # | Action | Owner | Échéance |
|---|--------|-------|----------|
| 1 | Ajouter `postgres_exporter` à `docker-compose.yml` (image `quay.io/prometheuscommunity/postgres-exporter`) | SRE | 3 jours |
| 2 | Métrique dérivée : `pg_stat_statements` exposée → quantiles de duration par query plan | SRE | 1 semaine |
| 3 | Healthcheck DB de l'API avec timeout 1 s → bascule en mode dégradé (cache lecture seule) si Postgres ne répond plus | Backend lead | 2 semaines |
| 4 | Runbook dédié : `runbooks/postgres-slow.md` — checklist pour distinguer slow query, slow connection, slow network | SRE | 1 semaine |
| 5 | Pour Kubernetes prod : `NetworkPolicy` + `kube-state-metrics` pour catcher les bascules d'AZ | Platform | 1 mois |

## Fix

```bash
./incidents/revert.sh 04
```

(Vérifie : `docker ps --filter "name=simplon_rag_postgres_replica"` doit
renvoyer vide. p95 sur `/messages` retombe sous 1 s en < 30 s.)
