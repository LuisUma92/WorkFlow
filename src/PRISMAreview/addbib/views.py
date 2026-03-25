# from asyncio import current_task
# from django.http import request
import bibtexparser
from django.utils.html import json
from django.shortcuts import render, redirect

from .forms import UploadFileForm
import prismadb.ppORM as parser
from prismadb.consumers import BibEntryProcessor


def index(request):
    uploaded_file = None
    if request.method == "POST":
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            parser.set_verbose(0)
            parser.init_structure()
            library = bibtexparser.load(request.FILES['file'])
            library = [parser.parse_entry(entry) for entry in library.entries]
            keyword = form.save_keyword()
            database = form.get_database()

            request.session["library"] = json.dumps(library)
            request.session["keyword"] = keyword
            request.session["database"] = database

            return redirect('process_bib_entries')
    else:
        form = UploadFileForm()

    context = {
            'form': form,
            'uploaded_file': uploaded_file
            }

    return render(
            request,
            "addbib/bibImportPage.html",
            context
            )


def process_bib_entries(request):
    processor = BibEntryProcessor()
    errors = []
    context = {}
    print("llegué")

    if request.method == 'POST':
        bibkeys = request.POST.get('bibkeys')
        if isinstance(bibkeys, str):
            bibkeys = [bibkeys]
        library = []
        for bibkey in bibkeys:
            bib_data, authors, url = handle_corrected_data(request, bibkey)
            library.append([
                bib_data,
                authors,
                url
                ])
        print(library)
    else:
        library = json.loads(request.session.get("library", '[]'))
    keyword = request.session.get('keyword', '')
    database = request.session.get('database', '')
    while library:
        entry = library.pop(0)

        bib_data = entry[0]
        author_data = entry[1]
        url_data = entry[2]

        try:
            if request.method == 'POST':
                processor.update_bib_entry(bib_data)
            else:
                processor.add_bib_entry(bib_data)
                processor.add_authors(author_data, bib_data)
                processor.add_url(url_data, bib_data, database)

        except Exception as e:
            print(e)
            if 'Inconsistencies' in str(e):
                errors.append({
                    'error': str(e),
                    'entry': entry
                    })
            elif 'Duplicate entry' in str(e):
                # Handle duplicate entries
                print("already exists")
            else:
                print(e)
                errors.append({
                    'error': e,
                    'entry': entry
                    })

    request.session["library"] = json.dumps(library)
    request.session["keyword"] = keyword
    request.session["database"] = database

    context['errors'] = errors if errors else None
    context['success'] = not errors
    return render(request, 'addbib/process_bib_entries.html', context)


def handle_corrected_data(request, bibkey):
    current_bib_data = {}
    author_data = {}
    current_url_data = {}
    for key in request.POST:
        if key.startswith(f'bib_data[{bibkey}]'):
            field_name = key[len(f'bib_data[{bibkey}]:'):]
            current_bib_data[field_name] = request.POST[key]
        elif key.startswith(f'author_data[{bibkey}]'):
            parts = key.split('-')
            author_type = parts[1]
            field_name = parts[2]
            if author_type not in author_data:
                author_data[author_type] = []
            for name in request.POST[key]:
                author_data[author_type].append({field_name: name})
        elif key.startswith(f'url_data[{key}]'):
            field_name = key[len(f'url_data[{key}]'):]
            current_url_data[field_name] = request.POST[key]
    new_author_data = {}
    for author_type in author_data.keys():
        author_extra = {}
        new_author_list = []
        if len(author_data[author_type]) % 2 == 0:
            number_of_authors = int(len(author_data[author_type])/2)
        else:
            number_of_authors = int(len(author_data[author_type])/2 - 0.5)
            print("ME CAGO EN LA PUTA")

        for i in range(number_of_authors):
            current_author = author_data[author_type][i]
            current_author.update(
                    author_data[author_type][i+number_of_authors]
            )
            if number_of_authors % 2 != 0 and i+1 == number_of_authors:
                index = len(author_data[author_type])-1
                author_extra = author_data[author_type][index]
            new_author_list.append(current_author)
            if author_extra:
                new_author_list.append(author_extra)
        new_author_data[author_type] = new_author_list
    return current_bib_data, new_author_data, current_url_data
