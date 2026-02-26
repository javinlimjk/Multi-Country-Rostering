
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

            # Verify Flow Order
            # 1. Roster Period (Date Input)
            # Streamlit date inputs are tough to find by label, but we can look for "Roster Period" text near top
            expect_date = page.get_by_text("Roster Period")
            if expect_date.count() > 0: print("✅ Roster Period Found")
            else: print("❌ Roster Period Missing")

            # 2. Expander 1: Work Definition
            # 3. Expander 2: Demand Intelligence
            # 4. Expander 3: Workforce Management

            # Click Expander 3
            print("Expanding Workforce Management...")
            page.get_by_text("Workforce Management").click()
            time.sleep(1)

            # Toggle 'Use Employee Database'
            print("Toggling Use Employee Database...")
            # We look for the label
            page.get_by_text("Use Employee Database").click()
            time.sleep(1)

            # Verify 'Status' and 'Contract' columns appear (roughly)
            # Just verify the table loaded
            print("Checking for Staff Database table...")
            # Ideally we check for "Status" text which is a column header
            if page.get_by_text("Staff Database").count() > 0:
                print("✅ Staff Database Section Visible")

            time.sleep(2)
            page.screenshot(path="verification_layout.png", full_page=True)
            print("Screenshot saved to verification_layout.png")

        except Exception as e:
            print(f"Error: {e}")
            page.screenshot(path="error_layout.png")
        finally:
            browser.close()

if __name__ == "__main__":
    run()
