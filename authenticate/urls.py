
from django.urls import path
from .views import *
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    # TokenRefreshView,
)

urlpatterns = [
    path('signup/',signup, name='signup'),
    path('send-otp-email/', send_otp_email_view, name='send_otp_email'),
    path('verify-otp-email/', verify_otp_email_view, name='verify_otp_email'),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    # path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('manage-route/',manage_route, name='create-route'),
    path('route/',manage_route, name='present-route'),
    path('contact-us/',contact_us_mail, name='contact_us'),

]
