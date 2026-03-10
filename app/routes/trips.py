from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime, timezone
from app import db
from app.models import Trip, User, Settlement, trip_members
from app.utils import get_minimum_transactions, calculate_trip_balances, SUPPORTED_CURRENCIES

trips_bp = Blueprint('trips', __name__, url_prefix='/trips')


@trips_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_trip():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        trip_type = request.form.get('trip_type', 'trip')
        currency = request.form.get('currency', 'AUD')

        if not name:
            flash('Please provide a name.', 'error')
            return render_template('trips/new.html', currencies=SUPPORTED_CURRENCIES)

        trip = Trip(
            name=name,
            description=description,
            trip_type=trip_type,
            currency=currency,
            creator_id=current_user.id
        )
        db.session.add(trip)
        db.session.flush()  # Get the ID

        # Add creator as first member
        trip.members.append(current_user)
        db.session.commit()

        flash(f'{"Event" if trip_type == "event" else "Trip"} created!', 'success')
        return redirect(url_for('trips.view_trip', trip_id=trip.id))

    return render_template('trips/new.html', currencies=SUPPORTED_CURRENCIES)


@trips_bp.route('/<int:trip_id>')
@login_required
def view_trip(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    _check_member(trip)

    balances = calculate_trip_balances(trip)
    settlements = get_minimum_transactions(trip)
    existing_settlements = Settlement.query.filter_by(trip_id=trip.id).all()

    # User's own balance
    my_balance = balances.get(current_user.id, 0)

    return render_template(
        'trips/view.html',
        trip=trip,
        balances=balances,
        settlements=settlements,
        existing_settlements=existing_settlements,
        my_balance=my_balance,
        base_url=current_app.config['BASE_URL']
    )


@trips_bp.route('/<int:trip_id>/members', methods=['GET', 'POST'])
@login_required
def manage_members(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    _check_member(trip)

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add_by_email':
            email = request.form.get('email', '').strip().lower()
            user = User.query.filter_by(email=email).first()
            if not user:
                flash(f'No user found with email {email}. They need to register first.', 'error')
            elif user in trip.members:
                flash(f'{user.name} is already in this trip.', 'info')
            else:
                trip.members.append(user)
                db.session.commit()
                flash(f'{user.name} added to the trip!', 'success')

        elif action == 'add_by_phone':
            phone = request.form.get('phone', '').strip()
            user = User.query.filter_by(phone=phone).first()
            if not user:
                flash(f'No user found with phone {phone}. They need to register first.', 'error')
            elif user in trip.members:
                flash(f'{user.name} is already in this trip.', 'info')
            else:
                trip.members.append(user)
                db.session.commit()
                flash(f'{user.name} added!', 'success')

        elif action == 'remove':
            user_id = int(request.form.get('user_id'))
            if user_id == trip.creator_id:
                flash('Cannot remove the trip creator.', 'error')
            else:
                user = User.query.get(user_id)
                if user and user in trip.members:
                    trip.members.remove(user)
                    db.session.commit()
                    flash(f'{user.name} removed from trip.', 'success')

    return render_template('trips/members.html', trip=trip)


@trips_bp.route('/<int:trip_id>/toggle-status', methods=['POST'])
@login_required
def toggle_status(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    _check_member(trip)

    if trip.status == 'open':
        trip.status = 'closed'
        trip.closed_at = datetime.now(timezone.utc)
        # Generate settlement records
        transactions = get_minimum_transactions(trip)
        # Remove old pending settlements
        Settlement.query.filter_by(trip_id=trip.id, status='pending').delete()
        for t in transactions:
            s = Settlement(
                trip_id=trip.id,
                from_user_id=t['from_user'].id,
                to_user_id=t['to_user'].id,
                amount=t['amount'],
                currency=trip.currency
            )
            db.session.add(s)
        flash('Trip closed. Settlement summary generated.', 'success')
    else:
        trip.status = 'open'
        trip.closed_at = None
        flash('Trip reopened.', 'success')

    db.session.commit()
    return redirect(url_for('trips.view_trip', trip_id=trip.id))


@trips_bp.route('/<int:trip_id>/settle/<int:settlement_id>', methods=['POST'])
@login_required
def mark_settled(trip_id, settlement_id):
    settlement = Settlement.query.get_or_404(settlement_id)
    if settlement.from_user_id != current_user.id and settlement.to_user_id != current_user.id:
        flash('Not authorised.', 'error')
        return redirect(url_for('trips.view_trip', trip_id=trip_id))

    settlement.status = 'paid'
    settlement.paid_at = datetime.now(timezone.utc)
    db.session.commit()
    flash('Marked as paid!', 'success')
    return redirect(url_for('trips.view_trip', trip_id=trip_id))


@trips_bp.route('/join/<token>')
@login_required
def join_trip(token):
    trip = Trip.query.filter_by(invite_token=token).first_or_404()

    if current_user in trip.members:
        flash(f'You\'re already in "{trip.name}"!', 'info')
        return redirect(url_for('trips.view_trip', trip_id=trip.id))

    trip.members.append(current_user)
    db.session.commit()
    flash(f'You joined "{trip.name}"!', 'success')
    return redirect(url_for('trips.view_trip', trip_id=trip.id))


def _check_member(trip):
    """Verify current user is a member or redirect."""
    from flask import abort
    if current_user not in trip.members and trip.creator_id != current_user.id:
        abort(403)
