from django.urls import path
from .views import main, SearchQuery, SettingsQuery

urlpatterns = [
    path('', main),
    path('search', SearchQuery.as_view()),
    path('settings', SettingsQuery.as_view())
]
