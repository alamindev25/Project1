from apps.cms.models import FAQ, Page


def seed_page():
    about_us_content = """
<h2>About US</h2>
<p>Effective Date: February 20, 2026</p>
<p>Welcome to FORMEXL. We help professionals and teams generate high-quality business documents quickly and reliably.</p>

<h3>Who We Are</h3>
<p>FORMEXL is focused on simplifying document creation with clear templates, flexible customization, and fast export workflows.</p>

<h3>What We Build</h3>
<ul>
  <li>Ready-to-use business document templates</li>
  <li>Guided inputs for faster drafting</li>
  <li>Secure storage and retrieval of generated files</li>
  <li>Collaboration-friendly output for teams</li>
</ul>

<h3>Our Mission</h3>
<p>Our mission is to reduce document friction so users can focus on decisions, not formatting.</p>

<h3>How We Work</h3>
<p>We design for speed, clarity, and reliability. Product decisions are guided by user feedback, usability testing, and security best practices.</p>

<h3>Contact Us</h3>
<p>If you have questions about FORMEXL, contact: support@formexl.com</p>
"""

    privacy_policy_content = """
<h2>Privacy Policy</h2>
<p>Effective Date: February 20, 2026</p>

<h3>Personal Information We Collect</h3>
<p>When you visit our Site, we may automatically collect certain information about your device, including browser type, IP address, time zone, and some cookie data. We also collect information you provide directly, such as your name, email address, billing details, and any form data submitted through our services.</p>

<h3>How Do We Use Your Personal Information?</h3>
<p>We use your information to:</p>
<ul>
  <li>Provide, operate, and improve our services</li>
  <li>Process transactions and send service communications</li>
  <li>Detect and prevent fraud, abuse, or security incidents</li>
  <li>Respond to support requests and user inquiries</li>
</ul>

<h3>Sharing Your Personal Information</h3>
<p>We may share data with trusted service providers who support hosting, analytics, payments, and communication. We may also disclose information when required by law or to protect legal rights.</p>

<h3>Behavioural Advertising</h3>
<p>We may use limited data to show relevant promotions and measure campaign performance.</p>

<h3>Changes</h3>
<p>We may update this Privacy Policy from time to time to reflect legal, operational, or product changes.</p>

<h3>Contact Us</h3>
<p>For privacy questions, contact: support@formexl.com</p>
"""

    terms_and_conditions_content = """
<h2>Terms &amp; Conditions</h2>
<p>Effective Date: February 20, 2026</p>
<p>Welcome to FORMEXL. By accessing or using our services, you agree to these Terms and Conditions.</p>

<h3>Use of Service</h3>
<p>You agree to use the platform lawfully and responsibly. You must not misuse the service, attempt unauthorized access, or interfere with system integrity.</p>

<h3>Accounts and Access</h3>
<p>You are responsible for maintaining the confidentiality of your account credentials and for activities under your account.</p>

<h3>Content and Documents</h3>
<p>You are responsible for the legality and accuracy of content you submit. FORMEXL does not claim ownership of your original content.</p>

<h3>Payments and Billing</h3>
<p>Paid features, credits, or subscriptions are governed by the plan terms displayed at checkout.</p>

<h3>Service Availability</h3>
<p>We aim for reliable service but do not guarantee uninterrupted availability. Maintenance, updates, or third-party outages may affect access.</p>

<h3>Limitation of Liability</h3>
<p>To the fullest extent permitted by law, FORMEXL is not liable for indirect or consequential damages arising from service use.</p>

<h3>Changes to Terms</h3>
<p>We may update these terms from time to time. Continued use after updates means acceptance of the revised terms.</p>

<h3>Contact Us</h3>
<p>For terms-related questions, contact: support@formexl.com</p>
"""

    pages = [
    {
        "title": "About Us",
        "slug": "about-us",
        "content": about_us_content,
        "type": "about_us",
        "status": True
    },
    {
        "title": "Privacy Policy",
        "slug": "privacy-policy",
        "content": privacy_policy_content,
        "type": "privacy_policy",
        "status": True
    },
    {
        "title": "Terms and Conditions",
        "slug": "terms-and-conditions",
        "content": terms_and_conditions_content,
        "type": "terms_and_conditions",
        "status": True
    },
    {
        "title": "Cookie Policy",
        "slug": "cookie-policy",
        "content": "Our website uses cookies to enhance user experience. This policy explains what cookies we use and how you can manage them.",
        "type": "cookie_policy",
        "status": True
    },
    {
        "title": "Imprint",
        "slug": "imprint",
        "content": "This Imprint provides legal information about our company, including address, contact details, and responsible representatives.",
        "type": "imprint",
        "status": True
    }
]
    for page in pages:
        Page.objects.update_or_create(
            slug=page["slug"],
            defaults=page,
        )
    print("✅ Pages seeded successfully.")


def seed_faq():
    faqs = [
        {
            "question": "How can I create an account?",
            "answer": "You can create an account by clicking the 'Sign Up' button and filling out the registration form.",
            "status": True
        },
        {
            "question": "How do I reset my password?",
            "answer": "Click on 'Forgot Password' on the login page, then follow the instructions to reset your password.",
            "status": True
        },
        {
            "question": "Can I change my email address?",
            "answer": "Yes, you can update your email in your profile settings under 'Account Information'.",
            "status": True
        },
        {
            "question": "How do I contact support?",
            "answer": "You can reach our support team via the 'Contact Us' page or by emailing support@example.com.",
            "status": True
        },
        {
            "question": "Is my personal information safe?",
            "answer": "Yes, we use industry-standard security measures to protect your data.",
            "status": True
        }
    ]

    for faq in faqs:
        FAQ.objects.update_or_create(
            question=faq["question"],
            defaults=faq,
        )

    print("✅ FAQs seeded successfully.")