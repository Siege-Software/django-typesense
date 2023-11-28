import os
import sys

import django
from django.conf import settings
from django.test.utils import get_runner
from django.core.management import call_command

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")

django.setup()

call_command("updatecollections")

TestRunner = get_runner(settings)
test_runner = TestRunner()
failures = test_runner.run_tests(["tests"])

if failures:
    sys.exit(bool(failures))
