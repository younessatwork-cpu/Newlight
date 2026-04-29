# Generated for the Newlightemara rebuild. Keeps the requested PostgreSQL table names and columns.
import hashlib
from django.db import migrations, models
import django.utils.timezone


def seed_admin(apps, schema_editor):
    SystemUser = apps.get_model('ops', 'SystemUser')
    SystemUser.objects.get_or_create(
        username='admin',
        defaults={
            'password_hash': hashlib.sha256('Admin2026!'.encode('utf-8')).hexdigest(),
            'role': 'Admin',
            'reference': 'Newlightemara',
        },
    )


def unseed_admin(apps, schema_editor):
    SystemUser = apps.get_model('ops', 'SystemUser')
    SystemUser.objects.filter(username='admin').delete()


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name='Client',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('client_name', models.CharField(max_length=180)),
                ('work_type', models.CharField(blank=True, max_length=180)),
                ('budget', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('advance', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('total_points', models.IntegerField(default=0)),
                ('status', models.CharField(choices=[('active', 'Active'), ('completed', 'Completed'), ('paused', 'Paused'), ('cancelled', 'Cancelled')], default='active', max_length=30)),
            ],
            options={'db_table': 'clients', 'ordering': ['client_name']},
        ),
        migrations.CreateModel(
            name='Expense',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('date', models.DateField(default=django.utils.timezone.localdate)),
                ('client_name', models.CharField(max_length=180)),
                ('item', models.CharField(max_length=220)),
                ('amount', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('phase', models.CharField(choices=[('Incorporation', 'Incorporation'), ('Tirage', 'Tirage'), ('Appareillage', 'Appareillage'), ('Tableau', 'Tableau')], max_length=40)),
                ('supplier', models.CharField(blank=True, max_length=180)),
            ],
            options={'db_table': 'expenses', 'ordering': ['-date', '-id']},
        ),
        migrations.CreateModel(
            name='Inventory',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('item_name', models.CharField(max_length=220)),
                ('category', models.CharField(blank=True, max_length=120)),
                ('quantity', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('unit', models.CharField(default='pcs', max_length=40)),
            ],
            options={'db_table': 'inventory', 'ordering': ['item_name']},
        ),
        migrations.CreateModel(
            name='InventoryLog',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('date', models.DateField(default=django.utils.timezone.localdate)),
                ('item_name', models.CharField(max_length=220)),
                ('change_amount', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('direction', models.CharField(choices=[('IN', 'IN'), ('OUT', 'OUT')], max_length=5)),
                ('site_allocated', models.CharField(blank=True, max_length=180)),
                ('notes', models.TextField(blank=True)),
            ],
            options={'db_table': 'inventory_logs', 'ordering': ['-date', '-id']},
        ),
        migrations.CreateModel(
            name='LaborLog',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('date', models.DateField(default=django.utils.timezone.localdate)),
                ('client_name', models.CharField(max_length=180)),
                ('worker_name', models.CharField(max_length=150)),
                ('days', models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('cost', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('phase', models.CharField(choices=[('Incorporation', 'Incorporation'), ('Tirage', 'Tirage'), ('Appareillage', 'Appareillage'), ('Tableau', 'Tableau')], max_length=40)),
            ],
            options={'db_table': 'labor_logs', 'ordering': ['-date', '-id']},
        ),
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('date', models.DateField(default=django.utils.timezone.localdate)),
                ('client_name', models.CharField(max_length=180)),
                ('amount', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('method', models.CharField(blank=True, max_length=80)),
                ('notes', models.TextField(blank=True)),
            ],
            options={'db_table': 'payments', 'ordering': ['-date', '-id']},
        ),
        migrations.CreateModel(
            name='Progress',
            fields=[
                ('client_name', models.CharField(max_length=180, primary_key=True, serialize=False)),
                ('phase1', models.IntegerField(default=0)),
                ('phase2', models.IntegerField(default=0)),
                ('phase3', models.IntegerField(default=0)),
                ('phase4', models.IntegerField(default=0)),
            ],
            options={'db_table': 'progress'},
        ),
        migrations.CreateModel(
            name='SitePhoto',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('upload_date', models.DateTimeField(default=django.utils.timezone.now)),
                ('client_name', models.CharField(max_length=180)),
                ('phase', models.CharField(choices=[('Incorporation', 'Incorporation'), ('Tirage', 'Tirage'), ('Appareillage', 'Appareillage'), ('Tableau', 'Tableau')], max_length=40)),
                ('photo_data', models.TextField()),
                ('notes', models.TextField(blank=True)),
            ],
            options={'db_table': 'site_photos', 'ordering': ['-upload_date', '-id']},
        ),
        migrations.CreateModel(
            name='SystemUser',
            fields=[
                ('username', models.CharField(max_length=80, primary_key=True, serialize=False)),
                ('password_hash', models.CharField(db_column='password_hash', max_length=64)),
                ('role', models.CharField(choices=[('Admin', 'Admin'), ('Technician', 'Technician'), ('Client', 'Client')], max_length=30)),
                ('reference', models.CharField(blank=True, max_length=180)),
            ],
            options={'db_table': 'system_users'},
        ),
        migrations.CreateModel(
            name='Worker',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=150)),
                ('tjm', models.DecimalField(decimal_places=2, max_digits=12)),
                ('specialty', models.CharField(blank=True, max_length=150)),
            ],
            options={'db_table': 'workers', 'ordering': ['name']},
        ),
        migrations.RunPython(seed_admin, unseed_admin),
    ]
