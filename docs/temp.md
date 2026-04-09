# Espacio para diseñar prompts complejas

## Exercise as module

- Use Option B
- some exercises are created to use in evaluations
- some exercises come from the books
- this should take into account the fact that each institutions have different requisites
- memory from this differences is at 00AA-Lecture memories
- tikz and exercises should just have enough latex information for their work, maybe it would be better to abstract latex common parsing into a third module

## Exercise parsing model

- Exercises `.tex` must live all together at `00EE-ExamplesExercises`
- Each project could link specific routes to import files into test, practices, homework
- Use option C
- Why are exercise text stored at db, wouldn't be better use the `.tex` as truth source and store just metadata and references to the actual file?
- How are images managed? The stem text can have images, some answer are diagrams and graph
- For orphaned records, can create a cron service that ensure periodic actualization, and should exist an one-time command to update exercises records
- `crete.py` create placeholder files, if all stem_text are at db isn't it a problem? there should be some way to register if a file is placeholder, is in process or incomplete, or if is complete

## Latex parsing

- Structure of \question{}{}
  - first argument is for stem_text, image for the question it self
  - second argument show information for solution render. If the question doesn't have parts, the answer goes here
- \qpart{}{}
  - first argument is the specific instruction of the part. It can include o not the points
  - Second argument is the solution for the specific instruction

## Moodle XML export

- There is a problem with mathJax, I don't control institutional libraries imported
- MathJax doesn't know my custom commands and colors defined at `share/sty`
- bd
