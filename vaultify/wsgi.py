"""
WSGI config for vaultify project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

import os
import django
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vaultify.settings')

# Setup Django
django.setup()

# Run migrations automatically
from django.core.management import call_command
try:
    call_command('migrate')
except Exception as e:
    print(f"Migration failed: {e}")

application = get_wsgi_application()
