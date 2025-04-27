import telegram
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes
import json
import uuid
import os
import re
from datetime import datetime, timedelta
from fpdf import FPDF
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
print(f"Loaded TELEGRAM_TOKEN: {TELEGRAM_TOKEN}")
STELLAR_PUBLIC_KEY = os.getenv('STELLAR_PUBLIC_KEY')
STELLAR_SECRET_KEY = os.getenv('STELLAR_SECRET_KEY')
print(f"Loaded STELLAR_PUBLIC_KEY: {STELLAR_PUBLIC_KEY}")
print(f"Loaded STELLAR_SECRET_KEY: {STELLAR_SECRET_KEY}")

# Admin settings
ADMIN_USER_ID = 359966763  # Replace with your actual Telegram user ID
ADMIN_LOG_FILE = 'admin_log.txt'

# Directory to store EA files
EA_FILES_DIR = 'ea_files'
if not os.path.exists(EA_FILES_DIR):
    os.makedirs(EA_FILES_DIR)

# Bot link for trial version redirection
BOT_LINK = "https://t.me/YourLicenseBot"  # Replace with your actual bot link

# States for conversation
NAME, PRODUCT, PRICING_TIER, PAYMENT, ADMIN_ADD_PRODUCT, ADMIN_ADD_PRODUCT_FILE, ADMIN_EDIT_PRODUCT, ADMIN_EDIT_PRODUCT_ID, ADMIN_EDIT_PRODUCT_FIELD = range(9)

# License and transaction databases
LICENSE_DB = 'licenses.json'
TRANSACTION_DB = 'transactions.json'
PRODUCTS_DB = 'products.json'

# Load products dynamically
def load_products():
    try:
        with open(PRODUCTS_DB, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_products(products):
    with open(PRODUCTS_DB, 'w') as f:
        json.dump(products, f, indent=4)

# Load other databases
def load_licenses():
    try:
        with open(LICENSE_DB, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_licenses(licenses):
    with open(LICENSE_DB, 'w') as f:
        json.dump(licenses, f, indent=4)

def load_transactions():
    try:
        with open(TRANSACTION_DB, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_transactions(transactions):
    with open(TRANSACTION_DB, 'w') as f:
        json.dump(transactions, f, indent=4)

# Log admin actions
def log_admin_action(user_id, action):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(ADMIN_LOG_FILE, 'a') as f:
        f.write(f"[{timestamp}] User {user_id}: {action}\n")

# Test address for simulation
TEST_ADDRESS = "GABCDEFGHIJKLMNOPQRSTUVWXYZ234567ABCDEFGHIJKLMNOPQRSTUVW"

def generate_license_key():
    return str(uuid.uuid4())

def create_pdf_license(license_key, username, expiry, product_name, is_trial=False):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="License Certificate", ln=True, align='C')
    pdf.cell(200, 10, txt=f"Product: {product_name}", ln=True)
    pdf.cell(200, 10, txt=f"Username: {username}", ln=True)
    pdf.cell(200, 10, txt=f"License Key: {license_key}", ln=True)
    pdf.cell(200, 10, txt=f"Expiry: {expiry}", ln=True)
    if is_trial:
        pdf.cell(200, 10, txt=f"Trial Version - Purchase the full version at {BOT_LINK}", ln=True)
    pdf_file = f"license_{license_key}.pdf"
    pdf.output(pdf_file)
    return pdf_file

def check_payment(sender_address):
    print(f"check_payment: Comparing sender_address='{sender_address}' with TEST_ADDRESS='{TEST_ADDRESS}'")
    if sender_address == TEST_ADDRESS:
        return True, "simulated-tx-hash-1234567890"
    return False, None

# Admin commands
async def admin_list_products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("You are not authorized to use this command.")
        return
    
    log_admin_action(update.effective_user.id, "Listed products")
    products = load_products()
    if not products:
        await update.message.reply_text("No products available.")
        return
    
    product_list = "\n".join([f"ID: {key}\nName: {info['name']}\nFile: {info['file']}\n" +
                              (f"Is Trial: {info['is_trial']}\nExpiry Days: {info['expiry_days']}\n" if info.get('is_trial') else
                               "Pricing Tiers:\n" + "\n".join([f"  Tier {t_key}: ${t_info['price_usd']} ({t_info['price_xlm']} XLM, {t_info['expiry_days']} days)"
                                                              for t_key, t_info in info['pricing_tiers'].items()]) + "\n")
                              for key, info in products.items()])
    await update.message.reply_text(f"Products:\n{product_list}")

async def admin_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("You are not authorized to use this command.")
        return ConversationHandler.END
    
    # Clear any ongoing conversation
    context.user_data.clear()
    
    log_admin_action(update.effective_user.id, "Started adding a new product")
    await update.message.reply_text(
        "Let's add a new product.\n"
        "Please provide the product name (e.g., 'MT6 Expert Advisor')."
    )
    context.user_data['admin_product'] = {}
    return ADMIN_ADD_PRODUCT

async def admin_add_product_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if 'name' not in context.user_data['admin_product']:
        context.user_data['admin_product']['name'] = text
        await update.message.reply_text("Please upload the EA file for this product (e.g., 'expert_advisor.ex5').")
        return ADMIN_ADD_PRODUCT_FILE
    
    if 'is_trial' not in context.user_data['admin_product']:
        is_trial = text.lower() == 'yes'
        context.user_data['admin_product']['is_trial'] = is_trial
        if is_trial:
            await update.message.reply_text("Please provide the trial expiry days (e.g., 7).")
        else:
            await update.message.reply_text(
                "Please provide pricing tiers in the format:\n"
                "tier_number,price_usd,price_xlm,expiry_days\n"
                "For example: 1,10,50,30\n"
                "Enter one tier per message. Type 'done' when finished."
            )
        return ADMIN_ADD_PRODUCT
    
    if context.user_data['admin_product']['is_trial']:
        context.user_data['admin_product']['expiry_days'] = int(text)
        product = context.user_data['admin_product']
        products = load_products()
        new_id = str(max([int(k) for k in products.keys()] + [0]) + 1)
        products[new_id] = {
            'name': product['name'],
            'file': product['file'],
            'is_trial': True,
            'expiry_days': product['expiry_days']
        }
        save_products(products)
        log_admin_action(update.effective_user.id, f"Added product ID {new_id}: {product['name']}")
        await update.message.reply_text(f"Product added successfully! ID: {new_id}")
        context.user_data.pop('admin_product', None)
        return ConversationHandler.END
    
    if text.lower() == 'done':
        products = load_products()
        new_id = str(max([int(k) for k in products.keys()] + [0]) + 1)
        products[new_id] = {
            'name': context.user_data['admin_product']['name'],
            'file': context.user_data['admin_product']['file'],
            'pricing_tiers': context.user_data['admin_product'].get('pricing_tiers', {})
        }
        save_products(products)
        log_admin_action(update.effective_user.id, f"Added product ID {new_id}: {context.user_data['admin_product']['name']}")
        await update.message.reply_text(f"Product added successfully! ID: {new_id}")
        context.user_data.pop('admin_product', None)
        return ConversationHandler.END
    
    try:
        tier_number, price_usd, price_xlm, expiry_days = text.split(',')
        tier_number = tier_number.strip()
        price_usd = float(price_usd.strip())
        price_xlm = float(price_xlm.strip())
        expiry_days = int(expiry_days.strip())
        if 'pricing_tiers' not in context.user_data['admin_product']:
            context.user_data['admin_product']['pricing_tiers'] = {}
        context.user_data['admin_product']['pricing_tiers'][tier_number] = {
            'price_usd': price_usd,
            'price_xlm': price_xlm,
            'expiry_days': expiry_days
        }
        await update.message.reply_text("Tier added. Add another tier or type 'done' to finish.")
        return ADMIN_ADD_PRODUCT
    except Exception as e:
        await update.message.reply_text(f"Invalid format: {str(e)}. Please use: tier_number,price_usd,price_xlm,expiry_days (e.g., 1,10,50,30)")
        return ADMIN_ADD_PRODUCT

async def admin_add_product_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.document:
        await update.message.reply_text("Please upload a file (e.g., an .ex4 or .ex5 file).")
        return ADMIN_ADD_PRODUCT_FILE
    
    document = update.message.document
    file_name = document.file_name
    if not (file_name.endswith('.ex4') or file_name.endswith('.ex5')):
        await update.message.reply_text("Please upload a valid EA file (.ex4 or .ex5).")
        return ADMIN_ADD_PRODUCT_FILE
    
    # Download the file
    file = await document.get_file()
    file_path = os.path.join(EA_FILES_DIR, file_name)
    await file.download_to_drive(file_path)
    
    # Store the file path in user data
    context.user_data['admin_product']['file'] = file_path
    log_admin_action(update.effective_user.id, f"Uploaded EA file: {file_path}")
    
    await update.message.reply_text("File uploaded successfully! Is this a trial product? (yes/no)")
    return ADMIN_ADD_PRODUCT

async def admin_edit_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("You are not authorized to use this command.")
        return ConversationHandler.END
    
    # Check if a conversation is already active
    if context.user_data.get('admin_edit_product_id'):
        await update.message.reply_text(
            "You are already editing a product. Please finish or cancel the current process with /cancel before starting a new one."
        )
        return ConversationHandler.END

    # Clear any ongoing conversation to avoid conflicts
    context.user_data.clear()

    if context.args:
        product_id = context.args[0].strip()
        products = load_products()
        if product_id not in products:
            await update.message.reply_text("Product ID not found.")
            return ConversationHandler.END
        
        context.user_data['admin_edit_product_id'] = product_id
        context.user_data['admin_edit_product'] = products[product_id].copy()
        log_admin_action(update.effective_user.id, f"Started editing product ID {product_id}")
        await update.message.reply_text(
            f"Editing product ID {product_id}: {context.user_data['admin_edit_product']['name']}\n"
            "What would you like to edit?\n"
            "1. Name\n"
            "2. File\n"
            "3. Trial settings (if trial)\n"
            "4. Pricing tiers (if not trial)\n"
            "5. Done"
        )
        return ADMIN_EDIT_PRODUCT
    else:
        await update.message.reply_text("Please provide the product ID to edit (e.g., 1).")
        return ADMIN_EDIT_PRODUCT_ID

async def admin_edit_product_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    product_id = update.message.text.strip()
    # Remove any "ID: " prefix if present
    product_id = product_id.replace("ID: ", "").strip()
    
    products = load_products()
    if product_id not in products:
        await update.message.reply_text("Product ID not found. Please provide a valid product ID.")
        return ADMIN_EDIT_PRODUCT_ID
    
    context.user_data['admin_edit_product_id'] = product_id
    context.user_data['admin_edit_product'] = products[product_id].copy()
    log_admin_action(update.effective_user.id, f"Started editing product ID {product_id}")
    await update.message.reply_text(
        f"Editing product ID {product_id}: {context.user_data['admin_edit_product']['name']}\n"
        "What would you like to edit?\n"
        "1. Name\n"
        "2. File\n"
        "3. Trial settings (if trial)\n"
        "4. Pricing tiers (if not trial)\n"
        "5. Done"
    )
    return ADMIN_EDIT_PRODUCT

async def admin_edit_product_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text.strip()
    product_id = context.user_data.get('admin_edit_product_id')
    product = context.user_data.get('admin_edit_product')
    
    if not product_id or not product:
        await update.message.reply_text("Invalid state. Please start the edit process again with /admin_edit_product.")
        return ConversationHandler.END
    
    print(f"admin_edit_product_details: choice={choice}")
    
    if choice == '1':
        await update.message.reply_text("Please provide the new product name.")
        context.user_data['admin_edit_field'] = 'name'
        return ADMIN_EDIT_PRODUCT_FIELD
    elif choice == '2':
        await update.message.reply_text("Please provide the new file name.")
        context.user_data['admin_edit_field'] = 'file'
        return ADMIN_EDIT_PRODUCT_FIELD
    elif choice == '3' and product.get('is_trial', False):
        await update.message.reply_text("Please provide the new trial expiry days.")
        context.user_data['admin_edit_field'] = 'expiry_days'
        return ADMIN_EDIT_PRODUCT_FIELD
    elif choice == '4' and not product.get('is_trial', False):
        await update.message.reply_text(
            "Current pricing tiers:\n" +
            "\n".join([f"Tier {t_key}: ${t_info['price_usd']} ({t_info['price_xlm']} XLM, {t_info['expiry_days']} days)"
                       for t_key, t_info in product['pricing_tiers'].items()]) + "\n" +
            "Please provide the tier to edit (e.g., 1) or 'add' to add a new tier, or 'delete <tier_number>' to remove a tier."
        )
        context.user_data['admin_edit_field'] = 'pricing_tiers'
        return ADMIN_EDIT_PRODUCT_FIELD
    elif choice == '5':
        products = load_products()
        products[product_id] = product
        save_products(products)
        log_admin_action(update.effective_user.id, f"Finished editing product ID {product_id}")
        await update.message.reply_text("Product updated successfully!")
        context.user_data.clear()
        return ConversationHandler.END
    else:
        await update.message.reply_text("Invalid choice. Please select an option (1-5).")
        return ADMIN_EDIT_PRODUCT

async def admin_edit_product_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    product = context.user_data.get('admin_edit_product')
    field = context.user_data.get('admin_edit_field')
    subfield = context.user_data.get('admin_edit_subfield')
    
    if not field or not product:
        await update.message.reply_text("Invalid state. Please start the edit process again with /admin_edit_product.")
        return ConversationHandler.END
    
    print(f"admin_edit_product_field: field={field}, subfield={subfield}, text={text}")

    if subfield == 'edit_tier':
        try:
            price_usd, price_xlm, expiry_days = text.split(',')
            tier_number = context.user_data['admin_edit_tier']
            product['pricing_tiers'][tier_number] = {
                'price_usd': float(price_usd.strip()),
                'price_xlm': float(price_xlm.strip()),
                'expiry_days': int(expiry_days.strip())
            }
            log_admin_action(update.effective_user.id, f"Edited tier {tier_number} of product ID {context.user_data['admin_edit_product_id']}")
            context.user_data.pop('admin_edit_subfield', None)
            context.user_data.pop('admin_edit_tier', None)
            context.user_data.pop('admin_edit_field', None)
        except Exception as e:
            await update.message.reply_text(f"Invalid format: {str(e)}. Please use: price_usd,price_xlm,expiry_days (e.g., 10,50,30)")
            return ADMIN_EDIT_PRODUCT_FIELD
    elif subfield == 'add_tier':
        try:
            tier_number, price_usd, price_xlm, expiry_days = text.split(',')
            product['pricing_tiers'][tier_number.strip()] = {
                'price_usd': float(price_usd.strip()),
                'price_xlm': float(price_xlm.strip()),
                'expiry_days': int(expiry_days.strip())
            }
            log_admin_action(update.effective_user.id, f"Added tier {tier_number} to product ID {context.user_data['admin_edit_product_id']}")
            context.user_data.pop('admin_edit_subfield', None)
            context.user_data.pop('admin_edit_field', None)
        except Exception as e:
            await update.message.reply_text(f"Invalid format: {str(e)}. Please use: tier_number,price_usd,price_xlm,expiry_days (e.g., 1,10,50,30)")
            return ADMIN_EDIT_PRODUCT_FIELD
    elif field == 'name':
        product['name'] = text
        log_admin_action(update.effective_user.id, f"Edited name of product ID {context.user_data['admin_edit_product_id']} to {text}")
        context.user_data.pop('admin_edit_field', None)
    elif field == 'file':
        product['file'] = text
        log_admin_action(update.effective_user.id, f"Edited file of product ID {context.user_data['admin_edit_product_id']} to {text}")
        context.user_data.pop('admin_edit_field', None)
    elif field == 'expiry_days':
        product['expiry_days'] = int(text)
        log_admin_action(update.effective_user.id, f"Edited expiry_days of product ID {context.user_data['admin_edit_product_id']} to {text}")
        context.user_data.pop('admin_edit_field', None)
    elif field == 'pricing_tiers':
        if text.lower() == 'add':
            await update.message.reply_text(
                "Please provide the new tier in the format:\n"
                "tier_number,price_usd,price_xlm,expiry_days\n"
                "For example: 1,10,50,30"
            )
            context.user_data['admin_edit_subfield'] = 'add_tier'
            return ADMIN_EDIT_PRODUCT_FIELD
        elif text.lower().startswith('delete '):
            parts = text.split(' ')
            if len(parts) != 2 or not parts[1].isdigit():
                await update.message.reply_text("Invalid format. Please use: delete <tier_number> (e.g., delete 1)")
                return ADMIN_EDIT_PRODUCT_FIELD
            tier_number = parts[1]
            if tier_number in product['pricing_tiers']:
                del product['pricing_tiers'][tier_number]
                log_admin_action(update.effective_user.id, f"Deleted tier {tier_number} from product ID {context.user_data['admin_edit_product_id']}")
                context.user_data.pop('admin_edit_field', None)
            else:
                await update.message.reply_text("Tier not found.")
                return ADMIN_EDIT_PRODUCT_FIELD
        elif text in product['pricing_tiers']:
            context.user_data['admin_edit_tier'] = text
            context.user_data['admin_edit_subfield'] = 'edit_tier'
            await update.message.reply_text(
                "Please provide the updated tier details in the format:\n"
                "price_usd,price_xlm,expiry_days\n"
                "For example: 10,50,30"
            )
            return ADMIN_EDIT_PRODUCT_FIELD
        else:
            await update.message.reply_text("Invalid option. Please specify a tier to edit (e.g., 1), 'add', or 'delete <tier_number>'.")
            return ADMIN_EDIT_PRODUCT_FIELD
    else:
        await update.message.reply_text("Invalid state. Please start the edit process again with /admin_edit_product.")
        return ConversationHandler.END
    
    await update.message.reply_text(
        f"Updated successfully. What would you like to edit next?\n"
        "1. Name\n"
        "2. File\n"
        "3. Trial settings (if trial)\n"
        "4. Pricing tiers (if not trial)\n"
        "5. Done"
    )
    return ADMIN_EDIT_PRODUCT

async def admin_delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("You are not authorized to use this command.")
        return
    
    if not context.args:
        await update.message.reply_text("Please provide the product ID to delete. Usage: /admin_delete_product <product_id>")
        return
    
    product_id = context.args[0].strip()
    products = load_products()
    if product_id not in products:
        await update.message.reply_text("Product ID not found.")
        return
    
    product_name = products[product_id]['name']
    del products[product_id]
    save_products(products)
    log_admin_action(update.effective_user.id, f"Deleted product ID {product_id}: {product_name}")
    await update.message.reply_text(f"Product ID {product_id} deleted successfully!")

async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("You are not authorized to use this command.")
        return
    
    help_text = (
        "📋 **Admin Commands List** 📋\n\n"
        "Here are the available admin commands:\n\n"
        "1. **/admin_list_products**\n"
        "   - Description: Lists all products with their details.\n"
        "   - Usage: `/admin_list_products`\n\n"
        "2. **/admin_add_product**\n"
        "   - Description: Adds a new product (trial or paid).\n"
        "   - Usage: `/admin_add_product`\n"
        "   - Follow the prompts to enter product details.\n\n"
        "3. **/admin_edit_product**\n"
        "   - Description: Edits an existing product’s details (name, file, trial settings, or pricing tiers).\n"
        "   - Usage: `/admin_edit_product <product_id>`\n"
        "   - Example: `/admin_edit_product 1`\n\n"
        "4. **/admin_delete_product**\n"
        "   - Description: Deletes a product by its ID.\n"
        "   - Usage: `/admin_delete_product <product_id>`\n"
        "   - Example: `/admin_delete_product 5`\n\n"
        "5. **/admin_help**\n"
        "   - Description: Displays this help message with a list of admin commands.\n"
        "   - Usage: `/admin_help`\n\n"
        "💡 **Tip**: Ensure you are logged in as the admin (user ID: {ADMIN_USER_ID}) to use these commands."
    )
    await update.message.reply_text(help_text)

# User commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "Welcome to LicenseBot! Let's get started.\nWhat's your name?"
    )
    context.user_data['state'] = NAME
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['name'] = update.message.text.strip()
    products = load_products()
    product_list = "\n".join([f"{key}. {info['name']}" for key, info in products.items()])
    await update.message.reply_text(
        f"Hello {context.user_data['name']}! Please select a product:\n{product_list}\n\nType the number of your choice (e.g., 1 or 2 for full versions, 3 or 4 for trials)."
    )
    context.user_data['state'] = PRODUCT
    return PRODUCT

async def select_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    product_choice = update.message.text.strip()
    products = load_products()
    if product_choice not in products:
        product_list = "\n".join([f"{key}. {info['name']}" for key, info in products.items()])
        await update.message.reply_text(
            f"Invalid choice. Please select a product by typing the number:\n{product_list}"
        )
        return PRODUCT
    
    context.user_data['product'] = product_choice
    product_info = products[product_choice]
    
    if product_info.get('is_trial', False):
        username = context.user_data['name']
        expiry = (datetime.now() + timedelta(days=product_info['expiry_days'])).strftime('%Y-%m-%d')
        license_key = generate_license_key()
        product_name = product_info['name']
        product_file = product_info['file']
        
        licenses = load_licenses()
        licenses[license_key] = {
            'username': username,
            'hwid': '',
            'expiry': expiry,
            'active': True,
            'tx_hash': 'trial-no-payment',
            'product': product_name,
            'is_trial': True
        }
        save_licenses(licenses)
        
        transactions = load_transactions()
        transactions[license_key] = {
            'username': username,
            'product': product_name,
            'product_file': product_file,
            'pdf_file': f"license_{license_key}.pdf",
            'is_trial': True
        }
        save_transactions(transactions)
        
        pdf_file = create_pdf_license(license_key, username, expiry, product_name, is_trial=True)
        
        await update.message.reply_text(
            f"Trial License Generated!\n"
            f"License Key: {license_key}\n"
            f"Username: {username}\n"
            f"Product: {product_name}\n"
            f"Expiry: {expiry}\n"
            "Please enter this license key in your EA settings.\n"
            "When you run the EA for the first time, it will automatically detect your machine's Hardware ID (HWID) and register it with your license."
        )
        
        try:
            with open(pdf_file, 'rb') as f:
                await update.message.reply_text("Sending License Certificate...")
                await update.message.reply_document(f, caption="Your License Certificate")
            
            with open(product_file, 'rb') as f:
                await update.message.reply_text(f"Sending {product_name}...")
                await update.message.reply_document(f, caption=f"Your {product_name}")
            
            with open('usage_guide.pdf', 'rb') as f:
                await update.message.reply_text("Sending Usage Guide...")
                await update.message.reply_document(f, caption="Usage Guide")
            
            await update.message.reply_text(
                f"Thank you for trying our product! After the trial expires, purchase a full version at {BOT_LINK}."
            )
        except Exception as e:
            await update.message.reply_text(
                f"An error occurred while sending the files: {str(e)}\n"
                f"Please use /resend {license_key} to try again."
            )
        return ConversationHandler.END
    
    pricing_tiers = product_info['pricing_tiers']
    tier_list = "\n".join([f"{key}. ${info['price_usd']} ({info['expiry_days']} days)" for key, info in pricing_tiers.items()])
    await update.message.reply_text(
        f"You selected {product_info['name']}.\n"
        f"Please select a pricing tier:\n{tier_list}\n\nType the number of your choice (e.g., 1, 2, 3, or 4)."
    )
    context.user_data['state'] = PRICING_TIER
    return PRICING_TIER

async def select_pricing_tier(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tier_choice = update.message.text.strip()
    product_choice = context.user_data['product']
    products = load_products()
    product_info = products[product_choice]
    pricing_tiers = product_info['pricing_tiers']
    
    if tier_choice not in pricing_tiers:
        tier_list = "\n".join([f"{key}. ${info['price_usd']} ({info['expiry_days']} days)" for key, info in pricing_tiers.items()])
        await update.message.reply_text(
            f"Invalid choice. Please select a pricing tier by typing the number:\n{tier_list}"
        )
        return PRICING_TIER
    
    context.user_data['pricing_tier'] = tier_choice
    tier_info = pricing_tiers[tier_choice]
    payment_amount_xlm = tier_info['price_xlm']
    payment_amount_usd = tier_info['price_usd']
    
    await update.message.reply_text(
        f"You selected the ${payment_amount_usd} tier ({tier_info['expiry_days']} days).\n"
        f"To proceed, please send one of the following to this Stellar address: {STELLAR_PUBLIC_KEY}\n"
        f"- {payment_amount_xlm} XLM\n"
        f"- {payment_amount_usd} USDC (equivalent to ${payment_amount_usd})\n\n"
        "Once you've made the payment, send me your Stellar address (starting with G) that you used to make the payment.\n"
        f"For testing, you can use this address: {TEST_ADDRESS}\n\n"
        "Please type the address manually to avoid copying issues."
    )
    context.user_data['state'] = PAYMENT
    return PAYMENT

async def verify_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    sender_address = update.message.text.strip()
    sender_address = re.sub(r'[^A-Z0-9]', '', sender_address.upper())
    
    if len(sender_address) != 56 or not sender_address.startswith('G'):
        await update.message.reply_text(
            "Please provide a valid Stellar address starting with G (exactly 56 characters long).\n"
            f"Expected address for testing: {TEST_ADDRESS}"
        )
        return PAYMENT
    
    await update.message.reply_text("Verifying your payment, please wait...")
    
    payment_verified, tx_hash = check_payment(sender_address)
    
    if payment_verified:
        context.user_data['tx_hash'] = tx_hash
        product_choice = context.user_data['product']
        tier_choice = context.user_data['pricing_tier']
        products = load_products()
        product_info = products[product_choice]
        tier_info = product_info['pricing_tiers'][tier_choice]
        product_name = product_info['name']
        product_file = product_info['file']
        
        license_key = generate_license_key()
        username = context.user_data['name']
        expiry_days = tier_info['expiry_days']
        expiry = (datetime.now() + timedelta(days=expiry_days)).strftime('%Y-%m-%d')
        
        licenses = load_licenses()
        licenses[license_key] = {
            'username': username,
            'hwid': '',
            'expiry': expiry,
            'active': True,
            'tx_hash': context.user_data['tx_hash'],
            'product': product_name,
            'is_trial': False
        }
        save_licenses(licenses)
        
        transactions = load_transactions()
        transactions[license_key] = {
            'username': username,
            'product': product_name,
            'product_file': product_file,
            'pdf_file': f"license_{license_key}.pdf",
            'is_trial': False
        }
        save_transactions(transactions)
        
        pdf_file = create_pdf_license(license_key, username, expiry, product_name)
        
        await update.message.reply_text(
            f"Payment verified!\n"
            f"License Key: {license_key}\n"
            f"Username: {username}\n"
            f"Product: {product_name}\n"
            f"Expiry: {expiry}\n"
            "Please enter this license key in your EA settings.\n"
            "When you run the EA for the first time, it will automatically detect your machine's Hardware ID (HWID) and register it with your license."
        )
        
        try:
            with open(pdf_file, 'rb') as f:
                await update.message.reply_text("Sending License Certificate...")
                await update.message.reply_document(f, caption="Your License Certificate")
            
            with open(product_file, 'rb') as f:
                await update.message.reply_text(f"Sending {product_name}...")
                await update.message.reply_document(f, caption=f"Your {product_name}")
            
            with open('usage_guide.pdf', 'rb') as f:
                await update.message.reply_text("Sending Usage Guide...")
                await update.message.reply_document(f, caption="Usage Guide")
            
            await update.message.reply_text("Thank you! Check your files above.")
        except Exception as e:
            await update.message.reply_text(
                f"An error occurred while sending the files: {str(e)}\n"
                f"Please use /resend {license_key} to try again."
            )
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "Payment not found. Please ensure you sent the correct amount to the address provided.\n"
            f"Expected address for testing: {TEST_ADDRESS}"
        )
        return PAYMENT

async def resend_files(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Please provide your license key. Usage: /resend <license_key>")
        return
    
    license_key = context.args[0].strip()
    transactions = load_transactions()
    
    if license_key not in transactions:
        await update.message.reply_text("License key not found. Please contact support with your transaction details.")
        return
    
    transaction = transactions[license_key]
    product_name = transaction['product']
    product_file = transaction['product_file']
    pdf_file = transaction['pdf_file']
    username = transaction['username']
    is_trial = transaction.get('is_trial', False)
    
    await update.message.reply_text(f"Resending files for license key: {license_key}...")
    
    try:
        with open(pdf_file, 'rb') as f:
            await update.message.reply_text("Sending License Certificate...")
            await update.message.reply_document(f, caption="Your License Certificate")
        
        with open(product_file, 'rb') as f:
            await update.message.reply_text(f"Sending {product_name}...")
            await update.message.reply_document(f, caption=f"Your {product_name}")
        
        with open('usage_guide.pdf', 'rb') as f:
            await update.message.reply_text("Sending Usage Guide...")
            await update.message.reply_document(f, caption="Usage Guide")
        
        if is_trial:
            await update.message.reply_text(
                f"Thank you for trying our product! After the trial expires, purchase a full version at {BOT_LINK}."
            )
        else:
            await update.message.reply_text("Thank you! Check your files above.")
    except Exception as e:
        await update.message.reply_text(
            f"An error occurred while resending the files: {str(e)}\n"
            "Please contact support with your license key and transaction details."
        )

async def validate_license(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop('state', None)
    context.user_data.pop('name', None)
    context.user_data.pop('product', None)
    context.user_data.pop('tx_hash', None)

    if not context.args:
        await update.message.reply_text("Please provide a license key to validate. Usage: /validate <license_key>")
        context.user_data['validate_state'] = 'awaiting_key'
        return

    license_key = context.args[0].strip()
    licenses = load_licenses()

    if license_key not in licenses:
        await update.message.reply_text("Invalid license key. Please check and try again.")
        return

    license = licenses[license_key]
    expiry_date = datetime.strptime(license['expiry'], '%Y-%m-%d')
    current_date = datetime.now()

    if len(context.args) > 1:
        provided_hwid = context.args[1].strip()
        if license['hwid'] and license['hwid'] != provided_hwid:
            await update.message.reply_text("HWID mismatch. This license is locked to a different machine.")
            return
        if not license['active']:
            await update.message.reply_text("This license is deactivated.")
        elif current_date > expiry_date:
            msg = "This license has expired."
            if license.get('is_trial', False):
                msg += f" Purchase a full version at {BOT_LINK}."
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text(
                f"License is valid!\n"
                f"Username: {license['username']}\n"
                f"Product: {license['product']}\n"
                f"Expiry: {license['expiry']}\n"
                f"HWID: {license['hwid']}"
            )
    else:
        await update.message.reply_text("Please provide the HWID to validate this license (or type 'skip' to validate without HWID).")
        context.user_data['validate_key'] = license_key
        context.user_data['validate_state'] = 'awaiting_hwid'
        context.user_data['validate_start_time'] = datetime.now()

async def handle_validate_hwid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if 'validate_state' not in context.user_data or context.user_data['validate_state'] != 'awaiting_hwid':
        return

    if 'validate_start_time' not in context.user_data:
        context.user_data['validate_start_time'] = datetime.now()
    
    time_elapsed = (datetime.now() - context.user_data['validate_start_time']).total_seconds()
    if time_elapsed > 120:
        await update.message.reply_text("Validation timed out. Please use /validate again to start over.")
        context.user_data.pop('validate_state', None)
        context.user_data.pop('validate_key', None)
        context.user_data.pop('validate_start_time', None)
        return

    licenses = load_licenses()
    license_key = context.user_data['validate_key']
    license = licenses[license_key]
    expiry_date = datetime.strptime(license['expiry'], '%Y-%m-%d')
    current_date = datetime.now()

    hwid_input = update.message.text.strip()
    if hwid_input.lower() == 'skip':
        if not license['active']:
            await update.message.reply_text("This license is deactivated.")
        elif current_date > expiry_date:
            msg = "This license has expired."
            if license.get('is_trial', False):
                msg += f" Purchase a full version at {BOT_LINK}."
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text(
                f"License is valid!\n"
                f"Username: {license['username']}\n"
                f"Product: {license['product']}\n"
                f"Expiry: {license['expiry']}\n"
                f"HWID: {license['hwid']}"
            )
    else:
        provided_hwid = hwid_input
        if license['hwid'] and license['hwid'] != provided_hwid:
            await update.message.reply_text("HWID mismatch. This license is locked to a different machine.")
            context.user_data.pop('validate_state', None)
            context.user_data.pop('validate_key', None)
            context.user_data.pop('validate_start_time', None)
            return
        if not license['active']:
            await update.message.reply_text("This license is deactivated.")
        elif current_date > expiry_date:
            msg = "This license has expired."
            if license.get('is_trial', False):
                msg += f" Purchase a full version at {BOT_LINK}."
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text(
                f"License is valid!\n"
                f"Username: {license['username']}\n"
                f"Product: {license['product']}\n"
                f"Expiry: {license['expiry']}\n"
                f"HWID: {license['hwid']}"
            )

    context.user_data.pop('validate_state', None)
    context.user_data.pop('validate_key', None)
    context.user_data.pop('validate_start_time', None)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Process cancelled.")
    context.user_data.clear()
    return ConversationHandler.END

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CommandHandler('admin_add_product', admin_add_product),
            CommandHandler('admin_edit_product', admin_edit_product)
        ],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_product)],
            PRICING_TIER: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_pricing_tier)],
            PAYMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, verify_payment)],
            ADMIN_ADD_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_product_details)],
            ADMIN_ADD_PRODUCT_FILE: [MessageHandler(filters.Document.ALL, admin_add_product_file)],
            ADMIN_EDIT_PRODUCT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_edit_product_id)],
            ADMIN_EDIT_PRODUCT: [MessageHandler(filters.Regex('^[1-5]$'), admin_edit_product_details)],
            ADMIN_EDIT_PRODUCT_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_edit_product_field)],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CommandHandler('start', start)
        ],
        conversation_timeout=600
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("validate", validate_license))
    application.add_handler(CommandHandler("resend", resend_files))
    application.add_handler(CommandHandler("admin_list_products", admin_list_products))
    application.add_handler(CommandHandler("admin_delete_product", admin_delete_product))
    application.add_handler(CommandHandler("admin_help", admin_help))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_validate_hwid))
    application.run_polling()

if __name__ == '__main__':
    main()