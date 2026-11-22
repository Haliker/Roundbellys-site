from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

admin.site.site_header = "Roundbelly's office"
admin.site.site_title = "Roundbelly's office"
admin.site.index_title = "Website requests and bookings"

urlpatterns = [
    path("office/", admin.site.urls),
    # Old Wix addresses people may have bookmarked
    path("shop", RedirectView.as_view(url="/fundraising/", permanent=True)),
    path("shop/", RedirectView.as_view(url="/fundraising/", permanent=True)),
    path("wholesale-shop", RedirectView.as_view(url="/wholesale/", permanent=True)),
    path("", include("web.urls")),
]
