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
        Filtros originales (usuario, fechas, montos).
        OJO: NO filtramos por 'capital_pendiente' aquí porque no es campo de BD.
        """
        qs = Prestamo.objects.select_related("usuario").order_by("-fecha_desembolso")

        usuario = self.request.GET.get("usuario")
        fecha_inicio = self.request.GET.get("fecha_inicio")
        fecha_fin = self.request.GET.get("fecha_fin")
        monto_min = self.request.GET.get("monto_min")
        monto_max = self.request.GET.get("monto_max")

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

        return qs

    def get_context_data(self, **kwargs):
        """
        Además del contexto clásico (page_obj/paginator/prestamos),
        añadimos el agrupado por usuario usando un queryset NO paginado,
        y ahí aplicamos el criterio de 'histórico' con la propiedad Python
        'capital_pendiente' (no campo de BD).
        """
        context = super().get_context_data(**kwargs)

        historico = self.request.GET.get("historico") == "1"

        # ✅ Queryset completo y SIN paginar para el agrupado
        full_qs = self.get_queryset().select_related("usuario")

        # Helper para leer capital_pendiente de forma segura
        def cap_pend(p):
            # Usa la propiedad Python si existe; de lo contrario, 0 (no rompe)
            return getattr(p, "capital_pendiente", 0) or 0

        # Si NO es histórico, ocultamos préstamos con saldo 0
        if historico:
            qs_display = list(full_qs)
        else:
            qs_display = [p for p in full_qs if cap_pend(p) > 0]

        # Contador de préstamos pendientes por usuario (usando full_qs)
        pendientes_por_usuario = {}
        for p in full_qs:
            if cap_pend(p) > 0:
                pendientes_por_usuario[p.usuario_id] = pendientes_por_usuario.get(p.usuario_id, 0) + 1

        # Agrupar lo que se mostrará
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
            d["saldo_total"] += cap_pend(p)

        # Orden por nombre de usuario (cámbialo a saldo_total desc si prefieres)
        items = list(grupos.values())
        items.sort(key=lambda x: (x["usuario"].username or "").lower())

        # Paginación por usuario (independiente de la clásica)
        page_number = self.request.GET.get("page")
        paginator_users = Paginator(items, self.paginate_by)
        users_page = paginator_users.get_page(page_number)

        context["users_page"] = users_page
        context["paginator_users"] = paginator_users
        context["is_paginated_users"] = paginator_users.num_pages > 1
        context["historico"] = historico

        # Compatibilidad con plantillas antiguas
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
