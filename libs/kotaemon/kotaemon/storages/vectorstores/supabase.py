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
            # Index untuk metadata
            conn.execute(sqlalchemy.text(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_type 
                ON {self.table_name} ((metadata->>'type'))
            """))
            conn.execute(sqlalchemy.text(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_file_name 
                ON {self.table_name} ((metadata->>'file_name'))
            """))
            # ✅ TAMBAHAN: Full-text search index
            conn.execute(sqlalchemy.text(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_text_search 
                ON {self.table_name} USING gin(to_tsvector('indonesian', text))
            """))
            conn.commit()

    def add(self, embeddings, ids, metadatas=None, texts=None):
        """
        ✅ ENHANCED: Add dengan better text extraction dan logging
        """
        conn = psycopg2.connect(self.connection_string)
        cur = conn.cursor()
        rows = []
        
        for i, emb in enumerate(embeddings):
            meta = metadatas[i] if metadatas else {}
            text = texts[i] if texts else ""
            
            # ✅ ENHANCED: Multiple fallback untuk extract text
            if not text:
                # Try dari metadata['text']
                text = meta.get('text', '')
            
            if not text:
                # Try dari metadata['content']
                text = meta.get('content', '')
            
            if not text:
                # Try dari metadata['page_content']
                text = meta.get('page_content', '')
            
            # ✅ LOGGING: Debug apa yang disimpan
            if not text:
                print(f"⚠️ WARNING: Empty text for doc {ids[i]}")
                print(f"   Metadata keys: {list(meta.keys())}")
            else:
                print(f"✅ Saving doc {ids[i]}: {len(text)} chars")
            
            if hasattr(emb, "embedding"):
                emb_vector = emb.embedding
            else:
                emb_vector = emb
            emb_vector = [float(x) for x in emb_vector]
            
            # ✅ CRITICAL: Simpan text di metadata DAN kolom text
            meta['text'] = text
            meta['text_length'] = len(text)  # Untuk debugging
            
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
        
        print(f"✅ Successfully saved {len(rows)} documents to Supabase")

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
        """
        ✅ HYBRID SEARCH: Menggabungkan vector similarity + full-text search
        """
        try:
            with self.engine.connect() as conn:
                # Extract query text for full-text search
                query_text = kwargs.get('query_text', '')
                
                # ✅ IMPROVED: Preprocessing query text
                if query_text:
                    # Remove stopwords dan kata umum
                    import re
                    stopwords = {'ini', 'itu', 'yang', 'dan', 'atau', 'dari', 'ke', 'di', 'untuk', 
                                'dengan', 'pada', 'adalah', 'secara', 'dapat', 'akan', 'telah'}
                    
                    # Tokenize dan filter
                    tokens = re.findall(r'\w+', query_text.lower())
                    important_tokens = [t for t in tokens if t not in stopwords and len(t) > 2]
                    
                    # Reconstruct query untuk full-text search
                    cleaned_query = ' '.join(important_tokens)
                    
                    print(f"🔍 Original query: '{query_text}'")
                    print(f"🔍 Cleaned query: '{cleaned_query}'")
                else:
                    cleaned_query = query_text
                
                # ✅ DEFENSIVE: Skip full-text search jika query kosong setelah cleaning
                if not cleaned_query or len(cleaned_query.strip()) < 3:
                    print("⚠️ Query text too short or empty after cleaning, using vector search only")
                    # Fallback to pure vector search
                    sql = f"""
                        SELECT 
                            id, 
                            embedding, 
                            metadata, 
                            text,
                            embedding <-> (:embedding)::vector AS vector_distance,
                            0 AS text_score,
                            (1 - (embedding <-> (:embedding)::vector)) AS combined_score
                        FROM {self.table_name}
                    """
                    params = {"embedding": embedding, "top_k": top_k}
                    
                    # ✅ FIX: WHERE clause untuk vector-only search
                    where_clauses = []
                    if doc_ids:
                        where_clauses.append("id = ANY(:doc_ids)")
                        params["doc_ids"] = doc_ids
                    
                    filters = kwargs.get('filters')
                    if filters and hasattr(filters, 'filters'):
                        for filter_item in filters.filters:
                            if filter_item.key == "file_id":
                                where_clauses.append("metadata->>'file_id' = ANY(:file_ids)")
                                params["file_ids"] = filter_item.value
                    
                    if where_clauses:
                        sql += " WHERE " + " AND ".join(where_clauses)
                    
                    sql += " ORDER BY combined_score DESC LIMIT :top_k"
                else:
                    # ✅ HYBRID SEARCH SQL - FIXED AMBIGUOUS ID
                    sql = f"""
                        WITH vector_results AS (
                            SELECT 
                                id, 
                                embedding, 
                                metadata, 
                                text,
                                embedding <-> (:embedding)::vector AS vector_distance
                            FROM {self.table_name}
                    """
                    
                    # ✅ CRITICAL FIX: Add WHERE clause INSIDE CTE
                    cte_where_clauses = []
                    if doc_ids:
                        cte_where_clauses.append("id = ANY(:doc_ids)")
                    
                    filters = kwargs.get('filters')
                    if filters and hasattr(filters, 'filters'):
                        for filter_item in filters.filters:
                            if filter_item.key == "file_id":
                                cte_where_clauses.append("metadata->>'file_id' = ANY(:file_ids)")
                    
                    if cte_where_clauses:
                        sql += " WHERE " + " AND ".join(cte_where_clauses)
                    
                    sql += """
                        ),
                        text_results AS (
                            SELECT 
                                id,
                                ts_rank(
                                    to_tsvector('indonesian', COALESCE(text, '')), 
                                    plainto_tsquery('indonesian', :query_text)
                                ) AS text_score
                            FROM {table_name}
                            WHERE text IS NOT NULL 
                                AND text != ''
                                AND to_tsvector('indonesian', text) @@ plainto_tsquery('indonesian', :query_text)
                    """.format(table_name=self.table_name)
                    
                    # ✅ Add WHERE clause untuk text_results CTE juga
                    if cte_where_clauses:
                        sql += " AND " + " AND ".join(cte_where_clauses)
                    
                    sql += """
                        )
                        SELECT 
                            v.id,
                            v.embedding,
                            v.metadata,
                            v.text,
                            v.vector_distance,
                            COALESCE(t.text_score, 0) AS text_score,
                            (0.7 * (1 - v.vector_distance)) + (0.3 * COALESCE(t.text_score, 0)) AS combined_score
                        FROM vector_results v
                        LEFT JOIN text_results t ON v.id = t.id
                        ORDER BY combined_score DESC LIMIT :top_k
                    """
                    
                    params = {
                        "embedding": embedding, 
                        "query_text": cleaned_query,
                        "top_k": top_k
                    }
                    
                    # ✅ Add params untuk filtering
                    if doc_ids:
                        params["doc_ids"] = doc_ids
                    
                    if filters and hasattr(filters, 'filters'):
                        for filter_item in filters.filters:
                            if filter_item.key == "file_id":
                                params["file_ids"] = filter_item.value
                
                print(f"🔍 Executing SQL query...")
                result = conn.execute(sqlalchemy.text(sql), params)
                rows = result.fetchall()
                
                docs = []
                ids = []
                scores = []
                
                for row in rows:
                    doc_id = row[0]
                    meta = row[2] or {}
                    text = row[3] or ""
                    combined_score = float(row[6]) if len(row) > 6 else 0.0
                    
                    if isinstance(meta, str):
                        try:
                            meta = json.loads(meta)
                        except Exception:
                            meta = {}
                    
                    # ✅ Fallback: Ambil text dari metadata jika kolom text kosong
                    if not text:
                        text = meta.get("text", "")
                        if text:
                            print(f"⚠️ Retrieved text from metadata for doc {doc_id[:8]}...")
                    
                    docs.append({"id": doc_id, "text": text, "metadata": meta})
                    ids.append(doc_id)
                    scores.append(combined_score)
                
                print(f"✅ Hybrid search returned {len(docs)} documents")
                return docs, scores, ids
                
        except Exception as e:
            print(f"❌ Error in Supabase query: {e}")
            import traceback
            traceback.print_exc()
            # Return empty results instead of crashing
            return [], [], []