from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import UniqueConstraint

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    groups = db.relationship('Group', backref='owner', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


class Group(db.Model):
    __tablename__ = 'group'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    students = db.relationship('Student', backref='group', lazy=True, cascade='all, delete-orphan')
    subjects = db.relationship('Subject', backref='group', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Group {self.name}>'


class Student(db.Model):
    __tablename__ = 'student'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)  # Первые 2 слова из Excel
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    scores = db.relationship('Score', backref='student', lazy=True, cascade='all, delete-orphan')
    logs = db.relationship('AssignmentLog', backref='student', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Student {self.name}>'


class Subject(db.Model):
    __tablename__ = 'subject'

    id = db.Column(db.Integer, primary_key=True)
    display_name = db.Column(db.String(120), nullable=False)  # Например: "Гражданское право"
    slug = db.Column(db.String(120), nullable=False)          # Например: "гражданское_право"
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    scores = db.relationship('Score', backref='subject', lazy=True, cascade='all, delete-orphan')
    logs = db.relationship('AssignmentLog', backref='subject', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Subject {self.display_name}>'


class Score(db.Model):
    __tablename__ = 'score'
    __table_args__ = (UniqueConstraint('student_id', 'subject_id', name='uq_student_subject'),)

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    value = db.Column(db.Integer, default=0, nullable=False)

    def __repr__(self):
        return f'<Score student={self.student_id} subject={self.subject_id} value={self.value}>'


class AssignmentLog(db.Model):
    __tablename__ = 'assignment_log'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    # 'ASSIGN' | 'REPLACE_OUT' | 'REPLACE_IN'
    action = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<AssignmentLog {self.action} student={self.student_id}>'
