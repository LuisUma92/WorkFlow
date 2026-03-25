# import mysql.connector as sql
from channels.generic.websocket import AsyncConsumer, AsyncWebsocketConsumer
from django.shortcuts import Http404, get_object_or_404
from django.db.utils import IntegrityError
from django.utils.html import json
from django.core.exceptions import ObjectDoesNotExist
from .ppORM import parse_entry
from .models import Bib_entries, Author, Bib_author, Url_list
from .models import Referenced_databases, Author_type


class BibEntryProcessor(AsyncConsumer):
    def look_for_inconsistencies(self, entry, data):
        inconsistencies = []
        for field, new_value in data.items():
            existing_value = str(getattr(entry, field))
            new_value = data[field]
            if existing_value != new_value:
                inconsistencies.append({
                    'field': field,
                    'existing': existing_value,
                    'new': new_value
                    })
        if inconsistencies:
            # Raise an exception with details if there is a difference
            msn = f"Inconsistent data found: {inconsistencies}: "
            # msn += "Full content on database:"
            # msn += json.dumps(bib_entry)
            raise Exception(msn)
        return inconsistencies

    def add_bib_entry(self, bib_data):
        try:
            bib_entry = Bib_entries.objects.get(
                title=bib_data.get('title'),
                year=bib_data.get('year'),
                issue_volume=bib_data.get('issue_volume')
            )
            self.look_for_inconsistencies(
                    bib_entry,
                    bib_data
                    )
            # If no differences are found, return the existing entry
            return bib_entry
        except ObjectDoesNotExist:
            print(f"new entry {bib_data}")
            bib_entry = Bib_entries.objects.create(**bib_data)
            return bib_entry
        except Exception as e:
            print(f"Error from add_bib_entry: {e}")
            raise e

    def update_bib_entry(self, bib_data):
        try:
            bib_entry = get_object_or_404(
                        Bib_entries,
                        title=bib_data.get('title'),
                        year=bib_data.get('year'),
                        issue_volume=bib_data.get('issue_volume')
                        )
            for field, value in bib_data.items():
                setattr(bib_entry, field, value)
            # Save the updated entry
            bib_entry.save()
        except Http404:
            print("la cagué")
            print(f"{bib_data}")
            self.add_bib_entry(bib_data)

    def add_authors(self, author_data, bib_entry):
        bib_entry = Bib_entries.objects.get(**bib_entry)
        for author_type in author_data.keys():
            for author in author_data[author_type]:
                try:
                    author_obj, cr  = Author.objects.get_or_create(**author)
                    cat = Author_type.objects.get(type_of_author=author_type)
                    first_author = author == author_data[author_type][0]
                    this_author = Bib_author.objects.get_or_create(
                            id_author=author_obj,
                            id_article=bib_entry,
                            category=cat,
                            first_author=first_author
                            )
                except IntegrityError as e:
                    if "duplicate entry" in str(e).lower():
                        print(f"Already exists: {this_author}")
                        pass
                    else:
                        print("me cago en la puta")
                except Exception as e:
                    print("Será que entra directo aquí")
                    print(f"Processing: {author}")
                    print(e)

    def update_authors(self, author_data, bib_data):
        bib_entry = Bib_entries.objects.get(**bib_entry)
        for author_type in author_data.keys():
            for author in author_data[author_type]:
                try:
                    author_entry = get_object_or_404(
                                Author,
                                **author
                                )
                    for field, value in bib_data.items():
                        setattr(bib_entry, field, value)
                    # Save the updated entry
                    bib_entry.save()
                except Http404:
                    print("la cagué")
                    print(f"{bib_data}")
                    self.add_bib_entry(bib_data)

    def add_url(self, url_data, bib_entry, database):
        try:
            db_entry = Referenced_databases.objects.filter(
                    aliases__icontains=database
                    ).first()
            url_data['id_article'] = Bib_entries.objects.get(**bib_entry)
            url_data['id_database'] = db_entry
            url_data['main_url'] = True
            url, cr = Url_list.objects.get_or_create(**url_data)
        except IntegrityError as e:
            if "duplicate entry" in str(e).lower():
                print(f"Already exists: {url}")
                pass
            else:
                print(e)
        except Exception as e:
            print("Seré yo maestro?")
            print(e)
        return url_data

    async def process_entry(self, message):
        print('at least it started')
        database = message['database']
        errors = []
        processed_entries = 0
        total_entries = message['total_entries']
        for entry in message['library']:
            try:
                bib_data, author_data, url_data = parse_entry(entry)

                bib_entry = self.add_bib_entry(bib_data)

                self.add_authors(author_data, bib_entry)

                url_data = self.add_url(url_data, bib_entry, database)

                processed_entries += 1
                await self.channel_layer.group_send(
                    "progress_group",
                    {
                        "type": "update_progress",
                        "percentage": (processed_entries / total_entries)* 100,
                    }
                )
            except Exception as e:
                errors.append({
                    'bib_data': bib_data,
                    'author_data': author_data,
                    'url_data': url_data,
                    'error': str(e)
                })

        if errors:
            await self.channel_layer.group_send(
                "progress_group",
                {
                    "type": "process_errors",
                    "errors": errors,
                }
            )


class ProgressConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("progress_group", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
                "progress_group",
                self.channel_name
                )

    async def update_progress(self, event):
        percentage = event['percentage']
        await self.send(text_data=json.dumps({"percentage": percentage}))

    async def process_errors(self, event):
        errors = event['errors']
        await self.send(text_data=json.dumps({"errors": errors}))
