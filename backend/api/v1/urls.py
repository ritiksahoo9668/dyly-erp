from django.urls import include, path

from .views import health

urlpatterns = [
    path("health/", health, name="health"),
    path("auth/", include("apps.accounts.urls")),
    path("master/", include("apps.master.urls")),
    path("", include("apps.accounts.user_admin_urls")),
]
