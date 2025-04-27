import telegram
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update
from dotenv import load_dotenv
import os

load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Hello! I'm working.")

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.run_polling()

if __name__ == '__main__':
    main()