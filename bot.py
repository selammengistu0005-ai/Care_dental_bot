import logging
import os
import threading
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

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
    BOOK_NOTES,
    BOOK_BANK,
    BOOK_DATE,
    BOOK_TIME,
    BOOK_CONFIRM,
    BOOK_UPLOAD,
) = range(12)


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
    "of dental treatments tailored to your needs\\.\n"
    "\n"
    "✨ *Teeth Whitening* — Brighten your smile up to 8 shades\\.\n"
    "🦷 *Dental Implants* — Permanent, natural\\-looking replacements\\.\n"
    "🛡️ *Preventive Care* — Routine checkups and cleanings\\.\n"
    "😁 *Smile Makeover* — Personalised combination of treatments\\.\n"
    "📐 *Orthodontics* — Braces, aligners and bite correction\\.\n"
    "🔬 *Root Canal Therapy* — Relieve pain and save your natural tooth\\.\n"
    "💎 *Cosmetic Dentistry* — Veneers, bonding, contouring and more\\.\n"
    "🚨 *Emergency Care* — Prompt care when you need it most\\."
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

TEAM_TEXT = (
    "_Our Team_\n"
    "\n"
    "*Experienced, Caring, Dedicated*\n"
    "\n"
    "Behind every great smile is a passionate team of dental professionals "
    "committed to your health and comfort\\. Our diverse specialists work "
    "together seamlessly to deliver a complete, personalised care experience\\.\n"
    "\n"
    "🦷 *Dentist* — Comprehensive general and restorative dental care\\.\n"
    "🔪 *Surgeon* — Extractions, implants, and advanced procedures\\.\n"
    "😁 *Orthodontist* — Braces, aligners, and bite correction specialists\\.\n"
    "🧹 *Hygienist* — Professional cleaning and preventive care\\."
)

CONTACT_TEXT = (
    "_Get in Touch_\n"
    "\n"
    "*Contact Care Dental Clinic*\n"
    "\n"
    "📞  \\+251 911 234 567\n"
    "📞  \\+251 911 098 765\n"
    "📧  hello@caredental\\.et\n"
    "💬  @CareDentalClinic\n"
    "\n"
    "🕐  Mon – Fri: 8:00am – 6:00pm\n"
    "🕐  Sat: 9:00am – 2:00pm\n"
    "\n"
    "📍  24 Bright Smile Avenue, Suite 101,\n"
    "      Downtown, New York, NY 10001"
)

# ── Bookable services (matches website booking modal exactly) ─────────────────
BOOKING_SERVICES = [
    ("✨", "Teeth Whitening",  "60 min"),
    ("🦷", "Dental Implants",  "90 min"),
    ("🛡️", "Preventive Care",  "45 min"),
    ("😁", "Smile Makeover",   "120 min"),
    ("📐", "Orthodontics",     "60 min"),
    ("💉", "Dental Surgery",   "75 min"),
]

# ── Display-only services (Services page) ────────────────────────────────────
DISPLAY_SERVICES = [
    ("✨", "Teeth Whitening"),
    ("🦷", "Dental Implants"),
    ("🛡️", "Preventive Care"),
    ("😁", "Smile Makeover"),
    ("📐", "Orthodontics"),
    ("🔬", "Root Canal Therapy"),
    ("💎", "Cosmetic Dentistry"),
    ("🚨", "Emergency Care"),
]

# ── Bank accounts: name → (account_number, account_holder) ───────────────────
BANKS = {
    "Telebirr":     ("1234 5678 9012",      "Care Dental Clinic"),
    "Awash Bank":   ("0123 4567 8901 2345", "Care Dental Clinic"),
    "CBE Birr":     ("1000 2345 6789 0123", "Care Dental Clinic"),
    "Zemen Bank":   ("2345 6789 0123 4567", "Care Dental Clinic"),
    "Tsedey Bank":  ("3456 7890 1234 5678", "Care Dental Clinic"),
    "Dashen Bank":  ("4567 8901 2345 6789", "Care Dental Clinic"),
    "Wegagen Bank": ("5678 9012 3456 7890", "Care Dental Clinic"),
}

# ── Time slots (matches website exactly — 8 slots, no 1:00 PM or 6:00 PM) ────
TIME_SLOTS = [
    "09:00 AM", "10:00 AM", "11:00 AM", "12:00 PM",
    "02:00 PM", "03:00 PM", "04:00 PM", "05:00 PM",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def esc(text: str) -> str:
    """Escape a plain string for MarkdownV2."""
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in text)


# ── Keyboards ─────────────────────────────────────────────────────────────────

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏠 Home",        callback_data="nav:home"),
            InlineKeyboardButton("🦷 Services",    callback_data="nav:services"),
        ],
        [
            InlineKeyboardButton("ℹ️ About",       callback_data="nav:about"),
            InlineKeyboardButton("📞 Contact",     callback_data="nav:contact"),
        ],
        [
            InlineKeyboardButton("📅 Book an Appointment", callback_data="book:start"),
            InlineKeyboardButton("🦷 Our Services",        callback_data="nav:services"),
        ],
    ])


def services_display_keyboard():
    """Services page — non-clickable service tiles + Book + Back."""
    rows = [
        [
            InlineKeyboardButton(f"{DISPLAY_SERVICES[i][0]} {DISPLAY_SERVICES[i][1]}",   callback_data="noop"),
            InlineKeyboardButton(f"{DISPLAY_SERVICES[i+1][0]} {DISPLAY_SERVICES[i+1][1]}", callback_data="noop"),
        ]
        for i in range(0, len(DISPLAY_SERVICES), 2)
    ]
    rows.append([InlineKeyboardButton("📅 Book an Appointment", callback_data="book:start")])
    rows.append([InlineKeyboardButton("🏠 ← Back to Home",      callback_data="nav:home")])
    return InlineKeyboardMarkup(rows)


def about_keyboard():
    """About page — Meet Our Team + Book + Back."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Meet Our Team",           callback_data="nav:team")],
        [InlineKeyboardButton("📅 Book an Appointment",     callback_data="book:start")],
        [InlineKeyboardButton("🏠 ← Back to Home",          callback_data="nav:home")],
    ])


def team_keyboard():
    """Team page — Book + Back to About."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Book an Appointment", callback_data="book:start")],
        [InlineKeyboardButton("← Back to About",        callback_data="nav:about")],
    ])


def contact_keyboard():
    """Contact page — Get Directions + Book + Back."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📍 Get Directions", url="https://maps.google.com/?q=24+Bright+Smile+Avenue+New+York+NY+10001")],
        [InlineKeyboardButton("📅 Book an Appointment", callback_data="book:start")],
        [InlineKeyboardButton("🏠 ← Back to Home",      callback_data="nav:home")],
    ])


def booking_services_keyboard():
    """Step 1 of 5 — clickable service selection, 2 per row."""
    rows = [
        [
            InlineKeyboardButton(
                f"{BOOKING_SERVICES[i][0]} {BOOKING_SERVICES[i][1]}",
                callback_data=f"bsvc:{BOOKING_SERVICES[i][1]}"
            ),
            InlineKeyboardButton(
                f"{BOOKING_SERVICES[i+1][0]} {BOOKING_SERVICES[i+1][1]}",
                callback_data=f"bsvc:{BOOKING_SERVICES[i+1][1]}"
            ),
        ]
        for i in range(0, len(BOOKING_SERVICES), 2)
    ]
    rows.append([InlineKeyboardButton("❌ Cancel Booking", callback_data="book:cancel")])
    return InlineKeyboardMarkup(rows)


def bank_keyboard():
    """Step 2 of 5 — bank selection, 2 per row to match website grid."""
    bank_names = list(BANKS.keys())
    rows = []
    for i in range(0, len(bank_names), 2):
        row = [InlineKeyboardButton(bank_names[i], callback_data=f"bank:{bank_names[i]}")]
        if i + 1 < len(bank_names):
            row.append(InlineKeyboardButton(bank_names[i + 1], callback_data=f"bank:{bank_names[i + 1]}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("❌ Cancel Booking", callback_data="book:cancel")])
    return InlineKeyboardMarkup(rows)


def date_keyboard():
    """Step 3 of 5 — next 30 days, 3 per row."""
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
    """Step 3 of 5 — 8 time slots, 2 per row (matches website exactly)."""
    rows = []
    for i in range(0, len(TIME_SLOTS), 2):
        row = [InlineKeyboardButton(TIME_SLOTS[i], callback_data=f"time:{TIME_SLOTS[i]}")]
        if i + 1 < len(TIME_SLOTS):
            row.append(InlineKeyboardButton(TIME_SLOTS[i + 1], callback_data=f"time:{TIME_SLOTS[i + 1]}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("❌ Cancel Booking", callback_data="book:cancel")])
    return InlineKeyboardMarkup(rows)


def confirm_keyboard():
    """Step 4 of 5 — requires acknowledgment before final confirm."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("☑️ I confirm all information is correct", callback_data="book:acknowledged")],
        [InlineKeyboardButton("← Back", callback_data="book:back_to_time")],
    ])


def confirm_ready_keyboard():
    """Step 4 of 5 — shown after acknowledgment checkbox is ticked."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm Booking", callback_data="book:confirm")],
        [InlineKeyboardButton("← Back",             callback_data="book:back_to_time")],
    ])


def upload_keyboard():
    """Step 5 of 5 — prompt to send payment screenshot."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel Booking", callback_data="book:cancel")],
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
            reply_markup=about_keyboard(),
        )

    elif dest == "team":
        await query.edit_message_text(
            TEAM_TEXT,
            parse_mode="MarkdownV2",
            reply_markup=team_keyboard(),
        )

    elif dest == "contact":
        await query.edit_message_text(
            CONTACT_TEXT,
            parse_mode="MarkdownV2",
            reply_markup=contact_keyboard(),
        )

    return MAIN_MENU


# ── Booking: step 1 of 5 — service selection ─────────────────────────────────

async def book_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.pop("booking", None)
    await query.edit_message_text(
        "📅 *Book an Appointment*\n\n"
        "_Step 1 of 5_ — Please choose a service\\:",
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
        f"✅ *Service:* {esc(service)}\n\n"
        "_Step 2 of 5_ — Please enter your *full name*\\.\n\n"
        "📝 Example: `John Doe`",
        parse_mode="MarkdownV2",
    )
    return BOOK_FULL_NAME


# ── Booking: step 2 of 5 — personal info (name / email / phone / notes) ──────

async def book_got_fullname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    full_name = update.message.text.strip()
    context.user_data.setdefault("booking", {})["full_name"] = full_name
    await update.message.reply_text(
        f"✅ *Name:* {esc(full_name)}\n\n"
        "_Step 2 of 5_ — Please enter your *email address*\\.\n\n"
        "📝 Example: `johndoe@email.com`",
        parse_mode="MarkdownV2",
    )
    return BOOK_EMAIL


async def book_got_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    email = update.message.text.strip()
    context.user_data.setdefault("booking", {})["email"] = email
    await update.message.reply_text(
        f"✅ *Email:* {esc(email)}\n\n"
        "_Step 2 of 5_ — Please enter your *phone number*\\.\n\n"
        "📝 Example: `+251911223344`",
        parse_mode="MarkdownV2",
    )
    return BOOK_PHONE


async def book_got_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone = update.message.text.strip()
    context.user_data.setdefault("booking", {})["phone"] = phone
    await update.message.reply_text(
        f"✅ *Phone:* {esc(phone)}\n\n"
        "_Step 2 of 5_ — Any *optional notes* or requests for your appointment?\n\n"
        "📝 Example: `I have a fear of needles` — or tap *Skip* below\\.",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭️ Skip", callback_data="book:skip_notes")],
            [InlineKeyboardButton("❌ Cancel Booking", callback_data="book:cancel")],
        ]),
    )
    return BOOK_NOTES


async def book_got_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User typed optional notes."""
    notes = update.message.text.strip()
    context.user_data.setdefault("booking", {})["notes"] = notes
    return await _show_bank_selection(update, context, via_query=False)


async def book_skip_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User tapped Skip on the notes step."""
    query = update.callback_query
    await query.answer()
    context.user_data.setdefault("booking", {})["notes"] = ""
    return await _show_bank_selection(update, context, via_query=True)


async def _show_bank_selection(update, context, via_query: bool) -> int:
    """Show bank selection — called after notes (typed or skipped)."""
    b = context.user_data.get("booking", {})
    text = (
        f"✅ *Name:* {esc(b.get('full_name',''))}\n"
        f"✅ *Phone:* {esc(b.get('phone',''))}\n\n"
        "_Step 2 of 5_ — Please select your *payment method*\\:"
    )
    if via_query:
        await update.callback_query.edit_message_text(
            text,
            parse_mode="MarkdownV2",
            reply_markup=bank_keyboard(),
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode="MarkdownV2",
            reply_markup=bank_keyboard(),
        )
    return BOOK_BANK


# ── Booking: step 2 of 5 — bank / payment selection ──────────────────────────

async def book_bank_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    bank_name = query.data.split(":", 1)[1]
    account_no, account_holder = BANKS[bank_name]
    context.user_data.setdefault("booking", {})["bank"] = bank_name

    # Show account details then move straight to Step 3 (Date & Time)
    await query.edit_message_text(
        f"✅ *Payment:* {esc(bank_name)}\n\n"
        f"_Please send your payment to the account below, then choose your date\\._\n\n"
        f"🏦 *Account Number:*\n`{esc(account_no)}`\n\n"
        f"👤 *Account Holder:* {esc(account_holder)}\n\n"
        f"_Tap the account number above to copy it\\._\n\n"
        "_Step 3 of 5_ — Please choose your *preferred date*\\:",
        parse_mode="MarkdownV2",
        reply_markup=date_keyboard(),
    )
    return BOOK_DATE


# ── Booking: step 3 of 5 — date selection ────────────────────────────────────

async def book_date_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    chosen_date = query.data.split(":", 1)[1]
    d = date.fromisoformat(chosen_date)
    label = d.strftime("%A, %d %B %Y")
    context.user_data.setdefault("booking", {})["date"] = label

    # Date selected — immediately show time slots in the same message
    await query.edit_message_text(
        f"✅ *Date:* {esc(label)}\n\n"
        "_Step 3 of 5_ — Please choose your *preferred time*\\:",
        parse_mode="MarkdownV2",
        reply_markup=time_keyboard(),
    )
    return BOOK_TIME


# ── Booking: step 3 of 5 — time selection ────────────────────────────────────

async def book_time_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    chosen_time = query.data.split(":", 1)[1]
    context.user_data.setdefault("booking", {})["time"] = chosen_time
    b = context.user_data["booking"]

    # Step 4 — show summary and ask for acknowledgment before final confirm
    summary = (
        "📋 *Booking Summary — Step 4 of 5*\n\n"
        f"🦷 *Service:*   {esc(b.get('service',''))}\n"
        f"👤 *Name:*      {esc(b.get('full_name',''))}\n"
        f"📧 *Email:*     {esc(b.get('email',''))}\n"
        f"📞 *Phone:*     {esc(b.get('phone',''))}\n"
        + (f"📝 *Notes:*     {esc(b.get('notes',''))}\n" if b.get('notes') else "")
        + f"🏦 *Payment:*   {esc(b.get('bank',''))}\n"
        f"📅 *Date:*      {esc(b.get('date',''))}\n"
        f"🕐 *Time:*      {esc(b.get('time',''))}\n\n"
        "_Please review your details above, then tap the checkbox to confirm\\._"
    )
    await query.edit_message_text(
        summary,
        parse_mode="MarkdownV2",
        reply_markup=confirm_keyboard(),
    )
    return BOOK_CONFIRM


# ── Booking: step 4 of 5 — acknowledgment checkbox ───────────────────────────

async def book_acknowledged(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User ticked the 'I confirm all information is correct' checkbox."""
    query = update.callback_query
    await query.answer("✅ Great! Now tap Confirm Booking to finalise.")
    b = context.user_data.get("booking", {})

    summary = (
        "📋 *Booking Summary — Step 4 of 5*\n\n"
        f"🦷 *Service:*   {esc(b.get('service',''))}\n"
        f"👤 *Name:*      {esc(b.get('full_name',''))}\n"
        f"📧 *Email:*     {esc(b.get('email',''))}\n"
        f"📞 *Phone:*     {esc(b.get('phone',''))}\n"
        + (f"📝 *Notes:*     {esc(b.get('notes',''))}\n" if b.get('notes') else "")
        + f"🏦 *Payment:*   {esc(b.get('bank',''))}\n"
        f"📅 *Date:*      {esc(b.get('date',''))}\n"
        f"🕐 *Time:*      {esc(b.get('time',''))}\n\n"
        "☑️ _All information confirmed\\. Tap *Confirm Booking* to finalise\\._"
    )
    await query.edit_message_text(
        summary,
        parse_mode="MarkdownV2",
        reply_markup=confirm_ready_keyboard(),
    )
    return BOOK_CONFIRM


async def book_back_to_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Back button on confirm screen — returns to time selection."""
    query = update.callback_query
    await query.answer()
    b = context.user_data.get("booking", {})
    await query.edit_message_text(
        f"✅ *Date:* {esc(b.get('date',''))}\n\n"
        "_Step 3 of 5_ — Please choose your *preferred time*\\:",
        parse_mode="MarkdownV2",
        reply_markup=time_keyboard(),
    )
    return BOOK_TIME


async def book_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User tapped Confirm Booking — move to Step 5: upload screenshot."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📤 *Step 5 of 5 — Upload Payment Screenshot*\n\n"
        "Please send your payment screenshot as an *image* to confirm your appointment\\.\n\n"
        "_Your booking will be finalised once we receive your screenshot\\._",
        parse_mode="MarkdownV2",
        reply_markup=upload_keyboard(),
    )
    return BOOK_UPLOAD


# ── Booking: step 5 of 5 — receive payment screenshot ────────────────────────

async def book_got_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User sent a photo as payment proof — finalise booking."""
    b = context.user_data.get("booking", {})
    name = context.user_data.get("name", "")

    await update.message.reply_text(
        f"🎉 *You're All Set, {esc(name)}\\!*\n\n"
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


# ── Health check server (keeps Render web service alive) ─────────────────────

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    PORT = int(os.environ.get("PORT", 10000))
    health_server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    health_thread = threading.Thread(target=health_server.serve_forever, daemon=True)
    health_thread.start()
    logger.info(f"Health check server running on port {PORT}")

    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, got_name),
            ],
            MAIN_MENU: [
                CallbackQueryHandler(nav_handler,  pattern="^nav:"),
                CallbackQueryHandler(book_start,   pattern="^book:start$"),
                CallbackQueryHandler(noop_handler, pattern="^noop$"),
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
            BOOK_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, book_got_notes),
                CallbackQueryHandler(book_skip_notes, pattern="^book:skip_notes$"),
                CallbackQueryHandler(book_cancel,     pattern="^book:cancel$"),
            ],
            BOOK_BANK: [
                CallbackQueryHandler(book_bank_chosen, pattern="^bank:"),
                CallbackQueryHandler(book_cancel,      pattern="^book:cancel$"),
            ],
            BOOK_DATE: [
                CallbackQueryHandler(book_date_chosen, pattern="^date:"),
                CallbackQueryHandler(book_cancel,      pattern="^book:cancel$"),
            ],
            BOOK_TIME: [
                CallbackQueryHandler(book_time_chosen,  pattern="^time:"),
                CallbackQueryHandler(book_cancel,       pattern="^book:cancel$"),
            ],
            BOOK_CONFIRM: [
                CallbackQueryHandler(book_acknowledged, pattern="^book:acknowledged$"),
                CallbackQueryHandler(book_confirm,      pattern="^book:confirm$"),
                CallbackQueryHandler(book_back_to_time, pattern="^book:back_to_time$"),
                CallbackQueryHandler(book_cancel,       pattern="^book:cancel$"),
            ],
            BOOK_UPLOAD: [
                MessageHandler(filters.PHOTO, book_got_screenshot),
                CallbackQueryHandler(book_cancel, pattern="^book:cancel$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start",  start),
        ],
    )

    app.add_handler(conv)

    logger.info("Care Dental Clinic bot running via polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
