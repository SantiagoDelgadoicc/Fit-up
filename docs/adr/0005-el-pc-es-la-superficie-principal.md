# ADR-0005 — El PC es la superficie principal; el móvil, la secundaria

**Estado:** Aceptada (2026-09-07) · **Matiza a:** [ADR-0001](0001-distribucion-web-local-pwa.md)

## Contexto
ADR-0001 decidió *dónde* se ejecuta Fit-Up (servidor local + PWA accesible por LAN), pero
no dijo *dónde se usa más*. Al construir F1 se asumió implícitamente que el móvil era el
escenario principal y el escritorio una adaptación: maquetación mobile-first, ancho de
contenido de 820 px y barra inferior con un lateral añadido a partir de 900 px.

Esa suposición era incorrecta. **El uso principal es el PC.**

## Decisión
El escritorio deja de ser una adaptación del móvil y pasa a tener disposición propia:

- **Ancho por página.** Los formularios siguen estrechos —una línea de 1200 px no se lee
  bien—, pero el calendario y las vistas de datos usan hasta 1240 px.
- **Dos columnas** donde aporta: en el calendario, rejilla a la izquierda y detalle fijo a
  la derecha. Revisar varios días seguidos no debe obligar a abrir y cerrar un panel.
- **Densidad mayor en pantalla ancha.** Cada celda del mes muestra qué rutina tocaba, no
  solo un color: leer el mes de un vistazo es la ventaja del monitor grande.
- **Teclado.** Las flechas cambian de mes. Se añadirán más atajos donde ahorren trabajo.
- **Estados de hover** y navegación lateral con marca.

El móvil sigue siendo un escenario de primera: registrar en el gimnasio es el caso de uso
que justifica ADR-0001, y todo debe seguir funcionando a 375 px con targets de 44 px.

## Alternativas descartadas
- **Mantener mobile-first y adaptar:** más simple de mantener, pero desaprovecha el
  monitor justo donde más se usa la app, y el calendario mensual —la vista que más se
  beneficia del ancho— quedaba comprimida sin motivo.
- **Dos interfaces separadas:** duplicaría el trabajo de cada pantalla para un solo
  usuario. Desproporcionado.

## Consecuencias
- Cada pantalla se piensa en escritorio primero y se comprueba después a 375 px.
- Las fases pendientes heredan esta prioridad: el **mapa corporal** de F4 y el
  **temporizador** de F5 se diseñan para monitor, con su versión móvil verificada.
- Se mantiene una sola base de código y una sola hoja de estilos: la diferencia son
  puntos de ruptura y disposición, no componentes distintos.
- El token de acceso por LAN y la PWA instalable siguen siendo necesarios: que el PC sea
  lo principal no elimina el gimnasio.
