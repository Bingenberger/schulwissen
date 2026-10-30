from django.apps import AppConfig


class KernConfig(AppConfig):
    name = "kern"
    verbose_name = "Kern"

    def ready(self):
        from kern import dokumenttypen  # noqa: F401
