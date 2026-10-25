from django.templatetags.static import static
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from apps.system_setting.admin_profile import update_profile


def get_about_system():
    from apps.system_setting.models import AboutSystem
    about_system = AboutSystem.objects.first()
    if about_system:
        return about_system

    # Fallback keeps admin login usable even before system settings are seeded.
    return AboutSystem(
        name="Application",
        title="Admin Panel",
        email="admin@example.com",
        copyright="",
        description="",
    )


def get_file_url(file_field, fallback_url):
    if not file_field:
        return fallback_url

    try:
        return file_field.url
    except Exception:
        return fallback_url

def get_unfold_settings():
    return {
        "SITE_TITLE": lambda request: get_about_system().title,
        "SITE_HEADER": lambda request: get_about_system().title,
        # "SITE_SUBHEADER": lambda request: get_about_system().title,
        "SITE_URL": "/",
        "SITE_ICON": {
            "light": lambda request: get_file_url(get_about_system().logo, "/favicon.ico"),  # light mode
            "dark": lambda request: get_file_url(get_about_system().logo, "/favicon.ico"),  # dark mode
        },
        "SITE_SYMBOL": "speed",  # symbol from icon set
        "SITE_FAVICONS": [
            {
            "rel": "icon",
            "sizes": "32x32",
            "type": "image/svg+xml",
            "href": lambda request: get_file_url(get_about_system().favicon, "/favicon.ico"),
            },
        ],
        "DASHBOARD_CALLBACK": "apps.dashboard.views.dashboard_callback",

        "SHOW_HISTORY": True,  # show/hide "History" button, default: True
        "SHOW_VIEW_ON_SITE": True,  # show/hide "View on site" button, default: True
        "SHOW_BACK_BUTTON": True,  # show/hide "Back" button on changeform in header, default: False
        "STYLES": [
            lambda request: static("css/unfold_custom.css"),
        ],
        # "THEME": "light",
        "LOGIN": {
            "image": lambda request: static("sample/login-bg.jpg"),
            "redirect_after": lambda request: reverse_lazy("admin:APP_MODEL_changelist"),
        },
        "BORDER_RADIUS": "6px",
        "SIDEBAR": {
            "show_search": True,  # Search in applications and models names
            "show_all_applications": True,  # Dropdown with all applications and models
            "navigation": [
                {
                    "items": [
                        {
                            "title": _("Dashboard"),
                            "icon": "dashboard",
                            "link": reverse_lazy("admin:index"),
                            "permission": lambda request: request.user.is_staff,
                        },
                    ],
                },
                {
                    "title": _("User Management"),
                    "separator": True,  # Top border
                    "collapsible": True,  # Collapsible group of links
                    "items": [
                        {
                            "title": _("Users"),
                            "icon": "people",
                            "link": reverse_lazy("admin:user_user_changelist"),
                        },
                        {
                            "title": _("User Profiles"),
                            "icon": "badge",
                            "link": reverse_lazy("admin:user_userprofile_changelist"),
                        },
                        {
                            "title": _("OTP"),
                            "icon": "password",
                            "link": reverse_lazy("admin:user_otp_changelist"),
                        },
                    ],
                },
                {
                    "title": _("Subscription Management"),
                    "separator": True,
                    "collapsible": True,
                    "items": [
                        {
                            "title": _("Packages"),
                            "icon": "inventory_2",
                            "link": reverse_lazy("admin:subscription_subscriptionpackage_changelist"),
                        },
                        {
                            "title": _("Subscriptions"),
                            "icon": "workspace_premium",
                            "link": reverse_lazy("admin:subscription_subscription_changelist"),
                        },
                        {
                            "title": _("Payment Histories"),
                            "icon": "payments",
                            "link": reverse_lazy("admin:subscription_paymenthistory_changelist"),
                        },
                    ],
                },
                {
                    "title": _("Document Management"),
                    "separator": True,
                    "collapsible": True,
                    "items": [
                        {
                            "title": _("Template Categories"),
                            "icon": "category",
                            "link": reverse_lazy("admin:dashboard_templatecategory_changelist"),
                        },
                        {
                            "title": _("Document Types"),
                            "icon": "description",
                            "link": reverse_lazy("admin:dashboard_documenttype_changelist"),
                        },
                        {
                            "title": _("Document Templates"),
                            "icon": "article",
                            "link": reverse_lazy("admin:dashboard_documenttemplate_changelist"),
                        },
                        {
                            "title": _("Document Structures"),
                            "icon": "account_tree",
                            "link": reverse_lazy("admin:dashboard_documentstructure_changelist"),
                        },
                        {
                            "title": _("Document Schemas"),
                            "icon": "schema",
                            "link": reverse_lazy("admin:dashboard_documentschema_changelist"),
                        },
                        {
                            "title": _("Generated Documents"),
                            "icon": "file_copy",
                            "link": reverse_lazy("admin:dashboard_generateddocument_changelist"),
                        },
                        {
                            "title": _("Document Requests"),
                            "icon": "request_page",
                            "link": reverse_lazy("admin:dashboard_documentrequest_changelist"),
                        },
                        {
                            "title": _("Help Articles"),
                            "icon": "help_center",
                            "link": reverse_lazy("admin:dashboard_helparticle_changelist"),
                        },
                        {
                            "title": _("Payment Methods"),
                            "icon": "credit_card",
                            "link": reverse_lazy("admin:dashboard_paymentmethod_changelist"),
                        },
                        {
                            "title": _("Company Branding"),
                            "icon": "branding_watermark",
                            "link": reverse_lazy("admin:dashboard_companybranding_changelist"),
                        },

                    ],
                },
                {
                    "title": _("Notification Management"),
                    "separator": True,
                    "collapsible": True,
                    "items": [
                        {
                            "title": _("Notifications"),
                            "icon": "notifications",
                            "link": reverse_lazy("admin:notification_notification_changelist"),
                        },
                        {
                            "title": _("Device Tokens"),
                            "icon": "devices",
                            "link": reverse_lazy("admin:notification_devicetoken_changelist"),
                        },
                    ],
                },
                {
                    "title": _("System Setting"),
                    "separator": True,
                    "collapsible": True,
                    "items": [
                        {
                            "title": _("Update Profile"),
                            "icon": "edit",
                            "link": lambda req: update_profile(req),
                        },
                        {
                            "title": _("About System"),
                            "icon": "info",
                            "link": reverse_lazy(
                                "admin:system_setting_aboutsystem_changelist"
                            ),
                        },
                        {
                            "title": _("Social Media"),
                            "icon": "share",
                            "link": reverse_lazy(
                                "admin:system_setting_socialmedia_changelist"
                            ),
                        },
                        {
                            "title": _("SMTP Settings"),
                            "icon": "email",
                            "link": reverse_lazy(
                                "admin:system_setting_smtpsetting_changelist"
                            ),
                        },
                        {
                            "title": _("System Color"),
                            "icon": "palette",
                            "link": reverse_lazy(
                                "admin:system_setting_systemcolor_changelist"
                            ),
                        },
                        {
                            "title": _("Dynamic Pages"),
                            "icon": "web",
                            "link": reverse_lazy(
                                "admin:system_setting_dynamicpages_changelist"
                            ),
                        },
                        {
                            "title": _("Dashboard Settings"),
                            "icon": "tune",
                            "link": reverse_lazy(
                                "admin:system_setting_dashboardsettings_changelist"
                            ),
                        },
                        {
                            "title": _("Landing Hero"),
                            "icon": "view_compact",
                            "link": reverse_lazy(
                                "admin:system_setting_landingpagehero_changelist"
                            ),
                        },
                        {
                            "title": _("Landing Pricing"),
                            "icon": "sell",
                            "link": reverse_lazy(
                                "admin:system_setting_landingpagepricing_changelist"
                            ),
                        },
                        {
                            "title": _("Landing Features"),
                            "icon": "star",
                            "link": reverse_lazy(
                                "admin:system_setting_landingpagefeature_changelist"
                            ),
                        },
                        {
                            "title": _("Landing Badges"),
                            "icon": "military_tech",
                            "link": reverse_lazy(
                                "admin:system_setting_landingpagebadge_changelist"
                            ),
                        },
                        {
                            "title": _("Landing Sections"),
                            "icon": "view_module",
                            "link": reverse_lazy(
                                "admin:system_setting_landingpagesection_changelist"
                            ),
                        }
                    ],
                },
                {
                    "title": _("Content Management"),
                    "separator": True,
                    "collapsible": True,
                    "items": [
                        {
                            "title": _("Pages"),
                            "icon": "pages",
                            "link": reverse_lazy("admin:cms_page_changelist"),
                        },
                    ],
                },
                {
                    "title": _("CMS Management"),
                    "separator": True,
                    "collapsible": True,
                    "items": [
                        {
                            "title": _("CMS"),
                            "icon": "auto_stories",
                            "link": reverse_lazy("admin:cms_cms_changelist"),
                        },
                        {
                            "title": _("CMS Points"),
                            "icon": "auto_stories",
                            "link": reverse_lazy("admin:cms_cmspoint_changelist"),
                        },
                    ],
                },
                {
                    "title": _("FAQ Management"),
                    "separator": True,
                    "collapsible": True,
                    "items": [
                        {
                            "title": _("FAQs"),
                            "icon": "help",
                            "link": reverse_lazy("admin:cms_faq_changelist"),
                        },
                        {
                            "title": _("Contact Requests"),
                            "icon": "contact_mail",
                            "link": reverse_lazy("admin:system_setting_contactus_changelist"),
                        },
                    ],
                }
            ],
        },
    }
