from django.urls import path

from core.views import home, user_profile

urlpatterns = [
    path("", home, name="home"),
    path("user/<str:user_id>/", user_profile, name="user"),
]
