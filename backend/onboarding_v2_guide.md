# Onboarding V2 Question Bank Guide

Use `backend/config/onboarding_question_bank.json` as the source of truth.

## Recommended handoff format

Send questions as JSON with this structure:

```json
{
  "version": "2026-05-01",
  "sections": [
    { "key": "family_profile", "title": "Family Profile" }
  ],
  "questions": [
    {
      "id": "unique_question_id",
      "section": "family_profile",
      "field": "state",
      "type": "text",
      "required": true,
      "prompt": "Which state are you homeschooling in?",
      "retry_prompt": "Could you share your state one more time?",
      "options": [],
      "condition": {
        "field": "support_needed",
        "equals": true
      }
    }
  ]
}
```

## Supported `type` values

- `text`
- `number`
- `boolean`
- `single_select`
- `multi_select`

## Option format for select questions

```json
"options": [
  { "value": "classical", "label": "Classical", "synonyms": ["classical method"] },
  { "value": "eclectic", "label": "Eclectic" }
]
```

## Conditional logic (follow-up questions)

The question is asked only if condition matches:

```json
"condition": { "field": "support_needed", "equals": true }
```

or:

```json
"condition": { "field": "homeschool_style", "in": ["eclectic", "not_sure"] }
```

or:

```json
"condition": { "field": "main_goal", "exists": true }
```

## Best practice for writing prompts

- Keep one question per prompt.
- Keep prompts parent-friendly and natural.
- Use `retry_prompt` for graceful follow-up when answer is unclear.
- Keep IDs stable (do not rename IDs after launch unless you migrate data).

## How answers are saved

Each question maps to:

- `section` (profile section)
- `field` (key inside that section)

The system stores:

- raw answer text
- normalized value
- progress
- section data for later editing
