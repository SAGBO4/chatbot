## 1. Alembic Migration Setup

- [x] 1.1 Ajouter alembic aux dépendances dans `requirements.txt` et vérifier avec `pip install -r requirements.txt`
- [x] 1.2 Initialiser l'environnement Alembic async (`alembic.ini` et `alembic/`) et configurer `env.py` pour importer `Base.metadata` et `settings.DATABASE_URL`
- [x] 1.3 Générer la première révision de migration pour les tables `tickets` et `knowledge_articles` et vérifier sa cohérence
- [x] 1.4 Adapter `backend/database.py` pour intégrer ou documenter la commande de migration tout en préservant l'idempotence sur bases existantes

## 2. Global HTTP Client (Singleton)

- [x] 2.1 Refactoriser `bot/api_client.py` pour réutiliser un `httpx.AsyncClient` persistant avec méthode `close()`, et mettre à jour `bot/main.py` pour fermer le client proprement
- [x] 2.2 Configurer un client HTTP global persistant dans `backend/main.py` (via lifespan) et le partager avec `TelegramRelay` et `AIAssistantService`
- [x] 2.3 Exécuter les tests unitaires existants (`pytest tests/test_api.py tests/test_bot_handlers.py`) pour vérifier l'absence de régression de connectivité

## 3. LLM Resilience & Error Handling Tests

- [x] 3.1 Créer `tests/test_ai_assistant_resilience.py` couvrant les scénarios de timeouts (`httpx.ReadTimeout`, `httpx.ConnectTimeout`)
- [x] 3.2 Ajouter les scénarios de test pour les erreurs HTTP 429 (Rate Limit), HTTP 500 et les payloads JSON corrompus/incomplets
- [x] 3.3 Vérifier que tous les tests passent avec `pytest tests/test_ai_assistant_resilience.py`
