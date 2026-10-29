import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()                      # opens the secret envelope (.env)
TOKEN = os.getenv("BOT_TOKEN")     # takes the password out

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hi! I'm your expense bot.")

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))   # when someone sends /start, run start()
app.run_polling()                                 # the waiter at the door, asking "anyone there?"