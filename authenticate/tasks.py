from celery import shared_task
from django.contrib.auth import get_user_model
import logging
from django.core.cache import cache


logger = logging.getLogger(__name__)
User = get_user_model()

@shared_task
def reset_search_friend(user_id):
    try:
        user = User.objects.get(id=user_id)
        user.search_friend = False
        user.save()
        cache_key = f'search_friend_{user_id}'
        cache.delete(cache_key)  # Remove from cache
        logger.info(f"Search friend status reset to False for user {user_id} ({user.username})")
    except User.DoesNotExist:
        logger.error(f"User with ID {user_id} not found while resetting search_friend.")
    except Exception as e:
        logger.error(f"Error resetting search_friend for user {user_id}: {str(e)}", exc_info=True)