from rest_framework import serializers
from .models import AboutSystem, ContactUs

class AboutSystemSerializer(serializers.ModelSerializer):
    class Meta:
        model = AboutSystem
        fields = "__all__"


class ContactInformationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AboutSystem
        fields = ["email", "contact_phone", "office_address"]


class ContactUsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactUs
        fields = [
            "id",
            "name",
            "email",
            "purpose",
            "message",
            "status",
            "created_at",
        ]
        read_only_fields = ["id", "status", "created_at"]