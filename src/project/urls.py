from django.conf.urls import include, url
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.views import serve

urlpatterns = [
    url(r'^grappelli/', include('grappelli.urls')),
    url(r'^acra/', include('acra.urls')),
    url(r'^admin/', include(admin.site.urls)),

    url(r'', include('app.urls')),

]


if settings.DEBUG:
    urlpatterns = static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) + urlpatterns

    # This is my super hacky way to serve the favicon while running locally!
    from django.http import HttpResponse
    import os

    def favicon(request):
        image_data = open(os.path.join(settings.STATIC_ROOT,"favicon.ico"), "rb").read()
        return HttpResponse(image_data, content_type="image/png")

    urlpatterns.append(url(r'^favicon.*\.ico$', favicon))  # to serve the favicon in development


