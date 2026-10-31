from django.urls import path, include
from django.contrib import admin
from mikrotik_web_app.views import DashboardIndexView 

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Esta línea renderiza tu página de inicio directamente usando tu vista local
    path('', DashboardIndexView.as_view(), name='dashboard_index'),
    
    # Si vas a tener más sub-páginas web en el futuro (ej: /clientes/, /planes/):
    path('web/', include('mikrotik_web_app.urls')), 
]
