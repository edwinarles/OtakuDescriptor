import requests
import time
from datetime import datetime, timedelta
from config import Config

paypal_token_cache = {
    'token': None,
    'expires_at': None
}

def get_paypal_access_token():
    global paypal_token_cache
    if paypal_token_cache['token'] and paypal_token_cache['expires_at']:
        if datetime.now() < paypal_token_cache['expires_at']:
            return paypal_token_cache['token']
    
    url = f"{Config.PAYPAL_API}/v1/oauth2/token"
    headers = {"Accept": "application/json", "Accept-Language": "en_US"}
    data = {"grant_type": "client_credentials"}
    
    try:
        response = requests.post(
            url, headers=headers, data=data,
            auth=(Config.PAYPAL_CLIENT_ID, Config.PAYPAL_CLIENT_SECRET),
            timeout=10
        )
        response.raise_for_status()
        token_data = response.json()
        
        paypal_token_cache['token'] = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600) - 300
        paypal_token_cache['expires_at'] = datetime.now() + timedelta(seconds=expires_in)
        return paypal_token_cache['token']
    except Exception as e:
        print(f"❌ Error token PayPal: {e}")
        return None

def create_paypal_order(amount, user_id, return_url_base):
    access_token = get_paypal_access_token()
    if not access_token: return None
    
    url = f"{Config.PAYPAL_API}/v2/checkout/orders"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Prefer": "return=minimal"
    }
    
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {"currency_code": "USD", "value": amount},
            "description": "Anime Search Premium - 1 Month",
            "custom_id": str(user_id)
        }],
        "application_context": {
            "return_url": f"{return_url_base}/payment-success",
            "cancel_url": f"{return_url_base}/payment-cancel",
            "brand_name": "Anime Search",
            "user_action": "PAY_NOW"
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Error create order: {e}")
        return None

def capture_paypal_order(order_id):
    access_token = get_paypal_access_token()
    if not access_token: 
        print("❌ No se pudo obtener access token de PayPal")
        return None
    
    url = f"{Config.PAYPAL_API}/v2/checkout/orders/{order_id}/capture"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    
    try:
        print(f"📡 Capturando orden en PayPal: {order_id}")
        response = requests.post(url, headers=headers, timeout=15)
        print(f"📡 Status de respuesta PayPal: {response.status_code}")
        
        if response.status_code in [200, 201]:
            result = response.json()
            print(f"✅ Captura exitosa: {result.get('status')}")
            return result
        else:
            error_data = response.text
            print(f"❌ Error en captura PayPal (status {response.status_code}): {error_data}")
            # Si ya fue capturado, intentar obtener detalles
            if response.status_code == 422:
                print("⚠️ Orden posiblemente ya capturada")
            return None
    except Exception as e:
        import traceback
        print(f"❌ Excepción capturando orden: {e}")
        print(f"❌ Traceback: {traceback.format_exc()}")
        return None
