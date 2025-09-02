from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from fonar.models import Aporte, Usuario
from dashboard.forms import AporteForm

@login_required
def aporte_list(request):
    aportes = Aporte.objects.all().order_by('-fecha_aporte')
    usuarios = Usuario.objects.all()

    # 🔹 Filtros
    usuario_id = request.GET.get('usuario')
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')

    if usuario_id and usuario_id.isdigit():
        aportes = aportes.filter(usuario_id=usuario_id)
    if fecha_inicio:
        aportes = aportes.filter(fecha_aporte__gte=fecha_inicio)
    if fecha_fin:
        aportes = aportes.filter(fecha_aporte__lte=fecha_fin)

    context = {
        'aportes': aportes,
        'usuarios': usuarios,
        'usuario_id': usuario_id,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
    }
    return render(request, 'dashboard/aportes/list.html', context)


@login_required
def aporte_create(request):
    if request.method == 'POST':
        form = AporteForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('dashboard:aporte_list')
    else:
        form = AporteForm()
    return render(request, 'dashboard/aportes/form.html', {'form': form})


@login_required
def aporte_update(request, pk):
    aporte = get_object_or_404(Aporte, pk=pk)
    if request.method == 'POST':
        form = AporteForm(request.POST, request.FILES, instance=aporte)
        if form.is_valid():
            form.save()
            return redirect('dashboard:aporte_list')
    else:
        form = AporteForm(instance=aporte)
    return render(request, 'dashboard/aportes/form.html', {'form': form, 'aporte': aporte})


@login_required
def aporte_delete(request, pk):
    aporte = get_object_or_404(Aporte, pk=pk)
    if request.method == 'POST':
        aporte.delete()
        return redirect('dashboard:aporte_list')
    return render(request, 'dashboard/aportes/confirm_delete.html', {'aporte': aporte})


@login_required
def aporte_detail(request, pk):
    aporte = get_object_or_404(Aporte, pk=pk)
    return render(request, 'dashboard/aportes/detail.html', {'aporte': aporte})
