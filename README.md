# Work Flow

This package contains a set of scripts that I use form writing my tesis


## NoRI - Note Reference Insertion

Script that search for study summary files, fallowing an specific structure
on [YAML](https://yaml.org/) file format, and look for notes on the files.
It returns a string output to [Neovim](https://neovim.io/), the note structure
on the summary file indicates whether is paraphrase o verbatim, so that inset
a $\LaTeX$ quotation reference respectively.

### Directory expected structure

```
ROOT
├── master.tex
├── master.bib
├── lib
│   ├── bibkey-title.pdf
│   └── ...
├── lec
│   ├── lec_00.tex
│   ├── ...
│   └── lec_NN.tex
├── res
│   ├── sumary_00.tex
│   ├── ...
│   └── sumary_MM.tex
├── figures
│   ├── fig-00.pdf
│   ├── fig-00.pdf_tex
│   ├── fig-00.svg
│   └── ...
└── UltiSnips
    └── tex.snippets
```

### lib2bib

This script compares all files on lib directory with entries
on master.bib file. If a document on lib directory don't 
have a bib entries it proceed to create one.

### PRISMA 2020 - Register Structure

We use [PRIMA 2020](http://www.prisma-statement.org) for a
systematic review of the scientific article. This protocol
establishes the items to record for each Article Register.
This script interacts with a Data Base where Registers are
recorded. 

#### AddRegister()

This command interacts via CLI and ask to input item by item,
then send the information to de DB.

#### To do list

- An interaction to the data base for Summary Notes creation.
- Bib automatic update.

### Summary Notes structure

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
      '[n],[n+2-n+4]'

Key-Ideas:

Conclusions:

References: # Source references 
  n: the n reference
  n+2: other...
...
```

### Dependencies

* [Inkscape figure manager](https://github.com/gillescastel/latex-snippets)
* [`rofi`](https://github.com/davatorium/rofi) for a selection dialog

## CleTA - Clean Tex Auxiliary files

This scrip remove common auxiliary files used by $\LaTeX$




