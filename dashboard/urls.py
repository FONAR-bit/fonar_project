from django.urls import path
from dashboard.views.usuario_views import (
    UsuarioListView, UsuarioCreateView, UsuarioUpdateView, UsuarioDeleteView, UsuarioPasswordChangeView,
)
from dashboard.views.auth_views import AdminLoginView, AdminLogoutView
from dashboard.views.home_views import DashboardHomeView   # 👈 vista principal
from dashboard.views import pago_views   # 👈 agregamos esta importación
from dashboard.views import aporte_views
from dashboard.views import prestamo_views
from dashboard.views import tasa_views
from dashboard.views import solicitud_views
from dashboard.views.home_views import entregar_fondo_pdf

app_name = "dashboard"

urlpatterns = [
    # Página principal del dashboard
    path("", DashboardHomeView.as_view(), name="home"),

    # Rutas de autenticación admin
    path("login/", AdminLoginView.as_view(), name="admin-login"),
    path("logout/", AdminLogoutView.as_view(), name="admin-logout"),

    # Rutas de usuarios
    path("usuarios/", UsuarioListView.as_view(), name="usuarios-list"),
    path("usuarios/create/", UsuarioCreateView.as_view(), name="usuarios-create"),
    path("usuarios/<int:pk>/update/", UsuarioUpdateView.as_view(), name="usuarios-update"),
    path("usuarios/<int:pk>/delete/", UsuarioDeleteView.as_view(), name="usuarios-delete"),
    path("usuarios/<int:pk>/password/", UsuarioPasswordChangeView.as_view(), name="usuarios-password"),

    # Rutas de pagos
    path("pagos/", pago_views.PagoListView.as_view(), name="pagos-list"),
    path("pagos/create/", pago_views.PagoCreateView.as_view(), name="pagos-create"),
    path("pagos/<int:pk>/update/", pago_views.PagoUpdateView.as_view(), name="pagos-update"),
    path("pagos/<int:pk>/delete/", pago_views.PagoDeleteView.as_view(), name="pagos-delete"),
    path("pagos/<int:pk>/", pago_views.PagoDetailView.as_view(), name="pagos-detail"),

    # Rutas de aportes
    path('aportes/', aporte_views.aporte_list, name='aporte_list'),
    path('aportes/create/', aporte_views.aporte_create, name='aporte_create'),
    path('aportes/<int:pk>/edit/', aporte_views.aporte_update, name='aporte_update'),
    path('aportes/<int:pk>/delete/', aporte_views.aporte_delete, name='aporte_delete'),
    path('aportes/<int:pk>/', aporte_views.aporte_detail, name='aporte_detail'),

    # Rutas de prestamos
    path("prestamos/", prestamo_views.PrestamoListView.as_view(), name="prestamos-list"),
    path("prestamos/create/", prestamo_views.PrestamoCreateView.as_view(), name="prestamos-create"),
    path("prestamos/<int:pk>/", prestamo_views.PrestamoDetailView.as_view(), name="prestamos-detail"),
    path("prestamos/<int:pk>/update/", prestamo_views.PrestamoUpdateView.as_view(), name="prestamos-update"),
    path("prestamos/<int:pk>/delete/", prestamo_views.PrestamoDeleteView.as_view(), name="prestamos-delete"),

    # Rutas de tasas de interes
    path("tasas/", tasa_views.TasaInteresListView.as_view(), name="tasas-list"),
    path("tasas/create/", tasa_views.TasaInteresCreateView.as_view(), name="tasas-create"),
    path("tasas/<int:pk>/update/", tasa_views.TasaInteresUpdateView.as_view(), name="tasas-update"),
    path("tasas/<int:pk>/delete/", tasa_views.TasaInteresDeleteView.as_view(), name="tasas-delete"),

    # Rutas de Solicitudes creditos
    path("solicitudes/", solicitud_views.SolicitudListView.as_view(), name="solicitudes-list"),
    path("solicitudes/<int:pk>/update/", solicitud_views.SolicitudUpdateView.as_view(), name="solicitudes-update"),


    # Rutas de Entrega Fondo
    path("entregar-fondo/", entregar_fondo_pdf, name="entregar_fondo"),


]
