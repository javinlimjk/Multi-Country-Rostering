from playwright.sync_api import sync_playwright
import time

def verify_ui():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("Navigating to Streamlit...")
        try:
            page.goto("http://localhost:8501", timeout=30000)
        except Exception as e:
            print(f"Failed to load page: {e}")
            return

        # Wait for title
        try:
            page.wait_for_selector("text=SATS Roster AI", timeout=15000)
            print("Page loaded.")
        except:
            print("Timeout waiting for title.")

        # Take screenshot of Setup Tab
        time.sleep(2) # Allow styles to render
        page.screenshot(path="verification_setup.png", full_page=True)
        print("Screenshot 1 saved.")

        browser.close()

if __name__ == "__main__":
    verify_ui()
