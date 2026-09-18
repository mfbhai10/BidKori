"""
WSGI config for BidKori project (fallback for non-ASGI deployments).
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bidkori_core.settings')

application = get_wsgi_application()
