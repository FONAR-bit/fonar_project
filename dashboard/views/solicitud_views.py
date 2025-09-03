from django.views.generic import ListView, UpdateView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from dashboard.views.mixins import StaffRequiredMixin
from fonar.models import SolicitudPrestamo, Prestamo
from decimal import Decimal, ROUND_HALF_UP


class SolicitudListView(LoginRequiredMixin, StaffRequiredMixin, ListView):
    model = SolicitudPrestamo
    template_name = "dashboard/solicitudes/list.html"
    context_object_name = "solicitudes"
    ordering = ["-fecha_solicitud"]

    def get_queryset(self):
        queryset = super().get_queryset()

        usuario = self.request.GET.get("usuario")
        estado = self.request.GET.get("estado")
        fecha_inicio = self.request.GET.get("fecha_inicio")
        fecha_fin = self.request.GET.get("fecha_fin")

        # 🔎 Filtro por usuario
        if usuario:
            queryset = queryset.filter(usuario__username__icontains=usuario)

        # 🔎 Filtro por estado
        if estado:
            queryset = queryset.filter(estado=estado)

        # 🔎 Rango de fechas
        if fecha_inicio:
            queryset = queryset.filter(fecha_solicitud__gte=fecha_inicio)
        if fecha_fin:
            queryset = queryset.filter(fecha_solicitud__lte=fecha_fin)

        return queryset


class SolicitudUpdateView(LoginRequiredMixin, StaffRequiredMixin, UpdateView):
    model = SolicitudPrestamo
    fields = ["estado"]  # 👈 Solo permitir cambiar estado
    template_name = "dashboard/solicitudes/update.html"
    success_url = reverse_lazy("dashboard:solicitudes-list")

    def calcular_cuota_fija(self, monto, interes, cuotas):
        interes_mensual = interes / Decimal('100')
        if interes_mensual == 0:
            return (monto / cuotas).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        cuota = monto * (interes_mensual * (1 + interes_mensual) ** cuotas) / (
            (1 + interes_mensual) ** cuotas - 1
        )
        return cuota.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def get_context_data(self, **kwargs):
        """Agrega la simulación de cuotas al contexto"""
        context = super().get_context_data(**kwargs)
        solicitud = self.object

        cuotas = []
        if solicitud.monto and solicitud.cuotas and solicitud.interes is not None:
            monto = Decimal(solicitud.monto)
            interes = Decimal(solicitud.interes)
            cuotas_totales = int(solicitud.cuotas)
            cuota_fija = self.calcular_cuota_fija(monto, interes, cuotas_totales)

            saldo = monto
            interes_mensual = interes / Decimal('100')

            for i in range(1, cuotas_totales + 1):
                interes_mes = (saldo * interes_mensual).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                abono_capital = (cuota_fija - interes_mes).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                saldo -= abono_capital
                saldo = saldo.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                cuotas.append({
                    "numero": i,
                    "capital": round(abono_capital, 0),
                    "interes": round(interes_mes, 0),
                    "cuota": round(cuota_fija, 0),
                    "saldo": round(max(saldo, 0), 0),
                })

            total_credito = monto
            total_intereses = sum(c["interes"] for c in cuotas)
            total_pagar = total_credito + Decimal(total_intereses)

            context["simulacion"] = cuotas
            context["total_credito"] = total_credito
            context["total_intereses"] = total_intereses
            context["total_pagar"] = total_pagar

        return context

    def form_valid(self, form):
        """Si se aprueba, crear préstamo automáticamente"""
        response = super().form_valid(form)
        solicitud = self.object

        if solicitud.estado == "aprobado":
            # Revisar si ya existe préstamo con esta solicitud
            prestamo_existente = Prestamo.objects.filter(
                usuario=solicitud.usuario,
                monto=solicitud.monto,
                cuotas=solicitud.cuotas,
                fecha_desembolso=solicitud.fecha_deseada_desembolso
            ).first()

            if not prestamo_existente:
                Prestamo.objects.create(
                    usuario=solicitud.usuario,
                    monto=solicitud.monto,
                    interes=solicitud.interes,
                    cuotas=solicitud.cuotas,
                    fecha_desembolso=solicitud.fecha_deseada_desembolso
                )
                # ⚡ Las cuotas se crean automáticamente en signals.py

        return response
