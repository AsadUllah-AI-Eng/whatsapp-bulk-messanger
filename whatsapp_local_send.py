import os
import time
import urllib.parse
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ================= CONFIGURATION =================
EXCEL_FILE = "uploads/Clients.xlsx"  # Excel file name (must be in uploads folder)
MESSAGE = "Hello {name}, this is a test message sent automatically via WhatsApp Web!"
CHROME_USER_DATA_DIR = os.path.join(os.path.expanduser("~"), "AppData", "Local", "Google", "Chrome", "User Data", "BotProfile")
  # your Chrome user data path
CHROME_PROFILE = "Default"  # profile folder name (usually 'Default')
# ==================================================

def send_message(phone, name):
    """Send WhatsApp message to a single contact"""
    message = MESSAGE.format(name=name if pd.notna(name) else "")
    encoded_message = urllib.parse.quote(message)
    link = f"https://web.whatsapp.com/send?phone={phone}&text={encoded_message}&app_absent=0"
    driver.get(link)
    try:
        # Wait for chat box to load
        WebDriverWait(driver, 40).until(
            EC.presence_of_element_located((By.XPATH, "//div[@contenteditable='true'][@data-tab='10']"))
        )
        input_box = driver.find_element(By.XPATH, "//div[@contenteditable='true'][@data-tab='10']")
        input_box.send_keys(Keys.ENTER)
        print(f"✅ Sent to {name} ({phone})")
        time.sleep(5)
    except Exception as e:
        print(f"❌ Failed for {phone}: {e}")

# Setup Chrome
options = webdriver.ChromeOptions()
options.add_argument(f"--user-data-dir={CHROME_USER_DATA_DIR}")
options.add_argument(f"--profile-directory={CHROME_PROFILE}")
options.add_argument("--remote-debugging-port=9222")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--start-maximized")

# Initialize driver
driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
driver.get("https://web.whatsapp.com")
print("📱 Please scan the QR code if required... waiting for WhatsApp Web to load.")
time.sleep(15)

# Load Excel file
try:
    data = pd.read_excel(EXCEL_FILE)
    print(f"📋 Loaded {len(data)} contacts from {EXCEL_FILE}")
except FileNotFoundError:
    print(f"❌ Excel file '{EXCEL_FILE}' not found. Please place it in the same folder.")
    driver.quit()
    exit()

# Send messages
for _, row in data.iterrows():
    phone = str(row['phone'])
    name = row.get('name', '')
    send_message(phone, name)

print("✅ All messages processed successfully.")
driver.quit()
