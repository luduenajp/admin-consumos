import sqlite3

def clean_mp_imports():
    conn = sqlite3.connect('../data/app.db')
    cursor = conn.cursor()
    
    # Get purchase info from the imported rows of resumen-mp-marzo.pdf
    cursor.execute("SELECT parsed_payload_json, row_fingerprint FROM importedrow WHERE source_file = 'resumen-mp-marzo.pdf'")
    rows = cursor.fetchall()
    
    import json
    for row in rows:
        payload = json.loads(row[0])
        desc = payload['description']
        date_val = payload['purchase_date']
        installments = payload['installments_total']
        
        # 1. find the purchase
        # normalize description
        import re
        cleaned = re.sub(r"\b(?:C\.)\s*\d+\s*/\s*\d+\b|\b\d+\s*de\s*\d+\b", " ", desc, flags=re.IGNORECASE)
        cleaned = re.sub(r"^\s*\d{3,}\s+", "", cleaned)
        cleaned = re.sub(r"\s+\d{3,}\s*$", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        cursor.execute("SELECT id FROM purchase WHERE card_id=4 AND purchase_date=? AND installments_total=?", (date_val, installments))
        candidates = cursor.fetchall()
        
        purchase_id = None
        for (pid,) in candidates:
            cursor.execute("SELECT description FROM purchase WHERE id=?", (pid,))
            pdesc = cursor.fetchone()[0]
            if pdesc.lower() == cleaned.lower() or cleaned.lower() in pdesc.lower():
                purchase_id = pid
                break
                
        if purchase_id:
            print(f"Deleting purchase {purchase_id} ({desc})")
            cursor.execute("DELETE FROM installmentschedule WHERE purchase_id=?", (purchase_id,))
            cursor.execute("DELETE FROM purchasepayer WHERE purchase_id=?", (purchase_id,))
            cursor.execute("DELETE FROM purchase WHERE id=?", (purchase_id,))
            
    # Delete the imported rows
    cursor.execute("DELETE FROM importedrow WHERE source_file = 'resumen-mp-marzo.pdf'")
    print(f"Deleted {cursor.rowcount} imported rows.")
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    clean_mp_imports()
