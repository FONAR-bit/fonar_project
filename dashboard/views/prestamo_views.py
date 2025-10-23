from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db import transaction
from django.core.paginator import Paginator
from fonar.models import Prestamo, CuotaPrestamo
from dashboard.forms import PrestamoForm


class PrestamoListView(ListView):
    model = Prestamo
    template_name = "dashboard/prestamos/list.html"
    context_object_name = "prestamos"
    paginate_by = 10  # seguirá aplicando para la paginación clásica (por préstamos)

    def get_queryset(self):
        """
        Filtros originales (usuario, fechas, montos) + soporte opcional de 'estado'.
        Este queryset queda disponible como 'prestamos' y también sirve de base para el agrupado.
        """
        qs = Prestamo.objects.select_related("usuario").order_by("-fecha_desembolso")

        usuario = self.request.GET.get("usuario")
        fecha_inicio = self.request.GET.get("fecha_inicio")
        fecha_fin = self.request.GET.get("fecha_fin")
        monto_min = self.request.GET.get("monto_min")
        monto_max = self.request.GET.get("monto_max")
        estado = self.request.GET.get("estado")  # 'vigentes' | 'pagados' (opcional)

        if usuario:
            qs = qs.filter(usuario__username__icontains=usuario)

        if fecha_inicio:
            qs = qs.filter(fecha_desembolso__gte=fecha_inicio)
        if fecha_fin:
            qs = qs.filter(fecha_desembolso__lte=fecha_fin)

        if monto_min:
            qs = qs.filter(monto__gte=monto_min)
        if monto_max:
            qs = qs.filter(monto__lte=monto_max)

        # Si usan el filtro de estado clásico, lo aplicamos al queryset base
        if estado == "vigentes":
            qs = qs.filter(capital_pendiente__gt=0)
        elif estado == "pagados":
            qs = qs.filter(capital_pendiente=0)

        return qs

    def get_context_data(self, **kwargs):
        """
        Además del contexto clásico (page_obj/paginator/prestamos),
        añadimos un contexto paralelo para 'agrupado por usuario':
          - users_page: página de grupos (usuarios)
          - paginator_users / is_paginated_users
          - historico: bool que indica si se muestran también préstamos con saldo 0
        """
        context = super().get_context_data(**kwargs)

        # --- Modo agrupado por usuario ---
        historico = self.request.GET.get("historico") == "1"

        # Base ya filtrada por el get_queryset (respeta usuario/fechas/montos y quizá 'estado')
        base_qs = context["prestamos"]

        # Para mostrar: si NO es histórico, ocultamos los saldos 0
        if historico:
            qs_display = base_qs
        else:
            qs_display = base_qs.filter(capital_pendiente__gt=0)

        # Contador de pendientes reales por usuario (independiente del 'historico')
        pendientes_por_usuario = {}
        for p in base_qs:
            if (p.capital_pendiente or 0) > 0:
                pendientes_por_usuario[p.usuario_id] = pendientes_por_usuario.get(p.usuario_id, 0) + 1

        # Construir grupos por usuario a partir de lo que se va a mostrar (qs_display)
        grupos = {}  # user_id -> {"usuario": obj_user, "prestamos": [...], "saldo_total": Decimal, "pendientes_count": int}
        for p in qs_display.select_related("usuario"):
            d = grupos.get(p.usuario_id)
            if not d:
                d = {
                    "usuario": p.usuario,
                    "prestamos": [],
                    "saldo_total": 0,
                    "pendientes_count": pendientes_por_usuario.get(p.usuario_id, 0),
                }
                grupos[p.usuario_id] = d
            d["prestamos"].append(p)
            d["saldo_total"] += p.capital_pendiente or 0

        # Ordenar por nombre de usuario (puedes cambiar a saldo_total descendente si te interesa)
        items = list(grupos.values())
        items.sort(key=lambda x: (x["usuario"].username or "").lower())

        # Paginación por usuario (independiente de la paginación clásica por préstamos)
        page_number = self.request.GET.get("page")
        paginator_users = Paginator(items, self.paginate_by)
        users_page = paginator_users.get_page(page_number)

        context["users_page"] = users_page
        context["paginator_users"] = paginator_users
        context["is_paginated_users"] = paginator_users.num_pages > 1
        context["historico"] = historico

        # Para no romper plantillas antiguas que esperaban 'prestamos_filtrados_estado'
        # (ya no aplicamos ese filtrado “por página” aquí, porque el agrupado lo vuelve innecesario)
        context["prestamos_filtrados_estado"] = None

        return context


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
            response = super().form_valid(form)
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
