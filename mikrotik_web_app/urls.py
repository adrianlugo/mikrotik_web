from django.urls import path

from .views import (
    ClienteEliminarView,
    ClienteEstadoView,
    ClientesListView,
    ConexionActivaView,
    EnlacesISPListView,
    InterfacesListView,
    PlanesListView,
    RoutersListView,
    SincronizarMikrotikView,
)

urlpatterns = [
    path("clientes/sincronizar/", SincronizarMikrotikView.as_view(), name="sincronizar_mikrotik"),
    path("clientes/", ClientesListView.as_view(), name="clientes_list"),
    path("clientes/<int:pk>/estado/", ClienteEstadoView.as_view(), name="cliente_estado"),
    path("clientes/<int:pk>/eliminar/", ClienteEliminarView.as_view(), name="cliente_eliminar"),
    path("planes/", PlanesListView.as_view(), name="planes_list"),
    path("conexiones/", ConexionActivaView.as_view(), name="conexiones_list"),
    path("routers/", RoutersListView.as_view(), name="routers_list"),
    path("enlaces/", EnlacesISPListView.as_view(), name="enlaces_list"),
    path("interfaces/", InterfacesListView.as_view(), name="interfaces_list"),
]
