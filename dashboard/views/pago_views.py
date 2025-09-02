from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce
from fonar.models import Pago, PagoAplicacion
from dashboard.forms import PagoForm,  ValidatingPagoAplicacionFormSet


class PagoListView(ListView):
    model = Pago
    template_name = "dashboard/pagos/list.html"
    context_object_name = "pagos"
    paginate_by = 10

    def get_queryset(self):
        queryset = (
            Pago.objects.select_related("usuario")
            .annotate(
                aplicado=Coalesce(
                    Sum("aplicaciones__monto_aplicado"),
                    0,
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            )
            .order_by("-fecha")
        )

        # ---- filtros ----
        usuario = self.request.GET.get("usuario")
        validado = self.request.GET.get("validado")
        ordenar = self.request.GET.get("ordenar")

        if usuario:
            queryset = queryset.filter(usuario__username__icontains=usuario)

        if validado in ["True", "False"]:
            queryset = queryset.filter(validado=(validado == "True"))

        # ordenar
        if ordenar == "fecha":
            queryset = queryset.order_by("-fecha")
        elif ordenar == "monto":
            queryset = queryset.order_by("-monto_reportado")
        elif ordenar == "usuario":
            queryset = queryset.order_by("usuario__username")

     # ordenamiento dinámico
        ordenar = self.request.GET.get("ordenar")
        if ordenar in ["fecha", "-fecha", "monto_reportado", "-monto_reportado"]:
            queryset = queryset.order_by(ordenar)
        else:
            queryset = queryset.order_by("-fecha")  # por defecto

        return queryset

class PagoCreateView(CreateView):
    model = Pago
    form_class = PagoForm
    template_name = "dashboard/pagos/create.html"
    success_url = reverse_lazy("dashboard:pagos-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["formset"] = ValidatingPagoAplicacionFormSet(self.request.POST)
        else:
            context["formset"] = ValidatingPagoAplicacionFormSet()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context["formset"]
        if formset.is_valid():
            with transaction.atomic():
                self.object = form.save()
                formset.instance = self.object
                formset.save()
                messages.success(self.request, "✅ Pago creado con sus aplicaciones.")
                return redirect(self.success_url)
        else:
            return self.form_invalid(form)

class PagoUpdateView(UpdateView):
    model = Pago
    form_class = PagoForm
    template_name = "dashboard/pagos/update.html"
    success_url = reverse_lazy("dashboard:pagos-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pago = self.get_object()
        if self.request.POST:
            context["formset"] = ValidatingPagoAplicacionFormSet(
                self.request.POST,
                instance=pago,
                form_kwargs={"usuario": pago.usuario}
            )
        else:
            context["formset"] = ValidatingPagoAplicacionFormSet(
                instance=pago,
                form_kwargs={"usuario": pago.usuario}
            )
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context["formset"]
        if formset.is_valid():
            with transaction.atomic():
                self.object = form.save()
                formset.instance = self.object
                formset.save()
                action = self.request.POST.get("action")
                if action == "save_add":
                    messages.success(self.request, "✅ Pago actualizado. Puedes crear uno nuevo.")
                    return redirect("dashboard:pagos-create")
                elif action == "save_continue":
                    messages.success(self.request, "✅ Pago actualizado. Sigues editando.")
                    return redirect("dashboard:pagos-update", pk=self.object.pk)
                else:  # save normal
                    messages.success(self.request, "✅ Pago actualizado con sus aplicaciones.")
                    return redirect(self.success_url)
        else:
            return self.form_invalid(form)

class PagoDeleteView(DeleteView):
    model = Pago
    template_name = "dashboard/pagos/confirm_delete.html"
    success_url = reverse_lazy("dashboard:pagos-list")

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "🗑️ Pago eliminado correctamente.")
        return super().delete(request, *args, **kwargs)


class PagoDetailView(DetailView):
    model = Pago
    template_name = "dashboard/pagos/detail.html"
    context_object_name = "pago"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["formset"] = ValidatingPagoAplicacionFormSet(self.request.POST, instance=self.object)
        else:
            context["formset"] = ValidatingPagoAplicacionFormSet(instance=self.object)
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        formset = ValidatingPagoAplicacionFormSet(self.request.POST, instance=self.object)
        if formset.is_valid():
            formset.save()
            messages.success(self.request, "✅ Aplicaciones del pago actualizadas.")
            return redirect("dashboard:pagos-detail", pk=self.object.pk)
        return self.render_to_response(self.get_context_data(formset=formset))
