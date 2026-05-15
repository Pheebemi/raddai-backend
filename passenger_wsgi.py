import sys
import os

# Add your project directory to the path
sys.path.insert(0, os.path.dirname(__file__))

os.environ['DJANGO_SETTINGS_MODULE'] = 'school_management.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
