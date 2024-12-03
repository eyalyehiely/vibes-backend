from rest_framework import serializers
from .models import *
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer



# Helper to validate phone number
def validate_phone_number(phone_number):
    if not phone_number.isdigit() or len(phone_number) < 9 or len(phone_number) > 15:
        raise serializers.ValidationError("Enter a valid phone number 9 to 15 digits.")
    return phone_number


# Custom Token Serializer for JWT with additional claims
class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['first_name'] = user.first_name
        token['last_name'] = user.last_name
        token['user_id'] = str(user.id)
        return token


# CustomUser Serializer with phone number validation
class CustomUserSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(validators=[validate_phone_number])
    age = serializers.ReadOnlyField()

    class Meta:
        model = CustomUser
        fields = "__all__"



# class CompleteProfileSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = CustomUser
#         fields = ['phone_number',]




# class CompleteProfileSerializer(serializers.ModelSerializer):
#     gender = serializers.CharField(source='talent_profile.gender', read_only=False)
#     birth_date = serializers.DateField(source='talent_profile.birth_date', read_only=False)
#     age = serializers.SerializerMethodField()
#     phone_number = serializers.CharField()

#     class Meta:
#         model = CustomUser
#         fields = ['phone_number', 'gender', 'birth_date', 'age']

#     def get_age(self, obj):
#         if hasattr(obj, 'talent_profile') and obj.talent_profile.birth_date:
#             age = obj.talent_profile.age
#             print(f"Calculated age: {age}")  # Add this for debugging
#             return age
#         print("Age not found")  # Add this for debugging
#         return None

#     def update(self, instance, validated_data):
#         # Update fields from CustomUser
#         instance.phone_number = validated_data.get('phone_number', instance.phone_number)
#         instance.save()

#         # Update fields from Talent
#         talent_data = validated_data.get('talent_profile', {})
#         talent_profile = instance.talent_profile
#         if talent_profile:
#             talent_profile.gender = talent_data.get('gender', talent_profile.gender)
#             talent_profile.birth_date = talent_data.get('birth_date', talent_profile.birth_date)
#             talent_profile.save()

#         return instance



 

    


