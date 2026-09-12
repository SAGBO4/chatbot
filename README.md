# Telegram Support Bot with Knowledge Base & AI Feedback Loop

Ce projet implémente un système complet de support automatisé sur Telegram, connecté à une API Backend FastAPI, une base de connaissances évolutive et un module IA configurable.

---

## Architecture du Système

```
                    TELEGRAM
                       │
                       ▼
                ┌──────────────┐
                │  Bot Telegram │
                └──────┬───────┘
                       │
                       ▼
                ┌──────────────┐
                │ Backend API  │
                └──────┬───────┘
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
      Base de connaissances    IA (Optionnelle)
             │                   │
             └─────────┬─────────┘
                       ▼
                Réponse utilisateur
                       │
                 problème résolu ?
                    /       \
                  OUI        NON
                   │          │
                   ▼          ▼
                 FIN       TICKET
                              │
                              ▼
                         TEAM SUPPORT (Groupe Telegram)
                              │
                              ▼
                       Nouvelle solution
                              │
                              ▼
                    Base de connaissances
```

### Fonctionnalités clés :
1. **Support Telegram automatisé** : L'utilisateur pose sa question et reçoit une solution instantanée.
2. **Double validation (OUI / NON)** : Boutons interactifs sous la réponse pour valider la résolution.
3. **Escalade automatique (NON)** : Génération immédiate d'un ticket et notification dans un groupe Telegram support privé.
4. **Résolution par citation Telegram** : L'équipe support répond simplement au message du ticket dans le groupe pour envoyer la solution à l'utilisateur.
5. **Apprentissage continu (Feedback Loop)** : Chaque solution fournie par un agent support est automatiquement indexée dans la base de connaissances.
6. **IA Débrayable / Sans surcoût** : Fonctionne de manière 100 % autonome sans IA via recherche par similarité lexicale/sémantique, ou avec un LLM (OpenAI, Gemini, etc.) si une clé API est configurée.

---

## Structure du Projet

```
├── backend/
│   ├── config.py                 # Configuration Pydantic (variables d'environnement)
│   ├── database.py               # Moteur de base de données SQLAlchemy asynchrone (SQLite)
│   ├── models.py                 # Modèles (Tickets, Base de connaissances)
│   ├── schemas.py                # Schémas Pydantic pour requêtes / réponses
│   ├── main.py                   # Application FastAPI et routes REST
│   └── services/
│       ├── knowledge_base.py     # Moteur de recherche et d'ingestion KB
│       ├── query_orchestrator.py # Pipeline d'orchestration de requêtes
│       ├── ai_assistant.py       # Module IA optionnel (LLM RAG)
│       └── ticket_service.py     # Gestion du cycle de vie des tickets
├── bot/
│   ├── api_client.py             # Client HTTP asynchrone vers le backend
│   ├── keyboards.py              # Claviers inline Telegram (OUI / NON)
│   ├── main.py                   # Point d'entrée du bot Telegram (aiogram 3)
│   └── handlers/
│       ├── user_handlers.py      # Handlers pour les utilisateurs privés
│       └── support_handlers.py   # Handlers pour le groupe de support
├── tests/                        # Suite de tests unitaires et d'intégration E2E
├── Dockerfile                    # Image Docker de production
├── docker-compose.yml            # Déploiement multi-services (backend + bot)
├── requirements.txt              # Dépendances Python
└── .env.example                  # Exemple de variables d'environnement
```

---

## Installation & Démarrage Rapide

### 1. Cloner et configurer l'environnement

```bash
# Cloner le dépôt
git clone <url_du_repo>
cd chatbot

# Créer un environnement virtuel
virtualenv .venv
source .venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt

# Copier le fichier de configuration
cp .env.example .env
```

### 2. Configurer le fichier `.env`

Éditez le fichier `.env` avec vos identifiants Telegram :
```ini
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRstuVWXyz
TELEGRAM_SUPPORT_GROUP_ID=-1001234567890

# Activer l'IA (Optionnel)
AI_ENABLED=false
AI_API_KEY=
```

> **Astuce pour obtenir votre `TELEGRAM_SUPPORT_GROUP_ID` :**
> 1. Créez un groupe Telegram pour votre équipe support et ajoutez-y votre bot.
> 2. Envoyez un message dans le groupe, puis appelez `https://api.telegram.org/bot<TOKEN>/getUpdates` pour lire le `chat.id` (nombre négatif commençant par `-100`).

### 3. Lancer les services

#### Mode Développement local :
```bash
# Terminal 1 : Lancer le backend
uvicorn backend.main:app --reload --port 8000

# Terminal 2 : Lancer le bot Telegram
python -m bot.main
```

#### Mode Docker Compose :
```bash
docker compose up --build -d
```

---

## Tests et Vérification

La suite de tests automatisée couvre les tests unitaires, de base de données, d'API et le scénario complet de bout en bout (E2E) :

```bash
pytest -v
```
