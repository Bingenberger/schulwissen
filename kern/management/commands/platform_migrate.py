"""Explicit migration job with a PostgreSQL advisory lock per database."""
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Apply migrations and roles exclusively; never run on web process startup."

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(hashtext(current_database()), 1729)")
            if not cursor.fetchone()[0]:
                raise CommandError("Another migration job holds the database lock.")
            try:
                call_command("migrate", interactive=False)
                call_command("rollen_einrichten")
            finally:
                cursor.execute("SELECT pg_advisory_unlock(hashtext(current_database()), 1729)")
