"""Servidor MCP local que expone datos de ventas.incolpan.com a Claude Desktop.

Corre en la máquina del usuario y habla HTTPS contra la API REST ya existente
de la app (`/api/v1/`, autenticada con JWT). No accede a la base de datos ni
al servidor de producción directamente — solo consume endpoints de lectura.

Usa el login de administrador (`/auth/login-admin`), separado del login de
vendedores que usa la app móvil, para poder consultar todos los vendedores.
"""

import os

import httpx
from mcp.server.fastmcp import FastMCP

BASE_URL = os.environ.get("INCOLPAN_BASE_URL", "https://ventas.incolpan.com").rstrip("/")
USUARIO = os.environ.get("INCOLPAN_USUARIO", "")
CONTRASENA = os.environ.get("INCOLPAN_CONTRASENA", "")

mcp = FastMCP("incolpan")

_client = httpx.Client(base_url=BASE_URL, timeout=15.0)
_token = None


def _login():
    global _token
    if not USUARIO or not CONTRASENA:
        raise RuntimeError(
            "Faltan credenciales: define INCOLPAN_USUARIO e INCOLPAN_CONTRASENA "
            "en la configuración del servidor MCP."
        )
    resp = _client.post(
        "/api/v1/auth/login-admin",
        json={"usuario": USUARIO, "contrasena": CONTRASENA},
    )
    body = resp.json()
    if resp.status_code != 200 or not body.get("ok"):
        raise RuntimeError(f"Login falló: {body.get('error', resp.text)}")
    _token = body["data"]["access_token"]


def _get(path: str, params: dict | None = None) -> dict:
    """GET autenticado a la API. Reintenta login una vez si el token expiró/es inválido."""
    global _token
    params = {k: v for k, v in (params or {}).items() if v}

    for intento in range(2):
        if _token is None:
            _login()
        resp = _client.get(
            f"/api/v1{path}",
            params=params,
            headers={"Authorization": f"Bearer {_token}"},
        )
        if resp.status_code == 401 and intento == 0:
            _token = None
            continue
        break

    try:
        body = resp.json()
    except ValueError:
        return {"error": f"Respuesta no-JSON (HTTP {resp.status_code}): {resp.text[:300]}"}

    if resp.status_code != 200 or not body.get("ok"):
        return {"error": body.get("error", f"HTTP {resp.status_code}")}
    return body["data"]


@mcp.tool()
def listar_vendedores() -> dict:
    """Catálogo de vendedores (código y nombre), útil para saber qué código usar como filtro."""
    return _get("/admin/vendedores")


@mcp.tool()
def resumen_diario(fecha: str = "", vendedor: str = "") -> dict:
    """Resumen de un día: ventas, visitas, devoluciones, cambios e inventario.

    fecha: 'YYYY-MM-DD', por defecto hoy.
    vendedor: código de vendedor para filtrar; vacío = agregado de todos los vendedores.
    """
    return _get("/admin/analitica/resumen", {"fecha": fecha, "vendedor": vendedor})


@mcp.tool()
def breakdown_diario(fecha: str = "") -> dict:
    """Ranking de ventas por vendedor + top productos vendidos/devueltos de un día.

    fecha: 'YYYY-MM-DD', por defecto hoy. Ideal para comparar vendedores entre sí.
    """
    return _get("/admin/analitica/breakdown", {"fecha": fecha})


@mcp.tool()
def resumen_rango(desde: str, hasta: str, vendedor: str = "") -> dict:
    """Serie diaria + agregado de métricas en un rango de fechas (máx. 92 días).

    desde, hasta: 'YYYY-MM-DD'. vendedor: código de vendedor; vacío = todos.
    Útil para tendencias y comparaciones entre semanas/meses.
    """
    return _get("/admin/analitica/rango", {"desde": desde, "hasta": hasta, "vendedor": vendedor})


@mcp.tool()
def listar_despachos(fecha: str = "", vendedor: str = "", estado: str = "") -> dict:
    """Lista despachos (máx. 200), con estado derivado (ej. despachado/pendiente).

    fecha: 'YYYY-MM-DD'. vendedor: código de vendedor. estado: filtro exacto de estado.
    Todos los filtros son opcionales; vacíos = sin filtrar.
    """
    return _get("/despachos", {"fecha": fecha, "vendedor": vendedor, "estado": estado})


@mcp.tool()
def despacho_items(despacho_id: int) -> dict:
    """Items (productos, cantidades, precios) de un despacho por su id."""
    return _get(f"/despachos/{despacho_id}/items")


@mcp.tool()
def despacho_diferencias(despacho_id: int) -> dict:
    """Diferencias de un despacho: cantidad despachada vs confirmada vs vendida/devuelta."""
    return _get(f"/despachos/{despacho_id}/diferencias")


@mcp.tool()
def listar_productos() -> dict:
    """Catálogo completo de productos con precio, categoría y orden canónico."""
    return _get("/productos")


if __name__ == "__main__":
    mcp.run(transport="stdio")
