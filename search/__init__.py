__version__ = "0.0.1"

import environ
import django

from pathlib import Path

from django.conf import settings


env = environ.Env()

BASE_DIR = Path(__file__).resolve().parent.parent

ENV_FILE = BASE_DIR / '.env'

# reading .env file
environ.Env.read_env(ENV_FILE.__str__())

INSTALLED_APPS = ["search"]

TYPESENSE = {
    "nodes": [{"host": env('TYPESENSE_HOST'), "port": env('TYPESENSE_PORT'), "protocol": env('TYPESENSE_PROTOCOL')}],
    'api_key': env('TYPESENSE_API_KEY'),
    'connection_timeout_seconds': 2
}

settings.configure(INSTALLED_APPS=INSTALLED_APPS, TYPESENSE=TYPESENSE)

django.setup()
