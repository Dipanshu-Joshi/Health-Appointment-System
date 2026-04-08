import sys
import os
from pathlib import Path

from flask import Flask, redirect, url_for
from flask_login import LoginManager, current_user, login_required
from sqlalchemy import text
from werkzeug.security import generate_password_hash
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from utils.timezone_utils import (
    format_appointment_ist,
    format_appointment_ist_date,
    format_appointment_ist_time,
)

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# When started via `python app.py`, expose this module as `app` too.
# This prevents duplicate module loading (`__main__` vs `app`) and keeps
# one shared SQLAlchemy instance across imports.
sys.modules.setdefault("app", sys.modules[__name__])

# Shared extensions are initialized once and attached to the app in create_app.
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"


def create_app() -> Flask:
    """Application factory used to create and configure the Flask app."""
    app = Flask(__name__)

    # Load configuration from environment with safe development fallbacks.
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "fallback_dev_key")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "sqlite:///appointment.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Initialize Flask extensions.
    db.init_app(app)
    login_manager.init_app(app)

    # Import here to avoid circular imports.
    from models import User
    from routes.admin import admin_bp
    from routes.auth import auth_bp
    from routes.doctor import doctor_bp
    from routes.patient import patient_bp
    from routes.profile import profile_bp
    from routes.video import video_bp

    @login_manager.user_loader
    def load_user(user_id: str):
        return User.query.get(int(user_id))

    @app.context_processor
    def inject_time_helpers():
        return {
            "format_appointment_ist": format_appointment_ist,
            "format_appointment_ist_date": format_appointment_ist_date,
            "format_appointment_ist_time": format_appointment_ist_time,
        }

    app.jinja_env.globals.update(
        format_appointment_ist=format_appointment_ist,
        format_appointment_ist_date=format_appointment_ist_date,
        format_appointment_ist_time=format_appointment_ist_time,
    )

    # Register blueprints for modular route organization.
    app.register_blueprint(auth_bp)
    app.register_blueprint(patient_bp)
    app.register_blueprint(doctor_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(video_bp)

    @app.route("/")
    def home():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return redirect(url_for("auth.login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        """Role-based dashboard redirect after login."""
        if current_user.role == "patient":
            return redirect(url_for("patient.dashboard"))
        if current_user.role == "doctor":
            return redirect(url_for("doctor.dashboard"))
        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("home"))

    # Create database tables on first run.
    with app.app_context():
        db.create_all()

        # Backfill schema for older SQLite databases created before room_id existed.
        try:
            db.session.execute(text("ALTER TABLE appointments ADD COLUMN room_id VARCHAR(120)"))
            db.session.commit()
        except Exception:
            db.session.rollback()

        try:
            db.session.execute(text("ALTER TABLE appointments ADD COLUMN remark TEXT"))
            db.session.commit()
        except Exception:
            db.session.rollback()

        try:
            db.session.execute(text("ALTER TABLE users ADD COLUMN doctor_document VARCHAR(255)"))
            db.session.commit()
        except Exception:
            db.session.rollback()

        try:
            db.session.execute(text("ALTER TABLE users ADD COLUMN profile_image VARCHAR(255)"))
            db.session.commit()
        except Exception:
            db.session.rollback()

        # Keep one local admin account aligned with configured credentials.
        admin_email = os.getenv("ADMIN_EMAIL", "admin")
        admin_password = os.getenv("ADMIN_PASSWORD", "admin")

        admin_user = User.query.filter_by(role="admin").first()
        if not admin_user:
            admin_user = User(
                full_name="System Admin",
                email=admin_email,
                password_hash=generate_password_hash(admin_password),
                role="admin",
                doctor_status="approved",
            )
            db.session.add(admin_user)
        else:
            admin_user.email = admin_email
            admin_user.password_hash = generate_password_hash(admin_password)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    return app


# WSGI entrypoint for production servers, e.g. `gunicorn app:app`.
app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=debug)
