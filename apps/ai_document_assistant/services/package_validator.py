import re
import logging
from .validators import generate_default_field_placeholder, determine_field_width

logger = logging.getLogger(__name__)


class PackageValidator:
    def __init__(self):
        self.issues = []

    def validate(self, data: dict) -> dict:
        self.issues = []

        schema           = data.get("schema_definition", [])
        content_template = data.get("content_template", "")
        base_content     = data.get("base_content", {})

        flat_schema  = self._flatten_schema(schema)
        schema_labels = {v["label"]: k for k, v in flat_schema.items()}
        schema_names  = list(flat_schema.keys())

        # Step 1: Clean pseudo-logic + repair/detect orphan placeholders
        content_template = self._validate_and_repair_placeholders(
            content_template, schema_labels, schema_names, flat_schema
        )

        # Step 2: Base content validation
        self._validate_base_content(base_content, schema_names, flat_schema)

        # Step 3: Condition validation + repair
        self._validate_conditions(schema, flat_schema)

        # Step 4: Repeater children check
        self._validate_repeaters(schema, content_template)

        # Step 5: Signature consistency
        self._validate_signatures(base_content)

        # Step 6: Structural template quality checks
        self._detect_raw_field_dump(content_template)
        self._detect_empty_headings(content_template)

        # Step 7: Ensure visibility and required flags
        self._ensure_visibility_flags(schema)

        return {
            "valid": len(self.issues) == 0,
            "corrected_package": {
                "schema_definition": schema,
                "content_template":  content_template,
                "base_content":      base_content,
            },
            "issues": self.issues,
        }

    def _ensure_visibility_flags(self, fields):
        for field in fields or []:
            if isinstance(field, dict):
                has_conditions = bool(field.get("conditions"))
                field["is_visible"] = field.get("is_visible", not has_conditions)
                field["is_required"] = bool(field.get("is_required", field.get("required", False)))
                field.pop("required", None)
                field["placeholder"] = generate_default_field_placeholder(field)
                field["width"] = determine_field_width(field)
                if not field.get("position"):
                    field["position"] = field["width"]
                if isinstance(field.get("children"), list):
                    self._ensure_visibility_flags(field["children"])
                if isinstance(field.get("options"), list):
                    for opt in field["options"]:
                        if isinstance(opt, dict) and isinstance(opt.get("children"), list):
                            self._ensure_visibility_flags(opt["children"])


    def _flatten_schema(self, fields, parent_path=""):
        flat = {}
        for f in fields:
            name = f.get("name")
            if not name:
                continue
            flat[name] = {
                "label":   f.get("label", name),
                "type":    f.get("type"),
                "options": f.get("options", []),
                "parent":  parent_path,
                "raw":     f,
            }
            if f.get("children"):
                flat.update(self._flatten_schema(f["children"], parent_path=name))
            if isinstance(f.get("options"), list):
                for opt in f["options"]:
                    if isinstance(opt, dict) and isinstance(opt.get("children"), list):
                        flat.update(self._flatten_schema(opt["children"], parent_path=name))
        return flat

    
    # Step 1 — Placeholder repair (NO robotic dump)
    

    def _validate_and_repair_placeholders(
        self, template: str, schema_labels: dict, schema_names: list, flat_schema: dict
    ) -> str:

        # 1a. Strip AI pseudo-logic (Handlebars style)
        pseudo = re.findall(r'\{\{.*?\}\}', template, re.DOTALL)
        for p in pseudo:
            template = template.replace(p, "")
            self.issues.append(f"Removed pseudo-logic from template: '{p[:60]}'")
        if pseudo:
            template = re.sub(r'\n{3,}', '\n\n', template)

        # 1b. Identify container (group/repeater) labels — these must never
        #     appear as placeholders; remove any occurrences carefully
        container_labels = {
            v["label"] for v in flat_schema.values()
            if v["type"] in ("group", "repeater")
        }

        found_placeholders = re.findall(r'\[([^\]]+)\]', template)

        for ph in found_placeholders:
            # Container label leak — remove ONLY the placeholder brackets,
            # not the whole surrounding line (to avoid destroying valid content)
            if ph in container_labels:
                template = re.sub(rf'\[{re.escape(ph)}\]', "", template)
                template = re.sub(r'\n{3,}', '\n\n', template)
                self.issues.append(f"Removed container field placeholder from template: [{ph}]")
                continue

            # Exact label or name match → OK
            if ph in schema_labels or ph in schema_names:
                continue

            # Fuzzy repair (case/space insensitive)
            ph_clean = ph.replace(" ", "").lower()
            repaired = False
            for label, name in schema_labels.items():
                if ph_clean in (label.replace(" ", "").lower(), name.replace("_", "").lower()):
                    template = template.replace(f"[{ph}]", f"[{label}]")
                    self.issues.append(f"Repaired placeholder [{ph}] → [{label}]")
                    repaired = True
                    break

            if not repaired:
                # Orphan placeholder — log it, do NOT remove it
                # (it might be intentional freeform text in brackets)
                self.issues.append(f"Orphan placeholder in template: [{ph}]")

        # 1c. Missing placeholder check — LOG ONLY, do NOT append robotic dump
        #     The service.py quality-checker loop already retried the model for
        #     missing placeholders. Appending "Label: [Label]" here would
        #     reintroduce the exact robotic pattern we explicitly ban everywhere.
        for name, field_data in flat_schema.items():
            f_type  = field_data.get("type", "")
            f_label = field_data.get("label", name)

            if f_type in ("group", "repeater"):
                continue  # containers never appear as placeholders

            if f"[{f_label}]" not in template and f"[{name}]" not in template:
                # Fuzzy check — maybe the label was repaired above
                f_label_clean = f_label.replace(" ", "").lower()
                found_clean   = {p.replace(" ", "").lower() for p in re.findall(r'\[([^\]]+)\]', template)}
                if f_label_clean not in found_clean:
                    self.issues.append(
                        f"Missing placeholder for field '{name}' (label='{f_label}'). "
                        f"Quality checker should have caught this — manual review recommended."
                    )

        return template

    
    # Step 2 — Base content validation
    

    def _validate_base_content(self, base_content: dict, schema_names: list, flat_schema: dict):
        if "required_fields" in base_content:
            req = base_content["required_fields"]
            if isinstance(req, list):
                validated = []
                for rf in req:
                    if rf in schema_names:
                        # Extra guard: exclude checkbox/image/file/group/repeater/conditional
                        fdata = flat_schema.get(rf, {})
                        ftype = fdata.get("type", "")
                        raw   = fdata.get("raw", {})
                        if ftype in ("checkbox", "image", "file", "group", "repeater"):
                            self.issues.append(
                                f"Removed '{rf}' from required_fields — type '{ftype}' must not appear there"
                            )
                            continue
                        if raw.get("conditions"):
                            self.issues.append(
                                f"Removed conditional field '{rf}' from required_fields"
                            )
                            continue
                        validated.append(rf)
                    else:
                        # Fuzzy repair
                        rf_clean  = rf.replace("_", "").lower()
                        repaired  = False
                        for name in schema_names:
                            if rf_clean == name.replace("_", "").lower():
                                validated.append(name)
                                self.issues.append(f"Repaired required_field '{rf}' → '{name}'")
                                repaired = True
                                break
                        if not repaired:
                            self.issues.append(f"Removed unknown required_field: '{rf}'")
                base_content["required_fields"] = validated

        # Remove unknown root keys
        standard_keys = {"document_type", "signature_required", "required_fields"}
        for k in [k for k in list(base_content.keys()) if k not in standard_keys]:
            self.issues.append(f"Removed unknown key from base_content: '{k}'")
            del base_content[k]

    
    # Step 3 — Condition validation & repair
    

    def _validate_conditions(self, fields: list, flat_schema: dict):
        schema_names = list(flat_schema.keys())

        for f in fields:
            conds = f.get("conditions")

            # Auto-repair dict → list
            if isinstance(conds, dict):
                if "field" in conds and "value" in conds:
                    conds = [conds]
                else:
                    conds = [{"field": k, "value": v} for k, v in conds.items()]
                f["conditions"] = conds
                self.issues.append(f"Repaired conditions dict→list for field '{f.get('name')}'")

            if isinstance(conds, list):
                valid_conds = []
                for cond in conds:
                    if not isinstance(cond, dict):
                        continue
                    field_ref = cond.get("field")
                    val_ref   = cond.get("value")

                    # Repair unknown field reference
                    if field_ref and field_ref not in flat_schema:
                        ref_clean = field_ref.replace("_", "").lower()
                        found = next(
                            (n for n in schema_names if ref_clean == n.replace("_", "").lower()),
                            None,
                        )
                        if found:
                            cond["field"] = found
                            field_ref = found
                            self.issues.append(f"Repaired condition field '{field_ref}' → '{found}'")
                        else:
                            self.issues.append(f"Dropped condition — unknown field ref: '{field_ref}'")
                            continue

                    # Repair option value
                    if field_ref in flat_schema:
                        target = flat_schema[field_ref]
                        if target["type"] in ("select", "checkbox") and val_ref is not None:
                            valid_vals = [str(o.get("value", "")) for o in target.get("options", []) if isinstance(o, dict)]
                            if valid_vals:
                                refs = val_ref if isinstance(val_ref, list) else [val_ref]
                                repaired_refs = []
                                for vr in refs:
                                    vr_str = str(vr)
                                    if vr_str in valid_vals:
                                        repaired_refs.append(vr)
                                    else:
                                        match = next(
                                            (v for v in valid_vals if vr_str.lower() == v.lower()),
                                            None,
                                        )
                                        if match:
                                            repaired_refs.append(match)
                                            self.issues.append(f"Repaired condition value '{vr}' → '{match}'")
                                        else:
                                            repaired_refs.append(vr)
                                            self.issues.append(f"Condition value '{vr}' not in options for '{field_ref}'")
                                cond["value"] = repaired_refs if isinstance(val_ref, list) else repaired_refs[0]

                    valid_conds.append(cond)

                if valid_conds:
                    f["conditions"] = valid_conds
                elif "conditions" in f:
                    del f["conditions"]

            if f.get("children"):
                self._validate_conditions(f["children"], flat_schema)

    
    # Step 4 — Repeater children in template
    

    def _validate_repeaters(self, fields: list, template: str):
        for f in fields:
            if f.get("type") == "repeater":
                for child in f.get("children", []):
                    child_label = child.get("label", child.get("name", ""))
                    if child_label and f"[{child_label}]" not in template:
                        self.issues.append(
                            f"Repeater child '{child_label}' missing from content_template"
                        )
            if f.get("children"):
                self._validate_repeaters(f["children"], template)

    
    # Step 5 — Signature consistency
    

    def _validate_signatures(self, base_content: dict):
        val = base_content.get("signature_required")
        if val is not None and not isinstance(val, bool):
            self.issues.append("base_content.signature_required must be a boolean")

    
    # Step 6 — Template structural quality
    

    def _detect_raw_field_dump(self, template: str):
        lines = [l.strip() for l in template.strip().split("\n") if l.strip()]
        dump_lines = sum(
            1 for l in lines
            if re.match(r'^[\-\*]?\s*[a-zA-Z\s]+:\s*\[[a-zA-Z\s]+\]$', l)
        )
        if dump_lines > 3 and dump_lines > len(lines) * 0.4:
            self.issues.append(
                "CRITICAL_TEMPLATE_DUMP: Template contains a raw field dump "
                "instead of narrative paragraphs."
            )

    def _detect_empty_headings(self, template: str):
        lines = [l.strip() for l in template.strip().split("\n") if l.strip()]
        if not lines:
            return
        last = lines[-1]
        if len(last) < 50 and (last.startswith("Article") or last.endswith(":")):
            self.issues.append(
                "CRITICAL_EMPTY_HEADING: Template ends with a heading that has no content."
            )


def validate_package(data: dict) -> dict:
    return PackageValidator().validate(data)
