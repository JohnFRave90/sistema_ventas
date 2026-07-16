# MCP Incolpan

Servidor MCP local que conecta Claude Desktop a `ventas.incolpan.com` reusando la
API REST existente (`/api/v1/`, JWT). Solo expone endpoints de lectura — no toca
la base de datos ni el servidor de producción.

Usa credenciales de **administrador** (tabla `Usuario`, rol `administrador` o
`semiadmin`), autenticadas vía `/api/v1/auth/login-admin` — un endpoint separado
del login que usa la app móvil (vendedores). Esto permite consultar cualquier
vendedor individualmente o el conjunto de todos.

## Instalación

```bash
cd mcp_incolpan
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configurar Claude Desktop

Edita `~/Library/Application Support/Claude/claude_desktop_config.json` (créalo si
no existe) y agrega:

```json
{
  "mcpServers": {
    "incolpan": {
      "command": "/Users/johnvelasquez/Proyectos/sistema_ventas/mcp_incolpan/venv/bin/python",
      "args": ["/Users/johnvelasquez/Proyectos/sistema_ventas/mcp_incolpan/server.py"],
      "env": {
        "INCOLPAN_BASE_URL": "https://ventas.incolpan.com",
        "INCOLPAN_USUARIO": "tu_usuario_admin",
        "INCOLPAN_CONTRASENA": "tu_contrasena_admin"
      }
    }
  }
}
```

Reinicia Claude Desktop. Deberías ver las tools de `incolpan` disponibles (icono
de herramientas en el chat).

## Tools disponibles

| Tool | Endpoint | Alcance |
|---|---|---|
| `listar_vendedores()` | `/admin/vendedores` | Catálogo completo |
| `resumen_diario(fecha, vendedor)` | `/admin/analitica/resumen` | Un vendedor o todos, un día |
| `breakdown_diario(fecha)` | `/admin/analitica/breakdown` | Ranking por vendedor + top productos, un día |
| `resumen_rango(desde, hasta, vendedor)` | `/admin/analitica/rango` | Un vendedor o todos, hasta 92 días |
| `despachos_por_producto(desde, hasta, vendedor, producto_codigos)` | `/admin/despachos/por_producto` | Unidades entregadas a vendedores — dato base para producción |
| `devoluciones_por_producto(desde, hasta, vendedor, producto_codigos)` | `/admin/devoluciones/por_producto` | Unidades devueltas (no vendidas) |
| `pedidos_por_producto(desde, hasta, vendedor, producto_codigos)` | `/admin/pedidos/por_producto` | Preventa de clientes (NO ruta diaria del vendedor) |
| `listar_despachos(fecha, vendedor, estado)` | `/despachos` | Todos los vendedores, cualquier fecha |
| `despacho_items(despacho_id)` | `/despachos/<id>/items` | — |
| `despacho_diferencias(despacho_id)` | `/despachos/<id>/diferencias` | — |
| `listar_productos()` | `/productos` | Catálogo completo |

Todas requieren credenciales de administrador (login separado del de la app móvil).

## Probar sin Claude Desktop

```bash
source venv/bin/activate
INCOLPAN_USUARIO=... INCOLPAN_CONTRASENA=... mcp dev server.py
```

Abre el MCP Inspector en el navegador y ejecuta las tools manualmente.
