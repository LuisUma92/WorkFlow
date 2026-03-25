from rest_framework import serializers
from prismadb.models import Bib_entries


class BibEntriesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bib_entries
        fields = '__all__'  # or list the fields explicitly
