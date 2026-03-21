from extensions import db


class User(db.Model):
    __tablename__ = "users"

    # Keep attribute name `id` for app code, map it to DB column `user_id`.
    id = db.Column("user_id", db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    full_name = db.Column(db.String(150))
    designation = db.Column(db.String(100))
    department = db.Column(db.String(100))
    staff_no = db.Column(db.String(50), unique=True)
    contact = db.Column(db.String(50))
    role = db.Column(
        "user_type",
        db.Enum("technician", "complaint_locker", "other", "admin"),
        default="other",
    )
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    auth = db.relationship("UserAuth", back_populates="user", uselist=False)
    technician_profile = db.relationship("TechnicianProfile", back_populates="user", uselist=False)
    assigned_service_memos = db.relationship(
        "ServiceMemo",
        back_populates="assigned_user",
        foreign_keys="ServiceMemo.assigned_to",
    )


class UserAuth(db.Model):
    __tablename__ = "user_auth"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, unique=True)
    email = db.Column(db.String(120), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    user = db.relationship("User", back_populates="auth")


class TechnicianProfile(db.Model):
    __tablename__ = "technician_profile"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, unique=True)
    skills = db.Column(db.Text, nullable=False)
    availability_status = db.Column(
        db.Enum("available", "busy", "offline"),
        nullable=False,
        default="available",
    )
    max_active_jobs = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    user = db.relationship("User", back_populates="technician_profile")


class ServiceMemo(db.Model):
    __tablename__ = "service_memo"

    service_id = db.Column(db.Integer, primary_key=True)
    complain_no = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(100))
    ext_no = db.Column(db.String(20))
    user_name = db.Column(db.String(100))
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"))
    staff_no = db.Column(db.String(50))
    ip_address = db.Column(db.String(45))
    product_name = db.Column(db.String(100))
    model = db.Column(db.String(100))
    serial_no = db.Column(db.String(100))
    ram = db.Column(db.String(50))
    hdd = db.Column(db.String(50))
    lniata = db.Column(db.String(50))
    fault = db.Column(db.Boolean, default=False)
    diagnosed = db.Column(db.Boolean, default=False)
    data_backup = db.Column(db.Boolean, default=False)
    date_out = db.Column(db.Date)
    date_in = db.Column(db.Date)
    status = db.Column(db.String(100))
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.user_id"))
    user_details = db.Column(db.Text)
    diagnosis_notes = db.Column(db.Text)
    admin_action_notes = db.Column(db.Text)
    task_performed = db.Column(db.Boolean, default=False)
    last_updated = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    assigned_user = db.relationship(
        "User",
        back_populates="assigned_service_memos",
        foreign_keys=[assigned_to],
    )


class HardwareWorkshop(db.Model):
    __tablename__ = "hardware_workshop"

    voucher_id = db.Column(db.Integer, primary_key=True)
    complaint_no = db.Column(db.String(50))
    item_description = db.Column(db.String(255))
    qty_issued = db.Column(db.Integer)
    remarks = db.Column(db.Text)
    material_issued_by = db.Column(db.Integer, db.ForeignKey("users.user_id"))
    material_issued_by_designation = db.Column(db.String(100))
    material_issued_by_staff_no = db.Column(db.String(50))
    material_issued_by_signature = db.Column(db.String(255))
    user_name = db.Column(db.String(100))
    user_department = db.Column(db.String(100))
    user_designation = db.Column(db.String(100))
    user_staff_no = db.Column(db.String(50))
    user_contact = db.Column(db.String(50))
    user_signature = db.Column(db.String(255))
    technician_id = db.Column(db.Integer, db.ForeignKey("users.user_id"))
    technician_designation = db.Column(db.String(100))
    technician_staff_no = db.Column(db.String(50))
    technician_signature = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    material_issuer = db.relationship("User", foreign_keys=[material_issued_by])
    technician_user = db.relationship("User", foreign_keys=[technician_id])


# -------------------------------
# Complaint Locker Profile
# -------------------------------
class ComplaintLockerProfile(db.Model):
    __tablename__ = "complaint_lockers"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, unique=True)
    department = db.Column(db.String(100))
    location = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    user = db.relationship("User")


# -------------------------------
# Complaints Table
# -------------------------------
class Complaint(db.Model):
    __tablename__ = "complaints"

    id = db.Column(db.Integer, primary_key=True)

    locker_id = db.Column(db.Integer, db.ForeignKey("complaint_lockers.id"), nullable=False)

    technician_id = db.Column(
        db.Integer,
        db.ForeignKey("users.user_id"),  # Technician is stored in users
        nullable=True
    )

    title = db.Column(db.String(200), nullable=False)
    device_type = db.Column(db.String(50), nullable=True)
    description = db.Column(db.Text, nullable=False)

    status = db.Column(
        db.Enum("open", "in_progress", "closed"),
        default="open"
    )
    assigned_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime,
        server_default=db.func.now(),
        onupdate=db.func.now()
    )

    locker = db.relationship("ComplaintLockerProfile")
    technician = db.relationship("User", foreign_keys=[technician_id])
    internal_demand_voucher = db.relationship(
        "InternalDemandIssueVoucher",
        back_populates="complaint",
        uselist=False,
    )


class DeviceType(db.Model):
    __tablename__ = "device_types"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())


class Location(db.Model):
    __tablename__ = "locations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())


class InternalDemandIssueVoucher(db.Model):
    __tablename__ = "internal_demand_issue_vouchers"

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(
        db.Integer,
        db.ForeignKey("complaints.id"),
        nullable=False,
        unique=True,
    )
    item_description = db.Column(db.String(255), nullable=False)
    quantity_issued = db.Column(db.Integer, nullable=False)
    remarks = db.Column(db.Text)
    created_by_admin_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime,
        server_default=db.func.now(),
        onupdate=db.func.now(),
    )

    complaint = db.relationship("Complaint", back_populates="internal_demand_voucher")
    created_by_admin = db.relationship("User")


