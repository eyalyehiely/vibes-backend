from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    # Define the fields to display in the admin list view
    list_display = ('username', 'accept_terms', 'gender', 'age', 'birth_date', 'profile_picture','favorite_places','search_friends','longitude','latitude',)
    # Enable searching by username and gender
    search_fields = ('username', 'gender')
    # Add filters for gender and birth_date
    list_filter = ('gender', 'birth_date', 'accept_terms')
    # Group fields for detail view
    fieldsets = (
        (None, {'fields': ('username', 'password', 'accept_terms')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'gender', 'birth_date', 'profile_picture','favorite_places','search_friends','longitude','latitude','friends')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    # Fields for the add form
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'accept_terms'),
        }),
    )


@admin.register(Otp)
class OtpAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'is_used', 'attempt_count', 'is_expired')
    list_filter = ('is_used', 'created_at')
    search_fields = ('user__username',)

    def is_expired(self, obj):
        return obj.is_expired()
    is_expired.boolean = True  # Display as a boolean icon in the admin


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'activity_type', 'title', 'time', 'cost', 'created_at')
    list_filter = ('activity_type', 'time', 'created_at')
    search_fields = ('user__username', 'title', 'area', 'company', 'ai_suggestion')
    ordering = ('-created_at',)






@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'friend', 'created_at')
    # list_filter = ('created_at')
    search_fields = ('user', 'friend')
    ordering = ('-created_at',)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'chat_room', 'sender', 'receiver', 'is_read', 'timestamp')
    list_filter = ('is_read', 'timestamp')
    search_fields = ('chat_room__id', 'sender', 'receiver', 'content')
    ordering = ('-timestamp',)
    readonly_fields = ('timestamp',)  # Make the timestamp read-only in the admin