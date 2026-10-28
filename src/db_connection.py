import os
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv
from mysql.connector import Error

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def get_connection():
    """Connect Python to the configured MySQL database."""

    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "abandoned_cart_full_db"),
    )

    return connection


if __name__ == "__main__":
    try:
        connection = get_connection()

        if connection.is_connected():
            print("Successfully connected to MySQL!")

            cursor = connection.cursor()
            cursor.execute("SELECT DATABASE(), VERSION()")
            result = cursor.fetchone()

            print(f"Database: {result[0]}")
            print(f"MySQL version: {result[1]}")

            cursor.close()
            connection.close()
            print("Connection closed successfully.")

    except Error as error:
        print(f"MySQL connection failed: {error}")