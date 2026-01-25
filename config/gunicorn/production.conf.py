# Gunicorn configuration for NewFUHI production environment
# Location: /var/www/newfuhi/gunicorn.conf.py (symlink to this file)

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

# Restart workers after this many requests, to prevent memory leaks
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = "/var/log/newfuhi/gunicorn-access.log"
errorlog = "/var/log/newfuhi/gunicorn-error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "newfuhi-production"

# Server mechanics
daemon = False
pidfile = "/var/run/newfuhi/gunicorn.pid"
user = "newfuhi"
group = "newfuhi"
tmp_upload_dir = None

# SSL (if needed)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"

# Environment
raw_env = [
    "DJANGO_SETTINGS_MODULE=project.settings.production",
]

# Preload application for better performance
preload_app = True

# Worker process lifecycle
def on_starting(server):
    server.log.info("Starting NewFUHI production server")

def on_reload(server):
    server.log.info("Reloading NewFUHI production server")

def worker_int(worker):
    worker.log.info("Worker received INT or QUIT signal")

def pre_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_worker_init(worker):
    worker.log.info("Worker initialized (pid: %s)", worker.pid)

def worker_abort(worker):
    worker.log.info("Worker received SIGABRT signal")