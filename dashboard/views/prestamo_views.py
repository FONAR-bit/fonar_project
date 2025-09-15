from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db import transaction
from fonar.models import Prestamo, CuotaPrestamo
from dashboard.forms import PrestamoForm

class PrestamoListView(ListView):
    model = Prestamo
    template_name = "dashboard/prestamos/list.html"
    context_object_name = "prestamos"
    paginate_by = 10

    def get_queryset(self):
        qs = Prestamo.objects.select_related("usuario").order_by("-fecha_desembolso")

        usuario = self.request.GET.get("usuario")
        fecha_inicio = self.request.GET.get("fecha_inicio")
        fecha_fin = self.request.GET.get("fecha_fin")
        monto_min = self.request.GET.get("monto_min")
        monto_max = self.request.GET.get("monto_max")
        estado = self.request.GET.get("estado")

        # 🔎 Filtro por usuario
        if usuario:
            qs = qs.filter(usuario__username__icontains=usuario)

        # 🔎 Filtro por rango de fechas
        if fecha_inicio:
            qs = qs.filter(fecha_desembolso__gte=fecha_inicio)
        if fecha_fin:
            qs = qs.filter(fecha_desembolso__lte=fecha_fin)

        # 🔎 Filtro por rango de montos
        if monto_min:
            qs = qs.filter(monto__gte=monto_min)
        if monto_max:
            qs = qs.filter(monto__lte=monto_max)

        # Filtrar por estado (vigentes o pagados)
        if estado == "vigentes":
            qs = qs.filter(capital_pendiente__gt=0)
        elif estado == "pagados":
            qs = qs.filter(capital_pendiente=0)

        return qs

class PrestamoDetailView(DetailView):
    model = Prestamo
    template_name = "dashboard/prestamos/detail.html"
    context_object_name = "prestamo"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cuotas"] = self.object.cuotaprestamo_set.all().order_by("numero")
        return context


class PrestamoCreateView(CreateView):
    model = Prestamo
    form_class = PrestamoForm
    template_name = "dashboard/prestamos/form.html"
    success_url = reverse_lazy("dashboard:prestamos-list")

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)  # el modelo se encarga de generar cuotas
            messages.success(self.request, "✅ Préstamo creado con sus cuotas.")
            return response

class PrestamoUpdateView(UpdateView):
    model = Prestamo
    form_class = PrestamoForm
    template_name = "dashboard/prestamos/form.html"
    success_url = reverse_lazy("dashboard:prestamos-list")

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
            messages.success(self.request, "✅ Préstamo actualizado.")
            return response


class PrestamoDeleteView(DeleteView):
    model = Prestamo
    template_name = "dashboard/prestamos/confirm_delete.html"
    success_url = reverse_lazy("dashboard:prestamos-list")

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "🗑️ Préstamo eliminado correctamente.")
        return super().delete(request, *args, **kwargs)
