from django.core.management.base import BaseCommand
from django.db.models import Sum
from decimal import Decimal
from fonar.models import Pago, PagoAplicacion, CuotaPrestamo


class Command(BaseCommand):
    help = "Recalcula pagos y cuotas existentes en la base de datos"

    def handle(self, *args, **options):
        self.stdout.write("🔄 Recalculando todas las cuotas y pagos...")

        # Recalcular todas las cuotas
        for cuota in CuotaPrestamo.objects.all():
            totales = PagoAplicacion.objects.filter(cuota=cuota).aggregate(
                total_capital=Sum("capital"),
                total_interes=Sum("interes"),
            )

            cuota.capital_pagado = totales["total_capital"] or Decimal("0")
            cuota.interes_pagado = totales["total_interes"] or Decimal("0")
            cuota.pagada = cuota.capital_pagado >= cuota.capital
            cuota.save(update_fields=["capital_pagado", "interes_pagado", "pagada"])

        # Recalcular todos los pagos
        for pago in Pago.objects.all():
            total_aplicado = PagoAplicacion.objects.filter(pago=pago).aggregate(
                total=Sum("monto_aplicado")
            )["total"] or Decimal("0")

            pago.validado = (total_aplicado == pago.monto_reportado)
            pago.save(update_fields=["validado"])

        self.stdout.write(self.style.SUCCESS("✅ Recalculo completado"))
