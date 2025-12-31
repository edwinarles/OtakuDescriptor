from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from database import db
from services.paypal_service import create_paypal_order, capture_paypal_order
from config import Config

payment_bp = Blueprint('payment', __name__)

@payment_bp.route('/create-order', methods=['POST'])
def create_order():
    data = request.get_json()
    api_key = data.get('api_key')
    
    user = db.db.users.find_one({'api_key': api_key})
    if not user:
        return jsonify({'error': 'Invalid API key'}), 401
        
    order = create_paypal_order(Config.PREMIUM_PRICE, str(user['_id']), request.host_url.rstrip('/'))
    if not order:
        return jsonify({'error': 'Error creating PayPal order'}), 500
        
    approval_link = next((l['href'] for l in order.get('links', []) if l['rel'] == 'approve'), None)
    
    return jsonify({'order_id': order['id'], 'approval_url': approval_link})

@payment_bp.route('/capture-order', methods=['POST'])
def capture_order():
    data = request.get_json()
    order_id = data.get('order_id')
    
    print(f"📥 Captura de orden solicitada: {order_id}")
    
    if not order_id: 
        print("❌ Error: No se proporcionó order_id")
        return jsonify({'error': 'Order ID required'}), 400
    
    # Capturar el pago con PayPal
    capture = capture_paypal_order(order_id)
    print(f"📡 Respuesta de PayPal: {capture}")
    
    if not capture:
        print("❌ Error: No se recibió respuesta de PayPal")
        return jsonify({'error': 'PayPal capture failed - no response'}), 500
        
    if capture.get('status') != 'COMPLETED':
        status = capture.get('status', 'UNKNOWN')
        print(f"❌ Error: Pago no completado. Status: {status}")
        return jsonify({'error': f'Payment not completed. Status: {status}'}), 400
        
    # Actualizar Usuario
    try:
        purchase_units = capture.get('purchase_units', [])
        print(f"📦 Purchase units: {purchase_units}")
        
        if not purchase_units:
            print("❌ Error: No hay purchase units en la respuesta")
            return jsonify({'error': 'Invalid PayPal response - no purchase units'}), 500
        
        # El custom_id está dentro de payments > captures[0] en la respuesta de PayPal
        payments = purchase_units[0].get('payments', {})
        captures = payments.get('captures', [])
        
        if not captures:
            print("❌ Error: No hay captures en la respuesta")
            return jsonify({'error': 'Invalid PayPal response - no captures'}), 500
            
        user_id_str = captures[0].get('custom_id')
        print(f"👤 User ID desde PayPal (de captures): {user_id_str}")
        
        if not user_id_str:
            print("❌ Error: No se encontró custom_id en captures")
            return jsonify({'error': 'User ID not found in payment'}), 500
        
        from bson.objectid import ObjectId
        user_id = ObjectId(user_id_str)
        
        premium_until = datetime.now() + timedelta(days=30)
        
        # Actualizar usuario a premium
        result = db.db.users.update_one(
            {'_id': user_id},
            {'$set': {'is_premium': True, 'premium_until': premium_until}}
        )
        
        print(f"✅ Usuario actualizado: matched={result.matched_count}, modified={result.modified_count}")
        
        # Registrar Pago
        db.db.payments.insert_one({
            'user_id': user_id,
            'paypal_order_id': order_id,
            'amount': float(captures[0]['amount']['value']),
            'status': 'completed',
            'created_at': datetime.now()
        })
        
        print(f"✅ Pago completado exitosamente para usuario {user_id_str}")
        return jsonify({'status': 'success', 'message': 'Premium activated'})
        
    except Exception as e:
        import traceback
        print(f"❌ Error procesando captura de pago: {e}")
        print(f"❌ Traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Error processing payment: {str(e)}'}), 500
