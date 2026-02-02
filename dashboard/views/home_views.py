# views.py

from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from dashboard.views.mixins import StaffRequiredMixin
from django.db.models import Sum, Min, Max, Count
from django.utils import timezone
from django.utils.timezone import now
from django.shortcuts import redirect
from django.http import HttpResponse
from decimal import Decimal

from fonar.models import Usuario, Aporte, Prestamo, PagoAplicacion, FondoBalance

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Table,
    TableStyle,
    Spacer,
    Image,
    PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet

from django.conf import settings
import os


# ================================================================
# 🧩 Vista del Dashboard
# ================================================================
class DashboardHomeView(LoginRequiredMixin, StaffRequiredMixin, TemplateView):
    template_name = "dashboard/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        año_actual = self.request.GET.get("year")
        try:
            año_actual = int(año_actual)
        except (TypeError, ValueError):
            año_actual = timezone.now().year

        hoy = timezone.now().date()

        total_aportes_general = (
            Aporte.objects.filter(fecha_aporte__year=año_actual)
            .aggregate(total=Sum("monto"))["total"] or Decimal("0")
        )

        fecha_inicio_fondo = (
            Aporte.objects.filter(fecha_aporte__year=año_actual)
            .aggregate(fecha=Min("fecha_aporte"))["fecha"] or hoy
        )
        dias_fondo = max((hoy - fecha_inicio_fondo).days, 1)

        fecha_ultimo_aporte_general = (
            Aporte.objects.filter(fecha_aporte__year=año_actual)
            .aggregate(fecha=Max("fecha_aporte"))["fecha"]
        )

        total_intereses_general = (
            PagoAplicacion.objects.filter(
                tipo="prestamo",
                cuota__fecha_vencimiento__year=año_actual,
                pago__validado=True,
            ).aggregate(total=Sum("interes"))["total"] or Decimal("0")
        )

        # ============================================================
        # ✅ NUEVO: Pre-cálculos para Otros Aportes (Viaje/Actividad/Admin APP)
        # ============================================================

        # 1) Aportes Viaje (sumatoria por usuario)
        aportes_viaje_qs = (
            PagoAplicacion.objects.filter(
                tipo="aporte_viaje",
                pago__validado=True,
                pago__fecha__year=año_actual,
                pago__usuario__tipo_usuario="asociado",
            )
            .values("pago__usuario")
            .annotate(total=Sum("monto_aplicado"))
        )
        aportes_viaje_map = {
            row["pago__usuario"]: (row["total"] or Decimal("0"))
            for row in aportes_viaje_qs
        }

        # 2) Recaudo Actividad (total y participantes para repartir en partes iguales)
        actividad_qs = PagoAplicacion.objects.filter(
            tipo="actividad_recaudo",
            pago__validado=True,
            pago__fecha__year=año_actual,
            pago__usuario__tipo_usuario="asociado",
        )

        total_recaudo_actividad = (
            actividad_qs.aggregate(total=Sum("monto_aplicado"))["total"] or Decimal("0")
        )

        participantes_actividad_ids = list(
            actividad_qs.values_list("pago__usuario", flat=True).distinct()
        )
        cantidad_participantes_actividad = len(participantes_actividad_ids)

        reparto_actividad_por_persona = (
            (total_recaudo_actividad / Decimal(cantidad_participantes_actividad))
            if cantidad_participantes_actividad > 0
            else Decimal("0")
        )

        # 3) Administración APP (resumen por usuario + totales)
        admin_app_qs = PagoAplicacion.objects.filter(
            tipo="admin_app",
            pago__validado=True,
            pago__fecha__year=año_actual,
            pago__usuario__tipo_usuario="asociado",
        ).select_related("pago", "pago__usuario")

        admin_app_total = (
            admin_app_qs.aggregate(total=Sum("monto_aplicado"))["total"] or Decimal("0")
        )

        admin_app_resumen = admin_app_qs.values("pago__usuario").annotate(
            total=Sum("monto_aplicado"),
            movimientos=Count("id"),
            ultima_fecha=Max("pago__fecha"),
        )

        admin_app_participantes = admin_app_resumen.count()
        admin_app_promedio = (
            (admin_app_total / Decimal(admin_app_participantes))
            if admin_app_participantes > 0
            else Decimal("0")
        )

        # Para mostrar nombres sin consultas extra por fila
        usuarios_lookup = {
            u.id: u for u in Usuario.objects.filter(tipo_usuario="asociado")
        }

        admin_app_data = []
        for row in admin_app_resumen:
            uid = row["pago__usuario"]
            uobj = usuarios_lookup.get(uid)
            nombre = (
                f"{uobj.first_name} {uobj.last_name}".strip()
                if uobj else str(uid)
            )
            admin_app_data.append({
                "usuario": nombre,
                "usuario_id": uid,
                "total": row["total"] or Decimal("0"),
                "movimientos": row["movimientos"] or 0,
                "ultima_fecha": row["ultima_fecha"],
            })

        # ============================================================
        # Construcción de tabla principal
        # ============================================================
        usuarios_data = []

        for usuario in Usuario.objects.filter(tipo_usuario="asociado"):
            primer_aporte = Aporte.objects.filter(usuario=usuario, fecha_aporte__year=año_actual).aggregate(fecha=Min("fecha_aporte"))["fecha"]
            total_aportes = Aporte.objects.filter(usuario=usuario, fecha_aporte__year=año_actual).aggregate(total=Sum("monto"))["total"] or Decimal("0")
            ultimo_aporte = Aporte.objects.filter(usuario=usuario, fecha_aporte__year=año_actual).aggregate(fecha=Max("fecha_aporte"))["fecha"]

            intereses_pagados = (
                PagoAplicacion.objects.filter(
                    prestamo__usuario=usuario,
                    pago__validado=True,
                    cuota__fecha_vencimiento__year=año_actual,
                ).aggregate(total=Sum("interes"))["total"] or Decimal("0")
            )

            capital_pendiente = sum(
                p.capital_pendiente
                for p in Prestamo.objects.filter(usuario=usuario, fecha_desembolso__year=año_actual)
            )

            participacion = (total_aportes / total_aportes_general * 100) if total_aportes_general > 0 else 0
            dias_vinculacion = (hoy - primer_aporte).days if primer_aporte else 0

            intereses_ganados = Decimal("0")
            if total_aportes > 0 and total_intereses_general > 0 and primer_aporte:
                intereses_ganados = (
                    total_intereses_general
                    * (total_aportes / total_aportes_general)
                    * (Decimal(dias_vinculacion) / Decimal(dias_fondo))
                )

            rentabilidad = (intereses_ganados / total_aportes * 100) if total_aportes > 0 else 0
            moroso = ultimo_aporte < fecha_ultimo_aporte_general if fecha_ultimo_aporte_general and ultimo_aporte else False

            pago_admin = intereses_ganados * Decimal("0.10")
            intereses_neto = intereses_ganados - pago_admin
            total_pagar = total_aportes + intereses_neto

            # ============================================================
            # ✅ NUEVO: valores para columnas adicionales en dashboard
            # ============================================================
            total_aportes_viaje = aportes_viaje_map.get(usuario.id, Decimal("0"))

            recaudo_actividad = (
                reparto_actividad_por_persona
                if usuario.id in participantes_actividad_ids
                else Decimal("0")
            )

            usuarios_data.append({
                "nombre": f"{usuario.first_name} {usuario.last_name}".strip(),
                "email": usuario.email,
                "estado_usuario": "Activo" if usuario.is_active else "Inactivo",
                "fecha_ingreso": primer_aporte,

                "total_aportes": total_aportes,
                "total_aportes_viaje": total_aportes_viaje,

                "intereses_pagados": intereses_pagados,
                "capital_pendiente": capital_pendiente,
                "participacion": participacion,
                "dias_vinculacion": dias_vinculacion,

                "intereses_ganados": intereses_ganados,
                "recaudo_actividad": recaudo_actividad,

                "rentabilidad": rentabilidad,
                "ultimo_aporte": ultimo_aporte,
                "estado_mora": "Moroso" if moroso else "Al día",

                "pago_admin": pago_admin,
                "intereses_neto": intereses_neto,
                "total_pagar": total_pagar,
            })

        total_intereses_pagados_terceros = PagoAplicacion.objects.filter(
            prestamo__usuario__tipo_usuario="tercero",
            pago__validado=True,
            cuota__fecha_vencimiento__year=año_actual,
        ).aggregate(total=Sum("interes"))["total"] or Decimal("0")

        capital_pendiente_terceros = sum(
            p.capital_pendiente
            for p in Prestamo.objects.filter(usuario__tipo_usuario="tercero", fecha_desembolso__year=año_actual)
        )

        if total_intereses_pagados_terceros > 0 or capital_pendiente_terceros > 0:
            usuarios_data.append({
                "nombre": "Terceros",
                "email": "-",
                "estado_usuario": "-",
                "fecha_ingreso": None,

                "total_aportes": Decimal("0"),
                "total_aportes_viaje": Decimal("0"),

                "intereses_pagados": total_intereses_pagados_terceros,
                "capital_pendiente": capital_pendiente_terceros,
                "participacion": 0,
                "dias_vinculacion": 0,

                "intereses_ganados": Decimal("0"),
                "recaudo_actividad": Decimal("0"),

                "rentabilidad": 0,
                "ultimo_aporte": None,
                "estado_mora": "-",

                "pago_admin": Decimal("0"),
                "intereses_neto": Decimal("0"),
                "total_pagar": Decimal("0"),
            })

        totales = {
            "total_aportes": sum(u["total_aportes"] for u in usuarios_data),
            "total_aportes_viaje": sum(u.get("total_aportes_viaje", 0) for u in usuarios_data),

            "intereses_pagados": sum(u["intereses_pagados"] for u in usuarios_data),
            "capital_pendiente": sum(u["capital_pendiente"] for u in usuarios_data),

            "intereses_ganados": sum(u["intereses_ganados"] for u in usuarios_data),

            # Total recaudado (actividad) - se reparte completo, así que total recaudado = total asignado
            "total_recaudo_actividad": total_recaudo_actividad,

            "pago_admin": sum(u["pago_admin"] for u in usuarios_data),
            "intereses_neto": sum(u["intereses_neto"] for u in usuarios_data),
            "total_pagar": sum(u["total_pagar"] for u in usuarios_data),

            # Administración APP (recaudo real)
            "admin_app_total": admin_app_total,
        }

        total_en_fondo = totales["total_aportes"] + totales["intereses_ganados"] - totales["capital_pendiente"]
        balance, _ = FondoBalance.objects.get_or_create(año=año_actual)

        primer_aporte_global = Aporte.objects.aggregate(fecha=Min("fecha_aporte"))["fecha"]
        primer_prestamo = Prestamo.objects.aggregate(fecha=Min("fecha_desembolso"))["fecha"]

        año_min = min(
            año_actual,
            primer_aporte_global.year if primer_aporte_global else año_actual,
            primer_prestamo.year if primer_prestamo else año_actual,
        )
        años_disponibles = list(range(año_min, timezone.now().year + 1))

        context.update({
            "usuarios_data": usuarios_data,
            "año_actual": año_actual,
            "totales": totales,
            "años_disponibles": años_disponibles,
            "total_en_fondo": total_en_fondo,
            "balance": balance,

            # ✅ NUEVO: datos para template
            "total_recaudo_actividad": total_recaudo_actividad,
            "cantidad_participantes_actividad": cantidad_participantes_actividad,
            "reparto_actividad_por_persona": reparto_actividad_por_persona,

            "admin_app_data": admin_app_data,
            "admin_app_total": admin_app_total,
            "admin_app_participantes": admin_app_participantes,
            "admin_app_promedio": admin_app_promedio,
        })
        return context

    def post(self, request, *args, **kwargs):
        año_actual = request.GET.get("year")
        try:
            año_actual = int(año_actual)
        except (TypeError, ValueError):
            año_actual = timezone.now().year

        balance, _ = FondoBalance.objects.get_or_create(año=año_actual)
        balance.nequi = request.POST.get("nequi") or 0
        balance.efectivo = request.POST.get("efectivo") or 0
        balance.daviplata = request.POST.get("daviplata") or 0
        balance.comentarios = request.POST.get("comentarios")
        balance.save()

        return redirect(f"{request.path}?year={año_actual}")


# ================================================================
# 📄 Función para generar PDF de entrega de fondo
# ================================================================
def entregar_fondo_pdf(request):
    año_actual = request.GET.get("year")
    try:
        año_actual = int(año_actual)
    except (TypeError, ValueError):
        año_actual = timezone.now().year

    hoy = timezone.now().date()

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="entrega_fondo_{año_actual}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    logo_path = os.path.join(settings.BASE_DIR, "static/images/logo.png")

    total_aportes_general = (
        Aporte.objects.filter(fecha_aporte__year=año_actual)
        .aggregate(total=Sum("monto"))["total"] or Decimal("0")
    )

    total_intereses_general = (
        PagoAplicacion.objects.filter(
            tipo="prestamo",
            cuota__fecha_vencimiento__year=año_actual,
            pago__validado=True,
        ).aggregate(total=Sum("interes"))["total"] or Decimal("0")
    )

    fecha_inicio_fondo = (
        Aporte.objects.filter(fecha_aporte__year=año_actual)
        .aggregate(fecha=Min("fecha_aporte"))["fecha"] or hoy
    )
    dias_fondo = max((hoy - fecha_inicio_fondo).days, 1)

    usuarios = Usuario.objects.filter(tipo_usuario="asociado")

    for usuario in usuarios:
        total_aportes = (
            Aporte.objects.filter(usuario=usuario, fecha_aporte__year=año_actual)
            .aggregate(total=Sum("monto"))["total"] or Decimal("0")
        )
        primer_aporte = (
            Aporte.objects.filter(usuario=usuario, fecha_aporte__year=año_actual)
            .aggregate(fecha=Min("fecha_aporte"))["fecha"]
        )
        dias_vinculacion = (hoy - primer_aporte).days if primer_aporte else 0

        intereses_ganados = Decimal("0")
        if total_aportes > 0 and total_intereses_general > 0 and primer_aporte:
            intereses_ganados = (
                total_intereses_general
                * (total_aportes / total_aportes_general)
                * (Decimal(dias_vinculacion) / Decimal(dias_fondo))
            )

        pago_admin = intereses_ganados * Decimal("0.10")
        intereses_neto = intereses_ganados - pago_admin
        total_pagar = total_aportes + intereses_neto

        if total_aportes > 0:
            if os.path.exists(logo_path):
                logo = Image(logo_path, width=200, height=100)
                logo.hAlign = "CENTER"
                elements.append(logo)
                elements.append(Spacer(1, 20))

            titulo = Paragraph("<para align='center'><b><font size=16>Entrega de Fondo</font></b></para>", styles["Normal"])
            elements.append(titulo)
            elements.append(Spacer(1, 20))

            datos_socio = [
                ["Socio", f"{usuario.first_name} {usuario.last_name}"],
                ["Correo", usuario.email or "-"],
                ["Fecha", hoy.strftime("%d/%m/%Y")],
            ]
            tabla_socio = Table(datos_socio, colWidths=[100, 350])
            tabla_socio.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            elements.append(tabla_socio)
            elements.append(Spacer(1, 20))

            datos_totales = [
                ["Concepto", "Valor"],
                ["Total Aportes", f"${total_aportes:,.0f}".replace(",", ".")],
                ["Intereses a Pagar", f"${intereses_neto:,.0f}".replace(",", ".")],
                ["Total a Pagar", f"${total_pagar:,.0f}".replace(",", ".")],
            ]
            tabla_totales = Table(datos_totales, colWidths=[200, 200])
            tabla_totales.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.black),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 12),
                ("ALIGN", (1, 1), (1, -2), "RIGHT"),
                ("FONTNAME", (0, 1), (-1, -2), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -2), 11),
                ("BACKGROUND", (0, -1), (-1, -1), colors.black),
                ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, -1), (-1, -1), 14),
                ("ALIGN", (1, -1), (1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            elements.append(tabla_totales)
            elements.append(Spacer(1, 40))
            elements.append(Paragraph("__________________________________", styles["Normal"]))
            elements.append(Paragraph("Firma del Socio", styles["Normal"]))
            elements.append(PageBreak())

    doc.build(elements)
    return response
