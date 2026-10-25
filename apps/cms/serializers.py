from rest_framework import serializers

from apps.cms.models import Page
from apps.system_setting.models import AboutSystem


class PageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    def get_image_url(self, obj):
        if not obj.image:
            return None

        request = self.context.get("request") if hasattr(self, "context") else None
        if request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url

    class Meta:
        model = Page
        fields = ["id", "title", "slug", "content", "image_url", "type", "status"]


class AboutUsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AboutSystem
        fields = [
            "id",
            "name",
            "title",
            "description",
            "email",
            "contact_phone",
            "office_address",
            "logo",
            "favicon",
            "copyright",
        ]
