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
    paginate_by = 10  # paginación clásica (por préstamos) que usa ListView

    def get_queryset(self):
        """
        Filtros originales (usuario, fechas, montos y opcional 'estado').
        Este queryset NO está paginado; ListView lo paginará para 'prestamos/page_obj'.
        """
        qs = Prestamo.objects.select_related("usuario").order_by("-fecha_desembolso")

        usuario = self.request.GET.get("usuario")
        fecha_inicio = self.request.GET.get("fecha_inicio")
        fecha_fin = self.request.GET.get("fecha_fin")
        monto_min = self.request.GET.get("monto_min")
        monto_max = self.request.GET.get("monto_max")
        estado = self.request.GET.get("estado")  # 'vigentes' | 'pagados' | None

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

        if estado == "vigentes":
            qs = qs.filter(capital_pendiente__gt=0)
        elif estado == "pagados":
            qs = qs.filter(capital_pendiente=0)

        return qs

    def get_context_data(self, **kwargs):
        """
        Además del contexto clásico (page_obj/paginator/prestamos),
        añadimos el agrupado por usuario usando un queryset **no paginado** (full_qs),
        para evitar filtrar sobre un queryset ya 'sliced'.
        """
        context = super().get_context_data(**kwargs)

        historico = self.request.GET.get("historico") == "1"

        # ✅ Tomamos el queryset COMPLETO y SIN PAGINAR
        full_qs = self.get_queryset().select_related("usuario")

        # Si NO es histórico, ocultamos saldos 0
        qs_display = full_qs if historico else full_qs.filter(capital_pendiente__gt=0)

        # Contador de préstamos pendientes (saldo > 0) por usuario, usando el queryset completo
        pendientes_por_usuario = {}
        for p in full_qs:
            if (p.capital_pendiente or 0) > 0:
                pendientes_por_usuario[p.usuario_id] = pendientes_por_usuario.get(p.usuario_id, 0) + 1

        # Agrupar para mostrar
        grupos = {}  # user_id -> {"usuario": User, "prestamos": [Prestamo], "saldo_total": Decimal, "pendientes_count": int}
        for p in qs_display:
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

        # Orden por nombre de usuario (puedes cambiar a saldo_total desc si te conviene)
        items = list(grupos.values())
        items.sort(key=lambda x: (x["usuario"].username or "").lower())

        # Paginación por usuario (independiente de la paginación 'clásica' de ListView)
        page_number = self.request.GET.get("page")
        paginator_users = Paginator(items, self.paginate_by)
        users_page = paginator_users.get_page(page_number)

        context["users_page"] = users_page
        context["paginator_users"] = paginator_users
        context["is_paginated_users"] = paginator_users.num_pages > 1
        context["historico"] = historico

        # Mantén compatibilidad con plantillas previas
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
