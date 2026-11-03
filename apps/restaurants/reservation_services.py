"""
Booking rules for table reservations.

Save as:  apps/restaurants/reservation_services.py

Everything that decides "can this time be booked?" lives here so the serializer (on create), the
available-slots endpoint and the owner's assign-table action all give the same answer.

Assumptions about your models (they match the serializers you shared):
    Restaurant:        opening_time, closing_time (TimeField), is_active
    RestaurantHoliday: restaurant (FK), holiday_date (DateField)
    RestaurantTable:   restaurant (FK), table_number, capacity, is_active
    Reservation:       restaurant (FK), table (FK, null), reservation_time (DateTimeField), party_size, status
"""
from datetime import datetime, timedelta

from django.utils import timezone

from apps.restaurants.models import Reservation, RestaurantHoliday, RestaurantTable

# A booking occupies its table for this long, so a 7pm booking blocks 7pm to 9pm.
RESERVATION_DURATION = timedelta(hours=2)
# Distance between bookable start times.
SLOT_STEP = timedelta(hours=1)
# Guests can't book a table that starts sooner than this from now.
MIN_NOTICE = timedelta(minutes=30)
# A restaurant with no tables set up yet accepts this many overlapping bookings (the old rule was 5 per hour).
FALLBACK_CAPACITY = 5
MAX_PARTY_SIZE = 50

HOLD_STATUSES = ('PENDING', 'CONFIRMED')


def _aware(day, clock):
    return timezone.make_aware(datetime.combine(day, clock), timezone.get_current_timezone())


def opening_window(restaurant, day):
    """(opens, closes) as aware datetimes for the service day that starts on `day`. Closing after midnight is supported."""
    opens = _aware(day, restaurant.opening_time)
    closes = _aware(day, restaurant.closing_time)
    if closes <= opens:
        closes += timedelta(days=1)
    return opens, closes


def service_day_for(restaurant, when):
    """The calendar day whose opening hours cover `when`, or None. Handles a late night that belongs to yesterday's service."""
    local = timezone.localtime(when)
    for day in (local.date(), local.date() - timedelta(days=1)):
        opens, closes = opening_window(restaurant, day)
        if opens <= local < closes:
            return day
    return None


def is_holiday(restaurant, day):
    return RestaurantHoliday.objects.filter(restaurant=restaurant, holiday_date=day).exists()


def overlapping_bookings(restaurant, start, exclude_id=None):
    """Active bookings that would still be using a table at `start`."""
    qs = Reservation.objects.filter(
        restaurant=restaurant,
        status__in=HOLD_STATUSES,
        reservation_time__gt=start - RESERVATION_DURATION,
        reservation_time__lt=start + RESERVATION_DURATION,
    )
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    return qs


def check_bookable(restaurant, start, party_size=1, exclude_id=None, now=None):
    """Returns (ok, reason). `reason` is a message a guest can read, or '' when ok."""
    now = now or timezone.now()
    if not getattr(restaurant, 'is_active', True):
        return False, 'This restaurant is not taking bookings right now.'
    if party_size < 1 or party_size > MAX_PARTY_SIZE:
        return False, f'Party size must be between 1 and {MAX_PARTY_SIZE}.'
    if start < now + MIN_NOTICE:
        return False, 'Please choose a time at least 30 minutes from now.'

    day = service_day_for(restaurant, start)
    if day is None:
        return False, 'The restaurant is closed at that time.'
    if is_holiday(restaurant, day):
        return False, 'The restaurant is closed on that day.'

    tables = list(RestaurantTable.objects.filter(restaurant=restaurant, is_active=True))
    busy = list(overlapping_bookings(restaurant, start, exclude_id).values_list('table_id', flat=True))

    if not tables:
        # No tables set up yet: fall back to a simple limit so booking still works.
        if len(busy) >= FALLBACK_CAPACITY:
            return False, 'That time is fully booked.'
        return True, ''

    suitable = {t.pk for t in tables if t.capacity >= party_size}
    if not suitable:
        return False, 'We don\'t have a table that large. Please call the restaurant.'
    taken = {tid for tid in busy if tid in suitable}
    unassigned = sum(1 for tid in busy if tid is None)
    if len(suitable) - len(taken) - unassigned <= 0:
        return False, 'That time is fully booked.'
    return True, ''


def slots_for_day(restaurant, day, party_size=1, now=None):
    """Every bookable start time on `day`, as dicts: {time, is_available, reason}."""
    now = now or timezone.now()
    opens, closes = opening_window(restaurant, day)
    closed_all_day = is_holiday(restaurant, day)
    slots = []
    current = opens
    while current < closes:
        if closed_all_day:
            ok, reason = False, 'The restaurant is closed on that day.'
        else:
            ok, reason = check_bookable(restaurant, current, party_size, now=now)
        slots.append({'time': current, 'is_available': ok, 'reason': reason})
        current += SLOT_STEP
    return slots


def table_conflict(table, reservation):
    """True when `table` is already held by another active booking that overlaps `reservation`."""
    return Reservation.objects.filter(
        table=table,
        status__in=HOLD_STATUSES,
        reservation_time__gt=reservation.reservation_time - RESERVATION_DURATION,
        reservation_time__lt=reservation.reservation_time + RESERVATION_DURATION,
    ).exclude(pk=reservation.pk).exists()


def tables_for_slot(restaurant, start, party_size=1, exclude_id=None):
    """Every in-use table of `restaurant` as it stands at `start`, for the guest's table picker.

    Returns a list of {table, is_available, reason}. A table is not available when another pending or confirmed booking
    holds it around that time, when it is too small for the party, or when bookings that have no table yet will use up
    the tables that are left.
    """
    tables = list(RestaurantTable.objects.filter(restaurant=restaurant, is_active=True).order_by('table_number'))
    busy = list(overlapping_bookings(restaurant, start, exclude_id).values_list('table_id', flat=True))
    held = {tid for tid in busy if tid is not None}
    unassigned = sum(1 for tid in busy if tid is None)
    free_suitable = [t for t in tables if t.pk not in held and t.capacity >= party_size]
    crowded = len(free_suitable) - unassigned <= 0

    rows = []
    for t in tables:
        if t.pk in held:
            ok, reason = False, 'Already booked for this time.'
        elif t.capacity < party_size:
            ok, reason = False, f'Seats {t.capacity}, too small for {party_size}.'
        elif crowded:
            ok, reason = False, 'No table is free at this time.'
        else:
            ok, reason = True, ''
        rows.append({'table': t, 'is_available': ok, 'reason': reason})
    return rows


def check_table(restaurant, table, start, party_size=1, exclude_id=None):
    """Can this guest take this exact table at `start`? Returns (ok, reason)."""
    if table.restaurant_id != restaurant.pk:
        return False, 'That table belongs to another restaurant.'
    if not table.is_active:
        return False, 'That table is out of service.'
    for row in tables_for_slot(restaurant, start, party_size, exclude_id):
        if row['table'].pk == table.pk:
            return row['is_available'], row['reason']
    return False, 'That table is not available.'
