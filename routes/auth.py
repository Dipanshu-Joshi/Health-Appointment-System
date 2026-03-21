from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from app import db
from models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _redirect_by_role(role: str):
    """Send logged-in users to their role-specific dashboard."""
    if role == "patient":
        return redirect(url_for("patient.dashboard"))
    if role == "doctor":
        return redirect(url_for("doctor.dashboard"))
    if role == "admin":
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("home"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return _redirect_by_role(current_user.role)

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid email or password.", "danger")
            return render_template("auth/login.html")

        # Doctors must be approved by admin before login is allowed.
        if user.role == "doctor" and user.doctor_status != "approved":
            flash("Your doctor account is pending admin approval.", "warning")
            return render_template("auth/login.html")

        login_user(user)
        flash("Login successful.", "success")
        return _redirect_by_role(user.role)

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return _redirect_by_role(current_user.role)

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        role = request.form.get("role", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not full_name or not email or not role or not password:
            flash("All fields are required.", "danger")
            return render_template("auth/register.html")

        if role not in ["patient", "doctor"]:
            flash("Please choose a valid role.", "danger")
            return render_template("auth/register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("auth/register.html")

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email is already registered.", "warning")
            return render_template("auth/register.html")

        doctor_status = "pending" if role == "doctor" else "approved"
        new_user = User(
            full_name=full_name,
            email=email,
            password_hash=generate_password_hash(password),
            role=role,
            doctor_status=doctor_status,
        )
        db.session.add(new_user)
        db.session.commit()

        if role == "doctor":
            flash(
                "Registration submitted. Please wait for admin approval before login.",
                "info",
            )
            return redirect(url_for("auth.login"))

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/logout")
def logout():
    if current_user.is_authenticated:
        logout_user()
        flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
