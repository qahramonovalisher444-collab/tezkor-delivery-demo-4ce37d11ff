import os


bind = f"0.0.0.0:{int(os.getenv('PORT', '10000'))}"
workers = 2
threads = 2
timeout = 60
graceful_timeout = 30
accesslog = "-"
errorlog = "-"
# Render is the only ingress to this container and terminates HTTPS at its edge.
forwarded_allow_ips = "*"
