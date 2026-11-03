from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import Http404
from django.shortcuts import get_object_or_404

from apps.orders.models import Order
from apps.restaurants.models import Restaurant, RestaurantStaffMember
from apps.kitchen.serializers import KitchenOrderSerializer
from apps.common.permissions import IsRestaurantStaffOrOwner

class KitchenOrderViewSet(viewsets.GenericViewSet):
    """Endpoints for the Kitchen Display System (KDS)"""
    serializer_class = KitchenOrderSerializer
    permission_classes = [IsAuthenticated, IsRestaurantStaffOrOwner]

    def get_queryset(self):
        user = self.request.user
        
        # Find the restaurant the staff member belongs to
        if user.role == 'RESTAURANT_OWNER':
            # An owner may have more than one restaurant; show the first (oldest) one.
            restaurant = Restaurant.objects.filter(owner=user).order_by('created_at').first()
            if restaurant is None:
                raise Http404('No restaurant is linked to this account.')
        else: # RESTAURANT_STAFF
            staff_member = get_object_or_404(RestaurantStaffMember, user=user)
            restaurant = staff_member.restaurant

        # KDS only cares about orders currently in the kitchen (CONFIRMED or PREPARING)
        return Order.objects.filter(
            restaurant=restaurant, 
            status__in=['CONFIRMED', 'PREPARING']
        ).prefetch_related('items__customizations', 'items__addons').order_by('placed_at')

    def list(self, request):
        """GET /api/v1/kitchen/orders/ - Get active orders for the kitchen"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='start')
    def start_preparation(self, request, pk=None):
        """POST /api/v1/kitchen/orders/{id}/start/ - Mark order as PREPARING"""
        order = self.get_object()
        
        if order.status != 'CONFIRMED':
            return Response({"error": f"Order must be CONFIRMED to start. Current: {order.status}"}, status=status.HTTP_400_BAD_REQUEST)
            
        order.update_status('PREPARING')
        serializer = self.get_serializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='ready')
    def mark_ready(self, request, pk=None):
        """POST /api/v1/kitchen/orders/{id}/ready/ - Mark order as READY for pickup/delivery"""
        order = self.get_object()
        
        if order.status != 'PREPARING':
            return Response({"error": f"Order must be PREPARING to mark as ready. Current: {order.status}"}, status=status.HTTP_400_BAD_REQUEST)
            
        order.update_status('READY')
        serializer = self.get_serializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)