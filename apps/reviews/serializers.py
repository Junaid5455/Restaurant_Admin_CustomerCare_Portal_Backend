from rest_framework import serializers

from apps.orders.models import Order
from .models import Review

COMMENT_MAX = 1000
REPLY_MAX = 1000


def public_name(user):
    """"Sara M." (first name and last initial). Reviews are public, so never show an email address."""
    first = (getattr(user, 'first_name', '') or '').strip()
    last = (getattr(user, 'last_name', '') or '').strip()
    if first and last:
        return f'{first} {last[0]}.'
    return first or 'Guest'


class ReviewSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=COMMENT_MAX)

    class Meta:
        model = Review
        fields = [
            'id', 'restaurant', 'restaurant_name', 'customer_name', 'order', 'order_number',
            'rating', 'comment', 'owner_reply', 'replied_at', 'is_visible', 'created_at',
        ]
        # The restaurant comes from the order; replies and visibility have their own endpoints.
        read_only_fields = ['restaurant', 'owner_reply', 'replied_at', 'is_visible', 'created_at']

    def get_customer_name(self, obj):
        return public_name(obj.customer)

    def validate_order(self, order):
        request = self.context['request']
        if self.instance is not None:
            if order != self.instance.order:
                raise serializers.ValidationError('You can\'t move a review to another order.')
            return order
        if order.customer_id != request.user.id:
            raise serializers.ValidationError('You can only review your own orders.')
        if order.status != 'DELIVERED':
            raise serializers.ValidationError('You can review an order once it has been delivered.')
        if Review.objects.filter(order=order).exists():
            raise serializers.ValidationError('You already reviewed this order.')
        return order

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError('Choose a rating from 1 to 5.')
        return value


class ReplySerializer(serializers.Serializer):
    reply = serializers.CharField(allow_blank=True, max_length=REPLY_MAX)


class EligibleOrderSerializer(serializers.ModelSerializer):
    """A delivered order the guest hasn't reviewed yet."""
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'order_number', 'restaurant', 'restaurant_name', 'created_at']
