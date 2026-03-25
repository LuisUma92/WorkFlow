from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='init_review'),
    path('including/', views.test_for_inclusion, name='test_for_inclusion'),
    path('tagging/', views.add_tag, name='add_tag'),
    path('reasoning/', views.add_rational, name='add_rational'),
    path('bib_entries/', views.BibEntriesList.as_view(), name='bib_entries_list'),
    path('bib_entries/<int:pk>/', views.BibEntriesDetail.as_view(), name='bib_entries_detail')
]
