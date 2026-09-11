import mysql.connector
import os

# Connects to the MySQL database using settings from environment variables
def get_db_connection():
    connection = mysql.connector.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", "password"),
        database=os.environ.get("DB_NAME", "pet_adoption")
    )
    return connection