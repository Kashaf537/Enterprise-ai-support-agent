# RAG Module Notes

## First-time setup

The first time you run the indexer, `sentence-transformers` needs to download
the `all-MiniLM-L6-v2` model (~80MB) from Hugging Face. This requires an
internet connection and happens automatically:

```bash
python -m backend.rag.build_index --rebuild
```

After the first run, the model is cached locally (typically in
`~/.cache/huggingface/`), so subsequent runs work fully offline.

## If you're behind a firewall / proxy

Set the standard Hugging Face environment variables before running:

```bash
export HF_HUB_OFFLINE=0          # ensure online mode for the first download
export HF_HOME=./hf_cache        # optional: control where the cache lives
```

## Rebuilding after editing knowledge_base/*.md

Any time you add, remove, or edit a markdown file in `knowledge_base/`, rerun:

```bash
python -m backend.rag.build_index --rebuild
```

Without `--rebuild`, the script skips indexing if the collection already has
data (see `VectorStore.build_from_knowledge_base`), since rebuilding on every
app startup would be wasteful for large knowledge bases.

## Verifying it worked

```bash
python -c "from backend.rag.retriever import retrieve; print(retrieve('how do refunds work?'))"
```

You should see a list of `RetrievedDocument` objects, the top one most likely
sourced from `refund_policy.md`.
