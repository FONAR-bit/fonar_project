from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy
from dashboard.forms import AdminLoginForm   # 👈 importamos el form con estilos

class AdminLoginView(LoginView):
    template_name = "dashboard/auth/login.html"
    authentication_form = AdminLoginForm      # 👈 usamos el form personalizado
    redirect_authenticated_user = True

    def get_success_url(self):
        # Validamos que solo staff o superuser puedan entrar
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            raise PermissionDenied("No tienes permisos para acceder al dashboard.")
        return reverse_lazy("dashboard:home")


class AdminLogoutView(LogoutView):
    next_page = reverse_lazy("dashboard:home")
