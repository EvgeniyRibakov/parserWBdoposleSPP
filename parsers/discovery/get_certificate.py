# -*- coding: utf-8 -*-
"""
Получение пути к сертификату mitmproxy
"""

import os
from pathlib import Path

# Стандартные пути к сертификату mitmproxy
possible_paths = [
    Path.home() / '.mitmproxy' / 'mitmproxy-ca-cert.pem',
    Path.home() / '.mitmproxy' / 'mitmproxy-ca-cert.cer',
    Path.home() / '.mitmproxy' / 'mitmproxy-ca.pem',
]

print("\nПоиск сертификата mitmproxy...\n")

for cert_path in possible_paths:
    if cert_path.exists():
        print(f"✓ Сертификат найден: {cert_path}")
        print(f"  Полный путь: {cert_path.absolute()}")
        print(f"\nДля установки:")
        print(f"  1. Откройте файл: {cert_path.absolute()}")
        print(f"  2. Установите в 'Доверенные корневые центры сертификации'")
        break
else:
    print("✗ Сертификат не найден в стандартных местах")
    print("\nАльтернативные способы:")
    print("1. Используйте Chrome с флагами --ignore-certificate-errors")
    print("2. Или запустите mitmproxy еще раз - он создаст сертификат")

