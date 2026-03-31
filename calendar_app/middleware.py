from django.conf import settings


class AdminXFrameOptionsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if hasattr(request, 'path'):
            admin_path = f'/{settings.SECRET_PATH}/admin/' if settings.SECRET_PATH else '/admin/'
            if request.path.startswith(admin_path):
                response['X-Frame-Options'] = 'SAMEORIGIN'
        return response
