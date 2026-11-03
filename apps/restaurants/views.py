import secrets
import string
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView

from apps.common.permissions import CanManageRestaurant, IsRestaurantOwner
from apps.restaurants.models import Restaurant, RestaurantHoliday, RestaurantDeliveryZone, RestaurantStaffMember, RestaurantTable, Reservation
from apps.restaurants.serializers import RestaurantDetailSerializer, RestaurantListSerializer, RestaurantDeliveryZoneSerializer, RestaurantSettingsSerializer, RestaurantHolidaySerializer, StaffMemberSerializer,     RestaurantTableSerializer, ReservationSerializer, AvailableSlotsSerializer, AvailableTableSerializer

from apps.menu.models import MenuCategory
from apps.menu.serializers import MenuCategoryDetailSerializer
from rest_framework.exceptions import ValidationError
from apps.users.models import User

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.db import transaction
from datetime import timedelta

from apps.restaurants import reservation_services




class RestaurantViewSet(viewsets.ModelViewSet):
    queryset = Restaurant.objects.all()
    serializer_class = RestaurantDetailSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['allows_delivery', 'allows_pickup', 'is_active'] # Removed 'is_featured'
    search_fields = ['name', 'description', 'city', 'state']
    ordering_fields = ['name', 'rating', 'delivery_fee', 'created_at']
    pagination_class = PageNumberPagination

    def get_permissions(self):
        if self.action in ['create']:
            permission_classes = [IsRestaurantOwner]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [CanManageRestaurant]
        else:
            permission_classes = [IsAuthenticatedOrReadOnly]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == 'list':
            return RestaurantListSerializer
        if self.action == 'retrieve':
            return RestaurantDetailSerializer
        return RestaurantDetailSerializer

    def get_queryset(self):
        user = self.request.user
        
        # Owners managing their restaurant see all their own restaurants
        if user.is_authenticated and user.role == 'RESTAURANT_OWNER' and self.action in ['list', 'retrieve', 'update', 'partial_update', 'destroy']:
            return Restaurant.objects.filter(owner=user).select_related('owner').prefetch_related('delivery_zones')
            
        # Customers and Anonymous users only see active restaurants
        queryset = Restaurant.objects.filter(is_active=True).select_related('owner').prefetch_related('delivery_zones')
        
        # Filter by delivery availability
        delivery_only = self.request.query_params.get('delivery_only')
        if delivery_only and delivery_only.lower() == 'true':
            queryset = queryset.filter(allows_delivery=True)
            
        return queryset

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticatedOrReadOnly])
    def menu(self, request, pk=None):
        """Get restaurant menu (categories and their active items)"""
        restaurant = self.get_object()
        categories = MenuCategory.objects.filter(
            restaurant=restaurant,
            is_active=True
        ).prefetch_related('items')
        
        serializer = MenuCategoryDetailSerializer(categories, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticatedOrReadOnly])
    def delivery_zones(self, request, pk=None):
        """Get restaurant delivery zones"""
        restaurant = self.get_object()
        zones = RestaurantDeliveryZone.objects.filter(restaurant=restaurant, is_active=True)
        
        serializer = RestaurantDeliveryZoneSerializer(zones, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticatedOrReadOnly])
    def search(self, request):
        """Advanced restaurant search endpoint: /api/v1/restaurants/search/?q=query"""
        query = request.query_params.get('q', '')
        if len(query) < 2:
            return Response({'error': 'Search query too short (min 2 chars)'}, status=status.HTTP_400_BAD_REQUEST)
        
        restaurants = self.get_queryset().filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(city__icontains=query)
        )[:20]
        
        serializer = RestaurantListSerializer(restaurants, many=True)
        return Response({
            'restaurants': serializer.data,
            'count': len(restaurants)
        })




class RestaurantSettingsView(APIView):
    """Get or Update restaurant settings"""
    permission_classes = [IsAuthenticated, IsRestaurantOwner]

    def get(self, request):
        restaurant = get_object_or_404(Restaurant, owner=request.user)
        serializer = RestaurantSettingsSerializer(restaurant)
        return Response(serializer.data)

    def patch(self, request):
        restaurant = get_object_or_404(Restaurant, owner=request.user)
        serializer = RestaurantSettingsSerializer(restaurant, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class RestaurantHolidayViewSet(viewsets.ModelViewSet):
    """Manage restaurant holidays/closures"""
    serializer_class = RestaurantHolidaySerializer
    permission_classes = [IsAuthenticated, IsRestaurantOwner]

    def get_queryset(self):
        return RestaurantHoliday.objects.filter(restaurant__owner=self.request.user)

    def perform_create(self, serializer):
        restaurant = get_object_or_404(Restaurant, owner=self.request.user)
        serializer.save(restaurant=restaurant)

class RestaurantDeliveryZoneViewSet(viewsets.ModelViewSet):
    """Manage restaurant delivery zones"""
    serializer_class = RestaurantDeliveryZoneSerializer
    permission_classes = [IsAuthenticated, IsRestaurantOwner]

    def get_queryset(self):
        return RestaurantDeliveryZone.objects.filter(restaurant__owner=self.request.user)

    def perform_create(self, serializer):
        restaurant = get_object_or_404(Restaurant, owner=self.request.user)
        serializer.save(restaurant=restaurant)



class StaffMemberViewSet(viewsets.ModelViewSet):
    """Manage restaurant staff"""
    serializer_class = StaffMemberSerializer
    permission_classes = [IsAuthenticated, IsRestaurantOwner]

    def get_queryset(self):
        return RestaurantStaffMember.objects.filter(restaurant__owner=self.request.user)

    def perform_create(self, serializer):
        restaurant = get_object_or_404(Restaurant, owner=self.request.user)
        staff_email = self.request.data.get('staff_email')
        
        if not staff_email:
            raise ValidationError({"staff_email": "This field is required."})
            
        # Look for existing user, or create a new one if they don't exist
        user, created = User.objects.get_or_create(
            email=staff_email,
            defaults={
                'role': 'RESTAURANT_STAFF',
                'is_active': True
            }
        )
        
        # If the user was already a customer, upgrade their role to staff
        if not created and user.role not in ['RESTAURANT_STAFF', 'DELIVERY_STAFF', 'RESTAURANT_OWNER', 'SUPER_ADMIN']:
            user.role = 'RESTAURANT_STAFF'
            user.save()
            
        # Prevent duplicate staff entries
        if RestaurantStaffMember.objects.filter(restaurant=restaurant, user=user).exists():
            raise ValidationError("This user is already a staff member at your restaurant.")
        
        # Pop 'staff_email' from validated data so it doesn't get passed to the DB
        validated_data = serializer.validated_data
        validated_data.pop('staff_email', None)
            
        serializer.save(restaurant=restaurant, user=user)

    @action(detail=True, methods=['post'], url_path='toggle-active')
    def toggle_active(self, request, pk=None):
        """POST /api/v1/restaurants/staff/{id}/toggle-active/"""
        staff_member = self.get_object()
        staff_member.is_active = not staff_member.is_active
        staff_member.save()
        
        return Response({"is_active": staff_member.is_active}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='update-permissions')
    def update_permissions(self, request, pk=None):
        """POST /api/v1/restaurants/staff/{id}/update-permissions/"""
        staff_member = self.get_object()
        
        permissions = ['can_manage_menu', 'can_manage_orders', 'can_manage_staff', 'can_manage_payments', 'can_view_analytics']
        for perm in permissions:
            if perm in request.data:
                setattr(staff_member, perm, request.data[perm])
        
        staff_member.save()
        serializer = self.get_serializer(staff_member)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RestaurantTableViewSet(viewsets.ModelViewSet):
    """Manage restaurant tables"""
    serializer_class = RestaurantTableSerializer
    permission_classes = [IsAuthenticated, IsRestaurantOwner]

    def get_queryset(self):
        return RestaurantTable.objects.filter(restaurant__owner=self.request.user).order_by('table_number')

    def _my_restaurant(self):
        # An owner with several restaurants gets the oldest one instead of an error.
        restaurant = Restaurant.objects.filter(owner=self.request.user).order_by('created_at').first()
        if restaurant is None:
            raise ValidationError({'detail': 'Create your restaurant before adding tables.'})
        return restaurant

    def perform_create(self, serializer):
        restaurant = self._my_restaurant()
        number = serializer.validated_data.get('table_number')
        if RestaurantTable.objects.filter(restaurant=restaurant, table_number__iexact=number).exists():
            raise ValidationError({'table_number': ['Table with this table number already exists.']})
        serializer.save(restaurant=restaurant)

    def perform_destroy(self, instance):
        upcoming = Reservation.objects.filter(
            table=instance, status__in=reservation_services.HOLD_STATUSES, reservation_time__gte=timezone.now()
        ).count()
        if upcoming:
            raise ValidationError({'detail': f'This table has {upcoming} upcoming booking(s). Cancel or move them first, or pause the table instead.'})
        instance.delete()


class ReservationViewSet(viewsets.ModelViewSet):
    """
    Manage reservations.

    Guests create bookings (POST /) and cancel them. Owners confirm, cancel, assign a table, and mark a booking
    completed or no-show. Plain PUT/PATCH/DELETE are switched off so nobody can edit a booking's status or restaurant directly.
    """
    serializer_class = ReservationSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'options']

    # ---------- querysets ----------
    def get_queryset(self):
        user = self.request.user
        if user.role == 'CUSTOMER':
            qs = Reservation.objects.filter(customer=user)
        elif user.role == 'RESTAURANT_OWNER':
            qs = Reservation.objects.filter(restaurant__owner=user)
        elif user.role == 'SUPER_ADMIN':
            qs = Reservation.objects.all()
        else:
            return Reservation.objects.none()
        qs = qs.select_related('restaurant', 'table', 'customer')

        # Optional filters (only on the list endpoint): ?status=PENDING,CONFIRMED  ?date_from=2026-10-01  ?date_to=2026-10-31
        if self.action == 'list':
            params = self.request.query_params
            statuses = [s.strip().upper() for s in params.get('status', '').split(',') if s.strip()]
            if statuses:
                qs = qs.filter(status__in=statuses)
            for key, lookup in (('date_from', 'reservation_time__date__gte'), ('date_to', 'reservation_time__date__lte')):
                raw = params.get(key)
                if raw:
                    day = parse_date(raw)
                    if day is None:
                        raise ValidationError({key: 'Use the format YYYY-MM-DD.'})
                    qs = qs.filter(**{lookup: day})
        return qs.order_by('-reservation_time')

    # ---------- helpers ----------
    @staticmethod
    def _is_manager(user, reservation):
        return user.role == 'SUPER_ADMIN' or (user.role == 'RESTAURANT_OWNER' and reservation.restaurant.owner_id == user.id)

    @staticmethod
    def _bad(message, code=status.HTTP_400_BAD_REQUEST):
        return Response({'error': message}, status=code)

    def _manager_or_403(self, request, reservation):
        if not self._is_manager(request.user, reservation):
            return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)
        return None

    # ---------- create ----------
    def create(self, request, *args, **kwargs):
        if request.user.role != 'CUSTOMER':
            return Response({'error': 'Only guests can make bookings.'}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        data = serializer.validated_data
        table = data.get('table')
        with transaction.atomic():
            if table is not None:
                # Lock the table row and check again, so two guests choosing the same table at the same moment can't both get it.
                RestaurantTable.objects.select_for_update().get(pk=table.pk)
                ok, reason = reservation_services.check_table(data['restaurant'], table, data['reservation_time'], data.get('party_size', 1))
                if not ok:
                    raise ValidationError({'table': f'Table {table.table_number} was just taken: {reason}'})
            # Customers can only create pending reservations
            serializer.save(customer=self.request.user, status='PENDING')

    # ---------- availability ----------
    @action(detail=False, methods=['get'], url_path='available-slots')
    def available_slots(self, request):
        """GET /api/v1/restaurants/reservations/available-slots/?restaurant_id=uuid&date=2026-10-10&party_size=4"""
        restaurant_id = request.query_params.get('restaurant_id')
        date_str = request.query_params.get('date')
        if not restaurant_id or not date_str:
            return self._bad('restaurant_id and date are required')

        day = parse_date(date_str)
        if day is None:
            return self._bad('date must look like 2026-10-10')
        try:
            party_size = int(request.query_params.get('party_size', 1))
        except ValueError:
            return self._bad('party_size must be a whole number')

        try:
            restaurant = Restaurant.objects.get(id=restaurant_id, is_active=True)
        except (Restaurant.DoesNotExist, ValueError, DjangoValidationError):
            return self._bad('Restaurant not found', status.HTTP_404_NOT_FOUND)

        if day < timezone.localdate() or day > timezone.localdate() + timedelta(days=90):
            return self._bad('Choose a date from today up to 90 days ahead.')

        slots = reservation_services.slots_for_day(restaurant, day, party_size)
        return Response(AvailableSlotsSerializer(slots, many=True).data)

    @action(detail=False, methods=['get'], url_path='available-tables')
    def available_tables(self, request):
        """GET /api/v1/restaurants/reservations/available-tables/?restaurant_id=uuid&time=2026-10-10T19:00:00%2B05:00&party_size=4

        Every in-use table at the restaurant for that start time, each marked available or not (and why), so a guest can pick one.
        """
        restaurant_id = request.query_params.get('restaurant_id')
        time_str = request.query_params.get('time')
        if not restaurant_id or not time_str:
            return self._bad('restaurant_id and time are required')

        start = parse_datetime(time_str)
        if start is None:
            return self._bad('time must be a date and time, like 2026-10-10T19:00:00+05:00')
        if timezone.is_naive(start):
            start = timezone.make_aware(start, timezone.get_current_timezone())
        try:
            party_size = int(request.query_params.get('party_size', 1))
        except ValueError:
            return self._bad('party_size must be a whole number')

        try:
            restaurant = Restaurant.objects.get(id=restaurant_id, is_active=True)
        except (Restaurant.DoesNotExist, ValueError, DjangoValidationError):
            return self._bad('Restaurant not found', status.HTTP_404_NOT_FOUND)

        rows = reservation_services.tables_for_slot(restaurant, start, party_size)
        return Response(AvailableTableSerializer(rows, many=True).data)

    # ---------- owner / guest actions ----------
    @action(detail=True, methods=['post'], url_path='confirm')
    def confirm_reservation(self, request, pk=None):
        """POST /api/v1/restaurants/reservations/{id}/confirm/ (owner only)"""
        reservation = self.get_object()
        denied = self._manager_or_403(request, reservation)
        if denied:
            return denied
        if reservation.status != 'PENDING':
            return self._bad(f'Only a pending booking can be confirmed (this one is {reservation.status.lower()}).')
        reservation.status = 'CONFIRMED'
        reservation.save(update_fields=['status'])
        return Response(ReservationSerializer(reservation).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel_reservation(self, request, pk=None):
        """POST /api/v1/restaurants/reservations/{id}/cancel/"""
        reservation = self.get_object()
        is_guest = request.user == reservation.customer
        if not is_guest and not self._is_manager(request.user, reservation):
            return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)
        if reservation.status not in reservation_services.HOLD_STATUSES:
            return self._bad(f'This booking is already {reservation.status.lower().replace("_", " ")}.')
        if is_guest and reservation.reservation_time < timezone.now():
            return self._bad('This booking has already started. Please contact the restaurant.')
        reservation.status = 'CANCELLED'
        reservation.save(update_fields=['status'])
        return Response({'message': 'Reservation cancelled'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='assign-table')
    def assign_table(self, request, pk=None):
        """POST /api/v1/restaurants/reservations/{id}/assign-table/  body: {"table": "<table uuid>"}  (null clears it)"""
        reservation = self.get_object()
        denied = self._manager_or_403(request, reservation)
        if denied:
            return denied
        if reservation.status not in reservation_services.HOLD_STATUSES:
            return self._bad('Tables can only be assigned to pending or confirmed bookings.')
        if 'table' not in request.data:
            return self._bad('table is required (send null to clear it).')

        table_id = request.data.get('table')
        if table_id in (None, ''):
            reservation.table = None
            reservation.save(update_fields=['table'])
            return Response(ReservationSerializer(reservation).data, status=status.HTTP_200_OK)

        try:
            table = RestaurantTable.objects.get(pk=table_id, restaurant=reservation.restaurant)
        except (RestaurantTable.DoesNotExist, ValueError, DjangoValidationError):
            return self._bad('That table does not belong to this restaurant.')
        if not table.is_active:
            return self._bad(f'Table {table.table_number} is out of service.')
        if table.capacity < reservation.party_size:
            return self._bad(f'Table {table.table_number} seats {table.capacity}, but this booking is for {reservation.party_size}.')
        if reservation_services.table_conflict(table, reservation):
            return self._bad(f'Table {table.table_number} is already booked around that time.')
        reservation.table = table
        reservation.save(update_fields=['table'])
        return Response(ReservationSerializer(reservation).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='complete')
    def complete_reservation(self, request, pk=None):
        """POST /api/v1/restaurants/reservations/{id}/complete/  Guests came and ate (owner only)"""
        reservation = self.get_object()
        denied = self._manager_or_403(request, reservation)
        if denied:
            return denied
        if reservation.status != 'CONFIRMED':
            return self._bad('Only a confirmed booking can be marked completed.')
        if reservation.reservation_time > timezone.now() + timedelta(minutes=30):
            return self._bad('This booking has not started yet.')
        reservation.status = 'COMPLETED'
        reservation.save(update_fields=['status'])
        return Response(ReservationSerializer(reservation).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='no-show')
    def no_show_reservation(self, request, pk=None):
        """POST /api/v1/restaurants/reservations/{id}/no-show/  Guests never arrived (owner only)"""
        reservation = self.get_object()
        denied = self._manager_or_403(request, reservation)
        if denied:
            return denied
        if reservation.status not in reservation_services.HOLD_STATUSES:
            return self._bad('Only a pending or confirmed booking can be marked no-show.')
        if reservation.reservation_time > timezone.now():
            return self._bad('This booking has not started yet.')
        reservation.status = 'NO_SHOW'
        reservation.save(update_fields=['status'])
        return Response(ReservationSerializer(reservation).data, status=status.HTTP_200_OK)
