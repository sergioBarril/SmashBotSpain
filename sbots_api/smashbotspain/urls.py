from django.conf.urls import include, url
from rest_framework.routers import DefaultRouter

from smashbotspain import views

# Create a router and register our viewsets with it.
router = DefaultRouter()
router.register(r'players', views.PlayerViewSet)
router.register(r'arenas', views.ArenaViewSet)
router.register(r'messages', views.MessageViewSet)
router.register(r'guilds', views.GuildViewSet)
router.register(r'tiers', views.TierViewSet)
router.register(r'regions', views.RegionViewSet)
router.register(r'characters', views.CharacterViewSet)

# The API URLs are now determined automatically by the router.
# Additionally, we include the login URLs for the browsable API.
urlpatterns = [
    url(r'^', include(router.urls))
]