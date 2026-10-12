import secrets


def generate_doctor_code() -> str:
    return f"DOC-{secrets.token_hex(4).upper()}"


def generate_hospital_code() -> str:
    return f"HOS-{secrets.token_hex(4).upper()}"
