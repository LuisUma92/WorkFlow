# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete`
#       set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create,
#       modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field
#   names.
from django.db import models
from django.db.models.fields import CharField
from django.db.models.fields.related import ForeignKey
# from django.db.models import Q, constants, constraints


isn_value_list = {
    "isan": "isan",
    "isbn": "isbn",
    "ismn": "ismn",
    "isrn": "isrn",
    "issn": "issn",
    "iswc": "iswc",
}


class Isn_list(models.Model):
    id_isn = models.CharField(
        max_length=4,
        choices=isn_value_list,
    )

    def __str__(self):
        return str(self.id_isn)


class Tags(models.Model):
    tag = models.CharField(max_length=200)

    def __str__(self):
        return str(self.tag)


class Author(models.Model):
    first_name = models.CharField(max_length=40)
    last_name = models.CharField(max_length=200)
    alias = models.SmallIntegerField(default=0, blank=True, null=True)
    affiliation = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["first_name", "last_name"], name="unique_author_entry"
            )
        ]

    def __str__(self):
        return f"{self.last_name}, {self.first_name}"


author_type_list = {
    "author": "author",
    "bookauthor": "bookauthor",
    "editor": "editor",
    "afterword": "afterword",
    "annotator": "annotator",
    "commentator": "commentator",
    "forward": "forward",
    "introduction": "introduction",
    "translator": "translator",
    "holder": "holder",
}


class Author_type(models.Model):
    type_of_author = models.CharField(max_length=12, choices=author_type_list)

    def __str__(self):
        return str(self.type_of_author)


class Referenced_databases(models.Model):
    name = CharField(max_length=200, blank=True, null=True)
    proxy = CharField(max_length=400, blank=True, null=True)
    aliases = CharField(max_length=5000, blank=True, null=True)

    def __str__(self):
        return str(self.name)


class Bib_entries(models.Model):
    entry_type = models.CharField(max_length=100, blank=True, null=True)
    bibkey = models.CharField(max_length=200, blank=True, null=True)
    # database_name = models.CharField(
    #         max_length=20,
    #         blank=True,
    #         null=True,
    #         db_comment=""
    #         )
    institution = models.CharField(max_length=200, db_comment="", blank=True, null=True)
    organization = models.CharField(
        max_length=200, db_comment="", blank=True, null=True
    )
    publisher = models.CharField(max_length=200, blank=True, null=True)
    title = models.CharField(max_length=500, blank=True, null=True)
    indextitle = models.CharField(max_length=500, db_comment="", blank=True, null=True)
    booktitle = models.CharField(max_length=500, db_comment="", blank=True, null=True)
    maintitle = models.CharField(max_length=500, db_comment="", blank=True, null=True)
    journaltitle = models.CharField(
        max_length=200, db_comment="", blank=True, null=True
    )
    issuetitle = models.CharField(max_length=500, db_comment="", blank=True, null=True)
    eventtitle = models.CharField(max_length=500, db_comment="", blank=True, null=True)
    reprinttitle = models.CharField(
        max_length=500, db_comment="", blank=True, null=True
    )
    series = models.CharField(max_length=200, db_comment="", blank=True, null=True)
    issue_volume = models.CharField(max_length=20, blank=True, null=True)
    # volume
    issue_number = models.CharField(max_length=20, blank=True, null=True)
    # number
    part = models.CharField(max_length=20, db_comment="", blank=True, null=True)
    issue = models.CharField(max_length=20, db_comment="", blank=True, null=True)
    volumes = models.CharField(max_length=20, db_comment="", blank=True, null=True)
    edition = models.PositiveSmallIntegerField(db_comment="", blank=True, null=True)
    version = models.CharField(max_length=50, db_comment="", blank=True, null=True)
    pubstate = models.CharField(max_length=100, db_comment="", blank=True, null=True)
    pages = models.CharField(max_length=20, blank=True, null=True)
    pagetotal = models.CharField(max_length=20, db_comment="", blank=True, null=True)
    pagination = models.CharField(max_length=200, db_comment="", blank=True, null=True)
    publication_date = models.DateField(db_comment="", blank=True, null=True)
    # date
    month = models.CharField(max_length=10, blank=True, null=True)
    year = models.SmallIntegerField(db_comment="", blank=True, null=True)
    eventdate = models.DateField(db_comment="", blank=True, null=True)
    urldate = models.DateField(db_comment="", blank=True, null=True)
    location = models.CharField(max_length=100, db_comment="", blank=True, null=True)
    venue = models.CharField(max_length=200, db_comment="", blank=True, null=True)
    # url	= models.TextField(
    #         max_length=21844,
    #         db_comment="",
    #         blank=True,
    #         null=True
    #         )
    doi = models.TextField(max_length=21844, db_comment="", blank=True, null=True)
    eid = models.TextField(max_length=21844, db_comment="", blank=True, null=True)
    eprint = models.TextField(max_length=21844, db_comment="", blank=True, null=True)
    eprinttype = models.TextField(
        max_length=21844, db_comment="", blank=True, null=True
    )
    addendum = models.TextField(max_length=21844, db_comment="", blank=True, null=True)
    notes = models.TextField(max_length=21844, db_comment="", blank=True, null=True)
    # note
    howpublished = models.TextField(
        max_length=21844, db_comment="", blank=True, null=True
    )
    language = models.CharField(max_length=200, db_comment="", blank=True, null=True)
    isn = models.CharField(max_length=200, blank=True, null=True)
    isn_type = models.ForeignKey(
        Isn_list, on_delete=models.PROTECT, blank=True, null=True
    )
    abstract_text = models.TextField(
        max_length=21844, db_comment="", blank=True, null=True
    )
    annotation = models.TextField(
        max_length=21844, db_comment="", blank=True, null=True
    )
    file_path = models.TextField(max_length=21844, db_comment="", blank=True, null=True)
    # file
    library = models.CharField(max_length=500, db_comment="", blank=True, null=True)
    label = models.CharField(max_length=500, db_comment="", blank=True, null=True)
    shorthand = models.CharField(max_length=500, db_comment="", blank=True, null=True)
    shorthandintro = models.TextField(
        max_length=21844, db_comment="", blank=True, null=True
    )
    execute_task = models.TextField(
        max_length=21844, db_comment="", blank=True, null=True
    )
    keywords = models.TextField(max_length=21844, db_comment="", blank=True, null=True)
    options = models.TextField(max_length=21844, db_comment="", blank=True, null=True)
    ids = models.CharField(max_length=500, db_comment="", blank=True, null=True)
    references = models.ManyToManyField("self", symmetrical=False, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["title", "year", "issue_volume"], name="unique_bib_entry"
            )
        ]

    def __str__(self):
        msn = ""
        title = str(self.title)
        if len(title) < 70:
            msn = f"({self.year}, No{self.issue_volume})-{title}"
        else:
            msn = f"({self.year}, No{self.issue_volume})-{title[:70]}"
        return msn


class Bib_author(models.Model):
    first_author = models.BooleanField(default=0)
    id_author = models.ForeignKey(Author, on_delete=models.PROTECT)
    id_article = models.ForeignKey(Bib_entries, on_delete=models.PROTECT)
    category = models.ForeignKey(Author_type, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["id_author", "id_article", "category"],
                name="unique_author_function_per_article",
            )
        ]


class Url_list(models.Model):
    id_article = models.ForeignKey(Bib_entries, on_delete=models.PROTECT)
    id_database = ForeignKey(Referenced_databases, on_delete=models.PROTECT)
    url_string = models.CharField(max_length=500)
    main_url = models.BooleanField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["id_article", "id_database"], name="unique_url_per_database"
            )
        ]

    def __str__(self):
        msn = f"URL for {self.id_article} at {self.id_database}"
        msn += "\n{self.url_string}"
        return msn


class Keyword(models.Model):
    keyword_list = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.keyword_list}"


class Reviewed(models.Model):
    id_key = models.ForeignKey(Keyword, on_delete=models.PROTECT)
    id_article = models.ForeignKey(Bib_entries, on_delete=models.PROTECT)
    retrieved = models.SmallIntegerField(default=0, blank=True, null=True)
    included = models.SmallIntegerField(default=0, blank=True, null=True)
    include_rationale = models.TextField(max_length=21844, blank=True, null=True)
    reatrive_rationale = models.TextField(max_length=21844, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["id_key", "id_article"],
                name="unique_review_per_article_per_keyword",
            )
        ]

    def __str__(self):
        return f"Inclusion for:\n{self.id_article}\nWith: {self.id_key}"


class Abstract(models.Model):
    id_article = models.ForeignKey(Bib_entries, on_delete=models.PROTECT)
    background = models.TextField(
        max_length=21844, db_comment="", blank=True, null=True
    )
    objectives = models.TextField(
        max_length=21844, db_comment="", blank=True, null=True
    )
    eligibility_criteria = models.TextField(
        max_length=21844, db_comment="", blank=True, null=True
    )
    information_sources = models.TextField(
        max_length=21844, db_comment="", blank=True, null=True
    )
    methods_synthesis = models.TextField(
        max_length=21844, db_comment="", blank=True, null=True
    )
    results_synthesis = models.TextField(
        max_length=21844, db_comment="", blank=True, null=True
    )
    discussion_conclusion = models.TextField(
        max_length=21844, db_comment="", blank=True, null=True
    )
    registration = models.TextField(
        max_length=21844, db_comment="", blank=True, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"PRISMA 2020 abstract checklist for {self.id_article}"


class Rationale_list(models.Model):
    rationale_argument = models.CharField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.rationale_argument)


class Review_rationale(models.Model):
    id_key = models.ForeignKey(Keyword, on_delete=models.PROTECT)
    id_article = models.ForeignKey(Bib_entries, on_delete=models.PROTECT)
    id_rationale = models.ForeignKey(Rationale_list, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["id_key", "id_article", "id_rationale"],
                name="dont_repit_rationale_per_article_per_keyword",
            )
        ]


class Article_tags(models.Model):
    id_tag = models.ForeignKey(Tags, on_delete=models.PROTECT)
    id_article = models.ForeignKey(Bib_entries, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["id_tag", "id_article"], name="dont_repit_tags_per_article"
            )
        ]


class Prisma2020Checklist(models.Model):
    id_article = models.ForeignKey(Bib_entries, on_delete=models.PROTECT)
    abstract = models.TextField(
        help_text="Abstract of the systematic review or meta-analysis."
    )
    registration = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Registration details (PROSPERO registration number).",
    )
    information_sources = models.TextField(
        help_text="Information sources used in the review (databases, registries)."
    )
    search_strategy = models.TextField(help_text="Search strategy details.")
    selection_process = models.TextField(
        help_text="Process for selecting studies (screening and inclusion)."
    )
    data_collection_process = models.TextField(
        help_text="Process for data collection (data extraction methods)."
    )
    data_items = models.TextField(
        help_text="List of all variables for which data were sought (PICO elements)."
    )
    study_risk_of_bias_assessment = models.TextField(
        help_text="Methods for assessing risk of bias in the included studies."
    )
    effect_measures = models.TextField(
        help_text="Effect measures (risk ratios, mean differences)."
    )
    synthesis_methods = models.TextField(
        help_text="Methods used to synthesize results."
    )
    reporting_bias_assessment = models.TextField(
        help_text="Methods used to assess reporting biases."
    )
    certainty_assessment = models.TextField(
        help_text="Methods for assessing the certainty of the body of evidence."
    )
    results_study_selection = models.TextField(
        help_text="Results of the study selection process (e.g., PRISMA flow diagram)."
    )
    results_study_characteristics = models.TextField(
        help_text="Characteristics of the included studies."
    )
    results_risk_of_bias_in_studies = models.TextField(
        help_text="Risk of bias in the included studies."
    )
    results_synthesis = models.TextField(
        help_text="Synthesis of the results (e.g., meta-analysis)."
    )
    results_reporting_biases = models.TextField(
        help_text="Results of the assessment of reporting biases."
    )
    results_certainty_of_evidence = models.TextField(
        help_text="Certainty of the evidence (e.g., GRADE)."
    )
    discussion_summary_of_evidence = models.TextField(
        help_text="Summary of the main findings."
    )
    discussion_limitations = models.TextField(
        help_text="Limitations of the evidence and the review process."
    )
    discussion_conclusions = models.TextField(
        help_text="General interpretation of the results."
    )
    funding = models.TextField(
        help_text="Details of funding sources and conflicts of interest."
    )
    accessibility_of_data = models.TextField(
        help_text="Accessibility of data, code, and other resources."
    )
    acknowledgements = models.TextField(
        help_text="Acknowledgements (e.g., contributors, peer reviewers)."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "PRISMA 2020 Checklist"
        verbose_name_plural = "PRISMA 2020 Checklists"

    def __str__(self):
        return f"PRISMA 2020 Checklist for {self.id_article}"
