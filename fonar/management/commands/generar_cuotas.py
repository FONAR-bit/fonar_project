from django.core.management.base import BaseCommand
from fonar.models import Prestamo

class Command(BaseCommand):
    help = "Genera cuotas para todos los préstamos existentes que no tengan plan de amortización"

    def handle(self, *args, **kwargs):
        prestamos = Prestamo.objects.all()
        total = 0

        for prestamo in prestamos:
            if prestamo.cuotaprestamo_set.count() == 0:  # Solo si aún no tiene cuotas
                prestamo.generar_cuotas()
                total += 1
                self.stdout.write(self.style.SUCCESS(f"Cuotas generadas para Préstamo #{prestamo.id}"))
            else:
                self.stdout.write(self.style.WARNING(f"Préstamo #{prestamo.id} ya tiene cuotas"))

        self.stdout.write(self.style.SUCCESS(f"\nProceso completado. Se generaron cuotas para {total} préstamo(s)."))
