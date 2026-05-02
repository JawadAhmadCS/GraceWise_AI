import json
import os
import re
from datetime import datetime
from pathlib import Path


SECTION_KEYS = {
    "family_profile",
    "child_profiles",
    "education_homeschool_plan",
    "special_needs_learning_support",
    "schedule_meal_planning",
    "goals_preferences",
}

YES_VALUES = {"yes", "y", "true", "1", "yeah", "yep", "sure", "ok", "okay"}
NO_VALUES = {"no", "n", "false", "0", "nope", "not"}
QUESTION_TYPES = {"text", "number", "boolean", "single_select", "multi_select"}


def _default_question_bank_path():
    base = Path(__file__).resolve().parents[1]
    return base / "config" / "onboarding_question_bank.json"


def get_question_bank_path():
    path_value = os.environ.get("ONBOARDING_QUESTION_BANK_PATH", "").strip()
    return Path(path_value) if path_value else _default_question_bank_path()


def _validate_question_bank_data(data):
    if not isinstance(data, dict):
        raise ValueError("Question bank root must be a JSON object")

    sections = data.get("sections")
    questions = data.get("questions")

    if not isinstance(sections, list):
        raise ValueError("Question bank 'sections' must be a list")
    if not isinstance(questions, list):
        raise ValueError("Question bank 'questions' must be a list")

    section_keys = set()
    for section in sections:
        if not isinstance(section, dict):
            raise ValueError("Each section must be an object")
        section_key = (section.get("key") or "").strip()
        section_title = (section.get("title") or "").strip()
        if section_key not in SECTION_KEYS:
            raise ValueError(f"Invalid section key '{section_key}' in sections")
        if not section_title:
            raise ValueError(f"Section '{section_key}' must include a non-empty title")
        if section_key in section_keys:
            raise ValueError(f"Duplicate section key: {section_key}")
        section_keys.add(section_key)

    missing_sections = SECTION_KEYS - section_keys
    if missing_sections:
        missing = ", ".join(sorted(missing_sections))
        raise ValueError(f"Missing required sections: {missing}")

    question_ids = set()
    question_fields = set()
    for q in questions:
        if not isinstance(q, dict):
            raise ValueError("Each question must be an object")

        qid = (q.get("id") or "").strip()
        if not qid:
            raise ValueError("Each question must have a non-empty id")
        if qid in question_ids:
            raise ValueError(f"Duplicate question id: {qid}")
        question_ids.add(qid)

        section = (q.get("section") or "").strip()
        if section not in SECTION_KEYS:
            raise ValueError(f"Invalid section '{section}' for question {qid}")

        field = (q.get("field") or "").strip()
        if not field:
            raise ValueError(f"Question {qid} is missing field")
        if field in question_fields:
            raise ValueError(f"Duplicate question field: {field}")
        question_fields.add(field)

        qtype = (q.get("type") or "").strip().lower()
        if qtype not in QUESTION_TYPES:
            raise ValueError(f"Invalid type '{qtype}' for question {qid}")

        prompt = (q.get("prompt") or "").strip()
        if not prompt:
            raise ValueError(f"Question {qid} is missing prompt")

        if "required" not in q:
            raise ValueError(f"Question {qid} must include required=true/false")
        if not isinstance(q.get("required"), bool):
            raise ValueError(f"Question {qid} has invalid required value")

        if qtype in {"single_select", "multi_select"}:
            options = q.get("options")
            if not isinstance(options, list) or not options:
                raise ValueError(f"Question {qid} must include non-empty options")
            for option in options:
                if isinstance(option, dict):
                    value = str(option.get("value", "")).strip()
                    label = str(option.get("label", "")).strip()
                    if not value or not label:
                        raise ValueError(f"Question {qid} has option missing value/label")
                elif not str(option).strip():
                    raise ValueError(f"Question {qid} has an empty option value")

        condition = q.get("condition")
        if condition is not None and not isinstance(condition, dict):
            raise ValueError(f"Question {qid} condition must be an object")

    return data


def load_question_bank():
    path = get_question_bank_path()

    if not path.exists():
        raise FileNotFoundError(f"Onboarding question bank not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return _validate_question_bank_data(data)


def save_question_bank(data, updated_by="system"):
    validated = _validate_question_bank_data(data)
    path = get_question_bank_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        backup_dir = path.parent / "onboarding_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        actor = re.sub(r"[^a-zA-Z0-9_.-]", "_", str(updated_by or "system"))
        backup_path = backup_dir / f"onboarding_question_bank_{stamp}_{actor}.json"
        backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        backup_path = None

    rendered = json.dumps(validated, indent=2, ensure_ascii=False) + "\n"
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(rendered, encoding="utf-8")
    temp_path.replace(path)

    return {
        "path": str(path),
        "backup_path": str(backup_path) if backup_path else None,
        "question_count": len(validated.get("questions") or []),
        "section_count": len(validated.get("sections") or []),
        "version": validated.get("version"),
    }


def list_questions(question_bank):
    return question_bank.get("questions") or []


def index_answers_by_field(answers):
    indexed = {}
    for ans in answers:
        field_key = ans.field_key
        value = ans.normalized_value
        indexed[field_key] = value
    return indexed


def _condition_matches(condition, answer_map):
    if not condition:
        return True

    field = condition.get("field")
    if not field:
        return True

    current = answer_map.get(field)

    if "equals" in condition:
        return current == condition["equals"]

    if "in" in condition and isinstance(condition["in"], list):
        return current in condition["in"]

    if condition.get("exists") is True:
        return current not in (None, "", [])

    return True


def get_applicable_questions(question_bank, answer_map):
    result = []
    for q in list_questions(question_bank):
        if _condition_matches(q.get("condition"), answer_map):
            result.append(q)
    return result


def calculate_progress(question_bank, answer_map):
    applicable = get_applicable_questions(question_bank, answer_map)
    required = [q for q in applicable if bool(q.get("required"))]

    completed_required = 0
    for q in required:
        value = answer_map.get(q["field"])
        if value not in (None, "", []):
            completed_required += 1

    percent = int((completed_required / len(required)) * 100) if required else 100

    return {
        "required_total": len(required),
        "required_completed": completed_required,
        "percent": percent,
        "is_complete": completed_required >= len(required),
    }


def get_next_question(question_bank, answer_map):
    for q in get_applicable_questions(question_bank, answer_map):
        value = answer_map.get(q["field"])
        if value in (None, "", []):
            return q
    return None


def _normalize_select_option(options, user_text):
    text = (user_text or "").strip().lower()
    if not text:
        return None

    best_value = None
    for opt in options or []:
        if isinstance(opt, dict):
            value = str(opt.get("value", "")).strip()
            label = str(opt.get("label", "")).strip()
            synonyms = [str(s).strip() for s in (opt.get("synonyms") or [])]
            candidates = [value.lower(), label.lower()] + [s.lower() for s in synonyms if s]
        else:
            value = str(opt).strip()
            candidates = [value.lower()]

        if text in candidates:
            return value

        for candidate in candidates:
            if candidate and candidate in text:
                best_value = value

    return best_value


def _normalize_boolean(user_text):
    text = (user_text or "").strip().lower()
    if text in YES_VALUES:
        return True
    if text in NO_VALUES:
        return False

    if any(token in text for token in YES_VALUES):
        return True
    if any(token in text for token in NO_VALUES):
        return False
    return None


def _normalize_number(user_text):
    match = re.search(r"-?\d+", user_text or "")
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def _normalize_multi_select(options, user_text):
    if not user_text:
        return []

    parts = re.split(r",|/|\band\b", user_text, flags=re.IGNORECASE)
    normalized = []
    for part in parts:
        value = _normalize_select_option(options, part.strip())
        if value and value not in normalized:
            normalized.append(value)

    return normalized


def extract_answer(question, user_text):
    q_type = (question.get("type") or "text").strip().lower()
    value = None
    needs_follow_up = False
    follow_up_prompt = None

    if q_type == "number":
        value = _normalize_number(user_text)
    elif q_type == "boolean":
        value = _normalize_boolean(user_text)
    elif q_type == "single_select":
        value = _normalize_select_option(question.get("options"), user_text)
    elif q_type == "multi_select":
        value = _normalize_multi_select(question.get("options"), user_text)
    else:
        value = (user_text or "").strip()

    if value in (None, "", []):
        needs_follow_up = True
        follow_up_prompt = question.get("retry_prompt") or "I want to make sure I captured that correctly. Could you share that one more time?"

    return {
        "normalized_value": value,
        "needs_follow_up": needs_follow_up,
        "follow_up_prompt": follow_up_prompt,
    }


def _extract_with_llm(question, user_text):
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None

    try:
        from langchain_openai import ChatOpenAI
    except Exception:
        return None

    model_name = os.environ.get("ONBOARDING_AI_MODEL", "gpt-4o-mini")
    llm = ChatOpenAI(
        model=model_name,
        temperature=0.1,
        api_key=api_key,
        timeout=20,
    )

    schema_hint = {
        "type": question.get("type"),
        "options": question.get("options", []),
        "required": bool(question.get("required")),
    }
    prompt = (
        "Extract a structured answer from the user's response.\n"
        "Return ONLY valid JSON in this format:\n"
        '{"normalized_value": <value|null>, "needs_follow_up": <true|false>, "follow_up_prompt": <string|null>}\n\n'
        f"Question: {question.get('prompt', '')}\n"
        f"Schema: {json.dumps(schema_hint)}\n"
        f"User answer: {user_text}\n"
    )

    try:
        response = llm.invoke(prompt)
        content = (getattr(response, "content", "") or "").strip()
        data = json.loads(content)
        if not isinstance(data, dict):
            return None
        if "normalized_value" not in data or "needs_follow_up" not in data:
            return None
        return {
            "normalized_value": data.get("normalized_value"),
            "needs_follow_up": bool(data.get("needs_follow_up")),
            "follow_up_prompt": data.get("follow_up_prompt"),
        }
    except Exception:
        return None


def extract_answer_with_ai(question, user_text):
    llm_result = _extract_with_llm(question, user_text)
    if llm_result is not None:
        return llm_result
    return extract_answer(question, user_text)


def build_question_prompt(question):
    prompt = (question.get("prompt") or "").strip()
    options = question.get("options") or []

    if options:
        rendered = []
        for opt in options:
            if isinstance(opt, dict):
                rendered.append(str(opt.get("label") or opt.get("value") or "").strip())
            else:
                rendered.append(str(opt).strip())
        rendered = [r for r in rendered if r]
        if rendered:
            prompt = f"{prompt}\nOptions: {', '.join(rendered)}"

    return prompt


def apply_answer_to_profile(profile, question, normalized_value):
    section = question["section"]
    field = question["field"]

    section_data = getattr(profile, section, None)
    if section_data is None:
        section_data = [] if section == "child_profiles" else {}

    if section == "child_profiles":
        if not isinstance(section_data, dict):
            section_data = {}
        section_data[field] = normalized_value
        setattr(profile, section, section_data)
        return

    if not isinstance(section_data, dict):
        section_data = {}

    section_data[field] = normalized_value
    setattr(profile, section, section_data)
