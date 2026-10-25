import re
import logging

logger = logging.getLogger(__name__)


def _enforce_repeater_children_required(children):
    """
    Ensure all direct content fields inside a required repeater (or repeater with min_items >= 1)
    have is_required=True and is_visible=True so that full entry data is required.
    Checkbox toggles, file/image attachments (unless already required), and fields with conditions remain optional.
    """
    if not isinstance(children, list):
        return
    for ch in children:
        if not isinstance(ch, dict):
            continue
        has_conditions = bool(ch.get("conditions"))
        ch_type = ch.get("type")
        if not has_conditions and ch_type not in ("checkbox", "file", "image"):
            if ch_type == "group":
                is_grp_req = bool(ch.get("is_required", ch.get("required", False)))
                if is_grp_req and isinstance(ch.get("children"), list):
                    _enforce_repeater_children_required(ch["children"])
            elif ch_type != "repeater":
                ch["is_required"] = True
                ch["is_visible"] = True


def generate_default_field_placeholder(node: dict) -> str:
    """
    Returns an appropriate placeholder:
    - For parent containers ('group', 'repeater'): A welcoming, descriptive section introduction.
    - For child inputs: A realistic, helpful example starting with 'e.g., ' or clear action instruction.
    """
    existing = node.get("placeholder")
    if existing and isinstance(existing, str) and existing.strip():
        return existing.strip()

    ftype = (node.get("type") or "text").lower()
    label = (node.get("label") or node.get("name") or "Field").strip()
    lbl_lower = label.lower()

    if ftype in ("group", "repeater"):
        if any(w in lbl_lower for w in ["personal", "identity", "individual"]):
            return "Please provide your primary personal and contact details."
        if any(w in lbl_lower for w in ["address", "residence", "location"]):
            return "Enter your complete residential or mailing address information."
        if any(w in lbl_lower for w in ["education", "academic", "qualification"]):
            return "List your academic qualifications and completed degrees."
        if any(w in lbl_lower for w in ["employment", "experience", "work history", "job"]):
            return "List your previous employment history and key responsibilities."
        if any(w in lbl_lower for w in ["guarantor", "reference"]):
            return "Provide personal and contact details of your guarantor or reference."
        if any(w in lbl_lower for w in ["emergency"]):
            return "Provide emergency contact details and designated contact person."
        if any(w in lbl_lower for w in ["financial", "bank", "payment", "remuneration"]):
            return "Enter your banking and remuneration details."
        return f"Please review and complete the {label} section below."

    # Specific child types
    if ftype == "email" or "email" in lbl_lower:
        return "e.g., john.smith@example.com"
    if ftype == "phone" or any(w in lbl_lower for w in ["phone", "mobile", "cell", "tel"]):
        return "e.g., +1 (555) 019-2834"
    if ftype == "date" or "date" in lbl_lower:
        if "birth" in lbl_lower or "dob" in lbl_lower:
            return "e.g., 1990-05-15"
        return "e.g., 2026-01-15"
    if ftype == "currency" or any(w in lbl_lower for w in ["salary", "amount", "fee", "cost", "price", "compensation"]):
        return "e.g., $5,000.00"
    if ftype == "number":
        if any(w in lbl_lower for w in ["zip", "postal"]):
            return "e.g., 10001"
        if any(w in lbl_lower for w in ["year"]):
            return "e.g., 2026"
        if any(w in lbl_lower for w in ["age"]):
            return "e.g., 30"
        return "e.g., 10"
    if ftype == "file":
        return f"Upload {label} document (PDF, JPG, PNG)"
    if ftype == "image":
        return f"Upload {label} image"
    if ftype == "signature":
        return f"Type or draw {label}"
    if ftype == "checkbox":
        return ""

    # Text / Textarea / Richtext / Select semantic matching
    if any(w in lbl_lower for w in ["full name", "first name", "last name", "candidate", "employee", "signatory", "manager", "director", "contact name", "verifier"]):
        return "e.g., John Smith"
    if any(w in lbl_lower for w in ["company", "organization", "employer", "client", "business", "institution"]):
        return "e.g., Acme Corporation LLC"
    if any(w in lbl_lower for w in ["street", "address line", "residence"]):
        return "e.g., 123 Main Street, Suite 400"
    if "city" in lbl_lower:
        return "e.g., New York"
    if "state" in lbl_lower or "province" in lbl_lower:
        return "e.g., NY"
    if any(w in lbl_lower for w in ["zip", "postal"]):
        return "e.g., 10001"
    if any(w in lbl_lower for w in ["title", "position", "designation", "role"]):
        return "e.g., Senior Operations Manager"
    if any(w in lbl_lower for w in ["degree"]):
        return "e.g., Bachelor of Computer Science"
    if "name" in lbl_lower:
        return "e.g., John Smith"

    return f"e.g., {label}"


def determine_field_width(node: dict) -> str:
    """
    Determines field width:
    - If explicit 'width' in ('full', 'half'), respect it.
    - If 'position' is 'left' or 'right', returns 'half'.
    - Defaults to 'full' when position is not specified or full.
    """
    raw_width = node.get("width")
    if raw_width in ("full", "half"):
        return raw_width

    position = node.get("position")
    if position in ("left", "right"):
        return "half"

    return "full"


def validate_output(data: dict, action: str = "generate"):
    """
    FormExL output validator.
    - Schema field type/key/section enforcement
    - Signature field removal
    - Missing placeholder: LOG ONLY — never dump robotic "Label: [Label]" into template
    """
    if not isinstance(data, dict):
        raise ValueError("Output must be a JSON object")

    if action == "generate":
        for key in ["schema_definition", "content_template", "base_content"]:
            if key not in data:
                raise ValueError(f"Missing required key in output: {key}")

    schema = data.get("schema_definition")
    if schema is not None and not isinstance(schema, list):
        raise ValueError("schema_definition must be a list")

    content_template = data.get("content_template", "")
    if not isinstance(content_template, str) or not content_template.strip():
        content_template = "Generated Document:\n\n"

    # ---- Remove signature fields ----
    def filter_signatures(fields_list):
        nonlocal content_template
        filtered = []
        for f in fields_list:
            if not isinstance(f, dict):
                filtered.append(f)
                continue
            name  = f.get("name",  "").lower()
            label = f.get("label", "").lower()
            ftype = f.get("type",  "").lower()
            
            # Combine signature and metadata keywords to strip them completely
            sig_keywords = {"signature", "signatory", "signed_by", "signed by", "signing_date", "signing date", "printed_name", "printed name"}
            is_sig = (
                ftype == "signature"
                or any(kw in name  for kw in sig_keywords)
                or any(kw in label for kw in sig_keywords)
                or name in {"creator_signing_option", "recipient_signature_required"}
            )
            
            if is_sig:
                lbl = f.get("label", name)
                content_template = re.sub(rf'\[{re.escape(lbl)}\]', "", content_template)
                content_template = re.sub(rf'\[{re.escape(name)}\]', "", content_template)
                content_template = re.sub(r'\n{3,}', '\n\n', content_template)
                logger.info(f"[Validator] Removed signature/metadata field completely: {lbl}")
                continue # DELETES the field from schema
                
            if f.get("children") and isinstance(f["children"], list):
                f["children"] = filter_signatures(f["children"])
            if f.get("options") and isinstance(f["options"], list):
                for opt in f["options"]:
                    if isinstance(opt, dict) and isinstance(opt.get("children"), list):
                        opt["children"] = filter_signatures(opt["children"])
            filtered.append(f)
        return filtered

    if schema is not None:
        schema = filter_signatures(schema)
        data["schema_definition"] = schema

    # ---- Field-level validation ----
    SUPPORTED_TYPES = {
        "text", "textarea", "email", "phone", "date",
        "number", "currency", "checkbox", "select",
        "richtext", "group", "repeater", "image", "file"
    }
    APPROVED_KEYS = {
        "name", "label", "type", "placeholder", "width",
        "section", "position", "options", "children",
        "conditions", "order", "repeatable", "min_items", "max_items",
        "is_required", "is_visible"
    }
    APPROVED_SECTIONS = {"IDENTITY", "PARTIES", "SCOPE", "FINANCIALS", "EXECUTION"}
    seen_fields = set()

    def validate_field(field):
        if not isinstance(field, dict):
            raise ValueError("Each schema item must be a JSON object")

        # Remove unapproved keys
        for k in [k for k in list(field.keys()) if k not in APPROVED_KEYS]:
            del field[k]

        # Normalise name
        name = field.get("name") or re.sub(r'[^a-z0-9_]', '_', field.get("label", "field").lower())
        name = re.sub(r'[^a-z0-9_]', '_', name.lower())
        base, counter = name, 1
        while name in seen_fields:
            name = f"{base}_{counter}"
            counter += 1
        field["name"] = name
        seen_fields.add(name)

        # Standardize is_required: remove legacy 'required' key
        req_val = field.pop("required", None)
        if "is_required" in field:
            is_req = bool(field["is_required"])
        elif req_val is not None:
            is_req = bool(req_val)
        else:
            is_req = False
        field["is_required"] = is_req

        # Standardize placeholder and width
        field["placeholder"] = generate_default_field_placeholder(field)
        field["width"] = determine_field_width(field)
        if not field.get("position"):
            field["position"] = field["width"]

        # Set initial visibility based on conditions if not already set
        if "is_visible" not in field:
            field["is_visible"] = not bool(field.get("conditions"))

        # Fix invalid type
        if field.get("type") not in SUPPORTED_TYPES:
            logger.warning(f"[Validator] Invalid type '{field.get('type')}' on field '{name}' — defaulting to 'text'")
            field["type"] = "text"

        # Auto-correct AI misclassifications
        f_type = field.get("type")
        lbl_lower = field.get("label", "").lower()
        if f_type in ("text", "textarea"):
            if any(w in lbl_lower for w in ["logo", "photo", "picture", "image"]):
                field["type"] = "image"
            elif any(w in lbl_lower for w in ["file", "attachment", "document upload"]):
                field["type"] = "file"

        # Fix invalid section
        if field.get("section") and field["section"] not in APPROVED_SECTIONS:
            logger.warning(f"[Validator] Invalid section '{field['section']}' on field '{name}' — removed")
            del field["section"]

        # Fix invalid conditions format
        if "conditions" in field and not isinstance(field["conditions"], (list, dict)):
            del field["conditions"]

        # Group/repeater: children must exist
        if field.get("type") in ("group", "repeater"):
            if not isinstance(field.get("children"), list):
                field["children"] = []
            for child in field["children"]:
                validate_field(child)

            if field.get("type") == "repeater":
                min_items = field.get("min_items")
                has_min = False
                if min_items is not None:
                    try:
                        if int(min_items) >= 1:
                            has_min = True
                    except (ValueError, TypeError):
                        pass
                elif field.get("is_required"):
                    field["min_items"] = 1
                    has_min = True

                if has_min:
                    field["is_required"] = True
                    _enforce_repeater_children_required(field["children"])

        # Select option children
        if field.get("options") and isinstance(field["options"], list):
            for opt in field["options"]:
                if isinstance(opt, dict) and isinstance(opt.get("children"), list):
                    for child in opt["children"]:
                        validate_field(child)

    if schema is not None:
        for field in schema:
            validate_field(field)

    # ---- Missing placeholder: LOG ONLY — do NOT append robotic dump ----
    # Rationale: service.py quality-checker loop already handles missing
    # placeholders by retrying the model. Appending "Label: [Label]" here
    # would undo that work and reintroduce the exact robotic pattern we ban.
    if schema is not None and content_template:
        def check_missing(fields_list):
            for field in fields_list:
                ftype = field.get("type", "")
                if ftype in ("group", "repeater"):
                    check_missing(field.get("children", []))
                    continue
                if field.get("options") and isinstance(field["options"], list):
                    for opt in field["options"]:
                        if isinstance(opt, dict) and isinstance(opt.get("children"), list):
                            check_missing(opt["children"])
                label = field.get("label", field.get("name", ""))
                name  = field.get("name", "")
                if f"[{label}]" not in content_template and f"[{name}]" not in content_template:
                    logger.warning(
                        f"[Validator] Placeholder missing in template for field '{name}' "
                        f"(label='{label}'). No auto-insert — quality checker should have caught this."
                    )
        check_missing(schema)

    data["content_template"] = content_template.strip()

    base_content = data.get("base_content")
    if base_content is not None and not isinstance(base_content, dict):
        raise ValueError("base_content must be a JSON object")
    elif isinstance(base_content, dict):
        base_content["required_fields"] = []

    return data
