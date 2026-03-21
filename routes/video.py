from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from models import Appointment

video_bp = Blueprint("video", __name__)


@video_bp.route("/video-call/<string:room_id>")
@login_required
def video_call(room_id: str):
    appointment = Appointment.query.filter_by(room_id=room_id, status="approved").first_or_404()

    # Only the assigned patient or doctor can enter this room.
    user_allowed = (
        (current_user.role == "patient" and appointment.patient_id == current_user.id)
        or (current_user.role == "doctor" and appointment.doctor_id == current_user.id)
    )
    if not user_allowed:
        flash("You are not authorized to access this video consultation.", "danger")
        return redirect(url_for("dashboard"))

    scheduled_at = datetime.combine(appointment.appointment_date, appointment.appointment_time)
    if datetime.now() < scheduled_at:
        flash("Call will be available at scheduled time.", "warning")
        return redirect(url_for("dashboard"))

    back_url = url_for("patient.dashboard") if current_user.role == "patient" else url_for("doctor.dashboard")
    return render_template("video_call.html", room_id=room_id, back_url=back_url)
