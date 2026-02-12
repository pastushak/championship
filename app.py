from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from models import db, Student, Match, Championship
from config import Config
from datetime import datetime
import random
import math

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'

# Простий клас користувача для адміністратора
class User:
    def __init__(self, id):
        self.id = id
        self.is_authenticated = True
        self.is_active = True
        self.is_anonymous = False
    
    def get_id(self):
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    if user_id == 'admin':
        return User('admin')
    return None


# ==================== ПУБЛІЧНІ СТОРІНКИ ====================

@app.route('/')
def index():
    """Головна сторінка"""
    championship = Championship.query.first()
    classes = db.session.query(Student.class_name).distinct().order_by(Student.class_name).all()
    classes = [c[0] for c in classes]
    
    # Статистика
    total_students = Student.query.count()
    total_matches = Match.query.count()
    completed_matches = Match.query.filter_by(is_completed=True).count()
    
    return render_template('index.html', 
                         championship=championship,
                         classes=classes,
                         total_students=total_students,
                         total_matches=total_matches,
                         completed_matches=completed_matches)


@app.route('/classes')
def classes():
    """Список класів"""
    classes_list = db.session.query(Student.class_name).distinct().order_by(Student.class_name).all()
    classes_data = []
    
    for class_tuple in classes_list:
        class_name = class_tuple[0]
        students = Student.query.filter_by(class_name=class_name).order_by(Student.last_name).all()
        classes_data.append({
            'name': class_name,
            'count': len(students)
        })
    
    return render_template('classes.html', classes=classes_data)


@app.route('/class/<class_name>')
def class_detail(class_name):
    """Детальна інформація про клас"""
    students = Student.query.filter_by(class_name=class_name).order_by(Student.seed).all()
    
    # Перевіряємо чи є жеребкування
    has_draw = any(s.seed is not None for s in students)
    
    return render_template('class_detail.html', 
                         class_name=class_name, 
                         students=students,
                         has_draw=has_draw)


@app.route('/bracket/<class_name>')
def bracket(class_name):
    """Турнірна сітка класу"""
    students = Student.query.filter_by(class_name=class_name).order_by(Student.seed).all()
    matches = Match.query.filter_by(class_name=class_name).order_by(Match.round_number, Match.match_number).all()
    
    # Групуємо матчі по раундах
    rounds = {}
    for match in matches:
        if match.round_number not in rounds:
            rounds[match.round_number] = []
        rounds[match.round_number].append(match)
    
    return render_template('bracket.html', 
                         class_name=class_name,
                         students=students,
                         rounds=sorted(rounds.items()))


@app.route('/matches')
def matches():
    """Список всіх поєдинків"""
    class_filter = request.args.get('class', '')
    name_filter = request.args.get('name', '')
    
    query = Match.query
    
    if class_filter:
        query = query.filter_by(class_name=class_filter)
    
    if name_filter:
        # Пошук по імені учня
        students = Student.query.filter(
            (Student.first_name.contains(name_filter)) |
            (Student.last_name.contains(name_filter)) |
            (Student.patronymic.contains(name_filter))
        ).all()
        student_ids = [s.id for s in students]
        query = query.filter(
            (Match.student1_id.in_(student_ids)) |
            (Match.student2_id.in_(student_ids))
        )
    
    matches_list = query.order_by(Match.scheduled_date.desc(), Match.round_number, Match.match_number).all()
    
    classes_list = db.session.query(Student.class_name).distinct().order_by(Student.class_name).all()
    classes_list = [c[0] for c in classes_list]
    
    return render_template('matches.html', 
                         matches=matches_list,
                         classes=classes_list,
                         class_filter=class_filter,
                         name_filter=name_filter)


# ==================== АДМІНІСТРАТИВНА ПАНЕЛЬ ====================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Вхід в адмінку"""
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == app.config['ADMIN_USERNAME'] and password == app.config['ADMIN_PASSWORD']:
            user = User('admin')
            login_user(user)
            flash('Успішний вхід!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Невірні дані для входу', 'danger')
    
    return render_template('admin/login.html')


@app.route('/admin/logout')
@login_required
def admin_logout():
    """Вихід з адмінки"""
    logout_user()
    flash('Ви вийшли з системи', 'info')
    return redirect(url_for('index'))


@app.route('/admin')
@login_required
def admin_dashboard():
    """Панель адміністратора"""
    classes_list = db.session.query(Student.class_name).distinct().order_by(Student.class_name).all()
    classes_data = []
    
    for class_tuple in classes_list:
        class_name = class_tuple[0]
        students_count = Student.query.filter_by(class_name=class_name).count()
        has_draw = db.session.query(Student).filter_by(class_name=class_name).filter(Student.seed.isnot(None)).count() > 0
        matches_count = Match.query.filter_by(class_name=class_name).count()
        
        classes_data.append({
            'name': class_name,
            'students_count': students_count,
            'has_draw': has_draw,
            'matches_count': matches_count
        })
    
    return render_template('admin/dashboard.html', classes=classes_data)


@app.route('/admin/students/<class_name>', methods=['GET', 'POST'])
@login_required
def admin_students(class_name):
    """Управління учнями класу"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            student = Student(
                first_name=request.form.get('first_name'),
                last_name=request.form.get('last_name'),
                patronymic=request.form.get('patronymic'),
                class_name=class_name
            )
            db.session.add(student)
            db.session.commit()
            flash(f'Учня {student.full_name} додано', 'success')
        
        elif action == 'delete':
            student_id = request.form.get('student_id')
            student = Student.query.get(student_id)
            if student:
                db.session.delete(student)
                db.session.commit()
                flash(f'Учня видалено', 'success')
        
        return redirect(url_for('admin_students', class_name=class_name))
    
    students = Student.query.filter_by(class_name=class_name).order_by(Student.last_name).all()
    return render_template('admin/students.html', class_name=class_name, students=students)


@app.route('/admin/draw/<class_name>', methods=['GET', 'POST'])
@login_required
def admin_draw(class_name):
    """Жеребкування для класу"""
    students = Student.query.filter_by(class_name=class_name).all()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'draw':
            # Проводимо жеребкування
            random.shuffle(students)
            for i, student in enumerate(students, 1):
                student.seed = i
            db.session.commit()
            
            # Генеруємо турнірну сітку
            generate_bracket(class_name)
            
            flash(f'Жеребкування для класу {class_name} проведено!', 'success')
            return redirect(url_for('admin_draw', class_name=class_name))
        
        elif action == 'update_ratings':
            # Оновлюємо рейтинги
            for student in students:
                rating_key = f'rating_{student.id}'
                if rating_key in request.form:
                    rating = request.form.get(rating_key)
                    student.rating = float(rating) if rating else 0
            db.session.commit()
            flash('Рейтинги оновлено!', 'success')
            return redirect(url_for('admin_draw', class_name=class_name))
    
    students = Student.query.filter_by(class_name=class_name).order_by(Student.rating.desc(), Student.seed).all()
    has_draw = any(s.seed is not None for s in students)
    
    # Розрахунок BYE
    n = len(students)
    bracket_size = 2 ** math.ceil(math.log2(n)) if n > 0 else 0
    byes_count = bracket_size - n
    
    return render_template('admin/draw.html', 
                         class_name=class_name, 
                         students=students,
                         has_draw=has_draw,
                         byes_count=byes_count)


def generate_bracket(class_name):
    """Генерація турнірної сітки після жеребкування з урахуванням рейтингу"""
    students = Student.query.filter_by(class_name=class_name).order_by(
        Student.rating.desc(), Student.seed
    ).all()
    n = len(students)
    
    # Видаляємо старі матчі
    Match.query.filter_by(class_name=class_name).delete()
    
    # Знаходимо найближчу степінь 2
    bracket_size = 2 ** math.ceil(math.log2(n))
    byes = bracket_size - n
    
    # СПЕЦІАЛЬНА ЛОГІКА ДЛЯ 5-А (33 учні)
    if n == 33 and '5' in class_name:
        # Всі крім 2 останніх отримують автопрохід в основну сітку
        for i, student in enumerate(students):
            if i < 31:  # Перші 31
                student.has_bye = True
            else:  # Останні 2
                student.has_bye = False
        db.session.commit()
        
        # Створюємо КВАЛІФІКАЦІЙНИЙ матч (round 0)
        qualification_match = Match(
            student1_id=students[-2].id,  # 32-й учень (слабший)
            student2_id=students[-1].id,  # 33-й учень (найслабший)
            class_name=class_name,
            round_number=0,  # Раунд 0 = кваліфікація
            match_number=1
        )
        db.session.add(qualification_match)
        db.session.flush()  # Зберігаємо кваліфікацію
        
        # Створюємо основну сітку для 32 місць (1/16, 1/8, 1/4, 1/2, фінал)
        total_rounds = 5
        
        # 1/16 фіналу (16 матчів для 32 учнів)
        # Розставляємо перших 30 учнів парами (матчі 1-15)
        for match_num in range(1, 16):
            idx1 = (match_num - 1) * 2  # 0, 2, 4, 6... до 28
            idx2 = idx1 + 1              # 1, 3, 5, 7... до 29
            
            match = Match(
                student1_id=students[idx1].id,
                student2_id=students[idx2].id,
                class_name=class_name,
                round_number=1,
                match_number=match_num
            )
            db.session.add(match)
        
        # Останній 16-й матч: 31-й учень vs переможець кваліфікації
        match = Match(
            student1_id=students[30].id,  # 31-й учень
            student2_id=None,  # Переможець кваліфікації (заповниться після)
            class_name=class_name,
            round_number=1,
            match_number=16
        )
        db.session.add(match)
        
        # Решта раундів (1/8, 1/4, 1/2, фінал)
        for round_num in range(2, total_rounds + 1):
            matches_in_round = 2 ** (total_rounds - round_num)
            for match_num in range(1, matches_in_round + 1):
                match = Match(
                    student1_id=None,
                    student2_id=None,
                    class_name=class_name,
                    round_number=round_num,
                    match_number=match_num
                )
                db.session.add(match)
        
        db.session.commit()
        return
    
    # СТАНДАРТНА ЛОГІКА ДЛЯ РЕШТИ КЛАСІВ (з BYE)
    # Позначаємо учнів з автопроходом (найсильніші за рейтингом)
    for i, student in enumerate(students):
        if i < byes:
            student.has_bye = True
        else:
            student.has_bye = False
    db.session.commit()
    
    # Створюємо перший раунд
    match_num = 1
    
    # Спочатку додаємо учнів з BYE
    for i in range(byes):
        student1 = students[i]
        match = Match(
            student1_id=student1.id,
            student2_id=None,  # BYE
            class_name=class_name,
            round_number=1,
            match_number=match_num,
            winner_id=student1.id,
            is_completed=True
        )
        db.session.add(match)
        match_num += 1
    
    # Потім додаємо звичайні матчі для решти учнів
    remaining_students = students[byes:]
    for i in range(0, len(remaining_students), 2):
        if i + 1 < len(remaining_students):
            student1 = remaining_students[i]
            student2 = remaining_students[i + 1]
            
            match = Match(
                student1_id=student1.id,
                student2_id=student2.id,
                class_name=class_name,
                round_number=1,
                match_number=match_num
            )
            db.session.add(match)
            match_num += 1
    
    db.session.commit()
    
    # Генеруємо наступні раунди (поки пусті)
    total_rounds = math.ceil(math.log2(bracket_size))
    for round_num in range(2, total_rounds + 1):
        matches_in_round = 2 ** (total_rounds - round_num)
        for match_num in range(1, matches_in_round + 1):
            match = Match(
                student1_id=None,
                student2_id=None,
                class_name=class_name,
                round_number=round_num,
                match_number=match_num
            )
            db.session.add(match)
    
    db.session.commit()


@app.route('/admin/match/<int:match_id>', methods=['POST'])
@login_required
def admin_update_match(match_id):
    """Оновлення результатів матчу"""
    match = Match.query.get_or_404(match_id)
    
    winner_id = request.form.get('winner_id')
    score1 = request.form.get('score1')
    score2 = request.form.get('score2')
    scheduled_date = request.form.get('scheduled_date')
    
    if winner_id:
        match.winner_id = int(winner_id)
        match.is_completed = True
        match.completed_date = datetime.utcnow()
    
    if score1:
        match.score1 = int(score1)
    if score2:
        match.score2 = int(score2)
    
    if scheduled_date:
        match.scheduled_date = datetime.fromisoformat(scheduled_date)
    
    match.notes = request.form.get('notes', '')
    
    db.session.commit()
    
    # Оновлюємо наступний раунд
    update_next_round(match)
    
    flash('Результат матчу оновлено', 'success')
    return redirect(request.referrer or url_for('admin_dashboard'))


def update_next_round(match):
    """Оновлення учасників наступного раунду"""
    if not match.is_completed or not match.winner_id:
        return
    
    # Знаходимо матч наступного раунду
    next_round = match.round_number + 1
    next_match_num = (match.match_number + 1) // 2
    
    next_match = Match.query.filter_by(
        class_name=match.class_name,
        round_number=next_round,
        match_number=next_match_num
    ).first()
    
    if next_match:
        # Визначаємо позицію (перший чи другий учень)
        if match.match_number % 2 == 1:
            next_match.student1_id = match.winner_id
        else:
            next_match.student2_id = match.winner_id
        
        db.session.commit()


@app.route('/admin/schedule/<class_name>', methods=['GET', 'POST'])
@login_required
def admin_schedule(class_name):
    """Планування розкладу матчів"""
    if request.method == 'POST':
        # Масове оновлення дат
        for key, value in request.form.items():
            if key.startswith('match_'):
                match_id = int(key.split('_')[1])
                match = Match.query.get(match_id)
                if match and value:
                    match.scheduled_date = datetime.fromisoformat(value)
        
        db.session.commit()
        flash('Розклад оновлено', 'success')
        return redirect(url_for('admin_schedule', class_name=class_name))
    
    matches = Match.query.filter_by(class_name=class_name).order_by(
        Match.round_number, Match.match_number
    ).all()
    
    return render_template('admin/schedule.html', class_name=class_name, matches=matches)


# ==================== ІНІЦІАЛІЗАЦІЯ ====================

@app.cli.command()
def init_db():
    """Ініціалізація бази даних"""
    import os
    
    # Видалити стару базу якщо існує
    if os.path.exists('championship.db'):
        os.remove('championship.db')
        print("Стару базу видалено")
    
    db.create_all()
    
    # Створюємо запис чемпіонату
    championship = Championship(
        name="Чемпіонат зі Швидкочислення 2024-2025",
        start_date=datetime.now(),
        is_active=True
    )
    db.session.add(championship)
    db.session.commit()
    
    print("База даних ініціалізована!")


@app.cli.command()
def add_sample_data():
    """Додавання тестових даних"""
    classes = ['5-А', '6-А', '6-Б', '7-А', '7-Б']
    first_names = ['Іван', 'Марія', 'Петро', 'Оксана', 'Андрій', 'Софія', 'Микола', 'Анна']
    last_names = ['Коваленко', 'Шевченко', 'Бойко', 'Мельник', 'Ткаченко', 'Кравченко', 'Морозов', 'Поліщук']
    
    for class_name in classes:
        for i in range(8):
            student = Student(
                first_name=random.choice(first_names),
                last_name=random.choice(last_names),
                patronymic='Іванович' if random.random() > 0.5 else 'Петрович',
                class_name=class_name,
                rating=random.randint(6, 12)
            )
            db.session.add(student)
    
    db.session.commit()
    print("Тестові дані додано!")


@app.cli.command()
def create_real_data():
    """Створити структуру для реальних класів"""
    # Спочатку очищаємо
    Student.query.delete()
    Match.query.delete()
    db.session.commit()
    
    # Створюємо класи з правильною кількістю місць
    classes_data = [
        ('5-А', 33),
        ('6-А', 31),
        ('6-Б', 27),
        ('7-А', 27),
        ('7-Б', 29)
    ]
    
    first_names = ['Іван', 'Марія', 'Петро', 'Оксана', 'Андрій', 'Софія', 'Микола', 'Анна', 
                   'Дмитро', 'Олена', 'Володимир', 'Юлія', 'Олександр', 'Катерина', 'Сергій', 'Наталія']
    last_names = ['Коваленко', 'Шевченко', 'Бойко', 'Мельник', 'Ткаченко', 'Кравченко', 'Морозов', 'Поліщук',
                  'Лисенко', 'Павленко', 'Іваненко', 'Савченко', 'Гнатенко', 'Руденко', 'Ковальчук', 'Романенко']
    patronymics = ['Іванович', 'Петрович', 'Володимирович', 'Андрійович', 'Михайлович', 'Олександрович',
                   'Іванівна', 'Петрівна', 'Володимирівна', 'Андріївна', 'Михайлівна', 'Олександрівна']
    
    total = 0
    for class_name, count in classes_data:
        for i in range(count):
            student = Student(
                first_name=random.choice(first_names),
                last_name=random.choice(last_names),
                patronymic=random.choice(patronymics),
                class_name=class_name,
                rating=round(random.uniform(6, 12), 1)
            )
            db.session.add(student)
            total += 1
    
    db.session.commit()
    print(f"✅ Створено {total} учнів:")
    for class_name, count in classes_data:
        print(f"   {class_name}: {count} учнів")
    print("\n💡 Тепер зайдіть в адмінку та проведіть жеребкування для кожного класу!")


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)