# Lectures structure

Para organizar la tesis en un directorio con el siguiente orden:

## Variables

```bash
ABS_SRC_DIR = /home/luis/.config/mytex
ABS_PARENT_DIR = /home/luis/Documents/01-U/00-Fisica
LECTURE_CODE = `AA{:04d}`
MAIN_NAME = `Name`
MAIN_CODE = `{:02d}AA`
ROOT = `${MAIN_CODE}+${MAIN_NAME}`
ABS_PROJECT_DIR = `(pwd)/${ROOT}`
```

## Main directory structure

```bash
${ABS_PARENT_DIR}/${ABS_PROJECT_DIR}
├─ lect
│ └─ ${LECTURE_CODE}
│ ├─ admin
│ ├─ eval
│ │ └─ {T{TN:02d}}
│ │ └─ {bookName} -> ${ABS_PARENT_DIR}/00EE-ExamplesExercises/{bookName}/
│ ├─ press
│ │ ├─ config
│ │ │ ├─ 0_packages.sty -> ${ABS_SRC_DIR}/sty/SetFormatP.sty
│ │ │ ├─ 1_loyaut.sty -> ${ABS_SRC_DIR}/sty/SetLoyaut.sty
│ │ │ ├─ 2_commands.sty -> ${ABS_SRC_DIR}/sty/SetCommands.sty
│ │ │ ├─ 3_units.sty -> ${ABS_SRC_DIR}/sty/SetUnits.sty
│ │ │ ├─ 4_biber.sty -> ${ABS_PARENT_DIR}/{##AA-Name}/config/4_biber.sty
│ │ │ ├─ 5_profiles.sty -> ${ABS_SRC_DIR}/sty/SetProfiles.sty
│ │ │ ├─ 6_headers.sty -> ${ABS_SRC_DIR}/sty/SetHeaders.sty
│ │ │ └─ title.tex -> ${ABS_SRC_DIR}/templates/title.tex
│ │ ├─ bib/ -> ${ABS_PARENT_DIR}/{##AA-Name}/bib
│ │ ├─ img/ -> ${ABS_PARENT_DIR}/{##AA-Name}/img
│ │ ├─ {T##}/ -> ${ABS_PARENT_DIR}{##AA-Name}/tex/{C##S##}/
│ │ └─ {T##}.tex
│ └─ config.yaml
├─ tex
│ ├─ notes
│ ├─ resumes
│ ├─ {C##S##}
│ │ └─ {topic01}.tex
│ └─ {C##S##}.tex
├─ bib
│ └─ {topic01} -> ${ABS_PARENT_DIR}/00BB-Library/{topic01}/
├─ img
│ ├─ own
│ └─ {bookName} -> ${ABS_PARENT_DIR}/00II-ImagesFigures/{bookName}/
├─ config
│ ├─ 0_packages.sty -> ${ABS_SRC_DIR}/sty/SetFormat.sty
│ ├─ 1_loyaut.sty -> ${ABS_SRC_DIR}/sty/SetLoyaut.sty
│ ├─ 2_commands.sty -> ${ABS_SRC_DIR}/sty/SetCommands.sty
│ ├─ 3_units.sty -> ${ABS_SRC_DIR}/sty/SetUnits.sty
│ ├─ 4_biber.sty
│ ├─ 5_profiles.sty -> ${ABS_SRC_DIR}/sty/SetProfiles.sty
│ ├─ 6_headers.sty -> ${ABS_SRC_DIR}/sty/SetHeaders.sty
│ └─ title.tex -> ${ABS_SRC_DIR}/templates/title.tex
├─ pro
├─ {##AA}.tex
└─ README.md
```

## Lectures structure

Hay cursos que como mezclan varios temas principales están agrupados en
un solo directorio. Cada curso tiene un directorio con el siguiente esquema

```bash
${ABS_PARENT_DIR}/00AA-Lectures
└─ ${LECTURE_CODE}
├─ admin
├─ eval
│ └─ {T##}
│ └─ {bookName} -> ${ABS_PARENT_DIR}/00EE-ExamplesExercises/{bookName}/
├─ press
│ ├─ config
│ │ ├─ 0_packages.sty -> ${ABS_SRC_DIR}/sty/SetFormatP.sty
│ │ ├─ 1_loyaut.sty -> ${ABS_SRC_DIR}/sty/SetLoyaut.sty
│ │ ├─ 2_commands.sty -> ${ABS_SRC_DIR}/sty/SetCommands.sty
│ │ ├─ 3_units.sty -> ${ABS_SRC_DIR}/sty/SetUnits.sty
│ │ ├─ 4_biber.sty
│ │ ├─ 5_profiles.sty -> ${ABS_SRC_DIR}/sty/SetProfiles.sty
│ │ ├─ 6_headers.sty -> ${ABS_SRC_DIR}/sty/SetHeaders.sty
│ │ └─ title.tex -> ${ABS_SRC_DIR}/templates/title.tex
│ ├─ bib
│ │ ├─ ${ROOT1}/ -> ${ABS_PARENT_DIR}/{ROOT1}/bib
│ │ └─ ${ROOT2}/ -> ${ABS_PARENT_DIR}/{ROOT2}/bib
│ ├─ img
│ │ ├─ ${ROOT1}/ -> ${ABS_PARENT_DIR}/{ROOT1}/img
│ │ └─ ${ROOT2}/ -> ${ABS_PARENT_DIR}/{ROOT2}/img
│ ├─ {T##}
│ │ ├─ ${ROOT1}-{C##S##} -> {ABS_PROJECT_DIR1}/tex/{C##S##}/
│ └─ {T##}.tex
└─ config.yaml
```

## Common files structure

Consdiere que existe el siguiente directorio

```bash
/home/luis/.config/mytex
├── img
│   ├── BoldR.png
│   └── ScriptR.png
├── inittex.sh
├── sty
│   ├── ColorsLight.sty
│   ├── PartialCommands.sty
│   ├── SetCommands.sty
│   ├── SetConstant.sty
│   ├── SetFormat.sty
│   ├── SetFormatP.sty
│   ├── SetHeaders.sty
│   ├── SetLoyaut.sty
│   ├── SetProfiles.sty
│   └── SetSymbols.sty
└── templates
    ├── 00AA.tex
    ├── 00-Glossary.tex
    ├── 01-Acronyms.tex
    ├── bibliography.bib
    ├── book-C00S00P000.tex
    ├── C0S0-000.tex
    ├── lect.tex
    ├── PartialPropousal.tex
    ├── PN-YYYY-IIIC.tex
    ├── tiks-machote.tex
    ├── title.tex
    ├── TNN.tex
    └── TNNE000.tex
```

En el directorio a crear las siguientes expresiones son variables del tipo
string cuyos caracteres son como se indican:

```bash
{##AA-Name}
{T##}
{C##S##}
```

De manera que cada `#` representa un número las letras `AA` deben ser
sustituidas
Las palabra `Name` debe ser sustituido.
Las letras `T`, `C` y `S` deben mantenerse.

Además la variable `{##AA}` debe ser lo que se indica en los primeros 4
caracteres de la variable `{##AA-Name}`

Necesito un scrip en bash que solicite el número de 2 dígitos que acompaña
el `{##AA-Name}` y el `{##AA}`, que pida las dos letras que se deben cambiar
por `AA`, que pida el nombre del directorio principal que se debe colocar en
lugar de `Name`.
Que solicite la cantidad de temas a crear.
La cantidad de temas a crear es un número entero.

Se debe crear cada carpeta, comenzando por `{##AA-Name}` pero empleando
los valores ingresados por el usuario.
Las carpetas y archivos asociados a la variable `{C##S##}`, `{bookName}` y
`{topic01}` deben ignorarse,
estas carpetas y archivos las creará otro script.

También se debe ignorar la craeación de los directorios `{T##}`

Se debe una copia del archivo `${ABS_SRC_DIR}/templates/TNN.tex`
con el nombre `T##.tex` para cada número desde el `01` hasta el número
indicado.
Note que todos los números son enteros y se escriben con dos dígitos,
rellenando con cero a la izquierda para números entre el 1 y el 9.

Luego debe crear un soft link para cara archivo que está seguido por los
caracteres `->`, donde lo primero es el nombre del archivo y
lo que sigue de esos caracteres es path absoluto al archivo que se debe
referenciar.

Debe crear una copia de `${ABS_SRC_DIR}/templates/00AA.tex` con el nombre
correcto `##AA.tex` empleado los valores ingresados por el usuario.

Debe crear el archivo `4_biber.sty`
Debe escribir dentro del archivo `4_biber.sty` el siguiente texto

```tex
\addbibresources{bib/}
```

Debe crear el archivo `README.md`

Y debe escribir en el archivo, usando el formato adecuado de markdown
el valor ingresado para `Name` como un header 1.

Debe escribir con formato header 2 las siguientes secciones:

- `Tabla de Contenidos`
- `Distribución de temas en el curso`
- `Bibliografía`
- `Pendientes`

En la sección de `Tabla de contenidos` se debe emplear algún mecanismo de
markdown para autogenerar un índice.
Se puede usar la versión de markdown que emplea github.com

En la sección de `Distribución de temas en el curso` se debe escribir una
lista no enumerada donde cada item corresponda con el nombre de todos los
archivos creados con el formato `T##.tex` pero sin incluir los caracteres
`.tex`

En la sección de `Pendientes` debe iniciar una todo list con el formato
adecuado para que presente como lista de pendientes indicando los siguientes
items

- Agregar libros y códigos a `README.md`.
- Crear carpetas con el link adecuado por cada libro tanto en `img/`
  como en `eval/TNN/`.
- Crear carpetas de las secciones correspondientes al curso.
