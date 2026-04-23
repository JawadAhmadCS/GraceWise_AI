from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from models import db, User, PasswordResetToken
from datetime import timedelta, datetime
import secrets
from utils.access_control import normalize_tier

from services.email_service import send_password_reset_email, send_welcome_email

auth_bp = Blueprint("auth", __name__)

def get_user_id():
    """Get user_id from JWT token and convert to int"""
    user_id = get_jwt_identity()
    if isinstance(user_id, str):
        user_id = int(user_id)
    return user_id

# ==================== SIGNUP ====================
@auth_bp.route("/signup", methods=["POST"])
def signup():
    """Register a new user"""
    try:
        data = request.json
        
        # Validate required fields
        if not data or not data.get('email') or not data.get('password') or not data.get('first_name'):
            return jsonify({"message": "Missing required fields: email, password, first_name"}), 400
        
        email = data.get('email').strip().lower()
        password = data.get('password')
        first_name = data.get('first_name')
        last_name = data.get('last_name', '')
        
        # Validate email format
        if '@' not in email:
            return jsonify({"message": "Invalid email format"}), 400
        
        # Validate password strength
        if len(password) < 6:
            return jsonify({"message": "Password must be at least 6 characters long"}), 400
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({"message": "Email already registered. Please sign in instead."}), 409
        
        # Create new user
        new_user = User(
            first_name=first_name,
            last_name=last_name,
            email=email
        )
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()

        send_welcome_email(new_user)
        
        return jsonify({
            "message": "User registered successfully!",
            "user": new_user.to_dict()
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error during registration: {str(e)}"}), 500


# ==================== LOGIN ====================
@auth_bp.route("/login", methods=["POST"])
def login():
    """User login and token generation"""
    try:
        data = request.json
        
        if not data or not data.get('email') or not data.get('password'):
            return jsonify({"message": "Missing email or password"}), 400
        
        email = data.get('email').strip().lower()
        password = data.get('password')
        
        # Find user by email
        user = User.query.filter_by(email=email).first()
        
        if not user or not user.check_password(password):
            return jsonify({"message": "Invalid email or password"}), 401
        
        if not user.is_active:
            return jsonify({"message": "User account is inactive"}), 403
        
        # Update last login timestamp
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Create access token
        access_token = create_access_token(
            identity=str(user.id),  # Convert to string to ensure proper JWT encoding
            expires_delta=timedelta(days=30)
        )
        
        return jsonify({
            "message": "Login successful!",
            "access_token": access_token,
            "user": user.to_dict()
        }), 200
    
    except Exception as e:
        return jsonify({"message": f"Login error: {str(e)}"}), 500


# ==================== FORGOT PASSWORD ====================
@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    """
    Generate a reset token and email it to the user.
    Response is intentionally generic to avoid account enumeration.
    """
    try:
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip().lower()

        if not email or "@" not in email:
            return jsonify({"message": "If this email exists, a reset link has been sent."}), 200

        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify({"message": "If this email exists, a reset link has been sent."}), 200

        # Invalidate active tokens before issuing a new one.
        active_tokens = PasswordResetToken.query.filter_by(user_id=user.id, used_at=None).all()
        for tok in active_tokens:
            tok.used_at = datetime.utcnow()

        token = secrets.token_urlsafe(48)
        expires_at = datetime.utcnow() + timedelta(hours=1)

        reset_token = PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=expires_at,
        )
        db.session.add(reset_token)
        db.session.commit()

        send_password_reset_email(user, token)

        return jsonify({"message": "If this email exists, a reset link has been sent."}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error processing request: {str(e)}"}), 500


# ==================== VALIDATE RESET TOKEN ====================
@auth_bp.route("/reset-password/validate", methods=["GET"])
def validate_reset_token():
    try:
        token = (request.args.get("token") or "").strip()
        if not token:
            return jsonify({"valid": False, "message": "Token is required"}), 400

        reset_token = PasswordResetToken.query.filter_by(token=token).first()
        if not reset_token or not reset_token.is_valid():
            return jsonify({"valid": False, "message": "Invalid or expired token"}), 400

        return jsonify({"valid": True}), 200
    except Exception as e:
        return jsonify({"valid": False, "message": f"Validation error: {str(e)}"}), 500


# ==================== RESET PASSWORD ====================
@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    try:
        data = request.get_json(silent=True) or {}
        token = (data.get("token") or "").strip()
        new_password = data.get("new_password") or ""

        if not token or not new_password:
            return jsonify({"message": "Missing token or new_password"}), 400

        if len(new_password) < 6:
            return jsonify({"message": "Password must be at least 6 characters long"}), 400

        reset_token = PasswordResetToken.query.filter_by(token=token).first()
        if not reset_token or not reset_token.is_valid():
            return jsonify({"message": "Invalid or expired token"}), 400

        user = User.query.get(reset_token.user_id)
        if not user:
            return jsonify({"message": "User not found"}), 404

        user.set_password(new_password)
        reset_token.used_at = datetime.utcnow()

        # Mark any other outstanding tokens as used.
        siblings = PasswordResetToken.query.filter_by(user_id=user.id, used_at=None).all()
        for sibling in siblings:
            if sibling.id != reset_token.id:
                sibling.used_at = datetime.utcnow()

        db.session.commit()
        return jsonify({"message": "Password reset successful. Please sign in."}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error resetting password: {str(e)}"}), 500


# ==================== GET CURRENT USER ====================
@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def get_current_user():
    """Get current logged-in user information"""
    try:
        user_id = get_user_id()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({"message": "User not found"}), 404
        
        return jsonify({"user": user.to_dict()}), 200
    
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500


# ==================== GET ALL USERS (ADMIN ONLY) ====================
@auth_bp.route("/all-users", methods=["GET"])
@jwt_required()
def get_all_users():
    """Get all users (admin only)"""
    try:
        user_id = get_user_id()
        current_user = User.query.get(user_id)
        
        if not current_user or not current_user.is_admin:
            return jsonify({"message": "Admin access required"}), 403
        
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        search = request.args.get('search', '', type=str)
        sort_by = request.args.get('sort_by', 'newest', type=str)
        
        # Build query
        query = User.query
        
        # Apply search filter
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                db.or_(
                    User.first_name.ilike(search_term),
                    User.last_name.ilike(search_term),
                    User.email.ilike(search_term)
                )
            )
        
        # Apply sorting
        if sort_by == 'oldest':
            query = query.order_by(User.created_at.asc())
        elif sort_by == 'name_asc':
            query = query.order_by(User.first_name.asc(), User.last_name.asc())
        elif sort_by == 'name_desc':
            query = query.order_by(User.first_name.desc(), User.last_name.desc())
        else:  # newest (default)
            query = query.order_by(User.created_at.desc())
        
        # Paginate
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        users = [user.to_dict() for user in pagination.items]
        
        return jsonify({
            "users": users,
            "total": pagination.total,
            "page": page,
            "per_page": per_page,
            "total_pages": pagination.pages
        }), 200
    
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500


# ==================== ADMIN UPDATE USER ACCESS ====================
@auth_bp.route("/admin/users/<int:target_user_id>", methods=["PATCH"])
@jwt_required()
def admin_update_user_access(target_user_id):
    """Allow admin to update user access flags"""
    try:
        admin_id = get_user_id()
        admin_user = User.query.get(admin_id)

        if not admin_user or not admin_user.is_admin:
            return jsonify({"message": "Admin access required"}), 403

        target_user = User.query.get(target_user_id)
        if not target_user:
            return jsonify({"message": "User not found"}), 404

        data = request.json or {}
        changed = False

        if "is_active" in data:
            target_user.is_active = bool(data["is_active"])
            changed = True

        if "is_admin" in data:
            requested_admin = bool(data["is_admin"])
            if target_user.id == admin_user.id and requested_admin is False:
                return jsonify({"message": "You cannot remove your own admin access"}), 400
            target_user.is_admin = requested_admin
            changed = True

        if "free_plan_tier" in data:
            requested_plan = normalize_tier(data.get("free_plan_tier"))
            if requested_plan not in {"plan", "thrive", "together"}:
                return jsonify({"message": "Invalid free_plan_tier. Use plan, thrive, or together"}), 400

            target_user.subscription_tier = requested_plan
            target_user.subscription_status = "active"
            target_user.trial_ends_at = None
            changed = True

        if not changed:
            return jsonify({"message": "No valid fields provided"}), 400

        db.session.commit()

        return jsonify({
            "message": "User access updated successfully",
            "user": target_user.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error: {str(e)}"}), 500


# ==================== UPDATE USER ====================
@auth_bp.route("/update", methods=["PUT"])
@jwt_required()
def update_user():
    """Update user information"""
    try:
        user_id = get_user_id()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({"message": "User not found"}), 404
        
        data = request.json
        
        if 'first_name' in data:
            user.first_name = data['first_name']
        
        if 'last_name' in data:
            user.last_name = data['last_name']
        
        db.session.commit()
        
        return jsonify({
            "message": "User updated successfully!",
            "user": user.to_dict()
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error: {str(e)}"}), 500


# ==================== CHANGE PASSWORD ====================
@auth_bp.route("/change-password", methods=["POST"])
@jwt_required()
def change_password():
    """Change user password"""
    try:
        user_id = get_user_id()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({"message": "User not found"}), 404
        
        data = request.json
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not current_password or not new_password:
            return jsonify({"message": "Missing required fields"}), 400
        
        if not user.check_password(current_password):
            return jsonify({"message": "Current password is incorrect"}), 401
        
        if len(new_password) < 6:
            return jsonify({"message": "Password must be at least 6 characters"}), 400
        
        user.set_password(new_password)
        db.session.commit()
        
        return jsonify({"message": "Password changed successfully!"}), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error: {str(e)}"}), 500


# ==================== UPDATE AVATAR ====================
@auth_bp.route("/update-avatar", methods=["POST"])
@jwt_required()
def update_avatar():
    """Update user avatar/profile picture"""
    try:
        user_id = get_user_id()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({"message": "User not found"}), 404
        
        if 'avatar' not in request.files:
            return jsonify({"message": "No avatar file provided"}), 400
        
        file = request.files['avatar']
        
        if file.filename == '':
            return jsonify({"message": "No file selected"}), 400
        
        # Validate file type
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
        if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
            return jsonify({"message": "Invalid file type. Only PNG, JPG, JPEG, GIF allowed"}), 400
        
        # Save avatar file (simple implementation - you may want to use cloud storage)
        import os
        avatar_dir = 'documents/avatars'
        if not os.path.exists(avatar_dir):
            os.makedirs(avatar_dir)
        
        filename = f"user_{user_id}_avatar.png"
        filepath = os.path.join(avatar_dir, filename)
        file.save(filepath)
        
        return jsonify({"message": "Avatar updated successfully", "avatar_url": f"/documents/avatars/{filename}"}), 200
    
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500


# ==================== CHECK EMAIL ====================
@auth_bp.route("/check-email", methods=["POST"])
def check_email():
    """Check if email is available"""
    try:
        data = request.json
        email = data.get('email', '').strip().lower()
        
        if not email:
            return jsonify({"available": False, "message": "Email is required"}), 400
        
        user = User.query.filter_by(email=email).first()
        
        return jsonify({
            "available": user is None,
            "message": "Email is available" if user is None else "Email already registered"
        }), 200
    
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500


# ==================== UPDATE PROFILE ====================
@auth_bp.route("/update-profile", methods=["PUT"])
@jwt_required()
def update_profile():
    """Update user profile (name)"""
    try:
        user_id = get_user_id()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({"message": "User not found"}), 404
        
        data = request.json
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        
        if not first_name:
            return jsonify({"message": "First name is required"}), 400
        
        user.first_name = first_name
        user.last_name = last_name
        db.session.commit()
        
        return jsonify({
            "message": "Profile updated successfully",
            "user": user.to_dict()
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error: {str(e)}"}), 500


# ==================== UPDATE EMAIL ====================
@auth_bp.route("/update-email", methods=["PUT"])
@jwt_required()
def update_email():
    """Update user email"""
    try:
        user_id = get_user_id()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({"message": "User not found"}), 404
        
        data = request.json
        new_email = data.get('new_email', '').strip().lower()
        password = data.get('password', '')
        
        if not new_email or not password:
            return jsonify({"message": "Email and password are required"}), 400
        
        # Verify password
        if not user.check_password(password):
            return jsonify({"message": "Incorrect password"}), 401
        
        # Check if email already exists
        existing_user = User.query.filter_by(email=new_email).first()
        if existing_user and existing_user.id != user_id:
            return jsonify({"message": "Email already in use"}), 409
        
        user.email = new_email
        db.session.commit()
        
        return jsonify({
            "message": "Email updated successfully",
            "user": user.to_dict()
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error: {str(e)}"}), 500


# ==================== NOTIFICATION PREFERENCES ====================
@auth_bp.route("/notification-preferences", methods=["PUT"])
@jwt_required()
def update_notification_preferences():
    """Update user notification preferences"""
    try:
        user_id = get_user_id()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({"message": "User not found"}), 404
        
        data = request.json
        notifications_enabled = data.get('notifications_enabled', True)
        
        # Store preference in user model (you may need to add this field to User model)
        # For now, we'll just return success. You can add a column to User model if needed
        # user.notifications_enabled = notifications_enabled
        # db.session.commit()
        
        return jsonify({
            "message": "Notification preferences updated successfully",
            "notifications_enabled": notifications_enabled
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error: {str(e)}"}), 500
