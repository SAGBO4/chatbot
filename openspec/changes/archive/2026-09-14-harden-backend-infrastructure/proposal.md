## Why

Le backend et le bot reposent actuellement sur des mécanismes fragiles ou sous-optimaux pour l'évolution de la base de données (modifications SQL ad-hoc faites à la main dans `database.py`), la communication HTTP sortante (instanciation et destruction de clients `httpx.AsyncClient` à chaque requête au lieu de mutualiser les connexions via un singleton), et la couverture de résilience de l'assistant IA face aux pannes des API tierces (timeouts, erreurs 429 / 5xx non testées formellement).

Stabiliser ces trois briques d'infrastructure garantit la fiabilité opérationnelle, prévient les pannes en production lors des montées de version et assure une dégradation gracieuse testée face aux fournisseurs d'IA externes.

## What Changes

- **Alembic Database Migrations** : Initialisation d'un environnement de migrations Alembic standardisé pour SQLAlchemy 2.0 (asyncio / aiosqlite), génération de la migration initiale pour `tickets` et `knowledge_articles`, et exécution automatisée ou documentée des migrations en remplacement de `_add_missing_columns`.
- **Client HTTP Global / Singleton (`httpx.AsyncClient`)** : Mutualisation des sessions HTTP dans le backend (lifespan FastAPI) et dans le bot Telegram (`api_client.py`) avec gestion propre du cycle de vie (`startup` / `shutdown`), éliminant l'overhead TCP/TLS à chaque requête.
- **Résilience & Tests d'Erreurs LLM** : Ajout de tests unitaires simulant explicitement les timeouts réseau, les dépassements de quota (HTTP 429), les erreurs serveur 5xx et les réponses JSON inattendues des fournisseurs LLM pour valider le comportement de fallback sans incident.

## Capabilities

### New Capabilities
- `database-migrations`: Gestion déclarative et versionnée des évolutions de schéma de base de données via Alembic avec support asynchrone.

### Modified Capabilities
- `ai-assistant`: Spécification explicite des exigences de résilience et de dégradation gracieuse en cas d'erreurs ou d'indisponibilité du fournisseur LLM (HTTP 429, timeouts, erreurs 5xx).

## Impact

- `backend/database.py` : Remplacement du mécanisme ad-hoc `_add_missing_columns` par l'exécution d'Alembic.
- `alembic.ini`, `alembic/` : Ajout des configurations et scripts de migration.
- `backend/main.py`, `backend/services/telegram_relay.py`, `backend/services/ai_assistant.py` : Utilisation de sessions HTTP partagées.
- `bot/api_client.py`, `bot/main.py` : Utilisation d'un client HTTP persistant pour le bot.
- `requirements.txt` : Ajout d'Alembic.
- `tests/test_api.py` / `tests/test_ai_assistant_resilience.py` : Ajout d'une suite de tests ciblant les pannes de fournisseurs externes.
