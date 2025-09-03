from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('mis-aportes/', views.ver_aportes, name='ver_aportes'),
    path('mis-prestamos/', views.ver_prestamos, name='ver_prestamos'),
    path('subir-pago/', views.subir_pago, name='subir_pago'),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', views.custom_logout, name='logout'),  # 👈 ahora usa tu vista
    path('mis-pagos/', views.mis_pagos, name='mis_pagos'),
    path("cuotas/<int:prestamo_id>/", views.cuotas_pendientes, name="cuotas_pendientes"),
    path("pago/<int:pago_id>/pdf/", views.pago_pdf, name="pago_pdf"),
    path("solicitar-prestamo/", views.solicitar_prestamo, name="solicitar_prestamo"),
    path("obtener-tasa/", views.obtener_tasa, name="obtener_tasa"),
    path("mis-solicitudes/", views.mis_solicitudes, name="mis_solicitudes"),
]
