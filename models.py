from datetime import datetime

from flask_login import UserMixin

from app import db


class User(UserMixin, db.Model):
    """Single user model that stores patients, doctors, and admins."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    profile_image = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(20), nullable=False)  # patient | doctor | admin
    doctor_status = db.Column(
        db.String(20),
        nullable=False,
        default="approved",
    )  # approved | pending | rejected
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    patient_appointments = db.relationship(
        "Appointment",
        foreign_keys="Appointment.patient_id",
        backref="patient",
        lazy=True,
    )
    doctor_appointments = db.relationship(
        "Appointment",
        foreign_keys="Appointment.doctor_id",
        backref="doctor",
        lazy=True,
    )


class Appointment(db.Model):
    """Appointment model that tracks patient-doctor booking lifecycle."""

    __tablename__ = "appointments"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    appointment_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.Time, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    room_id = db.Column(db.String(120), nullable=True)
    status = db.Column(
        db.String(30),
        nullable=False,
        default="pending",
    )  # pending | approved | completed | cancelled | reschedule_requested
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
