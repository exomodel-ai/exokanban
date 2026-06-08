import os
import logging
import asyncio
from abc import ABC, abstractmethod
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from telegram.constants import ParseMode
from dotenv import load_dotenv

load_dotenv()

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class UserInteraction(ABC):
    def __init__(self, telegram_token: str = None):
        self.mode = os.getenv("INTERACTION_MODE", "cli").lower()

        # Priority: use the token passed in; if None, fall back to .env
        self.token = telegram_token or os.getenv("TELEGRAM_TOKEN")

        # Optional user allowlist
        raw_allowed = os.getenv("TELEGRAM_ALLOWED_USERS", "")
        self.allowed_users = [int(i) for i in raw_allowed.split(",") if i]

    @abstractmethod
    async def process_prompt(self, user_id, text):
        """Override this in the application subclass."""
        pass

    def is_authorized(self, user_id):
        # Empty list means the bot is public
        if not self.allowed_users:
            return True
        return user_id in self.allowed_users

    # --- Telegram handler ---
    async def _handle_telegram(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message and update.message.text:
            user_id = update.effective_user.id

            if not self.is_authorized(user_id):
                logger.warning("Access denied: %s", user_id)
                await update.message.reply_text("❌ This bot is private.")
                return

            # 1. Run the prompt and capture the result
            result = await self.process_prompt(user_id, update.message.text)

            # 2. Ensure the result is a plain string
            if isinstance(result, str):
                text = result
            elif hasattr(result, 'model_dump_json'):
                # Pydantic object — format it
                text = f"✅ Object updated successfully:\n\n{str(result)}"
            else:
                # Generic fallback for lists, dicts, or other objects
                text = str(result)

            # 3. Safety cap: Telegram rejects messages longer than 4096 characters
            if len(text) > 4000:
                logger.warning("Response was too long for Telegram and was truncated.")
                text = text[:4000] + "\n\n... [Message truncated by Telegram limit]"

            # 4. Empty-response failsafe
            if not text:
                text = "⚠️ The agent processed the request but did not return any text message. Please try rephrasing your request."

            # 5. Send safely
            await update.message.reply_text(
                text,
                parse_mode=ParseMode.HTML if text.startswith("<") else None
            )

    # --- Runners ---
    def run(self):
        if self.mode == "telegram":
            if not self.token:
                raise ValueError("TELEGRAM_TOKEN is not configured in .env")

            logger.info("Starting TELEGRAM mode...")
            app = ApplicationBuilder().token(self.token).build()
            app.add_handler(MessageHandler(filters.TEXT | filters.COMMAND, self._handle_telegram))
            app.run_polling()

        else:
            logger.info("Starting CLI mode...")
            asyncio.run(self._run_cli())

    async def _run_cli(self):
        print("CLI mode active. Type 'exit' to quit.")
        while True:
            text = input(">>> ")
            if text.lower() in ["sair", "/sair", "exit", "/exit", "quit", "/quit"]: break
            response = await self.process_prompt("DEV-CLI", text)
            print(f"Bot: {response}\n")


# Minimal implementation for smoke-testing
class TesteBot(UserInteraction):
    async def process_prompt(self, user_id, text):
        # Echoes the message back with the user id
        return f"Test OK! User {user_id} said: {text}"

if __name__ == '__main__':
    bot = TesteBot()
    bot.run()
