from zoneinfo import ZoneInfo

from django.utils import timezone


class TimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        timezone_name = request.COOKIES.get("timezone")
        if timezone_name:
            try:
                # Activate the timezone for this request
                timezone.activate(ZoneInfo(timezone_name))
            except Exception:
                # Fallback to the project's default timezone if the name is invalid
                timezone.deactivate()
        else:
            # No cookie, so use the project's default timezone
            timezone.deactivate()

        return self.get_response(request)
