from typing import Type


def get_type_name(typ: Type) -> str:
    # if hasattr(typ, "__name__"):
    # return typ.__name__

    return str(typ)
