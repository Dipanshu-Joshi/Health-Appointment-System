from datetime import datetime

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app import db
from chatbot.rules import DEFAULT_MODEL, DISCLAIMER, get_bot_response, normalize_model_choice
from models import Appointment, User

patient_bp = Blueprint("patient", __name__, url_prefix="/patient")


def _format_remaining_seconds(total_seconds: int) -> str:
    """Return human-readable remaining time for call activation."""
    safe_seconds = max(total_seconds, 0)
    hours, remainder = divmod(safe_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


@patient_bp.route("/dashboard")
@login_required
def dashboard():
    if current_user.role != "patient":
        flash("Access denied: Patient account required.", "danger")
        return redirect(url_for("home"))

    appointments = (
        Appointment.query.filter_by(patient_id=current_user.id)
        .order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc())
        .all()
    )

    now = datetime.now()
    for appointment in appointments:
        appointment.scheduled_at = datetime.combine(appointment.appointment_date, appointment.appointment_time)
        # Keep approved/pending items in Upcoming so patients can still join when time arrives.
        appointment.is_past = appointment.status in ["completed", "cancelled"]
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
        "patient/dashboard.html",
        appointments=appointments,
        total_appointments=total_appointments,
        pending_count=pending_count,
        approved_count=approved_count,
        completed_count=completed_count,
    )


@patient_bp.route("/doctors")
@login_required
def approved_doctors():
    if current_user.role != "patient":
        flash("Access denied: Patient account required.", "danger")
        return redirect(url_for("home"))

    doctors = (
        User.query.filter_by(role="doctor", doctor_status="approved")
        .order_by(User.full_name.asc())
        .all()
    )
    return render_template("patient/doctors.html", doctors=doctors)


@patient_bp.route("/appointments/book/<int:doctor_id>", methods=["GET", "POST"])
@login_required
def book_appointment(doctor_id: int):
    if current_user.role != "patient":
        flash("Access denied: Patient account required.", "danger")
        return redirect(url_for("home"))

    doctor = User.query.filter_by(id=doctor_id, role="doctor", doctor_status="approved").first_or_404()

    if request.method == "POST":
        appointment_date_raw = request.form.get("appointment_date", "")
        appointment_time_raw = request.form.get("appointment_time", "")
        reason = request.form.get("reason", "").strip()

        if not appointment_date_raw or not appointment_time_raw or not reason:
            flash("All fields are required.", "danger")
            return render_template("patient/book_appointment.html", doctor=doctor)

        try:
            appointment_date = datetime.strptime(appointment_date_raw, "%Y-%m-%d").date()
            appointment_time = datetime.strptime(appointment_time_raw, "%H:%M").time()
        except ValueError:
            flash("Please enter a valid date and time.", "danger")
            return render_template("patient/book_appointment.html", doctor=doctor)

        appointment = Appointment(
            patient_id=current_user.id,
            doctor_id=doctor.id,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            reason=reason,
            status="pending",
        )
        db.session.add(appointment)
        db.session.commit()
        flash("Appointment booked successfully.", "success")
        return redirect(url_for("patient.dashboard"))

    return render_template("patient/book_appointment.html", doctor=doctor)


@patient_bp.route("/chatbot", methods=["GET", "POST"])
@login_required
def chatbot():
    if current_user.role != "patient":
        flash("Access denied: Patient account required.", "danger")
        return redirect(url_for("home"))

    # History format follows Chat Completions style for easy API reuse.
    # Example: {"role": "user", "content": "..."}
    conversation = session.get("chat_history", [])
    selected_model = normalize_model_choice(session.get("chat_model", DEFAULT_MODEL))

    if request.method == "POST":
        payload = request.get_json(silent=True) or request.form
        action = (payload.get("action") or "send").strip().lower()

        if action == "clear":
            session["chat_history"] = []
            session.modified = True
            return jsonify({"status": "ok", "cleared": True})

        user_message = (payload.get("message") or "").strip()
        selected_model = normalize_model_choice(payload.get("model") or selected_model)
        session["chat_model"] = selected_model
        current_app.logger.info("Chatbot selected model: %s", selected_model)

        image_bytes = None
        image_mime_type = None
        uploaded_image = request.files.get("image")
        if uploaded_image and uploaded_image.filename:
            if selected_model != "gemini":
                return jsonify({"error": "Image upload is available only with Gemini model."}), 400

            image_mime_type = (uploaded_image.mimetype or "").strip().lower()
            if not image_mime_type.startswith("image/"):
                return jsonify({"error": "Only image uploads are allowed."}), 400

            image_bytes = uploaded_image.read()
            if not image_bytes:
                return jsonify({"error": "Uploaded image is empty."}), 400
            if len(image_bytes) > 5 * 1024 * 1024:
                return jsonify({"error": "Image is too large. Max size is 5MB."}), 400

        if not user_message and not image_bytes:
            return jsonify({"error": "Message is required."}), 400

        if not user_message and image_bytes:
            user_message = "Please analyze this medical image and share general guidance."

        conversation.append({"role": "user", "content": user_message})

        # Send previous context only; the function adds the current user query.
        prior_context = conversation[:-1]
        bot_reply, model_used = get_bot_response(
            user_message,
            prior_context,
            model_choice=selected_model,
            image_bytes=image_bytes,
            image_mime_type=image_mime_type,
            include_model=True,
        )
        conversation.append({"role": "assistant", "content": bot_reply, "model": model_used})

        session["chat_history"] = conversation
        session.modified = True
        return jsonify({"response": bot_reply, "model": selected_model, "model_used": model_used})

    return render_template(
        "patient/chatbot.html",
        conversation=conversation,
        disclaimer=DISCLAIMER,
        selected_model=selected_model,
    )
