import sqlite3

def setup_database():
    conn = sqlite3.connect("expenses.db")  # Creates the database if it doesn't exist
    cursor = conn.cursor()

    # Create the Expenses table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            expense_name TEXT NOT NULL,
            paid_by TEXT NOT NULL,
            amount REAL NOT NULL,
            involved TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    print("Database and table set up successfully.")

# Call the setup function
setup_database()
