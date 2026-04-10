import mongoengine as me
from datetime import datetime


def init_db(app):
    me.connect(host=app.config['MONGODB_URI'])


class Student(me.Document):
    first_name = me.StringField(max_length=50, required=True)
    last_name = me.StringField(max_length=50, required=True)
    patronymic = me.StringField(max_length=50)
    class_name = me.StringField(max_length=10, required=True)
    rating = me.FloatField(default=0.0)
    bracket_status = me.StringField(choices=('main', 'qualification', 'none'), default='none')
    qualified = me.BooleanField(default=False)

    meta = {'collection': 'students', 'ordering': ['class_name', 'last_name']}

    @property
    def full_name(self):
        parts = [self.last_name, self.first_name]
        if self.patronymic and self.patronymic != '-':
            parts.append(self.patronymic)
        return ' '.join(parts)

    def __str__(self):
        return f'{self.full_name} ({self.class_name})'


class Match(me.Document):
    class_name = me.StringField(max_length=10, required=True)
    bracket_type = me.StringField(choices=('qualification', 'main', 'superfinal'), default='main')
    round_name = me.StringField(max_length=20, required=True)
    round_number = me.IntField(required=True)
    match_number = me.IntField(required=True)

    student1_id = me.StringField()
    student2_id = me.StringField()  # 'BYE' або ObjectId як string
    winner_id = me.StringField()

    is_completed = me.BooleanField(default=False)
    completed_date = me.DateTimeField()
    scheduled_date = me.DateTimeField()
    notes = me.StringField()

    meta = {'collection': 'matches', 'ordering': ['class_name', 'round_number', 'match_number']}

    @property
    def student1(self):
        if self.student1_id:
            try:
                return Student.objects.get(id=self.student1_id)
            except:
                return None
        return None

    @property
    def student2(self):
        if self.student2_id == 'BYE':
            return None
        if self.student2_id:
            try:
                return Student.objects.get(id=self.student2_id)
            except:
                return None
        return None

    @property
    def is_bye(self):
        return self.student2_id == 'BYE'

    @property
    def winner(self):
        if self.winner_id:
            try:
                return Student.objects.get(id=self.winner_id)
            except:
                return None
        return None

    @property
    def round_display(self):
        names = {
            'qualification': 'Кваліфікація',
            '1/32': '1/32 фіналу',
            '1/16': '1/16 фіналу',
            '1/8': '1/8 фіналу',
            '1/4': '1/4 фіналу',
            '1/2': '1/2 фіналу (Півфінал)',
            'final': 'Фінал',
        }
        return names.get(self.round_name, self.round_name)

    def __str__(self):
        return f'{self.class_name} {self.round_name} #{self.match_number}'


class SuperfinalMatch(me.Document):
    student1_id = me.StringField()
    student2_id = me.StringField()
    match_number = me.IntField(required=True)
    winner_id = me.StringField()
    is_completed = me.BooleanField(default=False)
    completed_date = me.DateTimeField()
    scheduled_date = me.DateTimeField()
    notes = me.StringField()

    @property
    def student1(self):
        if self.student1_id:
            try:
                return Student.objects.get(id=self.student1_id)
            except:
                return None
        return None

    @property
    def student2(self):
        if self.student2_id:
            try:
                return Student.objects.get(id=self.student2_id)
            except:
                return None
        return None

    @property
    def winner(self):
        if self.winner_id:
            try:
                return Student.objects.get(id=self.winner_id)
            except:
                return None
        return None

    meta = {'collection': 'superfinal_matches', 'ordering': ['match_number']}


class Championship(me.Document):
    name = me.StringField(max_length=200, default="Чемпіонат зі Швидкочислення")
    start_date = me.DateTimeField()
    end_date = me.DateTimeField()
    is_active = me.BooleanField(default=True)
    created_at = me.DateTimeField(default=datetime.utcnow)

    meta = {'collection': 'championship'}

    def __str__(self):
        return self.name