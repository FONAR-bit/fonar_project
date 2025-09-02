from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied

class StaffRequiredMixin(UserPassesTestMixin):
    """Permite acceso solo a staff o superusuarios"""

    def test_func(self):
        return self.request.user.is_authenticated and (
            self.request.user.is_staff or self.request.user.is_superuser
        )

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            # Si no está autenticado -> lo manda al login admin
            from django.shortcuts import redirect
            return redirect("dashboard:admin-login")
        raise PermissionDenied("No tienes permisos para acceder a esta sección.")
