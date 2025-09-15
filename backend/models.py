import mysql.connector
from config import DB_CONFIG

def init_db():
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            userpassword VARCHAR(50) NOT NULL,
            userrole VARCHAR(50) NOT NULL DEFAULT 'user'
        )
    """)

    # Create data table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS data (
            id INT AUTO_INCREMENT PRIMARY KEY,
            date DATE NOT NULL,
            column_a FLOAT,
            column_b FLOAT
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()
