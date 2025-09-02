from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.db.models import Sum
from datetime import timedelta
from decimal import Decimal, getcontext, ROUND_HALF_UP
from django.conf import settings
from dateutil.relativedelta import relativedelta

# más precisión para cálculos financieros
getcontext().prec = 28  


# -------------------------
# Usuario personalizado
# -------------------------
class Usuario(AbstractUser):
    is_admin = models.BooleanField(default=False)

    TIPO_CHOICES = [
        ("asociado", "Asociado"),
        ("tercero", "Tercero"),
    ]
    tipo_usuario = models.CharField(max_length=20, choices=TIPO_CHOICES, default="asociado")

    def __str__(self):
        return self.username


# -------------------------
# Aportes
# -------------------------
class Aporte(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    fecha_aporte = models.DateField()  # Fecha manual ingresada
    fecha_registro = models.DateTimeField(default=timezone.now)  # Fecha automática
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    soporte = models.FileField(upload_to='soportes/', null=True, blank=True)

    def __str__(self):
        return f"{self.usuario.username} - {self.monto} - {self.fecha_aporte}"


# -------------------------
# Tabla de Tasa de Interés
# -------------------------
class TasaInteres(models.Model):
    tipo_usuario = models.CharField(max_length=20, choices=Usuario.TIPO_CHOICES)
    tipo_credito = models.CharField(max_length=50, default="consumo")  # se puede extender
    cuotas_min = models.PositiveIntegerField()
    cuotas_max = models.PositiveIntegerField()
    interes_mensual = models.DecimalField(max_digits=5, decimal_places=2)  # % mensual
    vigente_desde = models.DateField(default=timezone.now)

    def __str__(self):
        return f"{self.tipo_usuario} - {self.tipo_credito} ({self.cuotas_min}-{self.cuotas_max}) → {self.interes_mensual}%"


# -------------------------
# Préstamos
# -------------------------
class Prestamo(models.Model):
    usuario = models.ForeignKey('Usuario', on_delete=models.CASCADE)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    interes = models.DecimalField(max_digits=5, decimal_places=2)  # tasa mensual
    cuotas = models.IntegerField(default=1)
    fecha_desembolso = models.DateField()
    fecha_creacion = models.DateTimeField(default=timezone.now)

    def calcular_cuota_fija(self):
        interes_mensual = (self.interes / Decimal('100'))   # tasa mensual
        if interes_mensual == 0:
            return (self.monto / self.cuotas).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        cuota = self.monto * (interes_mensual * (1 + interes_mensual) ** self.cuotas) / (
            (1 + interes_mensual) ** self.cuotas - 1
        )
        return cuota.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def monto_total(self):
        cuota = self.calcular_cuota_fija()
        return cuota * self.cuotas

    def generar_cuotas(self):
        self.cuotaprestamo_set.all().delete()
        cuota_fija = self.calcular_cuota_fija()
        saldo = self.monto
        fecha_venc = self.fecha_desembolso

        for i in range(1, self.cuotas + 1):
            interes = (saldo * (self.interes / Decimal('100'))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            capital = (cuota_fija - interes).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            # última cuota ajusta saldo
            if i == self.cuotas:
                capital = saldo.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                cuota_actual = (capital + interes).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            else:
                cuota_actual = cuota_fija

            fecha_venc = fecha_venc + relativedelta(months=+1)
            saldo = (saldo - capital).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            CuotaPrestamo.objects.create(
                prestamo=self,
                numero=i,
                fecha_vencimiento=fecha_venc,
                monto_cuota=cuota_actual,
                capital=capital,
                interes=interes,
                pagada=False
            )

    def saldo_pendiente(self):
        from .models import PagoAplicacion
        pagado = PagoAplicacion.objects.filter(
            prestamo=self,
            pago__validado=True
        ).aggregate(total=Sum('monto_aplicado'))['total'] or Decimal('0')
        return self.monto - pagado

    def save(self, *args, **kwargs):
        if self.pk:
            old = Prestamo.objects.get(pk=self.pk)
            super().save(*args, **kwargs)
            if (
                old.monto != self.monto
                or old.interes != self.interes
                or old.cuotas != self.cuotas
            ):
                self.cuotaprestamo_set.all().delete()
                self.generar_cuotas()
        else:
            super().save(*args, **kwargs)
            self.generar_cuotas()

    def __str__(self):
        return f"Préstamo #{self.id} - {self.usuario.username}"

    @property
    def capital_pendiente(self):
        from .models import PagoAplicacion

        # Total de capital pagado validado
        capital_pagado = PagoAplicacion.objects.filter(
            prestamo=self,
            pago__validado=True
        ).aggregate(total=Sum("capital"))["total"] or Decimal("0.00")

        # Capital pendiente = monto original - capital ya pagado
        return (self.monto - capital_pagado).quantize(Decimal("0.01"))


# -------------------------
# Solicitudes de Préstamos
# -------------------------
class SolicitudPrestamo(models.Model):
    ESTADO_CHOICES = [
        ("pendiente", "Pendiente"),
        ("aprobado", "Aprobado"),
        ("rechazado", "Rechazado"),
    ]
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    cuotas = models.PositiveIntegerField()
    fecha_solicitud = models.DateTimeField(default=timezone.now)
    fecha_deseada_desembolso = models.DateField()
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="pendiente")

    # tasa congelada en el momento de la solicitud
    interes = models.DecimalField(max_digits=5, decimal_places=2)

    def calcular_cuota_fija(self):
        interes_mensual = (self.interes / Decimal('100'))
        if interes_mensual == 0:
            return (self.monto / self.cuotas).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        cuota = self.monto * (interes_mensual * (1 + interes_mensual) ** self.cuotas) / (
            (1 + interes_mensual) ** self.cuotas - 1
        )
        return cuota.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def __str__(self):
        return f"Solicitud #{self.id} - {self.usuario.username} - {self.estado}"


# -------------------------
# Cuotas del préstamo
# -------------------------
class CuotaPrestamo(models.Model):
    prestamo = models.ForeignKey(Prestamo, on_delete=models.CASCADE)
    numero = models.PositiveIntegerField()
    fecha_vencimiento = models.DateField()
    monto_cuota = models.DecimalField(max_digits=12, decimal_places=2)
    interes = models.DecimalField(max_digits=12, decimal_places=2)
    capital = models.DecimalField(max_digits=12, decimal_places=2)
    pagada = models.BooleanField(default=False)
    fecha_pago = models.DateField(null=True, blank=True)
    capital_pagado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    interes_pagado = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    @property
    def capital_pendiente(self):
        cap = self.capital or Decimal('0')
        pag = self.capital_pagado or Decimal('0')
        return max(Decimal('0'), cap - pag)

    @property
    def interes_pendiente(self):
        inte = self.interes or Decimal('0')
        pag = self.interes_pagado or Decimal('0')
        return max(Decimal('0'), inte - pag)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['prestamo', 'numero'], name='uq_prestamo_numero')
        ]

    def __str__(self):
        return f"Cuota {self.numero} - Préstamo {self.prestamo.id}"


# -------------------------
# Pagos 
# -------------------------
class Pago(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    monto_reportado = models.DecimalField(max_digits=12, decimal_places=2)
    soporte = models.FileField(upload_to="pagos/soportes/", blank=True, null=True)
    fecha = models.DateTimeField(default=timezone.now) 
    validado = models.BooleanField(default=False)
    comentarios = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Pago {self.id} - {self.usuario.username}"

    @property
    def total_aplicado(self):
        return self.aplicaciones.aggregate(
            total=Sum("monto_aplicado")
        )["total"] or Decimal("0")

    @property
    def faltante(self):
        return (self.monto_reportado or Decimal("0")) - self.total_aplicado


# -------------------------
# Aplicación de Pagos 
# -------------------------
class PagoAplicacion(models.Model):
    TIPO_CHOICES = [
        ("aporte", "Aporte"),
        ("prestamo", "Préstamo"),
    ]

    pago = models.ForeignKey("Pago", on_delete=models.CASCADE, related_name="aplicaciones")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)

    prestamo = models.ForeignKey("Prestamo", on_delete=models.SET_NULL, null=True, blank=True)
    cuota = models.ForeignKey("CuotaPrestamo", on_delete=models.SET_NULL, null=True, blank=True)
    aporte = models.ForeignKey("Aporte", on_delete=models.SET_NULL, null=True, blank=True, related_name="aplicaciones")

    fecha_aporte = models.DateField(null=True, blank=True)
    capital = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    interes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monto_aplicado = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        from decimal import Decimal
        from django.utils import timezone
        from .models import Aporte

        if self.tipo == "prestamo":
            if self.cuota and not self.prestamo:
                self.prestamo = self.cuota.prestamo
            if self.cuota:
                if not self.capital:
                    self.capital = self.cuota.capital_pendiente
                if not self.interes:
                    self.interes = self.cuota.interes_pendiente
            self.monto_aplicado = (self.capital or Decimal("0")) + (self.interes or Decimal("0"))
            if self.aporte_id:
                try:
                    self.aporte.delete()
                except Exception:
                    pass
                self.aporte = None
        elif self.tipo == "aporte":
            self.prestamo = None
            self.cuota = None
            self.capital = Decimal("0")
            self.interes = Decimal("0")
            if not self.monto_aplicado:
                self.monto_aplicado = Decimal("0")
            usuario = self.pago.usuario if self.pago_id else None
            fecha_aporte = self.fecha_aporte or (self.pago.fecha.date() if self.pago_id else timezone.now().date())
            soporte = getattr(self.pago, "soporte", None)
            if self.aporte_id:
                ap = self.aporte
                ap.usuario = usuario or ap.usuario
                ap.fecha_aporte = fecha_aporte
                ap.monto = self.monto_aplicado
                if soporte:
                    ap.soporte = soporte
                ap.save()
            else:
                if usuario:
                    ap = Aporte.objects.create(
                        usuario=usuario,
                        fecha_aporte=fecha_aporte,
                        monto=self.monto_aplicado,
                        soporte=soporte
                    )
                    self.aporte = ap
        super().save(*args, **kwargs)

    def __str__(self):
        return f"PagoAplicacion {self.id} - {self.tipo} - {self.monto_aplicado}"


# -------------------------
# Retiros
# -------------------------
class Retiro(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    fecha = models.DateField(auto_now_add=True)
    motivo = models.TextField()

    def __str__(self):
        return f"{self.usuario.username} - {self.fecha}"


# -------------------------
# Balance del Fondo
# -------------------------
class FondoBalance(models.Model):
    año = models.PositiveIntegerField(unique=True)
    nequi = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    efectivo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    daviplata = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    comentarios = models.TextField(blank=True, null=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    def total_cuentas(self):
        return (self.nequi or 0) + (self.efectivo or 0) + (self.daviplata or 0)

    def __str__(self):
        return f"Balance {self.año}"