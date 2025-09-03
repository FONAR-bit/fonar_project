from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum
from decimal import Decimal
from django.utils import timezone
from .models import Prestamo, Pago, PagoAplicacion, CuotaPrestamo, SolicitudPrestamo


# ==== Señal para Prestamo ====
@receiver(post_save, sender=Prestamo)
def generar_cuotas_automaticas(sender, instance, created, **kwargs):
    """Genera cuotas automáticamente al crear un nuevo préstamo"""
    if created:
        instance.generar_cuotas()


# ==== Funciones de recalculo ====
def recalcular_pago(pago: Pago):
    """Recalcula el estado de validación de un Pago"""
    total_aplicado = PagoAplicacion.objects.filter(pago=pago).aggregate(
        total=Sum("monto_aplicado")
    )["total"] or 0

    pago.validado = (total_aplicado == pago.monto_reportado)
    pago.save(update_fields=["validado"])


def recalcular_cuota(cuota: CuotaPrestamo):
    """Recalcula capital/interés pagado y estado de la cuota"""
    totales = PagoAplicacion.objects.filter(cuota=cuota).aggregate(
        total_capital=Sum('capital'),
        total_interes=Sum('interes')
    )

    cuota.capital_pagado = totales['total_capital'] or Decimal('0')
    cuota.interes_pagado = totales['total_interes'] or Decimal('0')
    cuota.pagada = cuota.capital_pagado >= cuota.capital
    cuota.save(update_fields=["capital_pagado", "interes_pagado", "pagada"])


# ==== Señales de PagoAplicacion ====
@receiver(post_save, sender=PagoAplicacion)
def actualizar_cuota_y_pago_post_save(sender, instance, **kwargs):
    """Cuando se guarda una aplicación, recalcular cuota y pago"""
    if instance.cuota:
        recalcular_cuota(instance.cuota)
    if instance.pago:
        recalcular_pago(instance.pago)


@receiver(post_delete, sender=PagoAplicacion)
def actualizar_cuota_y_pago_post_delete(sender, instance, **kwargs):
    """Cuando se elimina una aplicación, recalcular cuota y pago"""
    if instance.cuota:
        recalcular_cuota(instance.cuota)
    if instance.pago:
        recalcular_pago(instance.pago)


# ==== Señal de Pago ====
@receiver(post_save, sender=Pago)
def actualizar_cuotas_por_pago(sender, instance, **kwargs):
    """Cuando se guarda un Pago, recalcular todas sus cuotas"""
    aplicaciones = PagoAplicacion.objects.filter(pago=instance)
    for app in aplicaciones:
        if app.cuota:
            recalcular_cuota(app.cuota)


@receiver(post_delete, sender=PagoAplicacion)
def borrar_aporte_asociado(sender, instance, **kwargs):
    """Si se elimina una aplicación tipo aporte, borrar el aporte relacionado"""
    if instance.tipo == "aporte" and getattr(instance, "aporte_id", None):
        try:
            instance.aporte.delete()
        except Exception:
            pass


# ==== Señal de SolicitudPrestamo ====
@receiver(post_save, sender=SolicitudPrestamo)
def crear_prestamo_si_aprobado(sender, instance, created, **kwargs):
    """
    Cuando una solicitud de préstamo cambia a estado 'aprobado',
    se crea automáticamente un Prestamo si no existe aún.
    """
    if instance.estado == "aprobado":
        prestamo_existente = Prestamo.objects.filter(
            usuario=instance.usuario,
            monto=instance.monto,
            cuotas=instance.cuotas,
            fecha_desembolso=instance.fecha_deseada_desembolso
        ).first()

        if not prestamo_existente:
            prestamo = Prestamo.objects.create(
                usuario=instance.usuario,
                monto=instance.monto,
                interes=instance.interes,
                cuotas=instance.cuotas,
                fecha_desembolso=instance.fecha_deseada_desembolso or timezone.now().date()
            )
            # Las cuotas se generan automáticamente por la señal de Prestamo
            print(f"✅ Prestamo #{prestamo.id} creado para solicitud #{instance.id}")
