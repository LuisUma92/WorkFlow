from django.contrib import admin
from .models import Reviewed,Tags,Rationale_list,Review_rationale,Keyword,Isn_list,Bib_author,Bib_entries,Article_tags,Author,Author_type,Abstract

# Register your models here.
admin.site.register(Abstract)
admin.site.register(Article_tags)
admin.site.register(Author)
admin.site.register(Author_type)
admin.site.register(Bib_author)
admin.site.register(Bib_entries)
admin.site.register(Isn_list)
admin.site.register(Keyword)
admin.site.register(Rationale_list)
admin.site.register(Review_rationale)
admin.site.register(Reviewed)
admin.site.register(Tags)
