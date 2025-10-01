# Work Flow Project

This package contains a set of scripts that I use form writing my tesis,
and work with latex.

## Packages

### lectkit

This group of python scripts are simple one file action that allows to make
interactions with files.

#### CleTA - Clean Tex Auxiliary files

This script remove common auxiliary files used by $\LaTeX$

#### NoFi - Notes to files

This script takes a plain tex file and creates subfiles for $\LaTeX$ to input.

Use the flag '%>' to define the 'path/to/file/to/make.tex' for create a new
$\LaTeX$ with the contents until next flag.

##### Example

'''tex
%>tex/C1/C1S1-001-file.tex
This lines are going to be copied to the file C1S1-001-file.tex at the
directory ./tex/C1
'''

##### Recommendation

Create a $\LaTeX$ file that input the plain tex file to compile as writing.

#### CreTE - Create Text Exercises

This script create all the files for exercises for a references book.
It uses a [json structure](Json Book-Exercises Structure) for each book.
You can define

##### Functions

###### init_books()

Create a global storage file

###### add_book(book_info)

Append a specified [book structure](Json Book-Exercises Structure) to the
global storage file

###### create_solution_file( start=1, end=1, ch=1, sec='01', book, verbose=2)

Require that the 'name=book' exists on the 'books.json' file from
'~.config/crete' directory.

###### exercises_file_content(ch, idx, book)

Returns a string formatted with the contents of each exercise file.

##### Json Book-Exercises Structure

```json
{
  "library": [
    {
       "name": "FirstAuthorLastname",
      "code": "MDS_code",
      "distro": [[ch,"sec",ini,end],]
    },
  ]
}
```

### ITeP - Init Tex Project

This scrip creates the structure for a $\LaTeX$ project.
The actual structure is on [structure files](./docs/ADR/structure.md).

#### To do

- Entries point: CLI, `config.yaml`
- Files per global structure that manage the main directory:
  `lecture.py`, `topic.py`
- Need a load `config.yaml` and in the file it must indicate the corresponding
  manager.
- Each structure files parse the corresponding `config.yaml`
- `init_structure.py` load up structure and creates directories and links
- `relink.py`

### PRISMAreview

This code is on pause. Another repository is developing it

#### NoRI - Note Reference Insertion

Script that search for study summary files, fallowing an specific structure
on [YAML](https://yaml.org/) file format, and look for notes on the files.
It returns a string output to [Neovim](https://neovim.io/), the note structure
on the summary file indicates whether is paraphrase o verbatim, so that inset
a $\LaTeX$ quotation reference respectively.

##### lib2bib

This script compares all files on lib directory with entries
on master.bib file. If a document on lib directory don't
have a bib entries it proceed to create one.

##### PRISMA 2020 - Register Structure

We use [PRIMA 2020](http://www.prisma-statement.org) for a
systematic review of the scientific article. This protocol
establishes the items to record for each Article Register.
This script interacts with a Data Base where Registers are
recorded.

###### Documentation

This library interacts via CLI and ask to input item by item,
then send the information to the DataBase.

###### To do list

- An interaction to the data base for Summary Notes creation.
- Bib automatic update.

##### Summary Notes structure

The summary consist of easy access files that provides the
notes, connections, ideas and other kinds of information
useful when writing essays.

```yaml
%YAML 1.2
---
Authors:
  - []
  - []

Title: |
  The title

Bib: | # citation-key defined on .bib file
  citation-key

Keywords:
  Article:
    - word 1
    - word 2
  Own:
  Nucleus:

Objective: |
  The objective

Definitions:
  Name:
    id:
    def: |
      the definition
    ideas: # list of personal conclusions or connections
      - |
        first idea or conclusion
    use: |
      examples or descriptions
    cite: # references made by authors on the source
      "[n],[n+2-n+4]"

Key-Ideas:

Conclusions:

References: # Source references
  n: the n reference
  n+2: other...
```

##### Dependencies

- [Inkscape figure manager](https://github.com/gillescastel/latex-snippets)
- [`rofi`](https://github.com/davatorium/rofi) for a selection dialog
