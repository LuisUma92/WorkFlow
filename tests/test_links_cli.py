import re
import types

import pytest

try:
    # Importa el entry point exacto que indicaste
    from itep.links import cli
except Exception as e:
    pytest.fail(f"No se pudo importar itep.links:cli ({e})")


def test_cli_is_click_command():
    """
    Verifica que 'cli' sea un comando de Click (BaseCommand o subclase).
    Evita atarse a si es Group o Command.
    """
    try:
        import click
    except Exception as e:  # pragma: no cover
        pytest.skip(f"Click no está instalado en el entorno de test: {e}")

    assert (
        hasattr(cli, "main")
        or hasattr(cli, "callback")
        or isinstance(cli, click.core.BaseCommand)
    ), "El objeto 'cli' no parece ser un comando Click válido"


def test_cli_help_runs_and_shows_usage(capsys):
    """
    Ejecuta 'cli --help' y exige exit_code == 0.
    No depende de opciones de negocio ni del filesystem.
    """
    import click
    from click.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])

    # Debe terminar correctamente
    assert result.exit_code == 0, (
        f"cli --help devolvió exit_code {result.exit_code}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    # Debe mostrar algún encabezado típico de Click
    out = result.stdout or ""
    assert "Usage" in out or "Uso" in out or "Options" in out, (
        "La salida de ayuda no contiene encabezados esperables de Click.\n"
        f"stdout:\n{out}"
    )


def test_cli_version_if_available():
    """
    Si el comando soporta --version (o -V), lo probamos.
    Detectamos la bandera leyendo el help para evitar falsos negativos.
    """
    from click.testing import CliRunner

    runner = CliRunner()
    help_out = runner.invoke(cli, ["--help"]).stdout or ""

    # Detecta banderas de versión comunes en Click
    has_version = any(flag in help_out for flag in ["--version", "-V"])

    if not has_version:
        pytest.skip("El CLI no declara --version/-V en la ayuda; se omite esta prueba.")

    # Prueba la(s) bandera(s) declaradas
    # Orden: primero --version si existe, si no -V
    for flag in ("--version", "-V"):
        if flag in help_out:
            res = runner.invoke(cli, [flag])
            assert res.exit_code == 0, f"{flag} devolvió exit_code {res.exit_code}"
            # La mayoría de Click imprime algo tipo 'prog, version x.y'
            # No exigimos un formato estricto; solo que haya algo con dígitos.
            assert re.search(r"\d+\.\d+", res.stdout or ""), f"La salida de {
                flag
            } no parece contener un número de versión:\n{res.stdout}"
            break


def test_cli_invocation_without_args_shows_usage_or_succeeds():
    """
    Invocar sin argumentos puede:
      - devolver 0 (si hay defaults), o
      - devolver 2 e imprimir 'Usage:' (Click cuando faltan args requeridos).

    Aceptamos ambas rutas para que el test sea estable sin conocer tus opciones.
    """
    from click.testing import CliRunner

    runner = CliRunner()
    res = runner.invoke(cli, [])
    if res.exit_code == 0:
        # Perfecto: el comando tiene comportamiento por defecto
        assert True
    else:
        # Para Click, falta de argumentos requeridos suele ser exit_code == 2
        assert res.exit_code in (1, 2), f"exit_code inesperado: {res.exit_code}"
        assert "Usage:" in (res.stdout or "") or "Uso:" in (res.stdout or ""), (
            "Al fallar sin args, se esperaba que la salida incluyera 'Usage:' de Click.\n"
            f"stdout:\n{res.stdout}\n"
            f"stderr:\n{res.stderr}"
        )
