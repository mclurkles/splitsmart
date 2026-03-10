from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from app.models import Trip, trip_members

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    from flask_login import current_user
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    # Trips where user is a member or creator
    my_trips = current_user.trips.order_by(Trip.created_at.desc()).all()

    # Also include trips user created but may not be a member of (edge case)
    created_ids = {t.id for t in my_trips}
    created = Trip.query.filter_by(creator_id=current_user.id).all()
    for t in created:
        if t.id not in created_ids:
            my_trips.append(t)

    open_trips = [t for t in my_trips if t.status == 'open']
    closed_trips = [t for t in my_trips if t.status == 'closed']

    return render_template('dashboard.html', open_trips=open_trips, closed_trips=closed_trips)
