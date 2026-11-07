from django.contrib.auth import get_user_model, authenticate
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from apps.users.models import EmailVerificationToken, PasswordResetToken
from django.utils import timezone
from apps.users.models import Campaign, SavedAddress, FavoriteRestaurant, FavoriteMenuItem, GiftCard
from apps.restaurants.serializers import RestaurantListSerializer
from apps.menu.serializers import MenuItemSerializer

from apps.users.models import (
    User, UserProfile, SavedAddress, FavoriteRestaurant, FavoriteMenuItem, 
    GiftCard, NotificationPreference, Notification
)



User = get_user_model()

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            'id', 'date_of_birth', 'gender', 'address', 'city', 
            'state', 'country', 'postal_code', 'loyalty_points', 
            'total_orders', 'total_spent'
        ]
        read_only_fields = ['id', 'loyalty_points', 'total_orders', 'total_spent']

class CustomUserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 
            'phone', 'role', 'profile_picture', 'is_active', 'date_joined', 'profile'
        ]
        # profile_picture is writable so a customer can upload their photo (PUT /users/me/ as multipart/form-data).
        read_only_fields = ['id', 'role', 'is_active', 'date_joined', 'profile']

    def validate_profile_picture(self, image):
        if image is None:
            return image
        if image.size > 5 * 1024 * 1024:
            raise serializers.ValidationError('The photo is larger than 5 MB.')
        content_type = getattr(image, 'content_type', '') or ''
        if content_type and content_type not in ('image/jpeg', 'image/png', 'image/webp', 'image/gif'):
            raise serializers.ValidationError('Upload a JPG, PNG, WebP or GIF image.')
        return image

class CustomUserCreateSerializer(CustomUserSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    password_confirm = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta(CustomUserSerializer.Meta):
        fields = CustomUserSerializer.Meta.fields + ['password', 'password_confirm']
        extra_kwargs = {
            'role': {'default': 'CUSTOMER'},
            'first_name': {'required': False},
            'last_name': {'required': False},
            'phone': {'required': False}
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password_confirm": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            user = authenticate(request=self.context.get('request'), username=email, password=password)
            
            if not user:
                raise serializers.ValidationError({"email": "Invalid credentials. User not found or password incorrect."})
            if not user.is_active:
                raise serializers.ValidationError({"email": "User account is disabled."})
            
            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError({"email": "Email and password are required."})

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True)
    new_password_confirm = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password_confirm": "New password fields didn't match."})
        return attrs



class EmailVerificationSerializer(serializers.Serializer):
    """Verify email with token"""
    token = serializers.CharField(max_length=255, required=True)
    
    def validate_token(self, value):
        try:
            token_obj = EmailVerificationToken.objects.get(token=value)
            if token_obj.is_used:
                raise serializers.ValidationError("This token has already been used.")
            if token_obj.is_expired():
                raise serializers.ValidationError("This token has expired.")
            return value
        except EmailVerificationToken.DoesNotExist:
            raise serializers.ValidationError("Invalid token.")

class ForgotPasswordSerializer(serializers.Serializer):
    """Request password reset"""
    email = serializers.EmailField(required=True)
    
    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email not found.")
        return value

class ResetPasswordSerializer(serializers.Serializer):
    """Reset password with token"""
    token = serializers.CharField(max_length=255, required=True)
    new_password = serializers.CharField(min_length=8, required=True)
    new_password_confirm = serializers.CharField(min_length=8, required=True)
    
    def validate(self, data):
        token = data.get('token')
        new_password = data.get('new_password')
        new_password_confirm = data.get('new_password_confirm')
        
        try:
            token_obj = PasswordResetToken.objects.get(token=token)
            if token_obj.is_used:
                raise serializers.ValidationError("This token has already been used.")
            if token_obj.is_expired():
                raise serializers.ValidationError("This token has expired.")
        except PasswordResetToken.DoesNotExist:
            raise serializers.ValidationError("Invalid token.")
        
        if new_password != new_password_confirm:
            raise serializers.ValidationError("Passwords do not match.")
        
        return data



class SavedAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedAddress
        fields = ['id', 'label', 'address', 'city', 'state', 'country', 'postal_code', 'latitude', 'longitude', 'is_default']
        read_only_fields = ['id']

    def create(self, validated_data):
        user = self.context['request'].user
        # If this is set as default, remove default from others
        if validated_data.get('is_default'):
            SavedAddress.objects.filter(user=user, is_default=True).update(is_default=False)
        return SavedAddress.objects.create(user=user, **validated_data)


class FavoriteRestaurantSerializer(serializers.ModelSerializer):
    restaurant = RestaurantListSerializer(read_only=True)
    restaurant_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = FavoriteRestaurant
        fields = ['id', 'restaurant', 'restaurant_id', 'created_at']
        read_only_fields = ['id', 'created_at']

class FavoriteMenuItemSerializer(serializers.ModelSerializer):
    menu_item = MenuItemSerializer(read_only=True)
    menu_item_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = FavoriteMenuItem
        fields = ['id', 'menu_item', 'menu_item_id', 'created_at']
        read_only_fields = ['id', 'created_at']

class GiftCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = GiftCard
        fields = ['id', 'code', 'initial_amount', 'balance', 'is_active', 'expires_at']
        read_only_fields = ['code', 'initial_amount', 'balance', 'is_active', 'expires_at']

class RewardSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['loyalty_points', 'total_orders', 'total_spent']





class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = ['id', 'email_promotions', 'sms_promotions', 'push_promotions', 'order_updates']

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'campaign', 'title', 'message', 'is_read', 'created_at']
        read_only_fields = ['campaign', 'title', 'message', 'created_at']

class CampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campaign
        fields = [
            'id', 'restaurant', 'name', 'channel', 'target_segment', 'subject', 
            'body', 'is_sent', 'sent_at', 'recipient_count', 'created_at'
        ]
        # Add 'restaurant' to read_only_fields so it doesn't demand it in the POST body
        read_only_fields = ['is_sent', 'sent_at', 'recipient_count', 'created_at', 'restaurant']