from rest_framework import serializers
from apps.menu.serializers import MenuCategorySerializer
from apps.restaurants import reservation_services
from apps.restaurants.models import Restaurant, RestaurantHoliday, RestaurantDeliveryZone, RestaurantStaffMember, RestaurantTable, Reservation



class RestaurantDeliveryZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantDeliveryZone
        fields = ['id', 'zone_name', 'delivery_fee', 'delivery_time_minutes', 'postal_codes', 'is_active']

class RestaurantListSerializer(serializers.ModelSerializer):
    is_open_now = serializers.SerializerMethodField()
    review_count = serializers.IntegerField(source='total_reviews', read_only=True)
    
    class Meta:
        model = Restaurant
        fields = [
            'id', 'name', 'slug', 'logo', 'rating', 'review_count', 
            'is_open_now', 'delivery_time_minutes', 'min_order_amount'
            # Removed 'is_featured'
        ]
    
    def get_is_open_now(self, obj):
        from django.utils import timezone
        current_time = timezone.now().time()
        return obj.opening_time <= current_time <= obj.closing_time

class RestaurantDetailSerializer(serializers.ModelSerializer):
    is_open_now = serializers.SerializerMethodField()
    review_count = serializers.IntegerField(source='total_reviews', read_only=True)
    delivery_zones = RestaurantDeliveryZoneSerializer(many=True, read_only=True)
    
    class Meta:
        model = Restaurant
        fields = [
            'id', 'name', 'slug', 'logo', 'banner', 'description', 'email', 'phone',
            'address', 'city', 'state', 'country', 'postal_code', 'latitude', 'longitude', 'opening_time', 'closing_time',
            'rating', 'review_count', 'is_open_now', 'delivery_time_minutes', 'delivery_fee', 
            'min_order_amount', 'allows_pickup', 'allows_delivery', 'allows_dine_in', 
            'is_active', 'delivery_zones'
            # Removed 'is_featured'
        ]
    
    def get_is_open_now(self, obj):
        from django.utils import timezone
        current_time = timezone.now().time()
        return obj.opening_time <= current_time <= obj.closing_time




class RestaurantSettingsSerializer(serializers.ModelSerializer):
    """Serializer for restaurant owner to update settings"""
    class Meta:
        model = Restaurant
        fields = [
            'id', 'name', 'description', 'logo', 'banner', 'email', 'phone',
            'address', 'city', 'state', 'country', 'postal_code', 'latitude', 'longitude',
            'opening_time', 'closing_time', 'is_open',
            'allows_pickup', 'allows_delivery', 'allows_dine_in',
            'min_order_amount', 'delivery_fee', 'delivery_time_minutes', 'tax_rate',
            
        ]
        read_only_fields = ['id']

class RestaurantHolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantHoliday
        fields = ['id', 'holiday_date', 'reason', 'created_at']
        read_only_fields = ['created_at']

class RestaurantDeliveryZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantDeliveryZone
        fields = ['id', 'zone_name', 'delivery_fee', 'delivery_time_minutes', 'postal_codes', 'is_active']



class StaffMemberSerializer(serializers.ModelSerializer):
    """Serializer for managing restaurant staff"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    staff_email = serializers.EmailField(write_only=True, required=False)
    
    class Meta:
        model = RestaurantStaffMember
        fields = [
            'id', 'user_email', 'staff_email', 'role', 'is_active', 
            'can_manage_menu', 'can_manage_orders', 'can_manage_staff', 
            'can_manage_payments', 'can_view_analytics', 'created_at'
        ]
        read_only_fields = ['is_active', 'created_at']



class RestaurantTableSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantTable
        fields = ['id', 'table_number', 'capacity', 'is_active', 'qr_code_token', 'created_at']
        read_only_fields = ['qr_code_token', 'created_at']

class ReservationSerializer(serializers.ModelSerializer):
    customer_email = serializers.CharField(source='customer.email', read_only=True)
    customer_name = serializers.SerializerMethodField()
    customer_phone = serializers.SerializerMethodField()
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)
    table_number = serializers.CharField(source='table.table_number', read_only=True)

    class Meta:
        model = Reservation
        fields = [
            'id', 'restaurant', 'restaurant_name', 'customer', 'customer_email', 'customer_name', 'customer_phone',
            'table', 'table_number', 'reservation_time', 'party_size', 'status', 'special_requests', 'created_at'
        ]
        # A guest may pick a `table` when booking (checked in validate). After that, owners change it through
        # POST /reservations/{id}/assign-table/ and `status` through the action endpoints.
        read_only_fields = ['customer', 'status']
        extra_kwargs = {
            'party_size': {'min_value': 1, 'max_value': reservation_services.MAX_PARTY_SIZE},
        }

    def get_customer_name(self, obj):
        user = obj.customer
        name = f"{getattr(user, 'first_name', '') or ''} {getattr(user, 'last_name', '') or ''}".strip()
        return name or None

    def get_customer_phone(self, obj):
        user = obj.customer
        return getattr(user, 'phone', None) or getattr(user, 'phone_number', None) or None

    def validate(self, attrs):
        # Booking rules apply when a guest creates a reservation (changes after that go through the action endpoints).
        if self.instance is None:
            ok, reason = reservation_services.check_bookable(
                attrs['restaurant'], attrs['reservation_time'], attrs.get('party_size', 1)
            )
            if not ok:
                raise serializers.ValidationError({'reservation_time': reason})
            table = attrs.get('table')
            if table is not None:
                ok, reason = reservation_services.check_table(
                    attrs['restaurant'], table, attrs['reservation_time'], attrs.get('party_size', 1)
                )
                if not ok:
                    raise serializers.ValidationError({'table': f'Table {table.table_number} can\u2019t be booked: {reason}'})
        return attrs

class AvailableSlotsSerializer(serializers.Serializer):
    """Serializer for returning available time slots"""
    time = serializers.DateTimeField()
    is_available = serializers.BooleanField()
    reason = serializers.CharField(allow_blank=True, required=False)


class AvailableTableSerializer(serializers.Serializer):
    """One table in the guest's table picker."""
    id = serializers.CharField(source='table.pk')
    table_number = serializers.CharField(source='table.table_number')
    capacity = serializers.IntegerField(source='table.capacity')
    is_available = serializers.BooleanField()
    reason = serializers.CharField(allow_blank=True)