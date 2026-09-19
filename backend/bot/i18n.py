import logging

logger = logging.getLogger(__name__)

DEFAULT_LANGUAGE = "fr"
SUPPORTED_LANGUAGES = ("fr", "en")

# {key: {"fr": ..., "en": ...}} for the messages the bot writes to users.
# `{placeholder}` tokens are filled with str.format in t().
TRANSLATIONS = {
    # --- user_handlers.py ---
    "welcome": {
        "fr": (
            "👋 **Bonjour et bienvenue sur notre service de support automatisé !**\n\n"
            "Posez-moi simplement votre question dans ce chat, et je chercherai immédiatement "
            "la solution la plus adaptée dans notre base de connaissances.\n\n"
            "Si la réponse ne vous convient pas, vous pourrez transférer votre demande "
            "à notre équipe humaine en un clic !"
        ),
        "en": (
            "👋 **Hello and welcome to our automated support service!**\n\n"
            "Just ask your question in this chat, and I'll immediately look for "
            "the best-matching solution in our knowledge base.\n\n"
            "If the answer doesn't suit you, you'll be able to forward your request "
            "to our human team with one click!"
        ),
    },
    "help": {
        "fr": (
            "ℹ️ **Aide**\n\n"
            "- Envoyez votre message texte décrivant votre problème.\n"
            "- Après réception de la réponse, cliquez sur **OUI** si votre problème est résolu, "
            "ou sur **NON** pour créer automatiquement un ticket auprès de notre équipe support."
        ),
        "en": (
            "ℹ️ **Help**\n\n"
            "- Send a text message describing your issue.\n"
            "- After receiving the answer, click **YES** if your problem is resolved, "
            "or **NO** to automatically create a ticket with our support team."
        ),
    },
    "button_yes": {"fr": "✅ OUI", "en": "✅ YES"},
    "button_no": {"fr": "❌ NON", "en": "❌ NO"},
    "button_webapp": {
        "fr": "📱 Centre d'Assistance Stack",
        "en": "📱 Stack Support Center",
    },
    "button_open_webapp": {
        "fr": "📱 Ouvrir l'Application Support",
        "en": "📱 Open the Support App",
    },
    "webapp_prompt": {
        "fr": "Accédez au centre d'assistance officiel Stack Wallet :",
        "en": "Open the official Stack Wallet support center:",
    },
    "webapp_not_configured": {
        "fr": "L'URL de la WebApp n'est pas encore configurée dans le fichier `.env` (variable `TELEGRAM_WEBAPP_URL`).",
        "en": "The WebApp URL is not configured yet in the `.env` file (`TELEGRAM_WEBAPP_URL` variable).",
    },
    "question_too_long": {
        "fr": "⚠️ Votre question est trop longue (maximum {max_length} caractères). Veuillez raccourcir votre message et réessayer.",
        "en": "⚠️ Your question is too long (maximum {max_length} characters). Please shorten your message and try again.",
    },
    "query_backend_error": {
        "fr": "⚠️ Une erreur est survenue lors de la communication avec le serveur. Veuillez réessayer ultérieurement.",
        "en": "⚠️ An error occurred while communicating with the server. Please try again later.",
    },
    "answer_prompt": {
        "fr": "🤖 **Réponse :**\n\n{answer}\n\n━━━━━━━━━━━━━━━━━━━\n❓ **Votre problème est-il résolu ?**",
        "en": "🤖 **Answer:**\n\n{answer}\n\n━━━━━━━━━━━━━━━━━━━\n❓ **Is your problem resolved?**",
    },
    "resolved_notice": {
        "fr": "{base_text}\n\n✅ **Statut : Problème résolu.**\nMerci d'avoir utilisé notre service support ! N'hésitez pas si vous avez d'autres questions. 👋",
        "en": "{base_text}\n\n✅ **Status: Problem resolved.**\nThank you for using our support service! Feel free to reach out if you have other questions. 👋",
    },
    "resolve_yes_ack": {
        "fr": "Merci pour votre retour !",
        "en": "Thank you for your feedback!",
    },
    "ticket_already_handled": {
        "fr": "Cette demande a déjà été prise en compte.",
        "en": "This request has already been handled.",
    },
    "ticket_created_ack": {
        "fr": "Ticket créé !",
        "en": "Ticket created!",
    },
    "ticket_escalated_notice": {
        "fr": "{base_text}\n\n🎟️ **Ticket #{ticket_id} créé et escaladé.**\nNotre équipe support a été notifiée et vous répondra directement ici dès qu'un agent aura pris en charge votre demande.",
        "en": "{base_text}\n\n🎟️ **Ticket #{ticket_id} created and escalated.**\nOur support team has been notified and will reply to you directly here as soon as an agent takes on your request.",
    },
    "ticket_creation_error": {
        "fr": "Erreur lors de la création du ticket",
        "en": "Error creating the ticket",
    },

    # --- support_handlers.py ---
    "support_no_matching_ticket": {
        "fr": "⚠️ Je n'ai pas pu associer ce message à un ticket. Répondez directement au message de la carte du ticket pour le résoudre.",
        "en": "⚠️ I couldn't match this message to a ticket. Reply directly to the ticket card message to resolve it.",
    },
    "support_voice_transcribed": {
        "fr": "🎙️ Message vocal transcrit automatiquement :\n\n_{transcribed}_",
        "en": "🎙️ Voice message automatically transcribed:\n\n_{transcribed}_",
    },
    "support_no_text_content": {
        "fr": "⚠️ Je ne peux résoudre un ticket qu'à partir d'un texte (ou d'une légende, ou d'un vocal transcrit automatiquement si l'IA OpenAI est configurée). Réécrivez votre solution en texte, ou ajoutez-la en légende de votre média.",
        "en": "⚠️ I can only resolve a ticket from text (or a caption, or an automatically transcribed voice message if OpenAI AI is configured). Rewrite your solution as text, or add it as your media's caption.",
    },
    "support_already_resolved": {
        "fr": "ℹ️ **Ticket #{ticket_id} déjà résolu !**\nCe ticket a déjà été résolu par *{resolved_by}*.\nVotre réponse n'a pas été renvoyée à l'utilisateur pour éviter les doublons.",
        "en": "ℹ️ **Ticket #{ticket_id} already resolved!**\nThis ticket was already resolved by *{resolved_by}*.\nYour reply was not sent to the user to avoid duplicates.",
    },
    "support_user_notification": {
        "fr": "📬 **Réponse de l'équipe support (Ticket #{ticket_id})**\n\n{solution}\n\n━━━━━━━━━━━━━━━━━━━\nTraité par : *{agent}*\nMerci de votre confiance ! 👋",
        "en": "📬 **Reply from the support team (Ticket #{ticket_id})**\n\n{solution}\n\n━━━━━━━━━━━━━━━━━━━\nHandled by: *{agent}*\nThank you for your trust! 👋",
    },
    "support_resolved_confirmation": {
        "fr": "✅ **Ticket #{ticket_id} résolu !**\n• La réponse a été transmise à l'utilisateur (`ID: {user_id}`).\n• La solution a été automatiquement intégrée dans la base de connaissances.",
        "en": "✅ **Ticket #{ticket_id} resolved!**\n• The reply was forwarded to the user (`ID: {user_id}`).\n• The solution was automatically added to the knowledge base.",
    },
    "support_resolution_error": {
        "fr": "❌ **Erreur lors de la résolution du ticket #{ticket_id}** (voir les logs pour le détail).",
        "en": "❌ **Error resolving ticket #{ticket_id}** (see logs for details).",
    },

    # --- community_handlers.py ---
    "community_mention_fallback": {
        "fr": "Utilisateur {user_id}",
        "en": "User {user_id}",
    },
    "community_ask_usage": {
        "fr": "ℹ️ Utilisation : `/ask votre question`",
        "en": "ℹ️ Usage: `/ask your question`",
    },
    "community_answer_prompt": {
        "fr": "{mention}\n\n🤖 **Réponse :**\n\n{answer}\n\n━━━━━━━━━━━━━━━━━━━\n❓ **Votre problème est-il résolu ?**",
        "en": "{mention}\n\n🤖 **Answer:**\n\n{answer}\n\n━━━━━━━━━━━━━━━━━━━\n❓ **Is your problem resolved?**",
    },
    "community_resolved_notice": {
        "fr": "{base_text}\n\n✅ **Statut : Problème résolu.**\nMerci d'avoir utilisé notre service support ! 👋",
        "en": "{base_text}\n\n✅ **Status: Problem resolved.**\nThank you for using our support service! 👋",
    },
    "community_resolution_expired": {
        "fr": "⏱️ Ce délai de confirmation a expiré.",
        "en": "⏱️ This confirmation window has expired.",
    },
    "community_ticket_ack": {
        "fr": "{base_text}\n\n🎟️ **Ticket ouvert.**\nNotre équipe support a été notifiée et reviendra vers vous directement.",
        "en": "{base_text}\n\n🎟️ **Ticket opened.**\nOur support team has been notified and will get back to you directly.",
    },
    "community_purge_not_admin": {
        "fr": "⛔ Seuls les administrateurs du groupe peuvent utiliser /purge.",
        "en": "⛔ Only group administrators can use /purge.",
    },
    "community_purge_result": {
        "fr": "🧹 {deleted} message(s) supprimé(s).",
        "en": "🧹 {deleted} message(s) deleted.",
    },

    # --- moderation_handlers.py ---
    "moderation_not_admin": {
        "fr": "⛔ Seuls les administrateurs du groupe peuvent utiliser cette commande.",
        "en": "⛔ Only group administrators can use this command.",
    },
    "moderation_no_target": {
        "fr": "⚠️ Indiquez la cible en répondant à son message, ou en donnant son ID Telegram en premier argument (ex : `/mute 123456789 3600`).",
        "en": "⚠️ Specify the target by replying to their message, or by giving their Telegram ID as the first argument (e.g. `/mute 123456789 3600`).",
    },
    "moderation_mute_error": {
        "fr": "❌ Impossible de mute cet utilisateur (voir les logs pour le détail).",
        "en": "❌ Could not mute this user (see logs for details).",
    },
    "moderation_mute_success": {
        "fr": "🔇 *{name}* a été mute {duration_text}.",
        "en": "🔇 *{name}* has been muted {duration_text}.",
    },
    "moderation_mute_duration_seconds": {
        "fr": "pendant {seconds} secondes",
        "en": "for {seconds} seconds",
    },
    "moderation_mute_indefinite": {
        "fr": "indéfiniment",
        "en": "indefinitely",
    },
    "moderation_unmute_error": {
        "fr": "❌ Impossible de unmute cet utilisateur (voir les logs pour le détail).",
        "en": "❌ Could not unmute this user (see logs for details).",
    },
    "moderation_unmute_success": {
        "fr": "🔊 *{name}* a été unmute.",
        "en": "🔊 *{name}* has been unmuted.",
    },
    "moderation_ban_error": {
        "fr": "❌ Impossible de bannir cet utilisateur (voir les logs pour le détail).",
        "en": "❌ Could not ban this user (see logs for details).",
    },
    "moderation_ban_success": {
        "fr": "🚫 *{name}* a été banni du groupe.",
        "en": "🚫 *{name}* has been banned from the group.",
    },
    "moderation_kick_error": {
        "fr": "❌ Impossible d'expulser cet utilisateur (voir les logs pour le détail).",
        "en": "❌ Could not kick this user (see logs for details).",
    },
    "moderation_kick_success": {
        "fr": "👢 *{name}* a été expulsé du groupe (peut revenir).",
        "en": "👢 *{name}* has been kicked from the group (can rejoin).",
    },
    "moderation_warn_error": {
        "fr": "❌ Impossible d'enregistrer l'avertissement (voir les logs pour le détail).",
        "en": "❌ Could not record the warning (see logs for details).",
    },
    "moderation_warn_success": {
        "fr": "⚠️ *{name}* a reçu un avertissement{reason_text}. Total : {total}.",
        "en": "⚠️ *{name}* received a warning{reason_text}. Total: {total}.",
    },

    # --- crypto_handlers.py ---
    "crypto_unavailable": {
        "fr": "⚠️ Les données de marché sont temporairement indisponibles. Réessayez dans quelques instants.",
        "en": "⚠️ Market data is temporarily unavailable. Please try again shortly.",
    },
    "crypto_unrecognized_asset": {
        "fr": "❓ Actif « {symbol} » non reconnu.",
        "en": "❓ Asset \"{symbol}\" not recognized.",
    },
    "crypto_price_reply": {
        "fr": "💰 **{symbol}**\nPrix : ${price:,.2f}\n{arrow} 24h : {change:+.2f}%\nCapitalisation : ${market_cap:,.0f}\nVolume 24h : ${volume:,.0f}",
        "en": "💰 **{symbol}**\nPrice: ${price:,.2f}\n{arrow} 24h: {change:+.2f}%\nMarket cap: ${market_cap:,.0f}\n24h volume: ${volume:,.0f}",
    },

    # --- setup_handlers.py ---
    "setup_not_owner": {
        "fr": "⛔ Seul le propriétaire du bot peut gérer la liste blanche des administrateurs.",
        "en": "⛔ Only the bot owner can manage the admin whitelist.",
    },
    "setup_not_authorized": {
        "fr": "⛔ Vous n'êtes pas autorisé à effectuer cette action.",
        "en": "⛔ You are not authorized to perform this action.",
    },
    "setup_whitelist_usage": {
        "fr": "ℹ️ Utilisation : `/whitelist add <user_id>` ou `/whitelist remove <user_id>`.",
        "en": "ℹ️ Usage: `/whitelist add <user_id>` or `/whitelist remove <user_id>`.",
    },
    "setup_whitelist_add_error": {
        "fr": "❌ Impossible d'ajouter {user_id} à la liste blanche.",
        "en": "❌ Could not add {user_id} to the whitelist.",
    },
    "setup_whitelist_added": {
        "fr": "✅ Utilisateur `{user_id}` ajouté à la liste blanche.",
        "en": "✅ User `{user_id}` added to the whitelist.",
    },
    "setup_whitelist_remove_error": {
        "fr": "❌ Impossible de retirer {user_id} de la liste blanche.",
        "en": "❌ Could not remove {user_id} from the whitelist.",
    },
    "setup_whitelist_removed": {
        "fr": "✅ Utilisateur `{user_id}` retiré de la liste blanche.",
        "en": "✅ User `{user_id}` removed from the whitelist.",
    },
    "setup_whitelist_not_present": {
        "fr": "ℹ️ Utilisateur `{user_id}` n'était pas dans la liste blanche.",
        "en": "ℹ️ User `{user_id}` was not on the whitelist.",
    },
    "setup_community_group_usage": {
        "fr": "ℹ️ Lancez `/setup_community` directement dans le groupe que vous voulez définir comme groupe communautaire.",
        "en": "ℹ️ Run `/setup_community` directly in the group you want to set as the community group.",
    },
    "setup_community_group_error": {
        "fr": "❌ Impossible d'enregistrer ce groupe comme groupe communautaire.",
        "en": "❌ Could not save this group as the community group.",
    },
    "setup_community_group_success": {
        "fr": "✅ Ce groupe est désormais le groupe communautaire actif. Les commandes /ask, /purge et de modération s'y appliquent maintenant.",
        "en": "✅ This group is now the active community group. The /ask, /purge, and moderation commands now apply here.",
    },
    "setup_tutorial": {
        "fr": (
            "👋 **Bienvenue !** Aucun groupe communautaire n'est encore configuré pour ce bot.\n\n"
            "Pour le configurer :\n"
            "1. Ajoutez ce bot comme **administrateur** dans le groupe Telegram que vous voulez utiliser comme groupe "
            "communautaire (avec les droits : restreindre les membres, bannir/débannir, supprimer des messages).\n"
            "2. Dans ce groupe, envoyez la commande `/setup_community`.\n"
            "3. C'est prêt ! Les membres peuvent poser leurs questions avec `/ask`, et vous disposez des commandes "
            "`/mute`, `/unmute`, `/ban`, `/kick`, `/warn` et `/purge`.\n\n"
            "Vous pourrez relancer `/setup_community` à tout moment pour changer de groupe communautaire."
        ),
        "en": (
            "👋 **Welcome!** No community group is configured for this bot yet.\n\n"
            "To configure it:\n"
            "1. Add this bot as an **administrator** in the Telegram group you want to use as the community "
            "group (with rights to: restrict members, ban/unban, delete messages).\n"
            "2. In that group, send the `/setup_community` command.\n"
            "3. You're all set! Members can ask questions with `/ask`, and you have the "
            "`/mute`, `/unmute`, `/ban`, `/kick`, `/warn`, and `/purge` commands available.\n\n"
            "You can run `/setup_community` again at any time to change the active community group."
        ),
    },
    "setup_language_usage": {
        "fr": "ℹ️ Utilisation : `/language fr` ou `/language en`.",
        "en": "ℹ️ Usage: `/language fr` or `/language en`.",
    },
    "setup_language_changed": {
        "fr": "✅ Langue du bot définie sur : {language}.",
        "en": "✅ Bot language set to: {language}.",
    },
}


def t(key: str, lang: str = DEFAULT_LANGUAGE, **kwargs) -> str:
    """
    Translation of `key` in `lang`, with `{placeholders}` filled from kwargs.

    Never raises: an unknown language falls back to French, and a missing key or a bad placeholder
    is logged as a warning and returns the bare key or the unformatted text.
    """
    entry = TRANSLATIONS.get(key)
    if entry is None:
        logger.warning("Missing i18n key: %s", key)
        return key

    text = entry.get(lang) or entry.get(DEFAULT_LANGUAGE) or key
    if not kwargs:
        return text
    try:
        return text.format(**kwargs)
    except (KeyError, IndexError) as exc:
        logger.warning("i18n formatting error for key %s: %s", key, exc)
        return text
