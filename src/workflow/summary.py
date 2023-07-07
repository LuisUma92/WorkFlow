from pathlib import Path



class Summary:

    def __init__(self, name="summary",path="/home"):
        self.fileName = name
        self.filePath = Path(path)
        self.fileContent = "%YAML 1.2\n---\n"
        self.author = []
        self.title = ""
        self.bib = ""
        self.keyWords = {
            "Article":[],
            "Own":[],
            "Nucleus":["\\nc{}{}"]
        }
        self.objective = ""
        self.definitions = {
            "Name":{
                "id":"",
                "def":"",
                "ideas":"",
                "cite":"",
            }
        }
        self.keyIdeas = []
        self.conclusions = []
        self.references = []
        self.charLim = 65

    def save(self):
        # write Authors
        self.fileContent += "Authors:\n"
        if len(self.author) >= 1:
            for thisAuthor in self.author:
                self.fileContent += f"  - [{thisAuthor[0]},{thisAuthor[1]}]\n"
            self.fileContent += "\n"
        else:
            self.fileContent += "  - [None,None]\n\n"
        # write title
        self.fileContent += "Title: |\n"
        self.saveText(self.title)
        self.fileContent += "\n"
        # write bib citation key
        self.fileContent += "Bib: |# citation-key defined on .bib file\n"
        self.saveText(self.bib)
        self.fileContent += "\n"
        # write key words
        self.fileContent += "Keywords:\n"
        self.saveDict(self.keyWords)
        self.fileContent += "\n"
        # write objetives
        self.fileContent += "Objective: |\n"
        self.saveText(self.objective)
        self.fileContent += "\n"
        # write Definitions
        self.fileContent += "Definitions:\n"
        self.saveDict(self.definitions)
        self.fileContent += "\n"
        #write Kew Ideas
        self.fileContent += "Key-Ideas:\n"
        self.saveList(self.keyIdeas)
        self.fileContent += "\n"
        self.fileContent += "Conclusions:"
        self.saveList(self.conclusions)
        self.fileContent += "\n"
        self.fileContent += "References: # Source references"
        self.saveList(self.references)
        self.fileContent += "\n"
        self.fileContent += "..."
        outputName = self.fileName + ".yaml"
        saveTo = self.filePath / outputName
        with open(saveTo, "w") as file:
            file.write(self.fileContent)

    def saveText(self, text, level = 1):
        if len(text) > self.charLim:
            for line in sentence2multipleLines(text, maxCharacterLine=self.charLim):
                self.fileContent += "  " * level
                self.fileContent += f"{line}\n"
        else:
            self.fileContent += "  " * level
            self.fileContent += f"{text}\n"

    def saveList(self, contentList, level = 1):
        for content in contentList:
            self.fileContent += "  " * level
            self.fileContent += "- |\n"
            self.saveText(content, level + 1)

    def saveDict(self,contentDict,level=1):
        for thisKey, content in contentDict.items():
                self.fileContent += "  " * level
                self.fileContent += f"{thisKey}:"
                contentLevel = level + 1
                if type(content) is str:
                    self.fileContent += " |\n"
                    self.saveText(content, contentLevel)
                elif type(content) is list:
                    self.saveList(content, contentLevel)
                elif type(content) is dict:
                    self.saveDict(content, contentLevel)


# Utility function separate one sentence into multiple lines with 
# a max length 
def sentence2multipleLines(sentence,maxCharacterLine = 70):
    wordList = sentence.split(" ")
    multipleLines = []
    i = 0
    while i < len(wordList):
        outputLine = wordList[i]
        i += 1
        c = 0
        while c <= maxCharacterLine:
                outputLine = f" {wordList[i]}"
                i += 1
                if i < len(wordList):
                        c = len(outputLine)
                else:
                        c = maxCharacterLine + 1
        multipleLines.append(outputLine)
    return multipleLines

