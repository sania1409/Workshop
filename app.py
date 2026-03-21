from flask import Flask
from config import Config
from extensions import db, migrate, bcrypt
from flask_login import LoginManager
from models import User
from sqlalchemy import text

login_manager = LoginManager()
login_manager.login_view = "auth_routes.login"


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    login_manager.init_app(app)

    # Import and register blueprints
    from routes.auth_routes import auth_routes
    from routes.main_routes import main_routes

    app.register_blueprint(auth_routes)
    app.register_blueprint(main_routes)
     
    from routes.complaint_routes import complaint_routes
    app.register_blueprint(complaint_routes)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Keep existing DB structure and add only auth/profile tables if missing.
    with app.app_context():
        db.session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS user_auth (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL UNIQUE,
                    email VARCHAR(120) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_user_auth_user FOREIGN KEY (user_id) REFERENCES users(user_id)
                        ON DELETE CASCADE
                )
                """
            )
        )
        db.session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS technician_profile (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL UNIQUE,
                    skills TEXT NOT NULL,
                    availability_status ENUM('available','busy','offline') NOT NULL DEFAULT 'available',
                    max_active_jobs INT NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_technician_profile_user FOREIGN KEY (user_id) REFERENCES users(user_id)
                        ON DELETE CASCADE
                )
                """
            )
        )
        db.session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS device_types (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(50) NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        db.session.execute(
            text(
                """
                INSERT IGNORE INTO device_types (name)
                VALUES
                    ('laptop'),
                    ('desktop'),
                    ('printer'),
                    ('scanner'),
                    ('network'),
                    ('other')
                """
            )
        )
        db.session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS locations (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(50) NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        db.session.execute(
            text(
                """
                INSERT IGNORE INTO locations (name)
                VALUES
                    ('head_office'),
                    ('station'),
                    ('workshop'),
                    ('other')
                """
            )
        )
        db.session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS internal_demand_issue_vouchers (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    complaint_id INT NOT NULL UNIQUE,
                    item_description VARCHAR(255) NOT NULL,
                    quantity_issued INT NOT NULL,
                    remarks TEXT,
                    created_by_admin_id INT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    CONSTRAINT fk_internal_demand_voucher_complaint
                        FOREIGN KEY (complaint_id) REFERENCES complaints(id)
                        ON DELETE CASCADE,
                    CONSTRAINT fk_internal_demand_voucher_admin
                        FOREIGN KEY (created_by_admin_id) REFERENCES users(user_id)
                )
                """
            )
        )
        db.session.commit()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
