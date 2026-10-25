import json
import logging
import re

from django.conf import settings
from openai import OpenAI

from ..prompts.unified_prompt import (
    SCHEMA_SYSTEM_PROMPT,
    SCHEMA_FEW_SHOT_USER,
    SCHEMA_FEW_SHOT_ASSISTANT,
    TEMPLATE_SYSTEM_PROMPT,
    REVIEW_SYSTEM_PROMPT,
)
from .validators import validate_output
from .package_validator import validate_package

logger = logging.getLogger(__name__)

# UTILITY FUNCTIONS

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def detect_family(doc_type: str, schema: list = None) -> str:
    """
    Keyword-based family detector, with schema-fallback support.
    FORM/LETTER/POLICY checked before CONTRACT to avoid false CONTRACT fallback.
    """
    dt = doc_type.lower()
    
    # Check doc_type first
    if any(w in dt for w in ["form", "application", "intake", "registration", "survey", "onboarding", "invoice", "receipt", "bill"]):
        return "FORM"
    if any(w in dt for w in ["letter"]):
        return "LETTER"
    if any(w in dt for w in ["policy", "code of conduct"]):
        return "POLICY"
    if any(w in dt for w in ["proposal"]):
        return "PROPOSAL"
    if any(w in dt for w in ["report"]):
        return "REPORT"
    if any(w in dt for w in ["manual", "handbook", "sop"]):
        return "MANUAL"
    if any(w in dt for w in ["notice"]):
        return "NOTICE"
    if any(w in dt for w in ["agreement", "contract", "nda", "mou", "sla", "deed", "partnership"]):
        return "CONTRACT"

    # If doc_type doesn't match and schema is provided, inspect schema fields
    if schema:
        field_names = [str(f.get("name", "")).lower() for f in schema]
        
        # Invoice/Form indicators
        if any("invoice" in n or "bill_to" in n or "due_date" in n for n in field_names):
            return "FORM"
            
        # Contract indicators
        if any("governing_law" in n or "dispute_resolution" in n or "liability_cap" in n or "indemnification" in n for n in field_names):
            return "CONTRACT"
            
        # Proposal indicators
        if any("deliverables" in n or "project_scope" in n or "milestones" in n for n in field_names):
            return "PROPOSAL"

    return "REPORT"


def extract_placeholders(schema: list) -> list:
    placeholders = []
    for field in schema or []:
        if not isinstance(field, dict):
            continue
        ftype = field.get("type", "")
        if ftype in ("group", "repeater"):
            children = field.get("children")
            if isinstance(children, list):
                placeholders.extend(extract_placeholders(children))
        else:
            label = field.get("label") or field.get("name")
            if label:
                placeholders.append(label)
    return placeholders


def find_missing_placeholders(template: str, placeholders: list) -> list:
    found_brackets = re.findall(r"\[([^\[\]]+)\]", template)
    found_normalized = {normalize(b) for b in found_brackets}
    return [p for p in placeholders if normalize(p) not in found_normalized]


def extract_doc_type_from_description(description: str) -> str:
    """
    Extracts the document type from user input.
    The text preceding any JSON payload is considered the doc_type.
    """
    doc_type = description
    for prefix in ["create ", "build ", "generate ", "make ", "draft ",
                    "write ", "creat ", "review ", "fix "]:
        if description.lower().startswith(prefix):
            doc_type = description[len(prefix):].strip()
            break
    # Strip out the JSON portion from the doc_type string
    bracket_idx = doc_type.find('[')
    brace_idx = doc_type.find('{')
    cut = None
    if bracket_idx != -1 and brace_idx != -1:
        cut = min(bracket_idx, brace_idx)
    elif bracket_idx != -1:
        cut = bracket_idx
    elif brace_idx != -1:
        cut = brace_idx
    if cut is not None and cut > 0:
        doc_type = doc_type[:cut].strip().rstrip(',').strip()
    return doc_type if doc_type else "Custom Document"


def extract_json_from_description(description: str):
    """
    Extracts a JSON payload from the user input.
    Handles both Array `[...]` and Object `{...}` structures.
    Rejects short or false-positive strings.
    
    Returns:
        tuple: (json_string, parsed_json) or (None, None) if extraction fails.
    """
    candidates = []

    # Try array [...]
    start = description.find('[')
    end = description.rfind(']')
    if start != -1 and end != -1 and end > start:
        s = description[start:end + 1]
        if '{' in s and len(s) > 30:
            candidates.append(s)

    # Try object {...}
    start = description.find('{')
    end = description.rfind('}')
    if start != -1 and end != -1 and end > start:
        s = description[start:end + 1]
        if len(s) > 30:
            candidates.append(s)
            
    # Try user forgot outer brackets: starts with { ends with ] or vice versa
    stripped = description.strip()
    if stripped.startswith('{') and stripped.endswith(']'):
        candidates.append('[' + stripped)
    elif stripped.startswith('[') and stripped.endswith('}'):
        candidates.append(stripped + ']')
    elif stripped.startswith('{') and stripped.endswith('}'):
        candidates.append('[' + stripped + ']')
        
    # Also add the raw text as a candidate if it looks like JSON at all
    if '{' in stripped and '}' in stripped:
        candidates.append(stripped)

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            # schema_definition array or object wrapping it
            if isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], dict):
                return candidate, parsed
            if isinstance(parsed, dict) and "schema_definition" in parsed:
                return candidate, parsed["schema_definition"]
        except json.JSONDecodeError:
            # Broken JSON — still return the string for review mode
            return candidate, None

    return None, None



# QUALITY CHECKERS


ROBOTIC_PATTERNS = [
    (r"\bThe\s+[A-Za-z' ]{2,40}\s+(is|are|was|were|will be)\s+\[",
     "The X is/will be [Placeholder]"),
    (r"\b(is|are)\s+(recorded|noted|captured|categorized|designated|listed|registered)\s+as\s+\[",
     "X is recorded/categorized as [Placeholder]"),
    (r"\b[A-Za-z][A-Za-z ]{2,30}:\s*\[",
     "Label: [Placeholder] pattern"),
    (r"(?m)^\s*[-*•]\s*\[",
     "Bullet list of placeholders"),
    (r"\bholds?\s+a[n]?\s+[a-z ]+\s+as\s+\[",
     "X holds a role as [Placeholder]"),
]


def detect_robotic_patterns(template: str) -> list:
    issues = []
    for pattern, desc in ROBOTIC_PATTERNS:
        for match in re.finditer(pattern, template):
            s = max(0, match.start() - 40)
            e = min(len(template), match.end() + 40)
            snippet = template[s:e].replace("\n", " ").strip()
            issues.append((desc, snippet))
    return issues


def check_heading_format(template: str, family: str) -> list:
    issues = []
    if family == "FORM" and re.search(r"Section Title\s*:", template, re.IGNORECASE):
        issues.append("FORM template contains banned 'Section Title:' prefix")
    if family == "LETTER" and re.search(r"^Article\s+[IVXLC]+\s*:", template, re.MULTILINE):
        issues.append("LETTER template contains banned Article headers")
    return issues


def check_bare_placeholders(template: str, schema: list) -> list:
    issues = []
    # fields that MUST be embedded in sentences (cannot be bare on their own line)
    embedded_types = {"text", "textarea", "email", "phone", "number", "currency", "date", "file"}
    embedded_labels = [f["label"] for f in schema if f.get("type") in embedded_types]
    
    for label in embedded_labels:
        esc = re.escape(label)
        for line in template.split("\n"):
            if re.search(rf"\[{esc}\]", line):
                if re.match(rf"^\s*\[{esc}\][\.\s]*$", line):
                    issues.append(f"Field [{label}] is bare/isolated on its own line — must be embedded in a sentence")
    return issues


def check_richtext_handling(template: str, schema: list) -> list:
    issues = []
    richtext_labels = [f["label"] for f in schema if f.get("type") == "richtext"]
    verbs = r"(is|are|was|were|provides|outlines|covers|describes|explains|details|contains)"
    for label in richtext_labels:
        esc = re.escape(label)
        if re.search(rf"\[{esc}\]\s+{verbs}\b|\bThe\s+\[{esc}\]", template, re.IGNORECASE):
            issues.append(f"Richtext [{label}] wrapped in descriptive sentence — should stand alone on its own line")
    return issues


def check_file_image_handling(template: str, schema: list) -> list:
    issues = []
    file_labels  = [f["label"] for f in schema if f.get("type") == "file"]
    image_labels = [f["label"] for f in schema if f.get("type") == "image"]

    for label in file_labels:
        esc = re.escape(label)
        for line in template.split("\n"):
            if re.search(rf"\[{esc}\]", line):
                if re.match(rf"^\[{esc}\][\.\s]*$", line.strip()):
                    issues.append(f"File [{label}] is bare/isolated — must be embedded in a sentence")
                break

    verbs = r"(symboli[sz]es|represents|reflects|serves as|is a testament|signifies|embodies)"
    for label in image_labels:
        esc = re.escape(label)
        if re.search(rf"\[{esc}\][^.\n]*{verbs}|{verbs}[^.\n]*\[{esc}\]", template, re.IGNORECASE):
            issues.append(f"Image [{label}] wrapped in marketing prose — must stand alone as header")
    return issues


def check_family_boilerplate_leak(template: str, family: str) -> list:
    if family == "CONTRACT":
        return []
    issues = []
    banned = [
        r"Representations?\s+and\s+Warranties",
        r"Limitation\s+of\s+Liability",
        r"Indemnification",
        r"Dispute\s+Resolution\s+and\s+Governing\s+Law",
        r"Entire\s+Agreement\s+Clause",
    ]
    for pattern in banned:
        if re.search(pattern, template, re.IGNORECASE):
            issues.append(f"CONTRACT-only boilerplate '{pattern}' found in {family} document")
    return issues


def check_checkbox_handling(template: str, schema: list) -> list:
    issues = []
    checkbox_labels = [f["label"] for f in schema if f.get("type") == "checkbox"]
    for label in checkbox_labels:
        esc = re.escape(label)
        count = len(re.findall(rf"\[{esc}\]", template))
        if count > 1:
            issues.append(f"Checkbox [{label}] appears {count} times — must appear exactly once")
        dump = rf"^\s*{esc}\s*:\s*\[{esc}\]\s*$"
        if re.search(dump, template, re.IGNORECASE | re.MULTILINE):
            issues.append(f"Checkbox [{label}] written as 'Label: [Placeholder]' dump")
    consecutive = r"(?:^[A-Za-z][A-Za-z ]{2,40}:\s*\[[^\[\]]+\]\s*\n){2,}"
    if re.search(consecutive, template, re.MULTILINE):
        issues.append("2+ consecutive 'Label: [Placeholder]' lines detected — banned placeholder dump")
    return issues


def check_group_field_handling(template: str, schema: list) -> list:
    issues = []
    def walk(fields):
        for f in fields:
            if f.get("type") == "group":
                esc = re.escape(f["label"])
                if re.search(rf"\[{esc}\]", template):
                    issues.append(f"Group container [{f['label']}] appears as placeholder — only children should be bracketed")
                walk(f.get("children", []))
    walk(schema)
    return issues


def check_repeater_example_style(template: str, schema: list) -> list:
    issues = []
    phrases = ["such as", "for instance", "including those named", "like", "for example", "e.g."]
    child_labels = []
    for f in schema:
        if f.get("type") == "repeater":
            for child in f.get("children", []):
                child_labels.append(child["label"])
    for label in child_labels:
        esc = re.escape(label)
        for phrase in phrases:
            p_esc = re.escape(phrase)
            if re.search(rf"{p_esc}\s*,?\s*\[{esc}\]", template, re.IGNORECASE):
                issues.append(f"Repeater [{label}] introduced with example phrase ('{phrase}') — must be a definitive statement")
                break
    return issues


def check_select_option_hallucination(template: str, schema: list) -> list:
    issues = []
    select_fields = [f for f in schema if f.get("type") == "select" and f.get("options")]
    for f in select_fields:
        label = f["label"]
        valid = {normalize(o["value"]) for o in f["options"]}
        esc = re.escape(label)
        match = re.search(rf"\[{esc}\][^.\n]{{0,200}}|.{{0,100}}\[{esc}\]", template, re.IGNORECASE)
        if not match:
            continue
        window = match.group(0)
        if re.search(r"(such as|including|options? (?:include|are))", window, re.IGNORECASE):
            em = re.search(r"(?:such as|including|options? (?:include|are))\s+([A-Za-z, /&-]+?)(?:\.|$)", window, re.IGNORECASE)
            if em:
                for c in re.split(r",|\band\b|\bor\b", em.group(1)):
                    c_clean = normalize(c)
                    if c_clean and len(c_clean) > 2 and c_clean not in valid and c_clean not in normalize(label):
                        issues.append(f"Select [{label}] mentions hallucinated option '{c.strip()}'")
    return issues



# AUTO-REPAIR FALLBACK


def auto_fix_checkbox_dump_block(template: str, schema: list) -> str:
    """
    Last-resort repair: remove stacked 'Label: [Placeholder]' dump blocks
    (typically from checkbox fields) and replace with a single natural sentence.
    """
    checkbox_fields = [f for f in schema if f.get("type") == "checkbox"]
    if not checkbox_fields:
        return template

    lines = template.split("\n")
    dump_indices = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        m = re.match(r"^([A-Za-z][A-Za-z ]{2,40}):\s*\[([^\[\]]+)\]\s*$", stripped)
        if m and normalize(m.group(1)) == normalize(m.group(2)):
            dump_indices.append(i)

    if not dump_indices:
        return template

    cleaned_lines = [line for i, line in enumerate(lines) if i not in dump_indices]
    cleaned = "\n".join(cleaned_lines).rstrip()

    remaining = [
        f["label"] for f in checkbox_fields
        if f"[{f['label']}]" not in cleaned
    ]
    if remaining:
        if len(remaining) == 1:
            sentence = f"This engagement additionally incorporates [{remaining[0]}] as an applicable provision where relevant."
        else:
            parts = ", ".join(f"[{c}]" for c in remaining[:-1])
            sentence = f"This engagement additionally incorporates {parts}, and [{remaining[-1]}] as applicable provisions where relevant."
        cleaned = cleaned + "\n\n" + sentence

    return cleaned



# DJANGO SERVICE CLASS


class OpenAIDocumentGeneratorService:

    def __init__(self):
        self.api_key = getattr(settings, "OPENAI_API_KEY", None)
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is missing in Django settings")
        self.client = OpenAI(api_key=self.api_key)


    # CALL 1 — Schema Generation


    def call_schema(self, document_type: str, max_retries: int = 3) -> dict:
        messages = [
            {"role": "system",    "content": SCHEMA_SYSTEM_PROMPT},
            {"role": "user",      "content": SCHEMA_FEW_SHOT_USER},
            {"role": "assistant", "content": SCHEMA_FEW_SHOT_ASSISTANT},
            {"role": "user",      "content": document_type},
        ]
        for attempt in range(1, max_retries + 1):
            try:
                resp = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    temperature=0.2,
                    max_tokens=3000,
                    response_format={"type": "json_object"},
                )
                result = json.loads(resp.choices[0].message.content)
                missing = [k for k in ["schema_definition", "base_content"] if k not in result]
                if missing:
                    raise ValueError(f"Missing keys: {missing}")
                logger.info(f"[Schema OK] Fields: {len(result['schema_definition'])}")
                return result
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"[Schema] Attempt {attempt} failed: {e}")
                if attempt == max_retries:
                    raise Exception(f"Schema generation failed: {e}")


    # CALL 2 — Template Generation + Quality Checker Loop


    def call_template(self, document_type: str, schema: list, max_retries: int = 4) -> str:
        placeholders = extract_placeholders(schema)
        placeholder_block = "\n".join([f"  - [{p}]" for p in placeholders])
        family = detect_family(document_type, schema)

        user_message = (
            f"Document Type: {document_type}\n"
            f"Document Family: {family}\n\n"
            f"REQUIRED PLACEHOLDERS — Every single one MUST appear in your template exactly as listed:\n"
            f"{placeholder_block}\n\n"
            f"Full Schema:\n{json.dumps(schema, indent=2)}\n\n"
            f"Write the complete content_template now. "
            f"Apply the Robotic Sentence Test to every sentence before finalizing."
        )

        messages = [
            {"role": "system", "content": TEMPLATE_SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ]

        template = ""

        for attempt in range(1, max_retries + 1):
            try:
                resp = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    temperature=0.4,
                    max_tokens=5000,
                    response_format={"type": "json_object"},
                    frequency_penalty=0.3,
                    presence_penalty=0.15,
                )
                result = json.loads(resp.choices[0].message.content)
                if "content_template" not in result:
                    raise ValueError("Missing content_template key")
                template = result["content_template"]

                # ---- Quality Checks ----
                problems = []

                mp = find_missing_placeholders(template, placeholders)
                if mp:
                    problems.append(f"MISSING PLACEHOLDERS ({len(mp)}): " + ", ".join(f"[{p}]" for p in mp))

                rp = detect_robotic_patterns(template)
                if rp:
                    ex = "; ".join(f'{d} -> "...{s}..."' for d, s in rp[:5])
                    problems.append(f"ROBOTIC SENTENCES ({len(rp)}): {ex}")

                hf = check_heading_format(template, family)
                if hf:
                    problems.append("HEADING FORMAT: " + "; ".join(hf))

                rt = check_richtext_handling(template, schema)
                if rt:
                    problems.append("RICHTEXT ISSUES: " + "; ".join(rt))

                fi = check_file_image_handling(template, schema)
                if fi:
                    problems.append("FILE/IMAGE ISSUES: " + "; ".join(fi))

                bp = check_bare_placeholders(template, schema)
                if bp:
                    problems.append("BARE PLACEHOLDER ISSUES: " + "; ".join(bp))

                bl = check_family_boilerplate_leak(template, family)
                if bl:
                    problems.append("BOILERPLATE LEAK: " + "; ".join(bl))

                cb = check_checkbox_handling(template, schema)
                if cb:
                    problems.append("CHECKBOX ISSUES: " + "; ".join(cb))

                gf = check_group_field_handling(template, schema)
                if gf:
                    problems.append("GROUP FIELD ISSUES: " + "; ".join(gf))

                re_issues = check_repeater_example_style(template, schema)
                if re_issues:
                    problems.append("REPEATER EXAMPLE-STYLE: " + "; ".join(re_issues))

                sh = check_select_option_hallucination(template, schema)
                if sh:
                    problems.append("SELECT HALLUCINATION: " + "; ".join(sh))

                if not problems:
                    logger.info(
                        f"[Template OK] {len(template)} chars, "
                        f"all {len(placeholders)} placeholders, 0 issues"
                    )
                    return template

                logger.warning(f"[Template] Attempt {attempt}: {len(problems)} problem(s)")
                for p in problems:
                    logger.warning(f"    - {p}")

                fix_instructions = "\n\n".join(problems)
                messages.append({"role": "assistant", "content": json.dumps(result)})
                messages.append({
                    "role": "user",
                    "content": (
                        f"Your template failed the automated quality check:\n\n"
                        f"{fix_instructions}\n\n"
                        f"Rewrite the COMPLETE content_template fixing ALL issues above. "
                        f"Return the full corrected template."
                    ),
                })

            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"[Template] Attempt {attempt} parse error: {e}")
                if attempt == max_retries:
                    raise Exception(f"Template generation failed: {e}")

        # ---- Last-resort auto-repair ----
        logger.warning("[Template] Max retries reached. Running auto-repair fallback...")
        template = auto_fix_checkbox_dump_block(template, schema)
        logger.warning("[Template] Auto-repair done. Returning repaired version.")
        return template


    # CALL 3 — Review / Fix broken JSON


    def call_review(self, raw_input: str) -> dict:
        messages = [
            {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Fix the following broken JSON schema or template structure "
                    f"and return a valid FormExL schema_definition array:\n\n{raw_input}"
                ),
            },
        ]
        try:
            resp = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.2,
                max_tokens=5000,
                response_format={"type": "json_object"},
            )
            return json.loads(resp.choices[0].message.content)
        except Exception as e:
            logger.error(f"[Review] Failed: {e}")
            raise Exception(f"Review failed: {e}")

    
    # MAIN ENTRY POINT
    

    def generate_document(self, description: str) -> dict:
        """
        Main routing logic:
        1. JSON detected + broken/review intent → Call 3 (Review)
        2. JSON detected + "make template"       → Call 2 only
        3. JSON detected + "make base content"   → Programmatic generation
        4. No JSON → Call 1 + Call 2 (normal flow)
        """

        doc_type = extract_doc_type_from_description(description)
        json_string, extracted_json = extract_json_from_description(description)
        text_intent = description.lower()

        # ROUTE DETECTION
        # "valid", "check", "verify" are CONFIRMATION words (user saying JSON is OK)
        # Only explicit repair/fix words should trigger review mode
        want_review = any(
            w in text_intent
            for w in ["review", "fix", "repair", "correct", "wrong", "broken", "error", "invalid"]
        )

        # Extra guard: if user says "is valid" / "this is valid" / "json is valid"
        # they are CONFIRMING the JSON — never route to review (unless it's actually broken)
        is_confirming_valid = bool(re.search(
            r"\b(this\s+)?(json\s+)?(is|looks?)\s+(valid|correct|fine|ok|okay|good)\b",
            text_intent
        ))

        # ---- ROUTE A: Broken JSON or explicit review request ----
        needs_review = extracted_json is None or (want_review and not is_confirming_valid)
        
        if json_string and needs_review:
            logger.info("Routing to Call 3 (Review) — broken JSON or review intent.")
            # Pass full description so AI sees everything, avoiding data loss if string was cut wrong
            package = self.call_review(description)

            if "schema_definition" not in package:
                raise ValueError("Reviewer did not return schema_definition")

            validate_output(package, action="review")
            validation_result = validate_package(package)
            final_package = validation_result["corrected_package"]

            # Strip hallucinated template/base_content the reviewer may have added
            final_package.pop("content_template", None)
            final_package.pop("base_content", None)
            final_package["validation_issues"] = validation_result["issues"]

            want_template     = "template" in text_intent
            want_base_content = "base content" in text_intent or "base_content" in text_intent

            if want_template or want_base_content:
                schema = final_package["schema_definition"]
                
                if want_template:
                    logger.info(f"Generating template after review fix with doc_type='{doc_type}'.")
                    final_package["content_template"] = self.call_template(doc_type, schema)
                
                if want_base_content:
                    logger.info("Generating base_content after review fix.")
                    final_package["base_content"] = {
                        "document_type": doc_type,
                        "signature_required": True,
                        "required_fields": [],
                    }
                
                if want_template:
                    validate_output(final_package, action="generate_custom")
                    vr = validate_package(final_package)
                    final_package["content_template"] = vr["corrected_package"]["content_template"]
                
                return {
                    "action": "generate_custom",
                    "change_analysis": ["Fixed schema syntax errors and generated requested content."],
                    "package": final_package,
                }
            return {
                "action": "review",
                "change_analysis": ["Fixed syntax errors and validated schema structure."],
                "package": final_package,
            }

        # ---- ROUTE B: Valid JSON provided ----
        if extracted_json is not None:
            schema = extracted_json
            want_template     = "template" in text_intent
            want_base_content = "base content" in text_intent or "base_content" in text_intent

            # Default: if user just pastes JSON without saying what they want → generate template
            if not want_template and not want_base_content:
                want_template = True
            package = {
                "schema_definition": schema
            }
            if want_template:
                logger.info(f"Routing to Call 2 (Template) with doc_type='{doc_type}'.")
                # doc_type is passed so detect_family() works correctly
                package["content_template"] = self.call_template(doc_type, schema)

            if want_base_content:
                logger.info("Generating base_content programmatically from schema.")
                package["base_content"] = {
                    "document_type": doc_type,
                    "signature_required": True,
                    "required_fields": [],
                }

            if want_template:
                temp_pkg = {
                    "schema_definition": schema,
                    "content_template": package.get("content_template", ""),
                    "base_content": package.get("base_content", {}),
                }
                validate_output(temp_pkg, action="generate")
                vr = validate_package(temp_pkg)
                package["content_template"] = vr["corrected_package"]["content_template"]

            return {
                "action": "generate_custom",
                "change_analysis": [],
                "package": package,
            }

        # ---- ROUTE C: Normal flow — plain text description ----
        logger.info(f"Normal generation flow for: {doc_type}")

        schema_result = self.call_schema(doc_type)
        schema       = schema_result["schema_definition"]
        base_content = schema_result["base_content"]
        action        = schema_result.get("action", "generate")
        change_analysis = schema_result.get("change_analysis", [])

        template = self.call_template(doc_type, schema)

        package = {
            "schema_definition": schema,
            "content_template":  template,
            "base_content":      base_content,
        }

        validate_output(package, action=action)
        validation_result = validate_package(package)
        final_package = validation_result["corrected_package"]
        final_package["validation_issues"] = validation_result["issues"]

        return {
            "action": action,
            "change_analysis": change_analysis,
            "package": final_package,
        }
