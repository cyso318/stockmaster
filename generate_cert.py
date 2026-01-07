"""
Generiert selbst-signiertes SSL-Zertifikat für lokale Entwicklung
"""

from OpenSSL import crypto
import os
import socket

def generate_self_signed_cert():
    """Erstellt selbst-signiertes Zertifikat"""

    # Erstelle Key-Pair
    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 2048)

    # Erstelle Zertifikat
    cert = crypto.X509()
    cert.get_subject().C = "DE"
    cert.get_subject().ST = "Germany"
    cert.get_subject().L = "Local"
    cert.get_subject().O = "StockMaster"
    cert.get_subject().OU = "Development"
    cert.get_subject().CN = "localhost"

    cert.set_serial_number(1000)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(365*24*60*60)  # 1 Jahr gültig
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)

    # Füge Subject Alternative Names hinzu (für IP-Adressen und Hostnamen)
    # Dies ermöglicht Zugriff über localhost, 127.0.0.1, und lokale IP
    san_list = [
        b'DNS:localhost',
        b'DNS:*.localhost',
        b'IP:127.0.0.1',
        b'IP:::1',  # IPv6 localhost
    ]

    # Füge lokale IP-Adressen hinzu
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        san_list.append(f'IP:{local_ip}'.encode())
        print(f"Lokale IP gefunden: {local_ip}")
    except:
        pass

    # Alle lokalen IPs finden
    try:
        import subprocess
        result = subprocess.run(['ipconfig'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if 'IPv4' in line and ':' in line:
                ip = line.split(':')[1].strip()
                if ip and ip != '127.0.0.1':
                    san_entry = f'IP:{ip}'.encode()
                    if san_entry not in san_list:
                        san_list.append(san_entry)
                        print(f"IP hinzugefuegt: {ip}")
    except:
        pass

    # Füge SAN Extension hinzu
    cert.add_extensions([
        crypto.X509Extension(b'subjectAltName', False, b', '.join(san_list))
    ])

    cert.sign(k, 'sha256')

    # Speichere Zertifikat und Key
    with open("cert.pem", "wb") as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))

    with open("key.pem", "wb") as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k))

    print("OK Zertifikat erstellt: cert.pem")
    print("OK Private Key erstellt: key.pem")
    print("\nHinweis: Dies ist ein selbst-signiertes Zertifikat.")
    print("Ihr Browser wird eine Warnung anzeigen - dies ist normal fuer lokale Entwicklung.")

if __name__ == '__main__':
    generate_self_signed_cert()
