# Physics project structure

Para organizar la tesis en un directorio con el siguiente orden:

## Variables

```bash
ABS_SRC_DIR=/home/luis/.config/mytex
ABS_PARENT_DIR=/home/luis/Documents/01-U/00-Fisica
ABS_DOCUMENTS_DIR=/home/luis/Documents
LECTURE_CODE='AA{:04d}'
MAIN_NAME='Name'
MAIN_CODE='{:02d}AA'
ROOT='${MAIN_CODE}+${MAIN_NAME}'
ABS_PROJECT_DIR='(pwd)/${ROOT}'
BOOK_REFERENCE='{MDS_code}_{FirstAuthorLastname}_E{Edition:02d}'
```

## Base directories structure

### Common Lectures

```bash
${ABS_PARENT_DIR}/00AA-Lectures
├──  UCIMED-CB0009
├──  UCR-FS0121
├──  UCR-FS0210
├──  UCR-FS0310
├──  UCR-FS0410
├──  Ufide-0225
├──  Ufide-0340
├──  Ufide-0430
└─ ${LECTURE_CODE}
```

### Library

```bash
${ABS_DOCUMENTS_DIR}/02-Library
├──  515-39-Chaos
├──  523-10-Universe
├──  530-00-Physics
│   ├──  00DT-Cambridge_Lectures-David_Tong
│   └──  IWIV6K~N
├──  530-07-EducationResearch
├──  530-11-Relativity
├──  530-12-QuantumMechanics
│   ├──  Decoherencia
│   ├──  NuclearTheory
│   ├──  PathIntegrals
│   └──  TimeOperator
├──  530-13-Statistical Physics
├──  530-14-FieldAndStringTheories
│   ├──  218-AdvancedQuantumFieldTheory-UC
│   └──  InfraredDivergence
├──  530-15-ComputationalPhysics
│   └──  Geant4
├──  530-15-MathematicalPhysics
│   └──  Nonlinear
├──  530-72-InstrumentationResearch
├──  530-80-Physical units measuring instruments
├──  531-00-Mechanics
│   └──  articles
├──  531-10-ParticleMechanics
├──  531-20-SolidState
│   └──  MaterialCharacterization
├──  535-00-Optics
│   ├──  OpticFiber
│   └──  RefractionIndex
├──  536-7-Termodinamics
├──  537-10-ElectromagneticTheory
│   └──  DarkCurrent
├──  539-70-AtomicNuclear
│   ├──  AMS
│   ├──  Applaied-Antropology
│   ├──  AtomicBeamMagneticResonance
│   ├──  BetasTotales
│   ├──  Dosimetry
│   ├──  FRN-7Be
│   ├──  GammaSpectroscopy-226Ra235UCorrection
│   ├──  GammaSpectroscopy-CascadeCorrection-Anticoincidence
│   ├──  GammaSpectroscopy-Cs137Soils
│   ├──  GammaSpectroscopy-HpGEDeathTime
│   ├──  GammaSpectroscopy-HPGeOptimization
│   ├──  GammaSpectroscopy-ParametersVality
│   ├──  GammaSpectroscopy-SensorsManuals
│   ├──  HPGe
│   ├──  HyperfineStructure
│   ├──  IsotopesApplication-TraceMetals
│   ├──  IsotopesApplications
│   ├──  MeasurementXRay
│   ├──  NaturalOriginatedRadionucleiMaterial
│   ├──  NuclearModel-ShellModel
│   ├──  ParticleAcceleration
│   ├──  PracticalSpectroscopySeries
│   ├──  SciFi
│   ├──  Scintillation
│   ├──  SiPM
│   ├──  Spectroscopy
│   ├──  toSort
│   └──  XRF
├──  ${topic01}
│   └──  ${sub-topic01}
└─ ${documents_to_sort}
```

### Solved exercises

This directories are created with [CreTE][../../src/lectkit/crete.py].
It uses the structure for each book described on [Json Book-Exercises Structure](../..//README.md)

```bash
${ABS_PARENT_DIR}/00EE-ExamplesExercises
├──  10MC
├──  20TD
├──  40EM
├──  50MQ
├──  er-530_R434f4-resnickF4
│   ├──  530-Resnickf4-C15
│   └──  530-Resnickf4-C19
├──  er-530_R434f5-resnick
│   ├──  530-Resnick-C01
│   ├──  530-Resnick-C02
│   ├──  530-Resnick-C03
│   ├──  530-Resnick-C04
│   ├──  530-Resnick-C05
│   ├──  530-Resnick-C06
│   ├──  530-Resnick-C07
│   ├──  530-Resnick-C08
│   ├──  530-Resnick-C09
│   ├──  530-Resnick-C10
│   ├──  530-Resnick-C11
│   ├──  530-Resnick-C12
│   ├──  530-Resnick-C13
│   ├──  530-Resnick-C14
│   ├──  530-Resnick-C15
│   ├──  530-Resnick-C16
│   ├──  530-Resnick-C17
│   ├──  530-Resnick-C18
│   ├──  530-Resnick-C19
│   ├──  530-Resnick-C20
│   ├──  530-Resnick-C21
│   ├──  530-Resnick-C22
│   ├──  530-Resnick-C23
│   ├──  530-Resnick-C24
│   ├──  530-Resnick-C25
│   ├──  530-Resnick-C26
│   ├──  530-Resnick-C27
│   ├──  530-Resnick-C28
│   ├──  530-Resnick-C29
│   ├──  530-Resnick-C30
│   ├──  530-Resnick-C31
│   ├──  530-Resnick-C32
│   ├──  530-Resnick-C33
│   ├──  530-Resnick-C34
│   ├──  530-Resnick-C35
│   ├──  530-Resnick-C36
│   ├──  530-Resnick-C37
│   ├──  530-Resnick-C38
│   ├──  530-Resnick-C39
│   ├──  530-Resnick-C40
│   ├──  530-Resnick-C41
│   ├──  530-Resnick-C42
│   ├──  530-Resnick-C43
│   ├──  530-Resnick-C44
│   ├──  530-Resnick-C45
│   ├──  530-Resnick-C46
│   ├──  530-Resnick-C47
│   ├──  530-Resnick-C48
│   ├──  530-Resnick-C49
│   ├──  530-Resnick-C50
│   ├──  530-Resnick-C51
│   └──  530-Resnick-C52
├──  er-530_S439fi14-sears
│   ├──  530-Sears-C01
│   ├──  530-Sears-C02
│   ├──  530-Sears-C03
│   ├──  530-Sears-C04
│   ├──  530-Sears-C05
│   ├──  530-Sears-C06
│   ├──  530-Sears-C07
│   ├──  530-Sears-C08
│   ├──  530-Sears-C09
│   ├──  530-Sears-C10
│   ├──  530-Sears-C11
│   ├──  530-Sears-C12
│   ├──  530-Sears-C13
│   ├──  530-Sears-C14
│   ├──  530-Sears-C15
│   ├──  530-Sears-C16
│   ├──  530-Sears-C17
│   ├──  530-Sears-C18
│   ├──  530-Sears-C19
│   ├──  530-Sears-C20
│   ├──  530-Sears-C21
│   ├──  530-Sears-C22
│   ├──  530-Sears-C23
│   ├──  530-Sears-C24
│   ├──  530-Sears-C25
│   ├──  530-Sears-C26
│   ├──  530-Sears-C27
│   ├──  530-Sears-C28
│   ├──  530-Sears-C29
│   ├──  530-Sears-C30
│   ├──  530-Sears-C31
│   ├──  530-Sears-C32
│   ├──  530-Sears-C33
│   ├──  530-Sears-C34
│   ├──  530-Sears-C35
│   ├──  530-Sears-C36
│   ├──  530-Sears-C37
│   ├──  530-Sears-C38
│   ├──  530-Sears-C39
│   ├──  530-Sears-C40
│   ├──  530-Sears-C41
│   ├──  530-Sears-C42
│   ├──  530-Sears-C43
│   └──  530-Sears-C44
├──  er-530_S492fi10-Serway
│   ├──  530-Serway-C01
│   ├──  530-Serway-C02
│   ├──  530-Serway-C03
│   ├──  530-Serway-C04
│   ├──  530-Serway-C05
│   ├──  530-Serway-C06
│   ├──  530-Serway-C07
│   ├──  530-Serway-C08
│   ├──  530-Serway-C09
│   ├──  530-Serway-C10
│   ├──  530-Serway-C11
│   ├──  530-Serway-C12
│   ├──  530-Serway-C13
│   ├──  530-Serway-C14
│   ├──  530-Serway-C15
│   ├──  530-Serway-C16
│   ├──  530-Serway-C17
│   ├──  530-Serway-C18
│   ├──  530-Serway-C19
│   ├──  530-Serway-C20
│   ├──  530-Serway-C21
│   ├──  530-Serway-C28
│   ├──  530-Serway-C29
│   ├──  530-Serway-C30
│   ├──  530-Serway-C31
│   └──  530-Serway-C36
└──  er-530_W696f6-wilson
    ├──  530-Wilson-C01
    ├──  530-Wilson-C02
    ├──  530-Wilson-C03
    ├──  530-Wilson-C04
    ├──  530-Wilson-C05
    ├──  530-Wilson-C06
    ├──  530-Wilson-C07
    ├──  530-Wilson-C08
    ├──  530-Wilson-C09
    ├──  530-Wilson-C10
    ├──  530-Wilson-C11
    ├──  530-Wilson-C12
    ├──  530-Wilson-C13
    ├──  530-Wilson-C14
    ├──  530-Wilson-C15
    ├──  530-Wilson-C16
    ├──  530-Wilson-C17
    ├──  530-Wilson-C18
    ├──  530-Wilson-C19
    ├──  530-Wilson-C20
    ├──  530-Wilson-C21
    ├──  530-Wilson-C22
    ├──  530-Wilson-C23
    ├──  530-Wilson-C24
    └──  530-Wilson-C25
```

### Figures

```bash
${ABS_PARENT_DIR}/00II-ImagesFigures
├──  10MC
│   ├──  NIST
│   └──  own
├──  20TD
├──  40EM
├──  530_B344f1-Bauer
├──  530_G433f4-Giancoli
├──  530_R434f4-resnickF4
├──  530_R434f5-resnick
├──  530_S439fi12-Sears
├──  530_S439fi14-Sears
├──  530_S492fi10-Serway
├──  530_W696f6
└──  icons
```

## Main topic directory structure

```bash
${ABS_PARENT_DIR}/${ROOT}
├─ tex
│  ├─ notes
│  ├─ resumes
│  └─ 'C{ch:02d}S{sec}'
│     └─ '{par:03d}-{content_name}.tex'
├─ bib
│  └─ FROM_ZOTERO.bib
├─ img
│  ├─ own -> ${ABS_PARENT_DIR}/00II-ImagesFigures/${CODE}
│  └─ '{BOOK_REFERENCE}' -> ${ABS_PARENT_DIR}/00II-ImagesFigures/${BOOK_REFERENCE}
├─ config
│  ├─ 0_packages.sty -> ${ABS_SRC_DIR}/sty/SetFormat.sty
│  ├─ 1_loyaut.sty -> ${ABS_SRC_DIR}/sty/SetLoyaut.sty
│  ├─ 2_commands.sty -> ${ABS_SRC_DIR}/sty/SetCommands.sty
│  ├─ 3_units.sty -> ${ABS_SRC_DIR}/sty/SetUnits.sty
│  ├─ 4_biber.sty
│  ├─ 5_profiles.sty -> ${ABS_SRC_DIR}/sty/SetProfiles.sty
│  ├─ 6_headers.sty -> ${ABS_SRC_DIR}/sty/SetHeaders.sty
│  └─ title.tex -> ${ABS_SRC_DIR}/templates/title.tex
├─ pro
├─ config.yaml
├─ '{MAIN_CODE}.tex'
└─ README.md
```

## Lectures structure

Some courses combine several main topics and are grouped into a single
directory.
Each course has a directory with the following structure.

```bash
${ABS_PARENT_DIR}/00AA-Lectures
└─ ${LECTURE_CODE}
   ├─ admin
   ├─ eval
   │  ├─ config
   │  │  ├─ 0_packages.sty -> ${ABS_SRC_DIR}/sty/SetFormatP.sty
   │  │  ├─ 1_loyaut.sty -> ${ABS_SRC_DIR}/sty/SetLoyaut.sty
   │  │  ├─ 2_commands.sty -> ${ABS_SRC_DIR}/sty/SetCommands.sty
   │  │  ├─ 2_partial.sty -> ${ABS_SRC_DIR}/sty/PartialCommands.sty
   │  │  ├─ 3_units.sty -> ${ABS_SRC_DIR}/sty/SetUnits.sty
   │  │  ├─ 4_biber-{ROOT1}.sty -> ${ABS_PARENT_DIR}/${ROOT1}/config/4_biber.sty
   │  │  ├─ 4_biber-{ROOT2}.sty -> ${ABS_PARENT_DIR}/${ROOT2}/config/4_biber.sty
   │  │  ├─ 5_profiles.sty -> ${ABS_SRC_DIR}/sty/SetProfiles.sty
   │  │  └─ 6_headers.sty -> ${ABS_SRC_DIR}/sty/SetHeaders.sty
   │  ├─ img
   │  │  ├─ '{BOOK_REFERENCE}' -> ${ABS_SRC_DIR}/00II-ImagesFigures/${BOOK_REFERENCE}
   │  │  └─ own
   │  └─ 'T{TN:02d}'
   │     └─ '{BOOK_REFERENCE}-C{ch:02d}' -> ${ABS_PARENT_DIR}/00EE-ExamplesExercises/er-${BOOK_REFERENCE}/${BOOK_REFERENCE}-C${ch:02ed}
   ├─ press
   │  ├─ config
   │  │  ├─ 0_packages.sty -> ${ABS_SRC_DIR}/sty/SetFormatP.sty
   │  │  ├─ 1_loyaut.sty -> ${ABS_SRC_DIR}/sty/SetLoyaut.sty
   │  │  ├─ 2_commands.sty -> ${ABS_SRC_DIR}/sty/SetCommands.sty
   │  │  ├─ 3_units.sty -> ${ABS_SRC_DIR}/sty/SetUnits.sty
   │  │  ├─ '4_biber-{LECTURE_CODE}.sty'
   │  │  ├─ '4_biber-{ROOT1}.sty' -> ${ABS_PARENT_DIR}/${ROOT1}/config/4_biber.sty
   │  │  ├─ '4_biber-{ROOT2}.sty' -> ${ABS_PARENT_DIR}/${ROOT2}/config/4_biber.sty
   │  │  ├─ 5_profiles.sty -> ${ABS_SRC_DIR}/sty/SetProfiles.sty
   │  │  ├─ 6_headers.sty -> ${ABS_SRC_DIR}/sty/SetHeaders.sty
   │  │  └─ title.tex -> ${ABS_SRC_DIR}/templates/title.tex
   │  ├─ bib
   │  │  ├─ '{ROOT1}' -> ${ABS_PARENT_DIR}/${ROOT1}/bib
   │  │  └─ '{ROOT2}' -> ${ABS_PARENT_DIR}/${ROOT2}/bib
   │  ├─ img
   │  │  ├─ '{ROOT1}' -> ${ABS_PARENT_DIR}/${ROOT1}/img
   │  │  ├─ '{ROOT2}' -> ${ABS_PARENT_DIR}/${ROOT2}/img
   │  │  └─ own
   │  ├─ 'T{TN:02d}'
   │  │  ├─ '{ROOT1}-C{ch:02d}S{sec}' -> ${ABS_PROJECT_DIR1}/tex/C${ch:02d}S${sec}/
   │  └─ 'T{TN:02d}'.tex
   └─ config.yaml
```

## Shared files

```bash
/home/luis/.config/mytex
├── img
│   ├── BoldR.png
│   └── ScriptR.png
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

## Misc

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
