import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    MONGODB_URI = os.environ.get('MONGODB_URI') or 'mongodb://localhost/championship'
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME') or 'fast.count.20202026'
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'fast.count.26'