"""Errores de la capa de aplicación.

Existen para que los casos de uso no tengan que conocer HTTP: el adaptador web
traduce cada tipo a su código de estado. Un servicio que lanzara
``HTTPException`` sería inutilizable desde el servidor MCP.
"""

from __future__ import annotations


class ApplicationError(Exception):
    """Base de todos los errores esperables de un caso de uso."""


class NotFound(ApplicationError):
    """El recurso pedido no existe."""


class Conflict(ApplicationError):
    """La operación choca con el estado actual (duplicado, ya registrado…)."""


class Invalid(ApplicationError):
    """La entrada viola una regla de negocio.

    Distinta de un error de validación de esquema: aquí la forma del dato es
    correcta pero el dominio lo rechaza (registrar en el futuro, por ejemplo).
    """


class Denied(ApplicationError):
    """El agente intentó algo para lo que no tiene permiso.

    No es un error de programación ni de datos: es el guardarraíl de ADR-0004
    haciendo su trabajo. Se distingue del resto porque el cliente puede
    resolverlo pidiendo al usuario que active el permiso.
    """


class Undeterminable(ApplicationError):
    """Faltan datos para responder con seguridad.

    No es un fallo: es la respuesta honesta cuando el sistema no puede
    determinar algo. Se propaga en lugar de sustituirse por un valor supuesto.
    """
