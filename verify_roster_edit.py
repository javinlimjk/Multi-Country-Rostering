
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

            # Generate Roster to get table
            print("Generating Roster...")
            page.get_by_role("button", name="Generate Roster").click()

            # Wait for "Optimization Complete" or table
            page.wait_for_selector("text=Optimization Complete", timeout=30000)
            print("Optimization Complete")

            # Look for the table
            # In Streamlit, data_editor is rendered.
            # We can verify the presence of "Edit Mode" caption
            if page.locator("text=Edit Mode").count() > 0:
                print("✅ Edit Mode Caption Found")

            time.sleep(2)
            page.screenshot(path="verification_edit.png", full_page=True)
            print("Screenshot saved to verification_edit.png")

        except Exception as e:
            print(f"Error: {e}")
            page.screenshot(path="error_edit.png")
        finally:
            browser.close()

if __name__ == "__main__":
    run()
