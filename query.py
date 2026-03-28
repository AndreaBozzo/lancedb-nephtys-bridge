import lancedb
from datetime import datetime

def query_stream(query_text: str):
    db = lancedb.connect("./data/nephtys_lancedb")
    table = db.open_table("live_streams")
    
    print(f"Ricerca per: '{query_text}'\n")
    
    results = table.search(query_text) \
        .limit(3) \
        .to_list()
                
    for r in results:
        ts = datetime.fromtimestamp(r['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{ts}] (Score: {r['_distance']:.4f})")
        print(f"Testo: {r['text']}")
        print("-" * 40)

if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "notizie su data engineering"
    query_stream(q)