import re
import unicodedata
import secrets

def limpiar_html(texto):
    """Elimina etiquetas HTML"""
    texto = re.sub(r'<.*?>', '', texto or '')
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()

def normalizar_texto(texto):
    """Convierte a minúsculas y elimina acentos"""
    if not texto:
        return ""
    texto = texto.lower().strip()
    texto = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    return texto

def generate_api_key():
    """Genera una clave API única"""
    return f"ask_{secrets.token_urlsafe(32)}"
