from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('estimator/', views.estimator, name='estimator'),
    path('estimator/pdf/', views.estimator_pdf, name='estimator_pdf'),
    path('clients/', views.clients, name='clients'),
    path('timesheets/', views.timesheets, name='timesheets'),
    path('payroll/', views.payroll, name='payroll'),
    path('efficiency/', views.efficiency, name='efficiency'),
    path('procurement/', views.procurement, name='procurement'),
    path('milestones/', views.milestones, name='milestones'),
    path('photos/', views.photos, name='photos'),
    path('warehouse/', views.warehouse, name='warehouse'),
    path('invoicing/', views.invoicing, name='invoicing'),
    path('invoicing/<int:client_id>/pdf/', views.invoice_pdf, name='invoice_pdf'),
    path('dispatch/', views.dispatch, name='dispatch'),
    path('settings/', views.settings_view, name='settings'),
    path('vip/', views.vip_portal, name='vip_portal'),
]
