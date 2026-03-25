from django.urls import re_path
from prismadb import consumers

websocket_urlpatterns = [
    re_path(r'ws/progress/$', consumers.BibEntryProcessor.as_asgi()),
]
