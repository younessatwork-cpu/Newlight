from django.db import models
from django.utils import timezone

PHASES = [
    ('Incorporation', 'Incorporation'),
    ('Tirage', 'Tirage'),
    ('Appareillage', 'Appareillage'),
    ('Tableau', 'Tableau'),
]

STATUS_CHOICES = [('active', 'Active'), ('completed', 'Completed'), ('paused', 'Paused'), ('cancelled', 'Cancelled')]
ROLE_CHOICES = [('Admin', 'Admin'), ('Technician', 'Technician'), ('Client', 'Client')]
DIRECTION_CHOICES = [('IN', 'IN'), ('OUT', 'OUT')]


class Worker(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=150)
    tjm = models.DecimalField(max_digits=12, decimal_places=2)
    specialty = models.CharField(max_length=150, blank=True)

    class Meta:
        db_table = 'workers'
        ordering = ['name']

    def __str__(self):
        return self.name


class Client(models.Model):
    id = models.AutoField(primary_key=True)
    client_name = models.CharField(max_length=180)
    work_type = models.CharField(max_length=180, blank=True)
    budget = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    advance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_points = models.IntegerField(default=0)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='active')

    class Meta:
        db_table = 'clients'
        ordering = ['client_name']

    def __str__(self):
        return self.client_name


class LaborLog(models.Model):
    id = models.AutoField(primary_key=True)
    date = models.DateField(default=timezone.localdate)
    client_name = models.CharField(max_length=180)
    worker_name = models.CharField(max_length=150)
    days = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    phase = models.CharField(max_length=40, choices=PHASES)

    class Meta:
        db_table = 'labor_logs'
        ordering = ['-date', '-id']


class Expense(models.Model):
    id = models.AutoField(primary_key=True)
    date = models.DateField(default=timezone.localdate)
    client_name = models.CharField(max_length=180)
    item = models.CharField(max_length=220)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    phase = models.CharField(max_length=40, choices=PHASES)
    supplier = models.CharField(max_length=180, blank=True)

    class Meta:
        db_table = 'expenses'
        ordering = ['-date', '-id']


class Progress(models.Model):
    client_name = models.CharField(max_length=180, primary_key=True)
    phase1 = models.IntegerField(default=0)
    phase2 = models.IntegerField(default=0)
    phase3 = models.IntegerField(default=0)
    phase4 = models.IntegerField(default=0)

    class Meta:
        db_table = 'progress'

    @property
    def average(self):
        return round((self.phase1 + self.phase2 + self.phase3 + self.phase4) / 4)


class SitePhoto(models.Model):
    id = models.AutoField(primary_key=True)
    upload_date = models.DateTimeField(default=timezone.now)
    client_name = models.CharField(max_length=180)
    phase = models.CharField(max_length=40, choices=PHASES)
    photo_data = models.TextField()
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'site_photos'
        ordering = ['-upload_date', '-id']


class Inventory(models.Model):
    id = models.AutoField(primary_key=True)
    item_name = models.CharField(max_length=220)
    category = models.CharField(max_length=120, blank=True)
    quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    unit = models.CharField(max_length=40, default='pcs')

    class Meta:
        db_table = 'inventory'
        ordering = ['item_name']

    def __str__(self):
        return self.item_name


class InventoryLog(models.Model):
    id = models.AutoField(primary_key=True)
    date = models.DateField(default=timezone.localdate)
    item_name = models.CharField(max_length=220)
    change_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    direction = models.CharField(max_length=5, choices=DIRECTION_CHOICES)
    site_allocated = models.CharField(max_length=180, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'inventory_logs'
        ordering = ['-date', '-id']


class SystemUser(models.Model):
    username = models.CharField(max_length=80, primary_key=True)
    password_hash = models.CharField(max_length=64, db_column='password_hash')
    role = models.CharField(max_length=30, choices=ROLE_CHOICES)
    reference = models.CharField(max_length=180, blank=True)

    class Meta:
        db_table = 'system_users'

    def __str__(self):
        return f'{self.username} ({self.role})'


class Payment(models.Model):
    id = models.AutoField(primary_key=True)
    date = models.DateField(default=timezone.localdate)
    client_name = models.CharField(max_length=180)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    method = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'payments'
        ordering = ['-date', '-id']
