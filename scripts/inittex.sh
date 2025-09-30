mkdir tex
mkdir tex/00-Glossaries
mkdir bib
mkdir img

export mytexcd=/home/luis/.config/mytex

cp $mytexcd/templates/00-Glossary.tex tex/00-Glossaries
cp $mytexcd/templates/01-Acronyms.tex tex/00-Glossaries
cp $mytexcd/templates/bibliography.bib bib
cp $mytexcd/templates/00AA.tex main.tex
