## Context

Actuellement, le backend exécute `init_db()` au démarrage (`lifespan`), qui appelle `Base.metadata.create_all` et inspecte les tables existantes pour faire des `ALTER TABLE ADD COLUMN` bruts. De plus, `api_client.py` côté bot ainsi que `telegram_relay.py` et `ai_assistant.py` côté backend réinstancient un `httpx.AsyncClient` à chaque appel HTTP. Enfin, les tests existants de l'assistant IA ne testent que les chemins nominaux (HTTP 200).

## Goals / Non-Goals

**Goals:**
- Configurer Alembic avec le support asynchrone (`asyncio`) pour les modèles SQLAlchemy existants (`Ticket`, `KnowledgeArticle`).
- Fournir une migration initiale couvrant l'état actuel du schéma.
- Remplacer l'instanciation ad-hoc de `httpx.AsyncClient` par un singleton / client managé au niveau du cycle de vie du backend et du bot.
- Ajouter des tests unitaires complets vérifiant que les timeouts, codes 429 et 500 des LLMs ne font pas crasher le service.

**Non-Goals:**
- Réécrire la logique métier de recherche ou les prompts de l'assistant IA.
- Remplacer SQLite/aiosqlite par un SGBD distant dans cette itération.

## Decisions

### 1. Structure et intégration d'Alembic
- **Choix**: Utiliser le template `async` d'Alembic (`alembic.ini` à la racine, dossier `alembic/`).
- **Configuration**: L'URL de la base dans `env.py` dérive dynamiquement de `backend.config.settings.DATABASE_URL`. Le `target_metadata` pointe sur `backend.models.Base.metadata`.
- **Rétrocompatibilité**: Pour les tests automatisés en mémoire ou les nouvelles installations, `init_db` exécutera les migrations ou `create_all` de manière idempotente sans perturber le cycle de test pytest.

### 2. Gestion du cycle de vie HTTP (`httpx.AsyncClient`)
- **Côté Backend**: Dans `backend/main.py`, le lifespan initialise un `httpx.AsyncClient(timeout=15.0)` stocké sur `app.state.http_client` et le referme proprement dans `finally: await app.state.http_client.aclose()`. Les services `TelegramRelay` et `AIAssistantService` acceptent un client injecté en priorité, tout en gardant une méthode d'accès globale par défaut.
- **Côté Bot**: Dans `bot/api_client.py`, la classe `BackendClient` maintient un `self._client: Optional[httpx.AsyncClient] = None` réutilisé à travers toutes les requêtes, avec une méthode `async def close()` appelée lors de l'arrêt du polling dans `bot/main.py`.

### 3. Stratégie de test des pannes LLM
- **Choix**: Utiliser `unittest.mock.AsyncMock` ou `httpx.MockTransport` dans `tests/test_ai_assistant_resilience.py`.
- **Cas couverts**:
  - `httpx.ReadTimeout` et `httpx.ConnectTimeout`
  - Réponses HTTP 429 (Rate Limit Exceeded)
  - Réponses HTTP 500 (Internal Server Error)
  - Payloads JSON invalides ou vides (`{}` ou `{"choices": []}`)

## Risks / Trade-offs

- [Alembic en environnement de test SQLite en mémoire] → Configuration d'Alembic pour supporter les URLs SQLite relatives et fallback gracieux dans la suite de tests unitaires pour éviter les verrous de fichiers.
- [Fermeture des connexions HTTP du bot à l'arrêt] → Ajout d'un bloc `try...finally` explicite dans `bot/main.py` pour fermer le client du bot en même temps que la session `Bot` d'aiogram.
