import re
from html import escape, unescape

from rest_framework import serializers

from .models import (
    CompanyBranding,
    CreditWallet,
    DocumentSchema,
    DocumentRequest,
    DocumentStructure,
    DocumentTemplate,
    DocumentType,
    GeneratedDocument,
    HelpArticle,
    PaymentMethod,
    TemplateCategory,
)


SAFE_INLINE_HTML_TAGS = {
    "b", "strong", "i", "em", "u", "s", "strike", "del",
    "span", "mark", "sub", "sup", "code", "pre", "small",
    "a", "img", "br"
}

SAFE_BLOCK_HTML_TAGS = {
    "p", "div", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "table", "thead", "tbody", "tfoot", "tr", "th", "td",
    "hr"
}

SAFE_HTML_TAGS = SAFE_INLINE_HTML_TAGS | SAFE_BLOCK_HTML_TAGS

TAG_REGEX = re.compile(r"(</?[a-zA-Z][a-zA-Z0-9]*(?:\s+[^<>]*)?>)")


def sanitize_rich_text_html(html_str):
    if not html_str:
        return ""
    clean = re.sub(
        r"<\s*(script|iframe|object|embed|style|meta|link|base)[^>]*>.*?</\s*\1\s*>",
        "",
        html_str,
        flags=re.IGNORECASE | re.DOTALL,
    )
    clean = re.sub(
        r"<\s*(script|iframe|object|embed|style|meta|link|base)[^>]*>",
        "",
        clean,
        flags=re.IGNORECASE,
    )
    clean = re.sub(r"(?i)\bon\w+\s*=\s*['\"][^'\"]*['\"]", "", clean)
    clean = re.sub(r"(?i)\bon\w+\s*=\s*[^\s>]+", "", clean)
    clean = re.sub(r"(?i)javascript\s*:", "", clean)
    return clean


def escape_preserving_safe_html(text):
    if not text:
        return ""
    clean = sanitize_rich_text_html(text)
    parts = TAG_REGEX.split(clean)
    out = []
    for part in parts:
        m = re.match(r"^<(/)?([a-zA-Z][a-zA-Z0-9]*)(\s+[^<>]*)?>$", part)
        if m:
            tag_name = m.group(2).lower()
            if tag_name in SAFE_HTML_TAGS:
                is_close = bool(m.group(1))
                attrs = m.group(3) or ""
                if is_close:
                    out.append(f"</{tag_name}>")
                else:
                    out.append(f"<{tag_name}{attrs}>")
            else:
                out.append(escape(part))
        else:
            out.append(escape(part))
    return "".join(out)


def render_text_as_html(value, compact=False):
    text = (value or "").strip()
    if not text:
        return ""

    if compact:
        normalized = text
        normalized = re.sub(r"<\s*hr\s*/?\s*>", "\n\n", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"<\s*br\s*/?\s*>", "\n", normalized, flags=re.IGNORECASE)
        normalized = re.sub(
            r"<\s*/\s*(p|div|h1|h2|h3|h4|h5|h6|tr|ul|ol|table|thead|tbody)\s*>",
            "\n",
            normalized,
            flags=re.IGNORECASE,
        )
        normalized = re.sub(r"<\s*li[^>]*>", "- ", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"<\s*(td|th)[^>]*>", " ", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"<[^>]+>", "", normalized)
        normalized = unescape(normalized)

        blocks = []
        for line in normalized.splitlines():
            clean = line.strip()
            if not clean:
                blocks.append("<p></p>")
                continue
            if re.match(r"^[-=_]{3,}$", clean):
                blocks.append("<p></p>")
                continue
            blocks.append(f"<p>{escape_preserving_safe_html(clean)}</p>")
        return "\n".join(blocks)

    if re.search(r"<\s*(h[1-6]|p|div|ul|ol|li|table|tr|td|th|br|hr|img|blockquote|pre)\b", text, re.IGNORECASE):
        sanitized = sanitize_rich_text_html(text)
        return re.sub(r"<\s*hr\s*/?\s*>", "<br /><br />", sanitized, flags=re.IGNORECASE)

    lines = [line.rstrip() for line in text.splitlines()]
    blocks = []
    paragraph_lines = []
    ul_items = []
    ol_items = []
    table_rows = []
    started = False

    def flush_paragraph():
        nonlocal paragraph_lines
        if paragraph_lines:
            content = " ".join(part.strip() for part in paragraph_lines if part.strip())
            if content:
                blocks.append(f"<p>{escape_preserving_safe_html(content)}</p>")
            paragraph_lines = []

    def flush_ul():
        nonlocal ul_items
        if ul_items:
            items_html = "".join(f"<li>{escape_preserving_safe_html(item)}</li>" for item in ul_items)
            blocks.append(f"<ul>{items_html}</ul>")
            ul_items = []

    def flush_ol():
        nonlocal ol_items
        if ol_items:
            items_html = "".join(f"<li>{escape_preserving_safe_html(item)}</li>" for item in ol_items)
            blocks.append(f"<ol>{items_html}</ol>")
            ol_items = []

    def flush_table():
        nonlocal table_rows
        if not table_rows:
            return

        header_cells = "".join(f"<th>{escape_preserving_safe_html(cell)}</th>" for cell in table_rows[0])
        body_rows = []
        for row in table_rows[1:]:
            body_cells = "".join(f"<td>{escape_preserving_safe_html(cell)}</td>" for cell in row)
            body_rows.append(f"<tr>{body_cells}</tr>")

        table_html = f"<table><thead><tr>{header_cells}</tr></thead>"
        if body_rows:
            table_html += f"<tbody>{''.join(body_rows)}</tbody>"
        table_html += "</table>"
        blocks.append(table_html)
        table_rows = []

    def flush_all_structures():
        flush_paragraph()
        flush_ul()
        flush_ol()
        flush_table()

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            flush_all_structures()
            continue

        if re.match(r"^[-=_]{3,}$", line):
            flush_all_structures()
            blocks.append("<br /><br />")
            started = True
            continue

        if line.startswith("|") and line.endswith("|"):
            flush_paragraph()
            flush_ul()
            flush_ol()

            if re.match(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?$", line):
                continue

            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if any(cells):
                table_rows.append(cells)
                started = True
            continue

        flush_table()

        ul_match = re.match(r"^[-*]\s+(.*)$", line)
        if ul_match:
            flush_paragraph()
            flush_ol()
            ul_items.append(ul_match.group(1).strip())
            started = True
            continue

        ol_match = re.match(r"^(\d+)\.\s+(.*)$", line)
        if ol_match:
            flush_paragraph()
            flush_ul()
            ol_items.append(ol_match.group(2).strip())
            started = True
            continue

        flush_ul()
        flush_ol()

        if not started and re.match(r"^[A-Z0-9\s&()/'\-]+$", line) and len(line) <= 120:
            flush_paragraph()
            blocks.append(f"<h1>{escape(line)}</h1>")
            started = True
            continue

        if re.match(r"^[A-Z0-9\s&()/'\-]{3,}$", line) and len(line) <= 120:
            flush_paragraph()
            blocks.append(f"<h2>{escape(line)}</h2>")
            started = True
            continue

        if line.endswith(":") and len(line) <= 120:
            flush_paragraph()
            blocks.append(f"<h3>{escape(line[:-1].strip())}</h3>")
            started = True
            continue

        label_value = re.match(r"^([A-Za-z][A-Za-z0-9\s/&()'\-]+):\s*(.+)$", line)
        if label_value:
            flush_paragraph()
            label = escape(label_value.group(1).strip())
            val = escape_preserving_safe_html(label_value.group(2).strip())
            blocks.append(f"<p><strong>{label}:</strong> {val}</p>")
            started = True
            continue

        paragraph_lines.append(line)
        started = True

    flush_all_structures()
    return "\n".join(blocks)


def remove_legacy_required_keys(data):
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            if k == "required":
                continue
            cleaned[k] = remove_legacy_required_keys(v)
        return cleaned
    elif isinstance(data, list):
        return [remove_legacy_required_keys(item) for item in data]
    return data


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


def sanitize_schema_fields(fields_list):
    """
    Recursively sanitize schema field definitions:
    - Removes 'required' key completely.
    - Sets 'is_required': False (or bool value if specified).
    - Sets 'is_visible': bool (defaults to not bool(conditions) or True).
    - Ensures 'placeholder' and 'width' are always populated.
    - Recursively processes 'children' if present.
    """
    if not isinstance(fields_list, list):
        return fields_list

    sanitized = []
    for item in fields_list:
        if not isinstance(item, dict):
            sanitized.append(item)
            continue

        node = dict(item)

        # Handle is_required: eliminate 'required', only keep 'is_required'
        if "is_required" in node:
            is_req = bool(node["is_required"])
        elif "required" in node:
            is_req = bool(node["required"])
        else:
            is_req = False

        if node.get("type") == "repeater":
            min_items = node.get("min_items")
            if min_items is not None:
                try:
                    if int(min_items) >= 1:
                        is_req = True
                except (ValueError, TypeError):
                    pass
            elif is_req:
                node["min_items"] = 1

        if node.get("type") == "richtext":
            node["option"] = "richtext"
            if not node.get("formatting_controls"):
                node["formatting_controls"] = [
                    "bold", "italic", "underline", "strike", "heading", "list", "ordered_list", "blockquote", "link", "clean"
                ]

        node.pop("required", None)
        node["is_required"] = is_req

        # Handle is_visible
        if "is_visible" not in node:
            node["is_visible"] = not bool(node.get("conditions"))
        else:
            node["is_visible"] = bool(node["is_visible"])

        # Handle placeholder and width
        node["placeholder"] = generate_default_field_placeholder(node)
        node["width"] = determine_field_width(node)
        if not node.get("position"):
            node["position"] = node["width"]

        # Recursively sanitize children
        if isinstance(node.get("children"), list):
            node["children"] = sanitize_schema_fields(node["children"])
            if node.get("type") == "repeater" and is_req:
                _enforce_repeater_children_required(node["children"])

        # Recursively sanitize options and option-level children if present
        if isinstance(node.get("options"), list):
            sanitized_options = []
            for opt in node["options"]:
                if isinstance(opt, dict):
                    opt_copy = dict(opt)
                    if isinstance(opt_copy.get("children"), list):
                        opt_copy["children"] = sanitize_schema_fields(opt_copy["children"])
                    sanitized_options.append(opt_copy)
                else:
                    sanitized_options.append(opt)
            node["options"] = sanitized_options

        sanitized.append(node)

    return remove_legacy_required_keys(sanitized)


class DocumentFieldDefinitionValidationMixin:
    ALLOWED_FIELD_TYPES = {
        "text",
        "textarea",
        "date",
        "email",
        "phone",
        "number",
        "currency",
        "checkbox",
        "select",
        "richtext",
        "group",
        "repeater",
        "signature",
        "image",
        "file",
    }
    ALLOWED_POSITIONS = {"top", "middle", "bottom", "signature_area", "custom", "left", "right", "full"}
    ALLOWED_CONDITION_OPERATORS = {
        "eq", "equals", "==",
        "neq", "not_equals", "!=",
        "in", "nin", "not_in",
        "contains", "is_empty", "is_not_empty",
        "gt", "gte", "lt", "lte"
    }

    def _validate_definition(self, value, field_name):
        if value in (None, ""):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError(f"{field_name} must be an array of field objects.")

        seen_names = set()
        self._validate_field_list(value, seen_names=seen_names, path=field_name)
        return value

    def _validate_field_list(self, field_list, seen_names, path):
        for idx, field_obj in enumerate(field_list):
            field_path = f"{path}[{idx}]"
            if not isinstance(field_obj, dict):
                raise serializers.ValidationError(f"{field_path} must be an object.")

            name = (field_obj.get("name") or "").strip()
            label = (field_obj.get("label") or "").strip()
            field_type = (field_obj.get("type") or "").strip().lower()

            if not name:
                raise serializers.ValidationError(f"{field_path}.name is required.")
            if not label:
                raise serializers.ValidationError(f"{field_path}.label is required.")
            if not field_type:
                raise serializers.ValidationError(f"{field_path}.type is required.")
            if field_type not in self.ALLOWED_FIELD_TYPES:
                raise serializers.ValidationError(f"{field_path}.type '{field_type}' is not supported.")

            if name in seen_names:
                raise serializers.ValidationError(f"Duplicate field name '{name}' found in schema.")
            seen_names.add(name)

            if "order" in field_obj and not isinstance(field_obj.get("order"), int):
                raise serializers.ValidationError(f"{field_path}.order must be an integer.")

            position = field_obj.get("position")
            if position is not None:
                position = str(position).strip().lower()
                if position not in self.ALLOWED_POSITIONS:
                    raise serializers.ValidationError(
                        f"{field_path}.position must be one of: {', '.join(sorted(self.ALLOWED_POSITIONS))}."
                    )

            if field_type == "select":
                options = field_obj.get("options")
                if not isinstance(options, list) or not options:
                    raise serializers.ValidationError(f"{field_path}.options must be a non-empty array for select fields.")
                for opt_idx, opt in enumerate(options):
                    if isinstance(opt, dict) and isinstance(opt.get("children"), list):
                        self._validate_field_list(
                            opt["children"],
                            seen_names=seen_names,
                            path=f"{field_path}.options[{opt_idx}].children"
                        )

            children = field_obj.get("children")
            if field_type in {"group", "repeater"}:
                if not isinstance(children, list) or not children:
                    raise serializers.ValidationError(f"{field_path}.children must be a non-empty array for {field_type} fields.")
                self._validate_field_list(children, seen_names=seen_names, path=f"{field_path}.children")
            elif children is not None:
                raise serializers.ValidationError(f"{field_path}.children is only allowed for group/repeater fields.")

            if field_type == "repeater":
                min_items = field_obj.get("min_items")
                max_items = field_obj.get("max_items")
                if min_items is not None and (not isinstance(min_items, int) or min_items < 0):
                    raise serializers.ValidationError(f"{field_path}.min_items must be a non-negative integer.")
                if max_items is not None and (not isinstance(max_items, int) or max_items < 1):
                    raise serializers.ValidationError(f"{field_path}.max_items must be a positive integer.")
                if isinstance(min_items, int) and isinstance(max_items, int) and min_items > max_items:
                    raise serializers.ValidationError(f"{field_path}.min_items cannot be greater than max_items.")

            conditions = field_obj.get("conditions")
            if conditions is not None:
                if not isinstance(conditions, list):
                    raise serializers.ValidationError(f"{field_path}.conditions must be an array.")
                for cond_idx, condition in enumerate(conditions):
                    cond_path = f"{field_path}.conditions[{cond_idx}]"
                    if not isinstance(condition, dict):
                        raise serializers.ValidationError(f"{cond_path} must be an object.")
                    ref_field = (condition.get("field") or "").strip()
                    operator = (condition.get("operator") or "").strip().lower()
                    if not ref_field:
                        raise serializers.ValidationError(f"{cond_path}.field is required.")
                    if not operator:
                        raise serializers.ValidationError(f"{cond_path}.operator is required.")
                    if operator not in self.ALLOWED_CONDITION_OPERATORS:
                        raise serializers.ValidationError(
                            f"{cond_path}.operator must be one of: {', '.join(sorted(self.ALLOWED_CONDITION_OPERATORS))}."
                        )
                    if "value" not in condition:
                        raise serializers.ValidationError(f"{cond_path}.value is required.")


class TemplateCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateCategory
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "icon",
            "template_count",
            "is_recommended",
            "is_popular",
        ]

class DocumentTypeSerializer(DocumentFieldDefinitionValidationMixin, serializers.ModelSerializer):
    category = TemplateCategorySerializer(read_only=True)

    class Meta:
        model = DocumentType
        fields = [
            "id",
            "category",
            "name",
            "slug",
            "description",
            "schema_definition",
        ]

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        schema = ret.get("schema_definition")
        if isinstance(schema, str):
            try:
                import json
                schema = json.loads(schema)
            except Exception:
                pass
        if isinstance(schema, list):
            ret["schema_definition"] = sanitize_schema_fields(schema)
        return remove_legacy_required_keys(ret)

    def validate_schema_definition(self, value):
        validated = self._validate_definition(value, "schema_definition")
        return sanitize_schema_fields(validated)


class DocumentTemplateSerializer(serializers.ModelSerializer):
    document_type = DocumentTypeSerializer(read_only=True)
    content_template = serializers.SerializerMethodField()
    content = serializers.SerializerMethodField()
    structure = serializers.SerializerMethodField()

    class Meta:
        model = DocumentTemplate
        fields = [
            "id",
            "document_type",
            "name",
            "slug",
            "description",
            "content_template",
            "content",
            "structure",
            "base_content",
            "preview_image",
            "usage_count",
        ]

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if isinstance(ret.get("document_type"), dict):
            dt = ret["document_type"]
            schema = dt.get("schema_definition")
            if isinstance(schema, str):
                try:
                    import json
                    schema = json.loads(schema)
                except Exception:
                    pass
            if isinstance(schema, list):
                dt["schema_definition"] = sanitize_schema_fields(schema)
        return remove_legacy_required_keys(ret)

    def get_content_template(self, obj):
        from .serializers import render_text_as_html
        return render_text_as_html(obj.content_template)
        
    def get_content(self, obj):
        from .serializers import render_text_as_html
        return render_text_as_html(obj.content_template)
        
    def get_structure(self, obj):
        from .views import _resolve_document_structure
        structure = _resolve_document_structure(obj)
        if not structure:
            return None

        return {
            "id": structure.id,
            "name": structure.name,
            "has_header": structure.has_header,
            "has_footer": structure.has_footer,
            "has_signature_section": structure.has_signature_section,
            "has_date_field": structure.has_date_field,
            "has_page_numbers": structure.has_page_numbers,
            "header_height_mm": structure.header_height_mm,
            "footer_height_mm": structure.footer_height_mm,
            "left_margin_mm": structure.left_margin_mm,
            "right_margin_mm": structure.right_margin_mm,
            "top_margin_mm": structure.top_margin_mm,
            "bottom_margin_mm": structure.bottom_margin_mm,
            "line_spacing": structure.line_spacing,
            "logo_width_mm": structure.logo_width_mm,
            "logo_position": structure.logo_position,
        }


class GenerateDocumentSerializer(serializers.Serializer):
    template_id = serializers.IntegerField()
    structure_id = serializers.IntegerField(required=False)
    name = serializers.CharField(max_length=160)
    form_data = serializers.JSONField()

    def validate_form_data(self, value):
        if isinstance(value, str):
            try:
                import json
                value = json.loads(value)
            except Exception:
                raise serializers.ValidationError("form_data must be valid JSON.")
        if not isinstance(value, dict):
            raise serializers.ValidationError("form_data must be a dictionary.")
        return value



class DocumentFeedbackSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=2000)

class GeneratedDocumentSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    document_type_name = serializers.CharField(source="document_type.name", read_only=True)
    template_name = serializers.CharField(source="template.name", read_only=True)
    structure_name = serializers.CharField(source="structure.name", read_only=True)
    rendered_content = serializers.SerializerMethodField()

    def get_rendered_content(self, obj):
        return render_text_as_html(getattr(obj, "rendered_content", ""))

    class Meta:
        model = GeneratedDocument
        fields = [
            "id",
            "name",
            "category_name",
            "document_type_name",
            "template_name",
            "structure",
            "structure_name",
            "status",
            "form_data",
            "input_fingerprint",
            "rendered_content",
            "credit_used",
            "generated_at",
            "previewed_at",
            "downloaded_at",
        ]

class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = [
            "id",
            "provider",
            "card_brand",
            "card_last4",
            "exp_month",
            "exp_year",
            "is_default",
        ]

class CreditWalletSerializer(serializers.ModelSerializer):
    credits_remaining = serializers.IntegerField(read_only=True)

    class Meta:
        model = CreditWallet
        fields = [
            "credits_limit",
            "credits_used",
            "credits_remaining",
            "plan_download_limit",
            "cycle_start",
            "cycle_end",
        ]


class CompanyBrandingSerializer(serializers.ModelSerializer):
    logo = serializers.ImageField(required=False, allow_null=True)
    company_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    address = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = CompanyBranding
        fields = ["logo", "company_name", "address", "phone"]


class HelpArticleSerializer(serializers.ModelSerializer):
    class Meta:
        model = HelpArticle
        fields = [
            "id",
            "section",
            "title",
            "slug",
            "short_description",
            "content",
            "is_popular",
        ]

class DocumentRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentRequest
        fields = [
            "id",
            "document_name",
            "category",
            "short_description",
            "status",
            "request_count",
            "created_at",
        ]
        read_only_fields = ["status", "request_count"]


class DocumentStructureSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentStructure
        fields =[
            "id",
            "structure_type",
            "name",
            "slug",
            "description",
            "has_header",
            "has_signature_section",
            "has_date_field",
            "has_page_numbers",
            "has_footer",
            "header_height_mm",
            "footer_height_mm",
            "left_margin_mm",
            "right_margin_mm",
            "top_margin_mm",
            "bottom_margin_mm",
            "line_spacing",
            "logo_width_mm",
            "logo_position",
            "is_active",
            "usage_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["slug", "usage_count", "created_at", "updated_at"]


class DocumentSchemaSerializer(serializers.ModelSerializer):
    structure_name = serializers.CharField(source="structure.name", read_only=True)

    ALLOWED_FIELD_TYPES = {
        "text",
        "textarea",
        "date",
        "email",
        "phone",
        "number",
        "currency",
        "checkbox",
        "select",
        "richtext",
        "group",
        "repeater",
        "signature",
        "image",
        "file",
    }
    ALLOWED_POSITIONS = {"top", "middle", "bottom", "signature_area", "custom", "left", "right", "full"}
    ALLOWED_CONDITION_OPERATORS = {
        "eq", "equals", "==",
        "neq", "not_equals", "!=",
        "in", "nin", "not_in",
        "contains", "is_empty", "is_not_empty",
        "gt", "gte", "lt", "lte"
    }

    class Meta:
        model = DocumentSchema
        fields = [
            "id",
            "structure",
            "structure_name",
            "fields_definition",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        fields_def = ret.get("fields_definition")
        if isinstance(fields_def, list):
            ret["fields_definition"] = sanitize_schema_fields(fields_def)
        return ret

    def validate_fields_definition(self, value):
        if value in (None, ""):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("fields_definition must be an array of field objects.")

        seen_names = set()
        self._validate_field_list(value, seen_names=seen_names, path="fields_definition")
        return sanitize_schema_fields(value)

    def _validate_field_list(self, field_list, seen_names, path):
        for idx, field_obj in enumerate(field_list):
            field_path = f"{path}[{idx}]"
            if not isinstance(field_obj, dict):
                raise serializers.ValidationError(f"{field_path} must be an object.")

            name = (field_obj.get("name") or "").strip()
            label = (field_obj.get("label") or "").strip()
            field_type = (field_obj.get("type") or "").strip().lower()

            if not name:
                raise serializers.ValidationError(f"{field_path}.name is required.")
            if not label:
                raise serializers.ValidationError(f"{field_path}.label is required.")
            if not field_type:
                raise serializers.ValidationError(f"{field_path}.type is required.")
            if field_type not in self.ALLOWED_FIELD_TYPES:
                raise serializers.ValidationError(f"{field_path}.type '{field_type}' is not supported.")

            if name in seen_names:
                raise serializers.ValidationError(f"Duplicate field name '{name}' found in schema.")
            seen_names.add(name)

            if "order" in field_obj and not isinstance(field_obj.get("order"), int):
                raise serializers.ValidationError(f"{field_path}.order must be an integer.")

            position = field_obj.get("position")
            if position is not None:
                position = str(position).strip().lower()
                if position not in self.ALLOWED_POSITIONS:
                    raise serializers.ValidationError(
                        f"{field_path}.position must be one of: {', '.join(sorted(self.ALLOWED_POSITIONS))}."
                    )

            if field_type == "select":
                options = field_obj.get("options")
                if not isinstance(options, list) or not options:
                    raise serializers.ValidationError(f"{field_path}.options must be a non-empty array for select fields.")
                for opt_idx, opt in enumerate(options):
                    if isinstance(opt, dict) and isinstance(opt.get("children"), list):
                        self._validate_field_list(
                            opt["children"],
                            seen_names=seen_names,
                            path=f"{field_path}.options[{opt_idx}].children"
                        )

            children = field_obj.get("children")
            if field_type in {"group", "repeater"}:
                if not isinstance(children, list) or not children:
                    raise serializers.ValidationError(f"{field_path}.children must be a non-empty array for {field_type} fields.")
                self._validate_field_list(children, seen_names=seen_names, path=f"{field_path}.children")
            elif children is not None:
                raise serializers.ValidationError(f"{field_path}.children is only allowed for group/repeater fields.")

            if field_type == "repeater":
                min_items = field_obj.get("min_items")
                max_items = field_obj.get("max_items")
                if min_items is not None and (not isinstance(min_items, int) or min_items < 0):
                    raise serializers.ValidationError(f"{field_path}.min_items must be a non-negative integer.")
                if max_items is not None and (not isinstance(max_items, int) or max_items < 1):
                    raise serializers.ValidationError(f"{field_path}.max_items must be a positive integer.")
                if isinstance(min_items, int) and isinstance(max_items, int) and min_items > max_items:
                    raise serializers.ValidationError(f"{field_path}.min_items cannot be greater than max_items.")

            conditions = field_obj.get("conditions")
            if conditions is not None:
                if not isinstance(conditions, list):
                    raise serializers.ValidationError(f"{field_path}.conditions must be an array.")
                for cond_idx, condition in enumerate(conditions):
                    cond_path = f"{field_path}.conditions[{cond_idx}]"
                    if not isinstance(condition, dict):
                        raise serializers.ValidationError(f"{cond_path} must be an object.")
                    ref_field = (condition.get("field") or "").strip()
                    operator = (condition.get("operator") or "").strip().lower()
                    if not ref_field:
                        raise serializers.ValidationError(f"{cond_path}.field is required.")
                    if not operator:
                        raise serializers.ValidationError(f"{cond_path}.operator is required.")
                    if operator not in self.ALLOWED_CONDITION_OPERATORS:
                        raise serializers.ValidationError(
                            f"{cond_path}.operator must be one of: {', '.join(sorted(self.ALLOWED_CONDITION_OPERATORS))}."
                        )
                    if "value" not in condition:
                        raise serializers.ValidationError(f"{cond_path}.value is required.")
