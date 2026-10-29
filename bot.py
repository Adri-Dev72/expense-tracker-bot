import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes,
)

import database
from categories import DEFAULT_CATEGORIES

load_dotenv()                      # opens the secret envelope (.env)
TOKEN = os.getenv("BOT_TOKEN")     # takes the password out


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hi! I'm your expense bot.\n\n"
        "Add an expense like this:\n/add 12.50 Starbucks\n\n"
        "Other commands: /last and /undo"
    )


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/add 12.50 Starbucks -> remember it, then ask for a category."""
    if len(context.args) < 2:
        await update.message.reply_text("Please use: /add 12.50 Starbucks")
        return

    amount_text = context.args[0].replace("$", "").replace(",", ".")
    try:
        amount = float(amount_text)
    except ValueError:
        await update.message.reply_text("The amount must be a number, like 12.50")
        return
    if not 0 < amount < 1_000_000:
        await update.message.reply_text("Please use an amount above 0, like 12.50")
        return

    merchant = " ".join(context.args[1:])
    # Sticky note: remember this expense until the user taps a category
    context.user_data["pending"] = {"amount": amount, "merchant": merchant}

    # Buttons, two per row
    buttons = [
        [InlineKeyboardButton(name, callback_data=f"cat:{name}")
         for name in DEFAULT_CATEGORIES[i:i + 2]]
        for i in range(0, len(DEFAULT_CATEGORIES), 2)
    ]
    await update.message.reply_text(
        f"💳 ${amount:.2f} at {merchant}\nPick a category:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def category_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Runs when the user taps a category button."""
    query = update.callback_query
    await query.answer()   # tells Telegram "button press received"

    pending = context.user_data.get("pending")
    if pending is None:
        await query.edit_message_text("That expense expired. Send /add again.")
        return

    category = query.data.split(":", 1)[1]
    database.add_expense(
        update.effective_user.id, pending["amount"], pending["merchant"], category
    )
    del context.user_data["pending"]   # throw the sticky note away
    await query.edit_message_text(
        f"✅ Saved: ${pending['amount']:.2f} at {pending['merchant']} · {category}"
    )


async def last(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = database.get_last_expense(update.effective_user.id)
    if row is None:
        await update.message.reply_text("No expenses yet. Try /add 5.00 Coffee")
        return
    amount, merchant, category, created_at = row
    await update.message.reply_text(
        f"🧾 Last purchase: {merchant} · ${amount:.2f} · {category}\n🕒 {created_at}"
    )


async def undo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    removed = database.delete_last_expense(update.effective_user.id)
    if removed is None:
        await update.message.reply_text("Nothing to undo yet.")
        return
    amount, merchant = removed
    await update.message.reply_text(f"↩️ Removed: {merchant} · ${amount:.2f}")


database.setup_database()
app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("add", add))
app.add_handler(CommandHandler("last", last))
app.add_handler(CommandHandler("undo", undo))
app.add_handler(CallbackQueryHandler(category_chosen, pattern="^cat:"))
app.run_polling()