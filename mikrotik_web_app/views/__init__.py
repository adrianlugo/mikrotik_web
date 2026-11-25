# mikrotik_web_app/views/__init__.py

from .auth_views import LoginView, LogoutView

from .dashboard_views import (
    DashboardIndexView,
    SincronizarMikrotikView,
)

from .pppoe_views import (
    ClientesListView,
    ClienteCrearView,
    ClienteEditarView,
    ClienteEstadoView,
    ClientePingView,
    ClientePatearView,
    ClienteEliminarView,
    PlanesListView,
    PlanCrearView,
    PlanEditarView,
    PlanEliminarView,
    ConexionActivaView,
)

from .router_views import (
    RoutersListView,
    RouterCrearView,
    RouterDetalleView,
    RouterEditarView,
    RouterEliminarView,
    RouterVerificarView,
    RouterSincronizarView,
    RouterRepararColasView,
    RouterConsumoView,
    RouterLeasesView,
)

from .network_views import (
    ClientesRedListView,
    ClienteRedCrearView,
    ClienteRedEditarView,
    ClienteRedRepararColaView,
    ClienteRedEliminarView,
)

from .billing_views import (
    FacturaListView,
    FacturaCrearView,
    FacturaEditarView,
    FacturaEliminarView,
    PagoListView,
    PagoCrearView,
    PagoEditarView,
    PagoEliminarView,
)