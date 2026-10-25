from django.core.cache import cache
from django.core.management.base import BaseCommand

from apps.cms.models import CMS, FAQ
from apps.system_setting.models import (
	LandingPageBadge,
	LandingCheckoutBrand,
	LandingPageFeature,
	LandingPageHero,
	LandingPreviewSample,
	LandingPagePricing,
	LandingTestimonial,
)


HERO_DEFAULTS = {
	"title": "Generate professional business documents instantly",
	"subtitle": "Structured templates, fast generation, and instant PDF export.",
	"cta_primary": "Get Started Free",
	"cta_secondary": "View Templates",
	"is_active": True,
}

FEATURES = [
	("Choose a category", "Select the document type that matches your need.", 1),
	("Pick a template", "Choose from professional business-ready templates.", 2),
	("Fill structured fields", "Complete guided form fields with your data.", 3),
	("Preview", "Review the final output before downloading.", 4),
	("Download", "Export a polished PDF in seconds.", 5),
]

BADGES = [
	("SSL Secured", "shield", 1),
	("Secure Payments", "card", 2),
	("Instant PDF Export", "download", 3),
	("Cancel Anytime", "clock", 4),
	("No Hidden Fees", "check", 5),
	("Privacy Protected", "lock", 6),
]

PRICING = [
	("starter", "monthly", 19.00, 15, "Start with Starter and upgrade anytime.", False, 0, 1),
	("pro", "monthly", 39.99, 60, "Best value for business owners who generate documents regularly.", True, 0, 2),
	("business", "monthly", 99.99, 200, "Designed for teams and organizations with high document volumes.", False, 0, 3),
	("starter", "yearly", 182.40, 180, "Save 20% with yearly billing.", False, 20, 1),
	("pro", "yearly", 383.90, 720, "Best value for business owners - save 20%.", True, 20, 2),
	("business", "yearly", 959.90, 2400, "Designed for teams - save 20% with yearly billing.", False, 20, 3),
]

PRICING_FEATURES = {
	"starter": "15 Downloads per month\nUnlimited Previews\nAdd custom logo\nUp to 5 sends (Email/Sign)\nManual print & sign",
	"pro": "60 Downloads per month\nUnlimited Previews\nAdd custom logo\nFull Email & E-sign\nDownload & Print",
	"business": "200 Downloads per month\nUnlimited Previews\nAdd custom logo\nFull Email & E-sign\nPriority Support\nDownload & Print",
}

PRICING_FOOTER = (
	"Credits reset every billing cycle. No rollover. Cancel anytime. "
	"No contracts. Taxes may apply depending on your location."
)

FAQS = [
	("How can I create an account?", "Click the Sign Up button and complete the registration form."),
	("How do I reset my password?", "Use Forgot Password from the login page and follow the instructions."),
	("Is my personal information safe?", "Yes. We use industry-standard security controls to protect your data."),
]

CMS_SECTIONS = [
	{
		"section": "hero",
		"title": "Generate professional Business documents instantly, accurately, every time.",
		"sub_title": "Designed for small businesses, consultants, and growing teams.",
		"button_text": "Get Started Free",
		"button_link": "/signup",
		"other": "View Templates",
		"background_image": "/media/about_system/logo/5-ai-document-generator.webp",
	},
	{
		"section": "formexl_engineered",
		"title": "Most templates online are generic. Formexl is engineered.",
		"sub_title": "We do not just give you a block of text. Formexl generates structured documents designed for real business use cases.",
		"description": "Fill-in-the-blank system for rapid creation. Standardized formatting and compliance-ready updates.",
		"background_image": "/media/about_system/favicon/design-brand-overlapping-one-line-colour_8B6fW9t.webp",
	},
	{
		"section": "what_is_formexl",
		"title": "What is Formexl",
		"sub_title": "We turn document chaos into a structured, repeatable process.",
		"description": "A practical workflow that reduces formatting errors and saves time.",
		"background_image": "/media/about_system/logo/design-brand-overlapping-one-line-colour_DHES113.webp",
	},
	{
		"section": "what_formexl_is",
		"title": "What Formexl Is",
		"description": "A structured platform for generating professional business documents using guided templates.",
		"short_description": "Streamlined workflow that eliminates formatting errors and manual editing.",
	},
	{
		"section": "what_formexl_is_not",
		"title": "What Formexl Is Not",
		"description": "Not a messy copy-and-paste editor and not a generic low-quality template site.",
		"short_description": "Not a tool that requires manual formatting or rewriting.",
	},
	{
		"section": "how_it_works",
		"title": "How It Works",
		"sub_title": "Most documents take 2-5 minutes to complete.",
		"background_image": "/media/about_system/logo/a-room-with-a-large-picture-on-the-wall-and-a-camera-free-photo.webp",
	},
	{
		"section": "watch_video",
		"title": "Watch how Formexl works in 30 seconds",
		"sub_title": "See how professionals generate business documents in minutes.",
		"video_link": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
		"background_image": "/media/about_system/logo/office-employee-with-ai-generated-free-png.webp",
	},
	{
		"section": "document_categories",
		"title": "Document Categories",
		"sub_title": "Browse templates organized by business function.",
		"button_text": "Browse Templates",
		"button_link": "/templates",
	},
	{
		"section": "preview_samples",
		"title": "Preview Samples",
		"sub_title": "View our recently generated documents.",
		"button_text": "View All Samples",
		"button_link": "/samples",
		"background_image": "/media/about_system/logo/design-brand-overlapping-one-line-colour_8B6fW9t_1.webp",
	},
	{
		"section": "trusted_professionals",
		"title": "Trusted by Business Professionals",
		"sub_title": "See how teams are simplifying document creation with Formexl.",
	},
	{
		"section": "secure_checkout",
		"title": "Secure checkout powered by Stripe",
		"sub_title": "Cancel anytime. Subscription renews automatically at the end of each billing period.",
	},
	{
		"section": "faq",
		"title": "Frequently Asked Questions",
		"sub_title": "Everything you need to know about using Formexl.",
		"background_image": "/media/about_system/favicon/office-employee-with-ai-generated-free-png.webp",
	},
	{
		"section": "cta_free_downloads",
		"title": "Start with 1 Free Document Downloads",
		"sub_title": "Create a free account and get complimentary document downloads.",
		"button_text": "Get Started",
		"button_link": "/signup",
		"other": "No credit card required.",
	},
	{
		"section": "footer",
		"title": "FORMEXL",
		"sub_title": "Create a free account and get complimentary document downloads.",
	},
]

PREVIEW_SAMPLES = [
	("Invoice", "about_system/favicon/design-brand-overlapping-one-line-colour_8B6fW9t.webp", 1),
	("Business Report", "about_system/logo/design-brand-overlapping-one-line-colour_8B6fW9t_1.webp", 2),
	("Service Contract", "about_system/logo/design-brand-overlapping-one-line-colour_DHES113.webp", 3),
]

TESTIMONIALS = [
	(
		"Liam",
		"Small Business Owner",
		5,
		"Formexl has reduced our document preparation time significantly.",
		"avatars/1.jpg",
		1,
	),
	(
		"Noah",
		"Operations Manager",
		5,
		"The team loves how clean the interface is and how fast output is generated.",
		"avatars/2.jpg",
		2,
	),
	(
		"Oliver",
		"Project Lead",
		5,
		"Support is responsive and document quality is consistently reliable.",
		"avatars/3.jpg",
		3,
	),
]

CHECKOUT_BRANDS = [
	("Stripe", 1),
	("Visa", 2),
	("Mastercard", 3),
	("Amex", 4),
]


class Command(BaseCommand):
	help = "Seed landing page content for fully dynamic API response."

	def handle(self, *args, **options):
		LandingPageHero.objects.update_or_create(id=1, defaults=HERO_DEFAULTS)

		for title, description, order in FEATURES:
			LandingPageFeature.objects.update_or_create(
				title=title,
				defaults={"description": description, "order": order, "is_active": True},
			)

		for title, icon, order in BADGES:
			LandingPageBadge.objects.update_or_create(
				title=title,
				defaults={"icon": icon, "order": order, "is_active": True},
			)

		for plan_name, billing_period, price, downloads, tagline, is_popular, save_percent, order in PRICING:
			defaults = {
				"price": price,
				"downloads": downloads,
				"tagline": tagline,
				"features": PRICING_FEATURES[plan_name],
				"footer_text": PRICING_FOOTER,
				"is_popular": is_popular,
				"save_percent": save_percent,
				"order": order,
				"is_active": True,
			}
			matched_qs = LandingPagePricing.objects.filter(plan_name=plan_name, billing_period=billing_period).order_by("id")
			target_row = matched_qs.first()
			if target_row:
				for key, value in defaults.items():
					setattr(target_row, key, value)
				target_row.save()
				matched_qs.exclude(id=target_row.id).update(is_active=False)
			else:
				LandingPagePricing.objects.create(plan_name=plan_name, billing_period=billing_period, **defaults)

		for question, answer in FAQS:
			FAQ.objects.update_or_create(
				question=question,
				defaults={"answer": answer, "status": True},
			)

		for row in CMS_SECTIONS:
			CMS.objects.update_or_create(
				page="landing",
				section=row["section"],
				defaults={
					"title": row.get("title"),
					"sub_title": row.get("sub_title"),
					"description": row.get("description"),
					"short_description": row.get("short_description"),
					"background_image": row.get("background_image"),
					"file_url": row.get("file_url"),
					"video_link": row.get("video_link"),
					"button_text": row.get("button_text"),
					"button_link": row.get("button_link"),
					"other": row.get("other"),
					"status": "active",
				},
			)

		for title, image_path, order in PREVIEW_SAMPLES:
			LandingPreviewSample.objects.update_or_create(
				title=title,
				defaults={
					"image": image_path,
					"order": order,
					"is_active": True,
				},
			)

		for name, role, rating, comment, avatar_path, order in TESTIMONIALS:
			LandingTestimonial.objects.update_or_create(
				name=name,
				defaults={
					"role": role,
					"rating": rating,
					"comment": comment,
					"avatar": avatar_path,
					"order": order,
					"is_active": True,
				},
			)

		for name, order in CHECKOUT_BRANDS:
			LandingCheckoutBrand.objects.update_or_create(
				name=name,
				defaults={
					"order": order,
					"is_active": True,
				},
			)

		try:
			cache.delete_many(["landing_page_data", "landing_page_data_v8", "landing_page_data_v9", "landing_page_data_v10", "landing_page_data_v11", "landing_page_data_v12", "landing_page_data_v13"])
		except Exception:
			pass

		self.stdout.write(self.style.SUCCESS("Landing content seeded successfully."))
