import hashlib
from django.contrib.auth.models import AbstractUser,Group, Permission
from django.db import models
import uuid,datetime
from django.utils import timezone

def profile_picture_upload_path(instance, filename):
    return f'assets/users/{instance.user_id}/profile_pictures/{filename}'



class CustomUser(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.EmailField(unique=True)
    accept_terms = models.BooleanField(default=True)
    gender = models.CharField(max_length=255, blank=True, null=True)
    birth_date = models.DateField(default=datetime.date.today, blank=True, null=True)
    profile_picture = models.ImageField(upload_to=profile_picture_upload_path, blank=True, null=True)
    favorite_activities = models.JSONField(default=list, blank=True)

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
        ('WATCH_MOVIE', 'Watching a Movie'),
        ('READ_BOOK', 'Reading a Book'),
        ('PLAY_GAME', 'Playing a Game'),
        ('LISTEN_MUSIC', 'Listening to Music'),
    ]

    ACTIVITY_TIME = [
        ('MORNING', 'Morning'),
        ('NOON', 'Noon'),
        ('AFTERNOON', 'Afternoon'),
        ('EVENING', 'Evening'),
        ('NIGHT', 'Night'),
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
    title = models.CharField(
        max_length=255,
    )
  
    time = models.CharField(
        max_length=20,
        choices=ACTIVITY_TIME,
    )
    cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    area = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )
    company = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )
    ai_suggestion= models.CharField( max_length=255,
        null=True,
        blank=True,)
    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Activities'

    def __str__(self):
        return f"{self.user.username} - {self.get_activity_type_display()} - {self.title}"
    

    class Meta:
        verbose_name_plural = 'Activities'

    def __str__(self):
        return f"{self.user.username} - {self.get_activity_type_display()} - {self.title}"


