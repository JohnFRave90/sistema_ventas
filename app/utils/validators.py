def validar_entero(valor, nombre_campo="campo"):
    """Convierte valor a entero o lanza ValueError con mensaje claro."""
    try:
        return int(valor)
    except (ValueError, TypeError):
        raise ValueError(f"'{nombre_campo}' debe ser un número entero válido.")


def validar_precio(valor, nombre_campo="precio"):
    """Convierte valor a float positivo o lanza ValueError."""
    try:
        v = float(valor)
    except (ValueError, TypeError):
        raise ValueError(f"'{nombre_campo}' debe ser un número válido.")
    if v < 0:
        raise ValueError(f"'{nombre_campo}' no puede ser un valor negativo.")
    return v


def validar_codigo(valor, nombre_campo="código", longitud_min=1):
    """Limpia espacios y verifica que el código no esté vacío."""
    if valor is None:
        raise ValueError(f"'{nombre_campo}' no puede estar vacío.")
    codigo = str(valor).strip()
    if len(codigo) < longitud_min:
        raise ValueError(
            f"'{nombre_campo}' debe tener al menos {longitud_min} caractere(s)."
        )
    return codigo
