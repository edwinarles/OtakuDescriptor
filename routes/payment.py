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
    
    if not order_id: return jsonify({'error': 'Order ID required'}), 400
    
    capture = capture_paypal_order(order_id)
    if not capture or capture.get('status') != 'COMPLETED':
        return jsonify({'error': 'Payment not completed'}), 400
        
    # Actualizar Usuario
    try:
        purchase_units = capture.get('purchase_units', [])
        user_id_str = purchase_units[0].get('custom_id')
        from bson.objectid import ObjectId
        user_id = ObjectId(user_id_str)
        
        premium_until = datetime.now() + timedelta(days=30)
        
        db.db.users.update_one(
            {'_id': user_id},
            {'$set': {'is_premium': True, 'premium_until': premium_until}}
        )
        
        # Registrar Pago
        db.db.payments.insert_one({
            'user_id': user_id,
            'paypal_order_id': order_id,
            'amount': float(purchase_units[0]['amount']['value']),
            'status': 'completed',
            'created_at': datetime.now()
        })
        
        return jsonify({'status': 'success', 'message': 'Premium activated'})
        
    except Exception as e:
        print(f"Error processing payment capture: {e}")
        return jsonify({'error': 'Error processing payment'}), 500
