"""
Professional document PDF rendering engine with reusable structures.
Supports automatic layout, multi-page handling, signatures, and consistent styling.
"""
import io
import os
import re
from types import SimpleNamespace
from datetime import datetime
from html import unescape
from PIL import Image

from django.conf import settings
from .serializers import render_text_as_html


def _safe_text(value):
    """Convert value to safe string, handle None."""
    if value is None:
        return ""
    return str(value)


def format_signing_timestamp(dt):
    """
    Format signing timestamp to standard enterprise format:
    e.g. 'Signed: October 13, 2026 at 8:33 AM EDT'
    """
    if not dt:
        return None
    if isinstance(dt, str):
        try:
            from dateutil import parser
            dt = parser.parse(dt)
        except Exception:
            return f"Signed: {dt}"
    try:
        from django.utils import timezone
        local_dt = timezone.localtime(dt) if timezone.is_aware(dt) else dt
        date_str = local_dt.strftime("%B %d, %Y")
        time_str = local_dt.strftime("%I:%M %p").lstrip("0")
        tz_str = local_dt.strftime("%Z")
        if tz_str and not tz_str.startswith(("+", "-")) and tz_str != "UTC":
            return f"Signed: {date_str} at {time_str} {tz_str}"
        elif tz_str and tz_str != "UTC":
            return f"Signed: {date_str} at {time_str} ({tz_str})"
        return f"Signed: {date_str} at {time_str}"
    except Exception:
        return f"Signed: {dt.strftime('%B %d, %Y at %I:%M %p')}"


def _get_output_path(document_id, user_id):
    """Get absolute and relative paths for document storage."""
    rel_dir = os.path.join("generated_documents", str(user_id))
    abs_dir = os.path.join(settings.MEDIA_ROOT, rel_dir)
    os.makedirs(abs_dir, exist_ok=True)
    filename = f"document_{document_id}.pdf"
    return os.path.join(abs_dir, filename), os.path.join(rel_dir, filename).replace('\\', '/')


def _get_output_path_signed(document_id, user_id):
    """Return path for signed PDF variant."""
    rel_dir = os.path.join("generated_documents", str(user_id))
    abs_dir = os.path.join(settings.MEDIA_ROOT, rel_dir)
    os.makedirs(abs_dir, exist_ok=True)
    filename = f"document_{document_id}_signed.pdf"
    return os.path.join(abs_dir, filename), os.path.join(rel_dir, filename).replace('\\', '/')


def _load_logo(branding):
    """Load and validate company logo for PDF embedding."""
    if not branding or not branding.logo:
        return None
    
    logo_path = branding.logo.path
    if not os.path.exists(logo_path):
        return None
    
    try:
        img = Image.open(logo_path)
        return img
    except Exception:
        return None


PX_TO_MM = 25.4 / 96.0
MARGIN_70PX_MM = 70 * PX_TO_MM


def _scale_logo(logo_img, width_mm):
    """Scale logo to fit PDF width constraint while maintaining aspect ratio."""
    from reportlab.lib.units import mm
    
    if not logo_img:
        return None
    
    width_px = width_mm * mm / 72 * 96  # Convert mm to pixels (rough)
    aspect_ratio = logo_img.height / logo_img.width
    height_px = width_px * aspect_ratio
    
    # Resize keeping aspect ratio
    logo_img.thumbnail((int(width_px), int(height_px)), Image.Resampling.LANCZOS)
    return logo_img


class ProfessionalDocumentRenderer:
    """
    Renders documents with reusable structures.
    Handles headers, footers, signatures, multi-page layout, and consistent styling.
    """
    
    def __init__(self, document, structure, branding=None):
        """
        Initialize renderer with document, its structure, and optional branding.
        
        Args:
            document: GeneratedDocument instance
            structure: DocumentStructure instance
            branding: CompanyBranding instance (optional)
        """
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
        from reportlab.lib import colors
        
        self.document = document
        self.structure = structure
        self.branding = branding
        self.canvas_class = canvas
        self.A4 = A4
        self.mm = mm
        self.colors = colors
        
        # Page setup
        self.page_width, self.page_height = A4
        fixed_margin = MARGIN_70PX_MM * mm
        self.left_margin = fixed_margin
        self.right_margin = fixed_margin
        self.top_margin = fixed_margin
        self.bottom_margin = fixed_margin
        self.content_width = self.page_width - self.left_margin - self.right_margin

    def _content_start_y(self):
        # Keep generated documents starting near the top regardless of oversized structure margins.
        return self.page_height - self.top_margin
    
    def _format_document_date(self):
        dt = getattr(self.document, "generated_at", None) or datetime.utcnow()
        return dt.strftime("%B %d, %Y")

    def _wrap_text(self, text, max_width_pt, font_name, font_size):
        """Wrap text by rendered width (points)."""
        from reportlab.pdfbase.pdfmetrics import stringWidth

        text = _safe_text(text).strip()
        if not text:
            return [""]

        words = text.split()
        lines = []
        current = []
        for word in words:
            probe = " ".join(current + [word])
            if stringWidth(probe, font_name, font_size) <= max_width_pt:
                current.append(word)
                continue
            if current:
                lines.append(" ".join(current))
            current = [word]

        if current:
            lines.append(" ".join(current))
        return lines or [""]

    def _normalize_value(self, value):
        if value is None:
            return ""
        if isinstance(value, dict):
            parts = [f"{_safe_text(k).replace('_', ' ').title()}: {_safe_text(v)}" for k, v in value.items()]
            return " | ".join(parts)
        if isinstance(value, list):
            return ", ".join(_safe_text(v) for v in value)
        return _safe_text(value)

    def _ensure_space(self, c, y, required_height, page_num):
        min_y = self.bottom_margin + 4 * self.mm
        if y - required_height >= min_y:
            return y, page_num

        self._draw_footer(c, page_num)
        c.showPage()
        page_num += 1
        y = self._draw_header(c, self._content_start_y())
        return y, page_num

    def _draw_header(self, c, y_position):
        """Header is intentionally disabled for plain template-style output."""
        return y_position

    def _draw_footer(self, c, page_num):
        """Footer hidden to keep previews consistent with plain template cards."""
        return

    def _split_form_sections(self, form_data):
        party_keywords = {
            "party", "client", "vendor", "recipient", "sender", "customer", "company",
            "name", "email", "phone", "address", "contact",
        }
        terms_keywords = {
            "term", "condition", "clause", "description", "summary", "scope", "policy", "duration", "note",
        }
        signature_keywords = {"signature", "sign", "signed", "signer"}

        sections = {
            "party": [],
            "main": [],
            "terms": [],
            "signature": [],
        }

        for raw_key, raw_value in (form_data or {}).items():
            key = _safe_text(raw_key)
            key_lower = key.lower()
            normalized_value = self._normalize_value(raw_value)
            if not normalized_value:
                continue

            if any(token in key_lower for token in signature_keywords):
                sections["signature"].append((key, normalized_value))
            elif any(token in key_lower for token in terms_keywords):
                sections["terms"].append((key, normalized_value))
            elif any(token in key_lower for token in party_keywords):
                sections["party"].append((key, normalized_value))
            else:
                sections["main"].append((key, normalized_value))

        return sections

    def _draw_section_heading(self, c, y, page_num, title):
        y, page_num = self._ensure_space(c, y, 10 * self.mm, page_num)
        c.setFillColor(self.colors.HexColor("#111827"))
        c.setFont("Helvetica-Bold", 12)
        c.drawString(self.left_margin, y, title)
        y -= 2 * self.mm
        c.setStrokeColor(self.colors.HexColor("#D1D5DB"))
        c.setLineWidth(0.6)
        c.line(self.left_margin, y, self.page_width - self.right_margin, y)
        y -= 5 * self.mm
        return y, page_num

    def _draw_key_value_items(self, c, y, page_num, items):
        for key, value in items:
            label = _safe_text(key).replace("_", " ").title()
            is_paragraph = len(value) > 140 or any(k in key.lower() for k in ["term", "description", "summary", "scope", "clause"])
            lines = self._wrap_text(value, self.content_width, "Helvetica", 10)
            required_height = (6 * self.mm) + (len(lines) * 4.4 * self.mm) + (2 * self.mm)
            y, page_num = self._ensure_space(c, y, required_height, page_num)

            c.setFillColor(self.colors.HexColor("#374151"))
            c.setFont("Helvetica-Bold", 10)
            c.drawString(self.left_margin, y, label)
            y -= 4.5 * self.mm

            c.setFillColor(self.colors.HexColor("#111827"))
            c.setFont("Helvetica", 10)
            for line in lines:
                c.drawString(self.left_margin, y, line)
                y -= 4.2 * self.mm

            y -= 2.2 * self.mm if is_paragraph else 1.2 * self.mm

        return y, page_num

    def _resolve_local_image_path(self, src):
        if not src or src.startswith("data:"):
            return None
        from urllib.parse import urlparse
        clean_src = src.strip()
        if "/media/" in clean_src:
            parsed = urlparse(clean_src)
            path = parsed.path
            idx = path.find('/media/')
            if idx != -1:
                rel = path[idx + len('/media/'):].lstrip('/')
                abs_path = os.path.join(settings.MEDIA_ROOT, rel)
                return os.path.normpath(abs_path)
        elif clean_src.startswith("media/"):
            rel = clean_src[len("media/"):].lstrip('/')
            abs_path = os.path.join(settings.MEDIA_ROOT, rel)
            return os.path.normpath(abs_path)
        if os.path.isabs(clean_src) and os.path.exists(clean_src):
            return clean_src
        return None

    def _prepare_signature_image_reader(self, src):
        """
        Prepares a ReportLab ImageReader from base64 or file path,
        cropping empty transparent padding and compositing onto white background.
        """
        from reportlab.lib.utils import ImageReader

        if src.startswith("data:image/") and ";base64," in src:
            import base64
            b64_str = src.split(";base64,")[1]
            img_bytes = base64.b64decode(b64_str)
            raw_io = io.BytesIO(img_bytes)
        else:
            img_path = self._resolve_local_image_path(src)
            if not img_path or not os.path.exists(img_path):
                if src.startswith(("http://", "https://")):
                    try:
                        import urllib.request
                        req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
                        with urllib.request.urlopen(req, timeout=5) as resp:
                            raw_io = io.BytesIO(resp.read())
                    except Exception:
                        return None, 0, 0
                else:
                    return None, 0, 0
            else:
                raw_io = img_path

        pil_img = Image.open(raw_io)
        if pil_img.mode in ("RGBA", "LA") or (pil_img.mode == "P" and "transparency" in pil_img.info):
            alpha = pil_img.convert("RGBA").split()[-1]
            bbox = alpha.getbbox()
            if bbox:
                pad = 8
                crop_box = (
                    max(0, bbox[0] - pad),
                    max(0, bbox[1] - pad),
                    min(pil_img.width, bbox[2] + pad),
                    min(pil_img.height, bbox[3] + pad)
                )
                pil_img = pil_img.crop(crop_box)
            bg = Image.new("RGBA", pil_img.size, (255, 255, 255, 255))
            pil_img = Image.alpha_composite(bg, pil_img.convert("RGBA")).convert("RGB")
        elif pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")

        out_io = io.BytesIO()
        pil_img.save(out_io, format="PNG")
        out_io.seek(0)

        reader = ImageReader(out_io)
        iw, ih = reader.getSize()
        return reader, iw, ih

    def _draw_signature_image_inline(self, c, y, page_num, label, src):
        """
        Draws inline signature block cleanly: label on top, handwritten signature image below with no overlap.
        """
        clean_label = (label or "Signature").strip().rstrip(":")
        role_label = clean_label.upper()

        reader, iw, ih = None, 0, 0
        try:
            reader, iw, ih = self._prepare_signature_image_reader(src)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to prepare signature image: {e}")

        if not reader or iw <= 0 or ih <= 0:
            required_height = 28
            y, page_num = self._ensure_space(c, y, required_height, page_num)
            c.setFillColor(self.colors.HexColor("#1F2937"))
            c.setFont("Helvetica-Bold", 9.5)
            c.drawString(self.left_margin, y, role_label)
            c.setFont("Helvetica-Oblique", 11)
            c.setFillColor(self.colors.HexColor("#1E3A8A"))
            c.drawString(self.left_margin, y - 14, "[Signed Electronically]")
            y -= required_height
            return y, page_num

        aspect = ih / float(iw)
        max_w, max_h = 160, 42
        w = min(iw, max_w)
        h = w * aspect
        if h > max_h:
            h = max_h
            w = h / aspect if aspect > 0 else max_w

        total_h = 14 + 6 + h + 8
        y, page_num = self._ensure_space(c, y, total_h, page_num)

        # Draw label clearly above the signature
        c.setFillColor(self.colors.HexColor("#1F2937"))
        c.setFont("Helvetica-Bold", 9.5)
        c.drawString(self.left_margin, y, role_label)

        # Draw signature image strictly below the label (guaranteed zero overlap)
        img_y = y - 14 - h
        c.drawImage(reader, self.left_margin, img_y, width=w, height=h, mask=None)

        y = img_y - 8
        return y, page_num

    def _draw_standalone_image(self, c, y, page_num, src):
        """
        Draws a standalone image block (e.g. document attachment, photo).
        """
        try:
            reader, iw, ih = self._prepare_signature_image_reader(src)
            if not reader or iw <= 0 or ih <= 0:
                return y, page_num

            aspect = ih / float(iw)
            max_w = self.content_width * 0.4
            max_h = 40 * self.mm
            w = min(iw, max_w)
            h = w * aspect
            if h > max_h:
                h = max_h
                w = h / aspect if aspect > 0 else max_w

            y, page_num = self._ensure_space(c, y, h + 10, page_num)
            y -= h
            c.drawImage(reader, self.left_margin, y, width=w, height=h, mask=None)
            y -= 10
            return y, page_num
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to draw standalone image: {e}")
            return y, page_num

    def _draw_rendered_body(self, c, y, page_num, rendered_content):
        blocks = self._extract_text_blocks_from_html(rendered_content)
        if not blocks:
            return y, page_num

        block_gap_pt = 6.0
        for block in blocks:
            style = block.get("style", "p")

            if style == "signature_line":
                y, page_num = self._draw_signature_image_inline(
                    c, y, page_num,
                    label=block.get("label", "Signature:"),
                    src=block.get("src", "")
                )
                continue

            if style == "image":
                src = block.get("src") or block.get("text", "")
                if src:
                    y, page_num = self._draw_standalone_image(c, y, page_num, src)
                continue

            text = _safe_text(block.get("text")).strip()
            if not text:
                # Blank lines in template should produce clear visual gaps.
                y, page_num = self._ensure_space(c, y, 12, page_num)
                y -= 12
                continue

            # Safety check: if text is a data:image base64 string, draw as image, NEVER as text!
            if text.startswith("data:image/") and ";base64," in text:
                y, page_num = self._draw_standalone_image(c, y, page_num, text)
                continue

            # Check if text is a direct image URL
            if re.match(r"^(https?://[^\s]+|/media/[^\s]+)\.(?:png|jpg|jpeg|gif|webp)(?:\?.*)?$", text, re.IGNORECASE):
                y, page_num = self._draw_standalone_image(c, y, page_num, text)
                continue

            # Check if text contains a URL (like from an anchor tag or direct link)
            link_url = None
            link_match = re.search(r"(https?://[^\s]+|/media/[^\s]+)", text, re.IGNORECASE)
            if link_match:
                link_url = link_match.group(0)
                # Remove the raw URL from the display text
                text = text.replace(link_url, "").strip()
                if not text:
                    text = "🔗 View Attached Document"

            is_heading = style in {"h1", "h2", "h3", "h4"} or (
                len(text) <= 80 and re.match(r"^[A-Z0-9\s&()/'\-]+$", text)
            )
            if is_heading:
                font_name, font_size = "Helvetica-Bold", 9.5
                leading = 12
                before_gap, after_gap = 8, 4
                text_color = self.colors.HexColor("#4B5563")
            else:
                font_name, font_size = "Helvetica", 9
                leading = 11
                before_gap, after_gap = 0, block_gap_pt
                text_color = self.colors.HexColor("#6B7280")

            if link_url:
                text_color = self.colors.HexColor("#2563EB")  # Blue color for links
            elif text.startswith("[") and text.endswith("]"):
                text_color = self.colors.HexColor("#9CA3AF")

            # If text has rich formatting tags (<b>, <i>, <u>, <strike>, etc.), render via ReportLab Paragraph
            has_rich_formatting = bool(re.search(r"</?(b|i|u|strike|sub|sup)\b", text, re.IGNORECASE))
            if has_rich_formatting and not link_url and not is_heading:
                try:
                    from reportlab.platypus import Paragraph
                    from reportlab.lib.styles import ParagraphStyle
                    p_style = ParagraphStyle(
                        f"RT_{font_name}_{font_size}",
                        fontName=font_name,
                        fontSize=font_size,
                        leading=leading,
                        textColor=text_color,
                    )
                    p = Paragraph(text, p_style)
                    w, h = p.wrap(self.content_width, self.page_height)
                    required_height = max(leading, before_gap + h + after_gap)
                    y, page_num = self._ensure_space(c, y, required_height, page_num)
                    if before_gap:
                        y -= before_gap
                    p.drawOn(c, self.left_margin, y - h)
                    y -= (h + after_gap)
                    continue
                except Exception:
                    # Fallback to plain text if malformed XML
                    text = re.sub(r"<[^>]+>", "", text)

            lines = self._wrap_text(text, self.content_width, font_name, font_size)
            required_height = max(leading, before_gap + (len(lines) * leading) + after_gap)
            y, page_num = self._ensure_space(c, y, required_height, page_num)

            if before_gap:
                y -= before_gap

            c.setFillColor(text_color)
            c.setFont(font_name, font_size)
            for line in lines:
                c.drawString(self.left_margin, y, line)
                
                if link_url:
                    from reportlab.pdfbase.pdfmetrics import stringWidth
                    line_width = stringWidth(line, font_name, font_size)
                    rect = (self.left_margin, y - 2, self.left_margin + line_width, y + font_size)
                    c.linkURL(link_url, rect)
                    
                    c.setStrokeColor(self.colors.HexColor("#2563EB"))
                    c.setLineWidth(0.5)
                    c.line(self.left_margin, y - 1, self.left_margin + line_width, y - 1)
                
                y -= leading

            y -= after_gap

        return y, page_num

    def _extract_text_blocks_from_html(self, html_content):
        content = _safe_text(html_content).replace("\r", "")
        if not content.strip():
            return []

        # 1. Match signature lines with img tag
        sig_img_re = re.compile(
            r"(?:<strong>\s*Signature:\s*</strong>|Signature:)\s*(?:<br\s*/?>\s*)*<img[^>]+src=[\"']([^\"']+)[\"'][^>]*>",
            re.IGNORECASE
        )
        content = sig_img_re.sub(r"\n[[SIG_LINE:\1]]\n", content)

        # 2. Match standalone img tags
        img_re = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"'][^>]*>", re.IGNORECASE)
        content = img_re.sub(r"\n[[IMG_BLOCK:\1]]\n", content)

        # 3. Anchor tags
        a_re = re.compile(r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.IGNORECASE)
        content = a_re.sub(r"\2 \1", content)

        # 4. Tables
        tr_re = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
        for tr_match in tr_re.finditer(content):
            row_inner = tr_match.group(1)
            cell_re = re.compile(r"<(td|th)[^>]*>(.*?)</\1>", re.IGNORECASE | re.DOTALL)
            cells = [unescape(re.sub(r"<[^>]+>", "", c.group(2))).strip() for c in cell_re.finditer(row_inner)]
            if cells:
                row_str = " | ".join(cells)
                content = content.replace(tr_match.group(0), f"\n{row_str}\n")

        # 5. Headings
        h_re = re.compile(r"<(h[1-4])[^>]*>(.*?)</\1>", re.IGNORECASE | re.DOTALL)
        content = h_re.sub(lambda m: f"\n[[H:{m.group(1).lower()}:{m.group(2)}]]\n", content)

        # 6. List items
        li_re = re.compile(r"<li[^>]*>(.*?)</li>", re.IGNORECASE | re.DOTALL)
        content = li_re.sub(r"\n- \1\n", content)

        # 7. Breaks, paragraphs, divs, tables
        content = re.sub(r"<\s*br\s*/?\s*>", "\n", content, flags=re.IGNORECASE)
        content = re.sub(r"<\s*hr\s*/?\s*>", "\n\n", content, flags=re.IGNORECASE)
        content = re.sub(r"</\s*(p|div|tr|table|thead|tbody)\s*>", "\n", content, flags=re.IGNORECASE)
        content = re.sub(r"<\s*(p|div|tr|table|thead|tbody)[^>]*>", "\n", content, flags=re.IGNORECASE)

        # Convert strong/em/del/s tags to standard ReportLab tags (b/i/strike)
        content = re.sub(r"<\s*strong\b[^>]*>", "<b>", content, flags=re.IGNORECASE)
        content = re.sub(r"<\s*/\s*strong\s*>", "</b>", content, flags=re.IGNORECASE)
        content = re.sub(r"<\s*em\b[^>]*>", "<i>", content, flags=re.IGNORECASE)
        content = re.sub(r"<\s*/\s*em\s*>", "</i>", content, flags=re.IGNORECASE)
        content = re.sub(r"<\s*(del|s)\b[^>]*>", "<strike>", content, flags=re.IGNORECASE)
        content = re.sub(r"<\s*/\s*(del|s)\s*>", "</strike>", content, flags=re.IGNORECASE)

        # 8. Strip remaining HTML tags EXCEPT safe inline formatting tags
        content = re.sub(r"<(?!/?(b|i|u|strike|sub|sup)\b)[^>]+>", "", content, flags=re.IGNORECASE)

        blocks = []
        for line in content.split("\n"):
            clean = line.strip()
            if not clean:
                continue
            if clean.startswith("[[SIG_LINE:") and clean.endswith("]]"):
                src = clean[len("[[SIG_LINE:"): -2].strip()
                blocks.append({"style": "signature_line", "label": "Signature:", "src": src})
            elif clean.startswith("[[IMG_BLOCK:") and clean.endswith("]]"):
                src = clean[len("[[IMG_BLOCK:"): -2].strip()
                blocks.append({"style": "image", "src": src})
            elif clean.startswith("[[H:") and clean.endswith("]]"):
                parts = clean[4:-2].split(":", 1)
                tag = parts[0]
                txt = unescape(parts[1]).strip()
                blocks.append({"style": tag, "text": txt})
            elif clean.startswith("data:image/") and ";base64," in clean:
                blocks.append({"style": "image", "src": clean})
            else:
                txt = unescape(clean)
                blocks.append({"style": "p", "text": txt})
        return blocks

    def _strip_legacy_signature_markup(self, html_content):
        """Strip raw legacy signature text or trailing placeholders so they don't duplicate."""
        if not html_content:
            return ""
        content = html_content
        content = re.sub(
            r"(?:<br\s*/?>\s*)?<p>\s*<strong>\s*Signature by[^<]+</strong>.*?</p>",
            "",
            content,
            flags=re.IGNORECASE | re.DOTALL,
        )
        content = re.sub(
            r"(?:<br\s*/?>\s*)?<strong>\s*Signature by[^<]+</strong>\s*(?:\n|<br\s*/?>)*",
            "",
            content,
            flags=re.IGNORECASE,
        )
        content = re.sub(
            r"(?:<strong>\s*Signature:\s*</strong>|Signature:)\s*(?:_+|<img[^>]+>|\[Signed Electronically\])",
            "",
            content,
            flags=re.IGNORECASE,
        )
        content = re.sub(
            r"(?:<strong>\s*Date:\s*</strong>|Date:)\s*(?:_+|\d{4}-\d{2}-\d{2}[^\n<]*)",
            "",
            content,
            flags=re.IGNORECASE,
        )
        content = re.sub(r"\[\[SIG_LINE:[^\]]+\]\]", "", content)
        content = re.sub(r"<p>\s*<strong>\s*Signature:\s*</strong>.*?</p>", "", content, flags=re.IGNORECASE | re.DOTALL)
        return content.strip()

    def _measure_signature_block_height(self, block, block_width):
        """Pre-calculate total vertical height of a standardized signature block."""
        h_role = 18

        sig_val = block.get("signature_value")
        if sig_val and block.get("is_signed"):
            if sig_val.startswith("data:image/") or sig_val.startswith("http") or "/media/" in sig_val:
                try:
                    _, iw, ih = self._prepare_signature_image_reader(sig_val)
                    if iw > 0 and ih > 0:
                        aspect = ih / float(iw)
                        max_w, max_h = min(160, block_width - 10), 42
                        w = min(iw, max_w)
                        h = min(w * aspect, max_h)
                    else:
                        h = 36
                except Exception:
                    h = 36
            else:
                h = 18
        else:
            h = 24

        h_sig = h + 8
        h_name = 13
        h_title = 13 if block.get("job_title") else 0
        h_date = 12 if block.get("signed_timestamp") or not block.get("is_signed") else 0

        return h_role + h_sig + h_name + h_title + h_date

    def _draw_standard_signature_block(self, c, x, y, block_width, block):
        """
        Draws a standardized enterprise signature block:
        AUTHORIZED SIGNER
        [Handwritten Signature]
        John Smith
        Director of Human Resources
        Signed: October 13, 2026 at 8:33 AM EDT
        """
        role = (block.get("role") or "AUTHORIZED SIGNER").strip().upper()
        full_name = (block.get("full_name") or "Signer").strip()
        job_title = (block.get("job_title") or "").strip() or None
        signed_timestamp = block.get("signed_timestamp")
        is_signed = block.get("is_signed", False)
        sig_val = block.get("signature_value")

        y_cursor = y

        # 1. Display role clearly above the signature
        c.setFont("Helvetica-Bold", 9.5)
        c.setFillColor(self.colors.HexColor("#1F2937"))
        c.drawString(x, y_cursor, role)
        y_cursor -= (12 + 6)

        # 2. Display handwritten signature
        if is_signed and sig_val:
            if sig_val.startswith("data:image/") or sig_val.startswith("http") or "/media/" in sig_val:
                reader, iw, ih = None, 0, 0
                try:
                    reader, iw, ih = self._prepare_signature_image_reader(sig_val)
                except Exception:
                    pass

                if reader and iw > 0 and ih > 0:
                    aspect = ih / float(iw)
                    max_w = min(160, block_width - 10)
                    max_h = 42
                    w = min(iw, max_w)
                    h = w * aspect
                    if h > max_h:
                        h = max_h
                        w = h / aspect if aspect > 0 else max_w

                    img_y = y_cursor - h
                    c.drawImage(reader, x, img_y, width=w, height=h, mask=None)
                    y_cursor = img_y - 8
                else:
                    c.setFont("Helvetica-Oblique", 12)
                    c.setFillColor(self.colors.HexColor("#1E3A8A"))
                    c.drawString(x, y_cursor - 12, "[Signed Electronically]")
                    y_cursor -= (16 + 8)
            else:
                c.setFont("Helvetica-Oblique", 13)
                c.setFillColor(self.colors.HexColor("#1E3A8A"))
                c.drawString(x, y_cursor - 12, str(sig_val))
                y_cursor -= (16 + 8)
        else:
            c.setStrokeColor(self.colors.HexColor("#9CA3AF"))
            c.setLineWidth(0.8)
            line_w = min(160, block_width - 10)
            c.line(x, y_cursor - 16, x + line_w, y_cursor - 16)
            y_cursor -= (20 + 8)

        # 3. Display signer's full name directly beneath the signature
        c.setFont("Helvetica-Bold", 9.5)
        c.setFillColor(self.colors.HexColor("#111827"))
        c.drawString(x, y_cursor, full_name[:40])
        y_cursor -= 13

        # 4. Display signer's job title when available
        if job_title:
            c.setFont("Helvetica", 8.5)
            c.setFillColor(self.colors.HexColor("#4B5563"))
            c.drawString(x, y_cursor, job_title[:45])
            y_cursor -= 12

        # 5. Display actual signing date and time immediately below
        if signed_timestamp:
            c.setFont("Helvetica", 8)
            c.setFillColor(self.colors.HexColor("#6B7280"))
            c.drawString(x, y_cursor, signed_timestamp)
            y_cursor -= 11
        elif not is_signed:
            c.setFont("Helvetica", 8)
            c.setFillColor(self.colors.HexColor("#9CA3AF"))
            c.drawString(x, y_cursor, "Date: ________________________")
            y_cursor -= 11

    def _draw_enterprise_signature_requests(self, c, y, page_num, signature_requests):
        """
        Draws enterprise-standard signature blocks for all SignatureRequests.
        Supports 1 signer, 2 signers (side-by-side dual column), or multiple signers in grid rows.
        Guarantees keep-together (entire row stays on same page) and zero overlap.
        """
        if not signature_requests:
            return y, page_num

        blocks_data = []
        for req in signature_requests:
            role = (req.signer_role or "").strip()
            if not role:
                owner_id = getattr(self.document, "user_id", None)
                owner_email = getattr(self.document.user, "email", None) if getattr(self.document, "user", None) else None
                if (req.sender_id and req.sender_id == owner_id) or (owner_email and req.recipient_email == owner_email):
                    role = "AUTHORIZED SIGNER"
                elif getattr(req, "depends_on_id", None) or "owner" in (req.recipient_name or "").lower():
                    role = "AUTHORIZED SIGNER"
                else:
                    role = "CLIENT"

            full_name = (req.recipient_name or "").strip()
            if not full_name:
                full_name = req.recipient_email or "Signer"

            job_title = (req.signer_title or "").strip() or None

            signed_timestamp = None
            if req.status == "signed" and req.signed_at:
                signed_timestamp = format_signing_timestamp(req.signed_at)

            blocks_data.append({
                "role": role,
                "full_name": full_name,
                "job_title": job_title,
                "signature_value": req.signature_value if req.status == "signed" else None,
                "signature_type": req.signature_type or "drawn",
                "signed_timestamp": signed_timestamp,
                "is_signed": req.status == "signed",
            })

        y, page_num = self._ensure_space(c, y, 24, page_num)
        y -= 12

        row_size = 2
        col_gap = 24
        col_width = (self.content_width - col_gap) / 2

        for i in range(0, len(blocks_data), row_size):
            row_blocks = blocks_data[i:i + row_size]

            row_heights = [self._measure_signature_block_height(b, col_width) for b in row_blocks]
            max_row_height = max(row_heights) if row_heights else 90

            y, page_num = self._ensure_space(c, y, max_row_height + 16, page_num)

            for col_idx, b in enumerate(row_blocks):
                if len(row_blocks) == 1 and len(blocks_data) == 1:
                    block_x = self.left_margin
                    actual_width = min(260, self.content_width)
                else:
                    block_x = self.left_margin + col_idx * (col_width + col_gap)
                    actual_width = col_width

                self._draw_standard_signature_block(c, block_x, y, actual_width, b)

            y -= (max_row_height + 16)

        return y, page_num

    def _draw_signature_section(self, c, y, page_num, signature_items):
        if not self.structure.has_signature_section:
            return y, page_num

        y, page_num = self._draw_section_heading(c, y, page_num, "Signatures")

        signer_names = []
        for key, value in signature_items:
            if "name" in key.lower() or "party" in key.lower() or "signer" in key.lower():
                signer_names.append(value)

        while len(signer_names) < 2:
            signer_names.append(f"Signer {len(signer_names) + 1}")

        blocks = [
            {
                "role": "CLIENT" if idx == 0 else "AUTHORIZED SIGNER",
                "full_name": signer_names[idx][:36],
                "is_signed": False,
            }
            for idx in range(2)
        ]

        col_gap = 24
        col_width = (self.content_width - col_gap) / 2
        max_h = max(self._measure_signature_block_height(b, col_width) for b in blocks)
        y, page_num = self._ensure_space(c, y, max_h + 16, page_num)

        for idx, b in enumerate(blocks):
            x = self.left_margin + idx * (col_width + col_gap)
            self._draw_standard_signature_block(c, x, y, col_width, b)

        y -= (max_h + 20)
        return y, page_num

    def render(self, signed=False):
        """Generate PDF using a unified base template across document types.

        If `signed=True`, writes to a separate signed filename so original
        unsigned PDF is preserved.
        """
        if signed:
            abs_path, rel_path = _get_output_path_signed(self.document.id, self.document.user_id)
        else:
            abs_path, rel_path = _get_output_path(self.document.id, self.document.user_id)

        buffer = io.BytesIO()
        c = self.canvas_class.Canvas(buffer, pagesize=self.A4)

        page_num = 1
        y = self._draw_header(c, self._content_start_y())

        rendered_content = _safe_text(getattr(self.document, "rendered_content", "")).strip()

        # Check for signature requests on this document
        signature_requests = []
        if hasattr(self.document, "signature_requests"):
            all_reqs = list(self.document.signature_requests.all().order_by("created_at", "id"))
            if any(r.status == "signed" for r in all_reqs) or signed:
                signature_requests = all_reqs

        if signature_requests:
            rendered_content = self._strip_legacy_signature_markup(rendered_content)

        if rendered_content:
            y, page_num = self._draw_rendered_body(c, y, page_num, rendered_content)
        else:
            sections = self._split_form_sections(self.document.form_data or {})

            if sections["party"]:
                y, page_num = self._draw_section_heading(c, y, page_num, "Party Information")
                y, page_num = self._draw_key_value_items(c, y, page_num, sections["party"])

            main_items = sections["main"]
            if main_items:
                y, page_num = self._draw_section_heading(c, y, page_num, "Main Content")
                y, page_num = self._draw_key_value_items(c, y, page_num, main_items)

            terms_items = sections["terms"]
            if terms_items:
                y, page_num = self._draw_section_heading(c, y, page_num, "Description / Terms")
                y, page_num = self._draw_key_value_items(c, y, page_num, terms_items)

            if not signature_requests:
                y, page_num = self._draw_signature_section(c, y, page_num, sections["signature"])

        if signature_requests:
            y, page_num = self._draw_enterprise_signature_requests(c, y, page_num, signature_requests)

        self._draw_footer(c, page_num)
        c.showPage()
        c.save()

        with open(abs_path, "wb") as pdf_file:
            pdf_file.write(buffer.getvalue())

        return abs_path, rel_path


def build_pdf_for_document(document, branding=None, signed=False):
    """
    Main entry point for PDF generation.
    Uses DocumentStructure for layout if available, falls back to default.
    """
    structure = getattr(document, "structure", None)
    if not structure:
        structure = SimpleNamespace(
            has_header=True,
            has_signature_section=False,
            has_date_field=True,
            has_page_numbers=True,
            has_footer=True,
            header_height_mm=30,
            footer_height_mm=16,
            left_margin_mm=20,
            right_margin_mm=20,
            top_margin_mm=20,
            bottom_margin_mm=16,
            line_spacing=1.2,
            logo_width_mm=36,
            logo_position="top_left",
        )

    renderer = ProfessionalDocumentRenderer(document, structure, branding)
    return renderer.render(signed=signed)
