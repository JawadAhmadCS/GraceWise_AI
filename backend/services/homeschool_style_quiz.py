from collections import Counter
import json
import re
from pathlib import Path

DEFAULT_STYLE_PROFILES = {
    "CL": {
        "title": "Classical",
        "summary": "You thrive with structure, deep learning, and clear academic progression.",
        "strengths": [
            "You value mastery and consistency.",
            "You are intentional about academic rigor.",
            "You create dependable rhythms for your family.",
        ],
    },
    "CM": {
        "title": "Charlotte Mason",
        "summary": "You lean toward rich books, short focused lessons, and heart-level learning.",
        "strengths": [
            "You nurture wonder and attention.",
            "You prioritize meaningful conversations.",
            "You blend academics with beauty and nature.",
        ],
    },
    "UN": {
        "title": "Unit Study",
        "summary": "You love connecting subjects around shared themes and real-life projects.",
        "strengths": [
            "You make learning feel connected and practical.",
            "You are strong at project-based teaching.",
            "You naturally adapt to family-wide learning.",
        ],
    },
    "TR": {
        "title": "Traditional",
        "summary": "You prefer proven classroom-like methods and measurable progress.",
        "strengths": [
            "You value clarity and accountability.",
            "You keep expectations consistent.",
            "You prefer structured pacing.",
        ],
    },
    "ON": {
        "title": "Online",
        "summary": "You value digital tools and flexible platform-based learning.",
        "strengths": [
            "You are resourceful with ed-tech tools.",
            "You scale learning with online systems.",
            "You support independent digital progress.",
        ],
    },
    "US": {
        "title": "Unschooling",
        "summary": "You trust natural curiosity and prioritize intrinsic motivation.",
        "strengths": [
            "You build ownership and confidence.",
            "You reduce pressure and preserve joy.",
            "You are responsive to each child's unique pace.",
        ],
    },
    "HY": {
        "title": "Hybrid",
        "summary": "You blend methods based on season, child, and subject.",
        "strengths": [
            "You are highly adaptable.",
            "You personalize learning with wisdom.",
            "You balance structure and flexibility well.",
        ],
    },
}

STYLE_CODE_ALIASES = {
    "cl": "CL",
    "classical": "CL",
    "cm": "CM",
    "charlotte_mason": "CM",
    "charlottemason": "CM",
    "un": "UN",
    "unit_study": "UN",
    "unitstudy": "UN",
    "tr": "TR",
    "traditional": "TR",
    "on": "ON",
    "online": "ON",
    "us": "US",
    "unschooling": "US",
    "hy": "HY",
    "hybrid": "HY",
    "eclectic": "HY",
}

LEGACY_OPTION_STYLE_EXPANSION = {
    "CL": ["CL", "TR"],
    "CM": ["CM"],
    "UN": ["UN"],
    "TR": ["TR"],
    "ON": ["ON"],
    "US": ["US"],
    "HY": ["HY", "ON"],
}

DEFAULT_QUESTIONS = [
    {
        "id": "q1",
        "question": "When planning your homeschool week, what feels most natural?",
        "options": [
            {"key": "q1_a", "text": "A clear schedule with specific subjects each day", "style": "classical"},
            {"key": "q1_b", "text": "Short meaningful lessons with books and narration", "style": "charlotte_mason"},
            {"key": "q1_c", "text": "A theme everyone can explore in different ways", "style": "unit_study"},
            {"key": "q1_d", "text": "Following the child's interests as they unfold", "style": "unschooling"},
            {"key": "q1_e", "text": "Mixing structure and flexibility based on the day", "style": "eclectic"},
        ],
    },
    {
        "id": "q2",
        "question": "What is your ideal role during learning time?",
        "options": [
            {"key": "q2_a", "text": "Instructor with a clear lesson plan", "style": "classical"},
            {"key": "q2_b", "text": "Guide who sparks reflection and discussion", "style": "charlotte_mason"},
            {"key": "q2_c", "text": "Facilitator of projects and hands-on discovery", "style": "unit_study"},
            {"key": "q2_d", "text": "Mentor who supports child-led exploration", "style": "unschooling"},
            {"key": "q2_e", "text": "Coach who adjusts approach as needed", "style": "eclectic"},
        ],
    },
    {
        "id": "q3",
        "question": "How do you usually choose curriculum?",
        "options": [
            {"key": "q3_a", "text": "Comprehensive, proven programs with progression", "style": "classical"},
            {"key": "q3_b", "text": "Living books and rich ideas over worksheets", "style": "charlotte_mason"},
            {"key": "q3_c", "text": "Resources that can connect across subjects", "style": "unit_study"},
            {"key": "q3_d", "text": "Minimal curriculum, mostly real-life learning", "style": "unschooling"},
            {"key": "q3_e", "text": "Different tools for different children/subjects", "style": "eclectic"},
        ],
    },
    {
        "id": "q4",
        "question": "When your child resists a lesson, what is your first instinct?",
        "options": [
            {"key": "q4_a", "text": "Keep the expectation but adjust pacing", "style": "classical"},
            {"key": "q4_b", "text": "Pause and reconnect through conversation", "style": "charlotte_mason"},
            {"key": "q4_c", "text": "Shift to a creative or practical activity", "style": "unit_study"},
            {"key": "q4_d", "text": "Let interest lead and revisit later", "style": "unschooling"},
            {"key": "q4_e", "text": "Try a different method entirely", "style": "eclectic"},
        ],
    },
    {
        "id": "q5",
        "question": "What does a successful homeschool day look like to you?",
        "options": [
            {"key": "q5_a", "text": "Core subjects completed with solid understanding", "style": "classical"},
            {"key": "q5_b", "text": "Deep ideas discussed and habits nurtured", "style": "charlotte_mason"},
            {"key": "q5_c", "text": "Meaningful project progress with family collaboration", "style": "unit_study"},
            {"key": "q5_d", "text": "Child highly engaged in self-directed learning", "style": "unschooling"},
            {"key": "q5_e", "text": "We adapted and still moved forward", "style": "eclectic"},
        ],
    },
    {
        "id": "q6",
        "question": "How do you feel about testing and assessments?",
        "options": [
            {"key": "q6_a", "text": "Useful for tracking mastery and gaps", "style": "classical"},
            {"key": "q6_b", "text": "Prefer narration, observation, and discussion", "style": "charlotte_mason"},
            {"key": "q6_c", "text": "Prefer project outputs over traditional tests", "style": "unit_study"},
            {"key": "q6_d", "text": "Mostly unnecessary for daily learning", "style": "unschooling"},
            {"key": "q6_e", "text": "Use whichever method fits the context", "style": "eclectic"},
        ],
    },
    {
        "id": "q7",
        "question": "Which environment helps your child learn best?",
        "options": [
            {"key": "q7_a", "text": "Consistent routine with predictable blocks", "style": "classical"},
            {"key": "q7_b", "text": "Calm rhythm with books, nature, and reflection", "style": "charlotte_mason"},
            {"key": "q7_c", "text": "Interactive spaces for experiments and projects", "style": "unit_study"},
            {"key": "q7_d", "text": "Real-world settings and everyday experiences", "style": "unschooling"},
            {"key": "q7_e", "text": "A mix depending on mood and goals", "style": "eclectic"},
        ],
    },
    {
        "id": "q8",
        "question": "When introducing a new topic, you usually start with:",
        "options": [
            {"key": "q8_a", "text": "Definitions, sequence, and core concepts", "style": "classical"},
            {"key": "q8_b", "text": "A compelling story or great book", "style": "charlotte_mason"},
            {"key": "q8_c", "text": "A hands-on challenge or mini project", "style": "unit_study"},
            {"key": "q8_d", "text": "Questions your child already has", "style": "unschooling"},
            {"key": "q8_e", "text": "Whatever approach fits that topic best", "style": "eclectic"},
        ],
    },
    {
        "id": "q9",
        "question": "What is your biggest homeschool priority this season?",
        "options": [
            {"key": "q9_a", "text": "Academic depth and skill progression", "style": "classical"},
            {"key": "q9_b", "text": "Character formation and love of learning", "style": "charlotte_mason"},
            {"key": "q9_c", "text": "Integrated learning that feels meaningful", "style": "unit_study"},
            {"key": "q9_d", "text": "Autonomy, confidence, and curiosity", "style": "unschooling"},
            {"key": "q9_e", "text": "Sustainable rhythms that actually work", "style": "eclectic"},
        ],
    },
    {
        "id": "q10",
        "question": "How do you make curriculum decisions when life gets busy?",
        "options": [
            {"key": "q10_a", "text": "Preserve core sequence and trim extras", "style": "classical"},
            {"key": "q10_b", "text": "Focus on essential books and habits", "style": "charlotte_mason"},
            {"key": "q10_c", "text": "Consolidate into one strong unit or project", "style": "unit_study"},
            {"key": "q10_d", "text": "Lean into organic learning opportunities", "style": "unschooling"},
            {"key": "q10_e", "text": "Pivot quickly and mix what serves us", "style": "eclectic"},
        ],
    },
]

DEFAULT_QUIZ_CONFIG = {
    "quiz_key": "homeschool_style",
    "title": "What Is Your Homeschool Style?",
    "description": "Answer 10 quick questions to discover your dominant homeschool style.",
    "styles": DEFAULT_STYLE_PROFILES,
    "questions": DEFAULT_QUESTIONS,
}

_ID_RE = re.compile(r"^[a-z0-9_]+$")


def _clone(value):
    return json.loads(json.dumps(value))


def _config_path():
    return Path(__file__).resolve().parents[1] / "config" / "homeschool_style_quiz.json"


def _normalize_id(value, fallback):
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9_]+", "_", text).strip("_")
    if not text:
        text = fallback
    if not _ID_RE.match(text):
        raise ValueError(f"Invalid id '{text}'. Use lowercase letters, numbers, and underscores only.")
    return text


def _clean_text(value, field_name):
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def _normalize_style_code(value):
    raw = str(value or "").strip().lower()
    raw = re.sub(r"[^a-z0-9_]+", "_", raw).strip("_")
    if not raw:
        raise ValueError("Style code is required")
    return STYLE_CODE_ALIASES.get(raw, raw.upper())


def validate_quiz_config(raw_config):
    if not isinstance(raw_config, dict):
        raise ValueError("Quiz config must be an object")

    title = _clean_text(raw_config.get("title"), "title")
    description = _clean_text(raw_config.get("description"), "description")

    raw_styles = raw_config.get("styles")
    if not isinstance(raw_styles, dict) or not raw_styles:
        raise ValueError("styles must be a non-empty object")

    normalized_styles = {}
    for raw_style_key, raw_profile in raw_styles.items():
        style_key = _normalize_style_code(raw_style_key)
        if style_key in normalized_styles:
            raise ValueError(f"Duplicate style key '{style_key}'")
        if not isinstance(raw_profile, dict):
            raise ValueError(f"Style '{style_key}' must be an object")

        style_title = _clean_text(raw_profile.get("title"), f"styles.{style_key}.title")
        style_summary = _clean_text(raw_profile.get("summary"), f"styles.{style_key}.summary")

        strengths = raw_profile.get("strengths")
        if isinstance(strengths, str):
            strengths = [chunk.strip() for chunk in strengths.split("\n") if chunk.strip()]
        if not isinstance(strengths, list) or not strengths:
            raise ValueError(f"styles.{style_key}.strengths must be a non-empty list")

        cleaned_strengths = []
        for idx, item in enumerate(strengths, start=1):
            strength_text = str(item or "").strip()
            if not strength_text:
                raise ValueError(f"styles.{style_key}.strengths[{idx}] cannot be empty")
            cleaned_strengths.append(strength_text)

        normalized_styles[style_key] = {
            "title": style_title,
            "summary": style_summary,
            "strengths": cleaned_strengths,
        }

    for code, profile in DEFAULT_STYLE_PROFILES.items():
        if code not in normalized_styles:
            normalized_styles[code] = _clone(profile)

    raw_questions = raw_config.get("questions")
    if not isinstance(raw_questions, list) or not raw_questions:
        raise ValueError("questions must be a non-empty list")

    normalized_questions = []
    question_ids = set()

    for q_index, raw_question in enumerate(raw_questions, start=1):
        if not isinstance(raw_question, dict):
            raise ValueError(f"Question #{q_index} must be an object")

        question_id = _normalize_id(raw_question.get("id"), f"q{q_index}")
        if question_id in question_ids:
            raise ValueError(f"Duplicate question id '{question_id}'")
        question_ids.add(question_id)

        question_text = _clean_text(raw_question.get("question"), f"questions[{q_index}].question")

        raw_options = raw_question.get("options")
        if not isinstance(raw_options, list) or len(raw_options) < 2:
            raise ValueError(f"Question '{question_id}' must have at least 2 options")

        option_keys = set()
        normalized_options = []
        for o_index, raw_option in enumerate(raw_options, start=1):
            if not isinstance(raw_option, dict):
                raise ValueError(f"Question '{question_id}' option #{o_index} must be an object")

            option_text = _clean_text(raw_option.get("text"), f"questions[{q_index}].options[{o_index}].text")

            raw_styles_value = raw_option.get("styles")
            if raw_styles_value is None:
                legacy_code = _normalize_style_code(raw_option.get("style"))
                raw_styles_value = LEGACY_OPTION_STYLE_EXPANSION.get(legacy_code, [legacy_code])

            if isinstance(raw_styles_value, str):
                raw_styles_value = [raw_styles_value]
            if not isinstance(raw_styles_value, list) or not raw_styles_value:
                raise ValueError(f"Question '{question_id}' option #{o_index} must map to at least one style")

            option_styles = []
            seen_styles = set()
            for raw_style in raw_styles_value:
                option_style = _normalize_style_code(raw_style)
                if option_style not in normalized_styles:
                    raise ValueError(
                        f"Question '{question_id}' option #{o_index} uses unknown style '{option_style}'"
                    )
                if option_style in seen_styles:
                    continue
                seen_styles.add(option_style)
                option_styles.append(option_style)

            option_key = _normalize_id(raw_option.get("key"), f"{question_id}_opt{o_index}")
            if option_key in option_keys:
                raise ValueError(f"Question '{question_id}' has duplicate option key '{option_key}'")
            option_keys.add(option_key)

            normalized_options.append({
                "key": option_key,
                "text": option_text,
                "style": option_styles[0],
                "styles": option_styles,
            })

        normalized_questions.append({
            "id": question_id,
            "question": question_text,
            "options": normalized_options,
        })

    return {
        "quiz_key": "homeschool_style",
        "title": title,
        "description": description,
        "styles": normalized_styles,
        "questions": normalized_questions,
    }


def _load_default_config():
    return validate_quiz_config(_clone(DEFAULT_QUIZ_CONFIG))


def load_quiz_config():
    path = _config_path()
    if not path.exists():
        return _load_default_config()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return validate_quiz_config(raw)
    except Exception:
        return _load_default_config()


def save_quiz_config(raw_config):
    normalized = validate_quiz_config(raw_config)
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    return normalized


def reset_quiz_config():
    return save_quiz_config(_clone(DEFAULT_QUIZ_CONFIG))


def get_admin_quiz_payload():
    return load_quiz_config()


def get_public_quiz_payload():
    config = load_quiz_config()
    return {
        "quiz_key": config["quiz_key"],
        "title": config["title"],
        "description": config["description"],
        "questions": [
            {
                "id": question["id"],
                "question": question["question"],
                "options": [
                    {
                        "key": option["key"],
                        "text": option["text"],
                    }
                    for option in question["options"]
                ],
            }
            for question in config["questions"]
        ],
    }


def calculate_result(answer_map):
    config = load_quiz_config()
    style_profiles = config["styles"]
    questions = config["questions"]

    style_counts = Counter({key: 0 for key in style_profiles.keys()})

    for question in questions:
        selected = (answer_map or {}).get(question["id"])
        for option in question["options"]:
            if option["key"] == selected:
                mapped_styles = option.get("styles") or [option.get("style")]
                for style_code in mapped_styles:
                    if style_code in style_counts:
                        style_counts[style_code] += 1
                break

    sorted_styles = sorted(style_counts.items(), key=lambda item: item[1], reverse=True)
    top_style = sorted_styles[0][0]
    second_style = sorted_styles[1][0] if len(sorted_styles) > 1 else top_style

    top_profile = style_profiles[top_style]
    second_profile = style_profiles[second_style]

    result_summary = (
        f"Primary style: {top_profile['title']}. "
        f"Secondary influence: {second_profile['title']}. "
        f"{top_profile['summary']}"
    )

    return {
        "result_key": top_style,
        "result_title": top_profile["title"],
        "result_summary": result_summary,
        "strengths": top_profile.get("strengths", []),
        "score_breakdown": dict(style_counts),
    }


def is_valid_answer_payload(answer_map):
    if not isinstance(answer_map, dict):
        return False

    config = load_quiz_config()
    for question in config["questions"]:
        question_id = question["id"]
        if question_id not in answer_map:
            return False

        valid_keys = {option["key"] for option in question["options"]}
        if answer_map[question_id] not in valid_keys:
            return False

    return True
