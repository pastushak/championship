#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для імпорту реальних даних учнів з CSV файлу
"""
import csv
import sys
from app import app, db
from models import Student, Match

def import_students(csv_file):
    """Імпортує учнів з CSV файлу"""
    
    with app.app_context():
        # Очищаємо старі дані
        print("🗑️  Видаляємо тестові дані...")
        Match.query.delete()
        Student.query.delete()
        db.session.commit()
        print("✅ Тестові дані видалено")
        
        # Читаємо CSV
        print(f"\n📖 Читаємо файл {csv_file}...")
        count = 0
        errors = 0
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                try:
                    # Обробляємо по батькові ("-" → None)
                    patronymic = row['По батькові'].strip()
                    if patronymic == '-':
                        patronymic = None
                    
                    # Обробляємо рейтинг
                    rating_str = row['Бал'].strip()
                    try:
                        rating = float(rating_str)
                    except ValueError:
                        rating = 0.0
                    
                    # Створюємо учня
                    student = Student(
                        first_name=row["Ім'я"].strip(),
                        last_name=row['Прізвище'].strip(),
                        patronymic=patronymic,
                        class_name=row['Клас'].strip(),
                        rating=rating
                    )
                    db.session.add(student)
                    count += 1
                    
                except Exception as e:
                    print(f"❌ Помилка у рядку {count + 1}: {e}")
                    errors += 1
        
        # Зберігаємо
        db.session.commit()
        
        # Статистика
        print(f"\n✅ Імпорт завершено!")
        print(f"📊 Імпортовано учнів: {count}")
        if errors > 0:
            print(f"⚠️  Помилок: {errors}")
        
        # Статистика по класах
        print("\n📋 Розподіл по класах:")
        classes_data = db.session.query(Student.class_name, db.func.count(Student.id)).group_by(Student.class_name).order_by(Student.class_name).all()
        
        for class_name, student_count in classes_data:
            print(f"   {class_name}: {student_count} учнів")
        
        print(f"\n🎯 Всього: {count} учнів")
        print("\n💡 Тепер зайдіть в адмінку та проведіть жеребкування для кожного класу!")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Використання: python3 import_real_students.py <csv_файл>")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    import_students(csv_file)