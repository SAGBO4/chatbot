# TODO — ce qu'il te reste à faire

Tout le code nécessaire est écrit et testé (56/56 tests passent). Ce qui reste est **de la
configuration et des décisions**, pas du code à écrire — sauf un point signalé plus bas (webhook
Brevo entrant).

## 1. Obligatoire pour que le bot tourne (local ou VPS)

Dans `.env` (déjà créé à la racine, avec secrets générés) :

- [ ] `TELEGRAM_BOT_TOKEN` : remplace le placeholder par le token donné par **@BotFather** sur Telegram.
- [ ] `TELEGRAM_SUPPORT_GROUP_ID` : remplace `0` par l'ID de ton groupe Telegram support (nombre
      négatif, ex. `-1001234567890`).
      → Crée le groupe, ajoute le bot dedans, puis récupère l'ID (ex. via `getUpdates` sur l'API
      Telegram, ou un bot comme @RawDataBot ajouté temporairement au groupe).

Sans ces deux valeurs, le bot Telegram ne peut pas fonctionner (token invalide = le bot ne se
connecte pas ; groupe non configuré = les tickets ne sont jamais notifiés côté équipe support, et
`support_handlers.py` ignore toute réponse puisqu'aucun groupe n'est reconnu comme légitime).

## 2. Obligatoire si le backend est exposé sur internet (ton cas : VPS)

- [x] Vérifie que `.env` sur le VPS a bien `API_KEY` renseigné avec une valeur longue et aléatoire
      (déjà généré dans le `.env` local — génère-en une **différente** pour le VPS avec
      `openssl rand -hex 32`, ne réutilise pas celle du repo local).
- [x] Mets **la même valeur** `API_KEY` dans le `.env` du processus bot (peut tourner ailleurs que
      le VPS backend) — `bot/api_client.py` l'envoie automatiquement dans le header `X-API-Key`.
- [x] Idem pour `EMAIL_WEBHOOK_SECRET` si tu actives le webhook email entrant (voir section Brevo).
      → `BREVO_INBOUND_SECRET` aussi généré et renseigné (`.env` local) pour le webhook Brevo natif
      (section 5).
- [ ] Si un jour un front web (autre que le bot) appelle l'API depuis un navigateur, régler
      `CORS_ALLOWED_ORIGINS=https://ton-domaine.com` (sinon laisse `*`, ça ne concerne pas le bot).

Sans `API_KEY` configuré, l'API refuse tout (503) — c'est voulu, pas un bug.

## 3. Optionnel — activer les réponses IA

Seulement si tu veux que le bot synthétise les réponses avec un LLM plutôt que de renvoyer le
texte brut de la base de connaissances :

- [ ] `AI_ENABLED=true`
- [ ] `AI_PROVIDER=openai` (ou `gemini`, ou `deepseek`)
- [ ] `AI_API_KEY=<ta clé du provider choisi>`
- [ ] `AI_MODEL=` (laisse vide pour le modèle par défaut du provider, ou précise-en un)

Si tu ne fais rien ici, le bot continue de fonctionner normalement en renvoyant directement la
solution trouvée dans la base de connaissances (comportement actuel, sans IA).

## 4. Email sortant — Brevo (notifications de ticket créé/résolu)

- [ ] `EMAIL_ENABLED=true`
- [ ] `SMTP_HOST=smtp-relay.brevo.com`
- [ ] `SMTP_PORT=587`
- [ ] `SMTP_USER=<login SMTP Brevo>`
- [ ] `SMTP_PASSWORD=<clé SMTP Brevo>`
- [ ] `SMTP_FROM=<adresse expéditeur vérifiée sur Brevo>`
- [ ] `SUPPORT_EMAIL_RECIPIENT=<adresse de ton équipe support>`

Rien à changer côté code : le relais SMTP de Brevo est compatible avec `email_service.py` tel
quel.

## 5. Email entrant — Brevo (réponse d'un agent par email → résolution de ticket)

**Implémenté** : `POST /api/webhooks/email-inbound/brevo` existe (`backend/main.py`), parse le
format natif de Brevo (`items[]`), traite chaque email du batch indépendamment (un item invalide
ne bloque pas les autres), et réutilise exactement la même logique de résolution que le webhook
générique (recherche du ticket, notification Telegram, mise à jour base de connaissances).
6 tests dédiés dans `tests/test_brevo_inbound_webhook.py` (38/38 tests passent au total).

- [x] `BREVO_INBOUND_SECRET` généré (`openssl rand -hex 32`) et renseigné dans le `.env` local.
- [ ] **Sur le VPS** : génère une valeur **différente** de `BREVO_INBOUND_SECRET` pour la prod
      (ne réutilise pas celle du repo local), et mets-la dans le `.env` du VPS.
- [ ] Configurer dans le dashboard Brevo le webhook "Inbound Parsing" vers :
  `https://<ton-backend>/api/webhooks/email-inbound/brevo?token=<BREVO_INBOUND_SECRET>`
  (nécessite que le backend soit exposé publiquement — impossible à tester en local sans un tunnel
  type ngrok/Cloudflare Tunnel).
- [ ] Si un reverse proxy est devant le backend, désactiver le logging des query strings pour ce
  chemin (le secret voyage dans l'URL, faute de mécanisme de signature côté Brevo).

**Tant que le webhook Brevo n'est pas configuré côté dashboard (avec une URL publique), une
réponse d'agent par email ne peut pas résoudre automatiquement un ticket** — seule la résolution
via Telegram (groupe support) fonctionne en local.

## 6. Si tu déploies avec `docker-compose.yml`
 
 - [x] **Corrigé** : Le montage monte désormais le répertoire `./data:/app/data` au lieu d'un fichier direct, évitant le piège de création d'un dossier `chatbot.db` vide. Un `.gitkeep` a été ajouté au dossier `data/`.

## 7. Si tu as déjà un `chatbot.db` local avec des tickets dedans

- [x] **Rien à faire** : `init_db()` détecte maintenant lui-même les colonnes manquantes sur une
      table déjà existante (`resolution_channel`, `support_group_message_id`) et les ajoute via
      `ALTER TABLE` au démarrage du backend — plus besoin de supprimer `chatbot.db`. C'était la
      faille critique remontée par l'ultrareview (toute base pré-existante plantait en 500 sur
      `/api/tickets` après mise à jour) ; corrigée dans `backend/database.py`, testée dans
      `tests/test_database.py`.

---

## ✅ Déjà fait (code, pas d'action de ta part)

- Faille critique corrigée : `support_handlers.py` ignore toute réponse ne provenant pas du groupe
  Telegram support configuré (`TELEGRAM_SUPPORT_GROUP_ID`), avec tests de non-régression.
- Audit de `user_handlers.py` : pas de faille équivalente trouvée.
- Webhook email entrant protégé par HMAC-SHA256 fail-closed (`EMAIL_WEBHOOK_SECRET`).
- Authentification API (`X-API-Key`) sur toutes les routes du backend (`/api/query`,
  `/api/tickets*`, `/api/knowledge*`), fail-closed si `API_KEY` non configuré.
- CORS corrigé (`allow_credentials=False`, origines configurables via `CORS_ALLOWED_ORIGINS`).
- Multi-provider IA (`openai` / `gemini` / `deepseek`) avec modèle par défaut par provider.
- Bug corrigé : le modèle Gemini par défaut (`gemini-1.5-flash`) est retiré côté Google (404). Remplacé
  par `gemini-2.5-flash`, vérifié avec un vrai appel à l'API. Pense à revérifier périodiquement que
  le modèle par défaut choisi (`AIAssistantService.DEFAULT_MODELS`) est toujours disponible pour ta
  clé (`GET https://generativelanguage.googleapis.com/v1beta/models?key=<ta_clé>`), les providers
  retirent leurs anciens modèles sans préavis long.
- Rappel : Gemini (ou tout provider IA) n'est appelé que si la base de connaissances a déjà trouvé un
  article correspondant à la question (`KB_CONFIDENCE_THRESHOLD`) — il reformule une réponse existante,
  il n'invente jamais une réponse à partir de rien. Base de connaissances vide ou question sans
  correspondance = pas d'appel IA, juste le message de fallback proposant l'escalade support.
- Résolution des tickets par réponse Telegram rendue robuste : identifiée en priorité par
  l'identité du message (`support_group_message_id`), et non plus seulement par une regex sur le
  texte de la carte ; l'ancienne regex reste en secours (aucune régression), et l'agent reçoit
  désormais un message explicite si sa réponse ne peut être associée à aucun ticket.
- Fichier `.env` local créé (gitignored) avec secrets déjà générés pour tester tout de suite.
- Base de connaissances initiale chargée (22 articles FAQ Stack Wallet, bilingue FR/EN) via
  `scripts/seed_knowledge_base.py` (upsert : relançable sans dupliquer, met à jour le contenu
  modifié et supprime les entrées retirées). Liste des canaux de support vérifiée sur la vraie
  page `stackwallet.com/index.html#support` (Telegram, Discord, Reddit, Twitter/X, YouTube,
  Session, Mastodon, email). Le prompt IA (`ai_assistant.py`) répond désormais explicitement dans
  la langue de la question de l'utilisateur.
- **4 anomalies "normal" de l'ultrareview corrigées** (branche `feat/email-support-sync`) :
  - Migration auto au démarrage (`backend/database.py`) — voir section 7 ci-dessus.
  - `clean_email_reply_body` ne renvoie plus le corps brut (citations comprises) quand la réponse
    d'un agent ne contient aucun nouveau contenu ; elle renvoie une chaîne vide.
  - Une réponse email vide après nettoyage des citations laisse maintenant le ticket **non résolu**
    (HTTP 400) au lieu de le résoudre avec une solution vide et de polluer la base de connaissances.
  - Le contenu d'email injecté dans les messages Telegram (nom de l'agent, solution) est désormais
    échappé (`escape_telegram_markdown`) avant d'être inséré dans le Markdown — un `_`, `*` ou `` ` ``
    dans l'email ne fait plus rejeter l'envoi par Telegram après coup.
  - 5 tests ajoutés pour ces 4 correctifs (`tests/test_database.py`, `tests/test_email_sync.py`).
- **5 anomalies "mineur" de l'ultrareview corrigées** :
  - Webhook Brevo : le token (`?token=`) est vérifié avant de parser le corps JSON, plus après —
    un appel non authentifié ne révèle plus la forme JSON attendue via un 422.
  - `EmailService._send_smtp_sync` gère désormais `SMTP_PORT=465` (TLS implicite : Gmail SSL,
    iCloud…) avec `smtplib.SMTP_SSL` ; le port 587 garde `SMTP` + `starttls()`.
  - Test sentinelle « groupe support non configuré » dédupliqué dans une seule méthode
    `Settings.support_group_is_configured()` (`backend/config.py`), utilisée par les 3 anciens
    call-sites.
  - `AIAssistantService` ne ferme plus un `httpx.AsyncClient` fourni par l'appelant (seul un client
    créé en interne est fermé après l'appel).
  - `.env.example` corrigé : modèle Gemini par défaut documenté `gemini-2.5-flash`.
  - 6 tests ajoutés (`tests/test_brevo_inbound_webhook.py`, `tests/test_email_service.py`,
    `tests/test_config.py`).
- **Bug pré-existant corrigé** : un agent qui répond avec un média (photo, sticker, vocal...) dans
  le groupe support ne fait plus planter le bot (`message.text.strip()` sur `None`).
  `bot/handlers/support_handlers.py` utilise maintenant, dans l'ordre : le texte, sinon la légende
  du média (une capture d'écran commentée résout directement le ticket), sinon une transcription
  automatique si c'est un vocal/audio et que `AI_PROVIDER=openai` (Whisper), sinon un message
  explicite demandant à l'agent de répondre en texte (plus de plantage silencieux).
  - Speech-to-text : `_transcribe_voice_message` télécharge le fichier vocal via l'API Telegram et
    appelle `POST https://api.openai.com/v1/audio/transcriptions` (modèle `whisper-1`). Uniquement
    disponible avec `AI_PROVIDER=openai` + `AI_API_KEY` — Whisper est spécifique à OpenAI, donc
    Gemini/DeepSeek retombent sur la demande de réponse texte.
  - 5 tests ajoutés (`tests/test_bot_handlers.py`) : média sans légende, photo avec légende, vocal
    transcrit, vocal sans provider OpenAI configuré.
- 56/56 tests passent (51 tests fonctionnels/sync + 5 tests de résilience LLM).
- **Hardening infrastructure backend (OpenSpec `harden-backend-infrastructure`)** :
  - **Alembic pour les migrations** : Environnement Alembic async configuré (`alembic.ini`, dossier `alembic/`), première révision générée (`create_initial_tables`), commande d'upgrade intégrée automatiquement dans `backend/database.py`.
  - **Client HTTP global (Singleton)** : Mutualisation d'une session `httpx.AsyncClient` persistante gérée dans le `lifespan` FastAPI (backend) et dans `BackendClient` avec fermeture propre dans `bot/main.py` (bot), éliminant l'overhead TCP/TLS répété.
  - **Tests de résilience LLM (`tests/test_ai_assistant_resilience.py`)** : Couverture complète des pannes externes (timeouts `ReadTimeout`/`ConnectTimeout`, code 429 Rate Limit, code 500, réponses JSON malformées ou vides) garantissant la dégradation gracieuse sans crash.
  - **Optimisation de la base de connaissances** : Pré-filtrage SQL `LIKE`/`ilike` avant le calcul de similarité, éliminant le chargement exhaustif de la table en mémoire.
  - **Docker & CI/CD** : Conteneur s'exécutant avec l'utilisateur non privilégié `appuser`, montage Docker Compose sécurisé (`./data:/app/data`), et workflow GitHub Actions (`.github/workflows/ci.yml`) ajouté.
- **Correctifs de l'Ultra-Review (branche `feat/ultra-review-fixes`)** :
  - **SEC-01 (Markdown & fallback Telegram)** : Échappement Markdown systématique des données utilisateur/agent (`bot/utils.py`, `support_handlers.py`, `user_handlers.py`) et fallback automatique en texte brut en cas d'erreur de parsing Telegram.
  - **OPS-01 (Permissions conteneur & persistance SQLite)** : `COPY --chown=appuser:appuser` et création de `/app/data` dans le `Dockerfile` ; `DATABASE_URL` par défaut aligné sur `./data/chatbot.db` pour garantir la persistance via le volume docker-compose.
  - **DB-01 (Telegram IDs 64-bit)** : Migration de `user_id` et `support_group_message_id` en `BigInteger` dans `backend/models.py` et dans la révision Alembic initiale pour compatibilité complète PostgreSQL.
  - **PERF-01 (Moteur de recherche hybride & fuzzy)** : Ajout des préfixes de stems dans le filtre SQL et fallback vers l'analyse n-grammes/floue en mémoire si aucun mot-clé exact n'est trouvé.
  - **RES-01 (Singleton HTTP dans le bot)** : Injection du `BackendClient` singleton dans le Dispatcher (`bot/main.py`) et fermeture propre dans le `finally` de l'application.
  - **OBS-01 (Logs TelegramRelay)** : Log explicite du code HTTP et du corps de rejet Telegram en cas d'échec d'envoi.
  - **TEST-01 & CI-01 (Tests & CI)** : Isolation hermétique des tests E2E (`AI_ENABLED=False`) et ajout de l'installation de `ruff` dans le workflow GitHub Actions.
  - **58/58 tests passent**.
