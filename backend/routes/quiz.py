from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from models import db, Quiz, QuizResult, User, Notification
import os
import json
from datetime import datetime
try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

quiz_bp = Blueprint("quiz", __name__)

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'doc', 'docx', 'md'}
UPLOAD_FOLDER = 'documents'

def get_user_id():
    """Get user_id from JWT token and convert to int"""
    user_id = get_jwt_identity()
    if isinstance(user_id, str):
        user_id = int(user_id)
    return user_id

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _get_current_user():
    user_id = get_user_id()
    return User.query.get(user_id)


def _admin_required():
    user = _get_current_user()
    if not user or not user.is_admin:
        return None, (jsonify({"message": "Admin access required"}), 403)
    return user, None


def _normalize_quiz_questions(raw_questions):
    if not isinstance(raw_questions, list) or len(raw_questions) == 0:
        raise ValueError("questions must be a non-empty list")

    normalized_questions = []
    for idx, item in enumerate(raw_questions, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Question #{idx} must be an object")

        question_text = str(item.get("question", "")).strip()
        if not question_text:
            raise ValueError(f"Question #{idx} text is required")

        raw_options = item.get("options")
        if not isinstance(raw_options, list):
            raise ValueError(f"Question #{idx} options must be a list")

        cleaned_options = []
        for opt in raw_options:
            text = str(opt).strip()
            if text:
                cleaned_options.append(text)

        if len(cleaned_options) < 2:
            raise ValueError(f"Question #{idx} must have at least 2 options")

        # Preserve order while removing duplicates.
        unique_options = list(dict.fromkeys(cleaned_options))
        if len(unique_options) < 2:
            raise ValueError(f"Question #{idx} must have at least 2 unique options")

        provided_correct = str(item.get("correct_answer", "")).strip()
        if not provided_correct:
            raise ValueError(f"Question #{idx} correct answer is required")
        if provided_correct not in unique_options:
            raise ValueError(f"Question #{idx} correct answer must match one of its options")

        explanation = str(item.get("explanation", "")).strip()

        normalized_question = {
            "question": question_text,
            "options": unique_options,
            "correct_answer": provided_correct,
            "explanation": explanation,
        }
        normalized_questions.append(normalized_question)

    return normalized_questions


# ==================== UPLOAD DOCUMENT ====================
@quiz_bp.route("/upload-document", methods=["POST"])
@jwt_required()
def upload_document():
    """Upload document for quiz generation"""
    try:
        user_id = get_user_id()
        user = User.query.get(user_id)
        
        print(f"Upload attempt - User ID: {user_id}, User: {user}")
        
        if not user:
            return jsonify({"message": "User not found"}), 404
        
        if not user.is_admin:
            return jsonify({"message": "Admin access required. Only admins can upload documents"}), 403
        
        # Log request details
        print(f"Request files: {request.files.keys()}")
        print(f"Request form: {request.form.keys()}")
        
        if 'file' not in request.files:
            error_msg = f"No file provided. Available files: {list(request.files.keys())}"
            print(error_msg)
            return jsonify({"message": error_msg}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({"message": "No file selected"}), 400
        
        if not allowed_file(file.filename):
            return jsonify({"message": f"Invalid file type '{file.filename.rsplit('.', 1)[1].lower()}'. Allowed: txt, pdf, doc, docx, md"}), 400
        
        # Create upload folder if it doesn't exist
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)
        
        # Save file with secure filename
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{timestamp}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
        file.save(filepath)
        
        # Trigger embedding creation (integrate with RAG system)
        try:
            from routes.rag_chatbot import create_document_embeddings
            create_document_embeddings(filepath)
        except Exception as e:
            print(f"Warning: Could not create embeddings: {e}")
        
        # Create notifications for all students (non-admin users)
        try:
            all_students = User.query.filter_by(is_admin=False).all()
            for student in all_students:
                notification = Notification(
                    user_id=student.id,
                    title="New Document Available",
                    message=f"A new document '{filename}' has been uploaded. Check it out!",
                    notification_type="document_upload"
                )
                db.session.add(notification)
            db.session.commit()
        except Exception as e:
            print(f"Warning: Could not create notifications: {e}")
        
        return jsonify({
            "message": "Document uploaded successfully!",
            "filename": unique_filename,
            "filepath": filepath
        }), 201
    
    except Exception as e:
        return jsonify({"message": f"Upload error: {str(e)}"}), 500


# ==================== GENERATE QUIZ ====================
@quiz_bp.route("/generate-quiz", methods=["POST"])
@jwt_required()
def generate_quiz():
    """Generate quiz from uploaded document using LLM"""
    try:
        user_id = get_user_id()
        user = User.query.get(user_id)
        
        if not user or not user.is_admin:
            return jsonify({"message": "Admin access required"}), 403
        
        data = request.json
        document_path = data.get('document_path')
        title = data.get('title', 'Quiz')
        description = data.get('description', '')
        num_questions = data.get('num_questions', 5)
        
        if not document_path or not os.path.exists(document_path):
            return jsonify({"message": "Invalid document path"}), 400
        
        # Read document content based on file type
        try:
            file_ext = os.path.splitext(document_path)[1].lower()
            
            if file_ext == '.pdf':
                # Read PDF
                if PdfReader is None:
                    return jsonify({"message": "PDF support not available. Please install PyPDF2."}), 500
                
                content = ""
                with open(document_path, 'rb') as pdf_file:
                    pdf_reader = PdfReader(pdf_file)
                    for page in pdf_reader.pages:
                        content += page.extract_text() + "\n"
            else:
                # Read as text file
                with open(document_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
        except Exception as e:
            return jsonify({"message": f"Error reading document: {str(e)}"}), 500
        
        if not content or len(content.strip()) == 0:
            return jsonify({"message": "Document is empty or cannot be read"}), 400
        
        # Generate quiz using LLM
        from langchain_groq import ChatGroq
        
        llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            api_key=os.environ.get('GROQ_API_KEY')
        )
        
        prompt = f"""Based on the following document content, generate a quiz with {num_questions} questions.

Document Content:
{content[:3000]}

Generate a quiz in the following JSON format:
{{
    "questions": [
        {{
            "question": "Question text here?",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_answer": "Option A",
            "explanation": "Brief explanation of why this is correct"
        }}
    ]
}}

Make sure questions are relevant, clear, and test understanding of the document content.
Return ONLY the JSON, no additional text."""

        response = llm.invoke(prompt)
        
        # Parse LLM response
        try:
            quiz_data = json.loads(response.content)
            questions = quiz_data.get('questions', [])
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
            if json_match:
                quiz_data = json.loads(json_match.group())
                questions = quiz_data.get('questions', [])
            else:
                return jsonify({"message": "Error parsing quiz from LLM response"}), 500
        
        # Create quiz in database
        new_quiz = Quiz(
            title=title,
            description=description,
            document_name=os.path.basename(document_path),
            questions=questions,
            created_by=user_id
        )
        
        db.session.add(new_quiz)
        db.session.commit()
        
        # Create notifications for all students (non-admin users)
        try:
            all_students = User.query.filter_by(is_admin=False).all()
            for student in all_students:
                notification = Notification(
                    user_id=student.id,
                    title="New Quiz Available",
                    message=f"A new quiz '{title}' has been generated. Test your knowledge!",
                    notification_type="quiz_created",
                    related_id=new_quiz.id
                )
                db.session.add(notification)
            db.session.commit()
        except Exception as e:
            print(f"Warning: Could not create notifications: {e}")
        
        return jsonify({
            "message": "Quiz generated successfully!",
            "quiz": new_quiz.to_dict()
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error generating quiz: {str(e)}"}), 500


# ==================== GET ALL QUIZZES ====================
@quiz_bp.route("/quizzes", methods=["GET"])
@jwt_required()
def get_quizzes():
    """Get all active quizzes"""
    try:
        include_all = (request.args.get("include_all", "0") or "0").strip().lower() in ("1", "true", "yes")
        current_user = _get_current_user()

        if include_all and current_user and current_user.is_admin:
            quizzes = Quiz.query.order_by(Quiz.created_at.desc()).all()
        else:
            quizzes = Quiz.query.filter_by(is_active=True).order_by(Quiz.created_at.desc()).all()

        return jsonify({
            "quizzes": [quiz.to_dict() for quiz in quizzes]
        }), 200
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500


# ==================== CREATE QUIZ MANUALLY (ADMIN) ====================
@quiz_bp.route("/quizzes", methods=["POST"])
@jwt_required()
def create_quiz_manually():
    """Create a quiz with full admin-provided questions/options"""
    try:
        user, admin_error = _admin_required()
        if admin_error:
            return admin_error

        payload = request.get_json(silent=True) or {}
        title = str(payload.get("title", "")).strip()
        description = str(payload.get("description", "")).strip()
        document_name = str(payload.get("document_name", "")).strip() or None
        is_active = bool(payload.get("is_active", True))
        questions = _normalize_quiz_questions(payload.get("questions"))

        if not title:
            return jsonify({"message": "title is required"}), 400

        quiz = Quiz(
            title=title,
            description=description,
            document_name=document_name,
            questions=questions,
            created_by=user.id,
            is_active=is_active,
        )

        db.session.add(quiz)
        db.session.commit()

        return jsonify({
            "message": "Quiz created successfully",
            "quiz": quiz.to_dict(),
        }), 201
    except ValueError as e:
        return jsonify({"message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error creating quiz: {str(e)}"}), 500


# ==================== GET QUIZ BY ID ====================
@quiz_bp.route("/quizzes/<int:quiz_id>", methods=["GET"])
@jwt_required()
def get_quiz(quiz_id):
    """Get specific quiz details"""
    try:
        quiz = Quiz.query.get(quiz_id)
        
        if not quiz:
            return jsonify({"message": "Quiz not found"}), 404
        
        return jsonify({"quiz": quiz.to_dict()}), 200
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500


# ==================== UPDATE QUIZ (ADMIN) ====================
@quiz_bp.route("/quizzes/<int:quiz_id>", methods=["PUT"])
@jwt_required()
def update_quiz(quiz_id):
    """Update quiz title/description/status/questions (admin only)"""
    try:
        _, admin_error = _admin_required()
        if admin_error:
            return admin_error

        quiz = Quiz.query.get(quiz_id)
        if not quiz:
            return jsonify({"message": "Quiz not found"}), 404

        payload = request.get_json(silent=True) or {}

        if "title" in payload:
            title = str(payload.get("title", "")).strip()
            if not title:
                return jsonify({"message": "title cannot be empty"}), 400
            quiz.title = title

        if "description" in payload:
            quiz.description = str(payload.get("description", "")).strip()

        if "document_name" in payload:
            document_name = str(payload.get("document_name", "")).strip()
            quiz.document_name = document_name or None

        if "is_active" in payload:
            quiz.is_active = bool(payload.get("is_active"))

        if "questions" in payload:
            quiz.questions = _normalize_quiz_questions(payload.get("questions"))

        db.session.commit()
        return jsonify({
            "message": "Quiz updated successfully",
            "quiz": quiz.to_dict(),
        }), 200
    except ValueError as e:
        return jsonify({"message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error updating quiz: {str(e)}"}), 500


# ==================== DELETE QUIZ ====================
@quiz_bp.route("/quizzes/<int:quiz_id>", methods=["DELETE"])
@jwt_required()
def delete_quiz(quiz_id):
    """Delete a quiz (admin only)"""
    try:
        user_id = get_user_id()
        user = User.query.get(user_id)

        if not user or not user.is_admin:
            return jsonify({"message": "Admin access required"}), 403

        quiz = Quiz.query.get(quiz_id)
        if not quiz:
            return jsonify({"message": "Quiz not found"}), 404

        db.session.delete(quiz)
        db.session.commit()

        return jsonify({"message": "Quiz deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error deleting quiz: {str(e)}"}), 500


# ==================== SUBMIT QUIZ ====================
@quiz_bp.route("/submit-quiz", methods=["POST"])
@jwt_required()
def submit_quiz():
    """Submit quiz answers and get auto-graded results"""
    try:
        user_id = get_user_id()
        data = request.json
        
        quiz_id = data.get('quiz_id')
        answers = data.get('answers', [])  # List of user answers
        
        if not quiz_id:
            return jsonify({"message": "Quiz ID required"}), 400
        
        quiz = Quiz.query.get(quiz_id)
        if not quiz:
            return jsonify({"message": "Quiz not found"}), 404
        
        # Auto-grade using LLM
        from langchain_groq import ChatGroq
        
        llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            api_key=os.environ.get('GROQ_API_KEY')
        )
        
        grading_prompt = f"""Grade the following quiz answers and provide feedback.

Quiz Questions and Correct Answers:
{json.dumps(quiz.questions, indent=2)}

User Answers:
{json.dumps(answers, indent=2)}

Provide a JSON response with:
1. Score (number of correct answers)
2. Detailed feedback for each question

Response format:
{{
    "score": <number>,
    "total": <total_questions>,
    "feedback": [
        {{
            "question_number": 1,
            "is_correct": true/false,
            "user_answer": "...",
            "correct_answer": "...",
            "explanation": "..."
        }}
    ]
}}

Return ONLY the JSON, no additional text."""

        response = llm.invoke(grading_prompt)
        
        # Parse grading results
        try:
            grading_data = json.loads(response.content)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
            if json_match:
                grading_data = json.loads(json_match.group())
            else:
                # Fallback: simple grading
                score = sum(1 for i, ans in enumerate(answers) if i < len(quiz.questions) and ans == quiz.questions[i].get('correct_answer'))
                grading_data = {
                    "score": score,
                    "total": len(quiz.questions),
                    "feedback": []
                }
        
        score = grading_data.get('score', 0)
        total = grading_data.get('total', len(quiz.questions))
        feedback = grading_data.get('feedback', [])
        
        # Save result to database
        quiz_result = QuizResult(
            quiz_id=quiz_id,
            user_id=user_id,
            answers=answers,
            score=score,
            total_questions=total,
            feedback=feedback
        )
        
        db.session.add(quiz_result)
        db.session.commit()
        
        return jsonify({
            "message": "Quiz submitted successfully!",
            "score": score,
            "total": total,
            "percentage": round((score / total * 100), 2) if total > 0 else 0,
            "feedback": feedback
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error submitting quiz: {str(e)}"}), 500


# ==================== GET USER QUIZ RESULTS ====================
@quiz_bp.route("/my-results", methods=["GET"])
@jwt_required()
def get_my_results():
    """Get current user's quiz results"""
    try:
        user_id = get_user_id()
        results = QuizResult.query.filter_by(user_id=user_id).order_by(QuizResult.completed_at.desc()).all()
        
        return jsonify({
            "results": [result.to_dict() for result in results]
        }), 200
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500


# ==================== GET ALL RESULTS (ADMIN) ====================
@quiz_bp.route("/all-results", methods=["GET"])
@jwt_required()
def get_all_results():
    """Get all quiz results (admin only)"""
    try:
        user_id = get_user_id()
        user = User.query.get(user_id)
        
        if not user or not user.is_admin:
            return jsonify({"message": "Admin access required"}), 403
        
        results = QuizResult.query.order_by(QuizResult.completed_at.desc()).all()
        
        return jsonify({
            "results": [result.to_dict() for result in results]
        }), 200
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500


# ==================== GET UPLOADED DOCUMENTS ====================
@quiz_bp.route("/uploaded-documents", methods=["GET"])
@jwt_required()
def get_uploaded_documents():
    """Get list of uploaded documents"""
    try:
        user_id = get_user_id()
        user = User.query.get(user_id)
        
        if not user or not user.is_admin:
            return jsonify({"message": "Admin access required"}), 403
        
        documents = []
        
        # Check upload folder
        if os.path.exists(UPLOAD_FOLDER):
            for filename in os.listdir(UPLOAD_FOLDER):
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                if os.path.isfile(filepath) and allowed_file(filename):
                    stat = os.stat(filepath)
                    documents.append({
                        "filename": filename,
                        "filepath": filepath,
                        "uploaded_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
        
        # Sort by upload time (newest first)
        documents.sort(key=lambda x: x['uploaded_at'], reverse=True)
        
        return jsonify({
            "documents": documents
        }), 200
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500
