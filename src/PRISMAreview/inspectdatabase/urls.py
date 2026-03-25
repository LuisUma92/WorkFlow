from django.urls import path
from . import views

urlpatterns = [
    path('select_model/', views.select_model_view, name='select_model'),
    path('display_content/<str:model_name>/<int:pk>/',
         views.display_model_row,
         name='display_model_row'),
]
