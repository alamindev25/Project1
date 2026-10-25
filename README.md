# Django Project Documentation

## Project Overview

This is a comprehensive Django REST Framework-based project with multiple modules for managing users, documents, subscriptions, notifications, CMS content, and more. The project is designed to serve as a backend for a document management and generation platform.

---

## Technology Stack

### Core Framework
- **Django 5.2.5** - Web framework
- **Django REST Framework 3.16.1** - API development
- **Python 3.x** - Programming language

### Authentication & Authorization
- **djangorestframework_simplejwt 5.5.1** - JWT token authentication
- **Firebase Admin 7.1.0** - Firebase authentication integration
- Custom authentication backends

### Database & Caching
- **SQLite** (default) - Database
- **Redis** - Caching and session management (configured in REDIS_CACHING.md)

### Async Task Processing
- **Celery 5.6.2** - Distributed task queue
- **Redis** - Celery broker and result backend (configured in CELERY_SETUP.md)
- **kombu 5.6.2** - Celery messaging library

### Media Management
- **Cloudinary 1.44.1** - Cloud-based media storage
- **Google Cloud Storage 3.8.0** - Additional cloud storage support
- **Firebase Cloud Storage** - Document and media management

### Admin & UI
- **django-unfold 0.64.2** - Modern Django admin interface
- **django-import-export 4.3.9** - Data import/export functionality
- **django-nested-admin 4.1.4** - Nested admin support

### Development & Debugging
- **django-debug-toolbar 6.0.0** - Development debugging
- **django-querycount 0.8.3** - Query performance monitoring
- **django-cors-headers 4.7.0** - CORS headers support

### Security & API
- **cryptography 46.0.3** - Encryption support
- **httpx 0.28.1** - HTTP client library
- **gunicorn 23.0.0** - Production WSGI server

---

## Project Structure

```
samyyttt_django/
├── apps/                          # Django applications
│   ├── cms/                       # Content Management System
│   │   ├── models.py             # CMS, FAQ, CMSPoint models
│   │   ├── views.py              # CMS API endpoints
│   │   ├── serializers.py        # Data serialization
│   │   ├── urls.py               # URL routing
│   │   └── migrations/           # Database migrations
│   │
│   ├── dashboard/                 # Dashboard & Document Management
│   │   ├── models.py             # Dashboard data models
│   │   ├── views.py              # Dashboard API endpoints
│   │   ├── pdf_service.py        # PDF generation service
│   │   ├── signals.py            # Django signals for events
│   │   ├── seed_data.py          # Sample data seeding
│   │   ├── management/           # Custom management commands
│   │   └── migrations/           # Database migrations
│   │
│   ├── notification/              # Notification System
│   │   ├── models.py             # Notification models
│   │   ├── views.py              # Notification API endpoints
│   │   ├── serializers.py        # Data serialization
│   │   ├── utils/                # Notification utilities
│   │   └── migrations/           # Database migrations
│   │
│   ├── social_auth/               # Social Authentication
│   │   ├── models.py             # Social auth models
│   │   ├── views.py              # Social login endpoints
│   │   ├── serializers.py        # Data serialization
│   │   └── migrations/           # Database migrations
│   │
│   ├── subscription/              # Subscription & Billing
│   │   ├── models.py             # Subscription, PaymentHistory models
│   │   ├── views.py              # Subscription API endpoints
│   │   ├── signals.py            # Subscription-related signals
│   │   ├── seed_data.py          # Sample subscription data
│   │   └── migrations/           # Database migrations
│   │
│   ├── system_setting/            # System Configuration
│   │   ├── models.py             # System settings, branding models
│   │   ├── admin.py              # Admin configuration
│   │   ├── admin_profile.py      # Custom admin profile
│   │   ├── views.py              # Settings API endpoints
│   │   ├── seed_data.py          # Default settings data
│   │   ├── management/           # Custom management commands
│   │   └── migrations/           # Database migrations
│   │
│   ├── user/                      # User Management
│   │   ├── models.py             # User model with roles (Admin, User)
│   │   ├── views.py              # User API endpoints
│   │   ├── authentication.py     # Custom authentication logic
│   │   ├── backends.py           # Authentication backends
│   │   ├── managers.py           # Custom user manager
│   │   ├── middleware.py         # Custom middleware
│   │   ├── utils.py              # User utilities
│   │   ├── seed_users.py         # Sample user data
│   │   ├── tests_*.py            # Unit tests
│   │   └── migrations/           # Database migrations
│   │
│   ├── utils/                     # Project-wide Utilities
│   │   ├── custom_exception.py   # Custom exception classes
│   │   ├── helpers.py            # Helper functions
│   │   └── tasks.py              # Celery async tasks
│   │
│   └── seeders/                   # Data Seeding
│       └── management/           # Seeding management commands
│
├── billing/                       # Billing System
│   ├── models.py                 # Billing models
│   ├── views.py                  # Billing API endpoints
│   ├── admin.py                  # Admin configuration
│   └── migrations/               # Database migrations
│
├── project/                       # Project Configuration
│   ├── settings.py               # Django settings
│   ├── urls.py                   # URL routing
│   ├── wsgi.py                   # WSGI configuration
│   ├── asgi.py                   # ASGI configuration (Celery)
│   ├── celery.py                 # Celery configuration
│   ├── firebase.py               # Firebase configuration
│   └── unfold_config.py          # Admin UI configuration
│
├── media/                         # User-uploaded media
│   ├── avatars/                  # User profile pictures
│   ├── cms/                      # CMS media files
│   ├── company_branding/         # Company branding assets
│   ├── generated_documents/      # Generated PDFs and documents
│   └── system_setting/           # System setting assets
│
├── static/                        # Static files
│   └── admin/                    # Admin static files
│
├── templates/                     # HTML templates
│   ├── admin/                    # Admin templates
│   └── email/                    # Email templates
│
├── manage.py                      # Django management script
├── requirements.txt               # Python dependencies
├── db.sqlite3                     # SQLite database
├── CELERY_SETUP.md                # Celery configuration guide
├── REDIS_CACHING.md               # Redis caching setup guide
└── README.md                      # This file
```

---

## Key Features & Components

### 1. **User Management** (`apps/user/`)
- Custom User model with role-based access (Admin, User)
- JWT-based authentication
- Firebase authentication integration
- Avatar management with Cloudinary
- OTP verification for security
- Custom authentication backends

### 2. **Dashboard** (`apps/dashboard/`)
- Document management interface
- PDF generation service for document creation
- Dashboard statistics and insights
- User-specific dashboard customization
- Related settings in system_setting

### 3. **Subscription System** (`apps/subscription/`)
- Subscription package management
- Payment history tracking
- Billing integration
- Subscription lifecycle management
- Signal-based event handling

### 4. **Content Management** (`apps/cms/`)
- CMS pages management
- FAQ management
- CMS points/sections
- Dynamic content management
- Landing page content

### 5. **Notification System** (`apps/notification/`)
- Real-time notifications
- Email notifications
- Notification preferences
- Notification utilities for event-based triggers
- Firebase integration for push notifications

### 6. **Social Authentication** (`apps/social_auth/`)
- Social login integration
- Multiple provider support (Google, Facebook, etc.)
- Social account linking

### 7. **System Settings** (`apps/system_setting/`)
- Global system configuration
- Landing page branding and customization
- Landing page sections (Hero, Features, Pricing, etc.)
- Company branding management
- Badge management for achievements

### 8. **Billing Module** (`billing/`)
- Billing operations
- Invoice management
- Payment processing

### 9. **Async Tasks** (`apps/utils/tasks.py`)
- Celery-based background tasks
- Email sending
- PDF generation
- Report generation
- Scheduled tasks

---

## Setup & Installation

### Prerequisites
- Python 3.8+
- Redis server
- PostgreSQL (optional, currently uses SQLite)

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd samyyttt_django
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   - Copy `.env.example` to `.env` (if available)
   - Set up Django SECRET_KEY, DEBUG, and other settings
   - Configure Firebase credentials
   - Set up Cloudinary API keys
   - Configure Redis connection

5. **Run migrations**
   ```bash
   python manage.py migrate
   ```

6. **Create superuser**
   ```bash
   python manage.py createsuperuser
   ```

7. **Load seed data (optional)**
   ```bash
   python manage.py seed_data  # For system settings
   python manage.py seed_users  # For sample users
   ```

8. **Start development server**
   ```bash
   python manage.py runserver
   ```

### Running Celery (for async tasks)
See `CELERY_SETUP.md` for detailed Celery configuration.

```bash
celery -A project worker -l info
```

### Redis Setup
See `REDIS_CACHING.md` for Redis caching configuration.

---

## API Endpoints Overview

### User APIs (`/api/user/`)
- `POST /register/` - User registration
- `POST /login/` - User login
- `POST /logout/` - User logout
- `GET/PUT /profile/` - User profile management
- `POST /resend-otp/` - Resend OTP
- `POST /avatar/` - Update avatar

### Dashboard APIs (`/api/dashboard/`)
- `GET /` - Dashboard overview
- `GET /documents/` - List documents
- `POST /documents/` - Create document
- `GET /documents/<id>/` - Document details
- `POST /generate-pdf/` - Generate PDF

### Subscription APIs (`/api/subscription/`)
- `GET /packages/` - List subscription packages
- `POST /subscribe/` - Subscribe to package
- `GET /history/` - Payment history

### CMS APIs (`/api/cms/`)
- `GET /pages/` - List CMS pages
- `GET /faq/` - Get FAQs
- `GET /settings/` - System settings

### Notification APIs (`/api/notification/`)
- `GET /` - List notifications
- `POST /mark-read/` - Mark notification as read

### System Settings APIs (`/api/system-setting/`)
- `GET /landing/` - Landing page data
- `GET /branding/` - Company branding

---

## Authentication

The project uses **JWT (JSON Web Tokens)** for API authentication.

1. **Obtain Token**
   ```
   POST /api/token/
   Body: {"email": "user@example.com", "password": "password"}
   ```

2. **Use Token**
   ```
   Authorization: Bearer <token>
   ```

3. **Firebase Authentication** - Also supported for mobile/social logins

---

## Admin Interface

Access the modern admin interface at `/admin/` (powered by django-unfold):
- User management
- Subscription management
- Content management
- System settings configuration
- Billing information

---

## Testing

Run tests for specific apps:

```bash
# User authentication tests
python manage.py test apps.user.tests_signin
python manage.py test apps.user.tests_resend_otp
python manage.py test apps.user.tests_avatar_update

# General tests
python manage.py test
```

---

## Important Configuration Files

- **`project/settings.py`** - Main Django settings
- **`project/celery.py`** - Celery configuration
- **`project/firebase.py`** - Firebase setup
- **`project/unfold_config.py`** - Admin UI customization
- **`CELERY_SETUP.md`** - Celery task queue setup guide
- **`REDIS_CACHING.md`** - Redis caching setup guide

---

## Signals & Event Handlers

The project uses Django signals for event-driven operations:
- **User creation events** - Notification on new user signup
- **Subscription events** - Triggered on subscription changes
- **Document events** - Triggered on document creation/update
- **Payment events** - Triggered on successful payment

See `apps/dashboard/signals.py` and `apps/subscription/signals.py` for details.

---

## Media Management

- **Cloudinary** - Primary media storage (avatars, CMS images)
- **Google Cloud Storage** - Secondary storage option
- **Local Media** - `/media/` directory for local storage during development

Media folders:
- `/media/avatars/` - User profile pictures
- `/media/cms/` - CMS content media
- `/media/generated_documents/` - Generated PDFs
- `/media/company_branding/` - Company logos and assets

---

## Dependencies Overview

- **API Framework**: Django REST Framework
- **Authentication**: SimpleJWT, Firebase
- **Task Queue**: Celery with Redis
- **Media Storage**: Cloudinary, Google Cloud
- **Admin Interface**: django-unfold
- **Data Validation**: djangorestframework validators
- **Security**: cryptography, defusedxml
- **HTTP**: httpx for API calls

---

## Deployment Considerations

- Use **Gunicorn** as production WSGI server
- Configure **Nginx** as reverse proxy
- Set `DEBUG = False` in production
- Use environment variables for sensitive data
- Configure proper ALLOWED_HOSTS
- Set up HTTPS/SSL certificates
- Use production database (PostgreSQL recommended)
- Configure Redis for caching and Celery
- Monitor Celery workers
- Set up logging and error tracking

---

## Common Management Commands

```bash
# Database operations
python manage.py migrate              # Run migrations
python manage.py makemigrations      # Create new migrations

# Seeding data
python manage.py seed_data           # Load system settings
python manage.py seed_users          # Load sample users

# Admin
python manage.py createsuperuser     # Create admin user
python manage.py changepassword      # Change user password

# Utilities
python manage.py shell               # Interactive shell
python manage.py collectstatic       # Collect static files
```

---

## Troubleshooting

### Database Issues
- Run `python manage.py migrate` to sync database
- Check `db.sqlite3` permissions

### Celery Not Working
- Ensure Redis is running
- Check Celery worker logs: `celery -A project worker -l info`
- See `CELERY_SETUP.md`

### Media Upload Issues
- Verify Cloudinary credentials
- Check `/media/` directory permissions
- Review `settings.py` for media configurations

### Authentication Failures
- Verify JWT_SECRET is configured
- Check Firebase credentials
- Review user roles and permissions

---

## Contributing

1. Create a feature branch
2. Make changes to relevant app
3. Write/update tests
4. Update migrations if models change
5. Submit pull request

---

## Support

For issues, configuration help, or feature requests, refer to:
- `CELERY_SETUP.md` - Async task configuration
- `REDIS_CACHING.md` - Caching setup
- Django documentation: https://docs.djangoproject.com/
- DRF documentation: https://www.django-rest-framework.org/

---

**Last Updated**: May 2026
**Django Version**: 5.2.5
**Python Version**: 3.8+
