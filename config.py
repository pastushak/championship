import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///championship.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Налаштування адміністратора
    ADMIN_USERNAME = 'admin'
    ADMIN_PASSWORD = 'admin123'
