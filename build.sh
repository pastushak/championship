#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

# Імпорт учнів з CSV якщо є і база порожня
python -c "
from app import app
from models import Student, Championship
from datetime import datetime

with app.app_context():
    # Створюємо запис чемпіонату якщо немає
    if Championship.objects.count() == 0:
        Championship(
            name='Чемпіонат зі Швидкочислення 2025-2026',
            start_date=datetime.now(),
            is_active=True
        ).save()
        print('Championship created')
    
    # Імпортуємо учнів якщо база порожня і є CSV
    import os
    if Student.objects.count() == 0 and os.path.exists('students.csv'):
        import csv
        count = 0
        with open('students.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                patronymic = row['По батькові'].strip()
                if patronymic == '-':
                    patronymic = None
                try:
                    rating = float(row['Бал'].strip())
                except:
                    rating = 0.0
                Student(
                    first_name=row[\"Ім'я\"].strip(),
                    last_name=row['Прізвище'].strip(),
                    patronymic=patronymic,
                    class_name=row['Клас'].strip(),
                    rating=rating
                ).save()
                count += 1
        print(f'Imported {count} students')
    else:
        print(f'Students already in DB: {Student.objects.count()}')
"