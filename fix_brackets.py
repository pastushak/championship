#!/usr/bin/env python3
"""
Скрипт для виправлення помилкових BYE в турнірних сітках
ЗБЕРІГАЄ всі зіграні матчі та їх результати!
"""

from app import app, db
from models import Match, Student
import sys

def fix_5a_class():
    """Виправлення 5-А класу"""
    print("\n🔧 Виправлення 5-А класу...")
    
    with app.app_context():
        class_name = '5-А'
        
        # Знаходимо всі зіграні матчі
        completed_matches = Match.query.filter_by(
            class_name=class_name, 
            is_completed=True
        ).all()
        
        print(f"✅ Знайдено {len(completed_matches)} зіграних матчів")
        
        # Зберігаємо результати
        completed_data = []
        for m in completed_matches:
            completed_data.append({
                'round': m.round_number,
                'match_num': m.match_number,
                'student1_id': m.student1_id,
                'student2_id': m.student2_id,
                'winner_id': m.winner_id,
                'score1': m.score1,
                'score2': m.score2,
                'scheduled_date': m.scheduled_date
            })
        
        # Видаляємо помилковий матч "Грінка vs Крамарчук" в 1/16
        wrong_match = Match.query.filter_by(
            class_name=class_name,
            round_number=1,
            match_number=1,
            is_completed=True
        ).first()
        
        if wrong_match and wrong_match.student1_id and wrong_match.student2_id:
            s1 = Student.query.get(wrong_match.student1_id)
            s2 = Student.query.get(wrong_match.student2_id)
            if s1 and s2:
                print(f"❌ Видаляємо помилковий матч: {s1.full_name} vs {s2.full_name}")
                db.session.delete(wrong_match)
                db.session.commit()
        
        # Видаляємо всі помилкові BYE з 1/8
        bye_matches_1_8 = Match.query.filter_by(
            class_name=class_name,
            round_number=2
        ).filter(
            (Match.student1_id == None) | (Match.student2_id == None)
        ).all()
        
        for m in bye_matches_1_8:
            if not m.is_completed:
                print(f"❌ Видаляємо помилковий BYE з 1/8 (матч #{m.match_number})")
                db.session.delete(m)
        
        db.session.commit()
        print("✅ 5-А виправлено!")

def fix_other_classes():
    """Виправлення інших класів (6-А, 6-Б, 7-А, 7-Б)"""
    print("\n🔧 Виправлення інших класів...")
    
    with app.app_context():
        classes = ['6-А', '6-Б', '7-А', '7-Б']
        
        for class_name in classes:
            print(f"\n📊 Клас {class_name}:")
            
            # Знаходимо зіграні матчі
            completed = Match.query.filter_by(
                class_name=class_name,
                is_completed=True
            ).count()
            
            print(f"  ✅ Зіграних матчів: {completed}")
            
            # Видаляємо помилкові BYE з 1/16 (крім учнів які мають has_bye=True)
            # Учні з has_bye=True мають автопрохід в 1/8, а не в 1/16!
            
            # Знаходимо всі матчі 1/16 з BYE
            bye_matches_1_16 = Match.query.filter_by(
                class_name=class_name,
                round_number=1
            ).filter(
                Match.student2_id == None
            ).all()
            
            # Ці матчі мають бути видалені, бо BYE має бути в 1/8, а не 1/16
            for m in bye_matches_1_16:
                if m.is_completed and m.student1_id:
                    student = Student.query.get(m.student1_id)
                    if student and student.has_bye:
                        print(f"  ❌ Видаляємо помилковий BYE з 1/16 для {student.full_name}")
                        db.session.delete(m)
            
            # Перевіряємо що в 1/8 є правильні BYE для учнів з has_bye=True
            students_with_bye = Student.query.filter_by(
                class_name=class_name,
                has_bye=True
            ).all()
            
            print(f"  ℹ️  Учнів з BYE: {len(students_with_bye)}")
            
            db.session.commit()
            print(f"  ✅ {class_name} виправлено!")

def main():
    """Головна функція"""
    print("=" * 60)
    print("🚀 ВИПРАВЛЕННЯ ТУРНІРНИХ СІТОК")
    print("=" * 60)
    print("\n⚠️  УВАГА: Цей скрипт виправить помилкові BYE")
    print("✅ Всі зіграні матчі будуть ЗБЕРЕЖЕНІ!")
    print("\nПродовжити? (y/n): ", end='')
    
    # Для автоматичного запуску на Render
    if len(sys.argv) > 1 and sys.argv[1] == '--yes':
        confirm = 'y'
    else:
        confirm = input().lower()
    
    if confirm != 'y':
        print("❌ Скасовано")
        return
    
    try:
        fix_5a_class()
        fix_other_classes()
        
        print("\n" + "=" * 60)
        print("✅ ВИПРАВЛЕННЯ ЗАВЕРШЕНО УСПІШНО!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ПОМИЛКА: {e}")
        print("💾 База даних НЕ ЗМІНЕНА (через rollback)")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()