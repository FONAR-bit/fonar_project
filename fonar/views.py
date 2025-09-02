from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from decimal import Decimal, ROUND_HALF_UP
from .models import Aporte, Prestamo, Pago, CuotaPrestamo, PagoAplicacion, SolicitudPrestamo, TasaInteres
from .forms import PagoForm, SolicitudPrestamoForm
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import logout
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from django.conf import settings
import os
from django.views.decorators.http import require_GET
from .models import SolicitudPrestamo


# Página de inicio con KPIs
@login_required
def inicio(request):
    usuario = request.user

    total_aportes = Aporte.objects.filter(usuario=usuario).aggregate(
        total=Sum('monto')
    )['total'] or Decimal('0')

    prestamos = Prestamo.objects.filter(usuario=usuario)
    total_prestamos = Decimal('0')

    for prestamo in prestamos:
        cuotas = CuotaPrestamo.objects.filter(prestamo=prestamo)
        capital_pendiente = cuotas.aggregate(
            total=Sum('capital')
        )['total'] or Decimal('0')

        capital_pagado = PagoAplicacion.objects.filter(
            prestamo=prestamo,
            pago__validado=True
        ).aggregate(
            total=Sum('capital')
        )['total'] or Decimal('0')

        saldo_capital = capital_pendiente - capital_pagado
        total_prestamos += saldo_capital

    diferencia = total_aportes - total_prestamos

    return render(request, 'fonar/inicio.html', {
        'total_aportes': total_aportes,
        'total_prestamos': total_prestamos,
        'diferencia': diferencia,
    })


@login_required
def ver_aportes(request):
    aportes = Aporte.objects.filter(usuario=request.user).order_by('-fecha_aporte')
    return render(request, 'fonar/ver_aportes.html', {'aportes': aportes})


@login_required
def ver_prestamos(request):
    prestamos = Prestamo.objects.filter(usuario=request.user)

    prestamos_data = []
    for prestamo in prestamos:
        cuotas = CuotaPrestamo.objects.filter(prestamo=prestamo).order_by("numero")
        aplicaciones = PagoAplicacion.objects.filter(
            prestamo=prestamo,
            pago__validado=True
        )

        total_pagado = aplicaciones.aggregate(Sum('monto_aplicado'))['monto_aplicado__sum'] or Decimal('0')
        total_pagado = total_pagado.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        saldo_pendiente = (prestamo.monto_total - total_pagado).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

        pagos = (
            aplicaciones
            .values("pago_id", "pago__fecha")
            .annotate(monto_pagado=Sum("monto_aplicado"))
            .order_by("-pago__fecha")
        )

        pagos_info = [
            {
                "monto_pagado": p["monto_pagado"].quantize(Decimal("1"), rounding=ROUND_HALF_UP),
                "fecha_pago": p["pago__fecha"]
            }
            for p in pagos
        ]

        prestamos_data.append({
            "prestamo": prestamo,
            "cuotas": cuotas,
            "pagos": pagos_info,
            "total_pagado": total_pagado,
            "saldo_pendiente": saldo_pendiente,
        })

    return render(request, 'fonar/mis_prestamos.html', {"prestamos_data": prestamos_data})


@login_required
def detalle_prestamo(request, prestamo_id):
    prestamo = get_object_or_404(Prestamo, id=prestamo_id, usuario=request.user)

    pagos = Pago.objects.filter(
        usuario=request.user,
        aplicaciones__prestamo=prestamo
    ).distinct()

    total_pagado = sum(p.monto_reportado for p in pagos)
    saldo_pendiente = prestamo.monto_total - total_pagado

    return render(request, 'fonar/detalle_prestamo.html', {
        'prestamo': prestamo,
        'pagos': pagos,
        'total_pagado': total_pagado,
        'saldo_pendiente': saldo_pendiente,
    })


@login_required
def subir_pago(request):
    if request.method == 'POST':
        form = PagoForm(request.POST, request.FILES)
        if form.is_valid():
            pago = form.save(commit=False)
            pago.usuario = request.user
            pago.save()
            return redirect('mis_pagos')
    else:
        form = PagoForm()
    return render(request, 'fonar/subir_pago.html', {'form': form})


@login_required
def mis_pagos(request):
    pagos = Pago.objects.filter(usuario=request.user).order_by('-fecha')
    return render(request, 'fonar/mis_pagos.html', {'pagos': pagos})


def cuotas_pendientes(request, prestamo_id):
    cuotas = CuotaPrestamo.objects.filter(prestamo_id=prestamo_id, pagada=False)
    data = [
        {"id": c.id, "texto": f"Cuota {c.numero} - Vence {c.fecha_vencimiento} - ${c.monto_cuota}"}
        for c in cuotas
    ]
    return JsonResponse(data, safe=False)


def custom_logout(request):
    logout(request)
    messages.success(request, "Sesión cerrada correctamente.")
    return redirect('login')


def pago_pdf(request, pago_id):
    pago = get_object_or_404(Pago, id=pago_id, usuario=request.user)

    if not pago.validado:
        return HttpResponse("Este pago aún no está validado.", status=403)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="pago_{pago.id}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    logo_path = os.path.join(settings.BASE_DIR, "static/images/logo.png")
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=200, height=100)
        logo.hAlign = "CENTER"
        elements.append(logo)
        elements.append(Spacer(1, 20))

        titulo = Paragraph(
            "<para align='center'><b><font size=16>Comprobante de Pago</font></b></para>",
            styles["Normal"]
        )
        subtitulo = Paragraph(
            "<para align='center'><font size=12>----------------------------------------------</font></para>",
            styles["Normal"]
        )
        elements.append(titulo)
        elements.append(subtitulo)
        elements.append(Spacer(1, 20))

    elements.append(Spacer(1, 12))
    elements.append(Spacer(1, 20))

    datos_pago = [
        ["Recibo N°", f"{pago.id}"],
        ["Fecha", pago.fecha.strftime("%d/%m/%Y")],
        ["Usuario", pago.usuario.get_full_name() or pago.usuario.username],
        ["Monto Reportado", f"${pago.monto_reportado:,.0f}"],
        ["Estado", "VALIDADO"]
    ]
    tabla_info = Table(datos_pago, colWidths=[100, 350])
    tabla_info.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(tabla_info)
    elements.append(Spacer(1, 20))

    data = [["Tipo", "Cuota", "Capital", "Interés", "Monto Aplicado"]]
    for linea in pago.aplicaciones.all():
        data.append([
            linea.tipo,
            str(linea.cuota) if linea.cuota else "-",
            f"${linea.capital:,.0f}",
            f"${linea.interes:,.0f}",
            f"${linea.monto_aplicado:,.0f}",
        ])

    tabla_detalle = Table(data, colWidths=[70, 150, 80, 80, 100])
    tabla_detalle.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(Paragraph("<b>Detalle de Aplicaciones</b>", styles["Heading3"]))
    elements.append(tabla_detalle)
    elements.append(Spacer(1, 30))

    elements.append(Paragraph(
        "Este comprobante certifica el registro del pago en el sistema <b>FONAR</b>.",
        styles["Italic"]
    ))
    elements.append(Spacer(1, 40))
    elements.append(Paragraph("__________________________________", styles["Normal"]))
    elements.append(Paragraph("Firma Responsable", styles["Normal"]))

    doc.build(elements)
    return response


# ============================
# NUEVAS VISTAS PARA CRÉDITOS
# ============================

@login_required
def solicitar_prestamo(request):
    if request.method == "POST":
        form = SolicitudPrestamoForm(request.user, request.POST)
        if form.is_valid():
            solicitud = form.save()
            messages.success(request, "✅ Tu solicitud fue enviada y está pendiente de aprobación.")
            return redirect("ver_prestamos")
    else:
        form = SolicitudPrestamoForm(request.user)

    return render(request, "fonar/solicitar_prestamo.html", {"form": form})


@login_required
@require_GET
def obtener_tasa(request):
    try:
        cuotas = int(request.GET.get("cuotas"))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Número de cuotas inválido"}, status=400)

    usuario = request.user

    tasa = (
        TasaInteres.objects.filter(
            tipo_usuario=usuario.tipo_usuario,
            cuotas_min__lte=cuotas,
            cuotas_max__gte=cuotas
        )
        .order_by("-vigente_desde")
        .first()
    )

    if not tasa:
        return JsonResponse({"error": "No hay tasa configurada para este rango de cuotas"}, status=404)

    return JsonResponse({"tasa": float(tasa.interes_mensual)})

def mis_solicitudes(request):
    solicitudes = SolicitudPrestamo.objects.filter(usuario=request.user).order_by("-fecha_solicitud")
    return render(request, "fonar/mis_solicitudes.html", {"solicitudes": solicitudes})
