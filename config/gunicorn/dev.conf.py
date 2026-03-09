# Gunicorn configuration for NewFUHI dev environment
# Location: /home/ubuntu/NewFUHI-dev/config/gunicorn/dev.conf.py

# Server socket
bind = "0.0.0.0:8001"
backlog = 2048

# Worker processes (lightweight for dev)
workers = 2
worker_class = "sync"
timeout = 120
keepalive = 2

# Logging
accesslog = "/var/log/newfuhi/dev-access.log"
errorlog = "/var/log/newfuhi/dev-error.log"
loglevel = "debug"

# Process naming
proc_name = "newfuhi-dev"

# Server mechanics
daemon = False
