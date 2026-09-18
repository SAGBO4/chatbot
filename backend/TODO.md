# TODO — ce qu'il te reste à faire

Tout le code nécessaire est écrit et testé (376/376 tests passent). Ce qui reste est **de la
configuration et des décisions**, pas du code à écrire — les intégrations (webhook Brevo entrant/sortant,
relais Telegram, base de connaissances, protection IDOR, résilience asynchrone, groupe communautaire,
modération, données crypto, bilinguisme FR/EN) sont opérationnelles.

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

- [ ] `BOT_OWNER_TELEGRAM_ID` : ton propre ID Telegram (nombre, pas ton `@username`) — message
      **@userinfobot** sur Telegram pour l'obtenir. C'est toi qui pourras configurer le groupe
      communautaire, gérer la liste blanche d'admins et changer la langue du bot (voir section 1bis).
      Sans cette valeur, personne ne peut lancer `/setup_community`, `/whitelist` ou `/language`.

## 1bis. Configurer le groupe communautaire (plus besoin de `.env`, se fait dans Telegram)

Contrairement au groupe support (section 1, fixe dans `.env`), le **groupe communautaire** (là où
les membres posent leurs questions avec `/ask`, où s'appliquent la modération et `/purge`) se
configure désormais depuis Telegram, à tout moment, sans redéploiement :

- [ ] Envoie `/start` en message privé au bot avec ton compte `BOT_OWNER_TELEGRAM_ID` → comme aucun
      groupe communautaire n'est encore configuré, le bot répond avec un tutoriel de configuration.
- [ ] Ajoute le bot comme **administrateur** du groupe Telegram que tu veux utiliser comme groupe
      communautaire, avec les droits : restreindre les membres, bannir/débannir, supprimer des
      messages (sinon `/mute`, `/ban`, `/kick` et `/purge` échoueront avec une erreur de permission
      Telegram).
- [ ] Dans ce groupe, envoie `/setup_community` — il devient immédiatement le groupe communautaire
      actif (relançable à tout moment pour en changer).
- [ ] (Optionnel) En tant que owner, `/whitelist add <user_id>` pour qu'un autre admin de confiance
      puisse aussi lancer `/setup_community` et `/language` (il ne pourra pas gérer la liste
      blanche lui-même, seul le owner le peut).
- [ ] (Optionnel) `/language en` pour basculer tous les messages du bot en anglais (`/language fr`
      pour revenir au français, qui est la langue par défaut).

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
ne bloque pas les autres), et réutilise la logique de résolution partagée (recherche du ticket,
notification Telegram, mise à jour base de connaissances).
Supporte désormais la **double authentification** : par en-tête HTTP (`X-Webhook-Token` ou
`X-Brevo-Token`) pour éviter l'exposition des secrets dans les URL et les journaux, tout en
préservant le paramètre de requête `?token=` avec masquage automatique dans les logs.

- [x] `BREVO_INBOUND_SECRET` généré (`openssl rand -hex 32`) et renseigné dans le `.env` local.
- [ ] **Sur le VPS** : génère une valeur **différente** de `BREVO_INBOUND_SECRET` pour la prod
      (ne réutilise pas celle du repo local), et mets-la dans le `.env` du VPS.
- [ ] Configurer dans le dashboard Brevo le webhook "Inbound Parsing" vers :
  `https://<ton-backend>/api/webhooks/email-inbound/brevo?token=<BREVO_INBOUND_SECRET>`
  (ou via un proxy ajoutant le header `X-Webhook-Token: <BREVO_INBOUND_SECRET>`).
  (Nécessite que le backend soit exposé publiquement — impossible à tester en local sans un tunnel
  type ngrok/Cloudflare Tunnel).
- [x] **Protection des journaux d'accès** :
  - Un middleware ASGI de log sécurisé et un filtre `SensitiveDataFilter` masquent automatiquement
    les paramètres sensibles (`?token=[REDACTED]`) dans tous les logs applicatifs.
  - Modèles de configuration reverse proxy prêts à l'emploi :
    - Nginx : `deploy/nginx.conf` (utilise un format de log sans query string sur la route webhook)
    - Caddy : `deploy/Caddyfile` (filtre et masque le paramètre `token` dans les logs)

**Tant que le webhook Brevo n'est pas configuré côté dashboard (avec une URL publique), une
réponse d'agent par email ne peut pas résoudre automatiquement un ticket** — seule la résolution
via Telegram (groupe support) fonctionne en local.

## 6. Déploiement Production & Base de Données (PostgreSQL / SQLite)
 
- [x] **SQLite WAL (Dev / Petit VPS)** : `docker-compose.yml` monte `./data:/app/data` et active le mode WAL automatiquement.
- [x] **PostgreSQL 16 (Gros volumes & Multi-agents)** : `docker-compose.prod.yml` prêt à l'emploi avec conteneur Postgres 16 dédié, volume persistant `postgres_data` et pool de connexions (`asyncpg`).
  - Lancement : `docker compose -f docker-compose.prod.yml up -d`
  - Migration : `DATABASE_URL=postgresql+asyncpg://... alembic upgrade head`

## 7. Monitoring, Alerting & Télémétrie (Sentry)

- [ ] (Optionnel) Si tu disposes d'un compte Sentry, renseigne `SENTRY_DSN=https://...` dans ton `.env`. Le backend FastAPI et le bot Telegram captureront automatiquement toutes les exceptions non gérées avec tracebacks complets.
- [x] Le endpoint `/health` effectue désormais un ping actif (`SELECT 1`) sur la base de données et renvoie un HTTP 503 en cas de perte de connectivité.

## 8. Protection Anti-Spam & Rate Limiting

- [x] **Bot Telegram** : Throttling middleware in-memory actif (`bot/middlewares/throttling.py`), plafonné à 5 requêtes par fenêtre de 10 secondes par `user_id`.
- [x] **Backend API** : Rate limiting SlowAPI actif sur `/api/query` (30/min) et `/api/tickets` (10/min), répondant en HTTP 429 Too Many Requests.

## 9. Si tu as déjà un `chatbot.db` local avec des tickets dedans

- [x] **Rien à faire** : `init_db()` détecte maintenant lui-même les colonnes manquantes sur une
      table déjà existante (`resolution_channel`, `support_group_message_id`) et les ajoute via
      `ALTER TABLE` au démarrage du backend — plus besoin de supprimer `chatbot.db`.

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
  - **SEC-03 (Validation expéditeur email entrant)** : Vérification de l'expéditeur via `ALLOWED_SUPPORT_EMAIL_SENDERS` et `Settings.is_authorized_email_sender` pour prévenir l'empoisonnement de la base de connaissances et de l'assistance.
  - **RACE-01 (Prévention double-clic utilisateur)** : Consommation et vidage immédiat de l'état FSM dans `handle_resolve_no` avant l'appel API, évitant la duplication de tickets.
  - **RACE-02 (Alerte collision multi-agents)** : Ajout de `is_newly_resolved` dans `TicketResponse` et avertissement explicite dans le groupe Telegram si un collègue a déjà résolu le ticket.
  - **SEC-04 (Validation stricte des entrées)** : Bornes `min_length` et `max_length` via Pydantic `Field` sur toutes les chaînes d'entrée (`query`, `question`, `solution`).
  - **DB-02 (SQLite WAL mode)** : Activation automatique de `PRAGMA journal_mode=WAL` et `PRAGMA synchronous=NORMAL` sur l'engine pour éliminer les erreurs `database is locked`.
  - **ARCH-01 (Atomicité transactionnelle)** : Paramètre `auto_commit=False` dans `KnowledgeBaseService.add_article` lors de la résolution de ticket pour garantir un commit atomique unique.
  - **DB-03 (Pagination bornée)** : Paramètres `limit` (1-100) et `offset` (>=0) bornés via `Query` sur `/api/tickets`.
  - **SEC-05 (En-tête API Gemini)** : Utilisation de l'en-tête officiel `x-goog-api-key` au lieu de la query string dans l'URL.
- **Renforcement Sécurité & Résilience (OpenSpec `harden-security-and-resilience`)** :
  - **Protection IDOR & Scoping Utilisateur** : `GET /api/tickets` et `GET /api/tickets/{ticket_id}` supportent désormais le filtrage `user_id`. Les requêtes restreintes à un utilisateur ne peuvent plus accéder aux tickets d'un autre utilisateur (renvoie `404 Not Found`).
  - **Isolation Robuste des Tâches de Fond (`_safe_background_task`)** : Encapsulation hermétique de toutes les notifications asynchrones (`EmailService` et `TelegramRelay` dans `BackgroundTasks`). Les pannes réseau, déconnexions SMTP et erreurs Telegram n'interrompent plus le cycle de vie de la réponse HTTP 200/201 et ne font plus crasher Starlette/FastAPI après commit DB.
  - **Authentification Double Brevo & Masquage des Logs** : Prise en charge des en-têtes `X-Webhook-Token` et `X-Brevo-Token` sur le webhook Brevo entrant (`/api/webhooks/email-inbound/brevo`) pour éliminer les secrets des URL. Middleware de log et filtre `SensitiveDataFilter` masquant automatiquement les paramètres sensibles (`?token=[REDACTED]`).
  - **Herméticité des Tests** : Fixtures autouse dans `conftest.py` interceptant les appels externes SMTP Brevo et API Telegram pour des tests déterministes, sûrs et ultra-rapides (< 17s).
  - **Couverture de Tests Exhaustive** : 11 nouvelles suites de tests modulaires couvrant les 5 axes (Fonctionnel, Sécurité, Robustesse, Multi-assertions HTTP/DB/Logs, Structure standardisée `test_<feature>_<scenario>_<attendu>`).
- **238/238 tests passent** avec 85.24% de couverture globale (`htmlcov/`).
- **Groupe communautaire, crypto et modération (OpenSpec `expand-bot-community-features`)** :
  - `/ask <question>` dans le groupe communautaire : réponse publique taguant l'utilisateur, boutons
    OUI/NON qui expirent après inactivité, escalade de ticket qui reste confinée au groupe
    admin/email (jamais affichée dans le groupe communautaire).
  - `/purge` : un admin du groupe communautaire peut supprimer les derniers messages du bot sans
    avoir besoin d'accès au groupe admin.
  - Modération `/mute`, `/unmute`, `/ban`, `/kick`, `/warn` réservée aux admins Telegram vérifiés en
    direct via l'API Telegram (`bot/admin_check.py`), avec persistance des avertissements
    (`community_warnings`).
  - `/btc`, `/eth`, `/firo`, etc. : prix, variation 24h, capitalisation et volume via CoinGecko, en
    DM comme en groupe, avec cache et dégradation propre en cas de panne du fournisseur.
- **Configuration dynamique du groupe communautaire, contrôle d'accès & bilinguisme (OpenSpec
  `add-dynamic-community-group-setup`)** :
  - Le groupe communautaire n'est plus figé dans `.env` : `/setup_community`, lancé directement
    dans le groupe cible par le owner (`BOT_OWNER_TELEGRAM_ID`) ou un admin whitelisté, le définit
    (ou le change) à tout moment, sans redéploiement. Le groupe admin (`TELEGRAM_SUPPORT_GROUP_ID`)
    reste volontairement fixe dans `.env` pour ne jamais pouvoir être détourné depuis Telegram.
  - `/whitelist add|remove <user_id>` (réservé au owner) délègue le droit de configurer le groupe
    communautaire et la langue à d'autres admins de confiance.
  - Tutoriel de premier contact : `/start` en DM par un owner/admin autorisé sans groupe
    communautaire configuré affiche les étapes de configuration.
  - `TELEGRAM_COMMUNITY_GROUP_ID` devient une valeur d'amorçage unique (migration automatique au
    premier démarrage si déjà configurée avant cette mise à jour), plus jamais relue ensuite.
  - Bot bilingue FR/EN (`bot/i18n.py`) : `/language fr|en` bascule tous les messages du bot,
    français par défaut.
  - Bug corrigé en cours de route : `BOT_OWNER_TELEGRAM_ID` vide dans `.env` faisait planter le
    démarrage entier (`Optional[int]` + pydantic-settings rejette une chaîne vide) — corrigé par un
    validateur qui traite une valeur vide comme non configurée.
- **376/376 tests passent** (46 fichiers de tests au total, dont de nombreux nouveaux depuis les deux
  changements ci-dessus).
- **Audit Qualité & Sécurité Statique / Dynamique validé à 100%** :
  - **Couverture de code** : `pytest --cov=backend --cov=bot --cov-report=html --cov-fail-under=85` exécuté avec succès (238 tests en 21s, seuil 85% dépassé).
  - **Mutation Testing (`mutmut`)** : Environnement configuré (`setup.cfg` ciblant `backend` et `bot`), runner pytest hermétique sans dépendances externes.
  - **Linter de sécurité AST (`bandit`)** : `bandit -r backend/ bot/` exécuté — **0 vulnérabilité détectée**.
  - **Analyse sémantique SAST (`semgrep`)** : `semgrep scan --config=auto backend/ bot/` exécuté sur 290 règles — **0 alerte de sécurité**.
  - **Audit des dépendances (`trivy` & `pip-audit`)** : `trivy fs` et `pip-audit` exécutés sur l'environnement complet et `requirements.lock` — **0 vulnérabilité connue, 0 fuite de secret**.

