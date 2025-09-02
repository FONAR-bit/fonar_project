from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from fonar import views
from django.shortcuts import render

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('fonar.urls')),  # vistas de socios
    path('accounts/login/', auth_views.LoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path("cuotas-pendientes/<int:prestamo_id>/", views.cuotas_pendientes, name="cuotas_pendientes"),
    path("dashboard/", include("dashboard.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# =========================
# Handlers de errores
# =========================
def custom_permission_denied_view(request, exception=None):
    return render(request, "403.html", status=403)

def custom_page_not_found_view(request, exception=None):
    return render(request, "404.html", status=404)

def custom_server_error_view(request):
    return render(request, "500.html", status=500)

handler403 = custom_permission_denied_view
handler404 = custom_page_not_found_view
handler500 = custom_server_error_view
