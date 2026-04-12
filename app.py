from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import init_db, Student, Match, SuperfinalMatch, Championship
from config import Config
from datetime import datetime
import random
import math

app = Flask(__name__)
app.config.from_object(Config)

init_db(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'


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
    championship = Championship.objects.first()
    classes = sorted(Student.objects.distinct('class_name'))
    total_students = Student.objects.count()
    total_matches = Match.objects.count()
    completed_matches = Match.objects(is_completed=True).count()
    return render_template('index.html',
                           championship=championship,
                           classes=classes,
                           total_students=total_students,
                           total_matches=total_matches,
                           completed_matches=completed_matches)


@app.route('/classes')
def classes():
    classes_list = sorted(Student.objects.distinct('class_name'))
    classes_data = []
    for class_name in classes_list:
        count = Student.objects(class_name=class_name).count()
        classes_data.append({'name': class_name, 'count': count})
    return render_template('classes.html', classes=classes_data)


@app.route('/class/<class_name>')
def class_detail(class_name):
    students = Student.objects(class_name=class_name).order_by('last_name')
    matches = Match.objects(class_name=class_name).order_by('round_number', 'match_number')
    has_bracket = matches.count() > 0
    return render_template('class_detail.html',
                           class_name=class_name,
                           students=students,
                           has_bracket=has_bracket)


@app.route('/bracket/<class_name>')
def bracket(class_name):
    matches_list = list(Match.objects(class_name=class_name).order_by('round_number', 'match_number'))

    # Один запит для всіх учнів
    student_ids = set()
    for m in matches_list:
        if m.student1_id and m.student1_id != 'BYE': student_ids.add(m.student1_id)
        if m.student2_id and m.student2_id != 'BYE': student_ids.add(m.student2_id)
        if m.winner_id: student_ids.add(m.winner_id)
    students_map = {str(s.id): s for s in Student.objects(id__in=list(student_ids))} if student_ids else {}

    rounds = {}
    for match in matches_list:
        key = (match.round_number, match.round_name)
        if key not in rounds:
            rounds[key] = []
        rounds[key].append(match)

    return render_template('bracket.html',
                           class_name=class_name,
                           rounds=sorted(rounds.items()),
                           students_map=students_map)


@app.route('/matches')
@login_required
def matches():
    class_filter = request.args.get('class', '')
    status_filter = request.args.get('status', 'ready')

    # Базовий запит — без BYE матчів
    base_q = Match.objects(student2_id__ne='BYE', student1_id__ne='BYE')
    if class_filter:
        base_q = base_q(class_name=class_filter)

    # Фільтр по статусу — одразу в MongoDB
    if status_filter == 'ready':
        # Обидва гравці є і матч не завершений
        query = base_q(
            student1_id__ne=None,
            student2_id__ne=None,
            is_completed=False
        )
    elif status_filter == 'completed':
        query = base_q(is_completed=True)
    elif status_filter == 'pending':
        query = base_q(is_completed=False)
    else:
        query = base_q

    matches_list = list(query.order_by('class_name', 'round_number', 'match_number'))

    classes_list = sorted(Student.objects.distinct('class_name'))

    # Статистика — тільки count запити, без завантаження даних
    total = base_q.count()
    completed = base_q(is_completed=True).count()
    pending = total - completed

    return render_template('matches.html',
                           matches=matches_list,
                           classes=classes_list,
                           class_filter=class_filter,
                           status_filter=status_filter,
                           total=total,
                           completed=completed,
                           pending=pending)



@app.route('/results')
def results():
    """Публічна сторінка результатів — тільки перегляд"""
    class_filter = request.args.get('class', '')
    round_filter = request.args.get('round', '')

    query = Match.objects(is_completed=True)
    if class_filter:
        query = query(class_name=class_filter)
    if round_filter:
        query = query(round_name=round_filter)

    matches_list = list(query.order_by('class_name', 'round_number', 'match_number'))

    # Один запит для всіх учнів
    student_ids = set()
    for m in matches_list:
        if m.student1_id: student_ids.add(m.student1_id)
        if m.student2_id and m.student2_id != 'BYE': student_ids.add(m.student2_id)
        if m.winner_id: student_ids.add(m.winner_id)
    students_map = {str(s.id): s for s in Student.objects(id__in=list(student_ids))} if student_ids else {}

    classes_list = sorted(Student.objects.distinct('class_name'))

    all_rounds = Match.objects.distinct('round_name')
    round_order = ['qualification', '1/32', '1/16', '1/8', '1/4', '1/2', 'final']
    rounds = sorted(all_rounds, key=lambda r: round_order.index(r) if r in round_order else 99)

    total = Match.objects.count()
    completed_count = Match.objects(is_completed=True).count()

    return render_template('results.html',
                           matches=matches_list,
                           students_map=students_map,
                           classes=classes_list,
                           rounds=rounds,
                           class_filter=class_filter,
                           round_filter=round_filter,
                           total=total,
                           completed=completed_count)


@app.route('/rules')
def rules():
    return render_template('rules.html')


@app.route('/superfinal')
def superfinal():
    sf_matches = SuperfinalMatch.objects.order_by('match_number')
    
    # Таблиця результатів
    participants = []
    all_student_ids = set()
    for m in sf_matches:
        if m.student1_id:
            all_student_ids.add(m.student1_id)
        if m.student2_id:
            all_student_ids.add(m.student2_id)
    
    standings = {}
    for sid in all_student_ids:
        try:
            s = Student.objects.get(id=sid)
            standings[sid] = {'student': s, 'wins': 0, 'losses': 0, 'played': 0}
        except:
            pass
    
    for m in sf_matches:
        if m.is_completed and m.winner_id:
            loser_id = m.student2_id if m.winner_id == m.student1_id else m.student1_id
            if m.winner_id in standings:
                standings[m.winner_id]['wins'] += 1
                standings[m.winner_id]['played'] += 1
            if loser_id in standings:
                standings[loser_id]['losses'] += 1
                standings[loser_id]['played'] += 1
    
    standings_list = sorted(standings.values(), key=lambda x: (-x['wins'], x['losses']))
    
    return render_template('superfinal.html',
                           matches=sf_matches,
                           standings=standings_list)


# ==================== АДМІНКА ====================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == app.config['ADMIN_USERNAME'] and password == app.config['ADMIN_PASSWORD']:
            login_user(User('admin'))
            flash('Успішний вхід!', 'success')
            return redirect(url_for('admin_dashboard'))
        flash('Невірні дані для входу', 'danger')
    return render_template('admin/login.html')


@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/admin')
@login_required
def admin_dashboard():
    classes_list = sorted(Student.objects.distinct('class_name'))
    classes_data = []
    for class_name in classes_list:
        students_count = Student.objects(class_name=class_name).count()
        matches_count = Match.objects(class_name=class_name).count()
        completed = Match.objects(class_name=class_name, is_completed=True).count()
        classes_data.append({
            'name': class_name,
            'students_count': students_count,
            'matches_count': matches_count,
            'completed_matches': completed,
            'has_bracket': matches_count > 0
        })
    return render_template('admin/dashboard.html', classes=classes_data)


# ==================== УЧНІ ====================

@app.route('/admin/students/<class_name>', methods=['GET', 'POST'])
@login_required
def admin_students(class_name):
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add':
            Student(
                first_name=request.form.get('first_name'),
                last_name=request.form.get('last_name'),
                patronymic=request.form.get('patronymic') or None,
                class_name=class_name,
                rating=float(request.form.get('rating') or 0)
            ).save()
            flash('Учня додано', 'success')

        elif action == 'delete':
            student_id = request.form.get('student_id')
            Student.objects(id=student_id).delete()
            flash('Учня видалено', 'success')

        elif action == 'update_status':
            # Оновлення статусів всіх учнів класу
            students = Student.objects(class_name=class_name)
            for student in students:
                status = request.form.get(f'status_{student.id}', 'none')
                student.bracket_status = status
                student.save()
            flash('Статуси оновлено', 'success')

        return redirect(url_for('admin_students', class_name=class_name))

    students = sorted(Student.objects(class_name=class_name), key=lambda s: (s.last_name.lower(), s.first_name.lower()))
    return render_template('admin/students.html', class_name=class_name, students=students)


# ==================== ПОБУДОВА СІТКИ (DRAG & DROP) ====================

@app.route('/admin/bracket-builder/<class_name>')
@login_required
def bracket_builder(class_name):
    students_main = Student.objects(class_name=class_name, bracket_status='main').order_by('-rating')
    students_qual = Student.objects(class_name=class_name, bracket_status='qualification').order_by('-rating')
    students_none = Student.objects(class_name=class_name, bracket_status='none').order_by('last_name')
    
    existing_matches = Match.objects(class_name=class_name).order_by('round_number', 'match_number')
    
    # Учні що вже в якомусь матчі
    used_student_ids = set()
    for m in existing_matches:
        if m.student1_id and m.student1_id != 'BYE':
            used_student_ids.add(m.student1_id)
        if m.student2_id and m.student2_id != 'BYE':
            used_student_ids.add(m.student2_id)
    
    return render_template('admin/bracket_builder.html',
                           class_name=class_name,
                           students_main=students_main,
                           students_qual=students_qual,
                           students_none=students_none,
                           existing_matches=existing_matches,
                           used_student_ids=used_student_ids)


@app.route('/admin/bracket-builder/<class_name>/generate', methods=['POST'])
@login_required
def generate_bracket_slots(class_name):
    """Генерує порожні слоти для сітки"""
    data = request.get_json()
    round_name = data.get('round_name')
    bracket_type = data.get('bracket_type', 'main')
    qual_slots = data.get('qual_slots', 2)  # скільки виходять з кваліфікації
    
    round_sizes = {
        'qualification': qual_slots,
        '1/32': 16,
        '1/16': 16,
        '1/8': 8,
        '1/4': 4,
        '1/2': 2,
        'final': 1,
    }
    
    round_order = {
        'qualification': 0,
        '1/32': 1,
        '1/16': 2,
        '1/8': 3,
        '1/4': 4,
        '1/2': 5,
        'final': 6,
    }
    
    num_matches = round_sizes.get(round_name)
    if not num_matches:
        return jsonify({'error': 'Невідомий раунд'}), 400
    
    # Перевіряємо чи такий раунд вже є
    existing = Match.objects(
        class_name=class_name,
        round_name=round_name,
        bracket_type=bracket_type
    ).count()
    
    if existing > 0:
        return jsonify({'error': f'Раунд {round_name} вже існує для цього класу'}), 400
    
    # Створюємо порожні матчі
    created = []
    for i in range(1, num_matches + 1):
        match = Match(
            class_name=class_name,
            bracket_type=bracket_type,
            round_name=round_name,
            round_number=round_order.get(round_name, 99),
            match_number=i,
            student1_id=None,
            student2_id=None
        ).save()
        created.append(str(match.id))
    
    return jsonify({'success': True, 'created': len(created), 'match_ids': created})


@app.route('/admin/bracket-builder/assign', methods=['POST'])
@login_required
def assign_student_to_slot():
    """Призначає учня до слоту матчу (drag & drop)"""
    data = request.get_json()
    match_id = data.get('match_id')
    slot = data.get('slot')  # 'student1' або 'student2'
    student_id = data.get('student_id')  # або 'BYE'
    
    try:
        match = Match.objects.get(id=match_id)
    except:
        return jsonify({'error': 'Матч не знайдено'}), 404
    
    if slot == 'student1':
        match.student1_id = student_id
    elif slot == 'student2':
        match.student2_id = student_id
    
    # Якщо BYE — одразу завершуємо матч
    if match.student1_id and match.student2_id == 'BYE':
        match.winner_id = match.student1_id
        match.is_completed = True
        match.completed_date = datetime.utcnow()
    elif match.student2_id and match.student1_id == 'BYE':
        match.winner_id = match.student2_id
        match.is_completed = True
        match.completed_date = datetime.utcnow()
    
    match.save()

    # Якщо матч завершився через BYE — перевіряємо наступний раунд
    if match.is_completed:
        maybe_advance_round(match)

    return jsonify({
        'success': True,
        'is_completed': match.is_completed,
        'winner_id': match.winner_id
    })


@app.route('/admin/bracket-builder/remove-slot', methods=['POST'])
@login_required
def remove_from_slot():
    """Прибирає учня зі слоту"""
    data = request.get_json()
    match_id = data.get('match_id')
    slot = data.get('slot')
    
    try:
        match = Match.objects.get(id=match_id)
    except:
        return jsonify({'error': 'Матч не знайдено'}), 404
    
    if slot == 'student1':
        match.student1_id = None
    elif slot == 'student2':
        match.student2_id = None
    
    # Скидаємо результат якщо прибрали учасника
    match.winner_id = None
    match.is_completed = False
    match.completed_date = None
    match.save()
    
    return jsonify({'success': True})


@app.route('/admin/bracket-builder/delete-round', methods=['POST'])
@login_required
def delete_round():
    """Видаляє весь раунд"""
    data = request.get_json()
    class_name = data.get('class_name')
    round_name = data.get('round_name')
    bracket_type = data.get('bracket_type', 'main')
    
    Match.objects(
        class_name=class_name,
        round_name=round_name,
        bracket_type=bracket_type
    ).delete()
    
    return jsonify({'success': True})


# ==================== РЕЗУЛЬТАТИ МАТЧІВ ====================

@app.route('/admin/match/<match_id>/result', methods=['POST'])
@login_required
def update_match_result(match_id):
    """Оновлення результату матчу"""
    try:
        match = Match.objects.get(id=match_id)
    except:
        flash('Матч не знайдено', 'danger')
        return redirect(request.referrer or url_for('admin_dashboard'))
    
    winner_id = request.form.get('winner_id')
    if winner_id:
        match.winner_id = winner_id
        match.is_completed = True
        match.completed_date = datetime.utcnow()
        match.notes = request.form.get('notes', '')
        match.save()
        flash('Результат збережено', 'success')
    
    return redirect(request.referrer or url_for('admin_dashboard'))


ROUND_ORDER = ['qualification', '1/32', '1/16', '1/8', '1/4', '1/2', 'final']
ROUND_SIZES  = {
    'qualification': None,  # dynamic
    '1/32': 16, '1/16': 16, '1/8': 8,
    '1/4': 4, '1/2': 2, 'final': 1
}
ROUND_NUMBER = {r: i for i, r in enumerate(ROUND_ORDER)}


def get_next_round(current_round):
    try:
        idx = ROUND_ORDER.index(current_round)
        if idx + 1 < len(ROUND_ORDER):
            return ROUND_ORDER[idx + 1]
    except ValueError:
        pass
    return None


def maybe_advance_round(match):
    """Одразу після визначення переможця просуває його в наступний раунд"""
    if not match.winner_id:
        return
    if match.round_name == 'final':
        return

    # ── Кваліфікація ──
    # Переможець одразу йде в порожній слот основної сітки
    if match.bracket_type == 'qualification':
        main_round_match = Match.objects(
            class_name=match.class_name,
            bracket_type='main'
        ).order_by('round_number', 'match_number').first()

        if not main_round_match:
            return

        main_round_name = main_round_match.round_name
        main_matches = list(Match.objects(
            class_name=match.class_name,
            bracket_type='main',
            round_name=main_round_name
        ).order_by('match_number'))

        # Знаходимо перший порожній слот
        for m in main_matches:
            if not m.student1_id:
                m.student1_id = match.winner_id
                _check_bye_and_save(m)
                return
            if not m.student2_id:
                m.student2_id = match.winner_id
                _check_bye_and_save(m)
                return
        return

    # ── Основна сітка ──
    next_round = get_next_round(match.round_name)
    if not next_round:
        return

    # Визначаємо позицію в наступному раунді
    # Пара N → наступна пара ceil(N/2), слот залежить від парності
    next_match_num = math.ceil(match.match_number / 2)
    slot = 'student1' if match.match_number % 2 == 1 else 'student2'

    # Шукаємо існуючий матч наступного раунду
    next_match = Match.objects(
        class_name=match.class_name,
        bracket_type='main',
        round_name=next_round,
        match_number=next_match_num
    ).first()

    if next_match:
        # Слот вже існує — заповнюємо
        if slot == 'student1' and not next_match.student1_id:
            next_match.student1_id = match.winner_id
        elif slot == 'student2' and not next_match.student2_id:
            next_match.student2_id = match.winner_id
        else:
            # Слот зайнятий — шукаємо будь-який порожній
            if not next_match.student1_id:
                next_match.student1_id = match.winner_id
            elif not next_match.student2_id:
                next_match.student2_id = match.winner_id
        _check_bye_and_save(next_match)
    else:
        # Матчу ще немає — створюємо
        all_current = list(Match.objects(
            class_name=match.class_name,
            bracket_type='main',
            round_name=match.round_name
        ).order_by('match_number'))
        total = len(all_current)
        num_next = math.ceil(total / 2)

        # Створюємо всі матчі наступного раунду якщо їх ще немає
        for i in range(1, num_next + 1):
            exists = Match.objects(
                class_name=match.class_name,
                bracket_type='main',
                round_name=next_round,
                match_number=i
            ).first()
            if not exists:
                Match(
                    class_name=match.class_name,
                    bracket_type='main',
                    round_name=next_round,
                    round_number=ROUND_NUMBER.get(next_round, 99),
                    match_number=i
                ).save()

        # Тепер заповнюємо потрібний слот
        new_next = Match.objects(
            class_name=match.class_name,
            bracket_type='main',
            round_name=next_round,
            match_number=next_match_num
        ).first()
        if new_next:
            if slot == 'student1':
                new_next.student1_id = match.winner_id
            else:
                new_next.student2_id = match.winner_id
            _check_bye_and_save(new_next)


def _check_bye_and_save(m):
    """Перевіряє BYE і зберігає матч"""
    if m.student1_id and m.student2_id == 'BYE':
        m.winner_id = m.student1_id
        m.is_completed = True
        m.completed_date = datetime.utcnow()
    elif m.student2_id and m.student1_id == 'BYE':
        m.winner_id = m.student2_id
        m.is_completed = True
        m.completed_date = datetime.utcnow()
    m.save()
    # Рекурсивно просуваємо якщо BYE завершив матч
    if m.is_completed and m.winner_id:
        maybe_advance_round(m)





@app.route('/admin/match/<match_id>/result-ajax', methods=['POST'])
@login_required
def update_match_result_ajax(match_id):
    """AJAX оновлення результату"""
    data = request.get_json()
    try:
        match = Match.objects.get(id=match_id)
    except:
        return jsonify({'error': 'Матч не знайдено'}), 404

    winner_id = data.get('winner_id')
    if winner_id:
        match.winner_id = winner_id
        match.is_completed = True
        match.completed_date = datetime.utcnow()
        match.save()

        # Перевіряємо чи треба створити наступний раунд
        maybe_advance_round(match)

    return jsonify({'success': True})


@app.route('/admin/match/<match_id>/reset', methods=['POST'])
@login_required
def reset_match_result(match_id):
    """Скидання результату матчу"""
    try:
        match = Match.objects.get(id=match_id)
    except:
        return jsonify({'error': 'Матч не знайдено'}), 404

    old_winner_id = match.winner_id

    match.winner_id = None
    match.is_completed = False
    match.completed_date = None
    match.save()

    # Прибираємо переможця з наступного раунду
    if old_winner_id:
        next_round = get_next_round(match.round_name)
        if next_round:
            next_match_num = math.ceil(match.match_number / 2)
            next_match = Match.objects(
                class_name=match.class_name,
                bracket_type=match.bracket_type,
                round_name=next_round,
                match_number=next_match_num
            ).first()
            if next_match:
                if next_match.student1_id == old_winner_id:
                    next_match.student1_id = None
                elif next_match.student2_id == old_winner_id:
                    next_match.student2_id = None
                # Скидаємо результат наступного матчу теж
                next_match.winner_id = None
                next_match.is_completed = False
                next_match.completed_date = None
                next_match.save()

    return jsonify({'success': True})


@app.route('/admin/superfinal/result-ajax', methods=['POST'])
@login_required
def superfinal_result_ajax():
    data = request.get_json()
    match_id = data.get('match_id')
    winner_id = data.get('winner_id')
    try:
        m = SuperfinalMatch.objects.get(id=match_id)
        m.winner_id = winner_id
        m.is_completed = True
        m.completed_date = datetime.utcnow()
        m.save()
        return jsonify({'success': True})
    except:
        return jsonify({'error': 'Помилка'}), 404


@app.route('/admin/superfinal/reset-ajax', methods=['POST'])
@login_required
def superfinal_reset_ajax():
    data = request.get_json()
    match_id = data.get('match_id')
    try:
        m = SuperfinalMatch.objects.get(id=match_id)
        m.winner_id = None
        m.is_completed = False
        m.completed_date = None
        m.save()
        return jsonify({'success': True})
    except:
        return jsonify({'error': 'Помилка'}), 404


# ==================== РАНДОМАЙЗЕР ====================

@app.route('/admin/randomize/<class_name>', methods=['GET', 'POST'])
@login_required
def randomize_bracket(class_name):
    """Автоматична генерація сітки через рандомайзер"""
    students = Student.objects(class_name=class_name).order_by('-rating')
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'randomize':
            round_name = request.form.get('round_name', '1/16')
            
            # Видаляємо старі матчі
            Match.objects(class_name=class_name).delete()
            
            students_list = list(students)
            random.shuffle(students_list)
            
            round_order = {
                '1/32': 1, '1/16': 2, '1/8': 3,
                '1/4': 4, '1/2': 5, 'final': 6
            }
            
            round_sizes = {
                '1/32': 16, '1/16': 16, '1/8': 8,
                '1/4': 4, '1/2': 2, 'final': 1
            }
            
            num_matches = round_sizes.get(round_name, 16)
            n = len(students_list)
            
            # Розставляємо учнів по парах
            for i in range(min(num_matches, n // 2)):
                s1 = students_list[i * 2] if i * 2 < n else None
                s2 = students_list[i * 2 + 1] if i * 2 + 1 < n else None
                
                match = Match(
                    class_name=class_name,
                    bracket_type='main',
                    round_name=round_name,
                    round_number=round_order.get(round_name, 2),
                    match_number=i + 1,
                    student1_id=str(s1.id) if s1 else None,
                    student2_id=str(s2.id) if s2 else 'BYE'
                )
                
                # BYE — одразу переможець
                if match.student2_id == 'BYE' and match.student1_id:
                    match.winner_id = match.student1_id
                    match.is_completed = True
                
                match.save()
            
            flash(f'Сітку рандомно згенеровано для {class_name}!', 'success')
            return redirect(url_for('bracket', class_name=class_name))
    
    return render_template('admin/randomize.html',
                           class_name=class_name,
                           students=students)


# ==================== СУПЕРФІНАЛ ====================

@app.route('/admin/superfinal', methods=['GET', 'POST'])
@login_required
def admin_superfinal():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'generate':
            # Отримуємо переможців фіналів кожного класу
            SuperfinalMatch.objects.delete()
            
            finalist_ids = request.form.getlist('finalist_ids')
            
            # Генеруємо кругову систему
            match_num = 1
            for i in range(len(finalist_ids)):
                for j in range(i + 1, len(finalist_ids)):
                    SuperfinalMatch(
                        student1_id=finalist_ids[i],
                        student2_id=finalist_ids[j],
                        match_number=match_num
                    ).save()
                    match_num += 1
            
            flash(f'Суперфінал згенеровано! {match_num - 1} матчів.', 'success')
        
        elif action == 'update_result':
            match_id = request.form.get('match_id')
            winner_id = request.form.get('winner_id')
            try:
                m = SuperfinalMatch.objects.get(id=match_id)
                m.winner_id = winner_id
                m.is_completed = True
                m.completed_date = datetime.utcnow()
                m.save()
                flash('Результат збережено', 'success')
            except:
                flash('Помилка', 'danger')
        
        return redirect(url_for('admin_superfinal'))
    
    # Збираємо фіналістів — переможці фінальних матчів кожного класу
    classes_list = sorted(Student.objects.distinct('class_name'))
    finalists = []
    for class_name in classes_list:
        final_match = Match.objects(
            class_name=class_name,
            round_name='final',
            is_completed=True
        ).first()
        if final_match and final_match.winner:
            finalists.append({
                'class_name': class_name,
                'student': final_match.winner
            })
    
    sf_matches = SuperfinalMatch.objects.order_by('match_number')
    
    return render_template('admin/superfinal.html',
                           finalists=finalists,
                           sf_matches=sf_matches)


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)