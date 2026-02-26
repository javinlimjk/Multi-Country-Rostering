
from playwright.sync_api import sync_playwright
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            print("Navigating to dashboard...")
            page.goto("http://localhost:8501", timeout=60000)

            # Wait for title
            page.wait_for_selector("text=Operations Dashboard", timeout=30000)
            print("Found Title")

            # Verify Roster Period (Fuzzy match)
            # Use a locator that finds text containing "Roster Period"
            if page.locator("text=Roster Period").count() > 0:
                print("✅ Roster Period Found")
            else:
                print("❌ Roster Period Missing (Locator Check)")

            # Click Expander 3
            print("Expanding Workforce Management...")
            page.get_by_text("3. Workforce Management").click()
            time.sleep(1)

            # Toggle 'Use Employee Database'
            print("Toggling Use Employee Database...")
            # Toggle widget usually has a label
            page.get_by_text("Use Employee Database").click()
            time.sleep(1)

            # Verify Status Column
            # In a streamlit dataframe, headers are usually distinct
            # We just check if the text "Status" is visible in the context of the table
            if page.locator("text=Status").count() > 0:
                print("✅ Status Column Header Found")
            else:
                print("❌ Status Column Header Missing")

            if page.locator("text=Contract").count() > 0:
                print("✅ Contract Column Header Found")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run()
