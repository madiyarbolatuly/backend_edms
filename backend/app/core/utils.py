import ulid

def get_ulid() -> str:
    return str(ulid.ULID())
