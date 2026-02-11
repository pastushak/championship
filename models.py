from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Student(db.Model):
    """Модель учня"""
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    patronymic = db.Column(db.String(50))
    class_name = db.Column(db.String(10), nullable=False)
    seed = db.Column(db.Integer)
    rating = db.Column(db.Integer, default=0)
    has_bye = db.Column(db.Boolean, default=False)
    
    home_matches = db.relationship('Match', foreign_keys='Match.student1_id', backref='student1', lazy=True)
    away_matches = db.relationship('Match', foreign_keys='Match.student2_id', backref='student2', lazy=True)
    
    @property
    def full_name(self):
        return f"{self.last_name} {self.first_name} {self.patronymic or ''}".strip()
    
    def __repr__(self):
        return f'<Student {self.full_name} ({self.class_name})>'


class Match(db.Model):
    """Модель поєдинку"""
    id = db.Column(db.Integer, primary_key=True)
    student1_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    student2_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=True)
    class_name = db.Column(db.String(10), nullable=False)
    round_number = db.Column(db.Integer, nullable=False)
    match_number = db.Column(db.Integer, nullable=False)
    
    winner_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=True)
    winner = db.relationship('Student', foreign_keys=[winner_id], backref='wins')
    
    scheduled_date = db.Column(db.DateTime, nullable=True)
    completed_date = db.Column(db.DateTime, nullable=True)
    is_completed = db.Column(db.Boolean, default=False)
    
    score1 = db.Column(db.Integer)
    score2 = db.Column(db.Integer)
    notes = db.Column(db.Text)
    
    def __repr__(self):
        return f'<Match {self.class_name} Round {self.round_number} Match {self.match_number}>'
    
    @property
    def round_name(self):
        """Назва раунду українською"""
        if self.round_number == 0:
            return "Кваліфікація"
        round_names = {
            1: "1/16 фіналу",
            2: "1/8 фіналу",
            3: "1/4 фіналу",
            4: "1/2 фіналу (Півфінал)",
            5: "Фінал",
            6: "За 3-є місце"
        }
        return round_names.get(self.round_number, f"Раунд {self.round_number}")


class Championship(db.Model):
    """Загальні налаштування чемпіонату"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), default="Чемпіонат зі Швидкочислення")
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Championship {self.name}>'