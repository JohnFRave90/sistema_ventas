from sqlalchemy import case
from app.models import Producto

def get_productos_ordenados():
    orden_productos = [
        '10001', '10003', '10297', '10004', '10041', '10040', '10137', '10251',
        '10238', '10068', '10019', '10058', '10020', '10021', '10059', '10022',
        '10023', '10060', '10092', '10219', '10024', '10291', '10254', '10094',
        '10218', '10061', '10031', '10034', '10296', '10033', '10035', '10192',
        '10193', '10007', '10009', '10133', '10322', '10008', '10010', '10016',
        '10321', '10072', '10069', '10070', '10080', '10079', '10063', '10203',
        '10183', '10082', '10055', '10326', '10002', '10052', '10043', '10073',
        '10086', '10091', '10175', '10202'
    ]

    orden_case = case(
        *[(Producto.codigo == codigo, idx) for idx, codigo in enumerate(orden_productos)],
        else_=9999
    )

    productos = (Producto.query
                 .filter_by(activo=True)
                 .order_by(orden_case, Producto.nombre)
                 .all())

    return productos
