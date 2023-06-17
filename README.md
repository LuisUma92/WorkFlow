# Work Flow

This package contains a set of scripts that I use form writing my tesis


## NoRI -Note Reference Insertion

Script that search for study summary files, fallowing an specific structure
on [YAML](https://yaml.org/) file format, and look for notes on the files.
It returns a string output to [Neovim](https://neovim.io/), the note structure
on the summary file indicates whether is paraphrase o verbatim, so that inset
a $\LaTeX$ quotation reference respectively.

### Directory expected structure

```
ROOT
├── master.tex
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

### Summary expected structure

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


