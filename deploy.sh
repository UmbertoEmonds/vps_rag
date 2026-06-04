#!/bin/bash
set -e

echo "🚀 Début du déploiement..."

cd "$(dirname "$0")"

# Reconstruire et relancer les conteneurs
echo "📦 Reconstruction et démarrage des services avec Docker Compose..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Lancer les migrations de base de données
if [ -d "./api/data/alembic" ]; then
    echo "🗄️ Vérification des migrations de base de données..."
    docker compose exec -T api alembic upgrade head || echo "⚠️ Pas de conteneur API actif pour exécuter Alembic (normal au premier run)"
fi

# Nettoyer les vieilles images Docker
echo "🧹 Nettoyage des images Docker obsolètes..."
docker image prune -f

echo "✅ Déploiement terminé avec succès !"