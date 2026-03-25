from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name="upload_file"),
    path('process',
         views.process_bib_entries,
         name='process_bib_entries')
    ]
