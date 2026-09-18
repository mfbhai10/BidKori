"""
Celery application configuration for BidKori.

Autodiscovers tasks from all installed Django apps.
Celery Beat will handle scheduled auction state transitions (Phase 3).
"""
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bidkori_core.settings')

app = Celery('bidkori_core')

# Read config from Django settings, using the CELERY_ namespace.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks.py in every installed app.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Diagnostic task — prints its own request for troubleshooting."""
    print(f'Request: {self.request!r}')
