#!/usr/bin/env bash
set -euo pipefail

# === Helper functions ===
pad2() {
  printf "%02d" "$1"
}

err() { printf "Error: %s\n" "$*" >&2; }

# === Gather inputs ===
read -rp "Ingrese el número (2 dígitos) para el código del tema: " NUM
if [[ ! "$NUM" =~ ^[0-9]{2}$ ]]; then
  err "El número debe tener exactamente 2 dígitos (ej. 01, 12, 99)."
  exit 1
fi

read -rp "Ingrese las DOS letras para el código del tema (A-Z): " AA
if [[ ! "$AA" =~ ^[A-Za-z]{2}$ ]]; then
  err "Debe ingresar exactamente 2 letras."
  exit 1
fi
AA_UPPER=$(echo "$AA" | tr '[:lower:]' '[:upper:]')

read -rp "Ingrese el 'Name' (nombre del directorio principal): " NAME
if [[ -z "$NAME" ]]; then
  err "El nombre no puede estar vacío."
  exit 1
fi

# === Derived vars ===
TAG="${NUM}${AA_UPPER}"             # {##AA}
ROOT="${TAG}-${NAME}"               # {##AA-Name}
ABS_PROJECT_DIR="$(pwd)/${ROOT}"
ABS_SRC_DIR="/home/luis/.config/mytex"
echo ">> Crear proyecto: ${ROOT}"
mkdir -p "${ABS_PROJECT_DIR}"

# === Create base directories ===
mkdir -p "${ABS_PROJECT_DIR}/lect"
mkdir -p "${ABS_PROJECT_DIR}/tex"
mkdir -p "${ABS_PROJECT_DIR}/tex/00-resumes"
mkdir -p "${ABS_PROJECT_DIR}/tex/01-glossaries"
mkdir -p "${ABS_PROJECT_DIR}/tex/02-notes"
mkdir -p "${ABS_PROJECT_DIR}/bib"
mkdir -p "${ABS_PROJECT_DIR}/img"
mkdir -p "${ABS_PROJECT_DIR}/config"
mkdir -p "${ABS_PROJECT_DIR}/pro"

# === Files & copies ===
# 1) Crear {##AA}.tex a partir de ${ABS_SRC_DIR}/templates/00AA.tex
SRC_00AA="${ABS_SRC_DIR}/templates/00AA.tex"
DEST_MAIN_TEX="${ABS_PROJECT_DIR}/${TAG}.tex"
if [[ -f "${SRC_00AA}" ]]; then
  cp -f "${SRC_00AA}" "${DEST_MAIN_TEX}"
  echo ">> Copiado: ${SRC_00AA} -> ${DEST_MAIN_TEX}"
else
  err "No se encuentra plantilla ${SRC_00AA}"
fi

SRC_00Gl="${ABS_SRC_DIR}/templates/00-Glossary.tex"
SRC_01Gl="${ABS_SRC_DIR}/templates/01-Acronyms.tex"
DEST_GL="${ABS_PROJECT_DIR}/tex/01-glossaries"
if [[ -f "${SRC_00Gl}" ]]; then
  cp -f "${SRC_00Gl}" "${DEST_GL}"
  echo ">> Copiado: ${SRC_00Gl} -> ${DEST_GL}"
else
  err "No se encuentra plantilla ${SRC_00GL}"
fi
if [[ -f "${SRC_01Gl}" ]]; then
  cp -f "${SRC_01Gl}" "${DEST_GL}"
  echo ">> Copiado: ${SRC_01Gl} -> ${DEST_GL}"
else
  err "No se encuentra plantilla ${SRC_01GL}"
fi

BIBER_FILE="${ABS_PROJECT_DIR}/config/4_biber.sty"
cat > "${BIBER_FILE}" <<'EOF'
% \addbibresource{bib/}
EOF
echo ">> Creado: ${BIBER_FILE}"
#
# ----- config/ (en raíz del proyecto) -----
ln -sfn "${ABS_SRC_DIR}/sty/SetFormat.sty"   "${ABS_PROJECT_DIR}/config/0_packages.sty"
ln -sfn "${ABS_SRC_DIR}/sty/SetLoyaut.sty"   "${ABS_PROJECT_DIR}/config/1_loyaut.sty"
ln -sfn "${ABS_SRC_DIR}/sty/SetCommands.sty" "${ABS_PROJECT_DIR}/config/2_commands.sty"
ln -sfn "${ABS_SRC_DIR}/sty/SetUnits.sty"    "${ABS_PROJECT_DIR}/config/3_units.sty"
ln -sfn "${ABS_SRC_DIR}/sty/SetProfiles.sty" "${ABS_PROJECT_DIR}/config/5_profiles.sty"
ln -sfn "${ABS_SRC_DIR}/sty/SetHeaders.sty" "${ABS_PROJECT_DIR}/config/6_headers.sty"
ln -sfn "${ABS_SRC_DIR}/templates/title.tex" "${ABS_PROJECT_DIR}/config/title.tex"


# === README.md ===
README="${ABS_PROJECT_DIR}/README.md"

cat > "${README}" <<EOF
# ${NAME}

## Tabla de Contenidos
- [Tabla de Contenidos](#tabla-de-contenidos)
- [Distribución de temas en el curso](#distribución-de-temas-en-el-curso)
- [Bibliografía](#bibliografía)
- [Pendientes](#pendientes)

## Distribución de temas en el curso

## Bibliografía
*(Agregar referencias en formato APA/Vancouver y DOIs)*

## Pendientes
- [ ] Agregar libros y códigos a "README.md"
- [ ] Crear carpetas con el link adecuado por cada libro tanto en "img/" como en "eval/TNN/"
- [ ] Crear carpetas de las secciones correspondientes al curso
EOF

echo ">> Creado: ${README}"

echo ">> Estructura base creada en: ${ABS_PROJECT_DIR}"
echo ">> Listo."
