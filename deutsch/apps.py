from django.apps import AppConfig


class DeutschConfig(AppConfig):
    name = "deutsch"
    verbose_name = "Arbeitsplan Deutsch"

    def ready(self) -> None:
        # Registriert die Eintragstypen „grundlagenkapitel", „ritual" und
        # „vorhaben" in der zentralen Registry.
        from deutsch import eintragstypen  # noqa: F401
