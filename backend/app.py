from flask import Flask, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager
import os
from dotenv import load_dotenv
from sqlalchemy.engine import URL

# Load env from both backend/.env and project-root/.env
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)

# Disable LangChain tracing/telemetry to avoid Pydantic v1 inference errors on Python 3.14
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGCHAIN_TRACING"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGSMITH_TRACING_V2"] = "false"

from flask_sqlalchemy import SQLAlchemy
from routes.dashboard import dashboard_bp
from routes.devotionals import devotionals_bp
from routes.child_progress import child_progress_bp
from routes.planner import planner_bp
from routes.curriculum import curriculum_bp
from models import db  # import db from models.py
from routes.rag_chatbot import rag_bp 
from routes.auth import auth_bp
from routes.quiz import quiz_bp
from routes.homeschool_style_quiz import homeschool_style_quiz_bp
from routes.billing import billing_bp
from routes.onboarding import onboarding_bp

#Create Flask app
app = Flask(__name__)

FLASK_ENV = os.environ.get("FLASK_ENV", "development").lower()
IS_PRODUCTION = FLASK_ENV == "production"

def parse_cors_origins(value: str):
    raw = (value or "*").strip()
    if raw == "*":
        return "*"
    return [origin.strip() for origin in raw.split(",") if origin.strip()]

# Enable CORS for frontend communication (set CORS_ORIGINS in production)
CORS(app, resources={r"/*": {"origins": parse_cors_origins(os.environ.get("CORS_ORIGINS", "*"))}})

# Always return OK for CORS preflight requests
@app.before_request
def handle_options_preflight():
    if request.method == "OPTIONS":
        return "", 200

# #Configure the database
# app.config['SQLALCHEMY_DATABASE_URI'] = "mysql+pymysql://root:@localhost/gracewise"
# app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///gracewise.db')

# Prefer explicit URI env vars. Fallback to DB_* parts to avoid hardcoded credentials.
database_uri = os.environ.get("SQLALCHEMY_DATABASE_URI") or os.environ.get("DATABASE_URL")
if not database_uri:
    database_uri = URL.create(
        drivername="mysql+pymysql",
        username=os.environ.get("DB_USER", "graceuser"),
        password=os.environ.get("DB_PASSWORD", "StrongPass123!"),
        host=os.environ.get("DB_HOST", "localhost"),
        database=os.environ.get("DB_NAME", "gracewise"),
    ).render_as_string(hide_password=False)

app.config['SQLALCHEMY_DATABASE_URI'] = database_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# JWT Configuration
jwt_secret = os.environ.get('JWT_SECRET_KEY')
if IS_PRODUCTION and not jwt_secret:
    raise RuntimeError("JWT_SECRET_KEY is required when FLASK_ENV=production")
app.config['JWT_SECRET_KEY'] = jwt_secret or 'your-secret-key-change-in-production'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = False
app.config['JWT_TOKEN_LOCATION'] = ['headers']
app.config['JWT_HEADER_NAME'] = 'Authorization'
app.config['JWT_HEADER_TYPE'] = 'Bearer'

#Initialize JWT
jwt = JWTManager(app)

#Initialize database with app
db.init_app(app)

#Register blueprints
app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
app.register_blueprint(devotionals_bp, url_prefix="/devotionals")
app.register_blueprint(child_progress_bp, url_prefix="/child_progress")
app.register_blueprint(planner_bp, url_prefix="/planner")
app.register_blueprint(curriculum_bp, url_prefix="/curriculum")
app.register_blueprint(rag_bp, url_prefix="/rag")
app.register_blueprint(quiz_bp, url_prefix="/quiz")
app.register_blueprint(homeschool_style_quiz_bp, url_prefix="/quiz")
app.register_blueprint(billing_bp, url_prefix="/billing")
app.register_blueprint(onboarding_bp, url_prefix="/onboarding")

#Create tables (optional, for first run)
with app.app_context():
    db.create_all()
    
    # Migrate planner table if needed
    try:
        from sqlalchemy import text
        inspector = db.inspect(db.engine)
        
        if 'planner' in inspector.get_table_names():
            existing_columns = [col['name'] for col in inspector.get_columns('planner')]
            
            columns_to_add = []
            if 'start_time' not in existing_columns:
                columns_to_add.append("ADD COLUMN start_time VARCHAR(10)")
            if 'end_time' not in existing_columns:
                columns_to_add.append("ADD COLUMN end_time VARCHAR(10)")
            if 'subject' not in existing_columns:
                columns_to_add.append("ADD COLUMN subject VARCHAR(100)")
            if 'subtitle' not in existing_columns:
                columns_to_add.append("ADD COLUMN subtitle VARCHAR(150)")
            if 'created_at' not in existing_columns:
                columns_to_add.append("ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
            if 'updated_at' not in existing_columns:
                columns_to_add.append("ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
            
            if columns_to_add:
                print("\n" + "="*50)
                print(f"Migrating planner table - adding {len(columns_to_add)} columns...")
                print("="*50)
                for column_def in columns_to_add:
                    sql = f"ALTER TABLE planner {column_def}"
                    db.session.execute(text(sql))
                db.session.commit()
                print("✅ Planner table migration completed!")
                print("="*50 + "\n")
    except Exception as e:
        print(f"⚠️  Planner migration note: {str(e)}")
        db.session.rollback()
    
    # Migrate ai_session table if needed
    try:
        from sqlalchemy import text
        inspector = db.inspect(db.engine)

        if 'ai_session' in inspector.get_table_names():
            existing_columns = [col['name'] for col in inspector.get_columns('ai_session')]
            columns_to_add = []

            if 'chat_type' not in existing_columns:
                columns_to_add.append("ADD COLUMN chat_type VARCHAR(20) DEFAULT 'general'")
            if 'title' not in existing_columns:
                columns_to_add.append("ADD COLUMN title VARCHAR(255)")
            if 'lesson_id' not in existing_columns:
                columns_to_add.append("ADD COLUMN lesson_id INTEGER")
            if 'lesson_name' not in existing_columns:
                columns_to_add.append("ADD COLUMN lesson_name VARCHAR(255)")
            if 'lesson_desc' not in existing_columns:
                columns_to_add.append("ADD COLUMN lesson_desc TEXT")
            if 'updated_at' not in existing_columns:
                columns_to_add.append("ADD COLUMN updated_at DATETIME")

            if columns_to_add:
                print("\n" + "="*50)
                print(f"Migrating ai_session table - adding {len(columns_to_add)} columns...")
                print("="*50)
                for column_def in columns_to_add:
                    sql = f"ALTER TABLE ai_session {column_def}"
                    db.session.execute(text(sql))
                db.session.execute(text("UPDATE ai_session SET chat_type = 'general' WHERE chat_type IS NULL OR chat_type = ''"))
                db.session.execute(text("UPDATE ai_session SET updated_at = started_at WHERE updated_at IS NULL"))
                db.session.commit()
                print("AI session migration completed.")
                print("="*50 + "\n")
    except Exception as e:
        print(f"AI session migration note: {str(e)}")
        db.session.rollback()

    # Migrate user table for subscriptions/onboarding support
    try:
        from sqlalchemy import text
        inspector = db.inspect(db.engine)

        if 'user' in inspector.get_table_names():
            existing_columns = [col['name'] for col in inspector.get_columns('user')]
            columns_to_add = []

            if 'subscription_tier' not in existing_columns:
                columns_to_add.append("ADD COLUMN subscription_tier VARCHAR(20) DEFAULT 'free'")
            if 'subscription_status' not in existing_columns:
                columns_to_add.append("ADD COLUMN subscription_status VARCHAR(30) DEFAULT 'inactive'")
            if 'stripe_customer_id' not in existing_columns:
                columns_to_add.append("ADD COLUMN stripe_customer_id VARCHAR(120)")
            if 'stripe_subscription_id' not in existing_columns:
                columns_to_add.append("ADD COLUMN stripe_subscription_id VARCHAR(120)")
            if 'trial_ends_at' not in existing_columns:
                columns_to_add.append("ADD COLUMN trial_ends_at DATETIME")
            if 'onboarding_completed' not in existing_columns:
                columns_to_add.append("ADD COLUMN onboarding_completed BOOLEAN DEFAULT 0")

            if columns_to_add:
                print("\n" + "="*50)
                print(f"Migrating user table - adding {len(columns_to_add)} columns...")
                print("="*50)
                for column_def in columns_to_add:
                    db.session.execute(text(f"ALTER TABLE user {column_def}"))
                db.session.commit()
                print("User table migration completed.")
                print("="*50 + "\n")
    except Exception as e:
        print(f"User migration note: {str(e)}")
        db.session.rollback()

    # Initialize admin user
    from models import User, AppSetting
    from routes.rag_chatbot import AI_PROMPT_KEY, DEFAULT_AI_PROMPT
    auto_create_admin = os.environ.get("AUTO_CREATE_ADMIN", "true").lower() == "true"
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@grace-wise.com")
    admin = User.query.filter_by(email=admin_email).first()

    if auto_create_admin and not admin:
        admin_password = os.environ.get("ADMIN_PASSWORD")
        if IS_PRODUCTION and not admin_password:
            raise RuntimeError("ADMIN_PASSWORD is required in production when AUTO_CREATE_ADMIN=true")
        if not admin_password:
            admin_password = "grace.admin@123"

        print("\n" + "="*50)
        print("Creating admin user...")
        print("="*50)
        admin = User(
            first_name="Admin",
            last_name="User",
            email=admin_email,
            is_admin=True
        )
        admin.set_password(admin_password)
        db.session.add(admin)
        db.session.commit()
        print(f"Admin user created: {admin_email}")
        print("="*50 + "\n")
    else:
        if admin:
            print(f"\nAdmin user already exists: {admin_email}\n")
        else:
            print("\nSkipping admin auto-create (AUTO_CREATE_ADMIN=false).\n")

    prompt_setting = AppSetting.query.filter_by(setting_key=AI_PROMPT_KEY).first()
    if not prompt_setting:
        prompt_setting = AppSetting(setting_key=AI_PROMPT_KEY, setting_value=DEFAULT_AI_PROMPT)
        db.session.add(prompt_setting)
        db.session.commit()
        print("Default AI prompt initialized.")

#Initialize RAG system on startup
with app.app_context():
    from routes.rag_chatbot import get_qa_chain
    print("\n" + "="*50)
    print("Initializing RAG system at startup...")
    print("="*50)
    get_qa_chain()
    print("RAG system ready for requests.\n")

#Run the app
if __name__ == "__main__":
    app.run(
        debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true",
        use_reloader=False,
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5000")),
        threaded=True,
    )

