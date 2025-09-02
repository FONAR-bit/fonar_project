from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from dashboard.views.mixins import StaffRequiredMixin
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from dashboard.forms import TasaInteresForm
from fonar.models import TasaInteres


class TasaInteresListView(LoginRequiredMixin, StaffRequiredMixin, PermissionRequiredMixin, ListView):
    model = TasaInteres
    template_name = "dashboard/tasas/list.html"
    context_object_name = "tasas"
    permission_required = "fonar.view_tasainteres"
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset()
        tipo_usuario = self.request.GET.get("tipo_usuario")
        if tipo_usuario:
            qs = qs.filter(tipo_usuario=tipo_usuario)
        return qs.order_by("-vigente_desde")


class TasaInteresCreateView(LoginRequiredMixin, StaffRequiredMixin, PermissionRequiredMixin, CreateView):
    model = TasaInteres
    form_class = TasaInteresForm
    template_name = "dashboard/tasas/create.html"
    success_url = reverse_lazy("dashboard:tasas-list")
    permission_required = "fonar.add_tasainteres"


class TasaInteresUpdateView(LoginRequiredMixin, StaffRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = TasaInteres
    form_class = TasaInteresForm
    template_name = "dashboard/tasas/update.html"
    success_url = reverse_lazy("dashboard:tasas-list")
    permission_required = "fonar.change_tasainteres"


class TasaInteresDeleteView(LoginRequiredMixin, StaffRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = TasaInteres
    template_name = "dashboard/tasas/delete.html"
    success_url = reverse_lazy("dashboard:tasas-list")
    permission_required = "fonar.delete_tasainteres"
