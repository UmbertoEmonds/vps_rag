# Incident `HALL-003` — Hallucinations silencieuses

## Code apprenant

> « Incident **HALL-003**. Un apprenant a signalé que le bot lui a parlé d'une
> formation qui n'existe pas chez nous. C'est arrivé combien de fois ? À vous. »

C'est l'incident **« silencieux »** : aucune alerte ne sonnera, aucune métrique
RED ne bouge. Ce qui compte est de prouver que l'instrumentation LLM (Phase 4)
**est nécessaire** parce que sans elle, on ne voit rien.

## Catégorie

**LLM qualité.** Cas direct de la « fuite par hallucination » mentionnée dans
le brief (RGPD : risque de mentionner un dossier d'apprenant d'une autre
formation).

## Injection

```bash
cd <leur-clone>
./incidents/apply.sh 03
```

**Important** : pour que l'incident soit observable, **pose toi-même** depuis
le frontend des questions à la limite du périmètre, par exemple :

- « Avez-vous une formation Cloud AWS de 6 mois ? »
- « Quel est le tarif de la formation cybersécurité avancée ? »
- « Les frais de scolarité sont-ils déductibles d'impôts ? »

Note les réponses : un patché renverra des réponses **plausibles mais
inventées** (chiffres faux, modalités fantaisistes) au lieu de « je n'ai pas
trouvé ».

## Revert

```bash
./incidents/revert.sh 03
```

## Ce qui se passe sous le capot

Le `RAG_SYSTEM_PROMPT` a perdu :

- le mot **EXCLUSIVEMENT** dans le rôle,
- la règle 1 stricte (« UNIQUEMENT avec les informations présentes »),
- la règle 2 (« ne jamais inventer »).

Le modèle est désormais invité à **compléter avec ses connaissances générales**
quand le contexte est insuffisant. Il s'exécute, plausiblement.

## Signaux attendus

| Source | Signal | Fenêtre |
|--------|--------|---------|
| Prometheus | **Rien d'anormal** (latence stable, pas de 5xx) | — |
| Alertmanager | **Aucune alerte** | — |
| Grafana panel `rag_evaluator_score` | Histogramme glisse légèrement vers la gauche (le LLM-évaluateur juge moins favorablement les réponses non sourcées) | 5-10 min |
| Langfuse (Phase 4) | Faithfulness scores chutent dans le dashboard Ragas ; user feedback 👎 si endpoint `/feedback` implémenté | 5-10 min |
| Manual QA | L'apprenant·e qui pose la question lit des bêtises plausibles | immédiat |

## Pédagogiquement

L'objectif est de leur faire dire :

> « Sans Langfuse / sans scoring qualité / sans feedback utilisateur,
> on ne **peut pas** voir cet incident dans notre observabilité actuelle. »

C'est la justification écrite « pourquoi Langfuse plutôt que Prometheus seul »
qui doit ressortir du post-mortem.

## Indices à donner si le binôme sèche

- **5 min** : « Toutes les réponses sont-elles fondées sur la documentation
  fournie ? Comment le savez-vous depuis votre stack ? »
- **10 min** : « Quelle métrique mesure la qualité d'une réponse, pas sa
  vitesse ? »
- **15 min** : « Si l'utilisateur pouvait noter 👎, vous l'auriez vu où ? »

## Anti-spoilers

- Ne PAS dire « prompt » ni « contexte » jusqu'au debrief.
- Pousser à utiliser l'eval Ragas (`POST /eval/run`) avec un mini-corpus
  préparé — c'est un signal complémentaire que l'agent **peut** détecter.

## Critères de validation (RNCP)

- C11.3 — Monitoring de la qualité LLM, pas seulement de la latence
- C11.3 — Pseudonymisation : aucune trace ne doit montrer le contenu brut de
  la question, même quand l'incident touche au RGPD
- C21.2 — Le post-mortem distingue **signaux observés** (rien) et **signaux
  manquants** (faithfulness, feedback), et propose d'ajouter ces signaux
