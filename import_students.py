from dotenv import load_dotenv
load_dotenv()

from app import app
from models import Student, Championship
import csv

with app.app_context():
    # Створюємо чемпіонат якщо немає
    if Championship.objects.count() == 0:
        Championship(name='Чемпіонат зі Швидкочислення 2025-2026', is_active=True).save()
        print('Чемпіонат створено')

    # Імпортуємо учнів
    if Student.objects.count() == 0:
        count = 0
        with open('students.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    rating = float(row['Бал'].strip())
                except:
                    rating = 0.0
                Student(
                    first_name=row["Ім'я"].strip(),
                    last_name=row['Прізвище'].strip(),
                    class_name=row['Клас'].strip(),
                    rating=rating
                ).save()
                count += 1
        print(f'✅ Імпортовано {count} учнів!')
    else:
        print(f'ℹ️  Вже є {Student.objects.count()} учнів в базі')
        print('Якщо хочеш перезаписати — виконай Student.objects.delete() спочатку')