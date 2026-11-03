from django.db.models import Avg, Count
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.restaurants.models import Restaurant
from .models import Review


def refresh_restaurant_rating(restaurant_id):
    """Recompute the restaurant's average rating and review count from its visible reviews."""
    stats = Review.objects.filter(restaurant_id=restaurant_id, is_visible=True).aggregate(avg=Avg('rating'), n=Count('id'))
    average = round(stats['avg'], 2) if stats['avg'] is not None else 0
    # update() on purpose: no signals, no side effects on other restaurant fields.
    Restaurant.objects.filter(pk=restaurant_id).update(rating=average, total_reviews=stats['n'])


@receiver(post_save, sender=Review)
def review_saved(sender, instance, **kwargs):
    refresh_restaurant_rating(instance.restaurant_id)


@receiver(post_delete, sender=Review)
def review_deleted(sender, instance, **kwargs):
    refresh_restaurant_rating(instance.restaurant_id)
