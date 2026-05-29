#!/bin/bash

# Interrompt le script si une commande échoue
set -e

echo "🚀 Début du déploiement..."

# 1. Se déplacer dans le dossier de l'application sur le VPS
cd "$(dirname "$0")"

# 2. Récupérer la dernière version du code
echo "📥 Récupération des dernières modifications Git..."
git fetch origin main
git reset --hard origin/main

# 3. Reconstruire et relancer les conteneurs
echo "📦 Reconstruction et démarrage des services avec Docker Compose..."
# (Ajuste docker-compose.yml si tu utilises docker-compose.prod.yml)
docker compose up -d --build

# 4. Optionnel : Lancer les migrations de base de données (vu ton dossier alembic)
if [ -d "./api/data/alembic" ]; then
    echo "🗄️ Vérification des migrations de base de données..."
    docker compose exec -T api alembic upgrade head || echo "⚠️ Pas de conteneur API actif pour exécuter Alembic (normal au premier run)"
fi

# 5. Nettoyer les vieilles images Docker pour ne pas saturer le VPS
echo "🧹 Nettoyage des images Docker obsolètes..."
docker image prune -f

echo "✅ Déploiement terminé avec succès !"
