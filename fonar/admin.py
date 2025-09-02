from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from decimal import Decimal, InvalidOperation
from django.forms.models import BaseInlineFormSet
from .models import Usuario, Aporte, Prestamo, Retiro, CuotaPrestamo, Pago, PagoAplicacion, SolicitudPrestamo, TasaInteres
from .forms import PagoAplicacionForm
from django.utils.formats import number_format


# ========== InlineFormSet con validación ==========
class PagoAplicacionInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        total_aplicado = Decimal("0")
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if form.cleaned_data.get("DELETE"):
                continue
            monto = form.cleaned_data.get("monto_aplicado") or Decimal("0")
            total_aplicado += monto

        monto_reportado = self.instance.monto_reportado or Decimal("0")
        raw = self.data.get("monto_reportado")
        if raw not in (None, ""):
            try:
                monto_reportado = Decimal(str(raw))
            except InvalidOperation:
                pass

        if total_aplicado > monto_reportado:
            raise ValidationError(
                f"❌ El total aplicado ({number_format(total_aplicado, decimal_pos=2)}) "
                f"supera el monto reportado ({number_format(monto_reportado, decimal_pos=2)}). "
                "Corrige las aplicaciones."
            )

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)

        # Hacer obligatorio "prestamo" solo si el tipo es "prestamo"
        class CustomFormset(formset):
            def clean(self_inner):
                super().clean()
                for form in self_inner.forms:
                    if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                        continue

                    tipo = form.cleaned_data.get("tipo")
                    prestamo = form.cleaned_data.get("prestamo")

                    if tipo == "prestamo" and not prestamo:
                        form.add_error(
                            "prestamo",
                            "⚠️ Debe seleccionar un préstamo si el tipo es 'préstamo'."
                        )

        return CustomFormset


# ========== Inline de PagoAplicacion ==========
class PagoAplicacionInline(admin.TabularInline):
    model = PagoAplicacion
    form = PagoAplicacionForm
    formset = PagoAplicacionInlineFormSet
    extra = 1
    can_delete = True
    fields = ("tipo", "cuota", "capital", "interes", "monto_aplicado", "fecha_aporte")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        from .models import Prestamo, CuotaPrestamo, Pago, PagoAplicacion

        pago_usuario_id = None
        pago_id = None

        # Detectar si estamos en edición de un pago
        if "change" in request.path:
            try:
                pago_id = request.path.strip("/").split("/")[-2]
                pago = Pago.objects.get(pk=pago_id)
                pago_usuario_id = pago.usuario_id
            except Exception:
                pass

        if not pago_usuario_id:
            pago_usuario_id = request.POST.get("usuario") or request.GET.get("usuario")

        # Filtro para campo "prestamo"
        if db_field.name == "prestamo":
            if pago_usuario_id:
                kwargs["queryset"] = Prestamo.objects.filter(
                    usuario_id=pago_usuario_id,
                    cuotaprestamo__pagada=False
                ).distinct()
            else:
                kwargs["queryset"] = Prestamo.objects.none()

        # Filtro para campo "cuota"
        if db_field.name == "cuota":
            if pago_usuario_id:
                qs = CuotaPrestamo.objects.filter(
                    prestamo__usuario_id=pago_usuario_id,
                    pagada=False
                )

                # 👇 Si estamos editando un pago, incluir también las cuotas ya seleccionadas
                if pago_id:
                    seleccionadas = PagoAplicacion.objects.filter(
                        pago_id=pago_id
                    ).values_list("cuota_id", flat=True)
                    qs = qs | CuotaPrestamo.objects.filter(pk__in=seleccionadas)

                kwargs["queryset"] = qs.distinct()
            else:
                kwargs["queryset"] = CuotaPrestamo.objects.none()

        return super().formfield_for_foreignkey(db_field, request, **kwargs)	

# ========== Admin de Pago ==========
@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ("id", "usuario", "monto_reportado_moneda", "faltante", "validado", "fecha")
    inlines = [PagoAplicacionInline]

    fieldsets = (
        ('Información del pago', {
            'fields': ('usuario', 'monto_reportado', 'faltante', 'comentarios', 'soporte', 'fecha')
        }),
        ('Gestión del administrador', {
            'fields': ('validado',)
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        """Hace que ciertos campos sean editables al crear y de solo lectura al editar."""
        if obj:  # Si es edición
            return ('usuario', 'soporte', 'faltante')
        return ('faltante',)  # En creación, solo 'faltante' y 'fecha' quedan readonly

    def faltante(self, obj):
        total_aplicado = obj.aplicaciones.aggregate(total=Sum("monto_aplicado"))["total"] or 0
        valor = obj.monto_reportado - total_aplicado
        return f"${number_format(valor, decimal_pos=2)}"
    faltante.short_description = "Monto faltante por cruzar"

    def monto_reportado_moneda(self, obj):
        return f"${number_format(obj.monto_reportado, decimal_pos=2)}"
    monto_reportado_moneda.short_description = "Monto reportado"

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

        from .models import PagoAplicacion
        from .signals import recalcular_cuota, recalcular_pago

        pago = form.instance

        # Recalcular todas las cuotas asociadas al pago
        aplicaciones = PagoAplicacion.objects.filter(pago=pago)
        for app in aplicaciones:
            if app.cuota:
                recalcular_cuota(app.cuota)

        # Recalcular el estado del pago
        recalcular_pago(pago)

# ========== Admin de Usuario ==========
@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('username', 'email', 'tipo_usuario', 'is_admin', 'is_staff', 'is_active')
    list_filter = ('tipo_usuario', 'is_admin', 'is_staff')
    search_fields = ('username', 'email')
    ordering = ('username',)

    fieldsets = UserAdmin.fieldsets + (
        ('Información adicional', {
            'fields': ('tipo_usuario', 'is_admin')
        }),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información adicional', {
            'fields': ('tipo_usuario', 'is_admin')
        }),
    )


# ========== Admin de Aporte ==========
@admin.register(Aporte)
class AporteAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'monto_moneda', 'fecha_aporte', 'fecha_registro')
    list_filter = ('fecha_aporte', 'fecha_registro')
    search_fields = ('usuario__username',)
    ordering = ('-fecha_aporte',)
    readonly_fields = ('fecha_registro',)

    def monto_moneda(self, obj):
        return f"${number_format(obj.monto, decimal_pos=2)}"
    monto_moneda.short_description = "Monto"


# ========== Admin de Prestamo ==========
@admin.register(Prestamo)
class PrestamoAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'monto_moneda', 'interes', 'cuotas', 'fecha_desembolso')
    list_filter = ('usuario', 'fecha_desembolso')
    search_fields = ('usuario__username',)

    def monto_moneda(self, obj):
        return f"${number_format(obj.monto, decimal_pos=2)}"
    monto_moneda.short_description = "Monto"


# ========== Admin de CuotaPrestamo ==========
@admin.register(CuotaPrestamo)
class CuotaPrestamoAdmin(admin.ModelAdmin):
    list_display = (
        'prestamo', 'numero', 'fecha_vencimiento',
        'capital_moneda', 'interes_moneda', 'saldo_moneda',
        'capital_pagado_moneda', 'interes_pagado_moneda',
        'capital_pendiente_moneda', 'interes_pendiente_moneda',
        'intereses_cobrados_efectivos_moneda',
        'pagada'
    )
    list_filter = ('pagada', 'fecha_vencimiento')
    search_fields = ('prestamo__usuario__username',)

    readonly_fields = (
        'capital_pagado_moneda', 'interes_pagado_moneda',
        'capital_pendiente_moneda', 'interes_pendiente_moneda',
        'intereses_cobrados_efectivos_moneda'
    )

    def capital_moneda(self, obj):
        return f"${number_format(obj.capital, decimal_pos=2)}"
    capital_moneda.short_description = "Capital"

    def interes_moneda(self, obj):
        return f"${number_format(obj.interes, decimal_pos=2)}"
    interes_moneda.short_description = "Interés"

    def saldo_moneda(self, obj):
        saldo = obj.capital_pendiente + obj.interes_pendiente
        return "${:,.2f}".format(saldo)

    # 👇 NUEVOS CAMPOS CON FORMATO
    def capital_pagado_moneda(self, obj):
        return f"${number_format(obj.capital_pagado, decimal_pos=2)}"
    capital_pagado_moneda.short_description = "Capital pagado"

    def interes_pagado_moneda(self, obj):
        return f"${number_format(obj.interes_pagado, decimal_pos=2)}"
    interes_pagado_moneda.short_description = "Interés pagado"

    def capital_pendiente_moneda(self, obj):
        return f"${number_format(obj.capital_pendiente, decimal_pos=2)}"
    capital_pendiente_moneda.short_description = "Capital pendiente"

    def interes_pendiente_moneda(self, obj):
        return f"${number_format(obj.interes_pendiente, decimal_pos=2)}"
    interes_pendiente_moneda.short_description = "Interés pendiente"

    def intereses_cobrados_efectivos_moneda(self, obj):
        return f"${number_format(obj.interes_pagado, decimal_pos=2)}"
    intereses_cobrados_efectivos_moneda.short_description = "Interés Real pagado"

# ========== Admin de Retiro ==========
@admin.register(Retiro)
class RetiroAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'fecha', 'motivo')
    list_filter = ('fecha',)
    search_fields = ('usuario__username',)
    ordering = ('-fecha',)
    readonly_fields = ('fecha',)

    def monto_moneda(self, obj):
        return f"${number_format(obj.monto, decimal_pos=2)}"
    monto_moneda.short_description = "Monto"

# ========== Admin de SolicitudPrestamo ==========
@admin.register(SolicitudPrestamo)
class SolicitudPrestamoAdmin(admin.ModelAdmin):
    list_display = (
        "id", "usuario", "monto_moneda", "cuotas", "interes",
        "estado", "fecha_solicitud", "fecha_deseada_desembolso"
    )
    list_filter = ("estado", "fecha_solicitud")
    search_fields = ("usuario__username",)
    ordering = ("-fecha_solicitud",)

    def monto_moneda(self, obj):
        return f"${number_format(obj.monto, decimal_pos=0)}"
    monto_moneda.short_description = "Monto"

    # 👇 Ahora solo guardamos la solicitud,
    # la creación del préstamo se maneja con signals.py
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        if obj.estado == "aprobado":
            self.message_user(
                request,
                f"✅ Solicitud #{obj.id} aprobada. El préstamo se creó automáticamente."
            )

# ========== Admin de TasaInteres ==========
@admin.register(TasaInteres)
class TasaInteresAdmin(admin.ModelAdmin):
    list_display = ("id", "tipo_usuario", "tipo_credito", "cuotas_min", "cuotas_max", "interes_mensual", "vigente_desde")
    list_filter = ("tipo_usuario", "tipo_credito")
    search_fields = ("tipo_usuario", "tipo_credito")
    ordering = ("-vigente_desde",)