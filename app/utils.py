"""
Utility functions for debt simplification and currency conversion.
"""
import requests
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


def simplify_debts(balances: dict) -> list:
    """
    Given a dict of {user_id: net_balance} where positive = owed money,
    negative = owes money, compute the minimum set of transactions.
    
    Uses a greedy algorithm: always match the largest creditor with largest debtor.
    Returns list of (from_user_id, to_user_id, amount) tuples.
    """
    # Separate into creditors (positive) and debtors (negative)
    creditors = [(uid, bal) for uid, bal in balances.items() if bal > 0.005]
    debtors = [(uid, -bal) for uid, bal in balances.items() if bal < -0.005]

    creditors.sort(key=lambda x: x[1], reverse=True)
    debtors.sort(key=lambda x: x[1], reverse=True)

    transactions = []
    i, j = 0, 0

    while i < len(creditors) and j < len(debtors):
        cred_id, cred_amount = creditors[i]
        debt_id, debt_amount = debtors[j]

        payment = min(cred_amount, debt_amount)
        if payment > 0.005:
            transactions.append((debt_id, cred_id, round(payment, 2)))

        creditors[i] = (cred_id, cred_amount - payment)
        debtors[j] = (debt_id, debt_amount - payment)

        if creditors[i][1] < 0.005:
            i += 1
        if debtors[j][1] < 0.005:
            j += 1

    return transactions


def calculate_trip_balances(trip):
    """
    Calculate net balance for each user in a trip.
    Returns dict of {user_id: net_balance_aud}
    Positive = others owe this user money
    Negative = this user owes others money
    """
    from app.models import Expense, ExpenseSplit

    balances = defaultdict(float)

    for expense in trip.expenses:
        # Payer gets credited the full amount
        balances[expense.payer_id] += expense.base_amount

        # Each split participant owes their share
        for split in expense.splits:
            balances[split.user_id] -= split.owed_amount

    return dict(balances)


def get_minimum_transactions(trip):
    """
    Returns the minimum set of transactions to settle a trip.
    Each item: {'from_user': User, 'to_user': User, 'amount': float}
    """
    from app.models import User

    balances = calculate_trip_balances(trip)
    transactions = simplify_debts(balances)

    result = []
    for from_id, to_id, amount in transactions:
        from_user = User.query.get(from_id)
        to_user = User.query.get(to_id)
        if from_user and to_user:
            result.append({
                'from_user': from_user,
                'to_user': to_user,
                'amount': amount,
                'currency': trip.currency
            })
    return result


# Simple in-memory cache for exchange rates (resets on restart, good enough for free tier)
_rate_cache = {}

SUPPORTED_CURRENCIES = [
    'AUD', 'USD', 'GBP', 'EUR', 'NZD', 'JPY', 'CAD', 'SGD', 'HKD', 'THB',
    'IDR', 'MYR', 'PHP', 'VND', 'INR', 'CHF', 'SEK', 'NOK', 'DKK', 'ZAR'
]


def get_exchange_rate(from_currency: str, to_currency: str = 'AUD') -> float:
    """
    Get exchange rate using the free Open Exchange Rates API (no key needed for basic).
    Falls back to 1.0 if unavailable.
    """
    if from_currency == to_currency:
        return 1.0

    cache_key = f"{from_currency}_{to_currency}"
    if cache_key in _rate_cache:
        return _rate_cache[cache_key]

    try:
        # Use the free frankfurter.app API - no API key needed
        url = f"https://api.frankfurter.app/latest?from={from_currency}&to={to_currency}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            rate = data['rates'].get(to_currency, 1.0)
            _rate_cache[cache_key] = rate
            return rate
    except Exception as e:
        logger.warning(f"Currency conversion failed: {e}")

    return 1.0


def convert_to_aud(amount: float, currency: str) -> tuple:
    """Returns (aud_amount, exchange_rate)"""
    if currency == 'AUD':
        return amount, 1.0
    rate = get_exchange_rate(currency, 'AUD')
    return round(amount * rate, 2), rate


def calculate_splits(expense, participants: list, split_type: str, split_data: dict = None):
    """
    Calculate owed amounts for each participant.
    
    participants: list of user_ids
    split_type: 'equal', 'percent', 'amount'
    split_data: dict of {user_id: value} for percent/amount splits
    
    Returns list of (user_id, owed_amount) tuples.
    """
    total = expense.base_amount
    result = []

    if split_type == 'equal':
        per_person = round(total / len(participants), 2)
        # Handle rounding - assign remainder to first person
        remainder = round(total - per_person * len(participants), 2)
        for i, uid in enumerate(participants):
            amt = per_person + (remainder if i == 0 else 0)
            result.append((uid, round(amt, 2)))

    elif split_type == 'percent':
        for uid in participants:
            pct = split_data.get(str(uid), 0) / 100.0
            result.append((uid, round(total * pct, 2)))

    elif split_type == 'amount':
        for uid in participants:
            amt = split_data.get(str(uid), 0)
            result.append((uid, round(float(amt), 2)))

    return result
