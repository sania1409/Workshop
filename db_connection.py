# db_connection.py
import mysql.connector

def get_db_connection():
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Rida766196$",
        database="workshop_db"
    )
    return db