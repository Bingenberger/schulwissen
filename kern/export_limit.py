"""One PDF request per container, shared across workers through flock."""
import fcntl
import os
from functools import wraps
from django.http import HttpResponse


def limited_pdf(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if kwargs.get("format") not in (None, "pdf"):
            return view(request, *args, **kwargs)
        descriptor = os.open("/tmp/schulwissen-pdf.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                response = HttpResponse("PDF-Erzeugung ausgelastet. Bitte erneut versuchen.", status=503)
                response["Retry-After"] = "5"
                return response
            return view(request, *args, **kwargs)
        finally:
            os.close(descriptor)
    return wrapped
