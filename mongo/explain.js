// Mide el uso de los índices con explain("executionStats"). Los números de mongo/explain.md
// salen de acá. Requiere la base cargada (python scripts/cargar.py):
//   docker compose exec mongo mongosh ecommerce --quiet --file /scripts/explain.js
//
// Cada consulta se ejecuta dos veces: dejando que Mongo elija el plan (usa el índice) y
// forzando hint({$natural: 1}), que obliga a recorrer la colección entera (COLLSCAN).
// Así se compara la misma consulta con y sin índice sin tener que borrarlo.

// Recorre el árbol del plan ganador y devuelve las etapas de arriba hacia abajo.
function etapas(plan) {
  const nodo = plan.queryPlan || plan; // con el motor SBE el árbol viene dentro de queryPlan
  const hijos = nodo.inputStages || (nodo.inputStage ? [nodo.inputStage] : []);
  const nombre = nodo.indexName ? `${nodo.stage}(${nodo.indexName})` : nodo.stage;
  return [nombre, ...hijos.flatMap(etapas)];
}

function medir(titulo, cursor) {
  const exp = cursor.explain("executionStats");
  const s = exp.executionStats;
  print(
    `  ${titulo.padEnd(24)} plan: ${etapas(exp.queryPlanner.winningPlan).join(" <- ").padEnd(42)}` +
      ` devueltos: ${String(s.nReturned).padStart(3)}` +
      `  claves: ${String(s.totalKeysExamined).padStart(3)}` +
      `  docs: ${String(s.totalDocsExamined).padStart(3)}`
  );
}

// ---------------------------------------------------------------- 1. RF2: productos por categoría y precio
print("\n1) Smartphones entre $200 y $1000, ordenados por precio (índice categoria_precio)");
const filtroProd = { categoria: "smartphones", precio: { $gte: 200, $lte: 1000 } };
medir("con índice", db.productos.find(filtroProd).sort({ precio: 1 }));
medir("sin índice", db.productos.find(filtroProd).sort({ precio: 1 }).hint({ $natural: 1 }));

// Mismo par de campos en el orden contrario, para mostrar por qué importa la regla ESR.
// Se crea solo para medir y se borra enseguida.
db.productos.createIndex({ precio: 1, categoria: 1 }, { name: "tmp_precio_categoria" });
medir("orden inverso (no ESR)", db.productos.find(filtroProd).sort({ precio: 1 }).hint("tmp_precio_categoria"));
db.productos.dropIndex("tmp_precio_categoria");

// ---------------------------------------------------------------- 2. RF5: pedidos de un cliente
// El cliente con más pedidos, para que el resultado tenga más de una fila que ordenar.
const top = db.pedidos.aggregate([
  { $group: { _id: "$cliente_id", n: { $sum: 1 } } },
  { $sort: { n: -1, _id: 1 } },
  { $limit: 1 },
]).next();
print(`\n2) Pedidos del cliente ${top._id} (tiene ${top.n}), del más reciente al más viejo (índice cliente_fecha)`);
medir("con índice", db.pedidos.find({ cliente_id: top._id }).sort({ fecha: -1 }));
medir("sin índice", db.pedidos.find({ cliente_id: top._id }).sort({ fecha: -1 }).hint({ $natural: 1 }));

// ---------------------------------------------------------------- 3. RF7: pedidos por estado y período
const desde2026 = { $gte: ISODate("2026-01-01T00:00:00Z") };
print("\n3) Pedidos cancelados desde 2026, por fecha (índice estado_fecha)");
medir("con índice", db.pedidos.find({ estado: "cancelado", fecha: desde2026 }).sort({ fecha: 1 }));
medir("sin índice", db.pedidos.find({ estado: "cancelado", fecha: desde2026 }).sort({ fecha: 1 }).hint({ $natural: 1 }));
print("   mismo índice con un estado muy frecuente:");
medir("entregados (con índice)", db.pedidos.find({ estado: "entregado", fecha: desde2026 }).sort({ fecha: 1 }));

// ---------------------------------------------------------------- 4. Índices únicos
print("\n4) Índice único: insertar un producto con un sku que ya existe");
const existente = db.productos.findOne({}, { sku: 1 });
try {
  db.productos.insertOne({ sku: existente.sku, titulo: "duplicado de prueba", categoria: "test", precio: 1, stock: 1 });
  print("  se insertó (no debería)");
} catch (e) {
  print(`  rechazado con código ${e.code}: ${e.errmsg || e.message}`);
}

// ---------------------------------------------------------------- 5. Costo de almacenamiento
print("\n5) Tamaño de datos vs. índices (bytes)");
["productos", "clientes", "pedidos"].forEach((c) => {
  const st = db[c].aggregate([{ $collStats: { storageStats: {} } }]).next().storageStats;
  const detalle = Object.entries(st.indexSizes).map(([n, b]) => `${n}=${b}`).join(", ");
  print(`  ${c.padEnd(10)} datos: ${String(st.size).padStart(7)}  índices: ${String(st.totalIndexSize).padStart(6)}  (${detalle})`);
});
