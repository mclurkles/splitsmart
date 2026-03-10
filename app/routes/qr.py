import io
import qrcode
import qrcode.image.svg
from flask import Blueprint, send_file, redirect, url_for, current_app, request
from flask_login import login_required, current_user
from app.models import Trip

qr_bp = Blueprint('qr', __name__, url_prefix='/qr')


@qr_bp.route('/trip/<int:trip_id>')
@login_required
def trip_qr(trip_id):
    """Generate a QR code image for joining a trip."""
    trip = Trip.query.get_or_404(trip_id)

    base_url = current_app.config['BASE_URL'].rstrip('/')
    join_url = f"{base_url}/trips/join/{trip.invite_token}"

    # Create QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(join_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#1a1a2e", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)

    return send_file(buf, mimetype='image/png', as_attachment=False)


@qr_bp.route('/trip/<int:trip_id>/page')
@login_required
def trip_qr_page(trip_id):
    """Page showing the QR code for sharing."""
    from flask import render_template
    trip = Trip.query.get_or_404(trip_id)

    # Verify user is a member
    if current_user not in trip.members and trip.creator_id != current_user.id:
        from flask import abort
        abort(403)

    base_url = current_app.config['BASE_URL'].rstrip('/')
    join_url = f"{base_url}/trips/join/{trip.invite_token}"

    return render_template('qr_page.html', trip=trip, join_url=join_url)
