from django.urls import path
from .views import WhatMovieAPIView

urlpatterns = [
    path('chat/', WhatMovieAPIView.as_view(), name='whatmovie_chat'),
]
