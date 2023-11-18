from django.http import JsonResponse
from rest_framework import status


class PageErrorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code == 404:
            return JsonResponse(
                {"error": "Page not found."}, status=status.HTTP_404_NOT_FOUND
            )
        return response
