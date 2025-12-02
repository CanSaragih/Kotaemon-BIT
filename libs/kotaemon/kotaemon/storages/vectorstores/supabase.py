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
                    metadata JSONB,
                    text TEXT
                )
            """))
            # Tambahkan index untuk metadata type
            conn.execute(sqlalchemy.text(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_type 
                ON {self.table_name} ((metadata->>'type'))
            """))
            # Tambahkan index untuk file_name
            conn.execute(sqlalchemy.text(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_file_name 
                ON {self.table_name} ((metadata->>'file_name'))
            """))
            conn.commit()

    def add(self, embeddings, ids, metadatas=None, texts=None):
        conn = psycopg2.connect(self.connection_string)
        cur = conn.cursor()
        rows = []
        for i, emb in enumerate(embeddings):
            meta = metadatas[i] if metadatas else {}
            text = texts[i] if texts else ""
            
            # Pastikan text tersimpan di kolom tersendiri
            if not text and meta.get('text'):
                text = meta.get('text')
            
            if hasattr(emb, "embedding"):
                emb_vector = emb.embedding
            else:
                emb_vector = emb
            emb_vector = [float(x) for x in emb_vector]  
            
            # Simpan text di metadata juga untuk backward compatibility
            meta['text'] = text
            
            rows.append((ids[i], emb_vector, json.dumps(meta), text))
        
        psycopg2.extras.execute_values(
            cur,
            f"""
            INSERT INTO {self.table_name} (id, embedding, metadata, text)
            VALUES %s
            ON CONFLICT (id) DO UPDATE SET 
                embedding = EXCLUDED.embedding, 
                metadata = EXCLUDED.metadata,
                text = EXCLUDED.text
            """,
            rows
        )
        conn.commit()
        cur.close()
        conn.close()

    def delete(self, ids):
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
        with self.engine.connect() as conn:
            conn.execute(sqlalchemy.text(f"DROP TABLE IF EXISTS {self.table_name}"))
            conn.commit()

    def query(self, embedding, top_k=5, doc_ids=None, **kwargs):
        with self.engine.connect() as conn:
            sql = f"""
                SELECT id, embedding, metadata, text
                FROM {self.table_name}
            """
            params = {"embedding": embedding, "top_k": top_k}
            
            # Filter berdasarkan doc_ids jika ada
            where_clauses = []
            if doc_ids:
                where_clauses.append("id = ANY(:doc_ids)")
                params["doc_ids"] = doc_ids
            
            # Tambahkan filter dari kwargs jika ada
            filters = kwargs.get('filters')
            if filters and hasattr(filters, 'filters'):
                for filter_item in filters.filters:
                    if filter_item.key == "file_id":
                        # Konversi file_id filter ke file_name
                        where_clauses.append("metadata->>'file_id' = ANY(:file_ids)")
                        params["file_ids"] = filter_item.value
            
            if where_clauses:
                sql += " WHERE " + " AND ".join(where_clauses)
            
            sql += " ORDER BY embedding <-> (:embedding)::vector LIMIT :top_k"
            
            result = conn.execute(sqlalchemy.text(sql), params)
            rows = result.fetchall()
            
            docs = []
            ids = []
            scores = []
            
            for row in rows:
                doc_id = row[0]
                meta = row[2] or {}
                text = row[3] or ""
                
                # Parse metadata jika string
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except Exception:
                        meta = {}
                
                # Ambil text dari berbagai sumber
                if not text:
                    text = meta.get("text", "")
                
                docs.append({"id": doc_id, "text": text, "metadata": meta})
                ids.append(doc_id)
                scores.append(0.0)  # Bisa dihitung jika perlu
            
            return docs, scores, ids