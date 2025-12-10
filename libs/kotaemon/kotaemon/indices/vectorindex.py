from __future__ import annotations

import threading
import uuid
from pathlib import Path
from typing import Optional, Sequence, cast

from theflow.settings import settings as flowsettings

from kotaemon.base import BaseComponent, Document, RetrievedDocument
from kotaemon.embeddings import BaseEmbeddings
from kotaemon.storages import BaseDocumentStore, BaseVectorStore

from .base import BaseIndexing, BaseRetrieval
from .rankings import BaseReranking, LLMReranking

VECTOR_STORE_FNAME = "vectorstore"
DOC_STORE_FNAME = "docstore"


class VectorIndexing(BaseIndexing):
    """Ingest the document, run through the embedding, and store the embedding in a
    vector store.

    This pipeline supports the following set of inputs:
        - List of documents
        - List of texts
    """

    cache_dir: Optional[str] = getattr(flowsettings, "KH_CHUNKS_OUTPUT_DIR", None)
    vector_store: BaseVectorStore
    doc_store: Optional[BaseDocumentStore] = None
    embedding: BaseEmbeddings
    count_: int = 0

    def to_retrieval_pipeline(self, *args, **kwargs):
        """Convert the indexing pipeline to a retrieval pipeline"""
        return VectorRetrieval(
            vector_store=self.vector_store,
            doc_store=self.doc_store,
            embedding=self.embedding,
            **kwargs,
        )

    def write_chunk_to_file(self, docs: list[Document]):
        # save the chunks content into markdown format
        if self.cache_dir:
            file_name = docs[0].metadata.get("file_name")
            if not file_name:
                return

            file_name = Path(file_name)
            for i in range(len(docs)):
                markdown_content = ""
                if "page_label" in docs[i].metadata:
                    page_label = str(docs[i].metadata["page_label"])
                    markdown_content += f"Page label: {page_label}"
                if "file_name" in docs[i].metadata:
                    filename = docs[i].metadata["file_name"]
                    markdown_content += f"\nFile name: {filename}"
                if "section" in docs[i].metadata:
                    section = docs[i].metadata["section"]
                    markdown_content += f"\nSection: {section}"
                if "type" in docs[i].metadata:
                    if docs[i].metadata["type"] == "image":
                        image_origin = docs[i].metadata["image_origin"]
                        image_origin = f'<p><img src="{image_origin}"></p>'
                        markdown_content += f"\nImage origin: {image_origin}"
                if docs[i].text:
                    markdown_content += f"\ntext:\n{docs[i].text}"

                with open(
                    Path(self.cache_dir) / f"{file_name.stem}_{self.count_+i}.md",
                    "w",
                    encoding="utf-8",
                ) as f:
                    f.write(markdown_content)

    def add_to_docstore(self, docs: list[Document]):
        if self.doc_store:
            print("Adding documents to doc store")
            self.doc_store.add(docs)

    def add_to_vectorstore(self, docs: list[Document]):
        # in case we want to skip embedding
        if self.vector_store:
            print(f"Getting embeddings for {len(docs)} nodes")
            embeddings = self.embedding(docs)
            print("Adding embeddings to vector store")
            
            # ✅ CRITICAL FIX: Extract text dan metadata dari docs
            texts = []
            metadatas = []
            
            for doc in docs:
                # Extract text
                text = doc.text if hasattr(doc, 'text') else str(doc)
                texts.append(text)
                
                # Extract metadata
                metadata = doc.metadata if hasattr(doc, 'metadata') else {}
                # ✅ Simpan text di metadata juga (backup)
                metadata['text'] = text
                metadata['doc_id'] = doc.doc_id
                metadatas.append(metadata)
                
                # ✅ Logging untuk debug
                print(f"  📄 Doc {doc.doc_id[:8]}...: {len(text)} chars, type={metadata.get('type', 'text')}")
            
            # ✅ Pass semua data ke vector store
            self.vector_store.add(
                embeddings=embeddings,
                ids=[t.doc_id for t in docs],
                texts=texts,  # ✅ CRITICAL
                metadatas=metadatas,  # ✅ CRITICAL
            )

    def run(self, text: str | list[str] | Document | list[Document]):
        input_: list[Document] = []
        if not isinstance(text, list):
            text = [text]

        for item in cast(list, text):
            if isinstance(item, str):
                input_.append(Document(text=item, id_=str(uuid.uuid4())))
            elif isinstance(item, Document):
                input_.append(item)
            else:
                raise ValueError(
                    f"Invalid input type {type(item)}, should be str or Document"
                )

        self.add_to_vectorstore(input_)
        self.add_to_docstore(input_)
        self.write_chunk_to_file(input_)
        self.count_ += len(input_)


class VectorRetrieval(BaseRetrieval):
    """Retrieve list of documents from vector store"""

    vector_store: BaseVectorStore
    doc_store: Optional[BaseDocumentStore] = None
    embedding: BaseEmbeddings
    rerankers: Sequence[BaseReranking] = []
    top_k: int = 5
    first_round_top_k_mult: int = 10
    retrieval_mode: str = "hybrid"  # vector, text, hybrid

    def _filter_docs(
        self, documents: list[RetrievedDocument], top_k: int | None = None
    ):
        if top_k:
            documents = documents[:top_k]
        return documents

    def run(
        self, text: str | Document, top_k: Optional[int] = None, **kwargs
    ) -> list[RetrievedDocument]:
        """Retrieve a list of documents from vector store

        Args:
            text: the text to retrieve similar documents
            top_k: number of top similar documents to return

        Returns:
            list[RetrievedDocument]: list of retrieved documents
        """
        if top_k is None:
            top_k = self.top_k

        do_extend = kwargs.pop("do_extend", False)
        thumbnail_count = kwargs.pop("thumbnail_count", 3)

        if do_extend:
            top_k_first_round = top_k * self.first_round_top_k_mult
        else:
            top_k_first_round = top_k

        if self.doc_store is None:
            raise ValueError(
                "doc_store is not provided. Please provide a doc_store to "
                "retrieve the documents"
            )

        result: list[RetrievedDocument] = []
        scope = kwargs.pop("scope", None)
        
        # ✅ CRITICAL FIX: Extract query text untuk hybrid search
        query_text = kwargs.pop("query_text", "")
        if not query_text:
            query_text = text.text if isinstance(text, Document) else text

        print(f"🔍 VectorRetrieval mode: {self.retrieval_mode}")
        print(f"🔍 Query text: '{query_text}'")

        if self.retrieval_mode == "vector":
            emb = self.embedding(text)[0].embedding
            _, scores, ids = self.vector_store.query(
                embedding=emb, 
                top_k=top_k_first_round, 
                doc_ids=scope, 
                query_text=query_text,
                **kwargs
            )
            docs = self.doc_store.get(ids)
            result = [
                RetrievedDocument(**doc.to_dict(), score=score)
                for doc, score in zip(docs, scores)
            ]
        elif self.retrieval_mode == "text":
            query = text.text if isinstance(text, Document) else text
            docs = []
            if scope:
                docs = self.doc_store.query(
                    query, top_k=top_k_first_round, doc_ids=scope
                )
            result = [RetrievedDocument(**doc.to_dict(), score=-1.0) for doc in docs]
        elif self.retrieval_mode == "hybrid":
            # ✅ FIX: Better error handling untuk hybrid mode
            import threading
            
            # similarity search section
            emb = self.embedding(text)[0].embedding
            vs_docs: list[RetrievedDocument] = []
            vs_ids: list[str] = []
            vs_scores: list[float] = []
            vs_error = None

            def query_vectorstore():
                nonlocal vs_docs
                nonlocal vs_scores
                nonlocal vs_ids
                nonlocal vs_error

                try:
                    assert self.doc_store is not None
                    _, vs_scores, vs_ids = self.vector_store.query(
                        embedding=emb, 
                        top_k=top_k_first_round, 
                        doc_ids=scope, 
                        query_text=query_text,
                        **kwargs
                    )
                    if vs_ids:
                        vs_docs = self.doc_store.get(vs_ids)
                except Exception as e:
                    vs_error = e
                    print(f"❌ Error in query_vectorstore: {e}")
                    import traceback
                    traceback.print_exc()

            # full-text search section
            ds_docs: list[RetrievedDocument] = []
            ds_error = None

            def query_docstore():
                nonlocal ds_docs
                nonlocal ds_error

                try:
                    assert self.doc_store is not None
                    query = text.text if isinstance(text, Document) else text
                    if scope:
                        ds_docs = self.doc_store.query(
                            query, top_k=top_k_first_round, doc_ids=scope
                        )
                except Exception as e:
                    ds_error = e
                    print(f"❌ Error in query_docstore: {e}")
                    import traceback
                    traceback.print_exc()

            vs_query_thread = threading.Thread(target=query_vectorstore)
            ds_query_thread = threading.Thread(target=query_docstore)

            vs_query_thread.start()
            ds_query_thread.start()

            vs_query_thread.join()
            ds_query_thread.join()

            # ✅ Check for errors
            if vs_error:
                print(f"⚠️ Vector search failed: {vs_error}")
                if ds_error:
                    print(f"⚠️ Docstore search also failed: {ds_error}")
                    raise vs_error  # Both failed, raise error
                else:
                    # Fallback to docstore only
                    print("⚠️ Falling back to docstore search only")
                    result = [
                        RetrievedDocument(**doc.to_dict(), score=-1.0)
                        for doc in ds_docs
                    ]
            elif ds_error:
                print(f"⚠️ Docstore search failed: {ds_error}")
                # Fallback to vector search only
                print("⚠️ Falling back to vector search only")
                result = [
                    RetrievedDocument(**doc.to_dict(), score=score)
                    for doc, score in zip(vs_docs, vs_scores)
                ]
            else:
                # Both succeeded
                result = [
                    RetrievedDocument(**doc.to_dict(), score=-1.0)
                    for doc in ds_docs
                    if doc not in vs_ids
                ]
                result += [
                    RetrievedDocument(**doc.to_dict(), score=score)
                    for doc, score in zip(vs_docs, vs_scores)
                ]
                print(f"✅ Got {len(vs_docs)} from vectorstore")
                print(f"✅ Got {len(ds_docs)} from docstore")

        # use additional reranker to re-order the document list
        if self.rerankers and text:
            for reranker in self.rerankers:
                # if reranker is LLMReranking, limit the document with top_k items only
                if isinstance(reranker, LLMReranking):
                    result = self._filter_docs(result, top_k=top_k)
                result = reranker.run(documents=result, query=text)

        result = self._filter_docs(result, top_k=top_k)
        print(f"✅ Got final {len(result)} retrieved documents")

        # add page thumbnails to the result if exists
        thumbnail_doc_ids: set[str] = set()
        # we should copy the text from retrieved text chunk
        for doc in result:
            thumbnail_id = doc.metadata.get("thumbnail_doc_id", "")
            if thumbnail_id:
                thumbnail_doc_ids.add(thumbnail_id)

        thumbnail_docs = []
        if do_extend and self.doc_store and thumbnail_doc_ids:
            thumbnail_docs = self.doc_store.get(list(thumbnail_doc_ids))

            if thumbnail_count and len(thumbnail_docs) > thumbnail_count:
                thumbnail_docs = thumbnail_docs[:thumbnail_count]
            for thumbnail in thumbnail_docs:
                thumbnail.metadata["type"] = "thumbnail"

            result += [
                RetrievedDocument(**doc.to_dict()) for doc in thumbnail_docs
            ]

        return result


class TextVectorQA(BaseComponent):
    retrieving_pipeline: BaseRetrieval
    qa_pipeline: BaseComponent

    def run(self, question, **kwargs):
        retrieved_documents = self.retrieving_pipeline(question, **kwargs)
        return self.qa_pipeline(question, retrieved_documents, **kwargs)
