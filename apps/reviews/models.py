from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.common.models import BaseModel
from apps.orders.models import Order
from apps.restaurants.models import Restaurant


class Review(BaseModel):
    """A guest's rating of one delivered order. One review per order."""
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='reviews')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='review')
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True, default='')
    owner_reply = models.TextField(blank=True, default='')
    replied_at = models.DateTimeField(null=True, blank=True)
    # The platform team can hide a review (abuse, spam). Hidden reviews don't count toward the restaurant's rating.
    is_visible = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['restaurant', 'is_visible']),
            models.Index(fields=['rating']),
        ]

    def __str__(self):
        return f'{self.rating}★ for {self.restaurant_id} by {self.customer_id}'
