from django.urls import path
from . import views

urlpatterns = [
    path('consulta/', views.consulta, name='consulta'),
    path('token/', views.token, name='token'),
]
