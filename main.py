import json
import os
import requests
import logging
from typing import Final
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.error import BadRequest
from collections import defaultdict

TOKEN: Final = os.getenv("TOKEN")
BOT_USERNAME: Final = '@split_shark_bot'
API_KEY = os.getenv("FREE_CURRENCY_API_KEY")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

def get_exchange_rate(base_currency, target_currency):
    try:
        api_key = os.getenv("FREE_CURRENCY_API_KEY")  # Store API key in an environment variable
        if not api_key:
            print("API key is missing. Set the FREE_CURRENCY_API_KEY environment variable.")
            return None
        
        url = f"https://api.freecurrencyapi.com/v1/latest?apikey={api_key}"
        response = requests.get(url)
        response.raise_for_status()  # Check for HTTP errors (4xx or 5xx)

        data = response.json()

        if "error" in data:
            print(f"API Error: {data['error'].get('message', 'Unknown API error')}")
            return None

        rates = data.get("data")  # FreeCurrencyAPI uses "data" instead of "rates"
        if not rates:
            print("No exchange rate data found.")
            return None

        if base_currency not in rates or target_currency not in rates:
            print(f"Base or target currency not found in response: {base_currency}, {target_currency}")
            return None

        # Convert base_currency to target_currency
        exchange_rate = rates[target_currency] / rates[base_currency]
        return exchange_rate

    except requests.exceptions.RequestException as e:
        print(f"Request Error: {e}")
        return None
    except (KeyError, TypeError) as e:
        print(f"JSON Error: {e}")
        return None
    except Exception as e:
        print(f"General Error: {e}")
        return None

    
# Individual Commands
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("To use Split Shark, add @split_shark_bot into your group chat. Click on /userguide to see how to use this bot!")

async def user_guide_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("How to use Split Shark \n 1. Add @split_shark_bot into a telegram group chat \n 2. Use /setcurrency to set the currency before adding any expenses \n 3. Use /add_expense to record a new transaction \n 4. Use /calculate_balances to check existing balance \n 5. Check balance in another currency using /exchangebal <target_currency>")

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f'Update {update} caused error {context.error}')

user_states = {}
#Group chat commands

async def get_group_members(group_id, context):
    try:
        # Get the list of chat administrators (more reliable than fetching all members)
        admins = await context.bot.get_chat_administrators(chat_id=group_id)
        bot_username = context.bot.username
        members = [
            f"@{admin.user.username}" if admin.user.username else admin.user.full_name
            for admin in admins if admin.user.username != bot_username
        ]
        return members
    except BadRequest as e:
        print(f"Failed to fetch group members: {e}")
        return []

# Create a function to load config
def load_config():
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
            # Migrate old format to new format if needed
            if isinstance(config.get("currency"), str):
                config = {"group_currencies": {}}
            if "group_currencies" not in config:
                config["group_currencies"] = {}
            return config
    except FileNotFoundError:
        # Create new config with group_currencies structure
        default_config = {"group_currencies": {}}
        with open("config.json", "w") as f:
            json.dump(default_config, f)
        return default_config
    except json.JSONDecodeError:
        return {"group_currencies": {}}

def save_config(config):
    try:
        with open("config.json", "w") as f:
            json.dump(config, f)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

async def set_currency_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != "group":
        await update.message.reply_text("To use Split Shark, add @split_shark_bot into your group chat")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Please provide a currency code, e.g., `/setcurrency SGD`")
        return
    
    group_id = str(update.message.chat_id)
    currency = context.args[0].upper()  # Convert to uppercase
    
    try:
        # Load current config
        config = load_config()
        
        # Set currency for this specific group
        config["group_currencies"][group_id] = currency
        
        # Save updated config
        if save_config(config):
            await update.message.reply_text(f"Currency set to {currency}. All expenses in this group will now follow this currency.")
        else:
            await update.message.reply_text("Failed to set currency. Please try again.")
    
    except Exception as e:
        print(f"Error in set_currency_command: {e}")
        await update.message.reply_text("An error occurred while setting the currency. Please try again.")

async def get_currency(group_id):
    try:
        config = load_config()
        return config["group_currencies"].get(str(group_id), "SGD")  # Default to SGD if not set
    except Exception as e:
        print(f"Error getting currency: {e}")
        return "SGD"  # Default to SGD in case of error

async def add_expense_record_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    group_id = str(update.message.chat_id)

    if update.message.chat.type != "group":
        await update.message.reply_text("To use Split Shark, add @split_shark_bot into your group chat")
        return

    # Load config to check if currency is set for this group
    config = load_config()
    if group_id not in config["group_currencies"]:
        await update.message.reply_text("Please set a currency first using /setcurrency before adding expenses")
        return
    
    user_states[user_id] = {"state": "waiting_for_expense_name", "data": {}}
    await update.message.reply_text("What is the name of the expense?")

async def show_currency_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != "group":
        await update.message.reply_text("To use Split Shark, add @split_shark_bot into your group chat")
        return
    
    group_id = str(update.message.chat_id)
    currency = await get_currency(group_id)
    await update.message.reply_text(f"Current group currency is set to: {currency}")

##add expense record
async def add_expense_record_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    group_id = str(update.message.chat_id)

    if update.message.chat.type != "group":
        await update.message.reply_text("To use Split Shark, add @split_shark_bot into your group chat")
        return

    # Load config to check if currency is set for this group
    config = load_config()
    if group_id not in config["group_currencies"]:
        await update.message.reply_text("Please set a currency first using /setcurrency before adding expenses")
        return
    
    # Initialize the state with both state and data
    user_states[user_id] = {
        "state": "waiting_for_expense_name",
        "data": {"group_id": group_id}
    }
    
    print(f"Initialized state for user {user_id}: {user_states[user_id]}")  # Debug print
    await update.message.reply_text("What is the name of the expense?")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug("handle_text was called!")
    user_id = update.effective_user.id
    message_text = update.message.text
    
    logger.debug(f"Received message: {message_text} from user: {user_id}")
    logger.debug(f"Current user_states: {user_states}")
    
    if user_id not in user_states:
        logger.debug(f"No state found for user {user_id}")
        return
        
    state = user_states[user_id].get("state")
    logger.debug(f"Current state for user {user_id}: {state}")

    if state == "waiting_for_expense_name":
        await handle_expense_name(update, context)
    elif state == "waiting_for_amount":
        await handle_amount(update, context)

async def handle_expense_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    group_id = str(update.message.chat_id)
    
    print(f"Handling expense name for user {user_id}")  # Debug print
    
    try:
        # Get group members
        members = await get_group_members(group_id, context)
        
        if not members:
            await update.message.reply_text("No group members found. Please make sure the bot is an admin.")
            return
            
        # Save expense name
        expense_name = update.message.text
        if not expense_name:
            await update.message.reply_text("Please provide a valid expense name.")
            return
            
        user_states[user_id]["data"]["expense_name"] = expense_name
        
        # Create keyboard
        keyboard = []
        # Put 2 members per row
        for i in range(0, len(members), 2):
            row = []
            row.append(InlineKeyboardButton(members[i], callback_data=f"paid_by:{members[i]}"))
            if i + 1 < len(members):  # If there's another member to add to the row
                row.append(InlineKeyboardButton(members[i+1], callback_data=f"paid_by:{members[i+1]}"))
            keyboard.append(row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Update state
        user_states[user_id]["state"] = "waiting_for_paid_by"
        
        print(f"Updated state for user {user_id}: {user_states[user_id]}")  # Debug print
        
        await update.message.reply_text(
            f"Expense name: {expense_name}\nWho paid for this expense?",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        print(f"Error in handle_expense_name: {e}")  # Debug print
        await update.message.reply_text("An error occurred. Please try again with /add_expense")
        if user_id in user_states:
            del user_states[user_id]

async def handle_paid_by(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    
    print(f"Handling paid_by for user {user_id}")  # Debug print
    
    try:
        await query.answer()

        if query.data.startswith("paid_by:"):
            paid_by = query.data.split(":")[1]
            user_states[user_id]["data"]["paid_by"] = paid_by
            user_states[user_id]["state"] = "waiting_for_amount"
            
            print(f"Updated state for user {user_id}: {user_states[user_id]}")  # Debug print
            
            await query.edit_message_text(f"Paid by: {paid_by}\nHow much was the expense?")
            
    except Exception as e:
        print(f"Error in handle_paid_by: {e}")  # Debug print
        await query.edit_message_text("An error occurred. Please try again with /add_expense")
        if user_id in user_states:
            del user_states[user_id]

async def handle_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_states.get(user_id, {}).get("state") != "waiting_for_amount":
        return

    try:
        group_id = str(update.message.chat_id)
        members = await get_group_members(group_id, context)
        amount = float(update.message.text)
        if amount <= 0:
            await update.message.reply_text("Amount cannot be less than or equal to 0")
            return
        
        user_states[user_id]["data"]["amount"] = amount
        user_states[user_id]["state"] = "waiting_for_involved"

        await update.message.reply_text(
            "Who were involved in this expense?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(member, callback_data=f"involved:{member}") for member in members],
                [InlineKeyboardButton("Done", callback_data="involved:done")]
            ])
        )
    except ValueError:
        await update.message.reply_text("Please enter a valid number.")

async def handle_involved(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    await query.answer()

    if query.message.chat.type != "group":
        await query.message.reply_text("To use Split Shark, add @split_shark_bot into your group chat")
        return
    group_id = str(query.message.chat_id)  # Convert to string

    currency = await get_currency(group_id)
    members = await get_group_members(group_id, context)

    # Initialize 'involved' key if not already present
    if "involved" not in user_states[user_id]["data"]:
        user_states[user_id]["data"]["involved"] = []

    # Debug: Print the current state
    print(f"User state: {user_states[user_id]}")

    # Process the callback data
    if query.data.startswith("involved:"):
        participant = query.data.split(":")[1]
        if participant == "done":
            record = user_states[user_id]["data"]
            record["group_id"] = group_id

            # Debug: Print the record before saving
            print(f"Record to save: {record}")

            # Save to database and clear the state
            save_expense_record_to_db(record)
            user_states.pop(user_id)

            await query.edit_message_text(
                f"Expense '{record['expense_name']}' of {currency}{record['amount']:.2f} paid by {record['paid_by']} for "
                f"{', '.join(record['involved'])} added!"
            )
        else:
            # Toggle participant selection
            if participant in user_states[user_id]["data"]["involved"]:
                user_states[user_id]["data"]["involved"].remove(participant)
            else:
                user_states[user_id]["data"]["involved"].append(participant)

            # Debug: Print the updated involved list
            print(f"Updated involved: {user_states[user_id]['data']['involved']}")

            # Update message with the selected participants
            selected = user_states[user_id]["data"]["involved"]
            await query.edit_message_text(
                f"Selected: {', '.join(selected) or 'None'}. Select more or click 'Done'.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(member, callback_data=f"involved:{member}") for member in members],
                    [InlineKeyboardButton("Done", callback_data="involved:done")]
                ])
            )

def save_expense_record_to_db(record: dict):
    try:
        conn = sqlite3.connect("expenses.db")
        cursor = conn.cursor()

        # Ensure group_id is a string
        record["group_id"] = str(record["group_id"])

        cursor.execute(
            "INSERT INTO Expenses (group_id, expense_name, paid_by, amount, involved) VALUES (?, ?, ?, ?, ?)",
            (
                record["group_id"],
                record["expense_name"],
                record["paid_by"],
                record["amount"],
                json.dumps(record["involved"])
            )
        )
        conn.commit()
        print("Record saved successfully.")
    except Exception as e:
        print(f"Error saving record to DB: {e}")
    finally:
        conn.close()

async def calculate_balances_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != "group":
        await update.message.reply_text("To use Split Shark, add @split_shark_bot into your group chat")
        return

    group_id = update.message.chat_id
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    # Fetch expenses for the group
    cursor.execute("SELECT paid_by, amount, involved FROM Expenses WHERE group_id = ?", (group_id,))
    expenses = cursor.fetchall()
    conn.close()

    if not expenses:
        await update.message.reply_text("No expenses recorded for this group yet.")
        return

    balances = defaultdict(float)
    expenditures = defaultdict(float)
    currency = await get_currency(group_id)  # Await the currency function to get the actual value

    # Calculate balances and expenditures
    for paid_by, amount, involved_json in expenses:
        involved = json.loads(involved_json)
        share = amount / len(involved)

        # Update total expenditures per person
        expenditures[paid_by] += amount

        # Update balances
        for person in involved:
            if person == paid_by:
                continue
            balances[person] -= share
            balances[paid_by] += share

    # Optimize transactions using a settlement algorithm
    creditors = []
    debtors = []
    for user, balance in balances.items():
        if balance > 0:
            creditors.append((user, balance))
        elif balance < 0:
            debtors.append((user, -balance))

    transactions = []
    while creditors and debtors:
        creditor, credit_amount = creditors.pop()
        debtor, debt_amount = debtors.pop()

        settlement_amount = min(credit_amount, debt_amount)
        transactions.append(f"{debtor} owes {creditor} {currency} {settlement_amount:.2f}")

        # Update remaining balances
        credit_amount -= settlement_amount
        debt_amount -= settlement_amount

        if credit_amount > 0:
            creditors.append((creditor, credit_amount))
        if debt_amount > 0:
            debtors.append((debtor, debt_amount))

    # Add total expenditures per person
    expenditures_summary = ["\nTotal Expenditures:"]
    for user, amount in expenditures.items():
        expenditures_summary.append(f"{user}: {currency} {amount:.2f}")

    # Prepare and send the message
    message = "\n".join(transactions + expenditures_summary)
    await update.message.reply_text(message or "No balances to display.")

async def calculate_balance_ex_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != "group":
        await update.message.reply_text("To use Split Shark, add @split_shark_bot into your group chat.")
        return
    
    group_id = update.message.chat_id
    currency = await get_currency(group_id)
    if not currency:
        await update.message.reply_text("Group currency not set. Please set it first.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Please specify the target currency, e.g., `/exchangebal EUR`.")
        return

    target_currency = context.args[0].upper()
    exchange_rate = get_exchange_rate(currency, target_currency)

    if exchange_rate is None:
        await update.message.reply_text("Invalid currency code or unable to fetch exchange rate. Please try again.")
        return

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute("SELECT paid_by, amount, involved FROM Expenses WHERE group_id = ?", (group_id,))
    expenses = cursor.fetchall()
    conn.close()

    if not expenses:
        await update.message.reply_text("No expenses recorded for this group yet.")
        return

    balances = defaultdict(float)
    expenditures = defaultdict(float)

    for paid_by, amount, involved_json in expenses:
        involved = json.loads(involved_json)
        # Convert amount to target currency *before* calculating shares
        converted_amount = amount * exchange_rate  # Convert here!
        share = converted_amount / len(involved)

        expenditures[paid_by] += converted_amount  # Store converted amount

        for person in involved:
            if person == paid_by:
                continue
            balances[person] -= share
            balances[paid_by] += share

    # Initialize creditors and debtors
    creditors = []
    debtors = []
    for user, balance in balances.items():
        if balance > 0:
            creditors.append((user, balance))
        elif balance < 0:
            debtors.append((user, -balance))

    transactions = []
    while creditors and debtors:
        creditor, credit_amount = creditors.pop()
        debtor, debt_amount = debtors.pop()

        settlement_amount = min(credit_amount, debt_amount)
        transactions.append(
            f"{debtor} owes {creditor} {target_currency} {settlement_amount:.2f} "
            f"(at 1 {currency} = {exchange_rate:.2f} {target_currency})"
        )

        # Update remaining balances
        credit_amount -= settlement_amount
        debt_amount -= settlement_amount

        if credit_amount > 0:
            creditors.append((creditor, credit_amount))
        if debt_amount > 0:
            debtors.append((debtor, debt_amount))

    # Add total expenditures per person
    expenditures_summary = [f"\nTotal Expenditures (converted to {target_currency}):"]
    for user, amount in expenditures.items():
        expenditures_summary.append(f"{user}: {amount:.2f} {target_currency}")

    # Prepare and send the message
    message = transactions + expenditures_summary
    await update.message.reply_text("\n".join(message) or "No balances to display.")

if __name__ == '__main__':
    print('Starting bot ...')
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('user_guide', user_guide_command))
    app.add_handler(CommandHandler('add_expense', add_expense_record_command))
    app.add_handler(CommandHandler('setcurrency', set_currency_command))
    app.add_handler(CommandHandler('showcurrency', show_currency_command))
    app.add_handler(CommandHandler('calculate_balances', calculate_balances_command))
    app.add_handler(CommandHandler('exchangebal', calculate_balance_ex_command))

    # Message handlers (for text inputs during states)
    app.add_handler(MessageHandler(
    filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUP,
    handle_text,
    block=False
))

    # CallbackQuery handlers (for inline keyboards)
    app.add_handler(CallbackQueryHandler(handle_paid_by, pattern='^paid_by:'))
    app.add_handler(CallbackQueryHandler(handle_involved, pattern='^involved:'))

    app.add_error_handler(error)

    print('Polling')
    app.run_polling(poll_interval=3)