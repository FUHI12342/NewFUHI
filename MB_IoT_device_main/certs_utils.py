# certs_utils.py - CircuitPython 対応版
# 注意: CircuitPython の os には os.path が存在しないため、文字列連結で処理します

def resolve_cert_paths(cfg):
    cert_dir = getattr(cfg, "CERT_DIR", "certs")
    cert_file = getattr(cfg, "CERT_FILE", None)
    key_file = getattr(cfg, "KEY_FILE", None)
    root_ca_file = getattr(cfg, "ROOT_CA_FILE", "AmazonRootCA1.pem")
    ca_at_root = getattr(cfg, "CA_AT_ROOT", False)

    # 証明書ファイル
    if cert_file:
        if not cert_file.startswith(cert_dir + "/") and not cert_file.startswith("/"):
            cert_file = f"{cert_dir}/{cert_file}"

    # 秘密鍵ファイル
    if key_file:
        if not key_file.startswith(cert_dir + "/") and not key_file.startswith("/"):
            key_file = f"{cert_dir}/{key_file}"

    # ルート CA
    if ca_at_root:
        root_ca = "/" + root_ca_file.lstrip("/")
    else:
        if not root_ca_file.startswith(cert_dir + "/") and not root_ca_file.startswith("/"):
            root_ca = f"{cert_dir}/{root_ca_file}"
        else:
            root_ca = root_ca_file

    return cert_file, key_file, root_ca