import asyncio
import time
import os
from playwright.async_api import async_playwright

TOUCH_SCRIPT = """
(() => {
    function initTouch() {
        if (window.__touchInitialized) return;
        window.__touchInitialized = true;

        const cursor = document.createElement('div');
        cursor.id = 'demo-touch-cursor';
        cursor.style.cssText = `
            position: fixed;
            width: 32px;
            height: 32px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(255,255,255,0.85) 0%, rgba(255,255,255,0.3) 65%, rgba(255,255,255,0.05) 100%);
            border: 2.5px solid rgba(255, 255, 255, 0.95);
            box-shadow: 0 0 18px rgba(255, 255, 255, 0.8), inset 0 0 8px rgba(255, 255, 255, 0.5);
            pointer-events: none;
            z-index: 99999999;
            transform: translate(-50%, -50%) scale(1);
            transition: transform 0.12s ease-out, opacity 0.2s ease;
            opacity: 0;
            left: 207px;
            top: 448px;
        `;
        document.body.appendChild(cursor);

        window.__triggerRipple = function(x, y) {
            cursor.style.opacity = '1';
            cursor.style.left = x + 'px';
            cursor.style.top = y + 'px';
            cursor.style.transform = 'translate(-50%, -50%) scale(0.85)';

            setTimeout(() => {
                cursor.style.transform = 'translate(-50%, -50%) scale(1)';
            }, 140);

            const ripple = document.createElement('div');
            ripple.style.cssText = `
                position: fixed;
                width: 34px;
                height: 34px;
                border-radius: 50%;
                background: rgba(255, 255, 255, 0.5);
                border: 2px solid rgba(255, 255, 255, 0.95);
                box-shadow: 0 0 20px rgba(255, 255, 255, 0.9);
                pointer-events: none;
                z-index: 99999998;
                transform: translate(-50%, -50%) scale(1);
                left: ${x}px;
                top: ${y}px;
                transition: transform 0.45s cubic-bezier(0.1, 0.8, 0.2, 1), opacity 0.45s cubic-bezier(0.1, 0.8, 0.2, 1);
            `;
            document.body.appendChild(ripple);

            requestAnimationFrame(() => {
                ripple.style.transform = 'translate(-50%, -50%) scale(2.6)';
                ripple.style.opacity = '0';
            });

            setTimeout(() => ripple.remove(), 500);
        };

        window.__moveTouch = function(x, y) {
            cursor.style.opacity = '1';
            cursor.style.left = x + 'px';
            cursor.style.top = y + 'px';
        };

        window.__hideTouch = function() {
            cursor.style.opacity = '0';
        };

        window.addEventListener('click', (e) => {
            window.__triggerRipple(e.clientX, e.clientY);
        });
    }

    if (document.body) {
        initTouch();
    } else {
        window.addEventListener('DOMContentLoaded', initTouch);
    }
})();
"""

async def smooth_scroll(page, delta_y, duration_ms=700):
    steps = 18
    step_duration = (duration_ms / 1000) / steps
    step_delta = delta_y / steps
    for _ in range(steps):
        await page.evaluate(f"window.scrollBy(0, {step_delta});")
        await asyncio.sleep(step_duration)

async def tap_loc(page, locator, wait_after=0.4):
    try:
        box = await locator.bounding_box()
        if box:
            cx = box['x'] + box['width'] / 2
            cy = box['y'] + box['height'] / 2
            await page.evaluate(f"window.__triggerRipple({cx}, {cy});")
            await asyncio.sleep(0.12)
        await locator.click()
    except Exception as e:
        print(f"Tap error on locator: {e}")
    await asyncio.sleep(wait_after)

async def tap_coords(page, x, y, wait_after=0.4):
    await page.evaluate(f"window.__triggerRipple({x}, {y});")
    await asyncio.sleep(0.12)
    await page.mouse.click(x, y)
    await asyncio.sleep(wait_after)

async def main():
    print("Starting Playwright Mobile Demo Recording...")
    out_dir = "/home/lesaint/Rendue/chatbot/recordings/session_video"
    os.makedirs(out_dir, exist_ok=True)
    for f in os.listdir(out_dir):
        if f.endswith('.webm'):
            os.remove(os.path.join(out_dir, f))

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--disable-gpu', '--no-sandbox', '--disable-dev-shm-usage']
        )
        context = await browser.new_context(
            viewport={'width': 414, 'height': 896},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
            user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
            record_video_dir=out_dir,
            record_video_size={'width': 828, 'height': 1792}
        )
        page = await context.new_page()
        await page.add_init_script(TOUCH_SCRIPT)

        t0 = time.time()
        def elapsed():
            return time.time() - t0

        async def wait_until(sec):
            remain = sec - elapsed()
            if remain > 0:
                await asyncio.sleep(remain)

        # -------------------------------------------------------------
        # SCENE 1: Accueil Mobile & Infrastructure Souveraine (0 -> 16.8s)
        # -------------------------------------------------------------
        print(f"[{elapsed():.1f}s] SCENE 1: Accueil Mobile...")
        await page.goto('https://chatbot-sigma-rose-10.vercel.app', wait_until='networkidle')
        await wait_until(2.5)

        # Scroll to show performance metrics (< 1 min, 99.98%, Souverain, 24/7)
        print(f"[{elapsed():.1f}s] Scrolling to KPI Bento cards...")
        await smooth_scroll(page, 320, duration_ms=900)
        await wait_until(6.5)

        # Scroll back up to search and interactive pills
        print(f"[{elapsed():.1f}s] Scrolling back to search & popular pills...")
        await smooth_scroll(page, -320, duration_ms=800)
        await wait_until(8.5)

        # Tap on category pill: "Restauration Seed"
        print(f"[{elapsed():.1f}s] Tapping category pill...")
        pill_btn = page.locator('button', has_text="Restauration Seed").first
        await tap_loc(page, pill_btn, wait_after=1.2)

        # Submit search query
        submit_btn = page.locator('button[type="submit"]').first
        await tap_loc(page, submit_btn, wait_after=1.2)

        # Scroll to show instant AI Answer Card
        await smooth_scroll(page, 280, duration_ms=700)
        await wait_until(16.8)

        # -------------------------------------------------------------
        # SCENE 2: Marché Crypto & Données Temps Réel (16.8s -> 32.5s)
        # -------------------------------------------------------------
        print(f"[{elapsed():.1f}s] SCENE 2: Marché Crypto (/crypto)...")
        crypto_tab = page.locator('nav[aria-label] a[href="/crypto"]').first
        await tap_loc(page, crypto_tab, wait_after=1.2)
        await page.wait_for_selector('input[type="text"]', timeout=5000)
        await wait_until(19.5)

        # Scroll through the live crypto list with sparklines
        print(f"[{elapsed():.1f}s] Scrolling crypto list...")
        await smooth_scroll(page, 380, duration_ms=1000)
        await wait_until(23.0)
        await smooth_scroll(page, -380, duration_ms=900)
        await wait_until(25.0)

        # Filter by typing 'ETH'
        print(f"[{elapsed():.1f}s] Filtering crypto search for ETH...")
        search_input = page.locator('input[type="text"]').first
        await tap_loc(page, search_input, wait_after=0.3)
        await search_input.fill('ETH')
        await wait_until(28.5)
        # Clear filter
        await search_input.fill('')
        await wait_until(32.5)

        # -------------------------------------------------------------
        # SCENE 3: Support Desk & Résolution (/tickets) (32.5s -> 47.0s)
        # -------------------------------------------------------------
        print(f"[{elapsed():.1f}s] SCENE 3: Support Desk (/tickets)...")
        tickets_tab = page.locator('nav[aria-label] a[href="/tickets"]').first
        await tap_loc(page, tickets_tab, wait_after=1.2)

        # Switch to '+ Nouveau ticket' mobile tab
        print(f"[{elapsed():.1f}s] Switching to New Ticket form...")
        new_ticket_btn = page.locator('button', has_text="Nouveau").first
        await tap_loc(page, new_ticket_btn, wait_after=1.2)

        # Interact with Category Pills
        print(f"[{elapsed():.1f}s] Selecting technical categories...")
        node_cat = page.locator('form button', has_text="Nœud").first
        await tap_loc(page, node_cat, wait_after=1.2)

        swap_cat = page.locator('form button', has_text="Swap").first
        await tap_loc(page, swap_cat, wait_after=1.2)

        # Scroll to show SLA and secure notice
        await smooth_scroll(page, 240, duration_ms=800)
        await wait_until(43.5)
        await smooth_scroll(page, -240, duration_ms=700)
        await wait_until(45.0)

        # Switch back to tickets list tab
        ticket_list_btn = page.locator('button', has_text="Tickets").first
        await tap_loc(page, ticket_list_btn, wait_after=1.0)
        await wait_until(47.0)

        # -------------------------------------------------------------
        # SCENE 4: Base de Connaissances & FAQ (/knowledge) (47.0s -> 62.5s)
        # -------------------------------------------------------------
        print(f"[{elapsed():.1f}s] SCENE 4: Base de Connaissances (/knowledge)...")
        kb_tab = page.locator('nav[aria-label] a[href="/knowledge"]').first
        await tap_loc(page, kb_tab, wait_after=1.5)

        # Select a category tag filter
        print(f"[{elapsed():.1f}s] Selecting knowledge tag...")
        tag_btn = page.locator('button', has_text="Sécurité").first
        await tap_loc(page, tag_btn, wait_after=1.2)

        # Open an article card
        print(f"[{elapsed():.1f}s] Opening technical guide modal...")
        article_card = page.locator('div[class*="cursor-pointer"]').first
        await tap_loc(page, article_card, wait_after=1.5)

        # View modal content
        await wait_until(57.0)

        # Close the article modal
        close_modal_btn = page.locator('button', has_text="Fermer la fiche").first
        if await close_modal_btn.count() > 0:
            await tap_loc(page, close_modal_btn, wait_after=1.0)
        else:
            await page.keyboard.press("Escape")

        await smooth_scroll(page, 200, duration_ms=700)
        await wait_until(62.5)

        # -------------------------------------------------------------
        # SCENE 5: Menu Drawer, Internationalisation & ROI (62.5s -> 80.0s)
        # -------------------------------------------------------------
        print(f"[{elapsed():.1f}s] SCENE 5: Mobile Drawer & ROI Synthesis...")
        menu_btn = page.locator('nav[aria-label] button', has_text="Menu").first
        await tap_loc(page, menu_btn, wait_after=1.5)

        # Switch language (FR -> EN)
        print(f"[{elapsed():.1f}s] Switching language FR -> EN...")
        lang_btn = page.locator('aside[role="dialog"] button', has_text="FR").first
        if await lang_btn.count() == 0:
            lang_btn = page.locator('button[aria-label*="language"]').first
        await tap_loc(page, lang_btn, wait_after=1.8)

        # Close Drawer
        print(f"[{elapsed():.1f}s] Closing Drawer...")
        close_drawer_btn = page.locator('aside[role="dialog"] button[aria-label*="Fermer"], aside[role="dialog"] button[aria-label*="Close"], aside[role="dialog"] button').first
        await tap_loc(page, close_drawer_btn, wait_after=1.0)

        # Return to Home (Support) for the grand finale
        print(f"[{elapsed():.1f}s] Returning to Home for final brand impression...")
        home_tab = page.locator('nav[aria-label] a[href="/"]').first
        await tap_loc(page, home_tab, wait_after=1.2)
        await smooth_scroll(page, -500, duration_ms=700)

        # Let final ROI pitch resonate on clean sovereign hero
        await wait_until(80.0)
        print(f"[{elapsed():.1f}s] Recording session completed perfectly!")

        await context.close()
        await browser.close()

asyncio.run(main())
