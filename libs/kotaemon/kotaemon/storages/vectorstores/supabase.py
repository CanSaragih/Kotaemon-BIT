import psycopg2
import psycopg2.extras
import numpy as np
import json
import sqlalchemy
from .base import BaseVectorStore

class SupabaseVectorStore(BaseVectorStore):
    def __init__(self, connection_string, table_name, embedding_dim, **kwargs):
        self.connection_string = connection_string
        self.table_name = table_name
        self.embedding_dim = embedding_dim
        self.engine = sqlalchemy.create_engine(connection_string)
        self._ensure_table()

    def _ensure_table(self):
        with self.engine.connect() as conn:
            conn.execute(sqlalchemy.text(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    id TEXT PRIMARY KEY,
                    embedding VECTOR({self.embedding_dim}),
                    metadata JSONB
                )
            """))
            conn.commit()

    def add(self, embeddings, ids, metadatas=None, texts=None):
        conn = psycopg2.connect(self.connection_string)
        cur = conn.cursor()
        rows = []
        for i, emb in enumerate(embeddings):
            meta = metadatas[i] if metadatas else {}
            if texts: 
                meta['text'] = texts[i]
            if hasattr(emb, "embedding"):
                emb_vector = emb.embedding
            else:
                emb_vector = emb
            emb_vector = [float(x) for x in emb_vector]  
            rows.append((ids[i], emb_vector, json.dumps(meta)))
        psycopg2.extras.execute_values(
            cur,
            f"""
            INSERT INTO {self.table_name} (id, embedding, metadata)
            VALUES %s
            ON CONFLICT (id) DO UPDATE SET embedding = EXCLUDED.embedding, metadata = EXCLUDED.metadata
            """,
            rows
        )
        conn.commit()
        cur.close()
        conn.close()

    def delete(self, ids):
        # Hapus data berdasarkan id
        conn = psycopg2.connect(self.connection_string)
        cur = conn.cursor()
        cur.execute(
            f"DELETE FROM {self.table_name} WHERE id = ANY(%s)",
            (ids,)
        )
        conn.commit()
        cur.close()
        conn.close()

    def drop(self):
        # Drop table
        with self.engine.connect() as conn:
            conn.execute(sqlalchemy.text(f"DROP TABLE IF EXISTS {self.table_name}"))
            conn.commit()

    def query(self, embedding, top_k=5, doc_ids=None, **kwargs):
        with self.engine.connect() as conn:
            sql = f"""
                SELECT id, embedding, metadata
                FROM {self.table_name}
            """
            params = {"embedding": embedding, "top_k": top_k}
            if doc_ids:
                sql += " WHERE id = ANY(:doc_ids)"
                params["doc_ids"] = doc_ids
            sql += " ORDER BY embedding <-> (:embedding)::vector LIMIT :top_k"
            result = conn.execute(sqlalchemy.text(sql), params)
            rows = result.fetchall()
            docs = []
            ids = []
            scores = []
            for row in rows:
                doc_id = row[0]
                meta = row[2] or {}
                # Ambil text dari metadata jika ada
                text = ""
                if isinstance(meta, dict):
                    text = meta.get("text", "")
                elif isinstance(meta, str):
                    try:
                        meta_dict = json.loads(meta)
                        text = meta_dict.get("text", "")
                        meta = meta_dict
                    except Exception:
                        pass
                docs.append({"id": doc_id, "text": text, "metadata": meta})
                ids.append(doc_id)
                # Anda bisa tambahkan skor similarity jika ingin
            return docs, scores, ids