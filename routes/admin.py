from flask import Blueprint, current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app import db
from models import Appointment, User

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/dashboard")
@login_required
def dashboard():
    if current_user.role != "admin":
        flash("Access denied: Admin account required.", "danger")
        return redirect(url_for("home"))

    pending_count = User.query.filter_by(role="doctor", doctor_status="pending").count()
    total_doctors = User.query.filter_by(role="doctor").count()
    appointment_count = Appointment.query.count()
    pending_appointments = Appointment.query.filter_by(status="pending").count()
    return render_template(
        "admin/dashboard.html",
        pending_count=pending_count,
        total_doctors=total_doctors,
        appointment_count=appointment_count,
        pending_appointments=pending_appointments,
    )


@admin_bp.route("/doctors")
@login_required
def doctor_approvals():
    if current_user.role != "admin":
        flash("Access denied: Admin account required.", "danger")
        return redirect(url_for("home"))

    doctors = User.query.filter_by(role="doctor").order_by(User.created_at.desc()).all()
    return render_template("admin/doctors.html", doctors=doctors)


@admin_bp.route("/doctors/<int:doctor_id>/approve", methods=["POST"])
@login_required
def approve_doctor(doctor_id: int):
    if current_user.role != "admin":
        flash("Access denied: Admin account required.", "danger")
        return redirect(url_for("home"))

    doctor = User.query.filter_by(id=doctor_id, role="doctor").first_or_404()
    doctor.doctor_status = "approved"
    db.session.commit()
    flash(f"Dr. {doctor.full_name} has been approved.", "success")
    return redirect(url_for("admin.doctor_approvals"))


@admin_bp.route("/doctors/<int:doctor_id>/reject", methods=["POST"])
@login_required
def reject_doctor(doctor_id: int):
    if current_user.role != "admin":
        flash("Access denied: Admin account required.", "danger")
        return redirect(url_for("home"))

    doctor = User.query.filter_by(id=doctor_id, role="doctor").first_or_404()
    doctor.doctor_status = "rejected"
    db.session.commit()
    flash(f"Dr. {doctor.full_name} has been rejected.", "warning")
    return redirect(url_for("admin.doctor_approvals"))


@admin_bp.route("/appointments")
@login_required
def all_appointments():
    if current_user.role != "admin":
        flash("Access denied: Admin account required.", "danger")
        return redirect(url_for("home"))

    appointments = (
        Appointment.query.order_by(
            Appointment.appointment_date.desc(),
            Appointment.appointment_time.desc(),
        ).all()
    )
    current_app.logger.debug(
        "Admin appointments status snapshot: %s",
        [
            {
                "id": appointment.id,
                "status": appointment.status,
                "patient": appointment.patient.full_name,
                "doctor": appointment.doctor.full_name,
            }
            for appointment in appointments
        ],
    )
    print(
        "Admin appointment statuses:",
        [(appointment.id, appointment.status) for appointment in appointments],
    )
    return render_template("admin/appointments.html", appointments=appointments)
