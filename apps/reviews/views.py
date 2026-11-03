import uuid

from django.db.models import Avg, Count
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.orders.models import Order
from apps.restaurants.models import Restaurant
from .models import Review
from .serializers import EligibleOrderSerializer, ReplySerializer, ReviewSerializer

OWNER = 'RESTAURANT_OWNER'
ADMIN = 'SUPER_ADMIN'
CUSTOMER = 'CUSTOMER'


def _bool(value):
    return {'true': True, '1': True, 'false': False, '0': False}.get(str(value).lower()) if value is not None else None


class ReviewViewSet(viewsets.ModelViewSet):
    """
    Reviews of delivered orders.

    - Anyone can read the visible reviews of one restaurant:  GET /reviews/?restaurant=<id>
    - Guests create (POST), edit (PATCH) and delete their own reviews. A review is locked once the restaurant replies.
    - Owners see every review of their restaurants and answer them with POST /reviews/{id}/reply/.
    - The platform team can hide a review with POST /reviews/{id}/moderate/.
    """
    serializer_class = ReviewSerializer
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    # ---------- permissions ----------
    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'summary'):
            return [AllowAny()]
        return [IsAuthenticated()]

    # ---------- querysets ----------
    def _restaurant_param(self):
        raw = self.request.query_params.get('restaurant')
        if not raw:
            return None
        try:
            return str(uuid.UUID(raw))
        except ValueError:
            raise ValidationError({'restaurant': 'Not a valid restaurant id.'})

    def _scope(self):
        """Which reviews this person may see, before the ?rating= and ?replied= filters."""
        user = self.request.user
        role = getattr(user, 'role', None) if user.is_authenticated else None
        restaurant_id = self._restaurant_param()
        qs = Review.objects.select_related('restaurant', 'customer', 'order')
        reading = self.action in ('list', 'retrieve', 'summary')

        # Anyone can read one restaurant's visible reviews, unless they run that restaurant (or the platform).
        if reading and restaurant_id:
            manages = role == ADMIN or (role == OWNER and Restaurant.objects.filter(pk=restaurant_id, owner=user).exists())
            if not manages:
                return qs.filter(restaurant_id=restaurant_id, is_visible=True)

        if role == CUSTOMER:
            qs = qs.filter(customer=user)
        elif role == OWNER:
            qs = qs.filter(restaurant__owner=user)
        elif role == ADMIN:
            pass
        elif self.action == 'retrieve':
            qs = qs.filter(is_visible=True)  # signed out: a single public review by id
        else:
            return Review.objects.none()

        if restaurant_id and self.action in ('list', 'summary'):
            qs = qs.filter(restaurant_id=restaurant_id)
        return qs

    def get_queryset(self):
        qs = self._scope()
        if self.action == 'list':
            params = self.request.query_params
            if params.get('rating', '').isdigit():
                qs = qs.filter(rating=int(params['rating']))
            replied = _bool(params.get('replied'))
            if replied is True:
                qs = qs.exclude(owner_reply='')
            elif replied is False:
                qs = qs.filter(owner_reply='')
        return qs.order_by('-created_at')

    # ---------- guest: create / edit / delete ----------
    def create(self, request, *args, **kwargs):
        if request.user.role != CUSTOMER:
            raise PermissionDenied('Only guests can write reviews.')
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        order = serializer.validated_data['order']
        serializer.save(customer=self.request.user, restaurant=order.restaurant)

    def update(self, request, *args, **kwargs):
        review = self.get_object()
        if review.customer_id != request.user.id:
            raise PermissionDenied('You can only edit your own review.')
        if review.owner_reply:
            raise ValidationError({'detail': 'The restaurant has replied, so this review can no longer be edited.'})
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        review = self.get_object()
        if review.customer_id != request.user.id and request.user.role != ADMIN:
            raise PermissionDenied('You can only delete your own review.')
        return super().destroy(request, *args, **kwargs)

    # ---------- guest: what can I still review? ----------
    @action(detail=False, methods=['get'], url_path='eligible')
    def eligible(self, request):
        """GET /reviews/eligible/ - delivered orders the guest has not reviewed yet (newest first, up to 50)."""
        if request.user.role != CUSTOMER:
            return Response([])
        orders = (
            Order.objects.filter(customer=request.user, status='DELIVERED', review__isnull=True)
            .select_related('restaurant')
            .order_by('-created_at')[:50]
        )
        return Response(EligibleOrderSerializer(orders, many=True).data)

    # ---------- everyone: rating summary ----------
    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        """GET /reviews/summary/?restaurant=<id> - average, count, 1-5 star breakdown and reply counts."""
        role = getattr(request.user, 'role', None) if request.user.is_authenticated else None
        if not request.query_params.get('restaurant') and role not in (OWNER, ADMIN):
            raise ValidationError({'restaurant': 'restaurant is required.'})
        base = self._scope()
        stats = base.aggregate(avg=Avg('rating'), n=Count('id'))
        dist = {str(i): 0 for i in range(1, 6)}
        for row in base.order_by().values('rating').annotate(c=Count('id')):
            dist[str(row['rating'])] = row['c']
        replied = base.exclude(owner_reply='').count()
        return Response({
            'average': round(stats['avg'], 2) if stats['avg'] is not None else 0,
            'total': stats['n'],
            'distribution': dist,
            'replied': replied,
            'awaiting_reply': stats['n'] - replied,
        })

    # ---------- owner: reply ----------
    @action(detail=True, methods=['post'], url_path='reply')
    def reply(self, request, pk=None):
        """POST /reviews/{id}/reply/  {"reply": "Thank you!"}  (an empty reply removes it)"""
        review = self.get_object()
        if request.user.role != ADMIN and review.restaurant.owner_id != request.user.id:
            raise PermissionDenied('Only the restaurant owner can reply.')
        data = ReplySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        text = data.validated_data['reply'].strip()
        review.owner_reply = text
        review.replied_at = timezone.now() if text else None
        review.save()
        return Response(ReviewSerializer(review, context={'request': request}).data, status=status.HTTP_200_OK)

    # ---------- platform team: hide / show ----------
    @action(detail=True, methods=['post'], url_path='moderate')
    def moderate(self, request, pk=None):
        """POST /reviews/{id}/moderate/  {"is_visible": false}  (platform team only)"""
        if request.user.role != ADMIN:
            raise PermissionDenied('Only the platform team can hide reviews.')
        review = self.get_object()
        value = _bool(request.data.get('is_visible'))
        if value is None:
            raise ValidationError({'is_visible': 'Send true or false.'})
        review.is_visible = value
        review.save()
        return Response(ReviewSerializer(review, context={'request': request}).data, status=status.HTTP_200_OK)
