import asyncio
import os
import subprocess
from playwright.async_api import async_playwright


# 2. Scene definitions
scenes = [
    {
        "id": "scene1",
        "duration": 16.8,
        "badge": "01 / ÉCOSYSTÈME SOUVERAIN & MINI APP",
        "title": "Support Mobile Natif & Architecture Haute Disponibilité",
        "desc": "Une expérience de support instantanée, intégrée directement dans Telegram. Conçue pour automatiser les requêtes, rassurer les utilisateurs et éliminer les points de friction 24h/24.",
        "bento": [
            ("Vitesse", "< 1 min", "Temps moyen de prise en charge et de réponse qualifiée"),
            ("Fiabilité", "99.98%", "Disponibilité garantie avec bascule automatique de secours"),
            ("Sécurité", "100%", "Architecture non-custodiale respectueuse de la vie privée")
        ],
        "subtitle": "« Bienvenue dans la démonstration de notre <span class='highlight'>WebApp mobile de support souverain</span>. Conçue pour une expérience native ultra-fluide, elle garantit un <span class='highlight'>temps de réponse inférieur à une minute</span> et une disponibilité de plus de 99,98 %. »",
        "accent": "#38bdf8",
        "glow": "rgba(56, 189, 248, 0.2)"
    },
    {
        "id": "scene2",
        "duration": 15.7,
        "badge": "02 / HUB FINANCIER & DONNÉES TEMPS RÉEL",
        "title": "Marché Crypto en Direct & Suivi d'Actifs 24/7",
        "desc": "Accès direct aux cours mondiaux et métriques de liquidité on-chain. Gardez vos utilisateurs engagés au sein d'une seule interface unifiée, résiliente et sécurisée.",
        "bento": [
            ("Portfolio", "100+ Actifs", "Couverture exhaustive des cryptomonnaies majeures et privées"),
            ("Résilience", "0 Coupure", "Architecture de cache d'urgence avec tolérance aux pannes API"),
            ("Rétention", "+45% In-App", "Fidélisation accrue des investisseurs dans votre écosystème")
        ],
        "subtitle": "« Depuis la barre de navigation tactile, accédez au <span class='highlight'>marché crypto en direct</span>. Avec le suivi en temps réel de plus de cent actifs, des graphiques instantanés et un moteur de recherche ultrarapide, <span class='highlight'>maximisez la rétention utilisateur</span>. »",
        "accent": "#10b981",
        "glow": "rgba(16, 185, 129, 0.2)"
    },
    {
        "id": "scene3",
        "duration": 14.5,
        "badge": "03 / DESK TECHNIQUE & RÉSOLUTION HYBRIDE",
        "title": "Guichet de Tickets Intelligent & Routage Dual",
        "desc": "Gestion complète des demandes d'assistance avec pré-qualification automatique par IA et transmission fluide vers vos ingénieurs de support.",
        "bento": [
            ("SLA Garanti", "< 15 min", "Traitement prioritaire selon la sévérité technique de la demande"),
            ("Routage Dual", "Groupe & DM", "Réponse citée dans le groupe public ET confirmation en privé"),
            ("Qualification", "IA Instant", "Catégorisation assistée (seed, nœuds RPC, transactions mémopool)")
        ],
        "subtitle": "« Le Desk de Support gère l'ensemble du cycle de résolution. Restauration de seed phrase, synchronisation de nœuds distants ou swaps : <span class='highlight'>notre moteur qualifie chaque demande</span> avec précision pour un <span class='highlight'>routage hybride intelligent</span>. »",
        "accent": "#a855f7",
        "glow": "rgba(168, 85, 247, 0.2)"
    },
    {
        "id": "scene4",
        "duration": 15.5,
        "badge": "04 / BASE DE CONNAISSANCES & AUTO-APPRENTISSAGE",
        "title": "Procédures Techniques Certifiées & Documentation",
        "desc": "Une bibliothèque dynamique de résolutions vérifiées qui enrichit automatiquement ses réponses pour supprimer le travail répétitif de vos équipes.",
        "bento": [
            ("Économie", "-70% Coûts", "Réduction drastique des coûts d'assistance opérationnelle"),
            ("Certifié", "100% Validé", "Guides rédigés et vérifiés par des experts en sécurité crypto"),
            ("Self-Service", "Autonomie", "Résolution immédiate sans attente pour l'utilisateur final")
        ],
        "subtitle": "« La base de connaissances interactive met à disposition des guides techniques vérifiés et consultables instantanément. En automatisant les résolutions récurrentes, votre entreprise <span class='highlight'>réduit ses coûts de support de plus de 70 %</span>. »",
        "accent": "#f59e0b",
        "glow": "rgba(245, 158, 11, 0.2)"
    },
    {
        "id": "scene5",
        "duration": 17.5,
        "badge": "05 / EXPANSION & AVANTAGE CONCURRENTIEL",
        "title": "Console Multilingue, Sécurité & Rentabilité ROI",
        "desc": "Un écosystème conçu pour scaler votre communauté à l'international, protéger vos secrets et transformer l'expérience client en un levier d'acquisition.",
        "bento": [
            ("International", "FR & EN", "Bascule linguistique en un clic pour une portée mondiale"),
            ("Souveraineté", "Zéro Fuite", "Conformité stricte, contrôle d'accès IDOR et chiffrement fort"),
            ("Rentabilité", "ROI ×4", "Amortissement immédiat et valorisation de votre image de marque")
        ],
        "subtitle": "« Grâce au menu latéral ergonomique, basculez en un geste entre le français et l'anglais, tout en surveillant la connectivité du réseau. Une solution clé en main, conçue pour <span class='highlight'>transformer votre support client en avantage concurrentiel</span>. »",
        "accent": "#38bdf8",
        "glow": "rgba(56, 189, 248, 0.2)"
    }
]

def render_html(s):
    bento_html = ""
    for label, metric, sub in s["bento"]:
        bento_html += f"""
        <div class='bento-card'>
          <div class='bento-label' style='color:{s["accent"]};'>{label}</div>
          <div class='bento-metric'>{metric}</div>
          <div class='bento-sub'>{sub}</div>
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset='utf-8'>
    <style>
      * {{ box-sizing: border-box; margin: 0; padding: 0; }}
      body {{
        width: 1920px;
        height: 1080px;
        background: radial-gradient(circle at 15% 30%, #161824 0%, #0a0b10 60%, #050608 100%);
        font-family: 'DejaVu Sans', 'Liberation Sans', sans-serif;
        color: #ffffff;
        position: relative;
        overflow: hidden;
      }}
      .glow-1 {{
        position: absolute;
        width: 650px;
        height: 650px;
        background: radial-gradient(circle, {s["glow"]} 0%, rgba(0,0,0,0) 70%);
        top: -120px;
        left: -120px;
        border-radius: 50%;
        filter: blur(50px);
      }}
      .glow-2 {{
        position: absolute;
        width: 500px;
        height: 500px;
        background: radial-gradient(circle, rgba(255,255,255,0.04) 0%, rgba(0,0,0,0) 70%);
        bottom: -50px;
        right: 400px;
        border-radius: 50%;
        filter: blur(50px);
      }}
      .grid-bg {{
        position: absolute;
        inset: 0;
        background-image: 
          linear-gradient(to right, rgba(255,255,255,0.03) 1px, transparent 1px),
          linear-gradient(to bottom, rgba(255,255,255,0.03) 1px, transparent 1px);
        background-size: 60px 60px;
      }}
      .layout {{
        position: relative;
        z-index: 10;
        display: flex;
        width: 1920px;
        height: 1080px;
        padding: 65px 85px;
        justify-content: space-between;
      }}
      .left-col {{
        width: 1120px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
      }}
      .header-badge {{
        display: inline-flex;
        align-items: center;
        gap: 10px;
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.2);
        padding: 8px 18px;
        border-radius: 9999px;
        font-size: 14px;
        font-weight: 700;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        color: #e2e8f0;
        width: fit-content;
      }}
      .header-badge .dot {{
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: {s["accent"]};
        box-shadow: 0 0 10px {s["accent"]};
      }}
      .scene-title {{
        font-size: 50px;
        font-weight: 800;
        line-height: 1.15;
        margin-top: 18px;
        background: linear-gradient(135deg, #ffffff 0%, #cbd5e1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
      }}
      .scene-desc {{
        font-size: 20px;
        color: #94a3b8;
        line-height: 1.5;
        margin-top: 14px;
        max-width: 950px;
      }}
      .bento-grid {{
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 20px;
        margin-top: 32px;
      }}
      .bento-card {{
        background: rgba(18, 20, 29, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 20px;
        padding: 24px;
        backdrop-filter: blur(16px);
      }}
      .bento-metric {{
        font-size: 38px;
        font-weight: 800;
        color: #ffffff;
        margin-top: 8px;
      }}
      .bento-label {{
        font-size: 15px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
      }}
      .bento-sub {{
        font-size: 14px;
        color: #94a3b8;
        margin-top: 6px;
        line-height: 1.4;
      }}
      .subtitles-box {{
        background: rgba(15, 17, 26, 0.9);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 18px;
        padding: 20px 28px;
        display: flex;
        align-items: center;
        gap: 20px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6);
        backdrop-filter: blur(20px);
      }}
      .voice-indicator {{
        display: flex;
        align-items: center;
        gap: 4px;
        height: 24px;
      }}
      .voice-bar {{
        width: 4px;
        border-radius: 2px;
        background: {s["accent"]};
      }}
      .voice-bar:nth-child(1) {{ height: 12px; }}
      .voice-bar:nth-child(2) {{ height: 22px; }}
      .voice-bar:nth-child(3) {{ height: 16px; }}
      .voice-bar:nth-child(4) {{ height: 8px; }}
      .subtitle-text {{
        font-size: 18px;
        font-weight: 500;
        color: #f8fafc;
        line-height: 1.45;
      }}
      .subtitle-text span.highlight {{
        color: {s["accent"]};
        font-weight: 700;
      }}
      .right-col {{
        width: 480px;
        display: flex;
        justify-content: center;
        align-items: center;
      }}
      .phone-frame {{
        width: 440px;
        height: 924px;
        border-radius: 54px;
        background: #1e2029;
        border: 3.5px solid #3b3f52;
        box-shadow: 
          0 0 0 1px #0a0b10,
          0 30px 80px rgba(0, 0, 0, 0.9),
          0 0 60px {s["glow"]};
        position: relative;
        padding: 14px;
      }}
      .phone-screen-window {{
        width: 414px;
        height: 896px;
        border-radius: 42px;
        background: #000000;
        overflow: hidden;
        position: relative;
      }}
      .dynamic-island {{
        position: absolute;
        top: 12px;
        left: 50%;
        transform: translateX(-50%);
        width: 120px;
        height: 32px;
        background: #000000;
        border-radius: 20px;
        z-index: 999;
      }}
    </style>
    </head>
    <body>
      <div class='glow-1'></div>
      <div class='glow-2'></div>
      <div class='grid-bg'></div>
      
      <div class='layout'>
        <div class='left-col'>
          <div>
            <div class='header-badge'>
              <div class='dot'></div>
              {s["badge"]}
            </div>
            <h1 class='scene-title'>{s["title"]}</h1>
            <p class='scene-desc'>{s["desc"]}</p>

            <div class='bento-grid'>
              {bento_html}
            </div>
          </div>

          <div class='subtitles-box'>
            <div class='voice-indicator'>
              <div class='voice-bar'></div>
              <div class='voice-bar'></div>
              <div class='voice-bar'></div>
              <div class='voice-bar'></div>
            </div>
            <div class='subtitle-text'>
              {s["subtitle"]}
            </div>
          </div>
        </div>

        <div class='right-col'>
          <div class='phone-frame'>
            <div class='dynamic-island'></div>
            <div class='phone-screen-window'></div>
          </div>
        </div>
      </div>
    </body>
    </html>
    """

async def generate_slides():
    os.makedirs("slides_yt", exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        for s in scenes:
            html = render_html(s)
            await page.set_content(html)
            path = f"slides_yt/{s['id']}.png"
            await page.screenshot(path=path)
            print(f"Generated {path}")
        await browser.close()

asyncio.run(generate_slides())
