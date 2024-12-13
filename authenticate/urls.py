
from django.urls import path
from .views import *
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    # TokenRefreshView,
)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('signup/',signup, name='signup'),
    path('send-otp-email/', send_otp_email_view, name='send_otp_email'),
    path('verify-otp-email/', verify_otp_email_view, name='verify_otp_email'),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('user/<uuid:user_id>/',user_details, name='user_details'),
    # path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('manage-route/',manage_route, name='create-route'),
    path('route/<uuid:route_id>/',route_details, name='present-route'),
    path('contact-us/',contact_us_mail, name='contact_us'),
    path('manage-profile-pic/<uuid:user_id>/',manage_profile_pic, name='manage_profile_pic'),
    path('manage-favorites/<uuid:user_id>/',manage_favorite_place, name='manage_favorite_place'),
    path('get-nearby-places/',get_nearby_places ,name='get_nearby_places'),
    path('save-user-location/',save_user_location ,name='save_user_location'),

]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

