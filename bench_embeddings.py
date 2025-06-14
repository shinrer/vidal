import sqlite3
import time
import argparse
from sentence_transformers import SentenceTransformer
import torch

from generate_embeddings import DATABASE_NAME, encode_batch


def main():
    parser = argparse.ArgumentParser(description="Benchmark embedding generation")
    parser.add_argument(
        "--model",
        default="intfloat/multilingual-e5-base",
        help="SentenceTransformer model to use",
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=128,
        help="Number of texts to encode per batch",
    )
    parser.add_argument(
        "--commit_interval",
        type=int,
        default=500,
        help="Unused but kept for CLI compatibility",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10000,
        help="Number of rows to encode for benchmarking",
    )

    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"👉  Using {device}")

    model = SentenceTransformer(args.model, device=device)
    if device == "cuda":
        model.half()
        torch.set_default_dtype(torch.float16)

    conn = sqlite3.connect(DATABASE_NAME)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(id_section) FROM RCP_Sections WHERE embedding IS NULL")
    total_pending = cur.fetchone()[0]

    cur.execute(
        "SELECT texte_section FROM RCP_Sections WHERE embedding IS NULL LIMIT ?",
        (args.limit,),
    )
    texts = [row[0] for row in cur.fetchall()]

    start = time.time()
    encode_batch(model, device, texts, args.batch_size)
    elapsed = time.time() - start

    rows_per_sec = len(texts) / elapsed if elapsed > 0 else 0
    eta_full = total_pending / rows_per_sec if rows_per_sec > 0 else float("inf")
    print(
        f"⏱️  Done in {elapsed:.1f}s ⇒ {rows_per_sec:.0f} rows/s, ETA_full {eta_full:.1f}s"
    )

    conn.close()


if __name__ == "__main__":
    main()
