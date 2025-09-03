from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, AuthenticationForm
from django.forms import inlineformset_factory, BaseInlineFormSet
from fonar.models import Pago, PagoAplicacion, CuotaPrestamo as Cuota, Aporte, Prestamo, CuotaPrestamo, TasaInteres 


Usuario = get_user_model()


# -----------------------
# Formularios de Usuarios
# -----------------------
class UsuarioForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ["username", "email", "is_active", "is_staff"]


class UsuarioCreateForm(UserCreationForm):
    class Meta:
        model = Usuario
        fields = ["username", "email", "first_name", "last_name","tipo_usuario", "is_active", "is_staff"]


class UsuarioUpdateForm(UserChangeForm):
    password = None  # Ocultamos campo de password
    class Meta:
        model = Usuario
        fields = ["username", "email", "is_active", "first_name", "last_name","tipo_usuario", "is_staff"]


class AdminLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Usuario",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Ingrese su usuario"
        })
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Ingrese su contraseña"
        })
    )


# -----------------------
# Formularios de Pagos
# -----------------------
class PagoForm(forms.ModelForm):
    class Meta:
        model = Pago
        fields = ["usuario", "monto_reportado", "soporte", "fecha", "validado", "comentarios"]
        widgets = {
            "usuario": forms.Select(attrs={"class": "form-select"}),
            "monto_reportado": forms.NumberInput(attrs={"class": "form-control text-end", "step": "0.01"}),
            "soporte": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "fecha": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date", "class": "form-control"}
            ),
            "validado": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "comentarios": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha"].input_formats = ["%Y-%m-%d"]


class PagoAplicacionForm(forms.ModelForm):
    class Meta:
        model = PagoAplicacion
        fields = [
            "tipo", "prestamo", "cuota", "aporte",
            "fecha_aporte", "capital", "interes", "monto_aplicado"
        ]
        widgets = {
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "prestamo": forms.Select(attrs={"class": "form-select"}),
            "cuota": forms.Select(attrs={"class": "form-select"}),
            "aporte": forms.HiddenInput(),  # 👈 ahora es hidden, no select
            "fecha_aporte": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date", "class": "form-control"}
            ),
            "capital": forms.NumberInput(attrs={"class": "form-control text-end", "step": "0.01"}),
            "interes": forms.NumberInput(attrs={"class": "form-control text-end", "step": "0.01"}),
            "monto_aplicado": forms.NumberInput(attrs={"class": "form-control text-end", "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        usuario = kwargs.pop("usuario", None)
        super().__init__(*args, **kwargs)

        # formato compatible con <input type="date">
        self.fields["fecha_aporte"].input_formats = ["%Y-%m-%d"]

        if "cuota" in self.fields:
            qs = Cuota.objects.filter(pagada=False)
            if usuario:
                qs = qs.filter(prestamo__usuario=usuario)
            if self.instance and self.instance.pk and self.instance.cuota:
                qs = (qs | Cuota.objects.filter(pk=self.instance.cuota.pk)).distinct()
            self.fields["cuota"].queryset = qs

        # aplica estilos
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({"class": "form-check-input"})
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.update({"class": "form-select"})
            else:
                css = field.widget.attrs.get("class", "")
                field.widget.attrs["class"] = f"{css} form-control".strip()


# -----------------------
# InlineFormset: Pago + Aplicaciones
# -----------------------
class BasePagoAplicacionFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()

        if any(self.errors):
            return

        total_aplicado = 0
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            monto = form.cleaned_data.get("monto_aplicado") or 0
            total_aplicado += monto

        pago = self.instance
        if pago and pago.monto_reportado is not None:
            if total_aplicado > pago.monto_reportado:
                raise forms.ValidationError(
                    f"❌ El monto aplicado ({total_aplicado:,}) no puede ser mayor al monto reportado ({pago.monto_reportado:,})."
                )


ValidatingPagoAplicacionFormSet = inlineformset_factory(
    Pago,
    PagoAplicacion,
    form=PagoAplicacionForm,
    formset=BasePagoAplicacionFormSet,
    extra=1,
    can_delete=True
)

class AporteForm(forms.ModelForm):
    class Meta:
        model = Aporte
        fields = ['usuario', 'fecha_aporte', 'monto', 'soporte']
        widgets = {
            'fecha_aporte': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'type': 'date'}
            ),
        }

class PrestamoForm(forms.ModelForm):
    class Meta:
        model = Prestamo
        fields = ["usuario", "monto", "interes", "cuotas", "fecha_desembolso"]
        widgets = {
            "usuario": forms.Select(attrs={"class": "form-select"}),
            "monto": forms.NumberInput(attrs={"class": "form-control text-end", "step": "0.01"}),
            "interes": forms.NumberInput(attrs={"class": "form-control text-end", "step": "0.01"}),
            "cuotas": forms.NumberInput(attrs={"class": "form-control text-end"}),
            "fecha_desembolso": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date", "class": "form-control"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha_desembolso"].input_formats = ["%Y-%m-%d"]

class TasaInteresForm(forms.ModelForm):
    class Meta:
        model = TasaInteres
        fields = ["tipo_usuario", "tipo_credito", "cuotas_min", "cuotas_max", "interes_mensual", "vigente_desde"]
        widgets = {
            "tipo_usuario": forms.Select(attrs={"class": "form-select"}),
            "tipo_credito": forms.TextInput(attrs={"class": "form-control"}),
            "cuotas_min": forms.NumberInput(attrs={"class": "form-control"}),
            "cuotas_max": forms.NumberInput(attrs={"class": "form-control"}),
            "interes_mensual": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "vigente_desde": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vigente_desde"].input_formats = ["%Y-%m-%d"]
