"""Seed the knowledge base with the initial Stack Wallet support content.

Usage:
    python -m scripts.seed_knowledge_base
"""
import asyncio

from backend.database import async_session_maker, init_db
from backend.services.knowledge_base import KnowledgeBaseService

# Each entry: (question, solution, keywords). Keywords cover both FR and EN
# terms so the lexical search matches questions asked in either language.
ARTICLES = [
    (
        "Où puis-je obtenir de l'aide / support Stack Wallet ? / Where can I get Stack Wallet support?",
        # Verified against the live "Support" section of stackwallet.com/index.html#support.
        "Nous proposons du support sur plusieurs canaux. Choisissez celui qui vous convient le mieux :\n"
        "• Email : support@stackwallet.com\n"
        "• Telegram : @stackwallet\n"
        "• Discord : Stack Wallet\n"
        "• Reddit : r/stackwallet\n"
        "• Twitter/X : @stack_wallet\n"
        "• YouTube : Stack Wallet\n"
        "• Session : @stack\n"
        "• Mastodon : @stackwallet\n\n"
        "We offer support on a variety of platforms. Please choose the one below that is most convenient for "
        "you:\n"
        "• Email: support@stackwallet.com\n"
        "• Telegram: @stackwallet\n"
        "• Discord: Stack Wallet\n"
        "• Reddit: r/stackwallet\n"
        "• Twitter/X: @stack_wallet\n"
        "• YouTube: Stack Wallet\n"
        "• Session: @stack\n"
        "• Mastodon: @stackwallet",
        "support, aide, help, contact, canal, channel, online support, support en ligne, telegram, discord, "
        "reddit, twitter, x, youtube, session, mastodon, email, mail",
    ),
    (
        "Qu'est-ce qu'une clé/phrase de récupération (seed) ? / What is a recovery key/phrase/seed?",
        "Ces termes sont utilisés de manière interchangeable et désignent la suite de mots fournie lors de la "
        "création d'un nouveau portefeuille crypto. Elle permet de récupérer et restaurer votre wallet en cas "
        "de perte ou de sinistre. NOTEZ-LA PAR ÉCRIT !\n"
        "These terms, used interchangeably, all refer to the string of words provided to you when you first "
        "set up a new crypto wallet. This is how you recover and restore your wallet in case of loss or "
        "catastrophe. WRITE IT DOWN!",
        "recovery key, seed, phrase, seed phrase, clé de récupération, restauration, restore, backup, sauvegarde",
    ),
    (
        "Comment Stack Wallet gagne-t-il de l'argent ? / How does Stack Wallet make money?",
        "Stack Wallet prélève une petite commission en plus de ses partenaires d'échange tiers pour l'utilisation "
        "de l'échange intégré. Pour l'envoi et la réception standard de crypto-monnaies, tous les frais vont aux "
        "mineurs de la blockchain. Nous ne gagnons PAS d'argent en vendant les données des utilisateurs (voir "
        "notre Politique de confidentialité), ni via des publicités.\n"
        "Stack Wallet charges a tiny fee alongside our third-party exchange providers to utilize the built-in "
        "exchange. But for standard sending and receiving of any cryptocurrency, all fees go to the blockchain "
        "miners. We do NOT make money by selling user data, nor by utilizing ads.",
        "frais, fee, business model, argent, money, commission, publicité, ads, données, privacy",
    ),
    (
        "Comment fonctionne le processus d'échange (exchange) ? / How does the exchange process work?",
        "Stack Wallet s'associe à des fournisseurs d'échange tiers pour tous les échanges ; nous ne réalisons "
        "aucun échange nous-mêmes. Ces tiers sont intégrés à l'application pour une expérience fluide : vous "
        "envoyez vos fonds au fournisseur d'échange tiers, qui vous renvoie ensuite la crypto-monnaie échangée.\n"
        "Stack Wallet partners with third-party exchange providers to do any and all exchanges. We do not do "
        "any exchanges ourselves. These third-parties are built into our app for a seamless experience: you "
        "send your funds to the third-party exchange, who then sends back the coin you are exchanging to.",
        "exchange, échange, swap, third-party, tiers, conversion",
    ),
    (
        "Stack Wallet prend-il en charge plusieurs portefeuilles pour la même crypto-monnaie ? / "
        "Does Stack Wallet support multiple wallets for the same cryptocurrency?",
        "Oui ! Pensez simplement à sauvegarder chaque clé de récupération séparément.\n"
        "We sure do! Just remember to back up each recovery key separately.",
        "multiple wallets, plusieurs portefeuilles, même crypto, recovery key, sauvegarde",
    ),
    (
        "Dois-je quand même noter ma clé de récupération si j'utilise Stack Wallet Backup (SWB) ? / "
        "Do I still need to write down my recovery key if I use Stack Wallet Backup?",
        "Oui. Stack Wallet Backup est une fonctionnalité pratique qui permet de restaurer facilement tous vos "
        "portefeuilles en même temps. Mais la technologie peut échouer : en cas de défaillance de SWB (fichier "
        "corrompu, perdu, etc.), avoir vos seeds notées par écrit garantit l'accès à vos fonds (restauration "
        "manuelle, un portefeuille à la fois).\n"
        "Yes. Stack Wallet Backup is a convenience feature that makes it simple and easy to restore all of your "
        "wallets at once. But sometimes technology fails. In the very unlikely event that SWB does fail (file "
        "corruption, file misplacement, etc.) having your seeds written down ensures you still have access to "
        "your funds. You'll just have to restore them all one at a time.",
        "stack wallet backup, swb, seed, recovery key, backup, sauvegarde",
    ),
    (
        "Stack Wallet Backup fonctionne-t-il avec d'autres portefeuilles ? / "
        "Does Stack Wallet Backup work with other wallets?",
        "Malheureusement non. Il n'existe pas de standard commun pour les sauvegardes de portefeuilles "
        "multi-devises, notamment car la plupart sont closed-source.\n"
        "Unfortunately, no. There is no set standard for multicoin wallet backups. Probably because most of "
        "them are closed-source.",
        "stack wallet backup, swb, interopérabilité, autre wallet, other wallets",
    ),
    (
        "Comment obtenir l'ajout de ma crypto-monnaie préférée sur Stack Wallet ? / "
        "How can I get my coin of choice onto Stack Wallet?",
        "Contactez-nous sur l'un de nos réseaux sociaux. Nous sommes ravis d'échanger avec vous et/ou votre "
        "communauté pour voir ce que nous pouvons faire pour intégrer votre projet à Stack Wallet.\n"
        "Drop us a line on any of our social media accounts. We're happy to talk with you and/or your community "
        "to see what we can do to bring your project to Stack Wallet.",
        "ajouter coin, add coin, nouvelle crypto, new cryptocurrency, listing",
    ),
    (
        "Comment restaurer mon portefeuille ? / How do I restore my wallet?",
        "Si la phrase de récupération unique du portefeuille (seed) a été correctement conservée, la "
        "restauration se fait simplement : sélectionnez « Add New » depuis la page My Stack, indiquez la "
        "crypto-monnaie du portefeuille, puis choisissez « Restore Wallet ». Entrez ensuite le nom souhaité et "
        "la phrase de récupération complète : votre portefeuille réapparaît dans votre Stack !\n"
        "If the wallet's unique recovery phrase (seed) has been stored properly, then restoring your wallet is "
        "as easy as selecting the \"Add New\" option from your My Stack page, letting us know which currency the "
        "wallet holds, and then choosing \"Restore Wallet\" on the following page. Enter your preferred name and "
        "the complete seed phrase you have saved for the wallet, and you will soon see it right back in your "
        "Stack!",
        "restaurer, restore, wallet, add new, restore wallet, seed, phrase de récupération",
    ),
    (
        "Stack Wallet est-il open-source ? / Is Stack Wallet open-source?",
        "Oui, complètement : pas partiellement, pas majoritairement, entièrement open-source. Un code "
        "entièrement ouvert offre sécurité, robustesse et stabilité.\n"
        "Yes, completely — not partially, not mostly, fully open-source. A completely open-source codebase "
        "offers security, power, and stability.",
        "open source, code source, sécurité, security, transparence",
    ),
    (
        "Stack Wallet est-il custodial ? Qui détient mes clés privées ? / "
        "Is Stack Wallet custodial? Who holds my private keys?",
        "Stack Wallet est non-custodial : vos clés privées restent uniquement entre vos mains. Nous ne touchons "
        "jamais à votre argent, nous fournissons seulement la « tirelire » ; vous seul contrôlez ce qu'elle "
        "contient.\n"
        "Stack Wallet is non-custodial. Stack Wallet keeps all private keys in your hands — we never touch "
        "your money. We just make the \"piggybank\", and you control all of the money inside it.",
        "non-custodial, custodial, clés privées, private keys, contrôle des fonds, self custody",
    ),
    (
        "Stack Wallet protège-t-il ma vie privée ? / Does Stack Wallet preserve my privacy?",
        "Oui. Toutes les technologies de confidentialité disponibles dans les crypto-monnaies prises en charge "
        "sont activées par défaut, pour protéger vos fonds des regards indiscrets.\n"
        "Yes. All privacy technologies implemented in the cryptocurrencies we support are turned on by "
        "default, keeping your funds safe from prying eyes.",
        "privacy, vie privée, confidentialité, anonymat, privacy by default",
    ),
    (
        "Quelles crypto-monnaies Stack Wallet prend-il en charge ? / "
        "Which cryptocurrencies does Stack Wallet support?",
        "Vous pouvez envoyer, recevoir et stocker : Monero, Bitcoin, Bitcoin Cash, Firo, Epic Cash, Namecoin, "
        "Wownero, Litecoin et Dogecoin.\n"
        "You can send, receive, and store: Monero, Bitcoin, Bitcoin Cash, Firo, Epic Cash, Namecoin, Wownero, "
        "Litecoin, and Dogecoin.",
        "multicurrency, cryptomonnaies supportées, supported coins, monero, bitcoin, bitcoin cash, firo, "
        "epic cash, namecoin, wownero, litecoin, dogecoin",
    ),
    (
        "L'échange intégré de Stack Wallet permet-il d'échanger des cryptos non supportées par l'app ? / "
        "Can Stack Wallet's built-in exchange trade coins it doesn't natively support?",
        "Oui. Stack Wallet s'est associé à des partenaires reconnus de l'écosystème pour proposer un échange "
        "rapide, sécurisé et simple, y compris pour des crypto-monnaies qui ne sont pas disponibles dans "
        "Stack Wallet elle-même.\n"
        "Yes. We've partnered with some of the best in the ecosystem to exchange your crypto in a quick, "
        "secure, and easy manner — even for cryptos not on Stack Wallet.",
        "built-in exchange, échange intégré, partenaires, exchange partners, coins non supportés",
    ),
    (
        "Comment fonctionne la sauvegarde personnalisée (custom backup) de Stack Wallet ? / "
        "How does Stack Wallet's custom backup work?",
        "Vous pouvez sauvegarder les données de Stack Wallet pour les restaurer facilement ou les transférer "
        "d'un appareil à l'autre, le tout protégé par une technologie de sécurité conçue sur mesure. La "
        "restauration complète de tous vos portefeuilles se fait en deux étapes simples.\n"
        "Back up your Stack Wallet data to easily restore it or transfer it between devices, protected by a "
        "custom-designed secure technology. Custom-made backup lets you safely and securely restore ALL of "
        "your wallets in two easy steps.",
        "custom backup, sauvegarde, restore, transfert appareil, transfer devices, stack wallet backup, swb",
    ),
    (
        "Qu'est-ce que le carnet d'adresses multi-portefeuille ? / What is the multiwallet address book?",
        "Créez plusieurs adresses de crypto-monnaies pour vos contacts et accédez-y facilement pour des "
        "transactions rapides et sans effort. Vous pouvez enregistrer plusieurs adresses sous un même contact "
        "et lui associer un emoji.\n"
        "Create multiple cryptocurrency addresses for your contacts and easily access them for a quick and "
        "painless transaction. Save multiple cryptocurrency addresses under one contact and assign an emoji.",
        "address book, carnet d'adresses, contacts, multiwallet, emoji",
    ),
    (
        "À quoi sert la fonctionnalité « Favorite wallets » ? / What does the Favorite wallets feature do?",
        "Lorsque vous avez plusieurs portefeuilles dans un même Stack, cette fonctionnalité vous permet de "
        "mettre en avant ceux que vous utilisez le plus (activable/désactivable).\n"
        "With many wallets in one Stack, the Favorites feature lets you give extra attention to the ones you "
        "use most (toggle it on or off).",
        "favorite wallets, portefeuilles favoris, favoris, toggle",
    ),
    (
        "Comment Stack Wallet se connecte-t-il aux nœuds du réseau ? / "
        "How does Stack Wallet connect to network nodes?",
        "Stack Wallet se connecte automatiquement à ses propres nœuds pour une expérience fluide, mais vous "
        "pouvez aussi choisir votre propre nœud.\n"
        "Auto connect to our nodes for a seamless experience, or choose your own!",
        "node, nœud, custom node, connexion réseau",
    ),
    (
        "Qu'est-ce que le « smart sync » de Stack Wallet ? / What is Stack Wallet's smart sync?",
        "Le smart sync vous permet de synchroniser avec la blockchain au moment qui vous convient, ce qui "
        "réduit les temps d'attente avant de pouvoir utiliser vos coins.\n"
        "Smart sync lets you sync to the blockchain when it's convenient for you, minimizing wait times before "
        "using your coins.",
        "smart sync, synchronisation, sync, temps d'attente, wait time",
    ),
    (
        "Stack Wallet propose-t-il un support testnet ? / Does Stack Wallet support testnet?",
        "Oui, la plupart des coins pris en charge disposent aussi de leur alternative testnet ; il suffit "
        "d'activer le mode avancé.\n"
        "Most coins we support come with their testnet alternatives too. Simply enter advanced mode.",
        "testnet, mode avancé, advanced mode",
    ),
    (
        "Stack Wallet prend-il en charge SegWit pour Bitcoin ? / Does Stack Wallet support SegWit for Bitcoin?",
        "Oui, Bitcoin utilise automatiquement la technologie SegWit dans Stack Wallet, ce qui permet de réduire "
        "les frais de transaction.\n"
        "Bitcoin uses SegWit technology automatically, saving you on fees.",
        "segwit, bitcoin, frais, fees",
    ),
    (
        "Qu'est-ce que la technologie « Post » utilisée pour les coins Mimblewimble ? / "
        "What is the \"Post\" technology used for Mimblewimble coins?",
        "Les coins basés sur Mimblewimble (comme Epic Cash) utilisent la technologie Post, qui simplifie "
        "l'envoi et la réception en une opération unique et fluide, là où ce processus est habituellement "
        "plus contraignant.\n"
        "Mimblewimble coins utilize Post technology, turning the painful sending and receiving process into a "
        "simple, one-and-done affair.",
        "post technology, mimblewimble, epic cash, envoi réception, sending receiving",
    ),
]

# Questions from earlier revisions of this script that have since been merged
# into another entry above (rather than kept as a near-duplicate). Removed
# here so re-running the script also cleans up an already-seeded database.
RETIRED_QUESTIONS = [
    "Quels sont les canaux de support en ligne de Stack Wallet ? / "
    "What are Stack Wallet's online support channels?",
]


async def main() -> None:
    await init_db()
    async with async_session_maker() as session:
        for question in RETIRED_QUESTIONS:
            article = await KnowledgeBaseService.get_article_by_question(session, question.strip())
            if article:
                await KnowledgeBaseService.delete_article(session, article)
                print(f"Deleted retired article #{article.id}: {question[:60]}...")

        for question, solution, keywords in ARTICLES:
            article = await KnowledgeBaseService.get_article_by_question(session, question.strip())
            if article is None:
                article = await KnowledgeBaseService.add_article(
                    session=session,
                    question=question,
                    solution=solution,
                    keywords=keywords,
                )
                print(f"Added article #{article.id}: {article.question[:60]}...")
            elif article.solution.strip() != solution.strip() or (article.keywords or "").strip() != keywords.strip():
                await KnowledgeBaseService.update_article(
                    session=session, article=article, solution=solution, keywords=keywords
                )
                print(f"Updated article #{article.id}: {article.question[:60]}...")
            else:
                print(f"Unchanged: {question[:60]}...")


if __name__ == "__main__":
    asyncio.run(main())
