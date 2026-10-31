from django.urls import path
from .views import DashboardIndexView, SincronizarMikrotikView, ClientesListView

urlpatterns = [
    path('', DashboardIndexView.as_view(), name='dashboard_index'),
    path('sincronizar/', SincronizarMikrotikView.as_view(), name='sincronizar_mikrotik'), # <-- Nueva ruta
    path('clientes/', ClientesListView.as_view(), name='clientes_list'),
]
