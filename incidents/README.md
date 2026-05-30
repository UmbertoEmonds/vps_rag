# Game Day — Incident Library

Toolbox formateur pour le **game day** de la Phase 5 du brief. Chaque incident est :

- déclenchable en **< 60 sec** sur la machine d'un binôme (patch git ou script docker) ;
- **réversible** sans `docker compose down -v` (pas de perte de données) ;
- détectable via l'instrumentation que les apprenants ont mise en place dans les
  Phases 1 à 4 (logs JSON, Prometheus, Grafana, Loki, Alertmanager, Langfuse).

> ⚠️ Ne PAS publier ce dossier dans le repo public de starter. Cette branche
> `feat/gameday-incidents` est destinée à rester sur le clone privé du
> formateur. Les apprenants forkent depuis `main`.

## Vue d'ensemble

| # | Code | Catégorie | Mécanisme | Phase qui le détecte au mieux |
|---|------|-----------|-----------|-------------------------------|
| 01 | `TOKENS-001` | LLM | Évaluateur durci → boucle rewrite + tokens × N | Phase 4 Langfuse (traces longues) + Phase 2 (`rag_agent_decisions_total{decision="rewrite"}`) |
| 02 | `LAT-002` | App | `asyncio.sleep` aléatoire (40 % req) dans `retrieve` | Phase 2/3 (`rag_agent_node_duration_seconds{node="retrieve"}` p95) |
| 03 | `HALL-003` | LLM | Prompt RAG ouvre aux hallucinations | Phase 4 Langfuse + qualité (`rag_evaluator_score`, feedback 👎) |
| 04 | `INFRA-004` | Infra | Pumba netem 500 ms ± 100 ms vers Postgres | Phase 2/3 (latence sur **plusieurs** nœuds touchant la DB) |
| 05 | `INGEST-005` | App (ingestion) | `chunk_size=32` forcé → chunks × 15, coût × 15, qualité retrieval effondrée | Phase 2/3 (HTTP RED sur `/documents/ingest-*`) + Phase 4 (coût Langfuse) |

Au moins **1 incident sur 5 est LLM-specific** (en réalité 2 le sont, `TOKENS-001`
et `HALL-003`), conformément à l'exigence du brief. Les 3 autres couvrent
respectivement app-side chat (`LAT-002`), infrastructure réseau (`INFRA-004`),
et app-side ingestion (`INGEST-005`).

## Règle du jeu (à annoncer en début de Phase 5)

> « Pendant le game day, vous diagnostiquez **uniquement** via votre stack
> observabilité : Grafana, Loki, Alertmanager, Langfuse. `git diff`,
> `git status`, `git log`, lecture brute du code source, `docker exec ...
> cat ...`, `docker logs api | grep ...` sont **interdits**. Écrivez votre
> post-mortem comme si c'était une vraie prod : vous n'avez pas accès au
> commit fautif, vous n'avez que vos signaux. »

Justification pédagogique : en production réelle, un bug LLM peut être :

- dans un prompt stocké en base de données ou en Langfuse Prompts,
- dans un modèle hosted que vous ne contrôlez pas,
- dans une configuration Helm/Terraform appliquée par un autre service,
- dans une dérive de données silencieuse,

…toutes situations où le `git diff` du repo applicatif ne montre **rien**. Le
game day reproduit ces conditions.

En complément, les scripts `apply.sh` / `revert.sh` ci-dessous masquent
automatiquement les fichiers patchés de `git status` via
`git update-index --skip-worktree`. C'est un filet de sécurité contre les
apprenants qui oublieraient la règle.

## Procédure du game day

### 0. Préparation (J3, avant la séance)

```bash
# Cloner cette branche sur la machine formateur
git clone -b feat/gameday-incidents <repo>

# Pre-pull pumba pour ne pas attendre à l'injection
docker pull gaiaadm/pumba

# Vérifier les patches sur une copie propre du repo starter
for p in incidents/*/incident.patch; do
  echo "--- $p"
  (cd ~/Documents_Non_iCloud/workspace_python/simplon-rag-sample && git apply --check $p)
done
```

### 1. Injection sur un binôme

Tu te connectes (ou tu tapes directement) sur leur machine, dans leur clone du
repo. **Une seule commande par incident** :

```bash
# Incident 01 / 02 / 03 — patch git + masquage skip-worktree + rebuild
./incidents/apply.sh 01

# Incident 04 — pumba (pas de rebuild)
./incidents/apply.sh 04 10m 500 100
```

Le wrapper `apply.sh` :

1. Vérifie que le patch s'applique (`git apply --check`, fallback `--3way`).
2. Applique le patch sur le working tree.
3. Marque chaque fichier patché en `--skip-worktree` → invisible dans
   `git status` et dans `git diff` sans argument.
4. Reconstruit le conteneur API (~30-60 sec).

### 2. Briefing apprenant

Tu annonces le code de l'incident sans en révéler la nature :

> « Incident **TOKENS-001** en cours. Vous avez 25 minutes pour le détecter,
> le diagnostiquer et le mitiger. Go. »

### 3. Revert après debrief

```bash
./incidents/revert.sh 01    # ou 02, 03, 04
```

`revert.sh` retire le flag `skip-worktree`, restaure le fichier depuis HEAD,
et rebuild. Pour l'incident 04, stoppe le conteneur pumba (latence retirée
immédiatement).

### 4. Post-mortem

Choisis **1 incident** avec eux et lance la rédaction du post-mortem
selon la trame de cours (`runbooks/` du repo contient déjà 3 runbooks de référence).
Le `post-mortem.md` de chaque incident contient la **root cause attendue** pour t'aider
au debrief.

## Risques d'application des patches

Si un binôme a déjà modifié les zones patchées (peu probable pour `prompts.py`,
plus probable pour `nodes.py` après Phase 4 Langfuse), `git apply` échoue. Le
wrapper `apply.sh` retombe automatiquement sur `git apply --3way` qui tente
un merge. En dernier recours :

```bash
patch -p1 --fuzz=3 < incidents/<NN>/incident.patch     # tolérance large
```

Ou édite à la main le fichier ciblé (chaque `incident.patch` est court —
5 à 30 lignes — donc la transcription manuelle prend < 1 min), puis lance
manuellement :

```bash
git update-index --skip-worktree <fichier>
docker compose up -d --build api
```

## Cheatsheet incidents

### Ordre recommandé (escalade en complexité)

Avec 5 incidents disponibles, choisis-en 3 ou 4 selon le timing :

1. **`LAT-002`** (App, chat) — facile à détecter, alerte `HighChatLatencyP95`
   doit sonner sous 2 min. Mise en jambes.
2. **`INFRA-004`** (Infra) — même symptôme apparent (latence) mais cause
   différente. Force à distinguer *où* dans la chaîne.
3. **`INGEST-005`** (App, ingestion) — bascule la focale du chat vers
   l'ingestion. Révèle si les binômes ont instrumenté **toute** la chaîne
   RAG ou seulement `/messages`.
4. **`TOKENS-001`** (LLM) — facture qui explose, p99 qui monte. Sans Langfuse,
   diagnostic difficile. Le tournant pédagogique du game day.
5. **`HALL-003`** (LLM qualité) — pas de signal Prometheus, pas d'alerte. Seul
   Langfuse + feedback 👎 + Ragas le voit. C'est l'incident *« silencieux »*
   qui illustre pourquoi observabilité LLM ≠ observabilité applicative.

Pour un game day de 3 h : prendre 1, 3, 5 (couvre chat, ingestion, qualité
LLM). Pour 4 h : ajouter 2 ou 4 entre eux.

### Durées d'injection conseillées

- `01`, `03` : 15 min (laisse le temps au comportement de se manifester sur
  plusieurs conversations consécutives)
- `02` : 10 min (alerte rapide attendue)
- `04` : 10 min (suffisant pour que les dashboards bougent ; éviter > 15 min
  pour ne pas pourrir l'expérience de debrief)
- `05` : 15 min (l'effet n'est visible qu'après que le formateur a déclenché
  l'ingestion ; prévoir 2-3 PDFs à uploader)

## Structure des dossiers

```text
incidents/
├── README.md                       (ce fichier)
├── apply.sh                        # wrapper unique : ./apply.sh <NN>
├── revert.sh                       # wrapper unique : ./revert.sh <NN>
├── 01-evaluator-loop/
│   ├── incident.patch              # appliqué par apply.sh + skip-worktree
│   ├── trainer.md                  # instructions formateur (avec spoiler)
│   └── post-mortem.md              # root cause + actions correctives
├── 02-slow-retrieval/
│   ├── incident.patch
│   ├── trainer.md
│   └── post-mortem.md
├── 03-prompt-hallucination/
│   ├── incident.patch
│   ├── trainer.md
│   └── post-mortem.md
├── 04-pg-network-latency/
│   ├── inject.sh                   # pumba run (conteneur renommé
│   │                                 'simplon_rag_postgres_replica'
│   │                                 pour passer inaperçu dans docker ps)
│   ├── revert.sh
│   ├── trainer.md
│   └── post-mortem.md
└── 05-runaway-chunking/
    ├── incident.patch              # chunk_size 512 → 32 dans chunker.py
    ├── trainer.md                  # nécessite trigger ingestion par le formateur
    └── post-mortem.md
```

Chaque `trainer.md` contient : objectif pédagogique, commande d'injection, fenêtre de
détection attendue, indices à donner si l'équipe sèche, et anti-spoilers à éviter.
Chaque `post-mortem.md` contient la solution complète à utiliser pour le debrief.
