from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("api.v1.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif settings.SERVE_MATERIAL_MEDIA:
    # Only Material images are public; import source/error files stay unexposed.
    urlpatterns += [
        re_path(
            r"^media/(?P<path>materials/.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]
