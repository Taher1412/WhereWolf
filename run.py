"""Start Near.

  python run.py            -> http://localhost:8000/map   (laptop only)
  python run.py --https    -> https://<laptop-ip>:8443/field  (phones: the mic needs HTTPS)

With --https a self-signed certificate is created in data/ the first time.
On the phone, accept the browser warning once ("Advanced" -> "Proceed").
"""
import ipaddress
import socket
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent
CERT, KEY = ROOT / "data" / "cert.pem", ROOT / "data" / "key.pem"


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def make_cert(ip):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "near.local")])
    alt = x509.SubjectAlternativeName([x509.DNSName("localhost"),
                                       x509.IPAddress(ipaddress.ip_address(ip)),
                                       x509.IPAddress(ipaddress.ip_address("127.0.0.1"))])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=30))
            .add_extension(alt, critical=False).sign(key, hashes.SHA256()))
    CERT.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    KEY.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                                      serialization.PrivateFormat.TraditionalOpenSSL,
                                      serialization.NoEncryption()))


if __name__ == "__main__":
    ip = lan_ip()
    if "--https" in sys.argv:
        if not CERT.exists():
            make_cert(ip)
        print(f"\n  Coordinator: https://{ip}:8443/map\n  Field phone: https://{ip}:8443/field\n")
        uvicorn.run("backend.main:app", host="0.0.0.0", port=8443,
                    ssl_certfile=str(CERT), ssl_keyfile=str(KEY))
    else:
        print(f"\n  Coordinator: http://localhost:8000/map\n  Field (this laptop): http://localhost:8000/field\n")
        uvicorn.run("backend.main:app", host="0.0.0.0", port=8000)
