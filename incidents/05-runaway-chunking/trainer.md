# Incident `INGEST-005` — Runaway chunking

## Code apprenant

> « Incident **INGEST-005**. L'équipe pédagogique se plaint que l'import du
> nouveau référentiel RNCP prend une éternité et que les réponses depuis
> sont moins précises. À vous. »

## Catégorie

**App-side, pipeline d'ingestion.** Met en lumière que les bugs en ingestion
ont un effet *cascade* sur la qualité de retrieval — l'observabilité doit
couvrir les deux chaînes (ingest **et** chat), pas seulement la chaîne chat.

## Injection

```bash
cd <leur-clone>
./incidents/apply.sh 05
```

Le binôme ne verra rien tant qu'une ingestion n'a pas lieu. **Trigger-la toi-
même** depuis la machine du binôme (un PDF de `data/docs/` ou un PDF de test
préparé) :

```bash
# Depuis l'host du binôme
curl -F "file=@data/docs/sample.pdf" \
     http://localhost:8000/api/v1/documents/ingest-pdf

# Ou via l'interface si elle est exposée
```

Pour un effet visible plus rapide, ingère **2-3 PDF** consécutivement — ça
matérialise la spike sur le histogramme de latence.

Optionnellement, demande au binôme de **poser ensuite quelques questions**
sur le document nouvellement ingéré : ils observeront que la qualité des
réponses chute (chunks de 32 chars = pas assez de contexte pour répondre).

## Revert

```bash
./incidents/revert.sh 05
```

⚠️ **Important** : les documents ingérés *pendant* l'incident restent en DB
avec leurs chunks pourris. Pour un revert complet de la qualité retrieval,
il faut **re-ingérer** les PDFs concernés après le revert (ou nettoyer la
DB des docs incriminés). À mentionner dans le post-mortem.

## Ce qui se passe sous le capot

Dans `api/src/rag/rag/ingestion/chunker.py`, le `RecursiveCharacterTextSplitter`
est forcé à `chunk_size=32`, `chunk_overlap=0`, en ignorant les valeurs des
settings (512 / 64 par défaut).

Conséquences :

| Métrique | Normal | Sous incident | Ratio |
|----------|--------|---------------|-------|
| Chunks générés par PDF (5 pages) | ~20 | ~300+ | **× 15** |
| Appels Mistral embeddings | 1 batch de 20 | 1 batch de 300+ | × 15 (en tokens) |
| Coût d'ingestion par PDF | ~0,01 € | ~0,15 € | × 15 |
| Latence `POST /documents/ingest-pdf` | ~3 s | ~30-60 s | × 10-20 |
| Latence `POST /documents/ingest-urls` (web) | proportionnellement | proportionnellement | × 10-20 |
| Sémantique par chunk | 1 paragraphe utile | 5-6 mots sans contexte | qualité ≈ 0 |
| Score Ragas faithfulness post-ingestion | ~0,90 | ~0,40-0,55 | divisé par 2 |

## Signaux attendus

| Source | Signal | Fenêtre |
|--------|--------|---------|
| Grafana panel **HTTP RED `/documents/ingest-*`** | p95 latence × 10-20, error rate inchangé | < 1 min après 1 ingestion |
| Logs Loki (Phase 1) | nombreuses lignes par même `request_id` d'ingestion | immédiat |
| Langfuse (Phase 4) | coût par trace d'ingestion × 15, tokens facturés au plafond | < 5 min |
| Métrique `rag_retrieved_chunks` (au moment d'un chat) | nombre de chunks remontés OK, mais leur **taille** chute | observable seulement si une métrique de longueur de chunk existe |
| Ragas eval (`POST /eval/run`) | faithfulness chute si re-évalué après ingestion | sur demande |

## Pédagogiquement

L'objectif :

1. **« Notre observabilité couvre-t-elle ingestion ET retrieval ? »** — la
   plupart des binômes auront instrumenté le chat (`/messages`) et oublié
   `/documents/ingest-*`. C'est exactement le piège : les pics d'ingestion
   sont rares mais coûteux.
2. **« Un bug d'ingestion dégrade la qualité de retrieval »** — couplage
   non-évident entre les deux chaînes.
3. **« HTTP 200 OK ≠ tout va bien »** — l'endpoint répond normalement,
   c'est juste *plus long* et le contenu stocké est *moins utile*.

## Indices à donner si le binôme sèche

- **5 min** : « Comparez le temps d'ingestion d'aujourd'hui avec celui de
  votre démo de Phase 2. Combien de chunks par PDF en moyenne ? »
- **10 min** : « Toutes les métriques de votre dashboard couvrent-elles
  l'ingestion ou seulement le chat ? »
- **15 min** : « Si la facture Mistral monte sans que le trafic `/messages`
  ait bougé, où regarder ? »

## Anti-spoilers

- Ne pas dire « chunk_size », « splitter », ou « 32 ».
- Si la Phase 4 Langfuse est faite, pousser : « combien coûte une ingestion
  ce matin vs hier ? »

## Critères de validation (RNCP)

- C11.3 — Le monitoring couvre **toute** la chaîne RAG, pas seulement le
  point de consommation (`/messages`)
- C20.3 — Les endpoints d'ingestion sont instrumentés en RED de la même
  manière que le chat
- C21.2 — Le post-mortem identifie les **deux** symptômes (coût ingestion +
  qualité retrieval) et propose une action corrective pour chaque
