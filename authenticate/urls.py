
from django.urls import path
from .views import *

urlpatterns = [
    path('signup/',signup, name='signup'),
    # path('login/',login, name='login'),
    path('manage-route/',manage_route, name='create-route'),
    path('route/',manage_route, name='present-route'),
    path('contact-us/',contact_us_mail, name='contact_us'),

]
