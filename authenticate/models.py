import hashlib
from django.contrib.auth.models import AbstractUser,Group, Permission
from django.db import models
import uuid,datetime
from django.utils import timezone

def profile_picture_upload_path(instance, filename):
    return f'assets/users/{instance.id}/profile_pictures/{filename}'



class CustomUser(AbstractUser):
    GENDER_CHOICES = {
        ('זכר', 'זכר'),
        ('נקבה', 'נקבה'),
        ('אחר', 'אחר'),
        }
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.EmailField(unique=True)
    accept_terms = models.BooleanField(default=True)
    gender = models.CharField(max_length=4, choices=GENDER_CHOICES, blank=True, null=True)
    birth_date = models.DateField(default=datetime.date.today, blank=True, null=True)
    profile_picture = models.ImageField(upload_to=profile_picture_upload_path, blank=True, null=True, default='assets/default_profile_picture.jpg')
    favorite_places = models.JSONField(default=list, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    search_friends = models.BooleanField(default=False)
    friends = models.JSONField(blank=True, null=True)

    # Override the related_name to avoid conflicts
    groups = models.ManyToManyField(
        Group,
        related_name="customuser_groups",
        blank=True,
        help_text="The groups this user belongs to.",
        verbose_name="groups",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name="customuser_user_permissions",
        blank=True,
        help_text="Specific permissions for this user.",
        verbose_name="user permissions",
    )

    class Meta:
        verbose_name = 'Custom User'
        verbose_name_plural = 'Custom Users'
        db_table = 'custom_users'

    @property
    def age(self):
        if self.birth_date:
            today = timezone.now().date()
            user_age = today.year - self.birth_date.year - (
                (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
            )
            return user_age
        return None

    def __str__(self):
        return self.username
    

class Otp(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    code_hash = models.CharField(max_length=64)  # SHA-256 hash
    created_at = models.DateTimeField(auto_now_add=True)
    attempt_count = models.IntegerField(default=0)
    is_used = models.BooleanField(default=False)

    def set_code(self, code):
        self.code_hash = hashlib.sha256(code.encode()).hexdigest()
        self.save()
        

    def check_code(self, code):
        input_hash = hashlib.sha256(code.encode()).hexdigest()
        print(f"Checking OTP: stored hash {self.code_hash}, input hash {input_hash}")
        return self.code_hash == input_hash

    def is_expired(self):
        return timezone.now() > self.created_at + datetime.timedelta(minutes=5)  # OTP valid for 5 minutes

    def __str__(self):
        return f"OTP for {self.user.username if self.user.username else 'Unknown username'}"
    



class Activity(models.Model):
    ACTIVITY_TYPES = [
        ('לצפות בסרט', 'לצפות בסרט'),
        ('לשחק', 'לשחק'),
        ('מסעדה', 'מסעדה'),
        ('יין', 'יין'),
        ('מסיבה', 'מסיבה'),
        ('באולינג', 'באולינג')
    ]

    

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='activities',
    )
    activity_type = models.CharField(
        max_length=20,
        choices=ACTIVITY_TYPES,
        help_text="The type of activity."
    )
    title = models.CharField(max_length=255)
    time = models.DateTimeField(max_length=20)
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    area = models.CharField(max_length=255, null=True, blank=True)
    company = models.CharField(max_length=255, null=True, blank=True, default='myself')
    ai_suggestion = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Activities'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.get_activity_type_display()} - {self.title}"




class ChatRoom(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.UUIDField()  # UUID of the logged-in user
    friend = models.UUIDField()  # UUID of the friend
    created_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return f"ChatRoom between {self.user} and {self.friend}"

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=~models.Q(user=models.F('friend')),
                name='prevent_self_chat'
            ),
        ]
        unique_together = ['user', 'friend']  # Ensure a single chat room per user-friend pair


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chat_room = models.ForeignKey(
        ChatRoom, related_name='messages', on_delete=models.CASCADE
    )
    chat_room = models.ForeignKey('ChatRoom', on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey('authenticate.CustomUser', on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey('authenticate.CustomUser', on_delete=models.CASCADE, related_name='received_messages')
    content = models.TextField(blank=False, null=False)
    is_read = models.BooleanField(default=False)  # Indicates if the message is read
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)  # Message timestamp

    def __str__(self):
        return f"Message from {self.sender} to {self.receiver} at {self.timestamp}"

    class Meta:
        ordering = ['timestamp']  # Default ordering by timestamp