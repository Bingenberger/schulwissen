"""Separate process liveness and database/migration readiness."""
from django.db import connection, DatabaseError
from django.db.migrations.executor import MigrationExecutor
from django.http import JsonResponse


def live(request):
    return JsonResponse({"status": "alive"})


def ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        executor = MigrationExecutor(connection)
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            return JsonResponse({"status": "not-ready"}, status=503)
    except DatabaseError:
        return JsonResponse({"status": "not-ready"}, status=503)
    return JsonResponse({"status": "ready"})
