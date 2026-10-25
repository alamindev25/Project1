from datetime import datetime
from decimal import Decimal, InvalidOperation
from html import escape, unescape
import hashlib
import json
import os
import re
from urllib.parse import quote, unquote, urlparse

from django.core import signing
from django.core.cache import cache
from django.conf import settings
from django.db.models import Count, Q
from django.http import FileResponse, HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from apps.cms.models import CMS, FAQ, CMSPoint
from apps.subscription.models import PaymentHistory, Subscription
from apps.subscription.serializers import SubscriptionPackageSerializer
from apps.system_setting.models import (
    AboutSystem,
    DashboardSettings,
    LandingCheckoutBrand,
    LandingPageBadge,
    LandingPageFeature,
    LandingPageHero,
    LandingPagePricing,
    LandingPageSection,
    LandingPreviewSample,
    LandingTestimonial,
    SystemColor,
)
from apps.user.authentication import JWTAuthentication
from apps.user.models import User, UserProfile
from apps.utils.helpers import error, success
from apps.utils.tasks import dispatch_email_task

from .models import (
    CompanyBranding,
    CreditWallet,
    DocumentAction,
    DocumentFeedback,
    DocumentRequest,
    DocumentSchema,
    DocumentStructure,
    DocumentTemplate,
    DocumentType,
    GeneratedDocument,
    HelpArticle,
    PaymentMethod,
    SignatureRequest,
    SignatureAudit,
    TemplateCategory,
)

from .serializers import (
    CompanyBrandingSerializer,
    CreditWalletSerializer,
    DocumentFeedbackSerializer,
    DocumentRequestSerializer,
    DocumentSchemaSerializer,
    DocumentStructureSerializer,
    GenerateDocumentSerializer,
    GeneratedDocumentSerializer,
    HelpArticleSerializer,
    PaymentMethodSerializer,
    TemplateCategorySerializer,
    render_text_as_html,
    generate_default_field_placeholder,
    determine_field_width,
)
from .pdf_service import build_pdf_for_document


SIGNED_LINK_MAX_AGE_SECONDS = 30 * 60
# FREE_PLAN_ACCESS_LIMIT = 3
FREE_PLAN_ACCESS_LIMIT = 1
# FREE_PLAN_GENERATION_LIMIT = 1
FREE_PLAN_GENERATION_LIMIT = 1


def _active_subscription_for_user(user):
    return Subscription.objects.filter(user=user, status="active").order_by("-created_at").first()


def _has_free_generation_reached(user):
    return GeneratedDocument.objects.filter(user=user).count() >= FREE_PLAN_GENERATION_LIMIT

def _build_document_history_response(
    request,
    *,
    history_type="document",
    category_id=None,
    category_name=None,
    status_filter=None,
    search=None,
):
    documents_qs = GeneratedDocument.objects.filter(user=request.user).select_related(
        "category", "document_type", "template"
    )

    if category_id:
        documents_qs = documents_qs.filter(category_id=category_id)

    if category_name:
        # Allow partial, case-insensitive matching so typing 'finance' matches
        # categories like 'Finance & Billings'. Trim whitespace first.
        qname = (category_name or "").strip()
        if qname:
            documents_qs = documents_qs.filter(category__name__icontains=qname)

    if status_filter:
        documents_qs = documents_qs.filter(status=status_filter.lower())

    if search:
        documents_qs = documents_qs.filter(
            Q(name__icontains=search)
            | Q(category__name__icontains=search)
            | Q(document_type__name__icontains=search)
            | Q(template__name__icontains=search)
        )

    items = []
    if history_type in {"document", "all"}:
        include_delete = history_type == "all"
        for document in documents_qs:
            download_url = _build_authenticated_document_url(document.id, "download", request)
            delete_url = f"/api/documents/history/{document.id}/"
            item = {
                "id": document.id,
                "document_id": document.id,
                "title": document.name,
                "name": document.name,
                "date": document.generated_at,
                "status": document.status.capitalize(),
                "actions": {
                    "download": download_url,
                },
            }
            if include_delete:
                item["actions"]["delete"] = delete_url
            items.append(item)

    items.sort(key=lambda x: x["date"] or timezone.now(), reverse=True)

    data = {
        "title": "Document History",
        "subtitle": f"Showing {len(items)} documents",
        "items": items,
        "counts": {
            "total": len(items),
            "documents": len(items),
            "billing": 0,
        },
    }

    return success(data=data, message="History fetched successfully.")


def _user_display_name(user):
    profile = getattr(user, "user_profile", None)
    if profile:
        first_name = (profile.first_name or "").strip()
        last_name = (profile.last_name or "").strip()
        full_name = " ".join(part for part in [first_name, last_name] if part)
        if full_name:
            return full_name

    email = getattr(user, "email", "") or ""
    local_part = email.split("@")[0].replace(".", " ").replace("_", " ").strip()
    return local_part.title() if local_part else "Verified Customer"


def _user_avatar_url(request, user):
    avatar = getattr(user, "avatar", None)
    avatar_url = getattr(avatar, "url", None)
    return _to_absolute_uri(request, avatar_url)

def _feedback_item_from_testimonial(request, testimonial):
    return {
        "id": f"testimonial-{testimonial.id}",
        "name": testimonial.name,
        "role": testimonial.role,
        "rating": testimonial.rating,
        "comment": testimonial.comment,
        "avatar": _to_absolute_uri(request, testimonial.avatar.url) if testimonial.avatar else None,
        "source": "testimonial",
    }


def _feedback_item_from_document_feedback(request, feedback):
    user = feedback.user
    return {
        "id": f"feedback-{feedback.id}",
        "name": _user_display_name(user) if user else "Verified Customer",
        "role": "Document Customer",
        "rating": feedback.rating,
        "comment": feedback.comment or f"Rated {feedback.rating} stars after document generation.",
        "avatar": _user_avatar_url(request, user) if user else None,
        "source": "document_feedback",
        "document_name": feedback.document.name if feedback.document else None,
    }

def _build_rating_summary(items):
    ratings = [int(item.get("rating") or 0) for item in items if item.get("rating")]
    if not ratings:
        return {
            "average_rating": 0,
            "total_reviews": 0,
            "rating_label": "No reviews yet",
        }

    average_rating = round(sum(ratings) / len(ratings), 1)
    return {
        "average_rating": average_rating,
        "total_reviews": len(ratings),
        "rating_label": f"{average_rating}/5 from {len(ratings)} reviews",
    }

def _build_document_feedback_payload(document, request):
    return {
        "enabled": True,
        "auto_open": True,
        "skippable": True,
        "allow_cancel": True,
        "allow_comment": True,
        "submit_url": f"/api/documents/{document.id}/feedback/",
        "rating_min": 1,
        "rating_max": 5,
        "prompt_title": "Share your feedback",
        "prompt_subtitle": "Rate the document now. You can cancel if you do not want to leave feedback.",
        "submit_label": "Submit",
        "cancel_label": "Cancel",
        "cancel_action": "close_modal",
        "success_action": "refresh_landing_summary",
        "document_id": document.id,
        "document_name": document.name,
    }

def _build_document_access_key(document_id, purpose):
    payload = {
        "document_id": int(document_id),
        "purpose": purpose,
        "ts": int(timezone.now().timestamp()),
    }
    return signing.dumps(payload, salt="dashboard.document.access")


def _build_document_access_url(request, document_id, purpose):
    key = _build_document_access_key(document_id=document_id, purpose=purpose)
    encoded_key = quote(key, safe="")
    path = f"/api/documents/access/?access_key={encoded_key}"
    if purpose == "preview":
        path += "&inline=true"

    base_url = getattr(settings, "DOCUMENT_ACCESS_BASE_URL", "").strip()
    if base_url and request is not None and request.is_secure():
        parsed_base_url = urlparse(base_url)
        # Avoid mixed-content downloads when frontend is served over HTTPS.
        if parsed_base_url.scheme == "http":
            base_url = ""
    if base_url:
        return f"{base_url.rstrip('/')}{path}"

    if request is not None:
        return request.build_absolute_uri(path)

    return path


def _build_authenticated_document_url(document_id, purpose, request=None):
    # For browser-safe links, preview/download should use signed public URLs.
    if purpose in {"preview", "download"}:
        return _build_document_access_url(request, document_id, purpose)

    path = f"/api/documents/{document_id}/"

    base_url = getattr(settings, "DOCUMENT_ACCESS_BASE_URL", "").strip()
    if base_url and request is not None and request.is_secure():
        parsed_base_url = urlparse(base_url)
        # Avoid mixed-content downloads when frontend is served over HTTPS.
        if parsed_base_url.scheme == "http":
            base_url = ""
    if base_url:
        return f"{base_url.rstrip('/')}{path}"

    if request is not None:
        return request.build_absolute_uri(path)

    return path


def _resolve_document_structure(template, requested_structure_id=None):
    if requested_structure_id:
        return DocumentStructure.objects.filter(id=requested_structure_id, is_active=True).first()

    try:
        category_name = (template.document_type.category.name or "").lower()
        document_type_name = (template.document_type.name or "").lower()
    except Exception:
        category_name = ""
        document_type_name = ""

    if any(k in f"{category_name} {document_type_name}" for k in ["legal", "nda", "confidential", "non-compete"]):
        return DocumentStructure.objects.filter(structure_type="legal", is_active=True).first()
    if any(k in f"{category_name} {document_type_name}" for k in ["contract", "service", "vendor", "consulting"]):
        return DocumentStructure.objects.filter(structure_type="contract", is_active=True).first()
    if any(k in f"{category_name} {document_type_name}" for k in ["invoice", "receipt", "purchase", "financial"]):
        return DocumentStructure.objects.filter(structure_type="financial", is_active=True).first()

    return DocumentStructure.objects.filter(is_active=True).order_by("id").first()


PLACEHOLDER_PATTERN = re.compile(r"\[([^\[\]]+)\]|\{\{([^\{\}]+)\}\}")


def _get_match_token(match):
    if not match:
        return ""
    return (match.group(1) or (match.group(2) if match.lastindex and match.lastindex >= 2 else "") or "").strip()

def _safe_text(value):
    if value is None:
        return ""
    return str(value)

def _normalize_template_key(value):
    return re.sub(r"[^a-z0-9]+", "", _safe_text(value).strip().lower())

def _parse_decimal_value(value):
    text = _safe_text(value).strip().replace(",", "").replace("$", "")
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None

def _format_currency_value(value):
    parsed = _parse_decimal_value(value)
    if parsed is None:
        return _safe_text(value)
    return f"${parsed:,.2f}"

def _finance_template_overrides(template, resolved_values):
    document_type = getattr(template, "document_type", None)
    doc_type_name = _safe_text(getattr(document_type, "name", "")).lower()
    values = dict(resolved_values or {})

    if doc_type_name in {"invoice", "purchase order"}:
        quantity = _parse_decimal_value(values.get("quantity"))
        unit_price = _parse_decimal_value(values.get("unitprice"))
        subtotal = _parse_decimal_value(values.get("subtotal"))
        taxes = _parse_decimal_value(values.get("taxes"))
        total_amount = _parse_decimal_value(values.get("totalamount"))

        if subtotal is None and quantity is not None and unit_price is not None:
            subtotal = quantity * unit_price
        if total_amount is None and subtotal is not None:
            total_amount = subtotal + (taxes or Decimal("0"))

        if subtotal is not None:
            values["subtotal"] = _format_currency_value(subtotal)
        if taxes is not None:
            values["taxes"] = _format_currency_value(taxes)
        if total_amount is not None:
            values["totalamount"] = _format_currency_value(total_amount)

        description_key = "descriptionofservicesproducts" if doc_type_name == "invoice" else "descriptionofgoodservices"
        description_value = _safe_text(values.get(description_key)).strip()
        if description_value:
            bullets = [line.strip("-• ") for line in re.split(r"[\n;]+", description_value) if line.strip()]
            values[description_key] = "\n".join(f"- {line}" for line in bullets)

    elif doc_type_name == "receipt":
        amount_paid = _parse_decimal_value(values.get("amountpaid"))
        remaining_balance = _parse_decimal_value(values.get("remainingbalance"))
        if amount_paid is not None:
            values["amountpaid"] = _format_currency_value(amount_paid)
        if remaining_balance is not None:
            if remaining_balance <= 0:
                values["remainingbalance"] = ""
                values["remainingbalancesection"] = ""
            else:
                values["remainingbalance"] = _format_currency_value(remaining_balance)
                values["remainingbalancesection"] = f"Remaining Balance: {values['remainingbalance']}"
        else:
            values["remainingbalancesection"] = ""

    elif doc_type_name == "billing statement":
        previous_balance = _parse_decimal_value(values.get("previousbalance")) or Decimal("0")
        payments_received = _parse_decimal_value(values.get("paymentsreceived")) or Decimal("0")
        adjustments = _parse_decimal_value(values.get("adjustments")) or Decimal("0")
        new_charges = _parse_decimal_value(values.get("newcharges")) or Decimal("0")
        total_amount_due = _parse_decimal_value(values.get("totalamountdue"))
        if total_amount_due is None:
            total_amount_due = previous_balance - payments_received + adjustments + new_charges
        values["previousbalance"] = _format_currency_value(previous_balance)
        values["paymentsreceived"] = _format_currency_value(payments_received)
        values["newcharges"] = _format_currency_value(new_charges)
        if _parse_decimal_value(values.get("adjustments")) is not None:
            values["adjustments"] = _format_currency_value(adjustments)
        else:
            values["adjustments"] = ""
        values["totalamountdue"] = _format_currency_value(total_amount_due)

    elif doc_type_name == "credit note":
        for key in ["amountcredited", "baseamount", "taxrefund", "remainingbalance"]:
            parsed = _parse_decimal_value(values.get(key))
            if parsed is not None:
                values[key] = _format_currency_value(parsed)

    elif doc_type_name == "debit note":
        for key in ["amountcharged", "updatedbalance"]:
            parsed = _parse_decimal_value(values.get(key))
            if parsed is not None:
                values[key] = _format_currency_value(parsed)

    elif doc_type_name == "loan agreement":
        start_date_raw = _safe_text(values.get("startdate")).strip()
        loan_term = _safe_text(values.get("loanterm")).strip().lower()
        if not _safe_text(values.get("maturitydate")).strip() and start_date_raw:
            try:
                start_date = datetime.strptime(start_date_raw, "%Y-%m-%d")
                if "month" in loan_term:
                    months_text = re.findall(r"\d+", loan_term)
                    months = int(months_text[0]) if months_text else 12
                    year = start_date.year + ((start_date.month - 1 + months) // 12)
                    month = ((start_date.month - 1 + months) % 12) + 1
                    day = min(start_date.day, 28)
                    maturity_date = start_date.replace(year=year, month=month, day=day)
                elif "year" in loan_term:
                    years_text = re.findall(r"\d+", loan_term)
                    years = int(years_text[0]) if years_text else 1
                    maturity_date = start_date.replace(year=start_date.year + years)
                elif "day" in loan_term:
                    days_text = re.findall(r"\d+", loan_term)
                    days = int(days_text[0]) if days_text else 30
                    maturity_date = start_date + timezone.timedelta(days=days)
                else:
                    maturity_date = start_date
                values["maturitydate"] = maturity_date.strftime("%Y-%m-%d")
            except Exception:
                pass

    return values


def _flatten_schema_fields(fields):
    for field in fields or []:
        if not isinstance(field, dict):
            continue
        yield field
        children = field.get("children")
        if isinstance(children, list) and children:
            yield from _flatten_schema_fields(children)
        options = field.get("options")
        if isinstance(options, list):
            for opt in options:
                if isinstance(opt, dict) and isinstance(opt.get("children"), list):
                    yield from _flatten_schema_fields(opt["children"])


def _build_schema_parent_map(fields, parent=None, parent_map=None):
    if parent_map is None:
        parent_map = {}
    for field in fields or []:
        if isinstance(field, dict):
            name = field.get("name")
            if name:
                parent_map[name] = parent
            children = field.get("children")
            if isinstance(children, list) and children:
                _build_schema_parent_map(children, parent=field, parent_map=parent_map)
            options = field.get("options")
            if isinstance(options, list):
                for opt in options:
                    if isinstance(opt, dict) and isinstance(opt.get("children"), list):
                        opt_val = opt.get("value", opt.get("label"))
                        for child in opt["children"]:
                            if isinstance(child, dict) and field.get("name") and not child.get("conditions"):
                                child["_option_parent_condition"] = {
                                    "field": field.get("name"),
                                    "operator": "eq",
                                    "value": opt_val,
                                }
                        _build_schema_parent_map(opt["children"], parent=field, parent_map=parent_map)
    return parent_map


def _placeholder_to_key_name(value):
    raw = _safe_text(value).strip().lower()
    return re.sub(r"[^a-z0-9]+", "_", raw).strip("_")


def _infer_dynamic_field_shape(placeholder_label):
    token = _safe_text(placeholder_label).strip().lower()

    if any(word in token for word in ["description", "details", "message", "summary", "notes", "purpose", "scope", "address"]):
        return "text", "textarea", []

    if any(word in token for word in ["date", "deadline", "expiry"]):
        return "date", "input", []

    if any(word in token for word in ["time"]):
        return "time", "input", []

    if any(word in token for word in ["email"]):
        return "email", "input", []

    if any(word in token for word in ["logo", "photo", "picture", "image"]):
        return "image", "image", []

    if any(word in token for word in ["file", "attachment", "document upload", "supporting document"]):
        return "file", "file", []

    if any(word in token for word in ["phone", "mobile", "contact number"]):
        return "tel", "input", []

    if any(word in token for word in ["amount", "price", "cost", "salary", "budget", "total", "tax", "quantity", "number"]):
        return "number", "input", []

    if any(word in token for word in ["status"]):
        return "text", "select", ["Pending", "In Progress", "Completed"]

    if any(word in token for word in ["priority"]):
        return "text", "select", ["Low", "Medium", "High"]

    if any(word in token for word in ["type", "category", "department", "method", "level"]):
        return "text", "select", []

    return "text", "input", []


def _extract_value_from_form_data(data, key_path):
    if not isinstance(data, dict) or not key_path:
        return None

    if key_path in data:
        return data[key_path]

    norm_target = _normalize_template_key(key_path)

    if "." in key_path:
        parts = key_path.split(".")
        curr = data
        found = True
        for part in parts:
            if not isinstance(curr, dict):
                found = False
                break
            norm_p = _normalize_template_key(part)
            if part in curr:
                curr = curr[part]
            else:
                match_val = None
                match_found = False
                for k, v in curr.items():
                    if _normalize_template_key(k) == norm_p:
                        match_val = v
                        match_found = True
                        break
                if match_found:
                    curr = match_val
                else:
                    found = False
                    break
        if found:
            return curr

    def search_dict(d, target):
        for k, v in d.items():
            if _normalize_template_key(k) == target:
                return v
            if isinstance(v, dict):
                res = search_dict(v, target)
                if res is not None:
                    return res
        return None

    return search_dict(data, norm_target)


def _evaluate_single_condition(condition, form_data):
    if not isinstance(condition, dict) or not isinstance(form_data, dict):
        return True

    target_field = condition.get("field")
    if not target_field:
        return True

    operator = (condition.get("operator") or "eq").strip().lower()
    expected_value = condition.get("value")

    actual_value = _extract_value_from_form_data(form_data, target_field)


    if isinstance(expected_value, bool):
        if actual_value is None:
            actual_bool = False
        elif isinstance(actual_value, bool):
            actual_bool = actual_value
        elif isinstance(actual_value, str):
            actual_bool = actual_value.strip().lower() in ("true", "yes", "1")
        else:
            actual_bool = bool(actual_value)

        if operator in ("eq", "equals", "=="):
            return actual_bool == expected_value
        elif operator in ("neq", "not_equals", "!="):
            return actual_bool != expected_value

    if operator in ("eq", "equals", "=="):
        if isinstance(expected_value, str) and isinstance(actual_value, str):
            return actual_value.strip().lower() == expected_value.strip().lower()
        return actual_value == expected_value
    elif operator in ("neq", "not_equals", "!="):
        if isinstance(expected_value, str) and isinstance(actual_value, str):
            return actual_value.strip().lower() != expected_value.strip().lower()
        return actual_value != expected_value
    elif operator == "in":
        if isinstance(expected_value, list):
            return actual_value in expected_value
        return str(actual_value) in str(expected_value)
    elif operator in ("nin", "not_in"):
        if isinstance(expected_value, list):
            return actual_value not in expected_value
        return str(actual_value) not in str(expected_value)
    elif operator == "contains":
        if actual_value is None:
            return False
        return str(expected_value).lower() in str(actual_value).lower()
    elif operator == "is_empty":
        return actual_value is None or str(actual_value).strip() == "" or actual_value == [] or actual_value == {}
    elif operator == "is_not_empty":
        return not (actual_value is None or str(actual_value).strip() == "" or actual_value == [] or actual_value == {})
    elif operator in ("gt", "gte", "lt", "lte"):
        try:
            act_num = float(actual_value)
            exp_num = float(expected_value)
            if operator == "gt": return act_num > exp_num
            if operator == "gte": return act_num >= exp_num
            if operator == "lt": return act_num < exp_num
            if operator == "lte": return act_num <= exp_num
        except (ValueError, TypeError):
            return False

    return True


def _is_field_visible_recursive(field, form_data, parent_map=None):
    if not isinstance(field, dict):
        return True

    opt_cond = field.get("_option_parent_condition")
    if opt_cond and not _evaluate_single_condition(opt_cond, form_data):
        return False

    conditions = field.get("conditions")
    if conditions and isinstance(conditions, list):
        for cond in conditions:
            if not _evaluate_single_condition(cond, form_data):
                return False

    if parent_map:
        field_name = field.get("name")
        parent_field = parent_map.get(field_name)
        if parent_field:
            if not _is_field_visible_recursive(parent_field, form_data, parent_map):
                return False

    return True


def _is_field_visible(field, form_data):
    return _is_field_visible_recursive(field, form_data)


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


def _format_schema_field_node(field):
    if not isinstance(field, dict):
        return None
    name = field.get("name")
    if not name:
        return None

    field_type = field.get("type", "text")
    raw_options = field.get("options")
    options = []
    if isinstance(raw_options, list):
        for opt in raw_options:
            if isinstance(opt, dict):
                opt_copy = dict(opt)
                if isinstance(opt_copy.get("children"), list):
                    opt_copy["children"] = [
                        _format_schema_field_node(ch)
                        for ch in opt_copy["children"]
                        if _format_schema_field_node(ch) is not None
                    ]
                options.append(opt_copy)
            else:
                options.append(str(opt))

    if field_type == "select" or options:
        option = "select"
    elif field_type == "richtext":
        option = "richtext"
    elif field_type == "textarea":
        option = "textarea"
    elif field_type == "checkbox":
        option = "checkbox"
    elif field_type in ("image", "file"):
        option = "file"
    elif field_type == "group":
        option = "group"
    elif field_type == "repeater":
        option = "repeater"
    elif field_type == "signature":
        option = "signature"
    else:
        option = "input"

    raw_children = field.get("children")
    children_nodes = None
    if field_type in ("group", "repeater") and isinstance(raw_children, list):
        children_nodes = []
        for child in raw_children:
            child_node = _format_schema_field_node(child)
            if child_node:
                children_nodes.append(child_node)

    is_required = bool(field.get("is_required", field.get("required", False)))
    min_items = field.get("min_items")
    max_items = field.get("max_items")
    if field_type == "repeater":
        if min_items is not None:
            try:
                if int(min_items) >= 1:
                    is_required = True
            except (ValueError, TypeError):
                pass
        elif is_required:
            min_items = 1

        if is_required and children_nodes:
            _enforce_repeater_children_required(children_nodes)

    has_conditions = bool(field.get("conditions"))
    is_visible = bool(field.get("is_visible", not has_conditions))

    formatting_controls = field.get("formatting_controls")
    if field_type == "richtext" and not formatting_controls:
        formatting_controls = [
            "bold",
            "italic",
            "underline",
            "strike",
            "heading",
            "list",
            "ordered_list",
            "blockquote",
            "link",
            "clean",
        ]

    width = determine_field_width(field)
    placeholder = generate_default_field_placeholder(field)
    position = field.get("position") or width

    node = {
        "key_name": _normalize_template_key(name),
        "name": name,
        "label": field.get("label", name),
        "type": field_type,
        "option": option,
        "options": options,
        "placeholder": placeholder,
        "width": width,
        "is_required": is_required,
        "is_visible": is_visible,
        "conditions": field.get("conditions"),
        "min_items": min_items,
        "max_items": max_items,
        "position": position,
        "order": field.get("order"),
        "section": field.get("section"),
        "children": children_nodes,
    }
    if formatting_controls is not None:
        node["formatting_controls"] = formatting_controls

    return node


def _sort_fields_by_order(fields_list):
    if not isinstance(fields_list, list):
        return fields_list
    def get_order(item):
        o = item.get("order") if isinstance(item, dict) else None
        return o if isinstance(o, int) else 999999
    sorted_list = sorted(fields_list, key=get_order)
    for item in sorted_list:
        if isinstance(item, dict) and isinstance(item.get("children"), list):
            item["children"] = _sort_fields_by_order(item["children"])
    return sorted_list


def _format_repeater_as_html(repeater_name, label, value_list, children_schema=None):
    if not isinstance(value_list, list) or not value_list:
        return ""

    headers = []
    if children_schema and isinstance(children_schema, list):
        for child in children_schema:
            if isinstance(child, dict):
                headers.append((child.get("name"), child.get("label") or child.get("name")))

    if not headers and isinstance(value_list[0], dict):
        for k in value_list[0].keys():
            headers.append((k, k.replace("_", " ").title()))

    if not headers:
        items_html = "".join(f"<li>{escape(_safe_text(v))}</li>" for v in value_list)
        return f"<div><strong>{escape(label)}:</strong><ul>{items_html}</ul></div>"

    th_html = "".join(f'<th style="border: 1px solid #d1d5db; padding: 8px; background-color: #f3f4f6; text-align: left;">{escape(h_label)}</th>' for _, h_label in headers)

    tr_html_list = []
    for item in value_list:
        if isinstance(item, dict):
            tds = "".join(f'<td style="border: 1px solid #d1d5db; padding: 8px;">{escape(_safe_text(item.get(k, "")))}</td>' for k, _ in headers)
            tr_html_list.append(f"<tr>{tds}</tr>")
        else:
            tr_html_list.append(f'<tr><td colspan="{len(headers)}" style="border: 1px solid #d1d5db; padding: 8px;">{escape(_safe_text(item))}</td></tr>')

    table_html = f'''
    <div style="margin: 12px 0;">
      <h4 style="margin-bottom: 6px; font-weight: 600;">{escape(label)}</h4>
      <table style="width: 100%; border-collapse: collapse; margin-top: 4px; font-size: 14px;">
        <thead><tr>{th_html}</tr></thead>
        <tbody>{"".join(tr_html_list)}</tbody>
      </table>
    </div>
    '''
    return table_html.strip()


def _build_dynamic_fields_from_content(content_template, schema_definition=None):
    if schema_definition and isinstance(schema_definition, list) and len(schema_definition) > 0:
        root_nodes = []
        for field in schema_definition:
            node = _format_schema_field_node(field)
            if node:
                root_nodes.append(node)
        return _sort_fields_by_order(root_nodes)

    fields = []
    seen = set()
    for match in PLACEHOLDER_PATTERN.finditer(_safe_text(content_template)):
        raw_token = _get_match_token(match)
        label = _safe_text(raw_token).strip()
        if not label:
            continue
        key_name = _placeholder_to_key_name(label)
        if not key_name or key_name in seen:
            continue
        seen.add(key_name)
        field_type, option, option_values = _infer_dynamic_field_shape(label)
        fields.append(
            {
                "key_name": key_name,
                "name": key_name,
                "label": label,
                "type": field_type,
                "option": option,
                "options": option_values,
                "is_required": False,
                "is_visible": True,
            }
        )
    return fields


def _flatten_data_dict(data, prefix="", result=None):
    if result is None:
        result = {}
    if isinstance(data, dict):
        for k, v in data.items():
            full_key = f"{prefix}.{k}" if prefix else k
            norm_k = _normalize_template_key(k)
            if norm_k and norm_k not in result:
                result[norm_k] = v
            norm_full = _normalize_template_key(full_key)
            if norm_full and norm_full not in result:
                result[norm_full] = v
            if isinstance(v, dict):
                _flatten_data_dict(v, full_key, result)
    return result


def _build_template_value_map(template, form_data):
    raw_data = form_data if isinstance(form_data, dict) else {}
    raw_lookup = _flatten_data_dict(raw_data)


    resolved_values = {}
    placeholder_map = {}
    document_type = getattr(template, "document_type", None)
    schema_definition = getattr(document_type, "schema_definition", None) or []

    for field in _flatten_schema_fields(schema_definition):
        canonical_key = _normalize_template_key(field.get("name"))
        if not canonical_key:
            continue

        placeholder_map[canonical_key] = canonical_key

        label_key = _normalize_template_key(field.get("label"))
        if label_key:
            placeholder_map[label_key] = canonical_key

        placeholder_key = _normalize_template_key(field.get("placeholder"))
        if placeholder_key:
            placeholder_map[placeholder_key] = canonical_key

        value = raw_lookup.get(canonical_key)
        if value is None:
            for alias in (label_key, placeholder_key):
                if alias and alias in raw_lookup:
                    value = raw_lookup[alias]
                    break

        if value is not None:
            resolved_values[canonical_key] = value

    for key, value in raw_lookup.items():
        resolved_values.setdefault(key, value)

    resolved_values = _finance_template_overrides(template, resolved_values)

    return resolved_values, placeholder_map


def _is_image_url_or_data(val):
    if not val or not isinstance(val, str):
        return False
    val_strip = val.strip()
    val_lower = val_strip.lower()
    if val_lower.startswith("data:image/"):
        return True
    img_exts = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico", ".tiff", ".jfif")
    clean_val = val_lower.split("?")[0].split("#")[0]
    if any(clean_val.endswith(ext) for ext in img_exts):
        return True
    if len(val_strip) > 80 and not any(c.isspace() for c in val_strip):
        if val_strip.startswith(("/9j/", "iVBORw", "R0lGOD", "UklGR", "PHN2Zw")):
            return True
    return False


def _is_likely_file_or_image_url(val):
    if not val or not isinstance(val, str):
        return False
    val_strip = val.strip()
    val_lower = val_strip.lower()
    if val_lower.startswith(("data:image/", "data:application/", "data:text/")):
        return True
    if val_lower.startswith(("http://", "https://", "/media/", "media/", "/static/", "static/")):
        return True
    all_exts = (
        ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico", ".tiff", ".jfif",
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt", ".zip", ".tar", ".gz"
    )
    clean_val = val_lower.split("?")[0].split("#")[0]
    if any(clean_val.endswith(ext) for ext in all_exts):
        return True
    if _is_image_url_or_data(val_strip):
        return True
    return False


def _extract_file_url(value):
    if not value:
        return "", False

    url = ""
    is_file_data = False

    if isinstance(value, list) and len(value) > 0:
        return _extract_file_url(value[0])
    elif isinstance(value, dict):
        url = (
            value.get("url")
            or value.get("path")
            or value.get("thumbUrl")
            or value.get("preview")
            or value.get("data")
            or value.get("base64")
            or value.get("fileUrl")
            or value.get("file_url")
            or value.get("src")
            or ""
        )
        if not url and isinstance(value.get("response"), dict):
            url = value["response"].get("url") or value["response"].get("secure_url") or value["response"].get("data") or ""
        if not url and isinstance(value.get("originFileObj"), dict):
            url = value["originFileObj"].get("url") or value["originFileObj"].get("preview") or ""
        if url and isinstance(url, str) and url.strip():
            url = url.strip()
            if _is_image_url_or_data(url) and not url.startswith("data:") and not url.startswith(("http://", "https://", "/")):
                if url.startswith("/9j/"):
                    url = f"data:image/jpeg;base64,{url}"
                elif not any(ext in url.lower() for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp")):
                    url = f"data:image/png;base64,{url}"
            is_file_data = True
    elif isinstance(value, str) and value.strip():
        s = value.strip()
        if _is_likely_file_or_image_url(s):
            url = s
            if _is_image_url_or_data(url) and not url.startswith("data:") and not url.startswith(("http://", "https://", "/")):
                if url.startswith("/9j/"):
                    url = f"data:image/jpeg;base64,{url}"
                elif len(url) > 80 and not any(ext in url.lower() for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp")):
                    url = f"data:image/png;base64,{url}"
            is_file_data = True

    return url, is_file_data


def _render_document_body(template, form_data, document_name=None):
    resolved_values, placeholder_map = _build_template_value_map(template, form_data)
    if document_name:
        for key in {"documentname", "documenttitle", "name"}:
            resolved_values.setdefault(key, _safe_text(document_name))

    document_type = getattr(template, "document_type", None)
    schema_definition = getattr(document_type, "schema_definition", None) or []
    parent_map = _build_schema_parent_map(schema_definition)

    schema_map = {}
    for f in _flatten_schema_fields(schema_definition):
        k = _normalize_template_key(f.get("name"))
        if k:
            schema_map[k] = f

    content_template = (getattr(template, "content_template", None) or "").strip()
    if not content_template:
        lines = []
        for field in _flatten_schema_fields(schema_definition):
            if field.get("type") in ("group", "repeater"):
                if field.get("type") == "repeater" and _is_field_visible_recursive(field, resolved_values, parent_map):
                    field_key = _normalize_template_key(field.get("name"))
                    value = resolved_values.get(field_key, "")
                    label = _safe_text(field.get("label") or field.get("name"))
                    rep_html = _format_repeater_as_html(field.get("name"), label, value, field.get("children"))
                    if rep_html:
                        lines.append(rep_html)
                continue

            if not _is_field_visible_recursive(field, resolved_values, parent_map):
                continue

            field_key = _normalize_template_key(field.get("name"))
            if not field_key:
                continue
            value = resolved_values.get(field_key, "")
            if value is None or (isinstance(value, str) and value.strip() == ""):
                continue
            label = _safe_text(field.get("label") or field.get("name"))

            url, is_file_data = _extract_file_url(value)
            is_image_field = field.get("type") == "image" or any(w in field_key for w in ("image", "photo", "picture", "logo"))
            is_file_field = field.get("type") == "file" or any(w in field_key for w in ("file", "document", "attachment"))
            if (is_image_field or is_file_field or is_file_data) and url:
                is_img = is_image_field or _is_image_url_or_data(url)
                if is_img:
                    lines.append(f"{label}:<br><img src=\"{url}\" alt=\"{escape(label)}\" style=\"max-width: 250px; max-height: 120px; border-radius: 4px; object-fit: contain;\" /><br>")
                else:
                    lines.append(f"{label}: <a href=\"{url}\" target=\"_blank\">View Attached Document: {escape(label)}</a>")
            else:
                lines.append(f"{label}: {_safe_text(value)}")

        if not lines and isinstance(form_data, dict):
            for key, value in form_data.items():
                value_text = _safe_text(value).strip()
                if value_text:
                    lines.append(f"{_safe_text(key)}: {value_text}")

        return "\n".join(lines).strip()

    def replace_placeholder(match):
        raw_token = _get_match_token(match)
        token = _normalize_template_key(raw_token)
        if not token:
            return ""
        canonical_key = placeholder_map.get(token, token)
        value = resolved_values.get(canonical_key, "")

        schema_field = schema_map.get(canonical_key, {})
        if schema_field and not _is_field_visible_recursive(schema_field, resolved_values, parent_map):
            return ""

        field_type = schema_field.get("type", "text")

        if field_type == "repeater" and isinstance(value, list):
            label = schema_field.get("label") or raw_token
            return _format_repeater_as_html(canonical_key, label, value, schema_field.get("children"))

        url, is_file_data = _extract_file_url(value)

        is_image_field = field_type == "image" or any(w in canonical_key for w in ("image", "photo", "picture", "logo"))
        is_file_field = field_type == "file" or any(w in canonical_key for w in ("file", "document", "attachment"))

        if (is_image_field or is_file_field or is_file_data) and url:
            is_img = is_image_field or _is_image_url_or_data(url)
            if is_img:
                return f'<br><img src="{url}" alt="{escape(raw_token)}" style="max-width: 250px; max-height: 120px; border-radius: 4px; object-fit: contain;" /><br>'
            else:
                return f'<a href="{url}" target="_blank">View Attached Document: {escape(raw_token)}</a>'

        return _safe_text(value)

    rendered = PLACEHOLDER_PATTERN.sub(replace_placeholder, content_template)
    lines = []
    for line in rendered.splitlines():
        if re.match(r"^\s*[^:\n<]+:\s*$", line):
            continue
        lines.append(line)
    rendered = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", rendered).strip()


def _find_repeater_ancestor(field_name, parent_map):
    if not parent_map or not field_name:
        return None
    curr = parent_map.get(field_name)
    while curr:
        if isinstance(curr, dict) and curr.get("type") == "repeater":
            return curr
        curr_name = curr.get("name") if isinstance(curr, dict) else None
        curr = parent_map.get(curr_name) if curr_name else None
    return None


def _is_field_in_optional_group(field_name, parent_map):
    curr = parent_map.get(field_name) if parent_map and field_name else None
    while curr and isinstance(curr, dict):
        if curr.get("type") == "repeater":
            break
        if curr.get("type") == "group":
            is_grp_req = bool(curr.get("is_required", curr.get("required", False)))
            if not is_grp_req:
                return True
        curr_name = curr.get("name")
        curr = parent_map.get(curr_name) if curr_name else None
    return False


def _is_repeater_item_non_empty(item):
    if not isinstance(item, dict):
        if item is None:
            return False
        if isinstance(item, str):
            return bool(item.strip())
        return True

    for val in item.values():
        if val is None:
            continue
        if isinstance(val, str) and val.strip():
            return True
        elif isinstance(val, (int, float)) and not isinstance(val, bool):
            return True
        elif isinstance(val, bool) and val:
            return True
        elif isinstance(val, list) and any(_is_repeater_item_non_empty(sub) for sub in val):
            return True
        elif isinstance(val, dict) and _is_repeater_item_non_empty(val):
            return True
    return False


def _missing_required_template_fields(template, form_data):
    resolved_values, _ = _build_template_value_map(template, form_data)
    missing_fields = []
    document_type = getattr(template, "document_type", None)
    schema_definition = getattr(document_type, "schema_definition", None) or []
    parent_map = _build_schema_parent_map(schema_definition)

    for field in _flatten_schema_fields(schema_definition):
        if field.get("type") in ("group", "repeater"):
            continue

        field_name = field.get("name")
        field_key = _normalize_template_key(field_name)
        if not field_key:
            continue

        is_req = field.get("is_required")
        if is_req is None:
            is_req = field.get("required")

        repeater_ancestor = _find_repeater_ancestor(field_name, parent_map)
        if repeater_ancestor:
            rep_min_items = repeater_ancestor.get("min_items")
            rep_is_req = bool(repeater_ancestor.get("is_required", repeater_ancestor.get("required", False)))
            try:
                if rep_min_items is not None and int(rep_min_items) >= 1:
                    rep_is_req = True
            except (ValueError, TypeError):
                pass

            if (
                rep_is_req
                and not field.get("conditions")
                and field.get("type") not in ("checkbox", "file", "image")
                and not _is_field_in_optional_group(field_name, parent_map)
            ):
                is_req = True

        if not is_req:
            continue

        if not _is_field_visible_recursive(field, resolved_values, parent_map):
            continue

        if repeater_ancestor:
            rep_key = _normalize_template_key(repeater_ancestor.get("name"))
            items = resolved_values.get(rep_key)
            if items is None and isinstance(form_data, dict):
                items = form_data.get(repeater_ancestor.get("name")) or form_data.get(rep_key)

            if isinstance(items, list) and items:
                for idx, item_dict in enumerate(items, 1):
                    if not isinstance(item_dict, dict):
                        continue
                    item_val = item_dict.get(field_name)
                    if item_val is None:
                        item_val = item_dict.get(field_key)
                    if item_val is None or (isinstance(item_val, str) and item_val.strip() == "") or item_val == [] or item_val == {}:
                        label = _safe_text(field.get("label") or field_name)
                        err_label = f"{label} (Entry #{idx})" if len(items) > 1 else label
                        if err_label not in missing_fields:
                            missing_fields.append(err_label)
            continue

        value = resolved_values.get(field_key)
        if value is None:
            value = resolved_values.get(field_name)

        if value is None or (isinstance(value, str) and value.strip() == "") or value == [] or value == {}:
            missing_fields.append(_safe_text(field.get("label") or field_name))

    return missing_fields


def _validate_repeater_min_max_items(template, form_data):
    resolved_values, _ = _build_template_value_map(template, form_data)
    validation_errors = []
    document_type = getattr(template, "document_type", None)
    schema_definition = getattr(document_type, "schema_definition", None) or []
    parent_map = _build_schema_parent_map(schema_definition)

    for field in _flatten_schema_fields(schema_definition):
        if field.get("type") != "repeater":
            continue

        if not _is_field_visible_recursive(field, resolved_values, parent_map):
            continue

        field_name = field.get("name")
        field_key = _normalize_template_key(field_name)
        if not field_key:
            continue

        items = resolved_values.get(field_key)
        if items is None and isinstance(form_data, dict):
            items = form_data.get(field_name) or form_data.get(field_key)

        raw_items = items if isinstance(items, list) else []
        valid_items = [it for it in raw_items if _is_repeater_item_non_empty(it)]
        valid_count = len(valid_items)
        raw_count = len(raw_items)

        min_items = field.get("min_items")
        max_items = field.get("max_items")
        is_req = field.get("is_required")
        if is_req is None:
            is_req = field.get("required")

        try:
            if min_items is not None:
                min_items = int(min_items)
        except (ValueError, TypeError):
            min_items = None

        try:
            if max_items is not None:
                max_items = int(max_items)
        except (ValueError, TypeError):
            max_items = None

        if min_items is None and is_req:
            min_items = 1

        label = field.get("label") or field.get("name") or "Repeater"

        if min_items is not None and min_items > 0:
            if valid_count < min_items:
                if valid_count == 0:
                    validation_errors.append(f"'{label}' is required. Please provide at least {min_items} item(s).")
                else:
                    validation_errors.append(f"'{label}' requires at least {min_items} item(s). You provided {valid_count}.")

        if max_items is not None:
            if raw_count > max_items:
                validation_errors.append(f"'{label}' allows at most {max_items} item(s). You provided {raw_count}.")

    return validation_errors


def _wallet_limit_from_subscription(active_subscription):
    if not active_subscription or not active_subscription.subscriptionpackage:
        return FREE_PLAN_ACCESS_LIMIT

    package_downloads = active_subscription.subscriptionpackage.downloads or 1
    return max(1, int(package_downloads))


def _wallet_cycle_days_from_subscription(active_subscription):
    if not active_subscription or not active_subscription.subscriptionpackage:
        return 30

    package = active_subscription.subscriptionpackage
    try:
        billing_days = int(package.get_billing_days() or 0)
    except Exception:
        billing_days = 0

    return billing_days if billing_days > 0 else 30


def _sync_wallet_cycle(wallet, active_subscription):
    now = timezone.now()
    cycle_days = _wallet_cycle_days_from_subscription(active_subscription)

    desired_limit = _wallet_limit_from_subscription(active_subscription)
    if wallet.credits_limit != desired_limit:
        wallet.credits_limit = desired_limit
    if wallet.plan_download_limit != desired_limit:
        wallet.plan_download_limit = desired_limit

    if active_subscription and active_subscription.end_date:
        subscription_cycle_start = active_subscription.start_date or wallet.cycle_start or now
        if wallet.cycle_start != subscription_cycle_start:
            wallet.cycle_start = subscription_cycle_start
        if wallet.cycle_end != active_subscription.end_date:
            wallet.cycle_end = active_subscription.end_date
            wallet.credits_used = 0

    if wallet.cycle_end is None:
        wallet.cycle_start = wallet.cycle_start or now
        wallet.cycle_end = wallet.cycle_start + timezone.timedelta(days=cycle_days)

    if now >= wallet.cycle_end:
        wallet.credits_used = 0
        wallet.cycle_start = now
        wallet.cycle_end = now + timezone.timedelta(days=cycle_days)

    wallet.save(update_fields=["credits_limit", "credits_used", "plan_download_limit", "cycle_start", "cycle_end", "updated_at"])
    return wallet


def _subscription_plan_overview(active_subscription):
    if not active_subscription or not active_subscription.subscriptionpackage:
        return {
            "status": "inactive",
            "name": "Free",
            "downloads": FREE_PLAN_ACCESS_LIMIT,
            "billing_days": None,
            "price": Decimal("0.00"),
        }

    package = active_subscription.subscriptionpackage
    package_data = SubscriptionPackageSerializer(package).data
    return {
        "status": active_subscription.status,
        "name": package.plan_name or package.billing_cycle or "Subscription",
        "downloads": package.downloads,
        "billing_days": package_data.get("billing_days"),
        "price": package.price,
        "next_renewal": active_subscription.end_date,
    }


def _consume_action_credit(user, document, action, metadata=None, allow_repeat=False):
    wallet, _ = CreditWallet.objects.get_or_create(user=user)
    active_subscription = _active_subscription_for_user(user)
    wallet = _sync_wallet_cycle(wallet, active_subscription)

    existing = DocumentAction.objects.filter(user=user, document=document, action=action).first()
    if existing and not allow_repeat:
        return wallet, 0, "already_charged"

    if wallet.credits_remaining < 1:
        return wallet, 0, "insufficient_credits"

    if existing and allow_repeat:
        # Keep unique row per action/document but accumulate credits for repeated usage.
        existing.credit_used = int(existing.credit_used or 0) + 1
        if metadata:
            existing.metadata = metadata
        existing.save(update_fields=["credit_used", "metadata", "updated_at"])
    else:
        DocumentAction.objects.create(
            user=user,
            document=document,
            action=action,
            credit_used=1,
            metadata=metadata or {},
        )
    wallet.credits_used += 1
    wallet.save(update_fields=["credits_used", "updated_at"])
    return wallet, 1, "charged"


def _detect_signature_fields_from_rendered_content(rendered_content, sign_mode="client_only"):
    content = rendered_content or ""
    signature_matches = re.findall(
        r"(?:<strong>\s*Signature:\s*</strong>|Signature:)\s*_+",
        content,
        flags=re.IGNORECASE,
    )

    fields = [f"signature_{index + 1}" for index in range(len(signature_matches))]

    # Fallback if template has no explicit placeholder.
    if not fields:
        if sign_mode == "both":
            fields = ["signature_1", "signature_2"]
        else:
            fields = ["signature_1"]

    return fields


def _signature_fields_for_request(all_fields, signature_request):
    """Return only the subset of signature fields that apply to this specific SignatureRequest.

    Logic:
    - SignatureRequests for a document are ordered by creation time.
    - Detected fields use a numeric suffix (e.g. signature_1, date_1, signature_2).
    - Map the request's position in the request list to the numeric suffix and return only matching fields.
    - Fallback: if mapping fails, return first signature field only.
    """
    if not all_fields:
        return []

    try:
        # Get ordered requests for the same document and determine this request's index
        siblings = list(signature_request.document.signature_requests.order_by("created_at").values_list("id", flat=True))
        idx = siblings.index(signature_request.id)
        target_suffix = str(idx + 1)
    except Exception:
        # If anything goes wrong, default to first signer
        target_suffix = "1"

    selected = []
    for f in all_fields:
        if f.startswith("date"):
            continue
            
        # Match fields that end with _<n>
        m = re.match(r"(.+?)_(\d+)$", f)
        if m:
            if m.group(2) == target_suffix:
                selected.append(f)
        else:
            # include non-suffixed fields only for first signer
            if target_suffix == "1":
                selected.append(f)

    if not selected:
        # fallback to first signature field
        for f in all_fields:
            if f.startswith("signature"):
                selected = [f]
                break

    return selected


def _apply_signature_to_rendered_content(rendered_content, signature_value, date_value=None):
    content = rendered_content or ""
    safe_signature = (signature_value or "").strip()
    safe_date = (date_value or "").strip()

    replaced_sig = 0
    if safe_signature:
        if safe_signature.startswith("data:image/"):
            sig_repr = f'<img src="{safe_signature}" alt="Signature" style="max-height: 50px; max-width: 180px; object-fit: contain; vertical-align: middle;" />'
        else:
            sig_repr = safe_signature

        content, replaced_sig = re.subn(
            r"(<strong>\s*Signature:\s*</strong>\s*)_+",
            lambda m: f"{m.group(1)}{sig_repr}",
            content,
            count=1,
            flags=re.IGNORECASE,
        )
        if replaced_sig == 0:
            content, replaced_sig = re.subn(
                r"(Signature:\s*)_+",
                lambda m: f"{m.group(1)}{sig_repr}",
                content,
                count=1,
                flags=re.IGNORECASE,
            )
        if replaced_sig == 0:
            content, replaced_sig = re.subn(
                r"(<strong>\s*Signature:\s*</strong>\s*)(?!<img)",
                lambda m: f"{m.group(1)}{sig_repr}",
                content,
                count=1,
                flags=re.IGNORECASE,
            )
        if replaced_sig == 0:
            content, replaced_sig = re.subn(
                r"(Signature:\s*)(?!<img)",
                lambda m: f"{m.group(1)}{sig_repr}",
                content,
                count=1,
                flags=re.IGNORECASE,
            )

    if safe_date:
        content, replaced_date = re.subn(
            r"(<strong>\s*Date:\s*</strong>\s*)_+",
            lambda m: f"{m.group(1)}{safe_date}",
            content,
            count=1,
            flags=re.IGNORECASE,
        )
        if replaced_date == 0:
            content, replaced_date = re.subn(
                r"(Date:\s*)_+",
                lambda m: f"{m.group(1)}{safe_date}",
                content,
                count=1,
                flags=re.IGNORECASE,
            )
        if replaced_date == 0:
            content, replaced_date = re.subn(
                r"(<strong>\s*Date:\s*</strong>\s*)(?!\d{4})",
                lambda m: f"{m.group(1)}{safe_date}",
                content,
                count=1,
                flags=re.IGNORECASE,
            )
        if replaced_date == 0:
            content, replaced_date = re.subn(
                r"(Date:\s*)(?!\d{4})",
                lambda m: f"{m.group(1)}{safe_date}",
                content,
                count=1,
                flags=re.IGNORECASE,
            )

    # If the template had no signature placeholders, append the signature block at the bottom.
    if safe_signature and replaced_sig == 0:
        sig_html = f"\n<p><strong>Signature:</strong> {sig_repr}<br><strong>Date:</strong> {safe_date}</p>"
        content += sig_html
    return content


def _to_absolute_uri(request, value):
    if not value:
        return None

    if hasattr(value, "url"):
        try:
            value = value.url
        except Exception:
            value = str(value)

    if isinstance(value, str) and (value.startswith("http://") or value.startswith("https://")):
        return value

    try:
        return request.build_absolute_uri(value)
    except Exception:
        return value


def _looks_like_video(value):
    if not value or not isinstance(value, str):
        return False

    lower_value = value.lower()
    return any(token in lower_value for token in ("youtube.com", "youtu.be", ".mp4", ".webm", ".mov", ".m4v"))


def _resolve_cms_video_url(request, section):
    video_link = getattr(section, "video_link", None)
    if video_link:
        if isinstance(video_link, str) and video_link.strip():
            return video_link.strip()

        resolved_video_link = _to_absolute_uri(request, video_link)
        if isinstance(resolved_video_link, str) and resolved_video_link.strip():
            return resolved_video_link.strip()

    file_url = getattr(section, "file_url", None)
    if file_url:
        raw_file_url = getattr(file_url, "name", None) or str(file_url)
        if isinstance(raw_file_url, str) and _looks_like_video(raw_file_url):
            return raw_file_url.strip()

        return _to_absolute_uri(request, file_url)

    return None


def _preview_sample_items_from_cms_section(request, section):
    items = []
    for order, field_name in enumerate(("preview_image_1", "preview_image_2", "preview_image_3"), start=1):
        image = getattr(section, field_name, None)
        if not image:
            continue

        items.append(
            {
                "title": section.title or f"Preview Sample {order}",
                "image": _to_absolute_uri(request, image.url),
                "order": order,
            }
        )

    return items


# Keep section payload clean by exposing media only where the landing UI needs it.
SECTION_MEDIA_RULES = {
    "what_is_formexl": {"allow_image": False, "allow_video": False, "allow_file": False},
    "what_formexl_is": {"allow_image": False, "allow_video": False, "allow_file": False},
    "what_formexl_is_not": {"allow_image": False, "allow_video": False, "allow_file": False},
    "how_it_works": {"allow_image": False, "allow_video": False, "allow_file": False},
    "watch_video": {"allow_image": True, "allow_video": True, "allow_file": False},
    "preview_samples": {"allow_image": False, "allow_video": False, "allow_file": False},
    "faq": {"allow_image": True, "allow_video": False, "allow_file": False},
    "trusted_professionals": {"allow_image": False, "allow_video": False, "allow_file": False},
    "secure_checkout": {"allow_image": False, "allow_video": False, "allow_file": False},
    "cta_free_downloads": {"allow_image": False, "allow_video": False, "allow_file": False},
    "footer": {"allow_image": False, "allow_video": False, "allow_file": False},
    "document_categories": {"allow_image": False, "allow_video": False, "allow_file": False},
    "pricing_header": {"allow_image": False, "allow_video": False, "allow_file": False},
    "formexl_engineered": {"allow_image": True, "allow_video": False, "allow_file": False},
}


def _normalize_section_media(section_payload):
    key = str(section_payload.get("section") or "").strip().lower()
    rules = SECTION_MEDIA_RULES.get(key)
    if not rules:
        return section_payload

    if not rules.get("allow_image", False):
        section_payload["image"] = None
    if not rules.get("allow_video", False):
        section_payload["video_url"] = None
    if not rules.get("allow_file", False):
        section_payload["file_url"] = None

    return section_payload


def _prune_empty_response_values(value):
    """Recursively remove null/empty values to keep landing API payload clean."""
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            pruned_item = _prune_empty_response_values(item)
            if pruned_item is None:
                continue
            if isinstance(pruned_item, str) and not pruned_item.strip():
                continue
            if isinstance(pruned_item, (list, dict)) and not pruned_item:
                continue
            cleaned[key] = pruned_item
        return cleaned or None

    if isinstance(value, list):
        cleaned_list = []
        for item in value:
            pruned_item = _prune_empty_response_values(item)
            if pruned_item is None:
                continue
            if isinstance(pruned_item, str) and not pruned_item.strip():
                continue
            if isinstance(pruned_item, (list, dict)) and not pruned_item:
                continue
            cleaned_list.append(pruned_item)
        return cleaned_list or None

    return value


SECTION_RESPONSE_FIELDS = {
    "watch_video": ["section", "title", "sub_title", "image", "video_url"],
    "how_it_works": ["section", "title", "sub_title", "items"],
    "preview_samples": ["section", "title", "sub_title", "items"],
    "faq": ["section", "title", "sub_title", "image", "items"],
    "formexl_engineered": ["section", "title", "sub_title", "description", "image"],
    "document_categories": ["section", "title", "sub_title", "items"],
    "trusted_professionals": ["section", "title", "sub_title", "items"],
    "pricing_header": ["section", "title", "sub_title", "items"],
    "secure_checkout": ["section", "title", "sub_title", "items"],
    "cta_free_downloads": ["section", "title", "sub_title", "other"],
    "footer": ["section", "title", "sub_title"],
}


SECTION_ITEM_RESPONSE_FIELDS = {
    "how_it_works": ["title", "description"],
    "preview_samples": ["title", "image"],
    "faq": ["question", "answer"],
    "document_categories": ["name", "slug", "description", "icon", "template_count", "is_recommended", "is_popular"],
    "trusted_professionals": ["name", "role", "rating", "comment", "avatar"],
    "secure_checkout": ["name", "logo"],
}


WHAT_FORMEXL_ITEM_POINTS = {
    "what_formexl_is": [
        "A structured platform for generating professional business documents using guided templates.",
        "A streamlined workflow that eliminates formatting errors and manual editing.",
        "A system designed for businesses to produce consistent, polished documents instantly.",
        "Built for speed, accuracy, and repeatable document generation across categories.",
        "Most templates online are generic. Formexl generates structured documents designed for real business use.",
    ],
    "what_formexl_is_not": [
        "Not a messy copy-and-paste editor like Word or Google Docs.",
        "Not a basic template download site with low-quality formatting.",
        "Not a generic form builder with unprofessional output.",
        "Not a tool that requires manual formatting or rewriting.",
    ],
}


def _pick_fields(payload, allowed_fields):
    return {field: payload.get(field) for field in allowed_fields if field in payload}


# def _shape_section_payload_for_response(section_key, payload):
#     allowed_fields = SECTION_RESPONSE_FIELDS.get(section_key)
#     if allowed_fields:
#         shaped = _pick_fields(payload, allowed_fields)
#     else:
#         shaped = dict(payload)

#     shaped.pop("order", None)

#     items = shaped.get("items")
#     if not isinstance(items, list):
#         return shaped

#     item_fields = SECTION_ITEM_RESPONSE_FIELDS.get(section_key)
#     if item_fields:
#         shaped["items"] = [_pick_fields(item, item_fields) for item in items if isinstance(item, dict)]
#     else:
#         shaped["items"] = [item for item in items if isinstance(item, dict)]

#     if section_key == "what_is_formexl":
#         for item in shaped["items"]:
#             item_key = str(item.get("section") or "").strip().lower()
#             points = WHAT_FORMEXL_ITEM_POINTS.get(item_key)
#             if points:
#                 item["points"] = points

#     if section_key in {"what_is_formexl", "how_it_works", "preview_samples", "faq", "document_categories", "trusted_professionals", "pricing_header", "secure_checkout"}:
#         for item in shaped["items"]:
#             item.pop("order", None)

#     return shaped

def _shape_section_payload_for_response(section_key, payload):
    allowed_fields = SECTION_RESPONSE_FIELDS.get(section_key)
    shaped = _pick_fields(payload, allowed_fields) if allowed_fields else dict(payload)

    items = shaped.get("items")
    
    # Handle case where section has single item without "items" list for backward compatibility, but only if it has an "id" to look up points.
    if not items and "id" in shaped:
        items = [shaped]
    elif not isinstance(items, list):
        return shaped

    for item in items:
        cms_id = item.get("id")
        
        is_valid_id = isinstance(cms_id, int) or (isinstance(cms_id, str) and cms_id.isdigit())
        
        if cms_id and is_valid_id:
            
            db_points = CMSPoint.objects.filter(cms_id=cms_id).values_list('text', flat=True)
            
            if db_points.exists():
                item["points"] = list(db_points)
            else:
                item["points"] = []
        else:
            
            if "points" not in item: 
                item["points"] = []

    
    for item in items:
        item.pop("order", None)

    return shaped
# def _shape_section_payload_for_response(section_key, payload):
#     allowed_fields = SECTION_RESPONSE_FIELDS.get(section_key)
#     shaped = _pick_fields(payload, allowed_fields) if allowed_fields else dict(payload)

#     items = shaped.get("items")
    
#     if not items and "id" in shaped:
#         items = [shaped]
#     elif not isinstance(items, list):
#         return shaped

#     # 
#     for item in items:
#         cms_id = item.get("id")
#         if cms_id:
            
#             db_points = CMSPoint.objects.filter(cms_id=cms_id).values_list('text', flat=True)
            
#             if db_points.exists():
#                 item["points"] = list(db_points)
#             else:
                
#                 item["points"] = []

#     for item in items:
#         item.pop("order", None)

#     return shaped


def _build_landing_overview_data(request):
    about_system = AboutSystem.objects.first()

    categories = TemplateCategory.objects.filter(
        is_active=True,
        template_count__gt=0,
    )
    faqs = FAQ.objects.filter(status=True)[:10]
    landing_sections_qs = LandingPageSection.objects.filter(
        is_active=True,
        page__iexact="landing",
    ).order_by("order", "id")
    cms_sections_qs = CMS.objects.filter(
        status="active",
        page__iexact="landing",
    ).order_by("id")

    hero = LandingPageHero.objects.filter(is_active=True).first()
    features = LandingPageFeature.objects.filter(is_active=True).order_by("order")
    badges = LandingPageBadge.objects.filter(is_active=True).order_by("order")
    pricing_data = LandingPagePricing.objects.filter(is_active=True).order_by("billing_period", "order")
    preview_samples_qs = LandingPreviewSample.objects.filter(is_active=True).order_by("order", "id")
    testimonials_qs = LandingTestimonial.objects.filter(is_active=True).order_by("order", "id")
    feedback_qs = DocumentFeedback.objects.filter(is_public=True, document__isnull=False).select_related("user", "document").order_by("-created_at")[:6]
    checkout_brands_qs = LandingCheckoutBrand.objects.filter(is_active=True).order_by("order", "id")

    category_data = TemplateCategorySerializer(categories, many=True).data
    faq_data = [
        {"question": faq.question, "answer": faq.answer}
        for faq in faqs
    ]

    hero_data = {
        "title": hero.title if hero else "Generate professional business documents instantly",
        "subtitle": hero.subtitle if hero else "Structured templates, fast generation, and instant PDF export.",
        "cta_primary": hero.cta_primary if hero else "Get Started Free",
        "cta_secondary": hero.cta_secondary if hero else "View Templates",
    }

    contact_email = (getattr(about_system, "email", None) or "support@formexl.com").strip()
    contact_phone = (getattr(about_system, "contact_phone", None) or "+1 (555) 000-0000").strip()
    contact_address = (getattr(about_system, "office_address", None) or "123 Business Ave, Suite 100\nNew York, NY 10001").strip()
    contact_phone_link = "".join(ch for ch in contact_phone if ch.isdigit() or ch == "+")
    contact_information = {
        "title": "Contact Information",
        "email_label": "Email us at",
        "phone_label": "Call us at",
        "address_label": "Visit our office",
        "email": contact_email,
        "email_link": f"mailto:{contact_email}",
        "phone": contact_phone,
        "phone_link": f"tel:{contact_phone_link}" if contact_phone_link else None,
        "address": contact_address,
        "address_lines": [line.strip() for line in contact_address.splitlines() if line.strip()],
    }

    combined_sections = []
    cms_preview_samples_items = []
    for section in landing_sections_qs:
        payload = {
            "id": section.id,
            "source": "landing_page_section",
            "page": section.page,
            "section": section.section_key,
            "title": section.title,
            "sub_title": section.sub_title,
            "description": section.description,
            "short_description": section.short_description,
            "image": _to_absolute_uri(request, section.image.url) if section.image else None,
            "video_url": section.video_url,
            "file_url": None,
            "button_text": section.button_text,
            "button_link": section.button_link,
            "other": section.other,
            "order": section.order,
        }
        combined_sections.append(_normalize_section_media(payload))

    for section in cms_sections_qs:
        section_key = str(section.section or "").strip().lower()
        resolved_video_url = _resolve_cms_video_url(request, section) if section_key == "watch_video" else _to_absolute_uri(request, section.file_url)
        section_image = section.background_image or section.file_url
        is_video = section_key == "watch_video" or _looks_like_video(section.file_url)
        if section_key == "preview_samples":
            cms_preview_samples_items = _preview_sample_items_from_cms_section(request, section) or cms_preview_samples_items

        # For watch_video, use video_thumbnail if available, otherwise fallback to background_image
        if section_key == "watch_video":
            section_image = section.video_thumbnail or section.background_image
            image_url = _to_absolute_uri(request, section_image)
        else:
            image_url = _to_absolute_uri(request, section.background_image) or (None if is_video else _to_absolute_uri(request, section_image))

        payload = {
            "id": section.id,
            "source": "cms",
            "page": section.page,
            "section": section.section,
            "title": section.title,
            "sub_title": section.sub_title,
            "description": section.description,
            "short_description": section.short_description,
            "image": image_url,
            "video_url": resolved_video_url if is_video else None,
            "file_url": _to_absolute_uri(request, section.file_url),
            "button_text": section.button_text,
            "button_link": section.button_link,
            "other": section.other,
            "order": 0,
        }
        combined_sections.append(_normalize_section_media(payload))

    sections_by_key = {}
    unique_sections_by_key = {}
    for section in combined_sections:
        key = str(section.get("section") or "").strip().lower()
        if not key:
            continue

        sections_by_key.setdefault(key, []).append(section)

        current = unique_sections_by_key.get(key)
        if not current:
            unique_sections_by_key[key] = section
            continue

        current_priority = 2 if current.get("source") == "cms" else 1
        new_priority = 2 if section.get("source") == "cms" else 1
        if new_priority > current_priority or (
            new_priority == current_priority and section.get("order", 0) < current.get("order", 0)
        ):
            unique_sections_by_key[key] = section

    hero_candidates = sections_by_key.get("hero") or []
    hero_section = next(
        (
            item
            for item in hero_candidates
            if item.get("image") or item.get("video_url")
        ),
        hero_candidates[0] if hero_candidates else None,
    )
    if hero_section:
        hero_data["title"] = hero_section.get("title") or hero_data["title"]
        hero_data["subtitle"] = hero_section.get("sub_title") or hero_data["subtitle"]
        hero_data["cta_primary"] = hero_section.get("button_text") or hero_data["cta_primary"]
        hero_data["cta_secondary"] = hero_section.get("other") or hero_data["cta_secondary"]
        hero_data["hero_background_image"] = hero_section.get("image")
        hero_data["hero_media_url"] = hero_section.get("video_url")

    feature_items = [
        {
            "title": f.title,
            "description": f.description,
            "order": f.order,
        }
        for f in features
    ]
    if not feature_items:
        feature_items = [
            {"title": "Choose a category", "description": None, "order": 1},
            {"title": "Pick a template", "description": None, "order": 2},
            {"title": "Fill structured fields", "description": None, "order": 3},
            {"title": "Preview", "description": None, "order": 4},
            {"title": "Download", "description": None, "order": 5},
        ]

    badge_items = [
        {
            "title": b.title,
            "icon": b.icon,
        }
        for b in badges
    ]
    if not badge_items:
        badge_items = [
            {"title": "SSL Secured", "icon": "shield", "order": 1},
            {"title": "Secure Payments", "icon": "card", "order": 2},
            {"title": "Instant PDF Export", "icon": "download", "order": 3},
            {"title": "Cancel Anytime", "icon": "clock", "order": 4},
            {"title": "No Hidden Fees", "icon": "check", "order": 5},
            {"title": "Privacy Protected", "icon": "lock", "order": 6},
        ]

    landing_preview_samples_items = [
        {
            "id": sample.id,
            "title": sample.title,
            "image": _to_absolute_uri(request, sample.image.url) if sample.image else None,
            "order": sample.order,
        }
        for sample in preview_samples_qs
    ]
    preview_samples_items = cms_preview_samples_items or landing_preview_samples_items

    testimonials_items = [
        _feedback_item_from_testimonial(request, item)
        for item in testimonials_qs
    ]
    live_feedback_items = [
        _feedback_item_from_document_feedback(request, item)
        for item in feedback_qs
    ]
    combined_testimonials_items = live_feedback_items + testimonials_items

    checkout_brands = [
        {
            "id": brand.id,
            "name": brand.name,
            "logo": _to_absolute_uri(request, brand.logo.url) if brand.logo else None,
            "order": brand.order,
        }
        for brand in checkout_brands_qs
    ]

    pricing_by_period = {}
    for price_item in pricing_data:
        period = price_item.get_billing_period_display().lower()
        if period not in pricing_by_period:
            pricing_by_period[period] = []

        pricing_by_period[period].append({
            "name": price_item.get_plan_name_display(),
            "price": float(price_item.price),
            "downloads": price_item.downloads,
            "most_popular": price_item.is_popular,
            "save_percent": price_item.save_percent if price_item.save_percent > 0 else None,
            "tagline": price_item.tagline,
            "features": [f.strip() for f in price_item.features.split('\n')] if price_item.features else [],
            "footer_text": price_item.footer_text,
        })

    if not pricing_by_period:
        pricing_by_period = {
            "monthly": [
                {"name": "Free", "price": 0, "downloads": 1},
                {"name": "Starter", "price": 19, "downloads": 15},
                {"name": "Pro", "price": 39.99, "downloads": 60, "most_popular": True},
                {"name": "Business", "price": 99.99, "downloads": 200},
            ],
            "yearly": [
                {"name": "Starter", "price": 182.4, "downloads": 180, "save_percent": 20},
                {"name": "Pro", "price": 383.9, "downloads": 720, "save_percent": 20, "most_popular": True},
                {"name": "Business", "price": 959.9, "downloads": 2400, "save_percent": 20},
            ],
        }

    sections_data = {
        key: value
        for key, value in unique_sections_by_key.items()
        if key != "hero"
    }

    grouped_keys = {
        "what_is_formexl": ["what_formexl_is", "what_formexl_is_not"],
    }

    section_items_map = {
        "how_it_works": feature_items,
        "document_categories": category_data,
        "pricing_header": pricing_by_period,
        "faq": faq_data,
        "preview_samples": preview_samples_items,
        "trusted_professionals": combined_testimonials_items,
        "secure_checkout": checkout_brands,
    }

    consumed_child_keys = set()
    grouped_sections = {}

    for parent_key, child_keys in grouped_keys.items():
        parent_section = sections_data.get(parent_key)
        child_items = [
            sections_data[child_key]
            for child_key in child_keys
            if child_key in sections_data
        ]
        if not parent_section and not child_items:
            continue

        section_payload = dict(parent_section) if parent_section else {"section": parent_key}
        existing_items = section_payload.get("items")
        if not isinstance(existing_items, list):
            existing_items = []
        section_payload["items"] = existing_items + child_items
        grouped_sections[parent_key] = section_payload
        consumed_child_keys.update(child_keys)

    for key, value in sections_data.items():
        if key in consumed_child_keys:
            continue

        section_payload = dict(value)
        mapped_items = section_items_map.get(key)
        if mapped_items is not None:
            section_payload["items"] = mapped_items

        existing = grouped_sections.get(key)
        if existing:
            existing_items = existing.get("items")
            if not isinstance(existing_items, list):
                existing_items = []

            if isinstance(mapped_items, list):
                existing["items"] = existing_items + mapped_items
            elif mapped_items is not None:
                existing["items"] = mapped_items
            grouped_sections[key] = existing
            continue

        grouped_sections[key] = section_payload

    shaped_sections = {
        key: _shape_section_payload_for_response(key, section_payload)
        for key, section_payload in grouped_sections.items()
    }

    response_payload = {
        "landing_page": {
            "hero": hero_data,
            "contact_information": contact_information,
            "secure_badges_items": badge_items,
            "rating_summary": _build_rating_summary(combined_testimonials_items),
            "sections": shaped_sections,
        }
    }
    return _prune_empty_response_values(response_payload) or {"landing_page": {}}


def dashboard_callback(request, context):
    now = timezone.now()

    start_of_month = now.replace(day=1)
    total_subscribers = 20
    total_new_subscriptions = 5
    total_income = 1000

    if now.month == 12:
        start_of_next_month = now.replace(year=now.year + 1, month=1, day=1)
    else:
        start_of_next_month = now.replace(month=now.month + 1, day=1)

    active_system_color = SystemColor.objects.filter(is_active=True).first()
    system_color = active_system_color.code if active_system_color else "#FFA500"

    context.update(
        {
            "system_color": system_color,
            "total_users": User.objects.count(),
            "total_subscriptions": total_subscribers,
            "total_income": total_income,
            "total_new_subscriptions": total_new_subscriptions,
            "current_month_signups": User.objects.filter(
                created_at__gte=start_of_month,
                created_at__lt=start_of_next_month
            ).count(),
            "admins": User.objects.filter(is_staff=True).count(),
            "supper_admins": User.objects.filter(is_superuser=True).count(),
            "data": [
                User.objects.filter(
                    created_at__year=datetime.now().year,
                    created_at__month=m
                ).count() for m in range(1, 13)
            ]
        }
    )

    return context


class LandingOverviewAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    CACHE_KEY = 'landing_page_data_v13'
    CACHE_TIMEOUT = 86400  # 24 hours

    def get(self, request):
        cached_data = None
        try:
            cached_data = cache.get(self.CACHE_KEY)
        except Exception:
            pass

        if cached_data:
            return success(data=cached_data, message="Landing page data fetched successfully.")

        data = _build_landing_overview_data(request)

        try:
            cache.set(self.CACHE_KEY, data, self.CACHE_TIMEOUT)
        except Exception:
            pass

        return success(data=data, message="Landing page data fetched successfully.")


class DashboardOverviewAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        user = request.user
        wallet, _ = CreditWallet.objects.get_or_create(user=user)
        active_subscription = _active_subscription_for_user(user)
        wallet = _sync_wallet_cycle(wallet, active_subscription)
        user_type = "paid" if active_subscription else ("free" if not _has_free_generation_reached(user) else "free_limit_reached")
        dashboard_settings = DashboardSettings.objects.filter(is_active=True).first()

        sidebar_menu = [
            "Templates",
            "Billing & Payments",
            "History",
            "Help Center",
            "Settings",
        ]
        search_placeholder = "Search your templates"
        user_role_label = "Operations Manager"
        credits_text_template = "Credits Remaining {remaining}/{limit}"
        welcome_message = "Welcome to your dashboard!"

        if dashboard_settings:
            if dashboard_settings.sidebar_menu:
                sidebar_menu = [
                    item.strip() for item in dashboard_settings.sidebar_menu.splitlines() if item.strip()
                ] or sidebar_menu
            search_placeholder = dashboard_settings.search_placeholder or search_placeholder
            user_role_label = dashboard_settings.user_role_label or user_role_label
            credits_text_template = dashboard_settings.credits_text_template or credits_text_template
            welcome_message = dashboard_settings.welcome_message or welcome_message

        credits_text = credits_text_template.format(
            remaining=wallet.credits_remaining,
            limit=wallet.credits_limit,
        )

        data = {
            "welcome_message": welcome_message,
            "sidebar_menu": sidebar_menu,
            "topbar": {
                "search_placeholder": search_placeholder,
                "user": {
                    "name": user.email,
                    "role": user_role_label,
                    "avatar": user.avatar.url if user.avatar else None,
                },
            },
            "subscription": {
                **_subscription_plan_overview(active_subscription),
            },
            "user_type": user_type,
            "credits": {
                "remaining": wallet.credits_remaining,
                "limit": wallet.credits_limit,
                "text": credits_text,
            },
        }
        return success(data=data, message="Dashboard overview fetched successfully.")


class TemplateCategoryListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        tab = request.query_params.get("tab", "all")
        queryset = TemplateCategory.objects.filter(is_active=True)

        if tab == "recommended":
            queryset = queryset.filter(is_recommended=True)
        elif tab == "popular":
            queryset = queryset.filter(is_popular=True)
        elif tab == "recent" and request.user.is_authenticated:
            recent_category_ids = list(
                GeneratedDocument.objects.filter(user=request.user)
                .exclude(category__isnull=True)
                .order_by("-generated_at")
                .values_list("category_id", flat=True)[:9]
            )
            queryset = queryset.filter(id__in=recent_category_ids)
        serializer = TemplateCategorySerializer(queryset, many=True)
        # By default do not include the 'All Categories' placeholder unless explicitly requested
        include_all = request.query_params.get("include_all", "false").lower() not in ("0", "false", "no")
        data = serializer.data
        if include_all:
            all_item = {"id": 0, "name": "All Categories", "slug": "all", "description": None, "icon": None, "template_count": 0, "is_recommended": False, "is_popular": False}
            data = [all_item] + data

        return success(data=data, message="Template categories fetched successfully.")


class DocumentTypeListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        category_id = request.query_params.get("category_id")
        if not category_id:
            return error(message="category_id is required.")

        queryset = DocumentType.objects.filter(category_id=category_id, is_active=True).order_by("name")
        from .serializers import DocumentTypeSerializer
        data = DocumentTypeSerializer(queryset, many=True).data
        return success(data=data, message="Document types fetched successfully.")


class CategorySearchAPIView(APIView):
    """
    Search template categories by name, description, or slug.
    Supports filtering by status (recommended, popular).
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        search_query = request.query_params.get("q", "").strip()
        filter_type = request.query_params.get("filter", "all")  # all, recommended, popular
        limit = request.query_params.get("limit", 10)

        try:
            limit = int(limit)
            if limit <= 0 or limit > 100:
                limit = 10
        except (ValueError, TypeError):
            limit = 10

        queryset = TemplateCategory.objects.filter(is_active=True)

        # Apply search filter
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(slug__icontains=search_query)
            )

        # Apply category type filter
        if filter_type == "recommended":
            queryset = queryset.filter(is_recommended=True)
        elif filter_type == "popular":
            queryset = queryset.filter(is_popular=True)

        # Order by relevance (name match first, then by sort_order)
        queryset = queryset.order_by("sort_order", "name")

        # Apply limit
        queryset = queryset[:limit]

        serializer = TemplateCategorySerializer(queryset, many=True)
        return success(
            data=serializer.data,
            message=f"Found {len(serializer.data)} categor{'y' if len(serializer.data) == 1 else 'ies'} matching '{search_query}'." if search_query else "Categories fetched successfully."
        )

class TemplateListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        document_type_id = request.query_params.get("document_type_id")
        if not document_type_id:
            return error(message="document_type_id is required.")

        queryset = DocumentTemplate.objects.filter(document_type_id=document_type_id, is_active=True).order_by("name")
        from .serializers import DocumentTemplateSerializer
        data = DocumentTemplateSerializer(queryset, many=True).data
        return success(data=data, message="Templates fetched successfully.")


class TemplateFormSchemaAPIView(APIView):
    
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        template_id = request.query_params.get("template_id")
        if not template_id:
            return error(message="template_id is required.")

        template = (
            DocumentTemplate.objects.filter(id=template_id, is_active=True)
            .select_related("document_type", "document_type__category")
            .first()
        )
        if not template:
            return error(message="Template not found.", status_code=404)

        schema_definition = getattr(template.document_type, "schema_definition", None) if template.document_type else None
        dynamic_fields = _build_dynamic_fields_from_content(template.content_template, schema_definition)
        
        structure = _resolve_document_structure(template)
        structure_data = None
        if structure:
            structure_data = {
                "id": structure.id,
                "name": structure.name,
                "has_header": structure.has_header,
                "has_footer": structure.has_footer,
                "has_signature_section": structure.has_signature_section,
                "has_date_field": structure.has_date_field,
                "has_page_numbers": structure.has_page_numbers,
                "left_margin_mm": structure.left_margin_mm,
                "right_margin_mm": structure.right_margin_mm,
                "top_margin_mm": structure.top_margin_mm,
                "bottom_margin_mm": structure.bottom_margin_mm,
                "line_spacing": float(structure.line_spacing),
                "logo_width_mm": structure.logo_width_mm,
            }

        data = {
            "template_id": template.id,
            "template_name": template.name,
            "content": render_text_as_html(template.content_template),
            "structure": structure_data,
            "fields": dynamic_fields,
            "submit_contract": {
                "endpoint": "/api/documents/generate/",
                "method": "POST",
                "payload": {
                    "template_id": template.id,
                    "name": "string",
                    "form_data": "object",
                },
            },
        }

        from .serializers import remove_legacy_required_keys
        return success(data=remove_legacy_required_keys(data), message="Template dynamic form fields fetched successfully.")


def _handle_request_files_for_form(request, form_data, schema_definition=None):
    if not hasattr(request, "FILES") or not request.FILES:
        return form_data

    from django.core.files.storage import default_storage
    import uuid

    if not isinstance(form_data, dict):
        form_data = {}

    for key, uploaded_file in request.FILES.items():
        if not uploaded_file:
            continue
        try:
            ext = os.path.splitext(uploaded_file.name)[1]
            saved_name = f"doc_{uuid.uuid4().hex[:12]}{ext}"
            rel_path = os.path.join("document_uploads", saved_name).replace("\\", "/")
            saved_path = default_storage.save(rel_path, uploaded_file)
            file_url = f"{settings.MEDIA_URL}{saved_path}".replace("//", "/")
        except Exception:
            continue

        clean_key = key.replace("[", ".").replace("]", "").strip()
        key_parts = [p for p in clean_key.split(".") if p]
        leaf_name = key_parts[-1] if key_parts else clean_key

        # Top level keys
        form_data[key] = file_url
        if clean_key != key:
            form_data[clean_key] = file_url
        if leaf_name not in form_data:
            form_data[leaf_name] = file_url

        # Deep path if key has dots/brackets
        if len(key_parts) > 1:
            curr = form_data
            for part in key_parts[:-1]:
                if isinstance(curr, dict):
                    curr = curr.setdefault(part, {})
            if isinstance(curr, dict):
                curr[key_parts[-1]] = file_url

        # Recursively update any matching key in form_data
        matched = False
        def _recurse(d):
            nonlocal matched
            if isinstance(d, dict):
                for k, v in list(d.items()):
                    if k in (leaf_name, clean_key, key):
                        d[k] = file_url
                        matched = True
                    elif isinstance(v, (dict, list)):
                        _recurse(v)
            elif isinstance(d, list):
                for item in d:
                    _recurse(item)

        _recurse(form_data)

        # Match against schema definition if not matched yet
        if not matched and schema_definition:
            norm_leaf = _normalize_template_key(leaf_name)
            for f in _flatten_schema_fields(schema_definition):
                if f.get("type") in ("image", "file"):
                    f_name = f.get("name")
                    if f_name == leaf_name or _normalize_template_key(f_name) == norm_leaf:
                        def _assign_field(d):
                            if isinstance(d, dict):
                                for k, v in list(d.items()):
                                    if k == f_name:
                                        d[k] = file_url
                                    elif isinstance(v, (dict, list)):
                                        _assign_field(v)
                            elif isinstance(d, list):
                                for item in d:
                                    _assign_field(item)
                        _assign_field(form_data)
                        break

    return form_data


class GenerateDocumentAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        serializer = GenerateDocumentSerializer(data=request.data)
        if not serializer.is_valid():
            return error(message="Invalid input.", errors=serializer.errors)

        user = request.user
        active_subscription = _active_subscription_for_user(user)
        template = DocumentTemplate.objects.filter(
            id=serializer.validated_data["template_id"],
            is_active=True,
        ).select_related("document_type", "document_type__category").first()
        if not template:
            return error(message="Template not found.", status_code=404)

        if not active_subscription and _has_free_generation_reached(user):
            return error(
                message="Free plan allows only 1 document generation. Please upgrade to generate more documents.",
                errors="Subscription required for additional document generation.",
                status_code=402,
            )

        wallet, _ = CreditWallet.objects.get_or_create(user=user)
        wallet = _sync_wallet_cycle(wallet, active_subscription)

        form_data = serializer.validated_data["form_data"]
        schema_definition = getattr(getattr(template, "document_type", None), "schema_definition", None) or []
        form_data = _handle_request_files_for_form(request, form_data, schema_definition=schema_definition)
        serializer.validated_data["form_data"] = form_data
        raw_payload = json.dumps(form_data, sort_keys=True, separators=(",", ":"))
        fingerprint = hashlib.sha256(
            f"{user.id}:{template.id}:{raw_payload}".encode("utf-8")
        ).hexdigest()

        # Prevent duplicate double-click generation for the same template+form payload.
        rate_window_start = timezone.now() - timezone.timedelta(seconds=30)
        recent_duplicate = GeneratedDocument.objects.filter(
            user=user,
            template=template,
            input_fingerprint=fingerprint,
            generated_at__gte=rate_window_start,
        ).first()
        if recent_duplicate:
            # Reuse duplicate but still charge 1 credit for generation
            credits_charged = 0

            if wallet.credits_remaining < 1:
                return error(
                    message="Insufficient credits. Please upgrade your plan.",
                    errors="No credits available for document generation.",
                    status_code=402,
                )
            wallet.credits_used += 1
            wallet.save(update_fields=["credits_used", "updated_at"])
            credits_charged = 1
            
            document_data = GeneratedDocumentSerializer(recent_duplicate).data
            return success(
                data={
                    "id": document_data.get("id"),
                    "rendered_content": document_data.get("rendered_content"),
                    "credit_used": recent_duplicate.credit_used,
                    "generated_at": recent_duplicate.generated_at,
                    "preview_url": _build_authenticated_document_url(recent_duplicate.id, "preview", request),
                    "download_url": _build_authenticated_document_url(recent_duplicate.id, "download", request),
                },
                message="Recent generated document reused.",
            )

        structure = _resolve_document_structure(
            template,
            serializer.validated_data.get("structure_id"),
        )
        missing_fields = _missing_required_template_fields(template, serializer.validated_data["form_data"])
        repeater_errors = _validate_repeater_min_max_items(template, serializer.validated_data["form_data"])

        if missing_fields or repeater_errors:
            combined_errors = [f"{field} is required." for field in missing_fields] + repeater_errors
            msg = combined_errors[0] if combined_errors else "Validation failed."

            return error(
                message=msg,
                errors={"form_data": combined_errors},
                status_code=400,
            )

        rendered_content = _render_document_body(
            template,
            form_data,
            document_name=serializer.validated_data["name"],
        )

        # Consume 1 credit for document generation.
        credits_charged = 0

        if wallet.credits_remaining < 1:
            return error(
                message="Insufficient credits. Please upgrade your plan.",
                errors="No credits available for document generation.",
                status_code=402,
            )
        wallet.credits_used += 1
        wallet.save(update_fields=["credits_used", "updated_at"])
        credits_charged = 1

        document = GeneratedDocument.objects.create(
            user=user,
            category=template.document_type.category,
            document_type=template.document_type,
            template=template,
            structure=structure,
            name=serializer.validated_data["name"],
            form_data=form_data,
            input_fingerprint=fingerprint,
            rendered_content=rendered_content,
            status="active",
            credit_used=credits_charged,
        )

        branding = CompanyBranding.objects.filter(user=user).first()
        build_pdf_for_document(document=document, branding=branding)

        template.usage_count += 1
        template.save(update_fields=["usage_count"])

        if structure:
            structure.usage_count += 1
            structure.save(update_fields=["usage_count", "updated_at"])

        document_data = GeneratedDocumentSerializer(document).data
        return success(
            data={
                "id": document_data.get("id"),
                "rendered_content": document_data.get("rendered_content"),
                "credit_used": document.credit_used,
                "generated_at": document.generated_at,
                "preview_url": _build_authenticated_document_url(document.id, "preview", request),
                "download_url": _build_authenticated_document_url(document.id, "download", request),
            },
            message="Document generated successfully.",
            status_code=201,
        )


class DocumentFeedbackCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, document_id):
        document = GeneratedDocument.objects.filter(id=document_id, user=request.user).first()
        if not document:
            return error(message="Document not found.", status_code=404)

        serializer = DocumentFeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        feedback, _ = DocumentFeedback.objects.update_or_create(
            document=document,
            defaults={
                "user": request.user,
                "rating": serializer.validated_data["rating"],
                "comment": (serializer.validated_data.get("comment") or "").strip(),
                "is_public": True,
            },
        )

        try:
            cache.delete_many([LandingOverviewAPIView.CACHE_KEY])
        except Exception:
            pass

        landing_data = _build_landing_overview_data(request)
        return success(
            data={
                "feedback": {
                    "id": feedback.id,
                    "document_id": document.id,
                    "rating": feedback.rating,
                    "comment": feedback.comment,
                },
                "landing_page": landing_data.get("landing_page", {}),
            },
            message="Feedback saved successfully.",
            status_code=201,
        )


class DocumentPreviewAPIView(APIView):

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, document_id):
        document = GeneratedDocument.objects.filter(id=document_id, user=request.user).first()
        if not document:
            return error(message="Document not found.", status_code=404)

        document.previewed_at = timezone.now()
        document.save(update_fields=["previewed_at", "updated_at"])
        data = GeneratedDocumentSerializer(document).data
        data["like_what_you_see"] = {
            "create_copy_available": True,
            "copy_endpoint": f"/api/documents/{document.id}/copy/",
        }
        data["pdf"] = {
            "preview_url": _build_authenticated_document_url(document.id, "preview", request),
            "download_url": _build_authenticated_document_url(document.id, "download", request),
        }
        return success(data=data, message="Document preview fetched successfully.")


class DocumentDownloadAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, document_id):
        document = GeneratedDocument.objects.filter(id=document_id, user=request.user).first()
        if not document:
            return error(message="Document not found.", status_code=404)

        abs_path, rel_path = build_pdf_for_document(
            document=document,
            branding=CompanyBranding.objects.filter(user=request.user).first(),
        )
        if not os.path.exists(abs_path):
            return error(message="PDF generation failed.", status_code=500)

        document.downloaded_at = timezone.now()
        document.save(update_fields=["downloaded_at", "updated_at"])

        inline = str(request.query_params.get("inline", "false")).lower() in ("1", "true", "yes")
        response = FileResponse(open(abs_path, "rb"), content_type="application/pdf")
        disposition = "inline" if inline else "attachment"
        response["Content-Disposition"] = f'{disposition}; filename="{document.name}.pdf"'
        response["X-Document-Path"] = rel_path
        return response


class PublicDocumentAccessAPIView(APIView):
    permission_classes = []
    authentication_classes = []

    def get(self, request):
        access_key = request.query_params.get("access_key")
        if not access_key:
            return error(message="access_key is required.", status_code=400)

        # Query parsing can transform special chars (e.g. '+' to space).
        access_key = unquote(access_key).strip().replace(" ", "+")

        try:
            payload = signing.loads(
                access_key,
                salt="dashboard.document.access",
                max_age=SIGNED_LINK_MAX_AGE_SECONDS,
            )
        except signing.SignatureExpired:
            return error(message="Access link expired.", status_code=400)
        except signing.BadSignature:
            return error(message="Invalid or expired access link.", status_code=400)

        document_id = payload.get("document_id")
        purpose = payload.get("purpose", "download")
        if not document_id:
            return error(message="Invalid access payload.", status_code=400)

        document = GeneratedDocument.objects.filter(id=document_id).first()
        if not document:
            return error(message="Document not found.", status_code=404)

        abs_path, rel_path = build_pdf_for_document(
            document=document,
            branding=CompanyBranding.objects.filter(user=document.user).first(),
        )
        if not os.path.exists(abs_path):
            return error(message="PDF generation failed.", status_code=500)

        inline_q = str(request.query_params.get("inline", "false")).lower() in ("1", "true", "yes")
        inline = inline_q or purpose == "preview"
        disposition = "inline" if inline else "attachment"

        response = FileResponse(open(abs_path, "rb"), content_type="application/pdf")
        response["Content-Disposition"] = f'{disposition}; filename="{document.name}.pdf"'
        response["X-Document-Path"] = rel_path
        return response


class DocumentEditAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def put(self, request, document_id):
        document = GeneratedDocument.objects.filter(id=document_id, user=request.user).first()
        if not document:
            return error(message="Document not found.", status_code=404)

        form_data = request.data.get("form_data")
        name = request.data.get("name")
        if isinstance(form_data, str):
            try:
                import json
                form_data = json.loads(form_data)
            except Exception:
                pass

        if form_data is not None:
            schema_definition = getattr(getattr(document.template, "document_type", None), "schema_definition", None) or []
            form_data = _handle_request_files_for_form(request, form_data, schema_definition=schema_definition)
            missing_fields = _missing_required_template_fields(document.template, form_data)
            repeater_errors = _validate_repeater_min_max_items(document.template, form_data)
            if missing_fields or repeater_errors:
                combined_errors = [f"{field} is required." for field in missing_fields] + repeater_errors
                msg = combined_errors[0] if combined_errors else "Validation failed."

                return error(
                    message=msg,
                    errors={"form_data": combined_errors},
                    status_code=400,
                )

            document.form_data = form_data
            document.rendered_content = _render_document_body(
                document.template,
                form_data,
                document_name=document.name,
            )
        if name:
            document.name = name
            if form_data is None:
                document.rendered_content = _render_document_body(
                    document.template,
                    document.form_data,
                    document_name=document.name,
                )
        document.save()

        branding = CompanyBranding.objects.filter(user=request.user).first()
        build_pdf_for_document(document=document, branding=branding)

        return success(data=GeneratedDocumentSerializer(document).data, message="Document updated successfully.")


class DocumentHistoryAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        history_type = (request.query_params.get("type") or "document").lower()
        category_id = request.query_params.get("category_id")
        status_filter = request.query_params.get("status")
        search = request.query_params.get("search")
        return _build_document_history_response(
            request,
            history_type=history_type,
            category_id=category_id,
            status_filter=status_filter,
            search=search,
        )


class DocumentHistoryByCategoryAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        category_name = request.query_params.get("category_name")
        if not category_name:
            return error(message="category_name is required.", status_code=400)

        history_type = (request.query_params.get("type") or "document").lower()
        status_filter = request.query_params.get("status")
        search = request.query_params.get("search")

        return _build_document_history_response(
            request,
            history_type=history_type,
            category_name=category_name,
            status_filter=status_filter,
            search=search,
        )


class DocumentHistoryDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def delete(self, request, document_id):
        document = GeneratedDocument.objects.filter(id=document_id, user=request.user).first()
        if not document:
            return error(message="Document not found.", status_code=404)

        document.delete()
        return success(message="Document deleted successfully.")


class DocumentStructureListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        queryset = DocumentStructure.objects.filter(is_active=True).order_by("structure_type", "name")
        serializer = DocumentStructureSerializer(queryset, many=True)
        return success(data=serializer.data, message="Document structures fetched successfully.")

    def post(self, request):
        serializer = DocumentStructureSerializer(data=request.data)
        if not serializer.is_valid():
            return error(message="Invalid structure data.", errors=serializer.errors)

        structure = serializer.save()
        return success(
            data=DocumentStructureSerializer(structure).data,
            message="Document structure created successfully.",
            status_code=201,
        )


class DocumentStructureDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, structure_id):
        structure = DocumentStructure.objects.filter(id=structure_id).first()
        if not structure:
            return error(message="Structure not found.", status_code=404)
        return success(data=DocumentStructureSerializer(structure).data, message="Document structure fetched successfully.")

    def patch(self, request, structure_id):
        structure = DocumentStructure.objects.filter(id=structure_id).first()
        if not structure:
            return error(message="Structure not found.", status_code=404)

        serializer = DocumentStructureSerializer(structure, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(message="Invalid structure data.", errors=serializer.errors)

        serializer.save()
        return success(data=serializer.data, message="Document structure updated successfully.")


class DocumentSchemaListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        queryset = DocumentSchema.objects.select_related("structure").order_by("id")
        serializer = DocumentSchemaSerializer(queryset, many=True)
        return success(data=serializer.data, message="Document schemas fetched successfully.")


class DocumentSchemaDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, schema_id):
        schema = DocumentSchema.objects.select_related("structure").filter(id=schema_id).first()
        if not schema:
            return error(message="Schema not found.", status_code=404)
        return success(data=DocumentSchemaSerializer(schema).data, message="Document schema fetched successfully.")

    def patch(self, request, schema_id):
        schema = DocumentSchema.objects.select_related("structure").filter(id=schema_id).first()
        if not schema:
            return error(message="Schema not found.", status_code=404)

        serializer = DocumentSchemaSerializer(schema, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(message="Invalid schema data.", errors=serializer.errors)

        serializer.save()
        return success(data=serializer.data, message="Document schema updated successfully.")


class SendDocumentEmailAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, document_id):
        # Support both 'recipient_emails' (list) and 'recipient_email' (string)
        emails_raw = request.data.get("recipient_emails") or request.data.get("recipient_email")
        
        if isinstance(emails_raw, str):
            # If it's a comma-separated string or single string
            emails_raw = [e.strip() for e in emails_raw.split(",")]
        elif not isinstance(emails_raw, list):
            emails_raw = []

        # Filter out empty strings and remove duplicates while preserving order
        email_list = []
        for e in emails_raw:
            clean_email = str(e).strip()
            if clean_email and clean_email not in email_list:
                email_list.append(clean_email)

        if not email_list:
            return error(message="recipient_emails (or recipient_email) is required.")

        document = GeneratedDocument.objects.filter(id=document_id, user=request.user).first()
        if not document:
            return error(message="Document not found.", status_code=404)

        _, _, charge_status = _consume_action_credit(
            user=request.user,
            document=document,
            action="send_email",
            metadata={"recipient_emails": email_list},
        )
        if charge_status == "insufficient_credits":
            return error(message="Insufficient credits. Please upgrade your plan.", status_code=402)

        abs_path, _ = build_pdf_for_document(
            document=document,
            branding=CompanyBranding.objects.filter(user=request.user).first(),
        )
        if not os.path.exists(abs_path):
            return error(message="PDF generation failed.", status_code=500)

        with open(abs_path, "rb") as f:
            pdf_content = f.read()

        # Build email message with proper formatting
        profile = getattr(request.user, 'user_profile', None)
        sender_name = ""
        if profile and (profile.first_name or profile.last_name):
            sender_name = f"{profile.first_name} {profile.last_name}".strip()
        sender_name = sender_name or request.user.email
        custom_message = request.data.get("message") or "Please find the attached document."
        
        email_body = f"""
Hello,

{sender_name} has sent you a document: <strong>{document.name}</strong>

Message:
{custom_message}

Document Details:
- Type: {document.document_type.name if document.document_type else 'General'}
- Category: {document.category.name if document.category else 'Uncategorized'}
- Generated: {document.generated_at.strftime('%Y-%m-%d %H:%M:%S')}

Please find the PDF attached. You can download and review it.

Best regards,
{sender_name}
        """.strip()

        email_sent = dispatch_email_task(
            subject=f"Document: {document.name}",
            body=email_body,
            to_emails=email_list,
            attachments=[
                {
                    "filename": f"{document.name}.pdf",
                    "content": pdf_content,
                    "mimetype": "application/pdf",
                }
            ],
        )

        if not email_sent:
            return error(message="Email could not be sent. Please check SMTP/Celery settings.", status_code=500)

        return success(
            data={
                "document_id": document.id,
                "recipient_emails": email_list,
                "charged": charge_status == "charged",
            },
            message=f"Document sent via email successfully to {len(email_list)} recipient(s).",
        )


class SendDocumentSignatureAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, document_id):
        sign_mode = request.data.get("sign_mode", "both").strip().lower()

        document = GeneratedDocument.objects.filter(id=document_id, user=request.user).first()
        if not document:
            return error(message="Document not found.", status_code=404)

        recipient_email = None
        if sign_mode in ["both", "client_only"]:
            recipient_email = (request.data.get("recipient_email") or "").strip()
            if not recipient_email:
                return error(message="recipient_email is required for this signing mode.")

        _, _, charge_status = _consume_action_credit(
            user=request.user,
            document=document,
            action="send_signature",
            metadata={"sign_mode": sign_mode},
        )
        if charge_status == "insufficient_credits":
            return error(message="Insufficient credits. Please upgrade your plan.", status_code=402)

        created_requests_data = []
        signature_request = None
        owner_request = None

        # Parse role and job title metadata
        recipient_role = (
            request.data.get("recipient_role")
            or request.data.get("signer_role")
            or request.data.get("role")
            or "Client"
        )
        recipient_title = (
            request.data.get("recipient_title")
            or request.data.get("signer_title")
            or request.data.get("job_title")
            or request.data.get("title")
        )

        owner_name = (
            request.data.get("owner_name")
            or request.data.get("sender_name")
            or (getattr(request.user, 'user_profile', None) and getattr(request.user.user_profile, 'first_name', None))
            or request.user.email
        )
        owner_role = (
            request.data.get("owner_role")
            or request.data.get("sender_role")
            or "Authorized Signer"
        )
        owner_title = (
            request.data.get("owner_title")
            or request.data.get("sender_title")
        )

        # Create client signature request
        if sign_mode in ["both", "client_only"]:
            existing = SignatureRequest.objects.filter(document=document, recipient_email=recipient_email, status="pending").first()
            if existing:
                signature_request = existing
                if recipient_role and not existing.signer_role:
                    existing.signer_role = recipient_role
                if recipient_title and not existing.signer_title:
                    existing.signer_title = recipient_title
                existing.save(update_fields=["signer_role", "signer_title", "updated_at"])
            else:
                signature_request = SignatureRequest.objects.create(
                    document=document,
                    sender=request.user,
                    recipient_email=recipient_email,
                    recipient_name=request.data.get("recipient_name"),
                    signer_role=recipient_role,
                    signer_title=recipient_title,
                    expires_at=timezone.now() + timezone.timedelta(days=7),
                )
            created_requests_data.append({"id": signature_request.id, "token": signature_request.token, "recipient_email": signature_request.recipient_email})

        # Create owner signature request
        if sign_mode in ["both", "owner_only"]:
            owner_email = request.user.email
            owner_existing = SignatureRequest.objects.filter(document=document, recipient_email=owner_email, status="pending").first()
            if owner_existing:
                owner_request = owner_existing
                depends_on_req = owner_existing.depends_on
                if owner_role and not owner_existing.signer_role:
                    owner_existing.signer_role = owner_role
                if owner_title and not owner_existing.signer_title:
                    owner_existing.signer_title = owner_title
                owner_existing.save(update_fields=["signer_role", "signer_title", "updated_at"])
            else:
                depends_on_req = signature_request if sign_mode == "both" else None
                owner_request = SignatureRequest.objects.create(
                    document=document,
                    sender=request.user,
                    recipient_email=owner_email,
                    recipient_name=owner_name,
                    signer_role=owner_role,
                    signer_title=owner_title,
                    expires_at=timezone.now() + timezone.timedelta(days=14),
                    depends_on=depends_on_req,
                )
            created_requests_data.append({"id": owner_request.id, "token": owner_request.token, "recipient_email": owner_request.recipient_email, "depends_on": getattr(depends_on_req, 'id', None)})

        # Audit: record creation of signature request
        try:
            req_to_audit = signature_request if sign_mode in ["both", "client_only"] else owner_request
            if req_to_audit:
                SignatureAudit.objects.create(
                    signature_request=req_to_audit,
                    action="created",
                    actor=request.user.email if request.user else "system",
                    metadata={
                        "recipient_email": req_to_audit.recipient_email,
                        "ip": request.META.get("REMOTE_ADDR"),
                        "user_agent": request.META.get("HTTP_USER_AGENT"),
                        "sign_mode": sign_mode
                    },
                )
        except Exception:
            pass

        # Check if the AI generated signature placeholders. If not, append blank ones.
        content = document.rendered_content or ""
        signature_matches = re.findall(
            r"(?:<strong>\s*Signature:\s*</strong>|Signature:)\s*_+",
            content,
            flags=re.IGNORECASE,
        )
        
        if len(signature_matches) == 0:
            if sign_mode == "both":
                client_name = getattr(signature_request, "recipient_name", None) or getattr(signature_request, "recipient_email", None) or "Client"
                owner_name = getattr(owner_request, "recipient_name", None) or getattr(owner_request, "recipient_email", None) or "Owner"
                
                content += f"<br><strong>Signature by {client_name}</strong>"
                content += "\nSignature: ______________________________\nDate: ______________________________"
                
                content += f"<br><strong>Signature by {owner_name}</strong>"
                content += "\nSignature: ______________________________\nDate: ______________________________"
            elif sign_mode == "client_only":
                client_name = getattr(signature_request, "recipient_name", None) or getattr(signature_request, "recipient_email", None) or "Client"
                content += f"<br><strong>Signature by {client_name}</strong>"
                content += "\nSignature: ______________________________\nDate: ______________________________"
            elif sign_mode == "owner_only":
                owner_name = getattr(owner_request, "recipient_name", None) or getattr(owner_request, "recipient_email", None) or "Owner"
                content += f"<br><strong>Signature by {owner_name}</strong>"
                content += "\nSignature: ______________________________\nDate: ______________________________"
                
            document.rendered_content = content

        # Auto-detect signature/date placeholders from generated content.
        signature_fields = _detect_signature_fields_from_rendered_content(document.rendered_content, sign_mode)
        document.signature_fields = signature_fields
        document.save(update_fields=["signature_fields", "rendered_content", "updated_at"])

        base_url = request.build_absolute_uri("/").rstrip("/")
        
        email_sent = False
        sign_link = ""

        if sign_mode == "owner_only" and owner_request:
            sign_link = f"{base_url}/api/signatures/{owner_request.token}/sign-form/"
            email_sent = self._send_signature_email(owner_request, sign_link, document, request)
            if email_sent:
                owner_request.email_sent = True
                owner_request.save(update_fields=["email_sent", "updated_at"])
        elif signature_request:
            sign_link = f"{base_url}/api/signatures/{signature_request.token}/sign-form/"
            email_sent = self._send_signature_email(signature_request, sign_link, document, request)
            if email_sent:
                signature_request.email_sent = True
                signature_request.save(update_fields=["email_sent", "updated_at"])

        if not email_sent:
            return error(message="Signature email could not be sent. Please check SMTP/Celery settings.", status_code=500)

        msg = "Signature requests created successfully."
        if sign_mode == "both":
            msg = "Signature requests created (owner will be notified after recipient signs)."

        return success(
            data={
                "created_requests": created_requests_data,
                "sign_link": sign_link,
                "signature_fields": document.signature_fields or [],
                "charged": charge_status == "charged",
                "sign_mode": sign_mode
            },
            message=msg,
            status_code=201,
        )

    def _send_signature_email(self, req_obj, sign_link, document, request):
        profile = getattr(req_obj.sender, 'user_profile', None)
        sender_name = ""
        if profile and (profile.first_name or profile.last_name):
            sender_name = f"{profile.first_name} {profile.last_name}".strip()
        sender_name = sender_name or req_obj.sender.email
        
        custom_message = request.data.get("message") or "Please review and sign this document."
        signature_fields_list = document.signature_fields or []

        email_body = f"""
Hello {req_obj.recipient_name or 'there'},

{sender_name} has sent you a document for signature: <strong>{document.name}</strong>

Message:
{custom_message}

Document Details:
- Type: {document.document_type.name if document.document_type else 'General'}
- Signature Fields: {len(signature_fields_list) if signature_fields_list else 'Not specified'}
- Valid Until: {req_obj.expires_at.strftime('%Y-%m-%d')}

IMPORTANT: Please click the link below to view and sign the document:
{sign_link}

On the signing page:
1. Review the document carefully
2. Type your signature in the signature field(s)
3. Click "Submit Signature" to complete

This link expires on {req_obj.expires_at.strftime('%Y-%m-%d at %H:%M %Z')}.

Best regards,
{sender_name}
        """.strip()

        return dispatch_email_task(
            subject=f"Signature Request: {document.name}",
            body=email_body,
            to_emails=[req_obj.recipient_email],
        )


class SignatureRequestPublicDetailAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token):
        signature_request = SignatureRequest.objects.select_related("document", "sender").filter(token=token).first()
        if not signature_request:
            return error(message="Signature request not found.", status_code=404)

        if signature_request.expires_at and timezone.now() > signature_request.expires_at:
            signature_request.status = "expired"
            signature_request.save(update_fields=["status", "updated_at"])
            return error(
                message="Signature request expired.",
                errors={
                    "current_status": signature_request.status,
                    "preview_url": f"/api/signatures/{token}/preview/",
                },
                status_code=400,
            )

        document = signature_request.document
        return success(
            data={
                "request_id": signature_request.id,
                "status": signature_request.status,
                "document_id": document.id,
                "document_name": document.name,
                "sender_email": signature_request.sender.email,
                "recipient_email": signature_request.recipient_email,
                "preview_url": f"/api/signatures/{token}/preview/",
                "current_status": signature_request.status,
            },
            message="Signature request fetched successfully.",
        )


class SignatureRequestPublicPreviewAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token):
        signature_request = SignatureRequest.objects.select_related("document", "sender").filter(token=token).first()
        if not signature_request:
            return error(message="Signature request not found.", status_code=404)

        if signature_request.expires_at and timezone.now() > signature_request.expires_at:
            signature_request.status = "expired"
            signature_request.save(update_fields=["status", "updated_at"])
            return error(
                message="Signature request expired.",
                errors={"current_status": signature_request.status},
                status_code=400,
            )

        document = signature_request.document

        # If already signed and we have a stored signed PDF, serve that
        if signature_request.status == "signed":
            signed_rel = signature_request.signed_pdf_path or getattr(document, "signed_pdf_path", None)
            if signed_rel:
                signed_abs = os.path.join(settings.MEDIA_ROOT, signed_rel)
                if os.path.exists(signed_abs):
                    response = FileResponse(open(signed_abs, "rb"), content_type="application/pdf")
                    response["Content-Disposition"] = f'inline; filename="{document.name}-signed.pdf"'
                    response["X-Document-Path"] = signed_rel
                    # Allow embedding the preview in an iframe on same-origin pages
                    response["X-Frame-Options"] = "SAMEORIGIN"
                    return response

        abs_path, rel_path = build_pdf_for_document(
            document=document,
            branding=CompanyBranding.objects.filter(user=document.user).first(),
        )
        if not os.path.exists(abs_path):
            return error(message="PDF generation failed.", status_code=500)

        response = FileResponse(open(abs_path, "rb"), content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{document.name}.pdf"'
        response["X-Document-Path"] = rel_path
        # Allow embedding the preview in an iframe on same-origin pages
        response["X-Frame-Options"] = "SAMEORIGIN"
        return response


class SignatureRequestFormAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token):
        """Render HTML form for signing the document"""
        signature_request = SignatureRequest.objects.select_related("document", "sender").filter(token=token).first()
        if not signature_request:
            return HttpResponse(f"<h1>Error: Signature request not found</h1>", status=404)

        if signature_request.expires_at and timezone.now() > signature_request.expires_at:
            signature_request.status = "expired"
            signature_request.save(update_fields=["status", "updated_at"])
            return HttpResponse(f"<h1>Error: Signature request has expired</h1>", status=400)

        if signature_request.status != "pending":
            return HttpResponse(
                f"<h1>Signature Already {signature_request.status.title()}</h1>"
                f"<p>This document was already {signature_request.status} on {signature_request.signed_at or 'unknown'}</p>"
                f"<p>Preview: <a href='/api/signatures/{token}/preview/'>Preview Document</a></p>",
                status=400
            )
        document = signature_request.document
        signature_fields = _signature_fields_for_request(document.signature_fields or [], signature_request)
        raw_fields = signature_fields if signature_fields else ["signature"]
        fields_data = [
            {"id": re.sub(r'[^a-zA-Z0-9_]', '_', str(f)), "label": str(f)}
            for f in raw_fields
        ]
        field_ids_json = json.dumps([f["id"] for f in fields_data])

        profile = getattr(signature_request.sender, 'user_profile', None)
        sender_name = ""
        if profile and (profile.first_name or profile.last_name):
            sender_name = f"{profile.first_name} {profile.last_name}".strip()
        sender_name = sender_name or signature_request.sender.email

        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign Document: {document.name}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #FFFFFF 90%, #FFFFFF 90%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ 
            max-width: 1000px; 
            margin: 0 auto; 
            background: white; 
            border-radius: 8px; 
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{ 
            background: #f8f9fa; 
            padding: 20px; 
            border-bottom: 1px solid #e9ecef;
        }}
        .header h1 {{ color: #333; font-size: 24px; margin-bottom: 5px; }}
        .header p {{ color: #666; font-size: 14px; }}
        .content {{ padding: 30px; }}
        .doc-info {{ 
            background: #e7f3ff; 
            border-left: 4px solid #2196F3; 
            padding: 15px; 
            margin-bottom: 30px; 
            border-radius: 4px;
        }}
        .doc-info p {{ margin: 5px 0; color: #333; }}
        .doc-info label {{ font-weight: 600; color: #2196F3; }}
        .preview-section {{ 
            margin-bottom: 30px; 
            border: 1px solid #e9ecef; 
            border-radius: 4px; 
            overflow: hidden;
        }}
        .preview-header {{ 
            background: #f8f9fa; 
            padding: 15px; 
            font-weight: 600; 
            color: #333;
        }}
        .preview-container {{ 
            width: 100%; 
            height: 400px; 
            background: #f0f0f0; 
            overflow: auto;
        }}
        .signature-section {{ 
            background: #fffdf5; 
            border: 1px solid #fef08a;
            border-left: 4px solid #eab308; 
            padding: 24px; 
            margin-bottom: 30px; 
            border-radius: 8px;
        }}
        .signature-section h3 {{ color: #854d0e; margin-bottom: 10px; font-size: 18px; }}
        .signature-section .section-hint {{ color: #713f12; margin-bottom: 20px; font-size: 14px; }}

        .signature-field {{ 
            margin-bottom: 25px; 
            padding: 20px; 
            background: white; 
            border: 1px solid #e2e8f0; 
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        }}
        .signature-field .field-title {{ 
            display: block; 
            font-size: 15px; 
            font-weight: 700; 
            color: #1e293b; 
            margin-bottom: 14px;
        }}
        .sig-pad-box {{
            display: flex;
            flex-direction: column;
            align-items: center;
            width: 100%;
        }}
        .sig-pad-title {{
            font-size: 22px;
            font-weight: 700;
            color: #0f172a;
            margin-bottom: 16px;
            text-align: center;
        }}
        .canvas-wrap {{
            position: relative;
            width: 100%;
            height: 220px;
            border: 1.5px solid #cbd5e1;
            border-radius: 12px;
            background: #ffffff;
            overflow: hidden;
            cursor: default;
            transition: border-color 0.2s ease, box-shadow 0.2s ease;
        }}
        .canvas-wrap:hover, .canvas-wrap.active {{
            border-color: #38bdf8;
            box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.2);
        }}
        .sig-canvas {{
            width: 100%;
            height: 100%;
            display: block;
            touch-action: none;
            cursor: default;
        }}
        .sig-placeholder {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: #94a3b8;
            font-size: 14px;
            pointer-events: none;
            user-select: none;
            text-align: center;
            transition: opacity 0.2s ease;
        }}
        .sig-placeholder.hidden {{
            opacity: 0;
            pointer-events: none;
        }}
        .sig-toolbar {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 24px;
            margin-top: 14px;
            flex-wrap: wrap;
            width: 100%;
        }}
        .tool-item {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
            color: #475569;
            font-weight: 600;
        }}
        .color-picker {{
            width: 32px;
            height: 32px;
            padding: 2px;
            border: 1px solid #cbd5e1;
            border-radius: 50%;
            cursor: pointer;
            background: white;
            outline: none;
        }}
        .color-picker::-webkit-color-swatch-wrapper {{
            padding: 0;
        }}
        .color-picker::-webkit-color-swatch {{
            border: none;
            border-radius: 50%;
        }}
        .width-slider {{
            width: 90px;
            accent-color: #38bdf8;
            cursor: pointer;
        }}
        .btn-clear-sig {{
            background: #ffffff;
            border: 1.5px solid #38bdf8;
            color: #0284c7;
            padding: 8px 22px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }}
        .btn-clear-sig:hover {{
            background: #f0f9ff;
            color: #0369a1;
            border-color: #0284c7;
            box-shadow: 0 2px 6px rgba(56, 189, 248, 0.2);
        }}

        .actions {{ 
            display: flex; 
            gap: 12px; 
            margin-top: 30px;
        }}
        button {{ 
            padding: 12px 24px; 
            border: none; 
            border-radius: 6px; 
            font-size: 14px; 
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }}
        .btn-primary {{ 
            background: #0284c7; 
            color: white;
            flex: 1;
        }}
        .btn-primary:hover {{ 
            background: #0369a1; 
            box-shadow: 0 4px 12px rgba(2, 132, 199, 0.35);
        }}
        .btn-secondary {{ 
            background: #f1f5f9; 
            color: #475569; 
            border: 1px solid #cbd5e1;
            flex: 0 1 auto;
        }}
        .btn-secondary:hover {{ 
            background: #e2e8f0;
            color: #1e293b;
        }}
        .message {{ 
            padding: 12px; 
            border-radius: 6px; 
            margin-bottom: 20px; 
            display: none;
            font-size: 14px;
        }}
        .message.error {{ 
            background: #fef2f2; 
            color: #991b1b; 
            border: 1px solid #fecaca;
        }}
        .message.success {{ 
            background: #f0fdf4; 
            color: #166534; 
            border: 1px solid #bbf7d0;
        }}
        .spinner {{ 
            display: inline-block; 
            width: 16px; 
            height: 16px; 
            border: 2px solid rgba(255,255,255,0.3); 
            border-radius: 50%; 
            border-top-color: white; 
            animation: spin 0.8s linear infinite; 
            margin-right: 8px;
            vertical-align: middle;
        }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
        .footer {{ 
            background: #f8f9fa; 
            padding: 20px; 
            border-top: 1px solid #e9ecef; 
            color: #666; 
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔐 Document Signature Request</h1>
            <p>Please review and sign the document below</p>
        </div>
        
        <div class="content">
            <div id="message"></div>
            
            <div class="doc-info">
                <p><label>Document:</label> {document.name}</p>
                <p><label>From:</label> {sender_name}</p>
                <p><label>Request ID:</label> {signature_request.id}</p>
                <p><label>Expires:</label> {signature_request.expires_at.strftime('%B %d, %Y at %I:%M %p')}</p>
            </div>

            <div class="preview-section">
                <div class="preview-header">📄 Document Preview</div>
                <div class="preview-container">
                    <iframe src="/api/signatures/{token}/preview/" width="100%" height="100%" frameborder="0"></iframe>
                </div>
            </div>

            <form id="signForm">
                <div class="signature-section">
                    <h3>✍️ Sign Document</h3>
                    <p class="section-hint">
                        Please confirm your legal name and optional job title, then draw your signature below.
                    </p>
                    <div style="display: flex; gap: 12px; margin-bottom: 16px;">
                        <div style="flex: 1;">
                            <label style="display: block; font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 4px;">Full Name</label>
                            <input type="text" id="signer_name" name="signer_name" value="{signature_request.recipient_name or ''}" placeholder="e.g. John Smith" style="width: 100%; box-sizing: border-box; padding: 9px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 14px;" />
                        </div>
                        <div style="flex: 1;">
                            <label style="display: block; font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 4px;">Job Title (Optional)</label>
                            <input type="text" id="signer_title" name="signer_title" value="{signature_request.signer_title or ''}" placeholder="e.g. Director of Human Resources" style="width: 100%; box-sizing: border-box; padding: 9px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 14px;" />
                        </div>
                    </div>
                    
                    {"".join([f'''
                    <div class="signature-field">
                        <label class="field-title">Signature for "{f["label"]}"</label>
                        <div class="sig-pad-box">
                            <div class="sig-pad-title">Draw your eSignature here</div>
                            <div class="canvas-wrap" id="wrap_{f["id"]}">
                                <canvas id="canvas_{f["id"]}" class="sig-canvas"></canvas>
                                <div class="sig-placeholder" id="hint_{f["id"]}">✍️ Draw signature using mouse, finger, or stylus</div>
                            </div>
                            <div class="sig-toolbar">
                                <div class="tool-item">
                                    <input type="color" id="color_{f["id"]}" value="#000000" class="color-picker" title="Pen Color">
                                    <span style="font-size: 12px; color: #64748b; font-family: monospace;">#000000</span>
                                </div>
                                <div class="tool-item">
                                    <span>Width</span>
                                    <input type="range" id="width_{f["id"]}" min="1" max="8" value="3.5" step="0.5" class="width-slider" title="Pen Width">
                                </div>
                                <button type="button" class="btn-clear-sig" onclick="clearSigCanvas('{f["id"]}')">
                                    Clear and draw again
                                </button>
                            </div>
                            <input type="hidden" id="sig_{f["id"]}" name="sig_{f["id"]}" value="">
                        </div>
                    </div>
                    ''' for f in fields_data])}
                </div>

                <div class="actions">
                    <button type="submit" class="btn-primary">
                        <span id="btnText">Sign & Submit</span>
                    </button>
                    <button type="reset" class="btn-secondary">Clear All</button>
                </div>
            </form>
        </div>

        <div class="footer">
            <p>⏱️ This signature request expires on {signature_request.expires_at.strftime('%B %d, %Y')}.</p>
            <p>🔒 This document is securely stored and your signature will be recorded.</p>
        </div>
    </div>

    <script>
        const fieldIds = {field_ids_json};
        const canvasMap = {{}};

        function initSigPad(fieldId) {{
            const canvas = document.getElementById('canvas_' + fieldId);
            if (!canvas) return;
            const wrap = document.getElementById('wrap_' + fieldId);
            const hint = document.getElementById('hint_' + fieldId);
            const hiddenInput = document.getElementById('sig_' + fieldId);
            const colorInput = document.getElementById('color_' + fieldId);
            const widthInput = document.getElementById('width_' + fieldId);
            const ctx = canvas.getContext('2d');

            function resize() {{
                const rect = wrap.getBoundingClientRect();
                if (rect.width === 0) return;
                const dpr = window.devicePixelRatio || 1;

                let savedImg = null;
                if (canvasMap[fieldId] && canvasMap[fieldId].hasDrawn) {{
                    savedImg = canvas.toDataURL();
                }}

                canvas.width = rect.width * dpr;
                canvas.height = rect.height * dpr;
                ctx.scale(dpr, dpr);
                ctx.lineCap = 'round';
                ctx.lineJoin = 'round';

                if (savedImg) {{
                    const img = new Image();
                    img.onload = () => {{
                        ctx.drawImage(img, 0, 0, rect.width, rect.height);
                    }};
                    img.src = savedImg;
                }}
            }}

            resize();
            window.addEventListener('resize', resize);

            let isDrawing = false;
            let lastX = 0;
            let lastY = 0;

            function getPos(e) {{
                const rect = canvas.getBoundingClientRect();
                return {{
                    x: e.clientX - rect.left,
                    y: e.clientY - rect.top
                }};
            }}

            function startDraw(e) {{
                e.preventDefault();
                try {{ canvas.setPointerCapture(e.pointerId); }} catch(err) {{}}
                isDrawing = true;
                wrap.classList.add('active');
                const pos = getPos(e);
                lastX = pos.x;
                lastY = pos.y;
                hint.classList.add('hidden');
            }}

            function draw(e) {{
                if (!isDrawing) return;
                e.preventDefault();
                const pos = getPos(e);
                ctx.strokeStyle = colorInput ? colorInput.value : '#000000';
                ctx.lineWidth = widthInput ? parseFloat(widthInput.value) : 3.5;
                ctx.beginPath();
                ctx.moveTo(lastX, lastY);
                ctx.lineTo(pos.x, pos.y);
                ctx.stroke();
                lastX = pos.x;
                lastY = pos.y;
                if (canvasMap[fieldId]) {{
                    canvasMap[fieldId].hasDrawn = true;
                }}
            }}

            function stopDraw(e) {{
                if (!isDrawing) return;
                isDrawing = false;
                wrap.classList.remove('active');
                try {{ canvas.releasePointerCapture(e.pointerId); }} catch(err) {{}}
                if (canvasMap[fieldId] && canvasMap[fieldId].hasDrawn) {{
                    hiddenInput.value = canvas.toDataURL('image/png');
                }}
            }}

            canvas.addEventListener('pointerdown', startDraw);
            canvas.addEventListener('pointermove', draw);
            canvas.addEventListener('pointerup', stopDraw);
            canvas.addEventListener('pointercancel', stopDraw);

            canvasMap[fieldId] = {{
                canvas,
                ctx,
                wrap,
                hint,
                hiddenInput,
                hasDrawn: false,
                clear: function() {{
                    const rect = wrap.getBoundingClientRect();
                    ctx.clearRect(0, 0, rect.width, rect.height);
                    hiddenInput.value = '';
                    this.hasDrawn = false;
                    hint.classList.remove('hidden');
                }}
            }};
        }}

        function clearSigCanvas(fieldId) {{
            if (canvasMap[fieldId]) {{
                canvasMap[fieldId].clear();
            }}
        }}

        document.addEventListener('DOMContentLoaded', () => {{
            fieldIds.forEach(id => initSigPad(id));
        }});
        setTimeout(() => {{
            fieldIds.forEach(id => {{
                if (!canvasMap[id]) initSigPad(id);
            }});
        }}, 100);

        const form = document.getElementById('signForm');
        const messageDiv = document.getElementById('message');
        const btnText = document.getElementById('btnText');

        function showMessage(text, type) {{
            messageDiv.textContent = text;
            messageDiv.className = 'message ' + type;
            messageDiv.style.display = 'block';
            window.scrollTo({{ top: 0, behavior: 'smooth' }});
        }}

        form.addEventListener('submit', async (e) => {{
            e.preventDefault();

            // Validate all signature fields
            for (let id of fieldIds) {{
                const pad = canvasMap[id];
                if (!pad || !pad.hiddenInput.value) {{
                    showMessage('❌ Please draw your signature before submitting.', 'error');
                    const wrap = document.getElementById('wrap_' + id);
                    if (wrap) {{
                        wrap.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                        wrap.style.borderColor = '#ef4444';
                        setTimeout(() => {{ wrap.style.borderColor = '#cbd5e1'; }}, 2000);
                    }}
                    return;
                }}
            }}

            const submitBtn = form.querySelector('button[type="submit"]');
            const spinner = '<span class="spinner"></span>';
            submitBtn.innerHTML = spinner + 'Submitting...';
            submitBtn.disabled = true;

            try {{
                const signatures = fieldIds.map(id => canvasMap[id].hiddenInput.value).filter(Boolean);
                const signatureValue = signatures.join('; ');

                const nameInput = document.getElementById('signer_name');
                const titleInput = document.getElementById('signer_title');

                const response = await fetch('/api/signatures/{token}/sign/', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                    }},
                    body: JSON.stringify({{
                        signature_value: signatureValue,
                        signature_type: 'drawn',
                        signer_name: nameInput ? nameInput.value.trim() : '',
                        signer_title: titleInput ? titleInput.value.trim() : '',
                    }})
                }});

                const data = await response.json();

                if (response.ok) {{
                    showMessage('✅ Document signed successfully! You can now close this page.', 'success');
                    form.style.display = 'none';
                }} else {{
                    showMessage('❌ Error: ' + (data.message || 'Failed to sign document'), 'error');
                }}
            }} catch (error) {{
                showMessage('❌ Error: ' + error.message, 'error');
            }} finally {{
                submitBtn.innerHTML = 'Sign & Submit';
                submitBtn.disabled = false;
            }}
        }});

        form.addEventListener('reset', (e) => {{
            e.preventDefault();
            fieldIds.forEach(id => clearSigCanvas(id));
        }});
    </script>
</body>
</html>
        """

        return HttpResponse(html_content, content_type="text/html")


class SignatureRequestSignAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, token):
        signature_request = SignatureRequest.objects.select_related("document", "sender").filter(token=token).first()
        if not signature_request:
            return error(message="Signature request not found.", status_code=404)

        if signature_request.status != "pending":
            return error(
                message="Signature request is not pending.",
                errors={
                    "current_status": signature_request.status,
                    "preview_url": f"/api/signatures/{token}/preview/",
                },
                status_code=400,
            )

        if signature_request.expires_at and timezone.now() > signature_request.expires_at:
            signature_request.status = "expired"
            signature_request.save(update_fields=["status", "updated_at"])
            return error(message="Signature request expired.", status_code=400)

        signature_value = request.data.get("signature_value")
        if not signature_value:
            return error(message="signature_value is required.", status_code=400)

        signature_request.signature_type = request.data.get("signature_type") or "typed"
        signature_request.signature_value = signature_value
        signature_request.status = "signed"
        signature_request.signed_at = timezone.now()

        update_fields = [
            "signature_type",
            "signature_value",
            "status",
            "signed_at",
            "updated_at",
        ]
        if request.data.get("signer_name"):
            signature_request.recipient_name = str(request.data.get("signer_name")).strip()
            update_fields.append("recipient_name")
        if request.data.get("signer_title") or request.data.get("job_title"):
            signature_request.signer_title = str(request.data.get("signer_title") or request.data.get("job_title")).strip()
            update_fields.append("signer_title")
        if request.data.get("signer_role") or request.data.get("role"):
            signature_request.signer_role = str(request.data.get("signer_role") or request.data.get("role")).strip()
            update_fields.append("signer_role")

        signature_request.save(update_fields=update_fields)

        document = signature_request.document
        signed_date = timezone.localdate().isoformat()
        document.rendered_content = _apply_signature_to_rendered_content(
            rendered_content=document.rendered_content,
            signature_value=signature_value,
            date_value=signed_date,
        )
        document.save(update_fields=["rendered_content", "updated_at"])

        # Generate per-signer signed PDF and attach to this signature_request
        abs_path, rel_path = build_pdf_for_document(
            document=document,
            branding=CompanyBranding.objects.filter(user=document.user).first(),
            signed=True,
        )
        per_request_rel = None
        if abs_path and os.path.exists(abs_path):
            # rename to per-request file to avoid overwrite
            per_name = f"document_{document.id}_signed_by_{signature_request.id}.pdf"
            rel_dir = os.path.join("generated_documents", str(document.user_id))
            per_rel = os.path.join(rel_dir, per_name).replace('\\', '/')
            per_abs = os.path.join(settings.MEDIA_ROOT, per_rel)
            try:
                os.replace(abs_path, per_abs)
                per_request_rel = per_rel
                signature_request.signed_pdf_path = per_request_rel
                signature_request.save(update_fields=["signed_pdf_path", "updated_at"])
            except Exception:
                pass

        attachments = []
        if per_request_rel:
            with open(os.path.join(settings.MEDIA_ROOT, per_request_rel), "rb") as fh:
                attachments.append({
                    "filename": f"{document.name}-signed-by-{signature_request.id}.pdf",
                    "content": fh.read(),
                    "mimetype": "application/pdf",
                })

        # Notify owner (the sender) that this particular signer has signed
        email_sent = dispatch_email_task(
            subject=f"Document signed: {signature_request.document.name}",
            body=(
                f"A signer ({signature_request.recipient_email}) has signed the document '{signature_request.document.name}'. Signed on {signed_date}."
            ),
            to_emails=[signature_request.sender.email],
        )

        # Audit: record signing event
        try:
            SignatureAudit.objects.create(
                signature_request=signature_request,
                action="signed",
                actor=signature_request.recipient_email,
                metadata={
                    "ip": request.META.get("REMOTE_ADDR"),
                    "user_agent": request.META.get("HTTP_USER_AGENT"),
                    "signature_type": signature_request.signature_type,
                },
            )
        except Exception:
            pass

        # If this request has dependents (e.g., owner request depends on client), notify dependent(s)
        try:
            dependents = signature_request.dependents.filter(status="pending")
            for dep in dependents:
                # send sign email to dependent
                base_url = request.build_absolute_uri("/").rstrip("/")
                dep_link = f"{base_url}/api/signatures/{dep.token}/sign-form/"
                dep_body = f"Hello {dep.recipient_name or dep.recipient_email},\n\nA prior signer ({signature_request.recipient_email}) has completed signing. Please review and sign: {dep_link}"
                sent = dispatch_email_task(subject=f"Signature Request: {document.name}", body=dep_body, to_emails=[dep.recipient_email])
                if sent:
                    dep.email_sent = True
                    dep.save(update_fields=["email_sent", "updated_at"]) 
                try:
                    SignatureAudit.objects.create(
                        signature_request=dep,
                        action="email_sent",
                        actor="system",
                        metadata={"triggered_by": signature_request.id},
                    )
                except Exception:
                    pass
        except Exception:
            pass

        if not email_sent:
            return error(message="Signed notification email could not be sent.", status_code=500)

        # If there are no pending signature requests for this document, generate final combined signed PDF and email to all
        try:
            pending_reqs = SignatureRequest.objects.filter(document=document, status="pending")
            signed_reqs = SignatureRequest.objects.filter(document=document, status="signed")
            
            if not pending_reqs.exists() and signed_reqs.exists():
                abs_final, rel_final = build_pdf_for_document(document=document, branding=CompanyBranding.objects.filter(user=document.user).first(), signed=True)
                final_rel = None
                if abs_final and os.path.exists(abs_final):
                    final_name = f"document_{document.id}_final_signed.pdf"
                    rel_dir = os.path.join("generated_documents", str(document.user_id))
                    final_rel = os.path.join(rel_dir, final_name).replace('\\', '/')
                    final_abs = os.path.join(settings.MEDIA_ROOT, final_rel)
                    try:
                        os.replace(abs_final, final_abs)
                        document.signed_pdf_path = final_rel
                        document.save(update_fields=["signed_pdf_path", "updated_at"])
                    except Exception:
                        pass

                # Email final PDF to all unique emails (owner + all recipients)
                recipients = set([str(document.user.email)])
                for r in signed_reqs:
                    recipients.add(r.recipient_email)
                attachments = []
                if final_rel:
                    with open(os.path.join(settings.MEDIA_ROOT, final_rel), "rb") as fh:
                        attachments.append({
                            "filename": f"{document.name}-final-signed.pdf",
                            "content": fh.read(),
                            "mimetype": "application/pdf",
                        })
                dispatch_email_task(
                    subject=f"Final Signed Document: {document.name}",
                    body=f"The document '{document.name}' has been fully signed. Please find the final signed PDF attached.",
                    to_emails=list(recipients),
                    attachments=attachments,
                )
        except Exception:
            pass

        return success(
            data={
                "request_id": signature_request.id,
                "status": signature_request.status,
                "signed_at": signature_request.signed_at,
            },
            message="Document signed successfully.",
        )


class BillingOverviewAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        user = request.user
        active_subscription = Subscription.objects.filter(user=user, status="active").first()
        payment_methods = PaymentMethod.objects.filter(user=user)
        # Limit to only 1 most recent payment
        billing_history = PaymentHistory.objects.filter(user=user).order_by("-paid_at")[:1]

        method_data = PaymentMethodSerializer(payment_methods, many=True).data
        history_data = [
            {
                "plan": item.subscriptionpackage.plan_name if item.subscriptionpackage else "N/A",
                "status": "Paid" if item.payment_status == "success" else item.payment_status.capitalize(),
                "date": item.paid_at,
                "amount": item.amount,
                "invoice_id": item.transaction_id,
                "invoice_download_url": request.build_absolute_uri(f"/api/billing/invoice/{item.id}/download/?token={signing.dumps(item.id)}") if item.transaction_id else None,
            }
            for item in billing_history
        ]

        # Get and sync wallet to ensure credit limits are accurate per user
        wallet, _ = CreditWallet.objects.get_or_create(user=user)
        wallet = _sync_wallet_cycle(wallet, active_subscription)

        # Build current plan (downloads field already represents credit limit)
        current_plan = _subscription_plan_overview(active_subscription)

        data = {
            "current_plan": current_plan,
            "payment_methods": method_data,
            "billing_history": history_data,
            "stripe_integrated": True,
        }
        return success(data=data, message="Billing overview fetched successfully.")


class InvoiceDownloadAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, payment_history_id):
        # Try to authenticate user
        user = getattr(request, 'user', None)
        is_authenticated = user and user.is_authenticated
        
        # Check if signed URL token is provided
        signed_token = request.query_params.get('token')
        
        # Handle unsigned request (requires authentication)
        if not signed_token and not is_authenticated:
            return error(message="Unauthorized: Provide authentication or use a signed download link.", status_code=401)
        
        # If signed token provided, verify it
        if signed_token:
            try:
                payment_history_id_from_token = signing.loads(signed_token, max_age=3600)  # 1 hour expiry
                if payment_history_id_from_token != payment_history_id:
                    return error(message="Invalid or expired download link.", status_code=403)
            except signing.BadSignature:
                return error(message="Invalid or expired download link.", status_code=403)
            try:
                payment_history = PaymentHistory.objects.get(id=payment_history_id)
            except PaymentHistory.DoesNotExist:
                return error(message="Invoice not found.", status_code=404)
        else:
            # Authenticated user - verify ownership
            try:
                payment_history = PaymentHistory.objects.get(id=payment_history_id, user=request.user)
            except PaymentHistory.DoesNotExist:
                return error(message="Invoice not found.", status_code=404)

        try:
            # Generate PDF invoice
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            from reportlab.lib.units import inch
            from io import BytesIO

            buffer = BytesIO()
            pdf_canvas = canvas.Canvas(buffer, pagesize=letter)
            width, height = letter

            # Header
            pdf_canvas.setFont("Helvetica-Bold", 20)
            pdf_canvas.drawString(0.75 * inch, height - 0.75 * inch, "INVOICE")

            # Invoice details
            pdf_canvas.setFont("Helvetica", 10)
            y_position = height - 1.25 * inch

            pdf_canvas.drawString(0.75 * inch, y_position, f"Invoice ID: {payment_history.transaction_id}")
            y_position -= 0.2 * inch
            pdf_canvas.drawString(0.75 * inch, y_position, f"Date: {payment_history.paid_at.strftime('%B %d, %Y')}")
            y_position -= 0.2 * inch
            pdf_canvas.drawString(0.75 * inch, y_position, f"Status: Paid")

            # Customer info
            y_position -= 0.4 * inch
            pdf_canvas.setFont("Helvetica-Bold", 12)
            pdf_canvas.drawString(0.75 * inch, y_position, "Bill To:")
            y_position -= 0.25 * inch
            pdf_canvas.setFont("Helvetica", 10)
            pdf_canvas.drawString(0.75 * inch, y_position, payment_history.user.email)

            # Items table
            y_position -= 0.5 * inch
            pdf_canvas.setFont("Helvetica-Bold", 11)
            pdf_canvas.drawString(0.75 * inch, y_position, "Description")
            pdf_canvas.drawString(4 * inch, y_position, "Amount")

            # Line under headers
            pdf_canvas.line(0.75 * inch, y_position - 0.1 * inch, 7.75 * inch, y_position - 0.1 * inch)

            # Item rows
            y_position -= 0.3 * inch
            pdf_canvas.setFont("Helvetica", 10)
            plan_name = payment_history.subscriptionpackage.plan_name if payment_history.subscriptionpackage else "Subscription"
            pdf_canvas.drawString(0.75 * inch, y_position, plan_name)
            pdf_canvas.drawString(4 * inch, y_position, f"${payment_history.amount:.2f}")

            # Total
            y_position -= 0.4 * inch
            pdf_canvas.line(0.75 * inch, y_position, 7.75 * inch, y_position)
            y_position -= 0.2 * inch
            pdf_canvas.setFont("Helvetica-Bold", 11)
            pdf_canvas.drawString(4 * inch, y_position, "Total:")
            pdf_canvas.drawString(5.5 * inch, y_position, f"${payment_history.amount:.2f}")

            # Footer
            pdf_canvas.setFont("Helvetica", 8)
            pdf_canvas.drawString(0.75 * inch, 0.5 * inch, "Thank you for your subscription!")

            # IMPORTANT: Save the canvas to finalize the PDF
            pdf_canvas.save()
            
            # Get the PDF data
            pdf_data = buffer.getvalue()
            buffer.close()

            # Return PDF response
            response = HttpResponse(pdf_data, content_type='application/pdf')
            filename = f"invoice_{payment_history.transaction_id}.pdf"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response['Content-Length'] = len(pdf_data)
            return response
            
        except Exception as e:
            return error(message=f"Failed to generate invoice: {str(e)}", status_code=500)


class PaymentMethodAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        serializer = PaymentMethodSerializer(data=request.data)
        if not serializer.is_valid():
            return error(message="Invalid payment method data.", errors=serializer.errors)

        if serializer.validated_data.get("is_default", True):
            PaymentMethod.objects.filter(user=request.user, is_default=True).update(is_default=False)

        payment_method = serializer.save(user=request.user)
        return success(data=PaymentMethodSerializer(payment_method).data, message="Payment method added successfully.", status_code=201)

    def put(self, request, payment_method_id):
        payment_method = PaymentMethod.objects.filter(id=payment_method_id, user=request.user).first()
        if not payment_method:
            return error(message="Payment method not found.", status_code=404)

        serializer = PaymentMethodSerializer(payment_method, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(message="Invalid payment method data.", errors=serializer.errors)

        if serializer.validated_data.get("is_default") is True:
            PaymentMethod.objects.filter(user=request.user, is_default=True).exclude(id=payment_method.id).update(is_default=False)

        serializer.save()
        return success(data=serializer.data, message="Payment method updated successfully.")

    def delete(self, request, payment_method_id):
        payment_method = PaymentMethod.objects.filter(id=payment_method_id, user=request.user).first()
        if not payment_method:
            return error(message="Payment method not found.", status_code=404)

        payment_method.delete()
        return success(message="Payment method removed successfully.")


class CreditsOverviewAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        wallet, _ = CreditWallet.objects.get_or_create(user=request.user)
        active_subscription = _active_subscription_for_user(request.user)
        wallet = _sync_wallet_cycle(wallet, active_subscription)

        serializer = CreditWalletSerializer(wallet)
        return success(data=serializer.data, message="Credit summary fetched successfully.")


class CompanyBrandingAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        branding, _ = CompanyBranding.objects.get_or_create(user=request.user)
        serializer = CompanyBrandingSerializer(branding)
        return success(data=serializer.data, message="Company branding fetched successfully.")

    def post(self, request):
        # Check if branding already exists for this user
        if CompanyBranding.objects.filter(user=request.user).exists():
            return error(
                message="Company branding already exists for this user. Use PUT to update.",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Create new branding
        branding = CompanyBranding(user=request.user)
        serializer = CompanyBrandingSerializer(branding, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(message="Invalid branding data.", errors=serializer.errors)

        serializer.save()
        return success(
            data=serializer.data,
            message="Company branding created successfully.",
            status_code=status.HTTP_201_CREATED
        )

    def put(self, request):
        branding, _ = CompanyBranding.objects.get_or_create(user=request.user)
        serializer = CompanyBrandingSerializer(branding, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(message="Invalid branding data.", errors=serializer.errors)

        serializer.save()
        return success(data=serializer.data, message="Company branding updated successfully.")


class HelpCenterOverviewAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        def _short(text, limit=110):
            if not text:
                return ""
            text = str(text).strip()
            return text if len(text) <= limit else f"{text[:limit - 3]}..."

        search = request.query_params.get("search")
        queryset = HelpArticle.objects.filter(is_active=True)
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(content__icontains=search)
                | Q(short_description__icontains=search)
            )

        grouped = {
            "getting_started": HelpArticleSerializer(queryset.filter(section="getting_started")[:20], many=True).data,
            "billing": HelpArticleSerializer(queryset.filter(section="billing")[:20], many=True).data,
            "templates": HelpArticleSerializer(queryset.filter(section="templates")[:20], many=True).data,
        }

        popular_articles = HelpArticleSerializer(
            queryset.filter(is_popular=True)[:10],
            many=True,
        ).data

        most_requested = list(
            DocumentRequest.objects.values("document_name", "status")
            .annotate(total_requests=Count("id"))
            .order_by("-total_requests")[:10]
        )

        # Compact view model for card-based frontend layout
        section_meta = {
            "getting_started": {
                "title": "Getting Started",
                "subtitle": "Learn how to create and generate your first document.",
            },
            "billing": {
                "title": "Billing & Payments",
                "subtitle": "Understand subscriptions, credits, and invoices.",
            },
            "templates": {
                "title": "Templates & Docs",
                "subtitle": "How templates work and how to customize them.",
            },
        }

        section_cards = []
        for key in ["getting_started", "billing", "templates"]:
            section_articles = grouped.get(key, [])
            section_cards.append(
                {
                    "key": key,
                    "title": section_meta[key]["title"],
                    "subtitle": section_meta[key]["subtitle"],
                    "article_count": len(section_articles),
                    "articles": [
                        {
                            "id": article.get("id"),
                            "title": article.get("title"),
                            "slug": article.get("slug"),
                            "short_description": _short(article.get("short_description") or article.get("content"), 90),
                        }
                        for article in section_articles[:6]
                    ],
                }
            )

        popular_compact = [
            {
                "id": article.get("id"),
                "title": article.get("title"),
                "slug": article.get("slug"),
                "short_description": _short(article.get("short_description") or article.get("content"), 100),
            }
            for article in popular_articles
        ]

        most_requested_compact = [
            {
                "document_name": item.get("document_name"),
                "status": item.get("status"),
                "total_requests": item.get("total_requests", 0),
                "progress_percent": min(100, int((item.get("total_requests", 0) / 30) * 100)),
            }
            for item in most_requested
        ]

        data = {
            "header": {
                "title": "Help Center",
                "subtitle": "Find answers, guides, and support for using FORMEXL.",
            },
            "cards": section_cards,
            "popular_articles_compact": popular_compact,
            "most_requested_compact": most_requested_compact,
            "sections": grouped,
            "popular_articles": popular_articles,
            "most_requested_documents": most_requested,
        }
        return success(data=data, message="Help center data fetched successfully.")


class DocumentRequestAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        serializer = DocumentRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error(message="Invalid request data.", errors=serializer.errors)

        document_request = serializer.save(user=request.user)
        return success(data=DocumentRequestSerializer(document_request).data, message="Document request submitted successfully.", status_code=201)


class SettingsOverviewAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        profile = UserProfile.objects.filter(user=request.user).first()
        wallet, _ = CreditWallet.objects.get_or_create(user=request.user)
        active_subscription = Subscription.objects.filter(user=request.user, status="active").first()

        data = {
            "profile": {
                "email": request.user.email,
                "name": f"{profile.first_name} {profile.last_name}".strip() if profile else "",
                "phone": profile.phone if profile else None,
                "address": None,
            },
            "subscription": {
                "plan": active_subscription.subscriptionpackage.billing_cycle if active_subscription and active_subscription.subscriptionpackage else "Free",
                "status": active_subscription.status if active_subscription else "inactive",
                "credits_used": wallet.credits_used,
                "credits_limit": wallet.credits_limit,
            },
            "danger_zone": {
                "can_cancel_subscription": bool(active_subscription),
                "can_delete_account": True,
            },
        }
        return success(data=data, message="Settings overview fetched successfully.")


class DeleteAccountAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        confirm_text = request.data.get("confirm_text")
        if confirm_text != "DELETE":
            return error(message="Invalid confirmation text. Send confirm_text=DELETE.")

        user = request.user
        user.is_active = False
        user.save(update_fields=["is_active", "updated_at"])
        return success(message="Account deactivated successfully.")


class DocumentCopyAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, document_id):
        source_doc = GeneratedDocument.objects.filter(id=document_id, user=request.user).first()
        if not source_doc:
            return error(message="Document not found.", status_code=404)

        copied_doc = GeneratedDocument.objects.create(
            user=source_doc.user,
            category=source_doc.category,
            document_type=source_doc.document_type,
            template=source_doc.template,
            structure=source_doc.structure,
            name=f"{source_doc.name} (Copy)",
            form_data=source_doc.form_data,
            input_fingerprint=source_doc.input_fingerprint,
            rendered_content=source_doc.rendered_content,
            status="active",
            credit_used=0,
        )
        return success(
            data=GeneratedDocumentSerializer(copied_doc).data,
            message="Document copy created successfully.",
            status_code=201,
        )
