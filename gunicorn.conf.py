# Gunicorn configuration file optimized for cloud deployment (Render)
import os

# Server socket
# Render automatically injects the PORT environment variable (default: 10000)
port = os.environ.get('PORT', '10000')
bind = f"0.0.0.0:{port}"

# Worker processes:
# On Render free tier (512MB RAM), multiple worker processes duplicate memory and trigger OOM.
# Using 1 worker with threads (gthread) handles concurrent requests within ~60MB RAM.
workers = int(os.environ.get('WEB_CONCURRENCY', 1))
threads = int(os.environ.get('GUNICORN_THREADS', 4))
worker_class = 'gthread'

# Timeouts
timeout = 120
graceful_timeout = 30
keepalive = 5

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Process naming
proc_name = 'otakudescriptor'
daemon = False

# Avoid preloading in low memory environments so port binds immediately
preload_app = False
