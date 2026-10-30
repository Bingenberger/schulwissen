"""Interne Vorschau der gemeinsamen Oberflächenkomponenten."""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from kern import rechte


@login_required
def styleguide(request):
    if not rechte.ist_administration(request.user):
        raise PermissionDenied
    return render(request, "kern/styleguide.html")
