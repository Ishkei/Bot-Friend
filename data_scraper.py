import asyncio
from playwright.async_api import async_playwright
import os

async def scrape_page_details(page):
    """Scrapes and prints details of questions and answers on the current page."""
    print("\n" + "="*60)
    print("Scraping current page for details...")
    
    try:
        await page.wait_for_load_state('domcontentloaded')
        
        # --- Attempt to find the main question text ---
        # Surveys use different tags for questions (h1, h2, p, span, div). We'll try a few common ones.
        question_selectors = [
            'h1', 'h2', 'h3',
            'div[class*="question"]', 'p[class*="question"]', 'span[class*="question-text"]'
        ]
        
        question_text = "Question not found"
        for selector in question_selectors:
            if await page.locator(selector).first.is_visible(timeout=1000):
                question_text = await page.locator(selector).first.inner_text()
                break
        
        print(f"\nDiscovered Question: {question_text.strip()}")

        # --- Find all potential answers/interactive elements ---
        print("\n[Interactive Elements Found]")
        interactive_elements = await page.locator(
            'label, button, a, input[type="radio"], input[type="checkbox"], textarea'
        ).all()
        
        for element in interactive_elements:
            if await element.is_visible():
                tag = await element.evaluate('node => node.tagName.toLowerCase()')
                text = (await element.inner_text() or await element.get_attribute('aria-label') or "").strip()
                if text:
                    print(f"- <{tag}>: {text}")

        print("="*60)

    except Exception as e:
        print(f"An error occurred during scraping: {e}")

async def main():
    if not os.path.exists('auth.json'):
        print("Authentication file (auth.json) not found. Run 'save_auth.py' first.")
        return

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=False)
        context = await browser.new_context(storage_state="auth.json")
        page = await context.new_page()

        print("Session loaded. Navigating to Qmee surveys...")
        await page.goto("https://www.qmee.com/en-us/surveys")

        print("\nINSTRUCTIONS:")
        print("1. Start a survey in the browser window.")
        print("2. Once a question is displayed, press Enter here to scrape its details.")
        print("3. Answer the question manually in the browser to proceed.")
        print("4. Repeat for as many pages as you want to analyze.")
        print("5. Type 'quit' and press Enter to exit.")

        while True:
            user_input = input("\nPress Enter to scrape the page, or type 'quit' to exit: ")
            if user_input.lower() == 'quit':
                break
            await scrape_page_details(page)

        await browser.close()
        print("\nScraper finished.")

if __name__ == "__main__":
    asyncio.run(main())