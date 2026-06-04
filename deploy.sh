#!/bin/bash
set -e

echo "🚀 Début du déploiement..."

cd "$(dirname "$0")"

echo "📥 Récupération des dernières modifications Git..."
git pull origin main

echo "🛑 Arrêt des conteneurs existants..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml down

echo "📦 Reconstruction et démarrage des services avec Docker Compose..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

if [ -d "./api/data/alembic" ]; then
    echo "🗄️ Vérification des migrations de base de données..."
    docker compose exec -T api alembic upgrade head || echo "⚠️ Pas de conteneur API actif pour exécuter Alembic (normal au premier run)"
fi

echo "🧹 Nettoyage des images Docker obsolètes..."
docker image prune -f

echo "✅ Déploiement terminé avec succès !"