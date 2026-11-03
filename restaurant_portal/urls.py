"""
Main URL routing for the Restaurant Portal project.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),

    # Authentication (Djoser + JWT)
    path("api/v1/auth/", include("djoser.urls")),
    path("api/v1/auth/", include("djoser.urls.jwt")),

    # Application APIs
    path("api/v1/users/", include("apps.users.urls")),
    path("api/v1/restaurants/", include("apps.restaurants.urls")),
    path("api/v1/menu/", include("apps.menu.urls")),
    path("api/v1/orders/", include("apps.orders.urls")),
    path("api/v1/payments/", include("apps.payments.urls")),
    path("api/v1/kitchen/", include("apps.kitchen.urls")),
    path("api/v1/delivery/", include("apps.delivery.urls")),
    path("api/v1/support/", include("apps.support.urls")),
    path("api/v1/analytics/", include("apps.analytics.urls")),

    path("api/v1/reviews/", include("apps.reviews.urls")),

    # Common URLs (Super Admin Dashboard & Health Check) - INCLUDED UNDER api/v1/
    path("api/v1/", include("apps.common.urls")),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

    # Debug Toolbar
    import debug_toolbar
    urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]