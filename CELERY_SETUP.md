# Celery Setup for Email Sending

## Overview

Celery has been configured to handle asynchronous email sending, significantly improving API response times from ~5 seconds to ~50-200ms.

## Prerequisites

### Install Redis (Message Broker)

**Windows:**

1. Download Redis from: https://github.com/microsoftarchive/redis/releases
2. Or use Docker: `docker run -d -p 6379:6379 redis:alpine`
3. Or use WSL: `sudo apt install redis-server && redis-server`

**Mac:**

```bash
brew install redis
brew services start redis
```

**Linux:**

```bash
sudo apt install redis-server
sudo systemctl start redis
```

## Running the Application

### Terminal 1: Start Redis (if not running as service)

```bash
redis-server
```

### Terminal 2: Start Django Development Server

```bash
py manage.py runserver 3000
```

### Terminal 3: Start Celery Worker

```bash
celery -A project worker --loglevel=info --pool=solo
```

**Note:** On Windows, use `--pool=solo` flag for Celery worker.

## Configuration

### Environment Variables (optional)

Add these to your `.env` file to customize:

```env
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0
```

## What Changed

### Files Modified:

1. **project/celery.py** - Celery app configuration
2. **project/**init**.py** - Auto-import Celery app
3. **project/settings.py** - Celery settings
4. **apps/utils/tasks.py** - Async email task
5. **apps/user/serializers.py** - Updated to use async email task

### Email Sending:

- **Before:** Synchronous `send_email()` - blocks for 5 seconds
- **After:** `send_email_task.delay()` - returns immediately, email sent in background

## Monitoring

### Check Celery Worker Status:

```bash
celery -A project inspect active
```

### View Task Results:

```bash
celery -A project inspect registered
```

### Flower (Web-based monitoring - optional):

```bash
pip install flower
celery -A project flower
```

Then visit: http://localhost:5555

## Troubleshooting

### Redis Connection Error:

- Ensure Redis is running: `redis-cli ping` (should return "PONG")
- Check Redis connection: `redis-cli`

### Celery Not Processing Tasks:

- Verify Celery worker is running
- Check for errors in Celery worker logs
- Ensure the task is properly imported

### Email Not Sending:

- Check Celery worker logs for errors
- Verify SMTP settings in settings.py
- Check email credentials

## Production Deployment

For production, consider:

1. Use Celery with systemd or supervisor
2. Use Redis with persistence enabled
3. Add monitoring (Flower, Sentry)
4. Configure retry policies
5. Use RabbitMQ for more complex scenarios

### Example Supervisor Config (Linux):

```ini
[program:celery-worker]
command=/path/to/venv/bin/celery -A project worker --loglevel=info
directory=/path/to/project
user=www-data
autostart=true
autorestart=true
```
