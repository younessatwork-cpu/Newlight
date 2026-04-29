from __future__ import annotations

import base64
import io
import json
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import transaction
from django.db.models import Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .auth_utils import (
    authenticate,
    current_user,
    is_admin,
    is_technician,
    login_required,
    login_session,
    logout_session,
    roles_required,
    sha256_password,
)
from .models import (
    PHASES,
    Client,
    Expense,
    Inventory,
    InventoryLog,
    LaborLog,
    Payment,
    Progress,
    SitePhoto,
    SystemUser,
    Worker,
)

PHASE_NAMES = [p[0] for p in PHASES]


def D(value, default='0') -> Decimal:
    try:
        if value in (None, ''):
            return Decimal(default)
        return Decimal(str(value).replace(',', '.'))
    except (InvalidOperation, ValueError):
        return Decimal(default)


def I(value, default=0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(float(value))
    except (ValueError, TypeError):
        return default


def safe_date(value):
    if not value:
        return timezone.localdate()
    try:
        return date.fromisoformat(value)
    except ValueError:
        return timezone.localdate()


def metric_totals():
    labour = LaborLog.objects.aggregate(total=Sum('cost'))['total'] or Decimal('0')
    materials = Expense.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    collected = Client.objects.aggregate(total=Sum('advance'))['total'] or Decimal('0')
    contracts = Client.objects.aggregate(total=Sum('budget'))['total'] or Decimal('0')
    total_cost = labour + materials
    return {
        'labour': labour,
        'materials': materials,
        'collected': collected,
        'contracts': contracts,
        'total_cost': total_cost,
        'profit': collected - total_cost,
        'margin_pct': ((collected - total_cost) / collected * 100) if collected > 0 else Decimal('0'),
    }


def site_costs(client_name):
    labour = LaborLog.objects.filter(client_name=client_name).aggregate(total=Sum('cost'))['total'] or Decimal('0')
    materials = Expense.objects.filter(client_name=client_name).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    return labour, materials, labour + materials


def get_progress(client_name):
    progress, _ = Progress.objects.get_or_create(client_name=client_name)
    return progress


def client_outstanding(client: Client, excluding_payment: Payment | None = None) -> Decimal:
    paid = client.advance
    if excluding_payment:
        paid -= excluding_payment.amount
    return max(Decimal('0'), client.budget - paid)


def apply_payment(client: Client, amount: Decimal, method: str, notes: str, payment_date: date):
    outstanding = client_outstanding(client)
    if amount <= 0:
        raise ValueError('Payment amount must be positive.')
    if amount > outstanding:
        raise ValueError('Payment cannot exceed outstanding balance.')
    Payment.objects.create(date=payment_date, client_name=client.client_name, amount=amount, method=method, notes=notes)
    client.advance = client.advance + amount
    client.save(update_fields=['advance'])


def require_admin_post(request):
    if not is_admin(request):
        messages.error(request, 'Admin permission required.')
        return False
    return True


def recalc_labor_cost(worker_name: str, days: Decimal) -> Decimal:
    worker = Worker.objects.filter(name=worker_name).first()
    if not worker:
        return Decimal('0')
    return days * worker.tjm


def adjust_inventory_stock(item_name: str, amount: Decimal, direction: str, reverse: bool = False):
    item = Inventory.objects.filter(item_name=item_name).first()
    if not item:
        return
    sign = Decimal('1') if direction == 'IN' else Decimal('-1')
    if reverse:
        sign *= Decimal('-1')
    new_qty = item.quantity + (amount * sign)
    if new_qty < 0:
        raise ValueError('Inventory check-out cannot exceed stock.')
    item.quantity = new_qty
    item.save(update_fields=['quantity'])


def nav_redirect_for_user(request):
    user = current_user(request)
    if not user:
        return redirect('login')
    if user.get('role') == 'Client':
        return redirect('vip_portal')
    return redirect('dashboard')


def home(request):
    return nav_redirect_for_user(request)


def login_view(request):
    if current_user(request):
        return nav_redirect_for_user(request)
    if request.method == 'POST':
        user = authenticate(request.POST.get('username', '').strip(), request.POST.get('password', ''))
        if user:
            login_session(request, user)
            return nav_redirect_for_user(request)
        messages.error(request, 'Invalid username or password.')
    return render(request, 'ops/login.html')


def logout_view(request):
    logout_session(request)
    return redirect('login')


@login_required
@roles_required('Admin', 'Technician')
def dashboard(request):
    totals = metric_totals()
    rows = []
    for c in Client.objects.all():
        labour, materials, total_cost = site_costs(c.client_name)
        progress = get_progress(c.client_name)
        rows.append({
            'client': c,
            'labour': labour,
            'materials': materials,
            'total_cost': total_cost,
            'profit': c.advance - total_cost,
            'progress': progress.average,
        })
    recent = []
    for log in LaborLog.objects.all()[:5]:
        recent.append({'date': log.date, 'type': 'Labour', 'text': f'{log.worker_name} · {log.client_name}', 'amount': log.cost})
    for exp in Expense.objects.all()[:5]:
        recent.append({'date': exp.date, 'type': 'Material', 'text': f'{exp.item} · {exp.client_name}', 'amount': exp.amount})
    for p in Payment.objects.all()[:5]:
        recent.append({'date': p.date, 'type': 'Payment', 'text': f'{p.client_name} · {p.method}', 'amount': p.amount})
    recent = sorted(recent, key=lambda x: x['date'], reverse=True)[:10]
    spend_by_phase = {phase: Expense.objects.filter(phase=phase).aggregate(total=Sum('amount'))['total'] or Decimal('0') for phase in PHASE_NAMES}
    return render(request, 'ops/dashboard.html', {'totals': totals, 'rows': rows, 'recent': recent, 'spend_by_phase': spend_by_phase})


@login_required
@roles_required('Admin')
def estimator(request):
    total_historical_cost = (LaborLog.objects.aggregate(total=Sum('cost'))['total'] or Decimal('0')) + (Expense.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0'))
    total_historical_points = Client.objects.aggregate(total=Sum('total_points'))['total'] or 0
    cost_per_point = (total_historical_cost / Decimal(total_historical_points)) if total_historical_points else Decimal('0')
    result = None
    if request.method == 'POST':
        points = I(request.POST.get('points'))
        surface = D(request.POST.get('surface'))
        margin = D(request.POST.get('margin'))
        project_name = request.POST.get('project_name', '').strip()
        work_types = request.POST.getlist('work_types')
        if margin >= 100:
            messages.error(request, 'Margin must be below 100%.')
        else:
            base_cost = Decimal(points) * cost_per_point
            quote = base_cost / (Decimal('1') - (margin / Decimal('100'))) if margin < 100 else Decimal('0')
            result = {
                'project_name': project_name,
                'points': points,
                'surface': surface,
                'margin': margin,
                'work_types': ', '.join(work_types),
                'cost_per_point': cost_per_point,
                'base_cost': base_cost,
                'quote': quote,
            }
    historical = []
    for c in Client.objects.all():
        _, _, total_cost = site_costs(c.client_name)
        historical.append({'client': c, 'total_cost': total_cost, 'cpp': (total_cost / Decimal(c.total_points)) if c.total_points else Decimal('0')})
    return render(request, 'ops/estimator.html', {'cost_per_point': cost_per_point, 'total_historical_cost': total_historical_cost, 'total_historical_points': total_historical_points, 'result': result, 'historical': historical})


@login_required
@roles_required('Admin')
def estimator_pdf(request):
    project = request.GET.get('project', 'New project')
    points = D(request.GET.get('points'))
    margin = D(request.GET.get('margin'))
    quote = D(request.GET.get('quote'))
    base = D(request.GET.get('base'))
    rows = [
        ['Project', project],
        ['Points', f'{points:.0f}'],
        ['Margin', f'{margin:.2f}%'],
        ['Base cost', f'{base:,.2f} MAD'],
        ['Recommended quote', f'{quote:,.2f} MAD'],
    ]
    return build_pdf('Newlightemara Quote', rows, filename='newlightemara_quote.pdf')


@login_required
@roles_required('Admin')
def clients(request):
    if request.method == 'POST' and require_admin_post(request):
        action = request.POST.get('action')
        try:
            with transaction.atomic():
                if action == 'add':
                    client = Client.objects.create(
                        client_name=request.POST.get('client_name', '').strip(),
                        work_type=request.POST.get('work_type', '').strip(),
                        budget=D(request.POST.get('budget')),
                        advance=D(request.POST.get('advance')),
                        total_points=I(request.POST.get('total_points')),
                        status=request.POST.get('status', 'active'),
                    )
                    Progress.objects.get_or_create(client_name=client.client_name)
                    messages.success(request, 'Client portfolio created.')
                elif action == 'edit':
                    client = get_object_or_404(Client, pk=request.POST.get('id'))
                    old_name = client.client_name
                    new_name = request.POST.get('client_name', '').strip()
                    client.client_name = new_name
                    client.work_type = request.POST.get('work_type', '').strip()
                    client.budget = D(request.POST.get('budget'))
                    client.advance = D(request.POST.get('advance'))
                    client.total_points = I(request.POST.get('total_points'))
                    client.status = request.POST.get('status', 'active')
                    client.save()
                    if old_name != new_name:
                        LaborLog.objects.filter(client_name=old_name).update(client_name=new_name)
                        Expense.objects.filter(client_name=old_name).update(client_name=new_name)
                        SitePhoto.objects.filter(client_name=old_name).update(client_name=new_name)
                        Payment.objects.filter(client_name=old_name).update(client_name=new_name)
                        InventoryLog.objects.filter(site_allocated=old_name).update(site_allocated=new_name)
                        Progress.objects.filter(client_name=old_name).update(client_name=new_name)
                        SystemUser.objects.filter(reference=old_name, role='Client').update(reference=new_name)
                    Progress.objects.get_or_create(client_name=new_name)
                    messages.success(request, 'Client portfolio updated.')
                elif action == 'delete':
                    client = get_object_or_404(Client, pk=request.POST.get('id'))
                    name = client.client_name
                    LaborLog.objects.filter(client_name=name).delete()
                    Expense.objects.filter(client_name=name).delete()
                    SitePhoto.objects.filter(client_name=name).delete()
                    Payment.objects.filter(client_name=name).delete()
                    InventoryLog.objects.filter(site_allocated=name).delete()
                    Progress.objects.filter(client_name=name).delete()
                    client.delete()
                    messages.success(request, 'Client portfolio and related site data deleted.')
                elif action == 'complete':
                    client = get_object_or_404(Client, pk=request.POST.get('id'))
                    client.status = 'completed'
                    client.save(update_fields=['status'])
                    messages.success(request, 'Site marked completed.')
                elif action == 'payment':
                    client = get_object_or_404(Client, pk=request.POST.get('client_id'))
                    apply_payment(client, D(request.POST.get('amount')), request.POST.get('method', ''), request.POST.get('notes', ''), safe_date(request.POST.get('date')))
                    request.session['rain_money'] = True
                    messages.success(request, 'Payment received and client advance updated.')
        except ValueError as exc:
            messages.error(request, str(exc))
    rows = []
    for c in Client.objects.all():
        labour, materials, total_cost = site_costs(c.client_name)
        rows.append({'client': c, 'labour': labour, 'materials': materials, 'total_cost': total_cost, 'outstanding': max(Decimal('0'), c.budget - c.advance)})
    return render(request, 'ops/clients.html', {'rows': rows, 'phases': PHASE_NAMES})


@login_required
@roles_required('Admin', 'Technician')
def timesheets(request):
    user = current_user(request)
    technician = is_technician(request)
    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            with transaction.atomic():
                if action == 'add':
                    worker_name = request.POST.get('worker_name')
                    if technician:
                        worker_name = user.get('reference')
                    days = D(request.POST.get('days'))
                    LaborLog.objects.create(
                        date=safe_date(request.POST.get('date')),
                        client_name=request.POST.get('client_name'),
                        worker_name=worker_name,
                        days=days,
                        cost=recalc_labor_cost(worker_name, days),
                        phase=request.POST.get('phase'),
                    )
                    messages.success(request, 'Labour log saved.')
                elif action in ('edit', 'delete'):
                    log = get_object_or_404(LaborLog, pk=request.POST.get('id'))
                    if technician and log.worker_name != user.get('reference'):
                        messages.error(request, 'Technicians can only modify their own logs.')
                    elif action == 'delete':
                        log.delete()
                        messages.success(request, 'Labour log deleted.')
                    else:
                        worker_name = request.POST.get('worker_name')
                        if technician:
                            worker_name = user.get('reference')
                        days = D(request.POST.get('days'))
                        log.date = safe_date(request.POST.get('date'))
                        log.client_name = request.POST.get('client_name')
                        log.worker_name = worker_name
                        log.days = days
                        log.cost = recalc_labor_cost(worker_name, days)
                        log.phase = request.POST.get('phase')
                        log.save()
                        messages.success(request, 'Labour log updated.')
        except ValueError as exc:
            messages.error(request, str(exc))
    logs = LaborLog.objects.all()
    if technician:
        logs = logs.filter(worker_name=user.get('reference'))
    return render(request, 'ops/timesheets.html', {'clients': Client.objects.all(), 'workers': Worker.objects.all(), 'logs': logs[:100], 'phases': PHASE_NAMES})


@login_required
@roles_required('Admin')
def payroll(request):
    logs = LaborLog.objects.all()
    worker_filter = request.GET.get('worker', '')
    start = request.GET.get('start')
    end = request.GET.get('end')
    if worker_filter:
        logs = logs.filter(worker_name=worker_filter)
    if start:
        logs = logs.filter(date__gte=safe_date(start))
    if end:
        logs = logs.filter(date__lte=safe_date(end))
    if request.method == 'POST' and require_admin_post(request):
        action = request.POST.get('action')
        log = get_object_or_404(LaborLog, pk=request.POST.get('id'))
        if action == 'delete':
            log.delete()
            messages.success(request, 'Payroll log deleted.')
        elif action == 'edit':
            days = D(request.POST.get('days'))
            worker_name = request.POST.get('worker_name')
            log.date = safe_date(request.POST.get('date'))
            log.client_name = request.POST.get('client_name')
            log.worker_name = worker_name
            log.days = days
            log.cost = recalc_labor_cost(worker_name, days)
            log.phase = request.POST.get('phase')
            log.save()
            messages.success(request, 'Payroll log updated.')
        return redirect(f"{reverse('payroll')}?worker={worker_filter}&start={start or ''}&end={end or ''}")
    summary = logs.values('worker_name').annotate(total_days=Sum('days'), total_cost=Sum('cost')).order_by('worker_name')
    totals = {'days': logs.aggregate(total=Sum('days'))['total'] or Decimal('0'), 'cost': logs.aggregate(total=Sum('cost'))['total'] or Decimal('0')}
    return render(request, 'ops/payroll.html', {'logs': logs, 'summary': summary, 'workers': Worker.objects.all(), 'clients': Client.objects.all(), 'phases': PHASE_NAMES, 'totals': totals, 'filters': {'worker': worker_filter, 'start': start or '', 'end': end or ''}})


@login_required
@roles_required('Admin')
def efficiency(request):
    worker_phase = defaultdict(lambda: defaultdict(Decimal))
    site_phase = defaultdict(lambda: defaultdict(Decimal))
    daily = defaultdict(Decimal)
    for log in LaborLog.objects.all():
        worker_phase[log.worker_name][log.phase] += log.cost
        site_phase[log.client_name][log.phase] += log.cost
        daily[str(log.date)] += log.cost
    chart_labels = sorted(daily.keys())
    chart_values = [float(daily[k]) for k in chart_labels]
    return render(request, 'ops/efficiency.html', {'worker_phase': dict(worker_phase), 'site_phase': dict(site_phase), 'phases': PHASE_NAMES, 'chart_labels': json.dumps(chart_labels), 'chart_values': json.dumps(chart_values)})


@login_required
@roles_required('Admin')
def procurement(request):
    if request.method == 'POST' and require_admin_post(request):
        action = request.POST.get('action')
        if action == 'add':
            Expense.objects.create(date=safe_date(request.POST.get('date')), client_name=request.POST.get('client_name'), item=request.POST.get('item'), amount=D(request.POST.get('amount')), phase=request.POST.get('phase'), supplier=request.POST.get('supplier', ''))
            messages.success(request, 'Expense logged.')
        elif action == 'edit':
            exp = get_object_or_404(Expense, pk=request.POST.get('id'))
            exp.date = safe_date(request.POST.get('date'))
            exp.client_name = request.POST.get('client_name')
            exp.item = request.POST.get('item')
            exp.amount = D(request.POST.get('amount'))
            exp.phase = request.POST.get('phase')
            exp.supplier = request.POST.get('supplier', '')
            exp.save()
            messages.success(request, 'Expense updated.')
        elif action == 'delete':
            get_object_or_404(Expense, pk=request.POST.get('id')).delete()
            messages.success(request, 'Expense deleted.')
    phase_spend = {phase: Expense.objects.filter(phase=phase).aggregate(total=Sum('amount'))['total'] or Decimal('0') for phase in PHASE_NAMES}
    max_spend = max([Decimal('1')] + list(phase_spend.values()))
    phase_progress = {phase: int((value / max_spend) * 100) for phase, value in phase_spend.items()}
    return render(request, 'ops/procurement.html', {'clients': Client.objects.all(), 'expenses': Expense.objects.all(), 'phases': PHASE_NAMES, 'phase_spend': phase_spend, 'phase_progress': phase_progress})


@login_required
@roles_required('Admin')
def milestones(request):
    selected = request.GET.get('client') or (Client.objects.first().client_name if Client.objects.exists() else '')
    if request.method == 'POST' and require_admin_post(request):
        selected = request.POST.get('client_name')
        progress, _ = Progress.objects.get_or_create(client_name=selected)
        progress.phase1 = max(0, min(100, I(request.POST.get('phase1'))))
        progress.phase2 = max(0, min(100, I(request.POST.get('phase2'))))
        progress.phase3 = max(0, min(100, I(request.POST.get('phase3'))))
        progress.phase4 = max(0, min(100, I(request.POST.get('phase4'))))
        progress.save()
        messages.success(request, 'Milestones updated.')
    progress = get_progress(selected) if selected else None
    return render(request, 'ops/milestones.html', {'clients': Client.objects.all(), 'selected': selected, 'progress': progress})


@login_required
@roles_required('Admin', 'Technician')
def photos(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'upload':
            files = request.FILES.getlist('photos')
            for f in files:
                encoded = base64.b64encode(f.read()).decode('utf-8')
                mime = f.content_type or 'image/jpeg'
                SitePhoto.objects.create(client_name=request.POST.get('client_name'), phase=request.POST.get('phase'), photo_data=f'data:{mime};base64,{encoded}', notes=request.POST.get('notes', ''))
            messages.success(request, f'{len(files)} photo(s) uploaded.')
        elif action == 'edit':
            photo = get_object_or_404(SitePhoto, pk=request.POST.get('id'))
            if is_admin(request):
                photo.client_name = request.POST.get('client_name')
                photo.phase = request.POST.get('phase')
            photo.notes = request.POST.get('notes', '')
            photo.save()
            messages.success(request, 'Photo notes updated.')
        elif action == 'delete':
            get_object_or_404(SitePhoto, pk=request.POST.get('id')).delete()
            messages.success(request, 'Photo deleted.')
    photos_qs = SitePhoto.objects.all()
    client_filter = request.GET.get('client', '')
    phase_filter = request.GET.get('phase', '')
    if client_filter:
        photos_qs = photos_qs.filter(client_name=client_filter)
    if phase_filter:
        photos_qs = photos_qs.filter(phase=phase_filter)
    return render(request, 'ops/photos.html', {'clients': Client.objects.all(), 'photos': photos_qs, 'phases': PHASE_NAMES, 'filters': {'client': client_filter, 'phase': phase_filter}})


@login_required
@roles_required('Admin')
def warehouse(request):
    if request.method == 'POST' and require_admin_post(request):
        action = request.POST.get('action')
        try:
            with transaction.atomic():
                if action == 'add_item':
                    Inventory.objects.create(item_name=request.POST.get('item_name'), category=request.POST.get('category', ''), quantity=D(request.POST.get('quantity')), unit=request.POST.get('unit', 'pcs'))
                    messages.success(request, 'Inventory item added.')
                elif action == 'edit_item':
                    item = get_object_or_404(Inventory, pk=request.POST.get('id'))
                    old_name = item.item_name
                    item.item_name = request.POST.get('item_name')
                    item.category = request.POST.get('category', '')
                    item.quantity = D(request.POST.get('quantity'))
                    item.unit = request.POST.get('unit', 'pcs')
                    item.save()
                    if old_name != item.item_name:
                        InventoryLog.objects.filter(item_name=old_name).update(item_name=item.item_name)
                    messages.success(request, 'Inventory item updated.')
                elif action == 'delete_item':
                    item = get_object_or_404(Inventory, pk=request.POST.get('id'))
                    InventoryLog.objects.filter(item_name=item.item_name).delete()
                    item.delete()
                    messages.success(request, 'Inventory item and logs deleted.')
                elif action == 'stock_move':
                    item = get_object_or_404(Inventory, pk=request.POST.get('item_id'))
                    amount = D(request.POST.get('change_amount'))
                    direction = request.POST.get('direction')
                    adjust_inventory_stock(item.item_name, amount, direction)
                    InventoryLog.objects.create(date=safe_date(request.POST.get('date')), item_name=item.item_name, change_amount=amount, direction=direction, site_allocated=request.POST.get('site_allocated', ''), notes=request.POST.get('notes', ''))
                    messages.success(request, 'Inventory movement saved.')
                elif action == 'edit_log':
                    log = get_object_or_404(InventoryLog, pk=request.POST.get('id'))
                    adjust_inventory_stock(log.item_name, log.change_amount, log.direction, reverse=True)
                    new_item = Inventory.objects.filter(item_name=request.POST.get('item_name')).first()
                    if not new_item:
                        raise Http404('Inventory item not found')
                    amount = D(request.POST.get('change_amount'))
                    direction = request.POST.get('direction')
                    adjust_inventory_stock(new_item.item_name, amount, direction)
                    log.date = safe_date(request.POST.get('date'))
                    log.item_name = new_item.item_name
                    log.change_amount = amount
                    log.direction = direction
                    log.site_allocated = request.POST.get('site_allocated', '')
                    log.notes = request.POST.get('notes', '')
                    log.save()
                    messages.success(request, 'Inventory log updated.')
                elif action == 'delete_log':
                    log = get_object_or_404(InventoryLog, pk=request.POST.get('id'))
                    adjust_inventory_stock(log.item_name, log.change_amount, log.direction, reverse=True)
                    log.delete()
                    messages.success(request, 'Inventory log deleted and stock reversed.')
        except ValueError as exc:
            messages.error(request, str(exc))
    low_stock = Inventory.objects.filter(quantity__lte=5)
    return render(request, 'ops/warehouse.html', {'items': Inventory.objects.all(), 'logs': InventoryLog.objects.all()[:150], 'clients': Client.objects.all(), 'low_stock': low_stock})


@login_required
@roles_required('Admin')
def invoicing(request):
    client_id = request.GET.get('client_id') or (Client.objects.first().id if Client.objects.exists() else None)
    client = Client.objects.filter(pk=client_id).first() if client_id else None
    if request.method == 'POST' and require_admin_post(request):
        action = request.POST.get('action')
        try:
            with transaction.atomic():
                if action == 'payment':
                    client = get_object_or_404(Client, pk=request.POST.get('client_id'))
                    apply_payment(client, D(request.POST.get('amount')), request.POST.get('method', ''), request.POST.get('notes', ''), safe_date(request.POST.get('date')))
                    request.session['rain_money'] = True
                    messages.success(request, 'Payment received.')
                    return redirect(f"{reverse('invoicing')}?client_id={client.id}")
                elif action == 'edit_payment':
                    pay = get_object_or_404(Payment, pk=request.POST.get('id'))
                    old_client = Client.objects.filter(client_name=pay.client_name).first()
                    if old_client:
                        old_client.advance -= pay.amount
                        old_client.save(update_fields=['advance'])
                    new_client = Client.objects.filter(client_name=request.POST.get('client_name')).first()
                    if not new_client:
                        raise Http404('Client not found')
                    new_amount = D(request.POST.get('amount'))
                    if new_amount > client_outstanding(new_client):
                        raise ValueError('Payment cannot exceed outstanding balance.')
                    pay.date = safe_date(request.POST.get('date'))
                    pay.client_name = new_client.client_name
                    pay.amount = new_amount
                    pay.method = request.POST.get('method', '')
                    pay.notes = request.POST.get('notes', '')
                    pay.save()
                    new_client.advance += new_amount
                    new_client.save(update_fields=['advance'])
                    messages.success(request, 'Payment updated.')
                    return redirect(f"{reverse('invoicing')}?client_id={new_client.id}")
                elif action == 'delete_payment':
                    pay = get_object_or_404(Payment, pk=request.POST.get('id'))
                    c = Client.objects.filter(client_name=pay.client_name).first()
                    if c:
                        c.advance = max(Decimal('0'), c.advance - pay.amount)
                        c.save(update_fields=['advance'])
                    pay.delete()
                    messages.success(request, 'Payment deleted and client advance adjusted.')
        except ValueError as exc:
            messages.error(request, str(exc))
    labour = LaborLog.objects.filter(client_name=client.client_name) if client else LaborLog.objects.none()
    materials = Expense.objects.filter(client_name=client.client_name) if client else Expense.objects.none()
    payments = Payment.objects.filter(client_name=client.client_name) if client else Payment.objects.none()
    labour_total = labour.aggregate(total=Sum('cost'))['total'] or Decimal('0')
    materials_total = materials.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    paid = client.advance if client else Decimal('0')
    invoice = {'labour_total': labour_total, 'materials_total': materials_total, 'cost_total': labour_total + materials_total, 'paid': paid, 'outstanding': max(Decimal('0'), (client.budget if client else Decimal('0')) - paid)}
    return render(request, 'ops/invoicing.html', {'clients': Client.objects.all(), 'client': client, 'labour': labour, 'materials': materials, 'payments': payments, 'invoice': invoice})


@login_required
@roles_required('Admin')
def invoice_pdf(request, client_id):
    client = get_object_or_404(Client, pk=client_id)
    labour, materials, total_cost = site_costs(client.client_name)
    rows = [
        ['Client', client.client_name],
        ['Work type', client.work_type],
        ['Budget', f'{client.budget:,.2f} MAD'],
        ['Payments collected', f'{client.advance:,.2f} MAD'],
        ['Labour cost', f'{labour:,.2f} MAD'],
        ['Materials cost', f'{materials:,.2f} MAD'],
        ['Total cost', f'{total_cost:,.2f} MAD'],
        ['Outstanding balance', f'{max(Decimal("0"), client.budget - client.advance):,.2f} MAD'],
    ]
    return build_pdf(f'Invoice - {client.client_name}', rows, filename=f'invoice_{client.id}.pdf')


@login_required
@roles_required('Admin')
def dispatch(request):
    message = None
    selected_worker = None
    selected_client = None
    selected_phase = None
    if request.method == 'POST':
        selected_worker = Worker.objects.filter(pk=request.POST.get('worker_id')).first()
        selected_client = Client.objects.filter(pk=request.POST.get('client_id')).first()
        selected_phase = request.POST.get('phase')
        channel = request.POST.get('channel', 'WhatsApp')
        if selected_worker and selected_client:
            message = (
                f"Newlightemara dispatch via {channel}: Bonjour {selected_worker.name}, "
                f"merci d'intervenir sur le chantier {selected_client.client_name} "
                f"pour la phase {selected_phase}. Type de travaux: {selected_client.work_type}."
            )
    worker_cards = []
    for w in Worker.objects.all():
        recent_cost = LaborLog.objects.filter(worker_name=w.name).aggregate(total=Sum('cost'))['total'] or Decimal('0')
        days = LaborLog.objects.filter(worker_name=w.name).aggregate(total=Sum('days'))['total'] or Decimal('0')
        worker_cards.append({'worker': w, 'recent_cost': recent_cost, 'days': days})
    return render(request, 'ops/dispatch.html', {'workers': Worker.objects.all(), 'clients': Client.objects.all(), 'phases': PHASE_NAMES, 'message': message, 'worker_cards': worker_cards})


@login_required
@roles_required('Admin')
def settings_view(request):
    user = current_user(request)
    if request.method == 'POST' and require_admin_post(request):
        action = request.POST.get('action')
        try:
            if action == 'add_user':
                password = request.POST.get('password') or 'ChangeMe2026!'
                SystemUser.objects.create(username=request.POST.get('username').strip(), password_hash=sha256_password(password), role=request.POST.get('role'), reference=request.POST.get('reference', ''))
                messages.success(request, 'User added.')
            elif action == 'edit_user':
                u = get_object_or_404(SystemUser, username=request.POST.get('old_username'))
                new_username = request.POST.get('username').strip()
                if u.username != new_username:
                    if SystemUser.objects.filter(username=new_username).exists():
                        raise ValueError('Username already exists.')
                    SystemUser.objects.create(username=new_username, password_hash=u.password_hash, role=request.POST.get('role'), reference=request.POST.get('reference', ''))
                    u.delete()
                else:
                    u.role = request.POST.get('role')
                    u.reference = request.POST.get('reference', '')
                    u.save()
                messages.success(request, 'User updated.')
            elif action == 'delete_user':
                username = request.POST.get('username')
                if username == user.get('username'):
                    raise ValueError('You cannot delete your own account.')
                SystemUser.objects.filter(username=username).delete()
                messages.success(request, 'User deleted.')
            elif action == 'password_user':
                u = get_object_or_404(SystemUser, username=request.POST.get('username'))
                pwd = request.POST.get('password')
                if not pwd or len(pwd) < 8:
                    raise ValueError('Password must be at least 8 characters.')
                u.password_hash = sha256_password(pwd)
                u.save(update_fields=['password_hash'])
                messages.success(request, 'Password changed.')
            elif action == 'add_worker':
                Worker.objects.create(name=request.POST.get('name'), specialty=request.POST.get('specialty', ''), tjm=D(request.POST.get('tjm')))
                messages.success(request, 'Worker added.')
            elif action == 'edit_worker':
                w = get_object_or_404(Worker, pk=request.POST.get('id'))
                old_name = w.name
                w.name = request.POST.get('name')
                w.specialty = request.POST.get('specialty', '')
                w.tjm = D(request.POST.get('tjm'))
                w.save()
                if old_name != w.name:
                    LaborLog.objects.filter(worker_name=old_name).update(worker_name=w.name)
                    SystemUser.objects.filter(reference=old_name, role='Technician').update(reference=w.name)
                messages.success(request, 'Worker updated.')
            elif action == 'delete_worker':
                w = get_object_or_404(Worker, pk=request.POST.get('id'))
                LaborLog.objects.filter(worker_name=w.name).delete()
                SystemUser.objects.filter(reference=w.name, role='Technician').update(reference='')
                w.delete()
                messages.success(request, 'Worker deleted.')
        except ValueError as exc:
            messages.error(request, str(exc))
    return render(request, 'ops/settings.html', {'users': SystemUser.objects.all().order_by('username'), 'workers': Worker.objects.all(), 'clients': Client.objects.all()})


@login_required
@roles_required('Client')
def vip_portal(request):
    user = current_user(request)
    client = Client.objects.filter(client_name=user.get('reference')).first()
    if not client:
        return render(request, 'ops/vip.html', {'client': None})
    progress = get_progress(client.client_name)
    labour = LaborLog.objects.filter(client_name=client.client_name).order_by('-date')[:5]
    expenses = Expense.objects.filter(client_name=client.client_name).order_by('-date')[:5]
    payments = Payment.objects.filter(client_name=client.client_name).order_by('-date')[:5]
    photos = SitePhoto.objects.filter(client_name=client.client_name)[:12]
    _, _, total_cost = site_costs(client.client_name)
    return render(request, 'ops/vip.html', {'client': client, 'progress': progress, 'labour': labour, 'expenses': expenses, 'payments': payments, 'photos': photos, 'total_cost': total_cost})


def build_pdf(title, rows, filename='document.pdf'):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5 * cm, leftMargin=1.5 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    story = [Paragraph('Newlightemara', styles['Title']), Paragraph(title, styles['Heading2']), Spacer(1, 0.4 * cm)]
    table = Table(rows, colWidths=[6 * cm, 10 * cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#111827')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e2e8f0')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(table)
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(f'Generated on {timezone.localdate().isoformat()}', styles['Normal']))
    doc.build(story)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
