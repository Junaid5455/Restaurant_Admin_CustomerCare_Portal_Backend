from rest_framework import serializers
from apps.delivery.models import Delivery
from apps.orders.models import Order

class DeliverySerializer(serializers.ModelSerializer):
    """Serializer for delivery management"""
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    customer_email = serializers.CharField(source='order.customer.email', read_only=True)
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)
    delivery_address = serializers.CharField(source='order.delivery_address', read_only=True)
    delivery_instructions = serializers.CharField(source='order.delivery_instructions', read_only=True)
    delivery_latitude = serializers.DecimalField(source='order.delivery_latitude', max_digits=9, decimal_places=6, read_only=True)
    delivery_longitude = serializers.DecimalField(source='order.delivery_longitude', max_digits=9, decimal_places=6, read_only=True)
    driver_name = serializers.CharField(source='driver.user.email', read_only=True)
    
    class Meta:
        model = Delivery
        fields = [
            'id', 'order', 'order_number', 'customer_email', 'restaurant', 'restaurant_name',
            'driver', 'driver_name', 'status', 'pickup_address', 'delivery_address', 
            'delivery_instructions', 'delivery_latitude', 'delivery_longitude', 'estimated_delivery_time_minutes', 'actual_delivery_time_minutes',
            'assigned_at', 'picked_up_at', 'delivered_at', 'current_latitude', 'current_longitude',
            'last_location_update', 'delivery_rating', 'created_at'
        ]
        read_only_fields = [
            'order', 'restaurant', 'driver', 'status', 'pickup_address', 'actual_delivery_time_minutes',
            'assigned_at', 'picked_up_at', 'delivered_at', 'current_latitude', 'current_longitude',
            'last_location_update', 'created_at'
        ]

class AssignDriverSerializer(serializers.Serializer):
    """Serializer for assigning a driver"""
    driver_id = serializers.UUIDField(required=True)

class UpdateLocationSerializer(serializers.Serializer):
    """Serializer for updating driver location"""
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=True)