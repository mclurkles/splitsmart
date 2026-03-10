from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
import secrets


# Association table: which users are members of a trip
trip_members = db.Table('trip_members',
    db.Column('trip_id', db.Integer, db.ForeignKey('trip.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('joined_at', db.DateTime, default=lambda: datetime.now(timezone.utc))
)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    preferred_currency = db.Column(db.String(3), default='AUD')

    # Trips this user created
    created_trips = db.relationship('Trip', backref='creator', lazy=True, foreign_keys='Trip.creator_id')
    # Trips this user is a member of
    trips = db.relationship('Trip', secondary=trip_members, backref='members', lazy='dynamic')
    # Expenses this user paid
    paid_expenses = db.relationship('Expense', backref='payer', lazy=True, foreign_keys='Expense.payer_id')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.name}>'


class Trip(db.Model):
    """A Trip contains multiple expenses. An Event is a single-expense trip."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    trip_type = db.Column(db.String(10), default='trip')  # 'trip' or 'event'
    currency = db.Column(db.String(3), default='AUD')
    status = db.Column(db.String(10), default='open')  # 'open' or 'closed'
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    closed_at = db.Column(db.DateTime, nullable=True)
    invite_token = db.Column(db.String(32), unique=True, default=lambda: secrets.token_urlsafe(16))

    expenses = db.relationship('Expense', backref='trip', lazy=True, cascade='all, delete-orphan')

    def get_total(self):
        return sum(e.amount for e in self.expenses if e.currency == self.currency)

    def __repr__(self):
        return f'<Trip {self.name}>'


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey('trip.id'), nullable=False)
    payer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='AUD')
    amount_aud = db.Column(db.Float, nullable=True)  # Converted to AUD for settlement
    exchange_rate = db.Column(db.Float, default=1.0)
    split_type = db.Column(db.String(10), default='equal')  # 'equal', 'percent', 'amount'
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    splits = db.relationship('ExpenseSplit', backref='expense', lazy=True, cascade='all, delete-orphan')

    @property
    def base_amount(self):
        """Amount in AUD for settlement calculations."""
        return self.amount_aud if self.amount_aud else self.amount

    def __repr__(self):
        return f'<Expense {self.description} ${self.amount}>'


class ExpenseSplit(db.Model):
    """How an expense is split between participants."""
    id = db.Column(db.Integer, primary_key=True)
    expense_id = db.Column(db.Integer, db.ForeignKey('expense.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    split_type = db.Column(db.String(10), default='equal')  # 'equal', 'percent', 'amount'
    percent = db.Column(db.Float, nullable=True)   # e.g. 33.33
    amount = db.Column(db.Float, nullable=True)    # fixed AUD amount
    owed_amount = db.Column(db.Float, nullable=True)  # calculated at save time

    user = db.relationship('User', backref='splits')

    def __repr__(self):
        return f'<Split user={self.user_id} expense={self.expense_id} owes={self.owed_amount}>'


class Settlement(db.Model):
    """Records of actual payments between users to settle debts."""
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey('trip.id'), nullable=False)
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    to_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='AUD')
    status = db.Column(db.String(10), default='pending')  # 'pending', 'paid'
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    paid_at = db.Column(db.DateTime, nullable=True)

    from_user = db.relationship('User', foreign_keys=[from_user_id], backref='settlements_to_pay')
    to_user = db.relationship('User', foreign_keys=[to_user_id], backref='settlements_to_receive')
    trip = db.relationship('Trip', backref='settlements')
