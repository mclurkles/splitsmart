from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Trip, Expense, ExpenseSplit, User
from app.utils import calculate_splits, convert_to_aud, SUPPORTED_CURRENCIES

expenses_bp = Blueprint('expenses', __name__, url_prefix='/expenses')


@expenses_bp.route('/trip/<int:trip_id>/new', methods=['GET', 'POST'])
@login_required
def new_expense(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    _check_member(trip)

    if trip.status == 'closed':
        flash('This trip is closed. Reopen it to add expenses.', 'error')
        return redirect(url_for('trips.view_trip', trip_id=trip.id))

    if request.method == 'POST':
        description = request.form.get('description', '').strip()
        amount = request.form.get('amount', 0)
        currency = request.form.get('currency', trip.currency)
        payer_id = int(request.form.get('payer_id', current_user.id))
        split_type = request.form.get('split_type', 'equal')
        participant_ids = request.form.getlist('participants')

        if not description or not amount:
            flash('Please fill in description and amount.', 'error')
            return render_template('expenses/new.html', trip=trip, currencies=SUPPORTED_CURRENCIES)

        if not participant_ids:
            flash('Please select at least one person to split with.', 'error')
            return render_template('expenses/new.html', trip=trip, currencies=SUPPORTED_CURRENCIES)

        try:
            amount = float(amount)
        except ValueError:
            flash('Invalid amount.', 'error')
            return render_template('expenses/new.html', trip=trip, currencies=SUPPORTED_CURRENCIES)

        participant_ids = [int(pid) for pid in participant_ids]

        # Convert currency
        amount_aud, exchange_rate = convert_to_aud(amount, currency)

        expense = Expense(
            trip_id=trip_id,
            payer_id=payer_id,
            description=description,
            amount=amount,
            currency=currency,
            amount_aud=amount_aud,
            exchange_rate=exchange_rate,
            split_type=split_type,
            created_by_id=current_user.id
        )
        db.session.add(expense)
        db.session.flush()

        # Build split_data for percent/amount splits
        split_data = {}
        if split_type == 'percent':
            for pid in participant_ids:
                val = request.form.get(f'percent_{pid}', 0)
                split_data[str(pid)] = float(val)
        elif split_type == 'amount':
            for pid in participant_ids:
                val = request.form.get(f'amount_{pid}', 0)
                split_data[str(pid)] = float(val)

        # Calculate and save splits
        splits = calculate_splits(expense, participant_ids, split_type, split_data)
        for user_id, owed_amount in splits:
            s = ExpenseSplit(
                expense_id=expense.id,
                user_id=user_id,
                split_type=split_type,
                owed_amount=owed_amount
            )
            if split_type == 'percent':
                s.percent = split_data.get(str(user_id), 0)
            elif split_type == 'amount':
                s.amount = split_data.get(str(user_id), 0)
            db.session.add(s)

        db.session.commit()
        flash(f'Expense "{description}" added!', 'success')

        # If this is an event type, go straight back to trip
        return redirect(url_for('trips.view_trip', trip_id=trip.id))

    return render_template('expenses/new.html', trip=trip, currencies=SUPPORTED_CURRENCIES)


@expenses_bp.route('/<int:expense_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    trip = expense.trip
    _check_member(trip)

    if trip.status == 'closed':
        flash('Trip is closed.', 'error')
        return redirect(url_for('trips.view_trip', trip_id=trip.id))

    if request.method == 'POST':
        expense.description = request.form.get('description', expense.description).strip()
        amount = request.form.get('amount', expense.amount)
        currency = request.form.get('currency', expense.currency)
        payer_id = int(request.form.get('payer_id', expense.payer_id))
        split_type = request.form.get('split_type', expense.split_type)
        participant_ids = [int(pid) for pid in request.form.getlist('participants')]

        try:
            expense.amount = float(amount)
        except ValueError:
            flash('Invalid amount.', 'error')
            return render_template('expenses/edit.html', expense=expense, trip=trip, currencies=SUPPORTED_CURRENCIES)

        expense.currency = currency
        expense.payer_id = payer_id
        expense.split_type = split_type

        amount_aud, exchange_rate = convert_to_aud(expense.amount, currency)
        expense.amount_aud = amount_aud
        expense.exchange_rate = exchange_rate

        # Remove old splits
        ExpenseSplit.query.filter_by(expense_id=expense.id).delete()

        split_data = {}
        if split_type == 'percent':
            for pid in participant_ids:
                split_data[str(pid)] = float(request.form.get(f'percent_{pid}', 0))
        elif split_type == 'amount':
            for pid in participant_ids:
                split_data[str(pid)] = float(request.form.get(f'amount_{pid}', 0))

        splits = calculate_splits(expense, participant_ids, split_type, split_data)
        for user_id, owed_amount in splits:
            s = ExpenseSplit(
                expense_id=expense.id,
                user_id=user_id,
                split_type=split_type,
                owed_amount=owed_amount
            )
            db.session.add(s)

        db.session.commit()
        flash('Expense updated.', 'success')
        return redirect(url_for('trips.view_trip', trip_id=trip.id))

    return render_template('expenses/edit.html', expense=expense, trip=trip, currencies=SUPPORTED_CURRENCIES)


@expenses_bp.route('/<int:expense_id>/delete', methods=['POST'])
@login_required
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    trip = expense.trip
    _check_member(trip)

    if trip.status == 'closed':
        flash('Trip is closed.', 'error')
        return redirect(url_for('trips.view_trip', trip_id=trip.id))

    db.session.delete(expense)
    db.session.commit()
    flash('Expense deleted.', 'success')
    return redirect(url_for('trips.view_trip', trip_id=trip.id))


def _check_member(trip):
    from flask import abort
    if current_user not in trip.members and trip.creator_id != current_user.id:
        abort(403)
