from .auth_views import LoginView, LogoutView
from .dashboard_views import DashboardIndexView, SincronizarMikrotikView
from .pppoe_views import (
    ClientesListView, ClienteCrearView, ClienteEditarView,
    ClienteEstadoView, ClientePingView, ClientePateارView, ClienteEliminarView,
    PlanesListView, PlanCrearView, PlanEditarView, PlanEliminarView,
    ConexionActivaView
)
from .router_views import (
    RoutersListView, RouterCrearView, RouterEditarView, RouterDetalleView,
    RouterEliminarView, RouterVerificarView, RouterSincronizarView,
    RouterRepararColasView, RouterConsumoView, RouterLeasesView
)
from .network_views import (
    ClientesRedListView, ClienteRedCrearView, ClienteRedEditarView,
    ClienteRedRepararColaView, ClienteRedEliminarView, EnlacesISPListView, InterfacesListView
)
from .billing_views import (
    FacturaListView, FacturaCrearView, FacturaEditarView, FacturaEliminarView,
    PagoListView, PagoCrearView, PagoEditarView, PagoEliminarView
)