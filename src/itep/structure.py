"""
This is a general structure that every project file should implement this
to its specific needs
"""


class project_structure:
    code = ""
    name = ""
    topics = []
    books = []

    def get_description(self, var_name):
        if var_name == "code":
            msn = "Alfanumeric code"
        elif var_name == "name":
            msn = "Name of the project"
        elif var_name == "topics":
            msn = "List of strings, each one name a topic of the project"
        elif var_name == "books":
            msn = "List of book codes related to the project"
        else:
            msn = f"ERROR: {var_name} is not a variable of this object: {self}"
        return msn

    def get_code(self):
        return self.code

    def set_code(self, code):
        self.code = code

    def get_name(self):
        return self.name

    def set_name(self, name):
        self.name = name
