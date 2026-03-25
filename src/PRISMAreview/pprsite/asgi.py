"""
ASGI config for pprsite project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, ChannelNameRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from prismadb.consumers import BibEntryProcessor
from addbib.routing import websocket_urlpatterns


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pprsite.settings')

# application = get_asgi_application()

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
    "channel": ChannelNameRouter({
        "bib-entry-processor": BibEntryProcessor.as_asgi(),
    }),
})
