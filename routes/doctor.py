from datetime import datetime
import secrets

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from models import Appointment

doctor_bp = Blueprint("doctor", __name__, url_prefix="/doctor")


def _format_remaining_seconds(total_seconds: int) -> str:
    """Return human-readable remaining time for call activation."""
    safe_seconds = max(total_seconds, 0)
    hours, remainder = divmod(safe_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


@doctor_bp.route("/dashboard")
@login_required
def dashboard():
    if current_user.role != "doctor":
        flash("Access denied: Doctor account required.", "danger")
        return redirect(url_for("home"))

    appointments = (
        Appointment.query.filter_by(doctor_id=current_user.id)
        .order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc())
        .all()
    )

    now = datetime.now()
    for appointment in appointments:
        appointment.scheduled_at = datetime.combine(appointment.appointment_date, appointment.appointment_time)
        appointment.call_available = (
            appointment.status == "approved"
            and bool(appointment.room_id)
            and now >= appointment.scheduled_at
        )
        appointment.remaining_to_call = ""
        if appointment.status == "approved" and appointment.scheduled_at > now:
            seconds_left = int((appointment.scheduled_at - now).total_seconds())
            appointment.remaining_to_call = _format_remaining_seconds(seconds_left)

    total_appointments = len(appointments)
    pending_count = sum(1 for appointment in appointments if appointment.status == "pending")
    approved_count = sum(1 for appointment in appointments if appointment.status == "approved")
    completed_count = sum(1 for appointment in appointments if appointment.status == "completed")

    return render_template(
        "doctor/dashboard.html",
        appointments=appointments,
        total_appointments=total_appointments,
        pending_count=pending_count,
        approved_count=approved_count,
        completed_count=completed_count,
    )


@doctor_bp.route("/appointments/<int:appointment_id>/status", methods=["POST"])
@login_required
def update_appointment_status(appointment_id: int):
    if current_user.role != "doctor":
        flash("Access denied: Doctor account required.", "danger")
        return redirect(url_for("home"))

    appointment = Appointment.query.filter_by(id=appointment_id, doctor_id=current_user.id).first_or_404()
    new_status = request.form.get("status", "").strip()
    allowed_statuses = ["approved", "cancelled", "reschedule_requested"]

    if new_status not in allowed_statuses:
        flash("Invalid appointment status.", "danger")
        return redirect(url_for("doctor.dashboard"))

    appointment.status = new_status
    if new_status == "approved" and not appointment.room_id:
        appointment.room_id = f"appointment_{appointment.id}_{secrets.token_hex(4)}"
    db.session.commit()
    flash("Appointment status updated.", "success")
    return redirect(url_for("doctor.dashboard"))


@doctor_bp.route("/complete-appointment/<int:appointment_id>", methods=["POST"])
@login_required
def complete_appointment(appointment_id: int):
    if current_user.role != "doctor":
        flash("Access denied: Doctor account required.", "danger")
        return redirect(url_for("home"))

    appointment = Appointment.query.filter_by(id=appointment_id, doctor_id=current_user.id).first_or_404()
    if appointment.status != "approved":
        flash("Only approved appointments can be marked completed.", "warning")
        return redirect(url_for("doctor.dashboard"))

    scheduled_at = datetime.combine(appointment.appointment_date, appointment.appointment_time)
    if datetime.now() < scheduled_at:
        flash("Appointment can be marked completed after scheduled time.", "warning")
        return redirect(url_for("doctor.dashboard"))

    appointment.status = "completed"
    db.session.commit()
    flash("Appointment marked as completed.", "success")
    return redirect(url_for("doctor.dashboard"))


@doctor_bp.route("/patient-details/<int:appointment_id>")
@login_required
def patient_details(appointment_id: int):
    if current_user.role != "doctor":
        flash("Access denied: Doctor account required.", "danger")
        return redirect(url_for("home"))

    appointment = Appointment.query.filter_by(id=appointment_id, doctor_id=current_user.id).first_or_404()
    return render_template("doctor/patient_details.html", appointment=appointment)
