// Consultas del TP (5.3). Cada una tiene: objetivo, tipo de consulta que cubre, comando y
// resultado esperado. Los resultados esperados se verificaron corriendo el script sobre la
// base recién cargada (python scripts/cargar.py); la salida completa está en consultas_salida.txt.
//
//   docker compose exec mongo mongosh ecommerce --quiet --file /scripts/consultas.js

// Imprime cada documento en una línea para que la salida sea fácil de leer y de comparar.
function mostrar(numero, titulo, docs) {
  print(`\n=== ${numero}. ${titulo} (${docs.length} resultado${docs.length === 1 ? "" : "s"})`);
  docs.forEach((d) => print("  " + JSON.stringify(d)));
}

// ------------------------------------------------------------------------------------------
// 1. Comparación: productos por agotarse
// Objetivo: lista de reposición. Productos que todavía tienen stock pero menos de 10 unidades,
//   empezando por los más críticos. Los que tienen stock 0 no entran: esos ya no se venden.
// Operadores: $gt y $lt sobre el mismo campo (rango abierto).
// Resultado esperado: 21 productos, el primero con stock 1.
mostrar(1, "Productos por agotarse (0 < stock < 10)",
  db.productos.find(
    { stock: { $gt: 0, $lt: 10 } },
    { _id: 0, sku: 1, titulo: 1, categoria: 1, stock: 1 }
  ).sort({ stock: 1, sku: 1 }).toArray()
);

// ------------------------------------------------------------------------------------------
// 2. Comparación: tecnología económica
// Objetivo: armar una vidriera de "tecnología por menos de $500". Productos de las categorías
//   de tecnología con precio de hasta $500, del más barato al más caro.
// Operadores: $in (pertenencia a una lista) y $lte. Es un tipo de comparación distinto a la 1:
//   $in compara contra varios valores posibles del mismo campo.
// Resultado esperado: 15 productos (13 smartphones y 2 tablets; ninguna laptop cuesta menos de
//   $1000), desde el Realme C35 ($149.99) hasta el iPad Mini ($499.99).
mostrar(2, "Tecnología de hasta $500",
  db.productos.find(
    { categoria: { $in: ["smartphones", "tablets", "laptops"] }, precio: { $lte: 500 } },
    { _id: 0, titulo: 1, categoria: 1, precio: 1 }
  ).sort({ precio: 1, titulo: 1 }).toArray()
);

// ------------------------------------------------------------------------------------------
// 3. Operadores lógicos: candidatos para destacar en la portada
// Objetivo: productos con stock que, además, tengan un descuento fuerte (≥ 15 %) o una
//   valoración muy buena (≥ 4.5). Son los que conviene mostrar primero.
// Operadores: $and que combina una condición obligatoria con un $or de dos alternativas.
//   (El $and podría ser implícito; se escribe explícito para que se vea la estructura.)
// Resultado esperado: 64 productos cumplen; se muestran los 10 con más descuento (todos cerca del 19,5 %).
mostrar(3, "Con stock y (descuento >= 15% o rating >= 4.5), top 10 por descuento",
  db.productos.find(
    {
      $and: [
        { stock: { $gt: 0 } },
        { $or: [{ descuento_pct: { $gte: 15 } }, { rating_promedio: { $gte: 4.5 } }] },
      ],
    },
    { _id: 0, titulo: 1, descuento_pct: 1, rating_promedio: 1, stock: 1 }
  ).sort({ descuento_pct: -1 }).limit(10).toArray()
);
print("  total que cumplen:", db.productos.countDocuments({
  $and: [{ stock: { $gt: 0 } }, { $or: [{ descuento_pct: { $gte: 15 } }, { rating_promedio: { $gte: 4.5 } }] }],
}));

// ------------------------------------------------------------------------------------------
// 4. Atributos anidados: equipos para trabajo pesado
// Objetivo: un cliente busca un equipo con al menos 8 GB de RAM y 256 GB de almacenamiento.
// Por qué es interesante: ram_gb y almacenamiento_gb viven dentro de "atributos", un
//   subdocumento que solo existe en smartphones, tablets y laptops. La notación de punto
//   ("atributos.ram_gb") entra al documento anidado, y los productos sin esos campos
//   (ropa, almacén...) simplemente no coinciden: no hace falta filtrar la categoría.
// Resultado esperado: 8 productos (3 smartphones y 5 laptops), desde el Realme C35 ($149.99).
mostrar(4, "Equipos con RAM >= 8 GB y almacenamiento >= 256 GB",
  db.productos.find(
    { "atributos.ram_gb": { $gte: 8 }, "atributos.almacenamiento_gb": { $gte: 256 } },
    { _id: 0, titulo: 1, categoria: 1, precio: 1, "atributos.ram_gb": 1, "atributos.almacenamiento_gb": 1 }
  ).sort({ precio: 1 }).toArray()
);

// ------------------------------------------------------------------------------------------
// 5. Arreglos: productos con quejas
// Objetivo: para el área de calidad, productos que recibieron al menos una reseña negativa
//   (rating ≤ 2), con cuántas reseñas negativas tienen.
// Operadores: $elemMatch sobre el arreglo embebido de reviews: busca que UN MISMO elemento
//   cumpla la condición. $filter + $size (en la proyección) cuentan cuántos elementos la cumplen.
// Resultado esperado: 101 productos con al menos una reseña negativa; el peor es Cricket Ball
//   (sus 3 reseñas son negativas, rating 1.33).
mostrar(5, "Productos con reseñas negativas (rating <= 2), top 5",
  db.productos.find(
    { reviews: { $elemMatch: { rating: { $lte: 2 } } } },
    {
      _id: 0, titulo: 1, rating_promedio: 1,
      negativas: { $size: { $filter: { input: "$reviews", cond: { $lte: ["$$this.rating", 2] } } } },
    }
  ).sort({ negativas: -1, rating_promedio: 1 }).limit(5).toArray()
);
print("  total con al menos una negativa:", db.productos.countDocuments({ reviews: { $elemMatch: { rating: { $lte: 2 } } } }));

// ------------------------------------------------------------------------------------------
// 6. Proyección, ordenamiento y límite: los 5 pedidos más grandes
// Objetivo: identificar los pedidos de mayor importe (sin contar cancelados) para el área
//   comercial, mostrando solo lo necesario: número, cliente, fecha, total y unidades.
// Operadores: proyección que incluye un campo anidado (cliente.nombre, totales.total),
//   sort descendente y limit.
// Resultado esperado: 5 pedidos de más de $125.000 cada uno (todos incluyen vehículos);
//   el mayor es el 1028, de $155.507,16.
mostrar(6, "Los 5 pedidos de mayor importe (no cancelados)",
  db.pedidos.find(
    { estado: { $ne: "cancelado" } },
    { _id: 0, numero: 1, "cliente.nombre": 1, fecha: 1, "totales.total": 1, cantidad_unidades: 1 }
  ).sort({ "totales.total": -1 }).limit(5).toArray()
);

// ------------------------------------------------------------------------------------------
// 7. Aggregate: ventas por mes
// Objetivo: evolución mensual de la facturación (pedidos no cancelados).
// Etapas: $match (descarta cancelados) → $group por año-mes con $dateToString
//   → $sort cronológico → $project para redondear y renombrar.
// Resultado esperado: 12 meses (nov-2025 a oct-2026). Los picos (ene y jul-2026, unos
//   $490.000-$500.000) se explican por vehículos y motos (85 % y 72 % de lo facturado esos
//   meses), no por más pedidos: oct-2026 tiene 20 pedidos y factura solo $101.742.
mostrar(7, "Ventas por mes",
  db.pedidos.aggregate([
    { $match: { estado: { $ne: "cancelado" } } },
    {
      $group: {
        _id: { $dateToString: { format: "%Y-%m", date: "$fecha" } },
        pedidos: { $sum: 1 },
        importe: { $sum: "$totales.total" },
      },
    },
    { $sort: { _id: 1 } },
    { $project: { _id: 0, mes: "$_id", pedidos: 1, importe: { $round: ["$importe", 2] } } },
  ]).toArray()
);

// ------------------------------------------------------------------------------------------
// 8. Aggregate: productos más vendidos
// Objetivo: los 5 productos con más unidades vendidas y cuánto facturaron.
// Etapas: $match → $unwind (un documento por ítem del pedido) → $group por producto
//   → $sort → $limit. Se agrupa por producto_id y se toma el título copiado en el ítem,
//   así no hace falta ir a la colección productos.
// Resultado esperado: 5 productos con 25 a 29 unidades. Empatan Samsung Galaxy S10 y Cat Food
//   (29 unidades) pero con importes muy distintos: más unidades no implica más facturación.
mostrar(8, "Top 5 productos por unidades vendidas",
  db.pedidos.aggregate([
    { $match: { estado: { $ne: "cancelado" } } },
    { $unwind: "$items" },
    {
      $group: {
        _id: "$items.producto_id",
        titulo: { $first: "$items.titulo" },
        unidades: { $sum: "$items.cantidad" },
        importe: { $sum: "$items.subtotal" },
        pedidos: { $sum: 1 },
      },
    },
    { $sort: { unidades: -1, importe: -1 } },
    { $limit: 5 },
    { $project: { _id: 0, titulo: 1, unidades: 1, pedidos: 1, importe: { $round: ["$importe", 2] } } },
  ]).toArray()
);

// ------------------------------------------------------------------------------------------
// 9. Agrupamiento con cálculos estadísticos: precios por categoría
// Objetivo: entender el posicionamiento de precios de cada categoría: cantidad de productos,
//   promedio, mínimo, máximo y desvío estándar (qué tan dispersos están los precios).
// Acumuladores: $sum, $avg, $min, $max, $stdDevPop.
// Resultado esperado: 24 categorías; vehicle y motorcycle con los promedios más altos y
//   groceries con el más bajo.
mostrar(9, "Estadísticas de precio por categoría",
  db.productos.aggregate([
    {
      $group: {
        _id: "$categoria",
        productos: { $sum: 1 },
        promedio: { $avg: "$precio" },
        minimo: { $min: "$precio" },
        maximo: { $max: "$precio" },
        desvio: { $stdDevPop: "$precio" },
      },
    },
    { $sort: { promedio: -1 } },
    {
      $project: {
        _id: 0, categoria: "$_id", productos: 1, minimo: 1, maximo: 1,
        promedio: { $round: ["$promedio", 2] }, desvio: { $round: ["$desvio", 2] },
      },
    },
  ]).toArray()
);

// ------------------------------------------------------------------------------------------
// 10. Libre: facturación por categoría con $lookup
// Objetivo: qué categorías generan más ingresos. El pedido no guarda la categoría del
//   producto (no se copió porque no hace falta para mostrar el pedido), así que se cruza
//   con productos.
// Etapas: $unwind de ítems → $lookup a productos por producto_id (como un JOIN) → $unwind
//   del resultado → $group por categoría → $sort. También calcula la participación de cada
//   categoría sobre el total con $setWindowFields.
// Resultado esperado: 24 categorías. vehicle sola es el 52,6 % de la facturación, y con
//   relojes y motos las 4 primeras superan el 90 %; groceries vende 318 unidades pero
//   factura apenas el 0,1 %.
mostrar(10, "Facturación por categoría (cruce pedidos → productos)",
  db.pedidos.aggregate([
    { $match: { estado: { $ne: "cancelado" } } },
    { $unwind: "$items" },
    {
      $lookup: {
        from: "productos",
        localField: "items.producto_id",
        foreignField: "_id",
        as: "producto",
        pipeline: [{ $project: { _id: 0, categoria: 1 } }], // solo trae lo que se usa
      },
    },
    { $unwind: "$producto" },
    {
      $group: {
        _id: "$producto.categoria",
        importe: { $sum: "$items.subtotal" },
        unidades: { $sum: "$items.cantidad" },
      },
    },
    { $setWindowFields: { output: { total_general: { $sum: "$importe" } } } },
    { $sort: { importe: -1 } },
    {
      $project: {
        _id: 0, categoria: "$_id", unidades: 1,
        importe: { $round: ["$importe", 2] },
        participacion_pct: { $round: [{ $multiply: [{ $divide: ["$importe", "$total_general"] }, 100] }, 1] },
      },
    },
  ]).toArray()
);
