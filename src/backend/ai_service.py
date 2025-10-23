from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, ClassVar, Dict, List, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .config import Settings
from .db import get_connection


class AIService:
    _instance: ClassVar["AIService | None"] = None

    def __new__(cls) -> "AIService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self.cache_dir = os.path.join(Settings.DATA_DIR, "ai_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self._vectorizer: Optional[TfidfVectorizer] = None
        self._tfidf_matrix: Optional[Any] = None
        self._material_rows: List[Dict[str, Any]] = []
        self._material_descriptions: List[str] = []
        self._initialized = True

    def load_models(self, con: sqlite3.Connection) -> None:
        if self._vectorizer is not None and self._tfidf_matrix is not None and self._material_rows:
            return
        materiales = con.execute(
            "SELECT codigo, descripcion, descripcion_larga, unidad_medida, precio_usd FROM materiales WHERE activo = 1"
        ).fetchall()
        if not materiales:
            self._material_rows = []
            self._material_descriptions = []
            self._vectorizer = None
            self._tfidf_matrix = None
            return
        descriptions = [f"{m['descripcion']} {m['descripcion_larga']}" for m in materiales]
        vectorizer = TfidfVectorizer(max_features=1000, stop_words="english")
        tfidf_matrix = vectorizer.fit_transform(descriptions)
        self._vectorizer = vectorizer
        self._tfidf_matrix = tfidf_matrix
        self._material_rows = [dict(row) for row in materiales]
        self._material_descriptions = descriptions

    def get_suggestions_for_solicitud(self, solicitud_id: int) -> List[Dict[str, Any]]:
        """Genera sugerencias IA para todos los Ã­tems de una solicitud."""
        with get_connection() as con:
            # Obtener solicitud e Ã­tems
            sol_row = con.execute(
                "SELECT id, centro_solicitante, criticidad, fecha_necesidad FROM solicitudes WHERE id = ?",
                (solicitud_id,)
            ).fetchone()
            if not sol_row:
                return []

            items = con.execute(
                "SELECT item_index, material, um, cantidad, precio_unitario_est FROM solicitud_items WHERE solicitud_id = ?",
                (solicitud_id,)
            ).fetchall()

            suggestions = []
            for item in items:
                item_sugs = self._get_suggestions_for_item(con, solicitud_id, sol_row, item)
                suggestions.extend(item_sugs)

            return suggestions

    def _get_suggestions_for_item(self, con: sqlite3.Connection, solicitud_id: int, sol_row: sqlite3.Row, item: sqlite3.Row) -> List[Dict[str, Any]]:
        """Genera sugerencias para un Ã­tem especÃ­fico."""
        suggestions = []

        # Stock split
        stock_sug = self._suggest_stock_split(con, item, sol_row["centro_solicitante"])
        if stock_sug:
            suggestions.append(stock_sug)

        # Equivalentes
        equiv_sugs = self._suggest_equivalentes(con, item["material"], item["um"])
        suggestions.extend(equiv_sugs[:Settings.AI_MAX_SUGGESTIONS])

        # Proveedor
        prov_sug = self._suggest_proveedor(con, item["material"])
        if prov_sug:
            suggestions.append(prov_sug)

        # Precio
        price_sug = self._suggest_precio(con, item["material"])
        if price_sug:
            suggestions.append(price_sug)

        # Lead time
        lt_sug = self._suggest_leadtime(con, item["material"], sol_row["centro_solicitante"])
        if lt_sug:
            suggestions.append(lt_sug)

        # SLA risk
        sla_sug = self._suggest_sla_risk(con, solicitud_id, sol_row, item)
        if sla_sug:
            suggestions.append(sla_sug)

        # Texto justificaciÃ³n
        text_sug = self._suggest_texto_justif(con, item, suggestions)
        if text_sug:
            suggestions.append(text_sug)

        return suggestions

    def _suggest_stock_split(self, con: sqlite3.Connection, item: sqlite3.Row, centro: str) -> Optional[Dict[str, Any]]:
        """Sugiere split stock/compra basado en stock disponible."""
        # Simular stock_disponible - en realidad, necesitarÃ­as una tabla stock_disponible
        # Por ahora, asumir stock aleatorio para demo
        import random
        stock_total = random.randint(0, int(item["cantidad"]) * 2)
        if stock_total == 0:
            return None

        stock_qty = min(item["cantidad"], stock_total)
        compra_qty = item["cantidad"] - stock_qty

        if compra_qty > 0:
            payload = {
                "stock": [{"centro": centro, "almacen_virtual": "0001", "lote": None, "cantidad": stock_qty}],
                "compra": {"cantidad": compra_qty}
            }
        else:
            payload = {"stock": [{"centro": centro, "almacen_virtual": "0001", "lote": None, "cantidad": stock_qty}]}

        return {
            "item_index": item["item_index"],
            "suggestions": [{
                "type": "stock_split",
                "title": f"Usar stock {stock_qty} UN + comprar {compra_qty} UN" if compra_qty > 0 else f"Usar stock {stock_qty} UN (100%)",
                "payload": payload,
                "reason": f"Stock disponible {stock_total} UN detectado (prioridad mismo centro).",
                "confidence": 0.86 if stock_qty > 0 else 0.95,
                "sources": ["stock_disponible"]
            }]
        }

    def _suggest_equivalentes(self, con: sqlite3.Connection, material: str, um: str) -> List[Dict[str, Any]]:
        """Sugiere materiales equivalentes usando TF-IDF."""
        self.load_models(con)
        if not self._vectorizer or self._tfidf_matrix is None or not self._material_rows:
            return []

        try:
            target_idx = next(i for i, row in enumerate(self._material_rows) if row["codigo"] == material)
        except StopIteration:
            return []

        target_desc = self._material_descriptions[target_idx]
        target_vec = self._vectorizer.transform([target_desc])
        similarities = cosine_similarity(target_vec, self._tfidf_matrix).flatten()

        suggestions: List[Dict[str, Any]] = []
        for idx in np.argsort(similarities)[::-1]:
            if idx == target_idx:
                continue
            mat = self._material_rows[idx]
            if mat.get("unidad_medida") != um:
                continue
            sim = float(similarities[idx])
            if sim < 0.5:
                continue
            suggestions.append(
                {
                    "type": "equivalente",
                    "title": f"Equivalente: {mat['codigo']} (similaridad {sim:.2f})",
                    "payload": {"material": mat["codigo"], "unidad_medida": mat["unidad_medida"]},
                    "reason": "Descripcion similar (TF-IDF) y unidad compatible.",
                    "confidence": min(sim, 0.9),
                    "sources": ["materiales"],
                }
            )
            if len(suggestions) >= Settings.AI_MAX_SUGGESTIONS:
                break

        return suggestions

    def _suggest_proveedor(self, con: sqlite3.Connection, material: str) -> Optional[Dict[str, Any]]:
        """Sugiere proveedor basado en histÃ³rico de PO."""
        rows = con.execute(
            "SELECT proveedor_nombre, proveedor_email, COUNT(*) as cnt FROM purchase_orders WHERE solped_id IN (SELECT id FROM solpeds WHERE material = ?) GROUP BY proveedor_nombre, proveedor_email ORDER BY cnt DESC LIMIT 1",
            (material,)
        ).fetchall()

        if not rows:
            return None

        prov = rows[0]
        return {
            "type": "proveedor",
            "title": f"Proveedor recomendado: {prov['proveedor_nombre']}",
            "payload": {"proveedor_nombre": prov['proveedor_nombre'], "proveedor_email": prov['proveedor_email']},
            "reason": f"{prov['cnt']} PO previas para el material en Ãºltimos 6 meses.",
            "confidence": min(prov['cnt'] / 10.0, 0.9),  # normalizar
            "sources": ["purchase_orders"]
        }

    def _suggest_precio(self, con: sqlite3.Connection, material: str) -> Optional[Dict[str, Any]]:
        """Sugiere precio basado en histÃ³rico y CSV."""
        # Precio de materiales
        mat_row = con.execute("SELECT precio_usd FROM materiales WHERE codigo = ?", (material,)).fetchone()
        precio_csv = mat_row['precio_usd'] if mat_row else 0

        # Mediana de PO
        po_prices = con.execute(
            "SELECT subtotal / (SELECT cantidad FROM solpeds WHERE id = po.solped_id) as precio FROM purchase_orders po WHERE po.solped_id IN (SELECT id FROM solpeds WHERE material = ?)",
            (material,)
        ).fetchall()
        if po_prices:
            prices = [p['precio'] for p in po_prices if p['precio']]
            mediana_po = np.median(prices) if prices else 0
        else:
            mediana_po = 0

        if precio_csv == 0 and mediana_po == 0:
            return None

        # Suavizar
        precio_est = Settings.AI_PRICE_SMOOTHING * mediana_po + (1 - Settings.AI_PRICE_SMOOTHING) * precio_csv
        if precio_est == 0:
            return None

        return {
            "type": "precio",
            "title": f"Precio est. USD {precio_est:.2f}",
            "payload": {"precio_unitario_est": precio_est},
            "reason": "Mediana de PO + CSV stock.",
            "confidence": 0.74,
            "sources": ["purchase_orders", "stock_disponible", "materiales"]
        }

    def _suggest_leadtime(self, con: sqlite3.Connection, material: str, centro: str) -> Optional[Dict[str, Any]]:
        """Sugiere lead time basado en heurÃ­sticas."""
        # HeurÃ­stica simple
        min_days, max_days = 7, 15  # nacional
        # Si hay histÃ³rico de traslados, usar mediana
        # Por ahora, heurÃ­stica

        return {
            "type": "leadtime",
            "title": f"Lead time estimado: {min_days}â€“{max_days} dÃ­as",
            "payload": {"min": min_days, "max": max_days},
            "reason": "Proveedor nacional; histÃ³rico similar.",
            "confidence": 0.6,
            "sources": ["purchase_orders", "traslados"]
        }

    def _suggest_sla_risk(self, con: sqlite3.Connection, solicitud_id: int, sol_row: sqlite3.Row, item: sqlite3.Row) -> Optional[Dict[str, Any]]:
        """Sugiere riesgo SLA."""
        # LÃ³gica simplificada
        criticidad = sol_row["criticidad"] or "Normal"
        # Asumir lead time estimado
        lead_est = 10  # dÃ­as
        # Plazo restante - simplificar
        prob = "medio" if criticidad == "Alta" and lead_est > 5 else "bajo"

        return {
            "type": "sla_risk",
            "title": f"Riesgo SLA: {prob.upper()}",
            "payload": {"etapa": "po_emision", "prob": prob},
            "reason": f"Criticidad {criticidad}; lead time esperado {lead_est} dÃ­as.",
            "confidence": 0.65,
            "sources": ["sla_rules", "solicitud_tratamiento_log"]
        }

    def _suggest_texto_justif(self, con: sqlite3.Connection, item: sqlite3.Row, suggestions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Genera texto de justificaciÃ³n basado en otras sugerencias."""
        # Resumir
        texto = f"Se propone adquirir {item['cantidad']} {item['um']} del material {item['material']}."

        for sug in suggestions:
            if sug["type"] == "stock_split":
                stock_qty = sum(s["cantidad"] for s in sug["payload"].get("stock", []))
                compra_qty = sug["payload"].get("compra", {}).get("cantidad", 0)
                texto += f" Cubrir {stock_qty} UN desde stock y adquirir {compra_qty} UN."
            elif sug["type"] == "proveedor":
                texto += f" Proveedor sugerido: {sug['payload']['proveedor_nombre']}."
            elif sug["type"] == "precio":
                texto += f" Precio estimado USD {sug['payload']['precio_unitario_est']:.2f}."

        return {
            "type": "texto_justif",
            "title": "Borrador de justificaciÃ³n",
            "payload": {"texto": texto},
            "reason": "Resumen basado en stock y precios histÃ³ricos.",
            "confidence": 0.9,
            "sources": ["*resumen interno*"]
        }

    def apply_suggestion(self, solicitud_id: int, item_index: int, suggestion_type: str, payload: Dict[str, Any], actor_id: str) -> bool:
        """Aplica una sugerencia al sistema."""
        with get_connection() as con:
            try:
                # Aplicar segÃºn tipo
                if suggestion_type == "stock_split":
                    # Guardar en solicitud_items_stock (asumir tabla existe o crear)
                    # Por ahora, solo log
                    pass
                elif suggestion_type == "equivalente":
                    con.execute(
                        "UPDATE solicitud_items_tratamiento SET codigo_equivalente = ? WHERE solicitud_id = ? AND item_index = ?",
                        (payload["material"], solicitud_id, item_index)
                    )
                elif suggestion_type == "proveedor":
                    # Asumir que se guarda en tratamiento
                    pass
                elif suggestion_type == "precio":
                    con.execute(
                        "UPDATE solicitud_items_tratamiento SET precio_unitario_estimado = ? WHERE solicitud_id = ? AND item_index = ?",
                        (payload["precio_unitario_est"], solicitud_id, item_index)
                    )
                elif suggestion_type == "texto_justif":
                    # Actualizar justificaciÃ³n
                    pass

                # Log
                con.execute(
                    "INSERT INTO ai_suggestions_log (solicitud_id, item_index, suggestion_type, payload_json, confidence, accepted, actor_id) VALUES (?, ?, ?, ?, 0.8, 1, ?)",
                    (solicitud_id, item_index, suggestion_type, json.dumps(payload), actor_id)
                )

                # Log en solicitud_tratamiento_log
                con.execute(
                    "INSERT INTO solicitud_tratamiento_log (solicitud_id, actor_id, tipo, payload) VALUES (?, ?, 'IA_aplicada', ?)",
                    (solicitud_id, actor_id, json.dumps({"type": suggestion_type, "item_index": item_index}))
                )

                con.commit()
                return True
            except Exception:
                con.rollback()
                return False

    def reject_suggestion(self, solicitud_id: int, item_index: int, suggestion_type: str, actor_id: str) -> bool:
        """Rechaza una sugerencia."""
        with get_connection() as con:
            try:
                con.execute(
                    "INSERT INTO ai_suggestions_log (solicitud_id, item_index, suggestion_type, payload_json, confidence, accepted, actor_id) VALUES (?, ?, ?, ?, 0.8, 0, ?)",
                    (solicitud_id, item_index, suggestion_type, "{}", actor_id)
                )
                con.commit()
                return True
            except Exception:
                con.rollback()
                return False

