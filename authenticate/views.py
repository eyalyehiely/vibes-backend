import logging,time,openai,ssl,certifi,smtplib,os
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated,AllowAny
from .serializers import *
from .models import *
from .utils import *
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import logout as logout_method
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny,IsAuthenticated
from rest_framework import status
from .utils import generate_and_send_otp, verify_otp, can_request_otp
from rest_framework_simplejwt.tokens import RefreshToken
from django_ratelimit.decorators import ratelimit
from vibes.settings import EMAIL_HOST_USER, EMAIL_HOST_PASSWORD
from django.utils import timezone
from django.core.cache import cache
from email.message import EmailMessage

users_logger = logging.getLogger('users')

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

    


@api_view(['POST'])
def signup(request):
    # Get common data from request
    username = request.data.get('phone_number')
    first_name = request.data.get('first_name')
    last_name = request.data.get('last_name')
    gender = request.data.get('gender')
    birth_date = request.data.get('birth_date')


    # Check if the user with the username already exists
    if CustomUser.objects.filter(username=username).exists():
        return Response({'error': 'User with this phone number already exists.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        if not validate_phone_number(username):
            return Response({'error': 'Invalid phone number'}, status=status.HTTP_400_BAD_REQUEST)
            # Create the CustomUser instance 
        user = CustomUser.objects.create(
            username=username,  # Use phone number as the username
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            birth_date=birth_date
        )
        user.save()
          
        # Create a refresh token and add custom claims
        refresh = RefreshToken.for_user(user)
        refresh['first_name'] = first_name 
        refresh['last_name'] = last_name 
        refresh['user_id'] = str(user.id)

        access = refresh.access_token
        users_logger.debug(f'{username} created successfully')
        
        # Return the response with JWT tokens
        return Response({
            'status': 201,
            'user_id': user.id,
            'refresh': str(refresh),
            'access': str(access)
        }, status=status.HTTP_201_CREATED)

   
    except Exception as e:
        users_logger.error(f"Error creating user: {e}")
        return Response({"message": f"An error occurred while creating the user, {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    logout_method(request)
    users_logger.debug(f"User {request.user.username} logged out.")
    return Response({"message": "User logged out successfully."}, status=status.HTTP_200_OK)


@api_view(['POST'])
@ratelimit(key='ip', rate='5/m', method='POST', block=True)
@permission_classes([AllowAny]) 
def send_otp_email_view(request):
    start_time = time.time()
    logger.info("Received request to send OTP email.")
    serializer = EmailSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['username']
        logger.debug(f"Validated email: {email}")
        try:
            user = CustomUser.objects.filter(username=email).first()
            if user:
                logger.info(f"Found existing user for email: {email}")
            else:
                logger.info(f"No existing user found for email: {email}.")
                return Response({"detail": "User doesnt exist."}, status=status.HTTP_404_NOT_FOUND)
                # user = User.objects.create(username=email)
                # user.set_unusable_password()
                # user.save()
                # logger.debug(f"Created new user with email: {email}")
                


        except Exception as e:
            logger.error(f"Error querying or creating user for email {email}: {str(e)}")
            return Response({"detail": "Internal server error."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # if not can_request_otp(user):
        #     logger.warning(f"OTP request limit exceeded for user: {email}")
        #     return Response(
        #         {"detail": "OTP request limit exceeded. Please try again later."},
        #         status=status.HTTP_429_TOO_MANY_REQUESTS
        #     )

        try:
            generate_and_send_otp(user)
            users_logger.info(f"OTP generated and sent to email: {email}")
            end_time = time.time()  # Capture end time
            print(f"Function execution time: {end_time - start_time} seconds")
            return Response({"detail": "OTP sent successfully to your email."}, status=status.HTTP_200_OK)
        except Exception as e:
            users_logger.error(f"Failed to send OTP to email {email}: {str(e)}")
            return Response({"detail": "Failed to send OTP. Please try again later."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    users_logger.warning(f"Invalid serializer data: {serializer.errors}")
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



@api_view(['POST'])
@permission_classes([AllowAny])  # Allow unauthenticated users to verify OTPs
def verify_otp_email_view(request):
    start_time = time.time()
    users_logger.info("Received request to verify OTP.")
    serializer = OTPSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']
        users_logger.debug(f"Validated data - Email: {email}, OTP Code: {otp}")

        try:
            user = User.objects.filter(username=email).first()
            users_logger.info(f"Found user for OTP verification: {email}")
        except User.DoesNotExist:
            users_logger.warning(f"User with email {email} does not exist.")
            return Response({"detail": "User with this email does not exist."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            success, message = verify_otp(user,otp)
            print('success',success)
            if success:
                users_logger.info(f"OTP verified successfully for user: {email}")
                # Generate JWT tokens
                refresh = RefreshToken.for_user(user)
                refresh['username'] = user.username
                refresh['user_id'] = str(user.id)
                access_token = str(refresh.access_token)
                users_logger.debug(f"Generated JWT tokens for user: {email}")
                end_time = time.time()
                print(f"Function execution time: {end_time - start_time} seconds")
                return Response({
                    "detail": message,
                   'refresh': str(refresh),
                    'access': access_token
                }, status=status.HTTP_200_OK)
                

            else:
                users_logger.warning(f"OTP verification failed for user: {email}. Reason: {message}")
                return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            users_logger.error(f"Error during OTP verification for user {email}: {str(e)}")
            return Response({"detail": "Internal server error during OTP verification."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    users_logger.warning(f"Invalid serializer data: {serializer.errors}")
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def user_details(request, user_id):
    users_logger.info(f"Received {request.method} request for user: {user_id}")

    try:
        user = CustomUser.objects.filter(id=user_id).first()
        if not user:
            users_logger.warning(f"User {user_id} not found")
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        users_logger.error(f"Exception while retrieving user: {e}")
        return Response({'error': 'Server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Handle GET request
    if request.method == 'GET':
        users_logger.info(f"Attempting to retrieve details for user {user_id}")
        serializer = CustomUserSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Handle PUT request
    elif request.method == 'PUT':
        users_logger.info(f"Attempting to update details for user {user_id}")
        serializer = CustomUserSerializer(user, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            users_logger.info(f"User {user_id} updated successfully")
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            users_logger.warning(f"Validation failed for user {user_id}: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Handle DELETE request
    elif request.method == 'DELETE':
        try:
            user.delete()
            users_logger.info(f"User {user_id} deleted successfully")
            return Response({'message': 'User deleted successfully!'}, status=status.HTTP_200_OK)
        except Exception as e:
            users_logger.error(f"Error deleting user {user_id}: {e}")
            return Response({'error': 'Error deleting user from the database'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

@api_view(['POST','GET'])
# @permission_classes([AllowAny])
def manage_route(request):
    openai.api_key = os.getenv('OPEN_AI_API')
    user = request.user

    if request.method == 'POST':
        # if not request.user.is_authenticated:
        #     return Response({"error": "Authentication is required."}, status=401)

        # Extract data from the request
        time = request.data.get('time', '')
        company = request.data.get('company', '')
        cost = request.data.get('cost', '')
        kind_of_activity = request.data.get('kind_of_activity', '')
        area = request.data.get('area', '')

        logger.info(f"Parameters: time={time}, company={company}, cost={cost}, kind_of_activity={kind_of_activity}, area={area}")

        # Cache key for activity data
        cache_key = f"activity_data_{user.id}"
        activity_data = cache.get(cache_key, [])

        try:
            # Format user input for the AI
            route_user_message = (
                f"Hi chat, I want you to build an activity for {time} with {company}. "
                f"The estimated cost for the activity should be {cost}. "
                f"The kind of activity I want to do is {kind_of_activity}, and the area should be {area}."
            )

            # Call OpenAI API for conversation
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": route_user_message},
                ],
                max_tokens=150,
                temperature=0.7,
            )

            ai_message = response['choices'][0]['message']['content'].strip()
            logger.info(f"OpenAI response: {ai_message}")

            # Append activity data and cache it
            new_activity = {
                'time': time,
                'company': company,
                'cost': cost,
                'kind_of_activity': kind_of_activity,
                'area': area,
                'ai_suggestion': ai_message,
                'timestamp': timezone.now().isoformat(),
            }
            activity_data.append(new_activity)
            cache.set(cache_key, activity_data, timeout=600)  # Cache for 10 minutes

            # Save activity to the database
            Activity.objects.create(
                user=user,  # Fixed user assignment
                activity_type=kind_of_activity.upper().replace(" ", "_"),
                title=f"Suggested Activity for {time}",
                time=time,
                cost=float(cost) if cost else None,  # Fixed cost handling
                area=area,
                company=company,
                ai_suggestion=ai_message,
            )

            return Response({'user_input': route_user_message, 'ai_response': ai_message}, status=200)

        except Exception as e:
            logger.error(f"Error occurred for user {user.username if user.is_authenticated else 'Anonymous'}: {str(e)}", exc_info=True)
            return Response({'error': str(e)}, status=500)
    elif request.method == 'GET':
            # Cache key for activity data
            cache_key = f"activity_data_{user.id}"
            
            # Check for cached data
            activity_data = cache.get(cache_key)
            if activity_data:
                return Response({'activities': activity_data}, status=200)

            # If no cache, fetch activities from the database
            activities = Activity.objects.filter(user=user).order_by('-created_at')
            activity_list = [
                {
                    'id': activity.id,
                    'title': activity.title,
                    'type': activity.activity_type,
                    'time': activity.time,
                    'price': activity.price,
                    'area': activity.area,
                    'company': activity.company,
                    'created_at': activity.created_at.isoformat(),
                }
                for activity in activities
            ]

            # Cache the data for future requests
            cache.set(cache_key, activity_list, timeout=600)  # Cache for 10 minutes
            return Response({'activities': activity_list}, status=200)






@api_view(['POST'])
@permission_classes([IsAuthenticated])
def contact_us_mail(request):
    start_time = time.time()  # Track start time

    # Get data from the request
    contact_message = request.data.get('contactMessage')
    contact_subject = request.data.get('contactSubject')
    sender = request.user.username

    if not contact_message or not contact_subject or not sender:
        logger.error("Invalid request: missing required fields")
        return Response({"error": "Missing Message, Subject, or sender"}, status=400)

    # Build the email message
    msg = EmailMessage()
    msg.set_content(f"A message from: {sender}\n The message: {contact_message}")
    msg['Subject'] = contact_subject
    msg['From'] = EMAIL_HOST_USER
    msg['To'] = EMAIL_HOST_USER

    context = ssl.create_default_context(cafile=certifi.where())

    try:
        # Send the email
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as server:
            server.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
            server.send_message(msg)

        # Log success
        logger.info(f"Email sent successfully from {sender} to {EMAIL_HOST_USER}.")
        end_time = time.time()  # Track end time
        logger.info(f"Function execution time: {end_time - start_time} seconds")

        # Return success response
        return Response({"message": "Email sent successfully"}, status=200)

    except Exception as e:
        # Log the error
        logger.error(f"Failed to send email: {e}", exc_info=True)
        return Response({"error": "Failed to send email"}, status=500)


    





# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def get_nearby_places(request):
#     start_time = time.time()

#     # Get the latitude, longitude, radius, and category from the request
#     user_lat = request.GET.get('latitude')
#     user_lng = request.GET.get('longitude')
#     radius = request.GET.get('radius', 3000)  # Default radius is 3km
#     category = request.GET.get('category', '')

#     # Log the received parameters
#     place_users_logger.info(f"Received parameters: Latitude: {user_lat}, Longitude: {user_lng}, Radius: {radius}, Category: {category}")

#     # Validate latitude and longitude
#     if not user_lat or not user_lng:
#         place_users_logger.error("Missing latitude or longitude in request")
#         return Response({'error': 'Missing latitude or longitude'}, status=400)

#     # Map categories to Google Places types
#     category_map = {
#         'Restaurants': 'restaurant',
#         'Attractions': 'tourist_attraction',
#         'Accommodations': 'lodging'
#     }
#     place_type = category_map.get(category, None)

#     # Google Places API URL
#     google_places_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

#     # Parameters to pass to the Google Places API
#     params = {
#         'location': f'{user_lat},{user_lng}',
#         'radius': radius,
#         'key': GOOGLE_PLACES_API_KEY
#     }

#     # Add category type if available
#     if place_type:
#         params['type'] = place_type

#     # Log the outgoing API request
#     place_users_logger.info(f"Making request to Google Places API with params: {params}")

#     # Make the request to the Google Places API
#     try:
#         response = requests.get(google_places_url, params=params)
#         response.raise_for_status()  # Raise an exception if the response code is not 200
#     except requests.RequestException as e:
#         place_users_logger.error(f"Error fetching data from Google Places API: {e}")
#         return Response({'error': 'Failed to fetch data from Google Places API'}, status=500)

#     places_data = response.json()

#     # Log the response from Google Places API
#     place_users_logger.info(f"Google Places API response status: {response.status_code}, Data: {places_data}")

#     # Extract relevant data from the response
#     results = []
#     if 'results' in places_data:
#         for place in places_data['results']:
#             place_location = place.get('geometry', {}).get('location', {})
#             place_lat = place_location.get('lat')
#             place_lng = place_location.get('lng')

#             if place_lat and place_lng:
#                 # Calculate the distance between the user's location and the place
#                 distance = haversine(float(user_lat), float(user_lng), place_lat, place_lng)
#             else:
#                 distance = None

#             if distance <= float(radius):
#                 place_info = {
#                     'id':place.get('place_id'),
#                     'name': place.get('name'),
#                     'type': place.get('types', []),
#                     'location': place_location,
#                     'distance': f"{distance:.2f} km" if distance is not None else 'Unknown',
#                     'rating': place.get('rating', 'No rating available'),
#                     'opening_hours': place.get('opening_hours', {}).get('open_now', 'No hours available')
#                 }
#                 results.append(place_info)

#     # Log the number of places found
#     place_users_logger.info(f"Found {len(results)} places near location: {user_lat}, {user_lng}")

#     # Return the data as JSON
#     end_time = time.time()
#     place_users_logger.info(f"Function execution time: {end_time - start_time} seconds")
#     return Response({'places': results}, status=200)

