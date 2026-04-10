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
    matches = Match.objects(class_name=class_name).order_by('round_number', 'match_number')
    rounds = {}
    for match in matches:
        key = (match.round_number, match.round_name)
        if key not in rounds:
            rounds[key] = []
        rounds[key].append(match)
    return render_template('bracket.html',
                           class_name=class_name,
                           rounds=sorted(rounds.items()))


@app.route('/matches')
def matches():
    class_filter = request.args.get('class', '')
    query = Match.objects
    if class_filter:
        query = query(class_name=class_filter)
    matches_list = query.order_by('class_name', 'round_number', 'match_number')
    classes_list = sorted(Student.objects.distinct('class_name'))
    return render_template('matches.html',
                           matches=matches_list,
                           classes=classes_list,
                           class_filter=class_filter)


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
    """Перевіряє чи всі матчі раунду завершені і просуває переможців далі"""
    if match.round_name == 'final':
        return  # фінал — далі нема

    # Всі матчі цього раунду і типу сітки
    all_matches = list(Match.objects(
        class_name=match.class_name,
        round_name=match.round_name,
        bracket_type=match.bracket_type
    ).order_by('match_number'))

    # Перевіряємо чи всі завершені
    if not all(m.is_completed for m in all_matches):
        return

    winners = [m.winner_id for m in all_matches if m.winner_id]
    if not winners:
        return

    # ── Кваліфікація ──
    # Переможці йдуть у порожні слоти основної сітки (будь-який існуючий раунд)
    if match.bracket_type == 'qualification':
        # Знаходимо перший існуючий раунд основної сітки
        main_round_match = Match.objects(
            class_name=match.class_name,
            bracket_type='main'
        ).order_by('round_number', 'match_number').first()

        if not main_round_match:
            return  # основна сітка ще не створена — нічого не робимо

        main_round_name = main_round_match.round_name
        main_matches = list(Match.objects(
            class_name=match.class_name,
            bracket_type='main',
            round_name=main_round_name
        ).order_by('match_number'))

        # Розставляємо переможців кваліфікації у порожні слоти основної сітки
        winner_idx = 0
        for m in main_matches:
            if winner_idx >= len(winners):
                break
            changed = False
            if not m.student1_id:
                m.student1_id = winners[winner_idx]
                winner_idx += 1
                changed = True
            if winner_idx < len(winners) and not m.student2_id:
                m.student2_id = winners[winner_idx]
                winner_idx += 1
                changed = True
            if changed:
                # BYE автоматика
                if m.student1_id and m.student2_id == 'BYE':
                    m.winner_id = m.student1_id
                    m.is_completed = True
                    m.completed_date = datetime.utcnow()
                elif m.student2_id and m.student1_id == 'BYE':
                    m.winner_id = m.student2_id
                    m.is_completed = True
                    m.completed_date = datetime.utcnow()
                m.save()
        return

    # ── Основна сітка ──
    next_round = get_next_round(match.round_name)
    if not next_round:
        return

    # Перевіряємо чи наступний раунд вже існує
    existing = Match.objects(
        class_name=match.class_name,
        round_name=next_round,
        bracket_type='main'
    ).count()

    if existing > 0:
        # Раунд вже є — розставляємо переможців у порожні слоти
        _fill_next_round_winners(match.class_name, next_round, 'main', all_matches)
        return

    # Створюємо наступний раунд автоматично
    num_next = math.ceil(len(winners) / 2)
    if num_next == 0:
        return

    for i in range(num_next):
        s1 = winners[i * 2] if i * 2 < len(winners) else None
        s2 = winners[i * 2 + 1] if i * 2 + 1 < len(winners) else None

        new_match = Match(
            class_name=match.class_name,
            bracket_type='main',
            round_name=next_round,
            round_number=ROUND_NUMBER.get(next_round, 99),
            match_number=i + 1,
            student1_id=s1,
            student2_id=s2
        )

        # BYE автоматика
        if s1 and s2 == 'BYE':
            new_match.winner_id = s1
            new_match.is_completed = True
            new_match.completed_date = datetime.utcnow()
        elif s2 and s1 == 'BYE':
            new_match.winner_id = s2
            new_match.is_completed = True
            new_match.completed_date = datetime.utcnow()

        new_match.save()


def _fill_next_round_winners(class_name, next_round, bracket_type, prev_matches):
    """Розставляє переможців у вже існуючий наступний раунд"""
    next_matches = list(Match.objects(
        class_name=class_name,
        round_name=next_round,
        bracket_type=bracket_type
    ).order_by('match_number'))

    winners = [m.winner_id for m in prev_matches if m.winner_id]

    for i, next_match in enumerate(next_matches):
        s1 = winners[i * 2] if i * 2 < len(winners) else None
        s2 = winners[i * 2 + 1] if i * 2 + 1 < len(winners) else None
        changed = False

        if s1 and not next_match.student1_id:
            next_match.student1_id = s1
            changed = True
        if s2 and not next_match.student2_id:
            next_match.student2_id = s2
            changed = True

        if changed:
            # BYE автоматика
            if next_match.student1_id and next_match.student2_id == 'BYE':
                next_match.winner_id = next_match.student1_id
                next_match.is_completed = True
                next_match.completed_date = datetime.utcnow()
            elif next_match.student2_id and next_match.student1_id == 'BYE':
                next_match.winner_id = next_match.student2_id
                next_match.is_completed = True
                next_match.completed_date = datetime.utcnow()
            next_match.save()


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
    
    match.winner_id = None
    match.is_completed = False
    match.completed_date = None
    
    # Якщо це не BYE матч
    if match.student2_id != 'BYE' and match.student1_id != 'BYE':
        match.save()
    
    return jsonify({'success': True})


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