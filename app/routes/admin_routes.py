from flask import Blueprint, jsonify, request
from app.services.cart_cleanup import manual_cleanup, cleanup_service
from app.services.db_inventory import (
    get_inventory_summary, 
    get_stock_status_report, 
    cleanup_expired_reservations,
    get_available_stock
)
import os

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/cleanup/manual', methods=['POST'])
def trigger_manual_cleanup():
    """Manually trigger cart and reservation cleanup"""
    try:
        manual_cleanup()
        return jsonify({
            'status': 'success',
            'message': 'Manual cleanup completed successfully'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@admin_bp.route('/cleanup/status', methods=['GET'])
def get_cleanup_status():
    """Get status of cleanup service"""
    return jsonify({
        'status': 'success',
        'cleanup_service_running': cleanup_service.running,
        'cleanup_interval_hours': cleanup_service.cleanup_interval_hours,
        'cart_expiry_hours': cleanup_service.cart_expiry_hours,
        'reservation_expiry_hours': cleanup_service.reservation_expiry_hours
    })

@admin_bp.route('/inventory/summary', methods=['GET'])
def get_inventory_summary_route():
    """Get inventory summary"""
    try:
        summary = get_inventory_summary()
        return jsonify(summary)
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@admin_bp.route('/inventory/stock-report', methods=['GET'])
def get_stock_report():
    """Get detailed stock status report"""
    try:
        report = get_stock_status_report()
        return jsonify(report)
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@admin_bp.route('/stock/available/<product_id>', methods=['GET'])
def check_available_stock(product_id):
    """Check available stock for a specific product"""
    try:
        stock_info = get_available_stock(product_id)
        return jsonify(stock_info)
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@admin_bp.route('/reservations/cleanup', methods=['POST'])
def cleanup_reservations():
    """Clean up expired stock reservations"""
    try:
        hours = request.json.get('hours', 24) if request.json else 24
        result = cleanup_expired_reservations(hours)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@admin_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'WhatsApp Bot Admin',
        'cleanup_service_running': cleanup_service.running
    })
