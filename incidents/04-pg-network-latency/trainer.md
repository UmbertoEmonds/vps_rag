# Incident `INFRA-004` — Latence réseau Postgres

## Code apprenant

> « Incident **INFRA-004**. Une dégradation infra remonte du côté ops.
> Trouvez d'où ça vient. »

## Catégorie

**Infrastructure.** Pas de patch de code. Permet de tester si l'observabilité
sait distinguer un ralentissement applicatif (incident 02) d'un ralentissement
infra qui touche **toute** la chaîne DB.

## Injection

```bash
# Vérifier que pumba est dispo localement (à faire avant le J3)
docker image inspect gaiaadm/pumba >/dev/null 2>&1 || docker pull gaiaadm/pumba

cd <leur-clone>
./incidents/apply.sh 04 10m 500 100      # DURATION DELAY_MS JITTER_MS
```

Pas de rebuild de l'API — pumba injecte la latence au niveau réseau Docker du
conteneur cible (`simplon_rag_postgres_pgvector` par défaut). Le conteneur
pumba est **nommé volontairement `simplon_rag_postgres_replica`** pour passer
inaperçu dans `docker ps` (un binôme qui regarde la liste pensera à un sidecar
légitime).

## Revert

```bash
./incidents/revert.sh 04
```

(ou attendre l'expiration de `DURATION`.)

## Ce qui se passe sous le capot

`pumba netem delay --time 500 --jitter 100 simplon_rag_postgres_pgvector`
applique une règle `tc qdisc … netem` sur l'interface réseau virtuelle du
conteneur Postgres. **Tous** les paquets entrants/sortants subissent un délai
de 500 ms ± 100 ms.

Conséquence : **chaque** requête SQL initiée par l'API paie ~500 ms de RTT.
Multipliée par le nombre de queries par requête HTTP, ça donne des latences
de plusieurs secondes même pour les endpoints simples (`/health` pas affecté
car il ne ping pas la DB ; les conversations le sont fortement).

## Signaux attendus

| Source | Signal | Fenêtre |
|--------|--------|---------|
| Alertmanager → Discord | `HighChatLatencyP95` sonne | 1-2 min |
| Grafana panel **Latency per LangGraph node** | `load_history`, `retrieve`, `save_turn` ralentissent **tous les trois** | < 1 min |
| Grafana panel **Latency p95 /messages** | p95 entre 4 et 6 s | < 1 min |
| Healthcheck `/health` | reste vert (n'utilise pas la DB ou utilise un timeout court) | — |

## Pédagogiquement

Le binôme doit verbaliser :

1. **« La latence touche `load_history` ET `retrieve` ET `save_turn` »** —
   donc ce n'est pas un nœud précis qui rame, c'est la DB.
2. **« Generate, lui, n'est pas affecté »** — bonne séparation Mistral
   (HTTP externe) vs Postgres (réseau interne).
3. **« On ne saurait pas si la DB rame parce qu'elle est lente ou parce que
   le réseau est lent — il faudrait une métrique côté DB elle-même »** —
   amène à l'idée d'ajouter `pg_stat_statements` ou un exporter Postgres.

Si le binôme dit « le retrieval rame » sans distinguer DB-broad vs node-spécifique,
c'est qu'il a confondu `INFRA-004` avec `LAT-002`. C'est une excellente question
de jury : « si je vous montre ce dashboard, est-ce 02 ou 04 ? »

## Indices à donner si le binôme sèche

- **3 min** : « Comparez la latence des nœuds qui touchent la DB et de celui
  qui ne la touche pas (`generate`). »
- **8 min** : « Quels conteneurs sont en jeu dans la chaîne DB ? »
- **15 min** (si besoin) : « `docker ps` — y a-t-il un conteneur que vous
  ne reconnaissez pas dans la liste de la stack ? » (un œil avisé spottera
  `simplon_rag_postgres_replica` qui n'a aucune raison d'être là)

## Anti-spoilers

- Ne pas mentionner « pumba », « netem » ou « réseau » avant le debrief.
- En cas de vraie nécessité, dis : « le ralentissement est-il *à l'intérieur*
  de la DB ou *entre l'API et la DB* ? »

## Critères de validation (RNCP)

- C11.3 — La décomposition par nœud du graphe permet d'isoler la cause
  (la métrique `rag_agent_node_duration_seconds{node=…}` doit exister)
- C20.3 — La même alerte (`HighChatLatencyP95`) couvre les deux types de
  causes — l'alerte est bien sur le symptôme, pas sur la cause
- C21.2 — Le post-mortem propose **au moins** une métrique manquante pour
  distinguer 02 et 04 (ex : query duration DB-side via exporter)
