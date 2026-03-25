from re import T
from django.db import IntegrityError
from django.shortcuts import render, redirect
from django.utils.html import json, re
from prismadb.models import Keyword, Reviewed, Tags, Rationale_list
from prismadb.models import Review_rationale, Url_list, Bib_entries
from .forms import KeywordSelectionForm, RationaleSelectionForm, TagForm
from rest_framework import generics
from prismadb.serializer import BibEntriesSerializer


def index(request):
    if request.method == 'POST':
        form = KeywordSelectionForm(request.POST)
        # keyword_name = request.POST['keyword_name']
        if form.is_valid():
            keyword_name = form.cleaned_data['keyword_name']
            print(keyword_name)
            keyword = Keyword.objects.get(id=keyword_name)
            to_test = Reviewed.objects.filter(id_key=keyword)
            library = [review.id_article.id for review in to_test]

            entry_context = gather_entry_info(request, library.pop(0))
            # serialized = BibEntriesSerializer(library, many=True)
            context = {
                    'library': json.dumps(library)
                    # 'library': json.dumps(serialized.data)
                    }
            context.update(entry_context)
            return render(
                    request,
                    'review/to_include.html',
                    context
                    )
    else:
        form = KeywordSelectionForm()

    context = {
            'form': form
            }
    return render(
            request,
            'review/init_review.html',
            context
            )


def test_for_inclusion(request):
    library = json.loads(request.POST.get('library'))
    # current_entry = {'title': 'prueba'}
    entry_context = gather_entry_info(request, library.pop(0))

    # tags = Tags.objects
    # rationale = Rationale_list.objects

    context = {
            'library': library,
            # 'tags': tags,
            # 'rationales': rationale
            }
    context.update(entry_context)

        # return render(request, 'review/to_include.html', context)
    # context['tag_form'] = tag_form
    # context = {}
    return render(request, 'review/to_include.html', context)


def gather_entry_info(request, entry_id):
    url = Url_list.objects.filter(id_article=entry_id)[0]
    entry = Bib_entries.objects.filter(id=entry_id)[0]
    if request.method == 'POST':
        tag_form = TagForm(request.POST)
        if tag_form.is_valid():
            selected_tags_ids = tag_form.cleaned_data['tags']
            new_tag_value = tag_form.cleaned_data['new_tag']

            # Retrieve the selected tags
            selected_tags = Tags.objects.filter(id__in=selected_tags_ids)

            # Add new tag if provided
            if new_tag_value:
                new_tag, created = Tags.objects.get_or_create(tag=new_tag_value)
                selected_tags = list(selected_tags)  # Convert QuerySet to list
                selected_tags.append(new_tag)

        rationale_form = RationaleSelectionForm(request.POST)
        if rationale_form.is_valid():
            selected_rationale = rationale_form.cleaned_data['rationale']
            new_rationale = rationale_form.cleaned_data['new_rationale']

            if new_rationale:
                selected_rationale = Rationale_list.objects.create(
                        rationale_argument=new_rationale
                        )
    else:
        rationale_form = RationaleSelectionForm()
        tag_form = TagForm()
    context = {
            'entry': entry_id,
            'url': url.url_string,
            'article_title': entry.title,
            'year': entry.year,
            'rationale_form': rationale_form,
            'tag_form': tag_form
            # 'tags': tags,
            # 'rationales': rationale
            }
    return context


def add_tag(request):
    if request.method == 'POST':
        tag_words = request.POST.get('new_tag')
        try:
            tag, created = Tags.objects.get_or_create(
                    tag=tag_words
                    )
        except IntegrityError as e:
            print(e)
    return render(request, 'review/add_tag.html')


def add_rational(request):
    if request.method == 'POST':
        rational_words = request.POST.get('new_rational')
        try:
            rational, created = Rationale_list.objects.get_or_create(
                    rationale_argument=rational_words
                    )
        except IntegrityError as e:
            print(e)
    
    return render(request, 'review/add_rational.html')


class BibEntriesList(generics.ListCreateAPIView):
    queryset = Bib_entries.objects.all()
    serializer_class = BibEntriesSerializer


class BibEntriesDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Bib_entries.objects.all()
    serializer_class = BibEntriesSerializer
