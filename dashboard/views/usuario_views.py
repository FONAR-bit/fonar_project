from dashboard.views.mixins import StaffRequiredMixin
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from dashboard.forms import UsuarioCreateForm, UsuarioUpdateForm

Usuario = get_user_model()


class UsuarioListView(LoginRequiredMixin, StaffRequiredMixin, PermissionRequiredMixin, ListView):
    model = Usuario
    template_name = "dashboard/usuarios/list.html"
    context_object_name = "usuarios"
    permission_required = "auth.view_user"
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset()

        search = self.request.GET.get("q") or ""
        activo = self.request.GET.get("activo")
        staff = self.request.GET.get("staff")
        tipo_usuario = self.request.GET.get("tipo_usuario")

        if search.strip():
            qs = qs.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search)
            )

        if activo in {"1", "0"}:
            qs = qs.filter(is_active=(activo == "1"))

        if staff in {"1", "0"}:
            qs = qs.filter(is_staff=(staff == "1"))

        # 👇 Nuevo filtro por tipo_usuario
        if tipo_usuario in {"asociado", "tercero"}:
            qs = qs.filter(tipo_usuario=tipo_usuario)

        return qs.order_by("username")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        # para que la paginación conserve filtros/búsqueda
        params.pop("page", None)
        ctx["params"] = params.urlencode()
        return ctx


class UsuarioCreateView(LoginRequiredMixin, StaffRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Usuario
    form_class = UsuarioCreateForm
    template_name = "dashboard/usuarios/create.html"
    success_url = reverse_lazy("dashboard:usuarios-list")
    permission_required = "auth.add_user"


class UsuarioUpdateView(LoginRequiredMixin, StaffRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Usuario
    form_class = UsuarioUpdateForm
    template_name = "dashboard/usuarios/update.html"
    success_url = reverse_lazy("dashboard:usuarios-list")
    permission_required = "auth.change_user"


class UsuarioDeleteView(LoginRequiredMixin, StaffRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Usuario
    template_name = "dashboard/usuarios/delete.html"
    success_url = reverse_lazy("dashboard:usuarios-list")
    permission_required = "auth.delete_user"


class UsuarioPasswordChangeView(LoginRequiredMixin, StaffRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "auth.change_user"
    template_name = "dashboard/usuarios/password_change.html"

    def get(self, request, pk):
        usuario = get_object_or_404(Usuario, pk=pk)
        form = AdminPasswordChangeForm(user=usuario)
        return render(request, self.template_name, {"form": form, "object": usuario})

    def post(self, request, pk):
        usuario = get_object_or_404(Usuario, pk=pk)
        form = AdminPasswordChangeForm(user=usuario, data=request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Contraseña actualizada correctamente.")
            return redirect("dashboard:usuarios-update", pk=usuario.pk)
        return render(request, self.template_name, {"form": form, "object": usuario})
