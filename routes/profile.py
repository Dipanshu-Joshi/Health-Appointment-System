import os
import uuid

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app import db

profile_bp = Blueprint("profile", __name__)

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def _is_allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


@profile_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        if not full_name:
            flash("Name is required.", "danger")
            return redirect(url_for("profile.profile"))

        current_user.full_name = full_name

        uploaded = request.files.get("profile_image")
        if uploaded and uploaded.filename:
            if not _is_allowed_file(uploaded.filename):
                flash("Please upload a valid image file (png, jpg, jpeg, gif, webp).", "danger")
                return redirect(url_for("profile.profile"))

            uploads_dir = os.path.join(profile_bp.root_path, "..", "static", "uploads", "profiles")
            uploads_dir = os.path.abspath(uploads_dir)
            os.makedirs(uploads_dir, exist_ok=True)

            extension = secure_filename(uploaded.filename).rsplit(".", 1)[1].lower()
            unique_name = f"{uuid.uuid4().hex}.{extension}"
            file_path = os.path.join(uploads_dir, unique_name)
            uploaded.save(file_path)
            current_user.profile_image = f"uploads/profiles/{unique_name}"

        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("profile.profile"))

    return render_template("profile.html")
