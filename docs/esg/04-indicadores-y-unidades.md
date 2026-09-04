# ESG · 4. Indicadores, unidades y calidad del dato

## 4.1. Unidades

| Vector | Se agrega en | Se acepta |
|---|---|---|
| Agua | m³ | m³, litros |
| Electricidad | kWh | kWh, MWh, GWh, GJ |
| Gas | kWh | kWh, MWh, GJ, termias, **m³ con su poder calorífico** |
| Residuos | kg | kg, toneladas |

Los factores fijos son definiciones (1 MWh = 1.000 kWh) y viven en el código.
También están en la tabla `factor_de_conversion`, generados desde el código por
la siembra: **quien audita el informe pregunta con qué factor se convirtió**, y
esa respuesta tiene que poder consultarse sin leer código. Hay una prueba que
falla si la tabla y el código divergen.

**El gas en m³ es el caso que justifica media arquitectura.** El paso a kWh
depende del poder calorífico superior corregido, que en España va de 10,7 a 12,0
kWh/m³ según red, presión y periodo. Usar 11,63 para todo mete un 5 % de error
en el vector que más pesa en un edificio con calderas. Así que:

- si la factura trae su PCS, se aplica **y se guarda en la lectura**;
- si no lo trae, `cantidad_normalizada` queda `NULL`, la lectura **no entra en
  ninguna suma** y aparece en la cobertura como dato sin normalizar.

Un 0 habría sumado bien y mentido.

## 4.2. Del intervalo al mes

Una factura va del 14 de marzo al 16 de abril; el dashboard habla de meses. El
reparto es **proporcional a los días** y se hace **al consultar**, no al
guardar: el dato guardado sigue siendo el de la factura y el criterio se puede
cambiar sin recargar nada.

`[REQ]` La suma de lo repartido es **exactamente** la cantidad original: el
último mes se lleva el resto del redondeo. Con doce facturas al año y cuatro
decimales, redondear cada trozo por separado hacía que el total anual no
cuadrara con la suma de las facturas, y esa diferencia de céntimos es la que
hace que nadie se fíe del resto de la pantalla.

Una lectura que asoma por el borde de la ventana consultada solo cuenta por la
parte de dentro: el total de enero no puede depender de qué día facturó cada
comercializadora.

## 4.3. Intensidades

| Indicador | Denominador | Cuándo **no** se muestra |
|---|---|---|
| Consumo por m² | Superficie de referencia del activo, heredada de su cartera si no la fija | Sin superficie |
| Consumo por ocupante | Media de `ocupacion` en la ventana | Sin ocupación declarada |

En los dos casos, la ausencia se enseña como ausencia y **nunca como 0**: un
cero se leería como «este edificio no consume» y saldría el primero en el
ranking de eficiencia.

El indicador **siempre declara qué superficie ha usado**. Comparar un kWh/m²
calculado sobre superficie bruta con otro sobre alquilable no es una comparación
con ruido: es un error con dos decimales.

## 4.4. Cobertura, o por qué el número no viaja solo

```
cobertura = días con lectura / días en que el suministro estaba de alta
```

Un mes sin lectura es un mes sin lectura: no se estima nada por omisión. El
consumo del periodo viaja **siempre** con su cobertura, en la misma tarjeta, no
en una pestaña de «calidad del dato» que nadie abre. Un consumo con el 40 % de
cobertura no es un consumo bajo: es un consumo que falta.

Dos detalles que se pagan si no están:

- Un contador dado de alta en septiembre **no deja un agujero de ocho meses**:
  no existía. Sin eso, la cobertura de una cartera se hunde cada vez que entra
  un activo, y entonces nadie mira la cobertura.
- Lo `ESTIMADO` no se mezcla con lo `MEDIDO` ni en el total ni en la serie. Se
  enseña aparte. Un escalón en el gráfico que es criterio de carga y no consumo
  es peor que no tener el dato.

## 4.5. Comparativa

La variación se calcula contra la ventana anterior **de la misma longitud**. Sin
periodo anterior con el que comparar, la variación es `—` y no «0 %»: un 0 %
sería una afirmación falsa sobre una mejora que nadie ha medido.
