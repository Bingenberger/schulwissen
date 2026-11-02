"""Honor forwarding metadata only from explicitly configured proxy addresses."""
import ipaddress
import os


class TrustedProxyHeaders:
    def __init__(self, get_response):
        self.get_response = get_response
        self.allowed = {str(ipaddress.ip_address(value.strip()))
                        for value in os.environ.get("SW_PROXY_IPS", "127.0.0.1,::1").split(",")
                        if value.strip()}

    def __call__(self, request):
        try:
            trusted = str(ipaddress.ip_address(request.META.get("REMOTE_ADDR", ""))) in self.allowed
        except ValueError:
            trusted = False
        if not trusted:
            for key in list(request.META):
                if key.startswith("HTTP_X_FORWARDED_") or key in (
                        "HTTP_FORWARDED", "HTTP_X_REAL_IP", "REMOTE_USER",
                        "HTTP_REMOTE_USER", "HTTP_X_AUTH_REQUEST_USER"):
                    request.META.pop(key, None)
        return self.get_response(request)
