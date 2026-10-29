"""Pruebas del CRUD de productos (5.4): operaciones, validaciones y códigos HTTP."""
ID_INEXISTENTE = "0" * 24


def test_crear_y_obtener(api, nuevo_producto):
    creado = nuevo_producto(stock=5, marca="Marca X", atributos={"color": "rojo"})
    assert creado["rating_promedio"] is None and creado["reviews"] == []

    respuesta = api.get(f"/productos/{creado['id']}")
    assert respuesta.status_code == 200
    assert respuesta.json()["sku"] == creado["sku"]
    assert respuesta.json()["atributos"] == {"color": "rojo"}


def test_crear_devuelve_location(api):
    datos = {"sku": "TEST-LOCATION-1", "titulo": "x", "categoria": "test", "precio": 1, "stock": 1}
    respuesta = api.post("/productos", json=datos)
    assert respuesta.status_code == 201
    assert respuesta.headers["location"] == f"/productos/{respuesta.json()['id']}"


def test_campo_opcional_ausente_no_se_guarda_como_null(nuevo_producto, db):
    from bson import ObjectId
    creado = nuevo_producto()
    documento = db.productos.find_one({"_id": ObjectId(creado["id"])})
    # Igual que en el seed: si no hay marca, el campo no existe (no es marca: null).
    assert "marca" not in documento


def test_sku_duplicado_da_409(api, nuevo_producto):
    existente = nuevo_producto()
    datos = {"sku": existente["sku"], "titulo": "otro", "categoria": "test", "precio": 1, "stock": 1}
    respuesta = api.post("/productos", json=datos)
    assert respuesta.status_code == 409
    assert existente["sku"] in respuesta.json()["detail"]


def test_validaciones_de_alta_dan_422(api):
    base = {"sku": "TEST-VALIDO", "titulo": "x", "categoria": "test", "precio": 10, "stock": 1}
    invalidos = [
        {**base, "precio": -5},           # precio tiene que ser > 0
        {**base, "stock": -1},            # stock no puede ser negativo
        {**base, "sku": "minusculas"},    # formato de sku
        {**base, "precioo": 3},           # campo desconocido (extra="forbid")
        {k: v for k, v in base.items() if k != "titulo"},  # falta un obligatorio
    ]
    for datos in invalidos:
        assert api.post("/productos", json=datos).status_code == 422, datos


def test_id_mal_formado_da_422_e_inexistente_404(api):
    assert api.get("/productos/abc").status_code == 422
    assert api.get(f"/productos/{ID_INEXISTENTE}").status_code == 404
    assert api.patch(f"/productos/{ID_INEXISTENTE}", json={"precio": 1}).status_code == 404
    assert api.delete(f"/productos/{ID_INEXISTENTE}").status_code == 404


def test_listar_con_filtros(api):
    respuesta = api.get("/productos", params={"categoria": "smartphones", "precio_max": 300,
                                              "con_stock": True, "limite": 100})
    assert respuesta.status_code == 200
    productos = respuesta.json()
    assert productos, "el seed tiene smartphones de menos de $300"
    assert all(p["categoria"] == "smartphones" and p["precio"] <= 300 and p["stock"] > 0
               for p in productos)
    precios = [p["precio"] for p in productos]
    assert precios == sorted(precios)
    # El listado no trae los campos pesados
    assert "reviews" not in productos[0] and "descripcion" not in productos[0]


def test_listar_pagina_sin_repetir(api):
    pagina1 = api.get("/productos", params={"limite": 10, "desde": 0}).json()
    pagina2 = api.get("/productos", params={"limite": 10, "desde": 10}).json()
    assert len(pagina1) == len(pagina2) == 10
    assert not {p["id"] for p in pagina1} & {p["id"] for p in pagina2}


def test_actualizar_modifica_y_borra_campos(api, nuevo_producto):
    creado = nuevo_producto(marca="Marca X")
    respuesta = api.patch(f"/productos/{creado['id']}", json={"precio": 55.5, "marca": None})
    assert respuesta.status_code == 200
    actualizado = respuesta.json()
    assert actualizado["precio"] == 55.5
    assert actualizado["marca"] is None            # {"marca": null} la elimina
    assert actualizado["titulo"] == creado["titulo"]  # lo no enviado no cambia
    assert actualizado["actualizado_en"] > creado["actualizado_en"]


def test_actualizar_invalido_da_422(api, nuevo_producto):
    creado = nuevo_producto()
    assert api.patch(f"/productos/{creado['id']}", json={}).status_code == 422
    assert api.patch(f"/productos/{creado['id']}", json={"precio": None}).status_code == 422
    assert api.patch(f"/productos/{creado['id']}", json={"stock": -3}).status_code == 422


def test_actualizar_a_sku_existente_da_409(api, nuevo_producto):
    uno, otro = nuevo_producto(), nuevo_producto()
    assert api.patch(f"/productos/{uno['id']}", json={"sku": otro["sku"]}).status_code == 409


def test_eliminar_es_logico(api, nuevo_producto, db):
    from bson import ObjectId
    creado = nuevo_producto(categoria="test-baja")
    assert api.delete(f"/productos/{creado['id']}").status_code == 204
    # Para la API ya no existe...
    assert api.get(f"/productos/{creado['id']}").status_code == 404
    assert api.delete(f"/productos/{creado['id']}").status_code == 404
    assert api.get("/productos", params={"categoria": "test-baja"}).json() == []
    # ...pero el documento sigue en la base, marcado como inactivo
    documento = db.productos.find_one({"_id": ObjectId(creado["id"])})
    assert documento["activo"] is False


def test_review_recalcula_rating(api, nuevo_producto):
    creado = nuevo_producto()
    review = {"rating": 5, "comentario": "Excelente", "autor": "Ana", "email": "ana@example.com"}
    api.post(f"/productos/{creado['id']}/reviews", json=review)
    respuesta = api.post(f"/productos/{creado['id']}/reviews",
                         json={**review, "rating": 2, "comentario": "$precio caro"})
    assert respuesta.status_code == 201
    producto = respuesta.json()
    assert producto["rating_promedio"] == 3.5
    # Un comentario que empieza con $ se guarda tal cual (no se interpreta como campo)
    assert producto["reviews"][-1]["comentario"] == "$precio caro"


def test_review_invalida_da_422(api, nuevo_producto):
    creado = nuevo_producto()
    review = {"rating": 6, "comentario": "x", "autor": "Ana", "email": "ana@example.com"}
    assert api.post(f"/productos/{creado['id']}/reviews", json=review).status_code == 422
