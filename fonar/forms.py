from django import forms
from decimal import Decimal, InvalidOperation
from datetime import date
from .models import PagoAplicacion, Pago, CuotaPrestamo, SolicitudPrestamo, TasaInteres


class PagoAplicacionForm(forms.ModelForm):
    class Meta:
        model = PagoAplicacion
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        cuota = None
        if getattr(self.instance, "cuota", None):
            cuota = self.instance.cuota
        if not cuota:
            initial_cuota_id = self.initial.get("cuota") or self.data.get(f"{self.prefix}-cuota")
            if initial_cuota_id:
                try:
                    cuota = CuotaPrestamo.objects.get(pk=initial_cuota_id)
                except CuotaPrestamo.DoesNotExist:
                    pass

        if cuota:
            if (not self.instance.capital) and (f"{self.prefix}-capital" not in self.data):
                self.initial["capital"] = cuota.capital_pendiente
            if (not self.instance.interes) and (f"{self.prefix}-interes" not in self.data):
                self.initial["interes"] = cuota.interes_pendiente

    def clean(self):
        cleaned_data = super().clean()
        from decimal import Decimal

        tipo = cleaned_data.get("tipo")
        capital = cleaned_data.get("capital") or Decimal("0")
        interes = cleaned_data.get("interes") or Decimal("0")
        monto_aplicado = cleaned_data.get("monto_aplicado") or Decimal("0")

        if tipo == "prestamo":
            cleaned_data["monto_aplicado"] = capital + interes
        else:  # aporte
            cleaned_data["capital"] = Decimal("0")
            cleaned_data["interes"] = Decimal("0")
            if monto_aplicado <= 0:
                self.add_error("monto_aplicado", "Para aportes debes ingresar un monto mayor a 0.")

        return cleaned_data        


class PagoForm(forms.ModelForm):
    """Formulario para que el usuario suba pagos"""

    monto_reportado = forms.CharField(
        label="Monto reportado",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ingrese el valor del pago'
        })
    )

    class Meta:
        model = Pago
        fields = ['monto_reportado', 'soporte', 'comentarios']

    def clean_monto_reportado(self):
        monto = self.cleaned_data.get('monto_reportado')
        if not monto:
            raise forms.ValidationError("Debe ingresar un valor para el monto.")

        monto = monto.replace(".", "").replace(",", "")
        try:
            return Decimal(monto)
        except (InvalidOperation, TypeError, ValueError):
            raise forms.ValidationError("El monto ingresado no es válido. Usa solo números.")


# ==============================
# NUEVO: Formulario Solicitud de Préstamo
# ==============================
class SolicitudPrestamoForm(forms.ModelForm):
    monto = forms.CharField(
        label="Monto solicitado",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Ej: 1.000.000"
        })
    )

    class Meta:
        model = SolicitudPrestamo
        fields = ["monto", "cuotas", "fecha_deseada_desembolso"]
        widgets = {
            "fecha_deseada_desembolso": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "form-control",
                    "min": date.today().isoformat(),
                }
            )
        }

    def __init__(self, usuario, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario

        for name, field in self.fields.items():
            if name not in ["fecha_deseada_desembolso", "monto"]:
                field.widget.attrs.update({"class": "form-control"})

    def clean_monto(self):
        monto = self.cleaned_data.get("monto")
        if not monto:
            raise forms.ValidationError("Debe ingresar un monto.")

        # quitar separadores
        monto = str(monto).replace(".", "").replace(",", "")
        try:
            return Decimal(monto)
        except (InvalidOperation, TypeError, ValueError):
            raise forms.ValidationError("El monto ingresado no es válido. Usa solo números.")

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.usuario = self.usuario

        tasa = (
            TasaInteres.objects.filter(
                tipo_usuario=self.usuario.tipo_usuario,
                cuotas_min__lte=instance.cuotas,
                cuotas_max__gte=instance.cuotas
            )
            .order_by("-vigente_desde")
            .first()
        )
        if tasa:
            instance.interes = tasa.interes_mensual
        else:
            instance.interes = Decimal("0.00")

        if commit:
            instance.save()
        return instance
