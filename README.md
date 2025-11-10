# WhatsApp Bulk Messenger

A beautiful Flask web application for sending personalized WhatsApp messages to multiple contacts using an Excel file.

## Features

- 🎨 **Modern UI**: Beautiful, responsive design with WhatsApp-inspired colors
- 📱 **WhatsApp Integration**: Uses WhatsApp Web to send messages
- 📊 **Excel Support**: Upload Excel files with contact information
- 🎯 **Personalization**: Use `{name}` placeholder to personalize messages
- 📈 **Real-time Progress**: Live progress tracking with status updates
- ⏹️ **Stop/Start**: Ability to stop sending messages at any time
- 📁 **File Upload**: Drag & drop or click to upload Excel files

## Prerequisites

1. **Chrome Browser**: Make sure Google Chrome is installed
2. **WhatsApp Web**: You need to be logged into WhatsApp Web
3. **Python 3.7+**: Make sure Python is installed on your system

## Installation

1. **Clone or download** this project to your local machine

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Chrome Profile** (Optional):
   - The app uses a specific Chrome profile for WhatsApp Web
   - Default path: `C:\Users\ASAD\AppData\Local\Google\Chrome\User Data\BotProfile`
   - You can modify this in `app.py` if needed

## Excel File Format

Your Excel file should have the following columns:
- `phone`: Phone number (with country code, e.g., +1234567890)
- `name`: Contact name (optional, used for personalization)

Example:
| phone | name |
|-------|------|
| +1234567890 | John Doe |
| +0987654321 | Jane Smith |

## Usage

1. **Start the application**:
   ```bash
   python app.py
   ```

2. **Open your browser** and go to: `http://localhost:5000`

3. **Enter your message** in the text area. Use `{name}` to personalize with contact names

4. **Upload your Excel file** by clicking the upload area or dragging & dropping

5. **Click "Send Messages"** to start sending

6. **Monitor progress** in real-time with the progress bar and status updates

7. **Stop anytime** using the "Stop Sending" button if needed

## Message Personalization

Use the `{name}` placeholder in your message to personalize it:
- `Hello {name}, this is a test message!` → `Hello John Doe, this is a test message!`
- If no name is provided, the placeholder will be empty

## Important Notes

- **WhatsApp Web**: Make sure you're logged into WhatsApp Web in Chrome
- **Rate Limiting**: The app waits 5 seconds between messages to avoid spam detection
- **Chrome Profile**: The app uses a specific Chrome profile to maintain WhatsApp Web session
- **File Format**: Only Excel files (.xlsx, .xls) are supported
- **Phone Format**: Use international format with country code (e.g., +1234567890)

## Troubleshooting

1. **Chrome not opening**: Make sure Chrome is installed and the profile path is correct
2. **WhatsApp Web not loading**: Check your internet connection and try logging into WhatsApp Web manually
3. **Messages not sending**: Verify your Excel file format and phone number format
4. **Permission errors**: Make sure the uploads folder has write permissions

## Security Note

This application is for personal use only. Make sure you comply with WhatsApp's terms of service and local laws regarding bulk messaging.

## Support

If you encounter any issues, check:
1. Chrome browser installation
2. WhatsApp Web login status
3. Excel file format
4. Phone number format
5. Internet connection
