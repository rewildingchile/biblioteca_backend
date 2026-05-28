from rest_framework import serializers

from .models import GoogleDriveFileDocument


class GoogleDriveFileDocumentSerializer(serializers.ModelSerializer):

    # campos del modelo relacionado GoogleDriveFile
    drive_file_id = serializers.CharField(
        source="file.drive_file_id",
        read_only=True
    )

    file_name = serializers.CharField(
        source="file.name",
        read_only=True
    )

    mime_type = serializers.CharField(
        source="file.mime_type",
        read_only=True
    )

    web_view_link = serializers.CharField(
        source="file.drive_web_view_link",
        read_only=True
    )

    modified_time = serializers.DateTimeField(
        source="file.last_known_modified_time",
        read_only=True
    )

    class Meta:

        model = GoogleDriveFileDocument

        fields = [
            "drive_file_id",
            "file_name",
            "mime_type",
            "web_view_link",
            "modified_time",
            "text_content",
        ]