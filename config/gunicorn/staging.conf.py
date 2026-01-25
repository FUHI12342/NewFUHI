# Gunicorn configuration for NewFUHI staging environment
# Location: /var/www/newfuhi/gunicorn.conf.py

import multiprocessing
import os

# Server socket
bind = "127.0.0.1:8000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Restart workers after this many requests, with up to 100 random jitter
max_requests = 1000
max_requests_jitter = 100

# Restart workers after this many seconds
max_worker_age = 3600

# User and group
user = "newfuhi"
group = "newfuhi"

# Logging
logfile = "/var/log/newfuhi/gunicorn.log"
loglevel = "info"
access_logfile = "/var/log/newfuhi/gunicorn-access.log"
error_logfile = "/var/log/newfuhi/gunicorn-error.log"

# Log format
access_logformat = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "newfuhi-staging"

# Preload application
preload_app = True

# Graceful timeout
graceful_timeout = 30

# Temporary directory
tmp_upload_dir = None

# SSL (if needed in future)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"

# Environment variables
raw_env = [
    'DJANGO_ENVIRONMENT=staging',
]

# Hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    server.log.info("Starting NewFUHI staging server")

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    server.log.info("Reloading NewFUHI staging server")

def worker_int(worker):
    """Called just after a worker exited on SIGINT or SIGQUIT."""
    worker.log.info("Worker received INT or QUIT signal")

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def worker_abort(worker):
    """Called when a worker received the SIGABRT signal."""
    worker.log.info("Worker received SIGABRT signal")