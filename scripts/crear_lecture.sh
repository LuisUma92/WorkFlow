#!/usr/bin/env bash
set -euo pipefail

# =============================
# Inicializador de cursos (lect)
# =============================
#
# Uso:
#   init_lect_course.sh [RUTA_PROYECTO | --general] [-h|--help]
#
# Comportamiento:
# - Si se pasa una RUTA_PROYECTO (debe existir), se usa como ${ABS_PROJECT_DIR}.
# - Si se pasa la opción --general, se usa ${ABS_PARENT_DIR}/00AA-Lectures como ${ABS_PROJECT_DIR}
#   y se pedirá un ${LECTURE_CODE} para crear/usar ${ABS_PROJECT_DIR}/${LECTURE_CODE}.
# - Si no se pasa argumento, ${ABS_PROJECT_DIR} = $(pwd).
#
# =============================

ABS_PARENT_DIR="/home/luis/Documents/01-U/00-Fisica"
ABS_SRC_DIR="/home/luis/.config/mytex"

print_help() {
  sed -n '1,120p' "$0" | awk 'NR<=120 && /^#/{sub(/^# ?/,""); print}'
}

# --- Parse args ---
ARG_PROJECT="${1:-}"
if [[ "$ARG_PROJECT" == "-h" || "$ARG_PROJECT" == "--help" ]]; then
  print_help
  exit 0
fi

# === Gather inputs ===
read -rp "Ingrese el código numérico (4 dígitos) para el curso: " NUM
if [[ ! "$NUM" =~ ^[0-9]{4}$ ]]; then
  err "El número debe tener exactamente 4 dígitos (ej. 0121, 0210, 0009)."
  exit 1
fi

read -rp "Ingrese las DOS letras para el código del curso (A-Z): " AA
if [[ ! "$AA" =~ ^[A-Za-z]{2}$ ]]; then
  err "Debe ingresar exactamente 2 letras."
  exit 1
fi
AA_UPPER=$(echo "$AA" | tr '[:lower:]' '[:upper:]')

read -rp "Ingrese el de la universidad (UCR, UFide, UCIMED): " NAME
if [[ -z "$NAME" ]]; then
  err "El nombre no puede estar vacío."
  exit 1
fi

ROOT="${NAME}-${AA_UPPER}${NUM}"

# --- Resolve ABS_PROJECT_DIR ---
ABS_PROJECT_DIR="$(pwd)"
USE_GENERAL=false
if [[ -n "$ARG_PROJECT" ]]; then
  if [[ "$ARG_PROJECT" == "--general" ]]; then
    ABS_PROJECT_DIR="${ABS_PARENT_DIR}/00AA-Lectures"
    USE_GENERAL=true
  else
    if [[ -d "$ARG_PROJECT" ]]; then
      ABS_PROJECT_DIR="$(cd "$ARG_PROJECT" && pwd)"
    else
      echo "Error: La ruta proporcionada no existe: $ARG_PROJECT" >&2
      exit 1
    fi
  fi
fi

if $USE_GENERAL; then
  TARGET_DIR="${ABS_PROJECT_DIR}/${ROOT}"
else
  TARGET_DIR="${ABS_PROJECT_DIR}/lect/${ROOT}"
fi


mkdir -p "${TARGET_DIR}/admin"\
         "${TARGET_DIR}/eval" \
         "${TARGET_DIR}/eval/config" \
         "${TARGET_DIR}/press/notes" \
         "${TARGET_DIR}/press/config"\
         "${TARGET_DIR}/press/bib"\
         "${TARGET_DIR}/press/img"

# --- Enlaces en press/config ---
ln -sfn "${ABS_SRC_DIR}/sty/SetFormatP.sty" "${TARGET_DIR}/press/config/0_packages.sty"
ln -sfn "${ABS_SRC_DIR}/sty/SetLoyaut.sty"   "${TARGET_DIR}/press/config/1_loyaut.sty"
ln -sfn "${ABS_SRC_DIR}/sty/SetCommands.sty" "${TARGET_DIR}/press/config/2_commands.sty"
ln -sfn "${ABS_SRC_DIR}/sty/SetUnits.sty"    "${TARGET_DIR}/press/config/3_units.sty"
cat > "${TARGET_DIR}/press/config/4_biber.sty" <<'EOF'
% \addbibresources{bib/}
EOF
ln -sfn "${ABS_SRC_DIR}/sty/SetProfiles.sty" "${TARGET_DIR}/press/config/5_profiles.sty"
ln -sfn "${ABS_SRC_DIR}/sty/SetHeaders.sty"  "${TARGET_DIR}/press/config/6_headers.sty"
ln -sfn "${ABS_SRC_DIR}/templates/title.tex" "${TARGET_DIR}/press/config/title.tex"
#
# --- Enlaces en eval/config ---
ln -sfn "${ABS_SRC_DIR}/sty/SetFormatP.sty" "${TARGET_DIR}/eval/config/0_packages.sty"
ln -sfn "${ABS_SRC_DIR}/sty/SetLoyaut.sty"   "${TARGET_DIR}/eval/config/1_loyaut.sty"
ln -sfn "${ABS_SRC_DIR}/sty/SetCommands.sty" "${TARGET_DIR}/eval/config/2_commands.sty"
ln -sfn "${ABS_SRC_DIR}/sty/SetUnits.sty"    "${TARGET_DIR}/eval/config/3_units.sty"
cat > "${TARGET_DIR}/eval/config/4_biber.sty" <<'EOF'
% \addbibresources{bib/}
EOF
ln -sfn "${ABS_SRC_DIR}/sty/SetProfiles.sty" "${TARGET_DIR}/eval/config/5_profiles.sty"
ln -sfn "${ABS_SRC_DIR}/sty/SetHeaders.sty"  "${TARGET_DIR}/eval/config/6_headers.sty"
ln -sfn "${ABS_SRC_DIR}/templates/title.tex" "${TARGET_DIR}/eval/config/title.tex"

# --- Crear T##.tex ---
read -rp "¿Cuántos T##.tex desea crear en press/? (entero >=0, 0=ninguno): " N_T
if ! [[ "$N_T" =~ ^[0-9]+$ ]]; then
  echo "Error: Debe ingresar un entero." >&2
  exit 1
fi

SRC_TNN="${ABS_SRC_DIR}/templates/TNN.tex"
TOPICS=()
for ((i=1; i<=N_T; i++)); do
  printf -v TNUM "%02d" "$i"
  ead -rp "Ingrese el nombre del tema ${TNUM}: " NAME
  if [[ -z "$NAME" ]]; then
    err "El nombre no puede estar vacío."
    exit 1
  fi
  DEST="${TARGET_DIR}/press/T${TNUM}-${NAME}.tex"

  if [[ -f "$SRC_TNN" ]]; then
    cp -f "$SRC_TNN" "$DEST"
  else
    : > "$DEST"
  fi
  mkdir -p "${TARGET_DIR}/eval/${TNUM}-${NAME}"
  TOPICS+=("T${TNUM}-${NAME}")
  echo "Creado: press/T${TNUM}.tex"
done

# --- Funciones para preguntas ---
ask_yn_default() {
  local prompt="$1" default="$2" ans
  read -rp "$prompt " ans || true
  ans="${ans:-$default}"
  ans="$(echo "$ans" | tr '[:upper:]' '[:lower:]')"
  [[ "$ans" == "y" || "$ans" == "yes" || "$ans" == "s" ]]
}

BIB_ROOTS=()
IMG_ROOTS=()

# --- Enlaces a temas generales (bib/img) ---
if ask_yn_default "¿Desea agregar enlaces a temas generales? [Y/n]" "y"; then
  if ask_yn_default "¿Desea considerar el directorio actual como un tema general? [y/N]" "n"; then
    ROOT_SELF="$(basename "$ABS_PROJECT_DIR")"
    ln -sfn "${ABS_PARENT_DIR}/${ROOT_SELF}/bib" "${TARGET_DIR}/press/bib/${ROOT_SELF}"
    ln -sfn "${ABS_PARENT_DIR}/${ROOT_SELF}/img" "${TARGET_DIR}/press/img/${ROOT_SELF}"
    ln -sfn "${ABS_PARENT_DIR}/${ROOT_SELF}/tex/notes" "${TARGET_DIR}/notes/${ROOT_SELF}"
    BIB_ROOTS+=("$ROOT_SELF")
    IMG_ROOTS+=("$ROOT_SELF")
    echo "Enlazado tema general (actual): ${ROOT_SELF}"
  fi

  while :; do
    echo "-------------- Temas disponibles en ${ABS_PARENT_DIR} --------------"
    mapfile -t DIRS < <(find "$ABS_PARENT_DIR" -mindepth 1 -maxdepth 1 -type d -printf "%f\n" | sort)
    for i in "${!DIRS[@]}"; do
      printf "%3d) %s\n" "$((i+1))" "${DIRS[$i]}"
    done
    read -rp "Número del ROOT a agregar (o 'a' para abortar): " choice || true
    if [[ "$choice" == "a" || "$choice" == "A" ]]; then
      break
    fi
    if [[ "$choice" =~ ^[0-9]+$ ]]; then
      idx=$((choice-1))
      if (( idx >=0 && idx < ${#DIRS[@]} )); then
        ROOT_CHOSEN="${DIRS[$idx]}"
        ln -sfn "${ABS_PARENT_DIR}/${ROOT_CHOSEN}/bib" "${TARGET_DIR}/press/bib/${ROOT_CHOSEN}"
        ln -sfn "${ABS_PARENT_DIR}/${ROOT_CHOSEN}/img" "${TARGET_DIR}/press/img/${ROOT_CHOSEN}"
        ln -sfn "${ABS_PARENT_DIR}/${ROOT_CHOSEN}/tex/notes" "${TARGET_DIR}/press/notes/${ROOT_CHOSEN}"
        BIB_ROOTS+=("$ROOT_CHOSEN")
        IMG_ROOTS+=("$ROOT_CHOSEN")
        echo "Enlazado tema general: ${ROOT_CHOSEN}"
      fi
    fi
    if ! ask_yn_default "¿Desea seleccionar otro tema general? [Y/n]" "y"; then
      break
    fi
  done
fi

# -- Enlace a libros de texto
# if ask_yn_default "¿Desea agregar el libro de texto? [Y/n]" "y"; then
#     echo "-------------- Temas disponibles en ${ABS_PARENT_DIR}/00BB-Library --------------"
#     mapfile -t DIRS < <(find "$ABS_PARENT_DIR/" -mindepth 1 -maxdepth 1 -type d -printf "%f\n" | sort)
#     for i in "${!DIRS[@]}"; do
#       printf "%3d) %s\n" "$((i+1))" "${DIRS[$i]}"
#     done
#     read -rp "Número del ROOT a agregar (o 'a' para abortar): " choice || true
#     if [[ "$choice" == "a" || "$choice" == "A" ]]; then
#       break
#     fi
#
#   while :; do
#     if ! ask_yn_default "¿Desea agregar un libro más? [Y/n]" "n"; then
#       break
#     fi
#   done
# fi

# --- Crear config.yaml ---
CONFIG_YAML="${TARGET_DIR}/config.yaml"
LECTURE_CODE_BN="$(basename "$TARGET_DIR")"
DATE_NOW="$(date -Iseconds)"

{
  echo "lecture_code: \"${LECTURE_CODE_BN}\""
  echo "abs_project_dir: \"${TARGET_DIR}\""
  echo "abs_parent_dir: \"${ABS_PARENT_DIR}\""
  echo "abs_src_dir: \"${ABS_SRC_DIR}\""
  echo "created_at: \"${DATE_NOW}\""
  echo "version: \"1.0\""
  echo "template_source: \"${SRC_TNN}\""
  echo "press:"
  echo "  config_files:"
  echo "    - 0_packages.sty"
  echo "    - 1_loyaut.sty"
  echo "    - 2_commands.sty"
  echo "    - 3_units.sty"
  echo "    - 4_biber.sty"
  echo "    - 5_profiles.sty"
  echo "    - 6_headers.sty"
  echo "    - title.tex"
  echo "bib_roots:"
  for r in "${BIB_ROOTS[@]}"; do echo "  - ${r}"; done
  echo "img_roots:"
  for r in "${IMG_ROOTS[@]}"; do echo "  - ${r}"; done
  echo "topics:"
  for t in "${TOPICS[@]}"; do echo "  - ${t}"; done
} > "${CONFIG_YAML}"

echo "Creado: ${CONFIG_YAML}"
echo "Estructura creada en: ${TARGET_DIR}"
echo "Listo."

