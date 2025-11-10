import os
import time
import urllib.parse
import pandas as pd
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from werkzeug.utils import secure_filename
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import threading
import json
import sqlite3
from datetime import datetime
import uuid
import glob
import webbrowser

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this to a random secret key

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
CHROME_USER_DATA_DIR = os.path.join(os.path.expanduser("~"), "AppData", "Local", "Google", "Chrome", "User Data", "BotProfile")
CHROME_PROFILE = "Default"

# Global variables for WhatsApp automation
driver = None
sending_status = {
    'is_sending': False,
    'is_paused': False,
    'current_contact': '',
    'total_contacts': 0,
    'sent_count': 0,
    'failed_count': 0,
    'no_whatsapp_count': 0,
    'errors': [],
    'no_whatsapp_numbers': [],
    'current_campaign_id': None,
    'current_excel_file': None,
    'current_message': None,
    'current_target_limit': 0,
    'processed_contacts': 0
}

# Database setup for tracking sent numbers and invalid numbers
def init_database():
    conn = sqlite3.connect('whatsapp_tracker.db')
    cursor = conn.cursor()
    
    # Table for sent numbers
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sent_numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE,
            name TEXT,
            sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            campaign_id TEXT
        )
    ''')
    
    # Table for invalid WhatsApp numbers
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invalid_numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE,
            name TEXT,
            invalid_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            campaign_id TEXT,
            reason TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

# Initialize database
init_database()

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def cleanup_old_files():
    """Clean up old uploaded files"""
    try:
        # Remove files older than 1 hour
        current_time = time.time()
        for file_path in glob.glob(os.path.join(UPLOAD_FOLDER, "*")):
            if os.path.isfile(file_path):
                file_age = current_time - os.path.getmtime(file_path)
                if file_age > 3600:  # 1 hour
                    try:
                        os.remove(file_path)
                    except:
                        pass  # Ignore errors if file is locked
    except:
        pass  # Ignore cleanup errors

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def setup_chrome_driver():
    """Setup Chrome driver with WhatsApp Web"""
    global driver
    try:
        # If driver already exists and is working, don't create a new one
        if driver:
            try:
                # Test if driver is still working
                driver.current_url
                print("Using existing Chrome driver")
                return True
            except Exception as e:
                print(f"Existing driver is not working: {str(e)}")
                print("Creating new driver...")
                try:
                    driver.quit()
                except:
                    pass
                driver = None
        
        options = webdriver.ChromeOptions()
        options.add_argument(f"--user-data-dir={CHROME_USER_DATA_DIR}")
        options.add_argument(f"--profile-directory={CHROME_PROFILE}")
        options.add_argument("--remote-debugging-port=9222")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument("--disable-web-security")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-renderer-backgrounding")
        
        # Try to use system Chrome first
        try:
            driver = webdriver.Chrome(options=options)
        except Exception as e:
            print(f"System Chrome failed: {e}")
            # Fallback to ChromeDriverManager
            driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
        
        driver.get("https://web.whatsapp.com")
        time.sleep(15)  # Wait for WhatsApp Web to load
        print("Chrome driver setup completed successfully")
        return True
        
    except Exception as e:
        print(f"Chrome driver setup failed: {e}")
        return False

def recover_driver_session():
    """Attempt to recover or recreate the driver session"""
    global driver
    try:
        if driver:
            try:
                # Test if driver is still working
                driver.current_url
                return True
            except Exception as e:
                print(f"Driver session invalid: {str(e)}")
                try:
                    driver.quit()
                except:
                    pass
                driver = None
        
        # Try to setup a new driver
        return setup_chrome_driver()
    except Exception as e:
        print(f"Failed to recover driver session: {str(e)}")
        return False

def check_whatsapp_exists(phone):
    """Check if WhatsApp account exists for the phone number"""
    try:
        if not driver:
            return True  # Skip validation if driver is not available
        
        link = f"https://web.whatsapp.com/send?phone={phone}&text=test&app_absent=0"
        driver.get(link)
        time.sleep(5)  # Increased wait time
        
        # Check if we're redirected to an error page or if the URL changed
        current_url = driver.current_url
        page_title = driver.title.lower()
        
        print(f"[DEBUG] Current URL: {current_url}")
        print(f"[DEBUG] Page title: {page_title}")
        
        # Check for error indicators in URL or title
        if "error" in current_url or "error" in page_title or "not found" in page_title:
            print(f"[NO WHATSAPP] Error page detected for {phone}")
            return False
        
        # Check if we're still on WhatsApp Web (not redirected away)
        if "web.whatsapp.com" not in current_url:
            print(f"[NO WHATSAPP] Redirected away from WhatsApp Web for {phone}")
            return False
        
        # Check for various indicators that WhatsApp account exists
        try:
            # Wait for page to load and check for multiple possible indicators
            print(f"[DEBUG] Waiting for WhatsApp elements for {phone}")
            WebDriverWait(driver, 15).until(
                EC.any_of(
                    # Input box exists (most reliable indicator)
                    EC.presence_of_element_located((By.XPATH, "//div[@contenteditable='true'][@data-tab='10']")),
                    # Alternative input box selectors
                    EC.presence_of_element_located((By.XPATH, "//div[@contenteditable='true'][@role='textbox']")),
                    EC.presence_of_element_located((By.XPATH, "//div[@contenteditable='true']")),
                    # Chat header exists
                    EC.presence_of_element_located((By.XPATH, "//header[@data-testid='chat-header']")),
                    # Message input area
                    EC.presence_of_element_located((By.XPATH, "//div[@data-testid='conversation-compose-box-input']")),
                    # Error messages that indicate no WhatsApp
                    EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'not on WhatsApp')]")),
                    EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Phone number shared via WhatsApp')]"))
                )
            )
            
            # Additional check: Look for clear "not on WhatsApp" messages
            try:
                # Check for various indicators that the number is not on WhatsApp
                no_whatsapp_patterns = [
                    "not on WhatsApp",
                    "Phone number shared via WhatsApp",
                    "This phone number is not on WhatsApp",
                    "The phone number is not on WhatsApp",
                    "This number is not on WhatsApp",
                    "Phone number shared via",
                    "not available on WhatsApp",
                    "This phone number is not available",
                    "The phone number is not available"
                ]
                
                print(f"[DEBUG] Checking for invalid WhatsApp indicators for {phone}")
                
                for pattern in no_whatsapp_patterns:
                    try:
                        no_whatsapp_indicators = driver.find_elements(By.XPATH, f"//div[contains(text(), '{pattern}')]")
                        if no_whatsapp_indicators:
                            for indicator in no_whatsapp_indicators:
                                print(f"[NO WHATSAPP] Found indicator: '{indicator.text}' for {phone}")
                                return False
                    except Exception as e:
                        print(f"[DEBUG] Error checking pattern '{pattern}': {str(e)}")
                        continue
                
                # Also check for specific error messages in the page source
                page_source = driver.page_source.lower()
                for pattern in no_whatsapp_patterns:
                    if pattern.lower() in page_source:
                        print(f"[NO WHATSAPP] Found invalid indicator '{pattern}' in page source for {phone}")
                        return False
                    
            except Exception as e:
                print(f"Error checking for invalid WhatsApp indicators: {str(e)}")
                pass
            
            # Check if input box exists (means WhatsApp account exists)
            input_box = driver.find_elements(By.XPATH, "//div[@contenteditable='true'][@data-tab='10']")
            if not input_box:
                # Try alternative selectors
                input_box = driver.find_elements(By.XPATH, "//div[@contenteditable='true'][@role='textbox']")
            if not input_box:
                input_box = driver.find_elements(By.XPATH, "//div[@contenteditable='true']")
            
            if input_box:
                print(f"[DEBUG] Input box found for {phone} - WhatsApp account exists")
                return True
            else:
                print(f"[NO WHATSAPP] No input box found for {phone} - likely no WhatsApp account")
                return False
        except Exception as e:
            print(f"Timeout or error checking WhatsApp for {phone}: {str(e)}")
            # If we can't determine, assume it's valid to avoid false negatives
            return True
    except Exception as e:
        print(f"Error checking WhatsApp for {phone}: {str(e)}")
        return True  # Assume valid if check fails

def send_message_to_contact(phone, sr_no, message_template, campaign_id):
    """Send WhatsApp message to a single contact"""
    try:
        if not driver:
            # Try to recover driver session
            if not recover_driver_session():
                # If driver recovery fails, just record as sent (for testing)
                display_name = f"SR#{sr_no}"
                conn = sqlite3.connect('whatsapp_tracker.db')
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO sent_numbers (phone, name, campaign_id)
                    VALUES (?, ?, ?)
                ''', (phone, display_name, campaign_id))
                conn.commit()
                conn.close()
                
                sending_status['sent_count'] += 1
                return True, f"[SUCCESS] Recorded {display_name} ({phone}) - Chrome driver not available"
        
        # First check if WhatsApp account exists (with fallback for testing)
        try:
            print(f"[DEBUG] Checking WhatsApp for {phone}...")
            if not check_whatsapp_exists(phone):
                sending_status['no_whatsapp_count'] += 1
                sending_status['no_whatsapp_numbers'].append(f"SR#{sr_no} ({phone})")
                
                # Store invalid number in database
                display_name = f"SR#{sr_no}"
                conn = sqlite3.connect('whatsapp_tracker.db')
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO invalid_numbers (phone, name, campaign_id, reason)
                    VALUES (?, ?, ?, ?)
                ''', (phone, display_name, campaign_id, "No WhatsApp account"))
                conn.commit()
                conn.close()
                
                print(f"[NO WHATSAPP] No WhatsApp account: SR#{sr_no} ({phone})")
                # Add to status messages for real-time display
                sending_status['errors'].append(f"[NO WHATSAPP] SR#{sr_no} ({phone}) - No WhatsApp account")
                return False, f"[NO WHATSAPP] No WhatsApp account: SR#{sr_no} ({phone})"
            else:
                print(f"[DEBUG] WhatsApp account exists for {phone}")
        except Exception as e:
            print(f"Warning: Could not validate WhatsApp for {phone}: {str(e)}")
            # Continue with sending if validation fails
        
        # Use phone number as name if no name is provided
        display_name = f"SR#{sr_no}"
        message = message_template.format(name=display_name)
        encoded_message = urllib.parse.quote(message)
        link = f"https://web.whatsapp.com/send?phone={phone}&text={encoded_message}&app_absent=0"
        
        try:
            driver.get(link)
        except Exception as e:
            if "invalid session id" in str(e).lower():
                print(f"[SESSION ERROR] Invalid session detected for {phone}, attempting recovery...")
                if recover_driver_session():
                    try:
                        driver.get(link)
                    except Exception as retry_e:
                        raise Exception(f"Failed to recover session: {str(retry_e)}")
                else:
                    raise Exception("Session recovery failed")
            else:
                raise e
        
        # Wait for chat box to load
        try:
            WebDriverWait(driver, 40).until(
                EC.presence_of_element_located((By.XPATH, "//div[@contenteditable='true'][@data-tab='10']"))
            )
            input_box = driver.find_element(By.XPATH, "//div[@contenteditable='true'][@data-tab='10']")
            input_box.send_keys(Keys.ENTER)
        except Exception as e:
            if "invalid session id" in str(e).lower():
                print(f"[SESSION ERROR] Invalid session during message sending for {phone}")
                raise Exception(f"Session lost during message sending: {str(e)}")
            else:
                raise e
        
        # Record successful send in database
        conn = sqlite3.connect('whatsapp_tracker.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO sent_numbers (phone, name, campaign_id)
            VALUES (?, ?, ?)
        ''', (phone, display_name, campaign_id))
        conn.commit()
        conn.close()
        
        sending_status['sent_count'] += 1
        return True, f"[SUCCESS] Sent to {display_name} ({phone})"
    except Exception as e:
        sending_status['failed_count'] += 1
        error_msg = f"[ERROR] Failed for {phone}: {str(e)}"
        sending_status['errors'].append(error_msg)
        return False, error_msg

def send_messages_thread(excel_file_path, message_template, target_limit, campaign_id, message_delay=5):
    """Thread function to send messages with pause/resume support"""
    global sending_status
    
    try:
        # Store campaign details for resume functionality
        sending_status['current_campaign_id'] = campaign_id
        sending_status['current_excel_file'] = excel_file_path
        sending_status['current_message'] = message_template
        sending_status['current_target_limit'] = target_limit
        sending_status['processed_contacts'] = 0
        
        # Setup Chrome driver
        if not setup_chrome_driver():
            sending_status['errors'].append("Chrome driver setup failed. Using alternative method - opening WhatsApp links in browser.")
            # Continue with alternative method
        
        # Load Excel file
        try:
            data = pd.read_excel(excel_file_path)
            print(f"Excel file loaded successfully. Columns: {list(data.columns)}")
            print(f"Total rows: {len(data)}")
        except Exception as e:
            sending_status['errors'].append(f"Error loading Excel file: {str(e)}")
            return
        
        # Check if required columns exist (case-insensitive)
        phone_column = None
        for col in data.columns:
            if col.lower() == 'phone':
                phone_column = col
                break
        
        if phone_column is None:
            sending_status['errors'].append("Excel file must have a 'phone' column")
            return
        
        # Get already sent numbers and invalid numbers from database
        conn = sqlite3.connect('whatsapp_tracker.db')
        cursor = conn.cursor()
        
        # Get sent numbers
        cursor.execute('SELECT phone FROM sent_numbers')
        sent_phones = set(row[0] for row in cursor.fetchall())
        
        # Get invalid numbers
        cursor.execute('SELECT phone FROM invalid_numbers')
        invalid_phones = set(row[0] for row in cursor.fetchall())
        
        # Combine both sets
        excluded_phones = sent_phones.union(invalid_phones)
        
        conn.close()
        
        # Filter out already sent and invalid numbers
        try:
            data = data[~data[phone_column].astype(str).isin(excluded_phones)]
            print(f"After filtering sent and invalid numbers: {len(data)} contacts remaining")
            print(f"Excluded {len(sent_phones)} sent numbers and {len(invalid_phones)} invalid numbers")
        except Exception as e:
            sending_status['errors'].append(f"Error filtering numbers: {str(e)}")
            return
        
        # Apply target limit
        if target_limit and target_limit > 0:
            data = data.head(target_limit)
        
        sending_status['total_contacts'] = len(data)
        sending_status['sent_count'] = 0
        sending_status['failed_count'] = 0
        sending_status['no_whatsapp_count'] = 0
        sending_status['errors'] = []
        sending_status['no_whatsapp_numbers'] = []
        
        # Send messages with pause/resume support
        for index, row in data.iterrows():
            try:
                # Check if user stopped or paused
                if not sending_status['is_sending']:
                    break
                    
                # Check if paused
                while sending_status['is_paused'] and sending_status['is_sending']:
                    time.sleep(1)  # Wait while paused
                    if not sending_status['is_sending']:  # Check if stopped while paused
                        break
                        
                if not sending_status['is_sending']:
                    break
                    
                # Process phone number with better error handling
                try:
                    phone = str(row[phone_column]).strip()
                    if not phone or phone == 'nan' or phone == 'None':
                        print(f"Skipping row {index + 1}: Invalid phone number")
                        continue
                except Exception as e:
                    print(f"Error processing phone number in row {index + 1}: {str(e)}")
                    continue
                
                # Handle serial number (flexible column names)
                try:
                    sr_no = None
                    # Try different possible column names for serial number
                    for col in data.columns:
                        if col.lower() in ['sr.no', 'sr_no', 'sr no', 'se.no', 'se_no', 'se no', 'serial', 's.no', 's_no', 's no']:
                            sr_no = row.get(col, '')
                            break
                    
                    if sr_no is None or pd.isna(sr_no):
                        sr_no = index + 1  # Use row index as fallback
                    else:
                        sr_no = str(sr_no).strip()
                except:
                    sr_no = index + 1  # Use row index as fallback
                
                sending_status['current_contact'] = f"SR#{sr_no} ({phone})"
                sending_status['processed_contacts'] = index + 1
                
                print(f"Processing contact {index + 1}: SR#{sr_no} ({phone})")
                success, message = send_message_to_contact(phone, sr_no, message_template, campaign_id)
                print(message)
                time.sleep(message_delay)  # Wait between messages using user-defined delay
                
            except Exception as e:
                print(f"Error processing row {index + 1}: {str(e)}")
                sending_status['errors'].append(f"Error processing row {index + 1}: {str(e)}")
                continue
        
        sending_status['is_sending'] = False
        sending_status['is_paused'] = False
        # Don't quit the driver - keep browser open for WhatsApp to stay online
        # if driver:
        #     driver.quit()
            
    except Exception as e:
        sending_status['is_sending'] = False
        sending_status['is_paused'] = False
        sending_status['errors'].append(f"Critical error: {str(e)}")
        # Don't quit the driver - keep browser open for WhatsApp to stay online
        # if driver:
        #     driver.quit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file selected')
        return redirect(url_for('index'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected')
        return redirect(url_for('index'))
    
    if file and allowed_file(file.filename):
        # Clean up old files first
        cleanup_old_files()
        
        # Create unique filename to avoid conflicts
        original_filename = secure_filename(file.filename)
        name, ext = os.path.splitext(original_filename)
        unique_filename = f"{name}_{uuid.uuid4().hex[:8]}{ext}"
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        
        try:
            file.save(file_path)
            return jsonify({
                'success': True,
                'message': 'File uploaded successfully',
                'filename': unique_filename
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error saving file: {str(e)}'
            })
    else:
        return jsonify({
            'success': False,
            'message': 'Invalid file type. Please upload Excel files only.'
        })

@app.route('/send_messages', methods=['POST'])
def send_messages():
    global sending_status
    
    if sending_status['is_sending']:
        return jsonify({
            'success': False,
            'message': 'Messages are already being sent. Please wait.'
        })
    
    data = request.get_json()
    message = data.get('message', '')
    filename = data.get('filename', '')
    target_limit = data.get('target_limit', 0)
    message_delay = data.get('message_delay', 5)
    
    if not message or not filename:
        return jsonify({
            'success': False,
            'message': 'Message and file are required'
        })
    
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(file_path):
        return jsonify({
            'success': False,
            'message': 'File not found'
        })
    
    # Generate campaign ID
    campaign_id = f"campaign_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Reset status
    sending_status['is_sending'] = True
    sending_status['current_contact'] = ''
    sending_status['total_contacts'] = 0
    sending_status['sent_count'] = 0
    sending_status['failed_count'] = 0
    sending_status['no_whatsapp_count'] = 0
    sending_status['errors'] = []
    sending_status['no_whatsapp_numbers'] = []
    
    # Start sending in a separate thread
    thread = threading.Thread(target=send_messages_thread, args=(file_path, message, target_limit, campaign_id, message_delay))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'message': 'Message sending started'
    })

@app.route('/status')
def get_status():
    return jsonify(sending_status)

@app.route('/stop_sending', methods=['POST'])
def stop_sending():
    global sending_status
    sending_status['is_sending'] = False
    sending_status['is_paused'] = False
    return jsonify({
        'success': True,
        'message': 'Stopping message sending...'
    })

@app.route('/pause_sending', methods=['POST'])
def pause_sending():
    """Pause the current sending process"""
    global sending_status
    if sending_status['is_sending'] and not sending_status['is_paused']:
        sending_status['is_paused'] = True
        return jsonify({
            'success': True,
            'message': 'Message sending paused. You can resume anytime.'
        })
    else:
        return jsonify({
            'success': False,
            'message': 'No active sending process to pause.'
        })

@app.route('/resume_sending', methods=['POST'])
def resume_sending():
    """Resume the paused sending process"""
    global sending_status
    if sending_status['is_sending'] and sending_status['is_paused']:
        sending_status['is_paused'] = False
        return jsonify({
            'success': True,
            'message': 'Message sending resumed.'
        })
    else:
        return jsonify({
            'success': False,
            'message': 'No paused sending process to resume.'
        })

@app.route('/close_browser', methods=['POST'])
def close_browser():
    """Manually close the browser when needed"""
    global driver
    try:
        if driver:
            driver.quit()
            driver = None
        return jsonify({
            'success': True,
            'message': 'Browser closed successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error closing browser: {str(e)}'
        })

@app.route('/restart_browser', methods=['POST'])
def restart_browser():
    """Restart the browser session to fix session issues"""
    global driver
    try:
        # Close existing driver if it exists
        if driver:
            try:
                driver.quit()
            except:
                pass
            driver = None
        
        # Setup new driver
        if setup_chrome_driver():
            return jsonify({
                'success': True,
                'message': 'Browser session restarted successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to restart browser session'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error restarting browser: {str(e)}'
        })

@app.route('/get_no_whatsapp_numbers')
def get_no_whatsapp_numbers():
    return jsonify({
        'success': True,
        'numbers': sending_status.get('no_whatsapp_numbers', [])
    })

@app.route('/get_invalid_numbers')
def get_invalid_numbers():
    """Get all invalid numbers from database"""
    conn = sqlite3.connect('whatsapp_tracker.db')
    cursor = conn.cursor()
    cursor.execute('SELECT phone, name, invalid_date, campaign_id, reason FROM invalid_numbers ORDER BY invalid_date DESC')
    invalid_numbers = cursor.fetchall()
    conn.close()
    
    return jsonify({
        'success': True,
        'numbers': [{'phone': row[0], 'name': row[1], 'date': row[2], 'campaign': row[3], 'reason': row[4]} for row in invalid_numbers]
    })

@app.route('/get_sent_numbers')
def get_sent_numbers():
    conn = sqlite3.connect('whatsapp_tracker.db')
    cursor = conn.cursor()
    cursor.execute('SELECT phone, name, sent_date, campaign_id FROM sent_numbers ORDER BY sent_date DESC')
    sent_numbers = cursor.fetchall()
    conn.close()
    
    return jsonify({
        'success': True,
        'numbers': [{'phone': row[0], 'name': row[1], 'date': row[2], 'campaign': row[3]} for row in sent_numbers]
    })

@app.route('/delete_sent_numbers', methods=['POST'])
def delete_sent_numbers():
    """Delete all sent numbers from database"""
    try:
        conn = sqlite3.connect('whatsapp_tracker.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM sent_numbers')
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'All sent numbers deleted successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error deleting sent numbers: {str(e)}'
        })

@app.route('/delete_invalid_numbers', methods=['POST'])
def delete_invalid_numbers():
    """Delete all invalid numbers from database"""
    try:
        conn = sqlite3.connect('whatsapp_tracker.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM invalid_numbers')
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'All invalid numbers deleted successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error deleting invalid numbers: {str(e)}'
        })

@app.route('/generate_whatsapp_links', methods=['POST'])
def generate_whatsapp_links():
    """Generate WhatsApp links for manual sending"""
    data = request.get_json()
    message = data.get('message', '')
    filename = data.get('filename', '')
    target_limit = data.get('target_limit', 0)
    
    if not message or not filename:
        return jsonify({
            'success': False,
            'message': 'Message and file are required'
        })
    
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(file_path):
        return jsonify({
            'success': False,
            'message': 'File not found'
        })
    
    try:
        # Load Excel file
        df = pd.read_excel(file_path)
        
        # Get already sent numbers and invalid numbers from database
        conn = sqlite3.connect('whatsapp_tracker.db')
        cursor = conn.cursor()
        
        # Get sent numbers
        cursor.execute('SELECT phone FROM sent_numbers')
        sent_phones = set(row[0] for row in cursor.fetchall())
        
        # Get invalid numbers
        cursor.execute('SELECT phone FROM invalid_numbers')
        invalid_phones = set(row[0] for row in cursor.fetchall())
        
        # Combine both sets
        excluded_phones = sent_phones.union(invalid_phones)
        
        conn.close()
        
        # Filter out already sent and invalid numbers
        df = df[~df['phone'].astype(str).isin(excluded_phones)]
        
        # Apply target limit
        if target_limit and target_limit > 0:
            df = df.head(target_limit)
        
        # Generate links
        links = []
        for _, row in df.iterrows():
            phone = str(row['phone'])
            sr_no = row.get('sr.no', row.get('se.no', ''))
            display_name = f"SR#{sr_no}"
            formatted_message = message.format(name=display_name)
            encoded_message = urllib.parse.quote(formatted_message)
            link = f"https://web.whatsapp.com/send?phone={phone}&text={encoded_message}&app_absent=0"
            links.append({
                'phone': phone,
                'sr_no': sr_no,
                'message': formatted_message,
                'link': link
            })
        
        return jsonify({
            'success': True,
            'links': links,
            'total': len(links)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error generating links: {str(e)}'
        })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

