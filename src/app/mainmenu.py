"""
La idea de este scrip es el menú principal con la funcionalidad
de llamar a los diferentes programas.

En el workflow hay tres partes immportantes:
1. ITeP - Init Tex Project
    Este módulo debe proveer un API para crear, actualizar y usar las
    configuraciones del directorio donde se enceuntre el proyecto
2. lectkit
    Es un conjunto de funciones standalone que se llaman directamente desde
    la terminal o que puede ser integradas dendro del CI/CD del proyecto.
3. PRISMAR
    Es una implementación de RPISMA 2020 en SQL que permita administrar
    referencias y relaciones desde una una base de datos estructurada.
"""
