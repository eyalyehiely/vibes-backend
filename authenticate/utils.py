
import random,ssl,certifi,smtplib,logging
from datetime import timedelta
from django.utils import timezone
from .models import *
from django.contrib.auth import get_user_model
from email.message import EmailMessage
from vibes.settings import EMAIL_HOST_PASSWORD,EMAIL_HOST_USER
import math

logger = logging.getLogger('auth')

User = get_user_model()


from time import sleep

def send_email_with_retry(msg, retries=3, delay=5):
    for attempt in range(retries):
        try:
            context = ssl.create_default_context(cafile=certifi.where())
            with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as server:
                server.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
                server.send_message(msg)
            logger.info(f"Sent OTP to {msg['To']}.")
            return
        except Exception as e:
            logger.error(f"Failed to send OTP email on attempt {attempt + 1}: {e}")
            if attempt < retries - 1:
                sleep(delay)
            else:
                raise e
            

def generate_otp_code():
    """Generate a 6-digit random OTP code."""
    return f"{random.randint(100000, 999999)}"

def generate_and_send_otp(user):
    try:
        otp = generate_otp_code()
        # Save OTP to the database
        otp_record = Otp.objects.create(user=user)
        otp_record.set_code(otp)
        otp_record.save()
        logger.info(f"OTP entry saved for user: {user.username}")
    except Exception as e:
        logger.error(f"Failed to save OTP for user {user.username}: {e}")
        raise
    msg = EmailMessage()
    msg.set_content(f"Hi {user.username.split('@')[0].capitalize()},\n Your One-Time Password (OTP) for account verification is: {otp}.\n This OTP is valid for the next 5 minutes.\n Please do not share this code with anyone for security purposes.")
    msg['Subject'] = 'Vibes OTP Code'
    msg['From'] = EMAIL_HOST_USER
    msg['To'] = user.username
    # Create a secure SSL context using certifi
    context = ssl.create_default_context(cafile=certifi.where())

    try:
        logger.info(f"Attempting to send email via SMTP server: {EMAIL_HOST_USER} with SSL")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as server:
            server.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
            server.send_message(msg)
        logger.info(f"Sent OTP to {user.username}.")

    except Exception as e:
        logger.error(f"Failed to send OTP email: {e}")
        raise

def verify_otp(user, otp_code):
    """Verify the provided OTP code for the user."""
    try:
        # Fetch the latest OTP for the user
        otp = Otp.objects.filter(user=user, is_used=False).latest('created_at')
        
        # Check if the retrieved OTP is for the same user
        if otp.user != user:
            logger.error(f"Retrieved OTP for a different user. Expected {user.username}, but got {otp.user.username}.")
            return False, "Invalid OTP entry."

        logger.debug(f"Retrieved OTP entry: {otp} for user: {user.username}")
        
        # Check if the OTP has expired
        if otp.is_expired():
            logger.info(f"OTP expired for user: {user.username}")
            return False, "OTP has expired."
        
        # Check if the provided OTP code is correct
        if otp.check_code(otp_code):
            # print(otp.check_code(otp_code))
            otp.is_used = True
            otp.save()
            logger.info(f"OTP verified successfully for user: {user.username}")
            return True, "OTP verified successfully."
        else:
            otp.attempt_count += 1
            otp.save()
            logger.warning(f"Invalid OTP code provided for user: {user.username}. Attempt {otp.attempt_count}/5")
            
            # Optional: Handle exceeding max OTP attempts
            if otp.attempt_count >= 5:
                otp.is_used = True
                otp.save()
                logger.warning(f"Maximum OTP attempts exceeded for user: {user.username}")
                return False, "Maximum OTP attempts exceeded. Please request a new OTP."
            
            return False, "Invalid OTP."
    
    except Otp.DoesNotExist:
        logger.warning(f"No OTP found for user: {user.username}")
        return False, "No OTP found. Please request a new one."
    
def can_request_otp(user):
    """
    Check if the user can request a new OTP based on rate limiting.
    Example: Max 10 OTP requests per hour.
    """
    time_threshold = timezone.now() - timedelta(hours=1)
    recent_otps = Otp.objects.filter(user=user, created_at__gte=time_threshold).count()
    return recent_otps < 10  # Allow up to 10 OTP requests per hour



# Haversine formula for calculating distance
def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points 
    on the Earth (specified in decimal degrees using the Haversine formula).
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    r = 6371  # Radius of earth in kilometers
    return r * c  # Distance in kilometers