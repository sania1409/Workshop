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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_technician_profile_user FOREIGN KEY (user_id) REFERENCES users(user_id)
                        ON DELETE CASCADE
                )
                """
            )
        )
        db.session.commit()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
