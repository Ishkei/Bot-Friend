import asyncio
import google.generativeai as genai
from playwright.async_api import async_playwright
import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "YOUR_GOOGLE_API_KEY")
if not GOOGLE_API_KEY or GOOGLE_API_KEY == "YOUR_GOOGLE_API_KEY":
    print("ERROR: GOOGLE_API_KEY not found in .env file. Please set it.")
    exit()
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash-latest')

# --- PERSONA LOADING ---
try:
    with open('persona.json', 'r') as f:
        PERSONA = json.load(f)
    PERSONA_PROMPT = f"You are an AI assistant representing a person with these details: {json.dumps(PERSONA)}. Answer survey questions consistently. Be concise."
except FileNotFoundError:
    print("Error: persona.json not found! Please create it.")
    exit()

async def solve_with_hybrid_model(page):
    print("Handling page with Hybrid Vision/Scraping Model...")
    try:
        await asyncio.sleep(1)
        screenshot = await page.screenshot(type="png", full_page=True)
        interactive_elements = await page.locator('button, a, input, textarea, select, label').all()
        element_map = {}
        clean_elements_text = "[START of Interactive Elements]\n"
        for i, element in enumerate(interactive_elements):
            if await element.is_visible():
                text = (await element.inner_text() or await element.get_attribute('aria-label') or await element.get_attribute('placeholder') or "").strip()
                tag = await element.evaluate('node => node.tagName.toLowerCase()')
                if text and len(text) > 1:
                    element_map[i] = element
                    clean_elements_text += f"[{i}] <{tag}> {text}\n"
        clean_elements_text += "[END of Interactive Elements]"

        prompt = f"""
        {PERSONA_PROMPT}
        Analyze the attached screenshot and this list of interactive elements:
        ---
        {clean_elements_text}
        ---
        Your task is to respond with ONLY the number of the element to interact with next.
        """
        response = await model.generate_content_async([prompt, {"mime_type": "image/png", "data": screenshot}])
        decision_text = response.text.strip().replace("'", "").replace('"', '')
        print(f"AI Decision: Choose element number '{decision_text}'")
        element_id_to_click = int(decision_text)
        element_to_click = element_map.get(element_id_to_click)

        if element_to_click:
            action_text = (await element_to_click.inner_text() or "").strip()
            print(f"Executing action: Clicking on element [{element_id_to_click}] with text '{action_text}'")
            await element_to_click.click(timeout=10000)
            await page.wait_for_load_state('networkidle')
            return True
        else:
            print(f"Error: AI chose an invalid element ID: {element_id_to_click}")
            return False
    except Exception as e:
        print(f"An error occurred in the hybrid model: {e}")
        return False

async def handle_date_of_birth_page(page, persona):
    print("Detected 'Date of birth' page. Handling specifically...")
    try:
        dob_str = persona['about_you']['date_of_birth']
        dob_obj = datetime.strptime(dob_str, '%Y-%m-%d')
        year, month_name, day = str(dob_obj.year), dob_obj.strftime('%B'), str(dob_obj.day)
        
        await page.get_by_placeholder("MM").click()
        await page.get_by_role("option", name=month_name).click()
        await page.get_by_placeholder("DD").fill(day)
        await page.get_by_placeholder("YYYY").click()
        await page.get_by_text(year, exact=True).click()
        await page.locator('button[type="submit"], button:has-text("Next"), button:has-text("→")').first.click()
        
        await page.wait_for_load_state('networkidle')
        print("Successfully submitted Date of Birth.")
        return True
    except Exception as e:
        print(f"An error occurred while handling Date of Birth page: {e}")
        return False

async def page_router(page):
    print("Routing page...")
    if await page.locator('div:has-text("Date of birth")').count() > 0 and await page.get_by_placeholder("MM").count() > 0:
        return await handle_date_of_birth_page(page, PERSONA)
    else:
        return await solve_with_hybrid_model(page)

async def main():
    if not os.path.exists('auth.json'):
        print("Authentication file (auth.json) not found. Run 'save_auth.py' first.")
        return

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=False, slow_mo=50)
        context = await browser.new_context(storage_state="auth.json")
        page = await context.new_page()

        print("Session loaded. Navigating to surveys...")
        await page.goto("https://www.qmee.com/en-us/surveys", timeout=60000)

        try:
            print("Looking for a survey to start...")
            start_earning_button = page.get_by_role('button', name='Start earning')
            first_survey_card = page.locator('a.survey-card').first
            await asyncio.sleep(3) # A slightly longer pause for all dynamic content
            if await start_earning_button.is_visible(timeout=10000):
                print("Clicking 'Start earning' button...")
                await start_earning_button.click()
            elif await first_survey_card.is_visible(timeout=10000):
                print("Clicking the first available survey card...")
                await first_survey_card.click()
            else:
                raise Exception("No startup element found.")
            await page.wait_for_load_state('networkidle', timeout=30000)
        except Exception as e:
            print(f"Could not auto-start a survey. Please navigate to one manually. Error: {e}")
            input("Press Enter once you are on a survey page.")

        for i in range(20):
            print(f"\n--- Attempting Page {i+1} ---")
            await page.wait_for_load_state('domcontentloaded')
            success = await page_router(page)
            if not success:
                print("Failed to solve page. Stopping.")
                break
            await asyncio.sleep(2)

        print("\nBot has finished its run.")
        await context.close()
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())