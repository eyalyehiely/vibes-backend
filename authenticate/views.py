
from django.shortcuts import get_object_or_404
import logging,time,openai,os,requests,json,datetime,uuid
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
from rest_framework_simplejwt.tokens import RefreshToken
from django_ratelimit.decorators import ratelimit
from django.utils import timezone
from django.core.cache import cache
from django.utils.timezone import make_aware
from dateutil.parser import parse
from django.db.models import Q

GOOGLE_PLACES_API_KEY=os.getenv('GOOGLE_PLACES_API_KEY')
users_logger = logging.getLogger('users')

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

    


@api_view(['POST'])
def signup(request):
    start_time = time.time()
    # Get common data from request
    username = request.data.get('email')
    first_name = request.data.get('first_name')
    last_name = request.data.get('last_name')
    gender = request.data.get('gender')
    birth_date = request.data.get('birth_date')


    # Check if the user with the username already exists
    if CustomUser.objects.filter(username=username).exists():
        return Response({'error': 'User with this phone number already exists.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # if not validate_phone_number(username):
        #     return Response({'error': 'Invalid phone number'}, status=status.HTTP_400_BAD_REQUEST)
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
        signup_email(user=user)
        end_time = time.time()
        users_logger.info('total time', {start_time-end_time})
        
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
    users_logger.info("Received request to send OTP email.")
    serializer = EmailSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['username']
        users_logger.debug(f"Validated email: {email}")
        try:
            user = CustomUser.objects.filter(username=email).first()
            if user:
                users_logger.info(f"Found existing user for email: {email}")
            else:
                users_logger.info(f"No existing user found for email: {email}.")
                return Response({"detail": "User doesnt exist."}, status=status.HTTP_404_NOT_FOUND)
                # user = User.objects.create(username=email)
                # user.set_unusable_password()
                # user.save()
                # users_logger.debug(f"Created new user with email: {email}")
                


        except Exception as e:
            users_logger.error(f"Error querying or creating user for email {email}: {str(e)}")
            return Response({"detail": "Internal server error."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if not can_request_otp(user):
            users_logger.warning(f"OTP request limit exceeded for user: {email}")
            return Response(
                {"detail": "OTP request limit exceeded. Please try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

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
                    'status':200,
                    'user_id':user.id,
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
        


@api_view(['POST', 'GET','PUT'])
@permission_classes([IsAuthenticated])  # Ensure only authenticated users can access
def manage_route(request):
    openai.api_key = os.getenv('OPEN_AI_API')
    user = request.user

    if request.method == 'POST':
        # Extract data from the request
        time = request.data.get('time', '')
        company = request.data.get('company', 'myself')
        cost = request.data.get('cost', '')
        activity_type = request.data.get('activity_type', '')
        area = request.data.get('area', '')

        users_logger.info(f"Parameters: time={time}, company={company}, cost={cost}, activity_type={activity_type}, area={area}")

        # Cache key for activity data
        cache_key = f"activity_data_{user.id}"
        activity_data = cache.get(cache_key, [])

        try:
            # Convert naive datetime to timezone-aware
            if time:
                naive_datetime = parse(time)  
                time = make_aware(naive_datetime)

            # Format user input for the AI
            route_user_message = (
                f"Hi chat, I want you to give me options for a future activity in {time} with {company}. "
                f"The estimated cost for the activity should be not more than {cost} ils. "
                f"The kind of activity I want to do is {activity_type}, and the area should be {area}. "
                f"Please respond only in JSON format. Do not include any extra text, code snippets, or explanations. "
                f'''Your JSON response must follow this format:
                [
                    {{
                        "Activity": "Activity Name",
                        "Location": "Location Details",
                        "Estimated Cost": "Cost Estimate",
                        "Description": "Description of the activity"
                    }},
                    {{
                        "Activity": "Activity Name",
                        "Location": "Location Details",
                        "Estimated Cost": "Cost Estimate",
                        "Description": "Description of the activity"
                    }}
                ]'''
            )

            # Call OpenAI API for conversation
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": route_user_message},
                ],
                max_tokens=300,
                temperature=0.7,
            )

            ai_message = response['choices'][0]['message']['content'].strip()
            users_logger.info(f"OpenAI response: {ai_message}")

            # Clean AI response and parse as JSON
            try:
                clean_ai_message = ai_message.strip("```").replace("json", "").strip()
                ai_response_json = json.loads(clean_ai_message)

                # Ensure the response contains at least two options
                if len(ai_response_json) < 2:
                    users_logger.error("AI response does not contain two options.")
                    return Response({'error': 'AI response does not contain enough options.'}, status=500)

                combined_ai_suggestion = {
                    "option_1": ai_response_json[0],
                    "option_2": ai_response_json[1],
                }
            except json.JSONDecodeError as e:
                users_logger.error(f"Failed to parse AI response as JSON: {str(e)}")
                return Response({'error': 'AI response could not be parsed as JSON.'}, status=500)

            # Save activity to the database
            saved_activity = Activity.objects.create(
                user=user,
                activity_type=activity_type.upper().replace(" ", "_"),
                title=f"Suggested Activities for {time}",
                time=time,
                cost=float(cost) if cost else None,
                area=area,
                company=company,
                ai_suggestion=json.dumps(combined_ai_suggestion),  # Save both options as JSON
            )

            # Cache activity data
            activity_data.append({
                'time': time,
                'company': company,
                'cost': cost,
                'activity_type': activity_type,
                'area': area,
                'ai_suggestion': combined_ai_suggestion,
                'timestamp': timezone.now().isoformat(),
            })
            cache.set(cache_key, activity_data, timeout=600)  # Cache for 10 minutes

            return Response({
                'user_input': route_user_message,
                'ai_response': combined_ai_suggestion,
                'route_id': saved_activity.id,
            }, status=200)

        except Exception as e:
            users_logger.error(f"Error occurred for user {user.username}: {str(e)}", exc_info=True)
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
                'cost': activity.cost,
                'area': activity.area,
                'company': activity.company,
                'ai_suggestion': activity.ai_suggestion,
                'created_at': activity.created_at.isoformat(),
            }
            for activity in activities
        ]

        # Cache the data for future requests
        cache.set(cache_key, activity_list, timeout=600)  # Cache for 10 minutes
        return Response({'activities': activity_list}, status=200)
    
    elif request.method == 'PUT':
        # Get the activity id from the request
        activity_id = request.data.get('id')
        if activity_id:
            # Fetch the activity from the database
            activity = Activity.objects.get(id=activity_id)
            # Update the activity data
            activity.title = request.data.get('title')
            activity.time = request.data.get('time')
            activity.cost = request.data.get('cost')
            activity.area = request.data.get('area')
            activity.company = request.data.get('company')
            activity.ai_suggestion = request.data.get('ai_suggestion')
            activity.save()
            return Response({'message': 'Activity updated successfully'}, status=200)
        else:
            return Response({'error': 'Activity id not found'}, status=404)
        


@api_view(['GET'])
@permission_classes([IsAuthenticated])  # Ensure only authenticated users can access
def route_details(request, route_id):
    try:
        # Fetch the route or raise 404 if not found
        activity = get_object_or_404(Activity, id=route_id)

        # Construct the response data
        activity_data = {
            'id': activity.id,
            'title': activity.title,
            'type': activity.activity_type,
            'time': activity.time,
            'cost': activity.cost,
            'area': activity.area,
            'company': activity.company,
            'ai_suggestion': activity.ai_suggestion,
            'created_at': activity.created_at.isoformat(),
        }

        # Return the response
        return Response(activity_data, status=200)

    except Exception as e:
        # Handle unexpected errors
        return Response({'error': f"An error occurred: {str(e)}"}, status=500)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def contact_us_mail(request):
    start_time = time.time()  # Track start time

    # Get data from the request
    contact_message = request.data.get('contactMessage')
    contact_subject = request.data.get('contactSubject')
    sender = request.user.username

    try:
        # Validate required fields
        if not contact_message or not contact_subject or not sender:
            users_logger.error("Invalid request: missing required fields")
            return Response({"error": "Missing Message, Subject, or Sender"}, status=400)

        # Send the email
        contact_us_email(sender=sender, contact_subject=contact_subject, contact_message=contact_message)

        end_time = time.time()
        users_logger.info(f"Function execution time: {end_time - start_time:.2f} seconds")
        return Response({"message": "Email sent successfully"}, status=200)

    except Exception as e:
        # Handle unexpected errors
        users_logger.error(f"Error sending email: {str(e)}")
        return Response({"error": "Failed to send email"}, status=500)



@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def manage_profile_pic(request):
    try:
        user = request.user  # Directly use the authenticated user

        if request.method == 'POST':
            if 'profile_picture' not in request.FILES:
                users_logger.debug(f"No profile picture file provided for user {user.id}")
                return Response({'message': 'No profile picture file provided'}, status=status.HTTP_400_BAD_REQUEST)

            file = request.FILES['profile_picture']

            # Validate file type and size
            ALLOWED_CONTENT_TYPES = ['image/jpeg', 'image/png', 'image/gif']
            MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB

            if file.content_type not in ALLOWED_CONTENT_TYPES:
                users_logger.debug(f"Unsupported file type: {file.content_type} for user {user.id}")
                return Response({'message': 'Unsupported file type'}, status=status.HTTP_400_BAD_REQUEST)

            if file.size > MAX_UPLOAD_SIZE:
                users_logger.debug(f"File size exceeds limit for user {user.id}")
                return Response({'message': 'File size exceeds the limit'}, status=status.HTTP_400_BAD_REQUEST)

            user.profile_picture = file
            user.save()

            users_logger.debug(f"Profile picture saved for user {user.id}")
            return Response({'message': 'Profile picture uploaded successfully!', 'profile_picture': user.profile_picture.url}, status=status.HTTP_200_OK)

        elif request.method == 'DELETE':
            if user.profile_picture:
                user.profile_picture.delete()
                user.save()

                users_logger.debug(f"Profile picture deleted for user {user.id}")
                return Response({'message': 'Profile picture deleted successfully!'}, status=status.HTTP_200_OK)
            else:
                users_logger.debug(f"No profile picture to delete for user {user.id}")
                return Response({'message': 'No profile picture to delete'}, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        users_logger.error(f"Error managing profile picture for user {user.id}: {str(e)}")
        return Response({'message': 'An error occurred while managing the profile picture', 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def manage_profile_pic(request, user_id):
    try:
        # Fetch the CustomUser object
        user = CustomUser.objects.filter(id=user_id).first()
        if not user:
            users_logger.debug(f"Profile not found for {user_id}")
            return Response({'message': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

        # Handle POST request for uploading profile picture
        if request.method == 'POST':
            if 'profile_picture' not in request.FILES:
                users_logger.debug(f"No profile picture file provided for {user_id}")
                return Response({'message': 'No profile picture file provided'}, status=status.HTTP_400_BAD_REQUEST)

            # Upload the new profile picture
            user.profile_picture = request.FILES['profile_picture']
            user.save()

            users_logger.debug(f"Profile picture saved for {user_id}")
            return Response({
                'message': 'Profile picture uploaded successfully!',
                'profile_picture_url': user.profile_picture.url  # Return the S3 URL
            }, status=status.HTTP_200_OK)

        # Handle DELETE request for deleting profile picture
        elif request.method == 'DELETE':
            if user.profile_picture:
                # Delete the profile picture file from S3
                user.profile_picture.delete()
                user.save()

                users_logger.debug(f"Profile picture deleted for {user_id}")
                return Response({'message': 'Profile picture deleted successfully!'}, status=status.HTTP_200_OK)
            else:
                users_logger.debug(f"No profile picture to delete for {user_id}")
                return Response({'message': 'No profile picture to delete'}, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        users_logger.error(f"Error managing profile picture for {user_id}: {str(e)}")
        return Response({
            'message': 'An error occurred while managing the profile picture',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
# @permission_classes([IsAuthenticated])
def get_nearby_places(request):
    start_time = time.time()

    # Get the latitude, longitude, radius, and category from the request
    user_lat = request.GET.get('latitude')
    user_lng = request.GET.get('longitude')
    radius = request.GET.get('radius', 3000)  # Default radius is 3km
    category = request.GET.get('category', '')

    # Log the received parameters
    users_logger.info(f"Received parameters: Latitude: {user_lat}, Longitude: {user_lng}, Radius: {radius}, Category: {category}")

    # Validate latitude and longitude
    if not user_lat or not user_lng:
        users_logger.error("Missing latitude or longitude in request")
        return Response({'error': 'Missing latitude or longitude'}, status=400)

    # Map categories to Google Places types
    category_map = {
        'Restaurants': 'restaurant',
        'Attractions': 'tourist_attraction',
        'Accommodations': 'lodging',
        'Cafe':'cafe',
    }
    place_type = category_map.get(category, None)

    # Google Places API URL
    google_places_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

    # Parameters to pass to the Google Places API
    params = {
        'location': f'{user_lat},{user_lng}',
        'radius': radius,
        'key': GOOGLE_PLACES_API_KEY
    }

    # Add category type if available
    if place_type:
        params['type'] = place_type

    # Log the outgoing API request
    users_logger.info(f"Making request to Google Places API with params: {params}")

    # Make the request to the Google Places API
    try:
        response = requests.get(google_places_url, params=params)
        response.raise_for_status()  # Raise an exception if the response code is not 200
    except requests.RequestException as e:
        users_logger.error(f"Error fetching data from Google Places API: {e}")
        return Response({'error': 'Failed to fetch data from Google Places API'}, status=500)

    places_data = response.json()

    # Log the response from Google Places API
    users_logger.info(f"Google Places API response status: {response.status_code}, Data: {places_data}")

    # Extract relevant data from the response
    results = []
    if 'results' in places_data:
        for place in places_data['results']:
            place_location = place.get('geometry', {}).get('location', {})
            place_lat = place_location.get('lat')
            place_lng = place_location.get('lng')

            if place_lat and place_lng:
                # Calculate the distance between the user's location and the place
                distance = haversine(float(user_lat), float(user_lng), place_lat, place_lng)
            else:
                distance = None

            
            if distance <= float(radius):
                place_info = {
                    'id':place.get('place_id'),
                    'name': place.get('name'),
                    'type': place.get('types', []),
                    'location': place_location,
                    'distance': f"{distance:.2f} km" if distance is not None else 'Unknown',
                    'rating': place.get('rating', 'No rating available'),
                    'opening_hours': place.get('opening_hours', {}).get('open_now', 'No hours available'),
                    'phone_number':get_place_phone_number(str(place.get('place_id')))
                }
                results.append(place_info)

    # Log the number of places found
    users_logger.info(f"Found {len(results)} places near location: {user_lat}, {user_lng}")

    # Return the data as JSON
    end_time = time.time()
    users_logger.info(f"Function execution time: {end_time - start_time} seconds")
    return Response({'places': results}, status=200)






@api_view(['PUT', 'GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def manage_favorite_place(request, user_id):
    
    try:
        # Fetch the user
        user = CustomUser.objects.filter(id=user_id).first()
        if not user:
            users_logger.warning(f"User {user_id} not found")
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        if request.method == "GET":
            # Retrieve user details
            users_logger.info(f"Retrieving details for user {user_id}")
            serializer = CustomUserSerializer(user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        elif request.method == "PUT":
            # Add a new favorite place
            place_data = request.data.get('place')
            if not place_data:
                users_logger.warning(f"No 'place' data provided for user {user_id}")
                return Response({'error': 'No place data provided'}, status=status.HTTP_400_BAD_REQUEST)

            # Ensure place_id uniqueness
            place_data['id'] = str(uuid.uuid4())
            user.favorite_places.append(place_data)
            users_logger.info(f"Added new place for user {user_id}: {place_data}")

            # Update user
            serializer = CustomUserSerializer(user, data={'favorite_places': user.favorite_places}, partial=True)
            if serializer.is_valid():
                serializer.save()
                users_logger.info(f"Favorite places updated successfully for user {user_id}")
                return Response({'message': 'Place added successfully', 'data': serializer.data}, status=status.HTTP_200_OK)
            else:
                users_logger.warning(f"Validation errors while updating user {user_id}: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        elif request.method == "DELETE":
            # Get 'place_id' from the URL
            place_id = request.query_params.get('place_id') or request.data.get('place_id')
            if not place_id:
                return Response({'error': 'Place ID not provided'}, status=status.HTTP_400_BAD_REQUEST)

            # Filter favorite places
            updated_places = [place for place in user.favorite_places if place.get('id') != place_id]
            if len(updated_places) == len(user.favorite_places):
                return Response({'error': 'Place not found'}, status=status.HTTP_404_NOT_FOUND)

            user.favorite_places = updated_places
            user.save()
            return Response({'message': 'Place deleted successfully', 'favorite_places': user.favorite_places}, status=status.HTTP_200_OK)

    except Exception as e:
        users_logger.error(f"An error occurred for user {user_id}: {e}")
        return Response({'error': 'An internal error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_user_location(request):
    user = request.user
    try:
        # Get location data from request
        user_lat = request.data.get('latitude')
        user_long = request.data.get('longitude')
        if not user_long or not user_lat:
            return Response({'error': 'longitude or latitude not provided'}, status=status.HTTP_400_BAD_REQUEST)
        user.longitude = user_long
        user.latitude = user_lat
        user.save()
        return Response({'message': 'Location saved successfully'}, status=status.HTTP_200_OK)
    except Exception as e:
        users_logger.error(f"An error occurred for user {user.id}: {e}")
        return Response({'error': 'An internal error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





@api_view(['POST', 'GET'])
@permission_classes([IsAuthenticated])
def manage_chat(request):
    user = request.user

    if request.method == 'POST':
        data = request.data

        # Ensure required fields are present
        required_fields = ['content', 'sender', 'receiver']
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            return Response(
                {'error': f'Missing fields: {", ".join(missing_fields)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate UUID fields
        try:
            sender = uuid.UUID(data['sender'])
            receiver = uuid.UUID(data['receiver'])
        except (ValueError, TypeError):
            return Response({'error': 'Invalid sender or receiver UUID'}, status=status.HTTP_400_BAD_REQUEST)

        # Handle chat_room creation or retrieval
        chat_room = None
        if 'chat_room' in data and data['chat_room']:
            try:
                chat_room_id = uuid.UUID(data['chat_room'])
                chat_room = ChatRoom.objects.get(id=chat_room_id)
            except (ChatRoom.DoesNotExist, ValueError, TypeError):
                return Response({'error': 'Invalid or non-existent chat room'}, status=status.HTTP_404_NOT_FOUND)
        else:
            # Create a new chat room if not provided
            chat_room, created = ChatRoom.objects.get_or_create(
                Q(user=sender, friend=receiver) | Q(user=receiver, friend=sender),
                defaults={'created_at': datetime.datetime.now()}
            )

        # Ensure the sender is part of the chat room
        if str(user.id) not in [str(chat_room.user), str(chat_room.friend)]:
            return Response(
                {'error': 'You are not authorized to send messages in this chat room.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Save the message
        message_data = {
            'chat_room': chat_room.id,
            'sender': str(sender),
            'receiver': str(receiver),
            'content': data['content'],
            'timestamp': datetime.datetime.now()
        }
        serializer = MessageSerializer(data=message_data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'GET':
    # Retrieve chat_room_id from query params
        chat_room_id = request.GET.get('chat_room')

        if not chat_room_id:
            return Response({'error': 'Chat room ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Validate and retrieve the chat room
            chat_room = ChatRoom.objects.get(id=chat_room_id)
        except (ChatRoom.DoesNotExist, ValueError, TypeError):
            return Response({'error': 'Chat room does not exist'}, status=status.HTTP_404_NOT_FOUND)

        # Ensure the requesting user is part of the chat room
        if str(user.id) not in [str(chat_room.user), str(chat_room.friend)]:
            return Response(
                {'error': 'You are not authorized to view messages in this chat room.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Retrieve and serialize messages for the chat room
        messages = Message.objects.filter(chat_room=chat_room).order_by('timestamp')
        serializer = MessageSerializer(messages, many=True)

        return Response(
            {'chat_room': chat_room.id, 'messages': serializer.data},
            status=status.HTTP_200_OK
        )



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_chats(request):
    user = request.user
    try:
        # Retrieve chat rooms where the user is either the user or the friend
        chat_rooms = ChatRoom.objects.filter(models.Q(user=user.id) | models.Q(friend=user.id))

        # Serialize the chat rooms
        serializer = ChatRoomSerializer(chat_rooms, many=True)
        
        return Response(
            {'message': f'Found {len(chat_rooms)} chat rooms', 'chats': serializer.data},
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    



from .tasks import reset_search_friend


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def search_friend(request):
    user = request.user

    try:
        # Check the current search_friends status from the cache
        cache_key = f'search_friend_{user.id}'
        is_active = cache.get(cache_key)

        if is_active:
            # If already active, deactivate it
            cache.delete(cache_key)  # Remove from cache
            user.search_friends = False  # Use the correct property name
            user.save()
            users_logger.info(f"Deactivated search_friends for user {user.id} ({user.username})")
            return Response({'message': 'Search friend deactivated successfully'}, status=200)

        # Activate search_friends
        user.search_friends = True  # Use the correct property name
        user.save()
        users_logger.info(f"Activated search_friends for user {user.id} ({user.username})")

        # Set the status in the cache for 1 hour
        cache.set(cache_key, True, timeout=3600)

        # Schedule a task to reset search_friends after 1 hour
        reset_search_friend.apply_async((user.id,), countdown=3600)
        users_logger.info(f"Scheduled task to deactivate search_friends for user {user.id} in 1 hour")

        return Response({'message': 'Search friend activated for 1 hour'}, status=200)

    except Exception as e:
        users_logger.error(f"Error processing search friend request for user {user.id} ({user.username}): {str(e)}", exc_info=True)
        return Response({'error': 'An error occurred while processing your request.'}, status=500)