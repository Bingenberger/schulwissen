"""Der technische Verwaltungszugang vergibt keine zusätzlichen Inhaltsrechte."""

from kern import rechte


class AdministrationsMixin:
    """Zugangsregeln und rohe Verwaltungsdaten bleiben der Administration vorbehalten."""

    def has_module_permission(self, request):
        return rechte.ist_administration(request.user) and super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        return rechte.ist_administration(request.user) and super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        return rechte.ist_administration(request.user) and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return rechte.ist_administration(request.user) and super().has_change_permission(
            request, obj
        )

    def has_delete_permission(self, request, obj=None):
        return rechte.ist_administration(request.user) and super().has_delete_permission(
            request, obj
        )

    def get_queryset(self, request):
        menge = super().get_queryset(request)
        return menge if rechte.ist_administration(request.user) else menge.none()
