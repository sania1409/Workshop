import os

class Config:
    SECRET_KEY = 'your_secret_key'
    # Make sure password is URL-encoded if it has @ or % etc
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:Rida766196$@localhost/workshop_db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False