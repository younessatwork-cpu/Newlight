from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from ops.auth_utils import sha256_password
from ops.models import Client, Expense, Inventory, InventoryLog, LaborLog, Payment, Progress, SystemUser, Worker


class Command(BaseCommand):
    help = 'Seed optional demo data for local testing. Safe to run multiple times.'

    def add_arguments(self, parser):
        parser.add_argument('--noinput', action='store_true')

    def handle(self, *args, **options):
        workers = [
            ('Yassine', Decimal('350'), 'Electrician'),
            ('Karim', Decimal('300'), 'Technician'),
            ('Nabil', Decimal('450'), 'Chef chantier'),
        ]
        for name, tjm, specialty in workers:
            Worker.objects.get_or_create(name=name, defaults={'tjm': tjm, 'specialty': specialty})

        clients = [
            ('Villa Harhoura', 'Residential complete installation', Decimal('98000'), Decimal('25000'), 128, 'active'),
            ('Boutique Temara', 'Commercial renovation', Decimal('42000'), Decimal('12000'), 58, 'active'),
        ]
        for name, work_type, budget, advance, points, status in clients:
            Client.objects.get_or_create(client_name=name, defaults={'work_type': work_type, 'budget': budget, 'advance': advance, 'total_points': points, 'status': status})
            Progress.objects.get_or_create(client_name=name, defaults={'phase1': 80, 'phase2': 45, 'phase3': 10, 'phase4': 0})

        if not LaborLog.objects.exists():
            LaborLog.objects.create(date=timezone.localdate(), client_name='Villa Harhoura', worker_name='Yassine', days=Decimal('2'), cost=Decimal('700'), phase='Incorporation')
            LaborLog.objects.create(date=timezone.localdate(), client_name='Villa Harhoura', worker_name='Nabil', days=Decimal('1'), cost=Decimal('450'), phase='Tirage')
            LaborLog.objects.create(date=timezone.localdate(), client_name='Boutique Temara', worker_name='Karim', days=Decimal('1.5'), cost=Decimal('450'), phase='Incorporation')

        if not Expense.objects.exists():
            Expense.objects.create(date=timezone.localdate(), client_name='Villa Harhoura', item='Gaines ICTA', amount=Decimal('2100'), phase='Incorporation', supplier='Local supplier')
            Expense.objects.create(date=timezone.localdate(), client_name='Boutique Temara', item='Câble 2.5mm', amount=Decimal('1300'), phase='Tirage', supplier='Electro Maroc')

        for item_name, category, qty, unit in [('Câble 2.5mm', 'Cable', 240, 'm'), ('Disjoncteur 16A', 'Protection', 12, 'pcs'), ('Boite encastrement', 'Consumable', 4, 'pcs')]:
            Inventory.objects.get_or_create(item_name=item_name, defaults={'category': category, 'quantity': qty, 'unit': unit})

        if not InventoryLog.objects.exists():
            InventoryLog.objects.create(date=timezone.localdate(), item_name='Câble 2.5mm', change_amount=Decimal('50'), direction='OUT', site_allocated='Villa Harhoura', notes='Initial allocation')

        Payment.objects.get_or_create(client_name='Villa Harhoura', amount=Decimal('25000'), defaults={'date': timezone.localdate(), 'method': 'Cash', 'notes': 'Opening advance'})
        Payment.objects.get_or_create(client_name='Boutique Temara', amount=Decimal('12000'), defaults={'date': timezone.localdate(), 'method': 'Bank', 'notes': 'Opening advance'})

        SystemUser.objects.get_or_create(username='tech', defaults={'password_hash': sha256_password('Tech2026!'), 'role': 'Technician', 'reference': 'Yassine'})
        SystemUser.objects.get_or_create(username='client', defaults={'password_hash': sha256_password('Client2026!'), 'role': 'Client', 'reference': 'Villa Harhoura'})
        self.stdout.write(self.style.SUCCESS('Demo data ready.'))
