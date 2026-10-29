import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, filters,
)

import database
from categories import DEFAULT_CATEGORIES

load_dotenv()                      # opens the secret envelope (.env)
TOKEN = os.getenv("BOT_TOKEN")     # takes the password out


def in_rows(buttons, per_row=2):
    """Groups a flat list of buttons into rows (two per row)."""
    return [buttons[i:i + per_row] for i in range(0, len(buttons), per_row)]


# ---------------- Setup quiz ----------------

def pick_keyboard(selected):
    """The quiz buttons. A ✅ shows next to categories already tapped."""
    buttons = []
    for i, name in enumerate(DEFAULT_CATEGORIES):
        mark = "✅ " if i in selected else ""
        buttons.append(InlineKeyboardButton(mark + name, callback_data=f"pick:{i}"))
    rows = in_rows(buttons)
    rows.append([InlineKeyboardButton("➡️ Done", callback_data="pickdone")])
    return InlineKeyboardMarkup(rows)


async def begin_setup(message, context):
    # Sticky note for this person: what they picked so far and which step they're on
    context.user_data["setup"] = {"selected": set(), "custom": [], "typing": False}
    await message.reply_text(
        "Let's set up your categories 🧭\n\n"
        "Tap everything you spend money on, then press Done.",
        reply_markup=pick_keyboard(set()),
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if database.get_categories(update.effective_user.id):
        await update.message.reply_text(
            "👋 Welcome back!\n\n"
            "/add 12.50 Starbucks - save an expense\n"
            "/last - your latest purchase\n"
            "/undo - remove the last expense\n"
            "/setup - change your categories"
        )
    else:
        await update.message.reply_text("👋 Hi! I'm your expense bot.")
        await begin_setup(update.message, context)


async def setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await begin_setup(update.message, context)


async def pick_toggled(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """A category button was tapped: turn its ✅ on or off."""
    query = update.callback_query
    await query.answer()
    state = context.user_data.get("setup")
    if state is None:
        await query.edit_message_text("This setup expired. Send /setup to start again.")
        return
    index = int(query.data.split(":")[1])
    if index in state["selected"]:
        state["selected"].remove(index)
    else:
        state["selected"].add(index)
    await query.edit_message_reply_markup(reply_markup=pick_keyboard(state["selected"]))


async def pick_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Done with the buttons: now ask for custom categories."""
    query = update.callback_query
    state = context.user_data.get("setup")
    if state is None:
        await query.answer()
        await query.edit_message_text("This setup expired. Send /setup to start again.")
        return
    if not state["selected"]:
        await query.answer("Pick at least one category first 🙂", show_alert=True)
        return
    await query.answer()
    state["typing"] = True
    await query.edit_message_text(
        "Anything else you spend on that wasn't in the list?\n\n"
        "Type its name (for example: Pets) and send it. "
        "When you're finished, tap Done.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("✅ Done", callback_data="setupdone")]]
        ),
    )


async def text_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Typed text only matters while the quiz is asking for custom categories."""
    state = context.user_data.get("setup")
    if state is None or not state["typing"]:
        return
    message = update.effective_message
    text = message.text.strip()
    if not 1 <= len(text) <= 20:
        await message.reply_text("Please use a name between 1 and 20 characters.")
        return
    name = "📌 " + text[0].upper() + text[1:]
    if name.lower() in [c.lower() for c in state["custom"]]:
        await message.reply_text("You already added that one 🙂")
        return
    state["custom"].append(name)
    await message.reply_text(f"➕ Added {name}\nType another one, or tap Done above.")


async def setup_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quiz finished: save the list for this person."""
    query = update.callback_query
    await query.answer()
    state = context.user_data.get("setup")
    if state is None:
        await query.edit_message_text("This setup expired. Send /setup to start again.")
        return
    chosen = [DEFAULT_CATEGORIES[i] for i in sorted(state["selected"])] + state["custom"]
    database.save_categories(update.effective_user.id, chosen)
    del context.user_data["setup"]   # throw the sticky note away
    await query.edit_message_text(
        "🎉 All set! Your categories:\n\n" + "\n".join(chosen) +
        "\n\nAdd your first expense:\n/add 12.50 Starbucks"
    )


# ---------------- Expenses ----------------

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/add 12.50 Starbucks -> remember it, then ask for a category."""
    categories = database.get_categories(update.effective_user.id)
    if not categories:
        await update.message.reply_text("Let's set up your categories first: /setup")
        return

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
    context.user_data["pending"] = {
        "amount": amount, "merchant": merchant, "choices": categories,
    }

    buttons = [
        InlineKeyboardButton(name, callback_data=f"cat:{i}")
        for i, name in enumerate(categories)
    ]
    await update.message.reply_text(
        f"💳 ${amount:.2f} at {merchant}\nPick a category:",
        reply_markup=InlineKeyboardMarkup(in_rows(buttons)),
    )


async def category_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Runs when the user taps a category button after /add."""
    query = update.callback_query
    await query.answer()   # tells Telegram "button press received"

    pending = context.user_data.get("pending")
    index = int(query.data.split(":", 1)[1])
    if pending is None or index >= len(pending["choices"]):
        await query.edit_message_text("That expense expired. Send /add again.")
        return

    category = pending["choices"][index]
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
app.add_handler(CommandHandler("setup", setup))
app.add_handler(CommandHandler("add", add))
app.add_handler(CommandHandler("last", last))
app.add_handler(CommandHandler("undo", undo))
app.add_handler(CallbackQueryHandler(pick_toggled, pattern="^pick:"))
app.add_handler(CallbackQueryHandler(pick_done, pattern="^pickdone$"))
app.add_handler(CallbackQueryHandler(setup_done, pattern="^setupdone$"))
app.add_handler(CallbackQueryHandler(category_chosen, pattern="^cat:"))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_received))
app.run_polling()