import os
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

class TelegramNotifier:
    """Helper class to send status notifications via Telegram Bot API."""

    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.enabled = bool(self.token and self.chat_id)
        
        if not self.enabled:
            logging.warning("Telegram Bot notification is disabled. Credentials not set.")

    def send_message(self, text: str) -> bool:
        """Sends a text message to the specified Telegram chat.
        
        Args:
            text (str): Message content formatted in HTML.
            
        Returns:
            bool: True if sent successfully, False otherwise.
        """
        if not self.enabled:
            return False

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML"
        }

        try:
            logging.info(f"Attempting to send Telegram notification to chat: {self.chat_id}")
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logging.info("Telegram notification sent successfully.")
                return True
            else:
                logging.error(f"Failed to send Telegram notification (HTTP {response.status_code}): {response.text}")
                return False
        except Exception as e:
            logging.error(f"Exception raised while sending Telegram notification: {e}")
            return False

if __name__ == "__main__":
    # Test script execution
    logging.basicConfig(level=logging.INFO)
    notifier = TelegramNotifier()
    notifier.send_message("🤖 <b>[Test]</b> Telegram notification service has been initialized.")
