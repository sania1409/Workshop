from datetime import datetime
import ipaddress
import re
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, abort
from sqlalchemy import or_
from extensions import db
from models import Complaint, ComplaintLockerProfile, DeviceType, HardwareWorkshop, Location, ServiceMemo, TechnicianProfile, User

complaint_routes = Blueprint("complaint_routes", __name__)
DEFAULT_DEVICE_TYPES = ["laptop", "desktop", "printer", "scanner", "network", "other"]
DEFAULT_LOCATIONS = ["head_office", "station", "workshop", "other"]


def _get_or_create_locker_profile(user_id: int):
    locker = ComplaintLockerProfile.query.filter_by(user_id=user_id).first()
    if locker:
        return locker

    locker = ComplaintLockerProfile(user_id=user_id)
    db.session.add(locker)
    db.session.commit()
    return locker


def _to_date(value: str):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _get_device_types():
    names = [d.name for d in DeviceType.query.order_by(DeviceType.name.asc()).all() if d.name]
    if names:
        return names
    return DEFAULT_DEVICE_TYPES


def _get_locations():
    names = [l.name for l in Location.query.order_by(Location.name.asc()).all() if l.name]
    if names:
        return names
    return DEFAULT_LOCATIONS


def _next_complain_no():
    latest = ServiceMemo.query.order_by(ServiceMemo.service_id.desc()).first()
    if not latest or not latest.complain_no:
        return "CMP00001"

    text = latest.complain_no.strip().upper()
    match = re.search(r"(\d+)$", text)
    if not match:
        return "CMP00001"

    digits = match.group(1)
    prefix = text[: -len(digits)] or "CMP"
    return f"{prefix}{str(int(digits) + 1).zfill(len(digits))}"


def _skill_tokens(skills_text: str):
    if not skills_text:
        return []
    parts = re.split(r"[,;/\n]+", skills_text.lower())
    return [p.strip() for p in parts if p.strip()]


def _normalize_words(text: str):
    return [w for w in re.split(r"[^a-z0-9]+", (text or "").lower()) if w]


def _technician_active_load(user_id: int):
    complaint_load = Complaint.query.filter(
        Complaint.technician_id == user_id,
        or_(
            Complaint.status.in_(["open", "in_progress"]),
            Complaint.status.is_(None),
        ),
    ).count()
    memo_load = ServiceMemo.query.filter(
        ServiceMemo.assigned_to == user_id,
        or_(
            ServiceMemo.task_performed.is_(False),
            ServiceMemo.task_performed.is_(None),
        ),
    ).count()
    return complaint_load + memo_load


def _pick_technician_for_task(device_type: str, task_text: str):
    task_text = (task_text or "").lower()
    tech_profiles = (
        TechnicianProfile.query
        .join(User, TechnicianProfile.user_id == User.id)
        .filter(User.role == "technician")
        .order_by(User.id.asc())
        .all()
    )

    best_candidate = None  # (score, active_load, user_id)
    device_aliases = {
        "laptop": {"laptop", "notebook"},
        "desktop": {"desktop", "computer", "pc"},
        "printer": {"printer"},
        "scanner": {"scanner"},
        "network": {"network", "lan", "wifi", "internet", "router", "switch"},
        "other": {"other"},
    }
    target_device_tokens = device_aliases.get(device_type, {device_type})

    for profile in tech_profiles:
        # Only offline technicians are excluded hard.
        if profile.availability_status == "offline":
            continue

        tokens = _skill_tokens(profile.skills)
        if not tokens:
            continue

        active_load = _technician_active_load(profile.user_id)
        # Max jobs removed from assignment behavior: available means no active jobs.
        profile.availability_status = "busy" if active_load > 0 else "available"

        score = 0
        # Strong preference for explicit device match from dropdown.
        token_words = set()
        for token in tokens:
            token_words.update(_normalize_words(token))
        if token_words.intersection(target_device_tokens):
            score += 5

        for token in tokens:
            token_l = token.lower()
            if token_l in task_text:
                score += 1
                continue
            token_parts = _normalize_words(token_l)
            if token_parts and any(part in task_text for part in token_parts):
                score += 1

        if score <= 0:
            continue

        candidate = (score, active_load, profile.user_id)

        if (
            best_candidate is None
            or candidate[0] > best_candidate[0]
            or (candidate[0] == best_candidate[0] and candidate[1] < best_candidate[1])
            or (
                candidate[0] == best_candidate[0]
                and candidate[1] == best_candidate[1]
                and candidate[2] < best_candidate[2]
            )
        ):
            best_candidate = candidate

    if best_candidate is not None:
        return best_candidate[2]
    return None


def _pick_technician_for_complaint(title: str, description: str, device_type: str):
    complaint_text = f"{title or ''} {description or ''}"
    return _pick_technician_for_task(device_type=device_type, task_text=complaint_text)


def _refresh_technician_availability(user_id: int):
    profile = TechnicianProfile.query.filter_by(user_id=user_id).first()
    if not profile or profile.availability_status == "offline":
        return

    active_load = _technician_active_load(user_id)
    profile.availability_status = "busy" if active_load > 0 else "available"


def _locker_selectable_technicians():
    tech_profiles = (
        TechnicianProfile.query
        .join(User, TechnicianProfile.user_id == User.id)
        .filter(User.role == "technician")
        .order_by(User.full_name.asc(), User.username.asc())
        .all()
    )
    result = []
    for profile in tech_profiles:
        user = profile.user
        if not user:
            continue
        display_name = user.full_name or user.username
        skills = (profile.skills or "").strip() or "No skills listed"
        result.append({
            "id": user.id,
            "name": display_name,
            "skills": skills,
        })
    return result


# -----------------------------------
# Complaint Locker Dashboard Data
# -----------------------------------
@complaint_routes.route("/locker/complaints")
def locker_complaints():

    if "user_id" not in session or session.get("role") != "complaint_locker":
        return redirect(url_for("auth_routes.login"))

    # Get locker profile
    locker = _get_or_create_locker_profile(session["user_id"])

    complaints = Complaint.query.filter_by(locker_id=locker.id).all()

    return render_template("locker_complaints.html", complaints=complaints)


# -----------------------------------
# Create New Complaint
# -----------------------------------
@complaint_routes.route("/locker/complaints/new", methods=["GET", "POST"])
def create_complaint():

    if "user_id" not in session or session.get("role") != "complaint_locker":
        return redirect(url_for("auth_routes.login"))

    locker = _get_or_create_locker_profile(session["user_id"])

    if request.method == "POST":

        title = request.form.get("title")
        device_type = request.form.get("device_type", "").strip().lower()
        description = request.form.get("description")

        device_types = _get_device_types()
        if not title or not description or device_type not in device_types:
            flash("Title, device type, and description are required.", "danger")
            return render_template("new_complaint.html", device_types=device_types)

        technician_id = _pick_technician_for_complaint(title, description, device_type)
        complaint = Complaint(
            locker_id=locker.id,
            technician_id=technician_id,
            title=title,
            device_type=device_type,
            description=description,
            status="in_progress" if technician_id else "open",
            assigned_at=datetime.utcnow() if technician_id else None,
        )

        db.session.add(complaint)
        if technician_id:
            _refresh_technician_availability(technician_id)
        db.session.commit()

        if technician_id:
            technician = User.query.get(technician_id)
            technician_name = (technician.full_name or technician.username) if technician else "Technician"
            flash(f"Complaint created and assigned to {technician_name}.", "success")
        else:
            flash("Complaint created. No technician skill match found yet.", "warning")
        return redirect(url_for("complaint_routes.locker_complaints"))

    return render_template("new_complaint.html", device_types=_get_device_types())


# -----------------------------------
# View Complaint
# -----------------------------------
@complaint_routes.route("/locker/complaints/<int:id>")
def view_complaint(id):

    if "user_id" not in session or session.get("role") != "complaint_locker":
        return redirect(url_for("auth_routes.login"))

    locker = _get_or_create_locker_profile(session["user_id"])
    complaint = Complaint.query.get_or_404(id)

    if complaint.locker_id != locker.id:
        abort(403)

    return render_template("view_complaint.html", complaint=complaint)


# -----------------------------------
# Service Memo List
# -----------------------------------
@complaint_routes.route("/locker/service-memos")
def locker_service_memos():
    if "user_id" not in session or session.get("role") != "complaint_locker":
        return redirect(url_for("auth_routes.login"))

    # Keep backward compatibility for old rows where created_by_user_id is NULL.
    memos = (
        ServiceMemo.query
        .filter(
            or_(
                ServiceMemo.created_by_user_id == session["user_id"],
                (ServiceMemo.created_by_user_id.is_(None) & (ServiceMemo.user_name == session.get("username")))
            )
        )
        .order_by(ServiceMemo.service_id.desc())
        .all()
    )
    return render_template("locker_service_memos.html", memos=memos)


@complaint_routes.route("/locker/service-memos/<int:service_id>")
def locker_view_service_memo(service_id):
    if "user_id" not in session or session.get("role") != "complaint_locker":
        return redirect(url_for("auth_routes.login"))

    memo = ServiceMemo.query.get_or_404(service_id)
    is_owner = memo.created_by_user_id == session["user_id"]
    is_legacy_owner = (
        memo.created_by_user_id is None and memo.user_name == session.get("username")
    )
    if not (is_owner or is_legacy_owner):
        abort(403)

    return render_template("locker_view_service_memo.html", memo=memo)


# -----------------------------------
# Create Service Memo (Locker Input)
# -----------------------------------
@complaint_routes.route("/locker/service-memos/new", methods=["GET", "POST"])
def create_service_memo():
    if "user_id" not in session or session.get("role") != "complaint_locker":
        return redirect(url_for("auth_routes.login"))

    if request.method == "POST":
        device_type = request.form.get("product_name", "").strip().lower()
        location = request.form.get("location", "").strip().lower()
        technician_id_raw = request.form.get("technician_id", "").strip()
        staff_no = request.form.get("staff_no", "").strip().upper()
        ext_no = request.form.get("ext_no", "").strip()
        ip_address = request.form.get("ip_address", "").strip()
        model = request.form.get("model", "").strip()
        serial_no = request.form.get("serial_no", "").strip()
        ram = request.form.get("ram", "").strip()
        hdd = request.form.get("hdd", "").strip()
        user_details = request.form.get("user_details", "").strip()
        date_in_raw = request.form.get("date_in", "").strip()
        date_in = _to_date(date_in_raw)
        if not date_in_raw:
            date_in = datetime.utcnow().date()

        technicians = _locker_selectable_technicians()
        valid_technician_ids = {str(t["id"]) for t in technicians}
        if (
            device_type not in _get_device_types()
            or location not in _get_locations()
            or technician_id_raw not in valid_technician_ids
        ):
            flash("Location, device type, and technician are required.", "danger")
            return render_template(
                "new_service_memo.html",
                technicians=technicians,
                location_options=_get_locations(),
                device_types=_get_device_types(),
                auto_complain_no=_next_complain_no(),
                today_date=datetime.utcnow().date().isoformat(),
            )

        if not re.fullmatch(r"[A-Za-z][0-9]{5}", staff_no):
            flash("Staff number must be 1 letter followed by 5 digits (example: A12345).", "danger")
            return render_template(
                "new_service_memo.html",
                technicians=technicians,
                location_options=_get_locations(),
                device_types=_get_device_types(),
                auto_complain_no=_next_complain_no(),
                today_date=datetime.utcnow().date().isoformat(),
            )

        if ext_no and not re.fullmatch(r"[0-9]{1,20}", ext_no):
            flash("Ext number must contain digits only.", "danger")
            return render_template(
                "new_service_memo.html",
                technicians=technicians,
                location_options=_get_locations(),
                device_types=_get_device_types(),
                auto_complain_no=_next_complain_no(),
                today_date=datetime.utcnow().date().isoformat(),
            )

        if not serial_no:
            flash("Serial No is required.", "danger")
            return render_template(
                "new_service_memo.html",
                technicians=technicians,
                location_options=_get_locations(),
                device_types=_get_device_types(),
                auto_complain_no=_next_complain_no(),
                today_date=datetime.utcnow().date().isoformat(),
            )

        if not re.fullmatch(r"[A-Za-z0-9/-]{4,12}", serial_no):
            flash("Serial No must be 4-12 characters and use letters, digits, '-' or '/'.", "danger")
            return render_template(
                "new_service_memo.html",
                technicians=technicians,
                location_options=_get_locations(),
                device_types=_get_device_types(),
                auto_complain_no=_next_complain_no(),
                today_date=datetime.utcnow().date().isoformat(),
            )

        if ip_address:
            try:
                ipaddress.ip_address(ip_address)
            except ValueError:
                flash("Invalid IP address format.", "danger")
                return render_template(
                    "new_service_memo.html",
                    technicians=technicians,
                    location_options=LOCATION_OPTIONS,
                    device_types=_get_device_types(),
                    auto_complain_no=_next_complain_no(),
                    today_date=datetime.utcnow().date().isoformat(),
                )

        if len(model) > 100 or len(serial_no) > 12 or len(ram) > 3 or len(hdd) > 4:
            flash("One or more fields exceed allowed length.", "danger")
            return render_template(
                "new_service_memo.html",
                technicians=technicians,
                location_options=_get_locations(),
                device_types=_get_device_types(),
                auto_complain_no=_next_complain_no(),
                today_date=datetime.utcnow().date().isoformat(),
            )
        if len(user_details) > 2000:
            flash("User details cannot exceed 2000 characters.", "danger")
            return render_template(
                "new_service_memo.html",
                technicians=technicians,
                location_options=_get_locations(),
                device_types=_get_device_types(),
                auto_complain_no=_next_complain_no(),
                today_date=datetime.utcnow().date().isoformat(),
            )

        if date_in_raw and date_in is None:
            flash("Date In format is invalid.", "danger")
            return render_template(
                "new_service_memo.html",
                technicians=technicians,
                location_options=_get_locations(),
                device_types=_get_device_types(),
                auto_complain_no=_next_complain_no(),
                today_date=datetime.utcnow().date().isoformat(),
            )
        if date_in and date_in > datetime.utcnow().date():
            flash("Date In cannot be in the future.", "danger")
            return render_template(
                "new_service_memo.html",
                technicians=technicians,
                location_options=_get_locations(),
                device_types=_get_device_types(),
                auto_complain_no=_next_complain_no(),
                today_date=datetime.utcnow().date().isoformat(),
            )

        technician_id = int(technician_id_raw)
        complain_no = _next_complain_no()

        memo = ServiceMemo(
            complain_no=complain_no,
            location=location,
            ext_no=ext_no or None,
            user_name=session.get("username"),
            created_by_user_id=session["user_id"],
            staff_no=staff_no,
            ip_address=ip_address or None,
            product_name=request.form.get("product_name", "").strip() or None,
            model=model or None,
            serial_no=serial_no or None,
            ram=ram or None,
            hdd=hdd or None,
            data_backup=("data_backup" in request.form),
            date_in=date_in,
            status="pending",
            user_details=user_details or None,
            diagnosed=False,
            date_out=None,
            task_performed=False,
            assigned_to=technician_id,
        )

        db.session.add(memo)
        if technician_id:
            _refresh_technician_availability(technician_id)
        db.session.commit()
        technician = User.query.get(technician_id)
        technician_name = (technician.full_name or technician.username) if technician else "Technician"
        flash(f"Service memo submitted and assigned to {technician_name}.", "success")
        return redirect(url_for("complaint_routes.locker_service_memos"))

    return render_template(
        "new_service_memo.html",
        technicians=_locker_selectable_technicians(),
        location_options=_get_locations(),
        device_types=_get_device_types(),
        auto_complain_no=_next_complain_no(),
        today_date=datetime.utcnow().date().isoformat(),
    )


# -----------------------------------
# Technician Updates Complaint Status
# -----------------------------------
@complaint_routes.route("/technician/complaints/<int:id>/status", methods=["POST"])
def technician_update_complaint_status(id):
    if "user_id" not in session or session.get("role") != "technician":
        return redirect(url_for("auth_routes.login"))

    complaint = Complaint.query.get_or_404(id)
    if complaint.technician_id != session["user_id"]:
        abort(403)

    new_status = request.form.get("status", "").strip()
    if new_status not in {"in_progress", "closed"}:
        flash("Invalid complaint status.", "danger")
        return redirect(url_for("main_routes.technician_dashboard"))

    complaint.status = new_status
    _refresh_technician_availability(session["user_id"])
    db.session.commit()
    flash("Complaint status updated.", "success")
    return redirect(url_for("main_routes.technician_dashboard"))


# -----------------------------------
# Technician Views/Diagnoses Service Memo
# -----------------------------------
@complaint_routes.route("/technician/service-memos/<int:service_id>", methods=["GET", "POST"])
def technician_view_service_memo(service_id):
    if "user_id" not in session or session.get("role") != "technician":
        return redirect(url_for("auth_routes.login"))

    memo = ServiceMemo.query.get_or_404(service_id)
    if memo.assigned_to != session["user_id"]:
        abort(403)

    if request.method == "POST":
        diagnosis_notes = request.form.get("diagnosis_notes", "").strip()
        if not diagnosis_notes:
            flash("Diagnosis notes are required.", "danger")
            return render_template("technician_view_service_memo.html", memo=memo)

        memo.diagnosis_notes = diagnosis_notes
        memo.diagnosed = True
        memo.status = "diagnosed"
        db.session.commit()
        flash("Memo diagnosed successfully.", "success")
        return redirect(url_for("main_routes.technician_dashboard"))

    return render_template("technician_view_service_memo.html", memo=memo)


# -----------------------------------
# Admin Reviews/Completes Service Memo
# -----------------------------------
@complaint_routes.route("/admin/service-memos/<int:service_id>", methods=["GET", "POST"])
def admin_view_service_memo(service_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("auth_routes.login"))

    memo = ServiceMemo.query.get_or_404(service_id)
    existing_items = (
        HardwareWorkshop.query
        .filter_by(complaint_no=memo.complain_no)
        .order_by(HardwareWorkshop.created_at.asc())
        .all()
    )

    if request.method == "POST":
        admin_action_notes = request.form.get("admin_action_notes", "").strip()
        item_descriptions = [v.strip() for v in request.form.getlist("item_description") if v is not None]
        quantity_issued_raw = [v.strip() for v in request.form.getlist("quantity_issued") if v is not None]
        remarks_list = [v.strip() for v in request.form.getlist("remarks") if v is not None]

        if not admin_action_notes:
            flash("Admin action notes are required.", "danger")
            return render_template("admin_view_service_memo.html", memo=memo, items=existing_items)
        new_items = []
        for index, item_description in enumerate(item_descriptions):
            if not item_description:
                continue
            qty_raw = quantity_issued_raw[index] if index < len(quantity_issued_raw) else ""
            remark = remarks_list[index] if index < len(remarks_list) else ""
            try:
                quantity_issued = int(qty_raw)
            except (TypeError, ValueError):
                flash("Quantity issued must be a valid number.", "danger")
                return render_template("admin_view_service_memo.html", memo=memo, items=existing_items)
            if quantity_issued <= 0:
                flash("Quantity issued must be greater than 0.", "danger")
                return render_template("admin_view_service_memo.html", memo=memo, items=existing_items)
            new_items.append({
                "item_description": item_description,
                "quantity_issued": quantity_issued,
                "remarks": remark or None,
            })

        # Hardware items are optional; allow completion with zero items.

        memo.admin_action_notes = admin_action_notes
        memo.task_performed = True
        memo.status = "completed"
        memo.date_out = datetime.utcnow().date()

        admin_user = User.query.get(session["user_id"])
        for item in new_items:
            db.session.add(
                HardwareWorkshop(
                    complaint_no=memo.complain_no,
                    item_description=item["item_description"],
                    qty_issued=item["quantity_issued"],
                    remarks=item["remarks"],
                    material_issued_by=session["user_id"],
                    material_issued_by_designation=admin_user.designation if admin_user else None,
                    material_issued_by_staff_no=admin_user.staff_no if admin_user else None,
                    user_name=memo.user_name,
                    user_staff_no=memo.staff_no,
                    technician_id=memo.assigned_to,
                )
            )

        db.session.commit()

        if memo.assigned_to:
            _refresh_technician_availability(memo.assigned_to)
            db.session.commit()

        flash("Service memo marked as completed.", "success")
        return redirect(url_for("main_routes.admin_dashboard"))

    return render_template("admin_view_service_memo.html", memo=memo, items=existing_items)


@complaint_routes.route("/admin/internal-demand-vouchers/<int:voucher_id>/print")
def admin_print_internal_demand_voucher(voucher_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("auth_routes.login"))

    voucher = HardwareWorkshop.query.get_or_404(voucher_id)
    memo = ServiceMemo.query.filter_by(complain_no=voucher.complaint_no).first()
    items = HardwareWorkshop.query.filter_by(complaint_no=voucher.complaint_no).all()
    return render_template(
        "admin_print_internal_demand_voucher.html",
        complaint_no=voucher.complaint_no,
        items=items,
        memo=memo,
    )


@complaint_routes.route("/admin/internal-demand-vouchers/complaint/<complaint_no>/print")
def admin_print_internal_demand_voucher_for_complaint(complaint_no):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("auth_routes.login"))

    items = HardwareWorkshop.query.filter_by(complaint_no=complaint_no).all()
    if not items:
        abort(404)
    memo = ServiceMemo.query.filter_by(complain_no=complaint_no).first()
    return render_template(
        "admin_print_internal_demand_voucher.html",
        complaint_no=complaint_no,
        items=items,
        memo=memo,
    )
