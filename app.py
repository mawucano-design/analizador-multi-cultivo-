"""
Configuración para Sentinel Hub
"""

import os
from sentinelhub import SHConfig

def configurar_sentinelhub():
    """Configura las credenciales de Sentinel Hub"""
    
    config = SHConfig()
    
    # Obtener credenciales de variables de entorno
    client_id = os.getenv('b296cf70-c9d2-4e69-91f4-f7be80b99ed1')
    client_secret = os.getenv('358474d6-2326-4637-bf8e-30a709b2d6a6')
    
    if client_id and client_secret:
        config.sh_client_id = client_id
        config.sh_client_secret = client_secret
        config.save()
        print("✅ Credenciales de Sentinel Hub configuradas")
    else:
        print("⚠️  Credenciales de Sentinel Hub no encontradas en variables de entorno")
        print("   Configura:")
        print("   - SENTINELHUB_CLIENT_ID")
        print("   - SENTINELHUB_CLIENT_SECRET")
    
    return config

def verificar_configuracion():
    """Verifica que la configuración esté correcta"""
    config = SHConfig()
    
    if hasattr(config, 'sh_client_id') and hasattr(config, 'sh_client_secret'):
        if config.sh_client_id and config.sh_client_secret:
            return True
    
    return False
