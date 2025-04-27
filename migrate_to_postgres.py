import json
import os
import psycopg2
from psycopg2.extras import Json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

# Database connection
def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

# Initialize database tables
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            data JSONB NOT NULL
        );
        CREATE TABLE IF NOT EXISTS licenses (
            license_key TEXT PRIMARY KEY,
            data JSONB NOT NULL
        );
        CREATE TABLE IF NOT EXISTS transactions (
            license_key TEXT PRIMARY KEY,
            data JSONB NOT NULL
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

# Migrate JSON files to PostgreSQL
def migrate_products():
    with open('products.json', 'r') as f:
        products = json.load(f)
    
    conn = get_db_connection()
    cur = conn.cursor()
    for product_id, data in products.items():
        cur.execute("INSERT INTO products (id, data) VALUES (%s, %s) ON CONFLICT (id) DO UPDATE SET data = %s",
                    (product_id, Json(data), Json(data)))
    conn.commit()
    cur.close()
    conn.close()
    print("Products migrated successfully.")

def migrate_licenses():
    with open('licenses.json', 'r') as f:
        licenses = json.load(f)
    
    conn = get_db_connection()
    cur = conn.cursor()
    for license_key, data in licenses.items():
        cur.execute("INSERT INTO licenses (license_key, data) VALUES (%s, %s) ON CONFLICT (license_key) DO UPDATE SET data = %s",
                    (license_key, Json(data), Json(data)))
    conn.commit()
    cur.close()
    conn.close()
    print("Licenses migrated successfully.")

def migrate_transactions():
    with open('transactions.json', 'r') as f:
        transactions = json.load(f)
    
    conn = get_db_connection()
    cur = conn.cursor()
    for license_key, data in transactions.items():
        cur.execute("INSERT INTO transactions (license_key, data) VALUES (%s, %s) ON CONFLICT (license_key) DO UPDATE SET data = %s",
                    (license_key, Json(data), Json(data)))
    conn.commit()
    cur.close()
    conn.close()
    print("Transactions migrated successfully.")

if __name__ == "__main__":
    init_db()
    migrate_products()
    migrate_licenses()
    migrate_transactions()