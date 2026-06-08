import logging
import os
from datetime import date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set!")

# ── Conversation states ──────────────────────────────────────────────────────
(
    ASK_NAME,
    MAIN_MENU,
    BOOK_SERVICE,
    BOOK_FULL_NAME,
    BOOK_EMAIL,
    BOOK_PHONE,
    BOOK_BANK,
    BOOK_DATE,
    BOOK_TIME,
    BOOK_CONFIRM,
) = range(10)


# ── Static texts ─────────────────────────────────────────────────────────────

HOME_TEXT = (
    "_Your smile, our priority_\n"
    "\n"
    "*🦷 Gentle Care, Beautiful Smiles*\n"
    "\n"
    "At Care Dental Clinic, we combine compassionate care with modern dentistry "
    "to give you a smile you'll love\\. From routine checkups to full smile "
    "makeovers — we're here for every step\\."
)

SERVICES_TEXT = (
    "_What we offer_\n"
    "\n"
    "*Our Services*\n"
    "\n"
    "From routine checkups to complete smile makeovers, we offer a full range "
    "of dental treatments tailored to your needs\\."
)

ABOUT_TEXT = (
    "_About Us_\n"
    "\n"
    "*Dedicated to Your Dental Health \\& Wellbeing*\n"
    "\n"
    "Care Dental Clinic was founded on a simple belief — that every person "
    "deserves exceptional dental care in a welcoming, stress\\-free environment\\. "
    "Our experienced team combines the latest clinical techniques with a genuinely "
    "compassionate approach, ensuring every visit feels comfortable, personal, and "
    "professional\\. We are proud to serve our community and committed to building "
    "lasting relationships with every patient we treat\\.\n"
    "\n"
    "`10+ Years of Experience`\n"
    "`1,000+ Happy Patients`\n"
    "`97% Patient Satisfaction`\n"
    "\n"
    "_Our Mission_\n"
    "To provide every patient with personalised, compassionate dental care that "
    "prioritises their comfort, health, and confidence\\. We strive to make "
    "high\\-quality dentistry accessible, transparent, and genuinely life\\-changing "
    "— one smile at a time\\.\n"
    "\n"
    "_Our Vision_\n"
    "To be the most trusted dental clinic in our community — known not just for "
    "clinical excellence, but for the warmth, integrity, and dedication we bring "
    "to every patient relationship\\. We envision a future where everyone smiles "
    "with complete confidence\\."
)

CONTACT_TEXT = (
    "_Get in Touch_\n"
    "\n"
    "*Contact Care Dental Clinic*\n"
    "\n"
    "📞  \\+251 911 234 567\n"
    "📧  hello@caredental\\.et\n"
    "💬  @CareDentalClinic"
)

# Services list (shared between display & booking)
SERVICES = [
    ("✨", "Teeth Whitening"),
    ("🦷", "Dental Implants"),
    ("🛡️", "Preventive Care"),
    ("😁", "Smile Makeover"),
    ("📐", "Orthodontics"),
    ("🔬", "Root Canal Therapy"),
    ("💎", "Cosmetic Dentistry"),
    ("🚨", "Emergency Care"),
]

# Bank accounts: name → (account_number, account_holder)
BANKS = {
    "Telebirr":    ("0911 234 567",      "Care Dental Clinic"),
    "Awash Bank":  ("0134 5678 9012 3",  "Care Dental Clinic PLC"),
    "CBE Birr":    ("1000 4567 8901 23", "Care Dental Clinic PLC"),
    "Zemen Bank":  ("2580 1234 5678 9",  "Care Dental Clinic"),
    "Tsedey Bank": ("3690 8765 4321 0",  "Care Dental Clinic"),
    "Dashen Bank": ("4801 2345 6789 0",  "Care Dental Clinic PLC"),
    "Wegagen Bank":("5912 3456 7890 1",  "Care Dental Clinic"),
}

TIME_SLOTS = [
    "9:00 AM", "10:00 AM", "11:00 AM", "12:00 PM",
    "1:00 PM", "2:00 PM", "3:00 PM", "4:00 PM",
    "5:00 PM", "6:00 PM",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def esc(text: str) -> str:
    """Escape a plain string for MarkdownV2."""
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in text)


def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏠 Home",     callback_data="nav:home"),
            InlineKeyboardButton("🦷 Services", callback_data="nav:services"),
        ],
        [
            InlineKeyboardButton("ℹ️ About",    callback_data="nav:about"),
            InlineKeyboardButton("📞 Contact",  callback_data="nav:contact"),
        ],
        [
            InlineKeyboardButton("📅 Book an Appointment", callback_data="book:start"),
        ],
    ])


def services_display_keyboard():
    """Services page — non-clickable service tiles + Book + Back."""
    rows = [
        [
            InlineKeyboardButton(f"{SERVICES[i][0]} {SERVICES[i][1]}", callback_data="noop"),
            InlineKeyboardButton(f"{SERVICES[i+1][0]} {SERVICES[i+1][1]}", callback_data="noop"),
        ]
        for i in range(0, len(SERVICES), 2)
    ]
    rows.append([InlineKeyboardButton("📅 Book an Appointment", callback_data="book:start")])
    rows.append([InlineKeyboardButton("🏠 ← Back to Home",      callback_data="nav:home")])
    return InlineKeyboardMarkup(rows)


def back_with_book_keyboard():
    """About / Contact pages — Book + Back."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Book an Appointment", callback_data="book:start")],
        [InlineKeyboardButton("🏠 ← Back to Home",      callback_data="nav:home")],
    ])


def booking_services_keyboard():
    """Step 1 — clickable service selection."""
    rows = [
        [
            InlineKeyboardButton(f"{SERVICES[i][0]} {SERVICES[i][1]}",   callback_data=f"bsvc:{SERVICES[i][1]}"),
            InlineKeyboardButton(f"{SERVICES[i+1][0]} {SERVICES[i+1][1]}", callback_data=f"bsvc:{SERVICES[i+1][1]}"),
        ]
        for i in range(0, len(SERVICES), 2)
    ]
    rows.append([InlineKeyboardButton("❌ Cancel Booking", callback_data="book:cancel")])
    return InlineKeyboardMarkup(rows)


def bank_keyboard():
    """Step 5 — bank selection."""
    rows = [[InlineKeyboardButton(name, callback_data=f"bank:{name}")] for name in BANKS]
    rows.append([InlineKeyboardButton("❌ Cancel Booking", callback_data="book:cancel")])
    return InlineKeyboardMarkup(rows)


def bank_chosen_keyboard(bank_name: str):
    """After bank selected — show it as selected + continue."""
    rows = [[InlineKeyboardButton(f"✅ {bank_name}", callback_data="noop")]]
    rows.append([InlineKeyboardButton("➡️ Continue to Date", callback_data="book:to_date")])
    rows.append([InlineKeyboardButton("❌ Cancel Booking",   callback_data="book:cancel")])
    return InlineKeyboardMarkup(rows)


def date_keyboard():
    """Step 6 — next 30 days as inline buttons, 3 per row."""
    today = date.today()
    days = [today + timedelta(days=i) for i in range(30)]
    rows = []
    for i in range(0, len(days), 3):
        row = []
        for d in days[i:i+3]:
            label = f"{d.strftime('%a')} {d.strftime('%d/%m')}"
            row.append(InlineKeyboardButton(label, callback_data=f"date:{d.isoformat()}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("❌ Cancel Booking", callback_data="book:cancel")])
    return InlineKeyboardMarkup(rows)


def time_keyboard():
    """Step 7 — time slots, 2 per row."""
    rows = []
    for i in range(0, len(TIME_SLOTS), 2):
        row = [InlineKeyboardButton(TIME_SLOTS[i], callback_data=f"time:{TIME_SLOTS[i]}")]
        if i + 1 < len(TIME_SLOTS):
            row.append(InlineKeyboardButton(TIME_SLOTS[i+1], callback_data=f"time:{TIME_SLOTS[i+1]}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("❌ Cancel Booking", callback_data="book:cancel")])
    return InlineKeyboardMarkup(rows)


def confirm_keyboard():
    """Step 8 — final confirm."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm Booking", callback_data="book:confirm")],
        [InlineKeyboardButton("❌ Cancel Booking",  callback_data="book:cancel")],
    ])


# ── /start ────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "👋 *Hello\\! Welcome to Care Dental Clinic\\!*\n\nWhat's your name?",
        parse_mode="MarkdownV2",
    )
    return ASK_NAME


async def got_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    context.user_data["name"] = name
    await update.message.reply_text(
        f"Nice to meet you, *{esc(name)}\\!* 🎉\n\n" + HOME_TEXT,
        parse_mode="MarkdownV2",
        reply_markup=main_menu_keyboard(),
    )
    return MAIN_MENU


# ── Nav handler ───────────────────────────────────────────────────────────────

async def nav_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    dest = query.data.split(":", 1)[1]
    name = context.user_data.get("name", "")

    if dest == "home":
        greeting = f"_Welcome back, {esc(name)}\\!_\n\n" if name else ""
        await query.edit_message_text(
            greeting + HOME_TEXT,
            parse_mode="MarkdownV2",
            reply_markup=main_menu_keyboard(),
        )
    elif dest == "services":
        await query.edit_message_text(
            SERVICES_TEXT,
            parse_mode="MarkdownV2",
            reply_markup=services_display_keyboard(),
        )
    elif dest == "about":
        await query.edit_message_text(
            ABOUT_TEXT,
            parse_mode="MarkdownV2",
            reply_markup=back_with_book_keyboard(),
        )
    elif dest == "contact":
        await query.edit_message_text(
            CONTACT_TEXT,
            parse_mode="MarkdownV2",
            reply_markup=back_with_book_keyboard(),
        )
    return MAIN_MENU


# ── Booking: step 1 — service selection ──────────────────────────────────────

async def book_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.pop("booking", None)   # clear any previous booking draft
    await query.edit_message_text(
        "📅 *Book an Appointment*\n\n_Step 1 of 7_ — Please choose a service:",
        parse_mode="MarkdownV2",
        reply_markup=booking_services_keyboard(),
    )
    return BOOK_SERVICE


async def book_service_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    service = query.data.split(":", 1)[1]
    context.user_data.setdefault("booking", {})["service"] = service
    await query.edit_message_text(
        f"✅ Service: *{esc(service)}*\n\n"
        "_Step 2 of 7_ — Please enter your *full name*\\.\n\n"
        "📝 Example: `John Doe`",
        parse_mode="MarkdownV2",
    )
    return BOOK_FULL_NAME


# ── Booking: step 2 — full name ───────────────────────────────────────────────

async def book_got_fullname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    full_name = update.message.text.strip()
    context.user_data.setdefault("booking", {})["full_name"] = full_name
    await update.message.reply_text(
        f"✅ Name: *{esc(full_name)}*\n\n"
        "_Step 3 of 7_ — Please enter your *email address*\\.\n\n"
        "📝 Example: `johndoe@email.com`",
        parse_mode="MarkdownV2",
    )
    return BOOK_EMAIL


# ── Booking: step 3 — email ───────────────────────────────────────────────────

async def book_got_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    email = update.message.text.strip()
    context.user_data.setdefault("booking", {})["email"] = email
    await update.message.reply_text(
        f"✅ Email: *{esc(email)}*\n\n"
        "_Step 4 of 7_ — Please enter your *phone number*\\.\n\n"
        "📝 Example: `+251911223344` or `+251711223344`",
        parse_mode="MarkdownV2",
    )
    return BOOK_PHONE


# ── Booking: step 4 — phone ───────────────────────────────────────────────────

async def book_got_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone = update.message.text.strip()
    context.user_data.setdefault("booking", {})["phone"] = phone
    await update.message.reply_text(
        f"✅ Phone: *{esc(phone)}*\n\n"
        "_Step 5 of 7_ — Please select your *payment bank*\\:",
        parse_mode="MarkdownV2",
        reply_markup=bank_keyboard(),
    )
    return BOOK_BANK


# ── Booking: step 5 — bank selection ─────────────────────────────────────────

async def book_bank_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    bank_name = query.data.split(":", 1)[1]
    account_no, account_holder = BANKS[bank_name]
    context.user_data.setdefault("booking", {})["bank"] = bank_name

    await query.edit_message_text(
        f"✅ Bank: *{esc(bank_name)}*\n\n"
        f"_Please send your payment to the account below, then continue\\._\n\n"
        f"🏦 *Account Number:*\n`{esc(account_no)}`\n\n"
        f"👤 *Account Holder:* {esc(account_holder)}\n\n"
        f"_Tap the account number above to copy it\\._",
        parse_mode="MarkdownV2",
        reply_markup=bank_chosen_keyboard(bank_name),
    )
    return BOOK_DATE


async def book_to_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "_Step 6 of 7_ — Please choose your *preferred date*\\:",
        parse_mode="MarkdownV2",
        reply_markup=date_keyboard(),
    )
    return BOOK_DATE


# ── Booking: step 6 — date selection ─────────────────────────────────────────

async def book_date_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    chosen_date = query.data.split(":", 1)[1]   # ISO format: YYYY-MM-DD
    d = date.fromisoformat(chosen_date)
    label = d.strftime("%A, %d %B %Y")
    context.user_data.setdefault("booking", {})["date"] = label
    await query.edit_message_text(
        f"✅ Date: *{esc(label)}*\n\n"
        "_Step 7 of 7_ — Please choose your *preferred time*\\:",
        parse_mode="MarkdownV2",
        reply_markup=time_keyboard(),
    )
    return BOOK_TIME


# ── Booking: step 7 — time selection ─────────────────────────────────────────

async def book_time_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    chosen_time = query.data.split(":", 1)[1]
    context.user_data.setdefault("booking", {})["time"] = chosen_time
    b = context.user_data["booking"]

    summary = (
        "📋 *Booking Summary*\n\n"
        f"🦷 *Service:*   {esc(b['service'])}\n"
        f"👤 *Name:*      {esc(b['full_name'])}\n"
        f"📧 *Email:*     {esc(b['email'])}\n"
        f"📞 *Phone:*     {esc(b['phone'])}\n"
        f"🏦 *Bank:*      {esc(b['bank'])}\n"
        f"📅 *Date:*      {esc(b['date'])}\n"
        f"🕐 *Time:*      {esc(b['time'])}\n\n"
        "_Please review your details above and tap *Confirm Booking* to finalise\\._"
    )
    await query.edit_message_text(
        summary,
        parse_mode="MarkdownV2",
        reply_markup=confirm_keyboard(),
    )
    return BOOK_CONFIRM


# ── Booking: step 8 — confirm ─────────────────────────────────────────────────

async def book_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    b = context.user_data.get("booking", {})
    name = context.user_data.get("name", "")

    await query.edit_message_text(
        f"🎉 *Booking Confirmed, {esc(name)}\\!*\n\n"
        f"Your appointment for *{esc(b.get('service',''))}* has been received\\.\n\n"
        f"📅 *{esc(b.get('date',''))}* at *{esc(b.get('time',''))}*\n\n"
        "Our team will reach out to confirm your slot shortly\\. "
        "Thank you for choosing Care Dental Clinic\\! 🦷✨",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Back to Home", callback_data="nav:home")]
        ]),
    )
    context.user_data.pop("booking", None)
    return MAIN_MENU


# ── Booking: cancel ───────────────────────────────────────────────────────────

async def book_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.pop("booking", None)
    name = context.user_data.get("name", "")
    greeting = f"_Welcome back, {esc(name)}\\!_\n\n" if name else ""
    await query.edit_message_text(
        greeting + HOME_TEXT,
        parse_mode="MarkdownV2",
        reply_markup=main_menu_keyboard(),
    )
    return MAIN_MENU


# ── Noop ──────────────────────────────────────────────────────────────────────

async def noop_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    return MAIN_MENU


# ── /cancel command ───────────────────────────────────────────────────────────

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Cancelled\\. Type /start to begin again\\.", parse_mode="MarkdownV2"
    )
    return ConversationHandler.END


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, got_name),
            ],
            MAIN_MENU: [
                CallbackQueryHandler(nav_handler,   pattern="^nav:"),
                CallbackQueryHandler(book_start,    pattern="^book:start$"),
                CallbackQueryHandler(noop_handler,  pattern="^noop$"),
            ],
            BOOK_SERVICE: [
                CallbackQueryHandler(book_service_chosen, pattern="^bsvc:"),
                CallbackQueryHandler(book_cancel,         pattern="^book:cancel$"),
            ],
            BOOK_FULL_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, book_got_fullname),
            ],
            BOOK_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, book_got_email),
            ],
            BOOK_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, book_got_phone),
            ],
            BOOK_BANK: [
                CallbackQueryHandler(book_bank_chosen, pattern="^bank:"),
                CallbackQueryHandler(book_to_date,     pattern="^book:to_date$"),
                CallbackQueryHandler(book_cancel,      pattern="^book:cancel$"),
            ],
            BOOK_DATE: [
                CallbackQueryHandler(book_to_date,    pattern="^book:to_date$"),
                CallbackQueryHandler(book_date_chosen, pattern="^date:"),
                CallbackQueryHandler(book_cancel,      pattern="^book:cancel$"),
            ],
            BOOK_TIME: [
                CallbackQueryHandler(book_time_chosen, pattern="^time:"),
                CallbackQueryHandler(book_cancel,      pattern="^book:cancel$"),
            ],
            BOOK_CONFIRM: [
                CallbackQueryHandler(book_confirm, pattern="^book:confirm$"),
                CallbackQueryHandler(book_cancel,  pattern="^book:cancel$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)

    PORT = int(os.environ.get("PORT", 8443))
    logger.info("Care Dental Clinic bot running via webhook...")
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"https://care-dental-bot-naq9.onrender.com/{TOKEN}",
    )


if __name__ == "__main__":
    main()
