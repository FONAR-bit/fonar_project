from datetime import datetime
from decimal import Decimal
from django.views.generic import ListView
from django.db.models import Q
from fonar.models import PagoAplicacion

class OtrosAportesListView(ListView):
    template_name = "dashboard/otros-aportes/list.html"
    context_object_name = "items"
    paginate_by = 25

    TIPOS_VALIDOS = ("aporte_viaje", "admin_app", "actividad_recaudo")

    def get_queryset(self):
        qs = (PagoAplicacion.objects
              .select_related("pago", "pago__usuario")
              .filter(tipo__in=self.TIPOS_VALIDOS))

        usuario = self.request.GET.get("usuario", "").strip()
        if usuario:
            qs = qs.filter(
                Q(pago__usuario__username__icontains=usuario) |
                Q(pago__usuario__first_name__icontains=usuario) |
                Q(pago__usuario__last_name__icontains=usuario) |
                Q(pago__usuario__email__icontains=usuario)
            )

        tipo = self.request.GET.get("tipo", "").strip()
        if tipo in self.TIPOS_VALIDOS:
            qs = qs.filter(tipo=tipo)

        validado = self.request.GET.get("validado", "").strip()
        if validado in ("True", "False"):
            qs = qs.filter(pago__validado=(validado == "True"))

        anio = self.request.GET.get("anio", "").strip()
        if anio.isdigit():
            qs = qs.filter(pago__fecha__year=int(anio))

        ordenar = self.request.GET.get("ordenar", "").strip()
        allowed_orders = {"pago__fecha", "-pago__fecha", "monto_aplicado", "-monto_aplicado"}
        if ordenar in allowed_orders:
            qs = qs.order_by(ordenar)
        else:
            qs = qs.order_by("-pago__fecha", "-id")

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Lista simple de años para el filtro
        current_year = datetime.now().year
        ctx["years"] = list(range(current_year - 3, current_year + 1))
        return ctx
