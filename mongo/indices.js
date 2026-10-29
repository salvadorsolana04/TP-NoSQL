// Índices del TP (sección 8 del diseño). Se crean desde scripts/cargar.py después de cargar
// los datos; también se pueden correr a mano:
//   docker compose exec mongo mongosh ecommerce --quiet --file /scripts/indices.js
//
// createIndex no falla si el índice ya existe con la misma definición, así que el script
// se puede repetir. El análisis de su uso está en mongo/explain.md.

// ---------------------------------------------------------------- productos

// Único: el sku es el código de negocio del producto. No es por velocidad (con 194
// documentos se nota poco), sino para que Mongo rechace dos productos con el mismo sku,
// porque no hay otra restricción que lo impida.
db.productos.createIndex({ sku: 1 }, { unique: true, name: "sku_unico" });

// RF2: listar por categoría con rango y orden de precio. Regla ESR (Equality, Sort, Range):
// primero el campo que se compara por igualdad (categoria) y después el de rango/orden
// (precio). Así las claves de una categoría quedan juntas y ya ordenadas por precio:
// el índice recorre solo ese tramo y no hace falta ordenar en memoria.
db.productos.createIndex({ categoria: 1, precio: 1 }, { name: "categoria_precio" });

// ---------------------------------------------------------------- clientes

// Único: dos clientes no pueden compartir email (es como se identifican al comprar).
// También sirve para buscar un cliente por email sin recorrer la colección.
db.clientes.createIndex({ email: 1 }, { unique: true, name: "email_unico" });

// ---------------------------------------------------------------- pedidos

// RF5: pedidos de un cliente, del más reciente al más viejo. Igualdad en cliente_id y
// orden por fecha descendente. Se declara fecha: -1 por claridad, aunque un índice simple
// en una dirección también se puede recorrer al revés.
db.pedidos.createIndex({ cliente_id: 1, fecha: -1 }, { name: "cliente_fecha" });

// RF7: reportes por estado en un período (por ejemplo, cancelados en 2026).
// Igualdad en estado, rango en fecha: misma regla ESR que categoria_precio.
db.pedidos.createIndex({ estado: 1, fecha: 1 }, { name: "estado_fecha" });

print("índices creados:");
["productos", "clientes", "pedidos"].forEach((c) =>
  print(`  ${c}: ${db[c].getIndexes().map((i) => i.name).join(", ")}`)
);
