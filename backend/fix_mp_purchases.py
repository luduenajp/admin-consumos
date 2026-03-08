import sqlite3

def fix_db():
    conn = sqlite3.connect('data/app.db')
    cursor = conn.cursor()
    
    # Buscamos compras de MP que se hayan asignado mal a Abril 2026 (first_installment_month='2026-04')
    # Y que sean de las fechas problemáticas (ej 11/feb) o en general corregir las que digan 2026-04 y Card 4 (MercadoPago)
    
    # 1. Update purchase first_installment_month
    cursor.execute("""
        UPDATE purchase 
        SET first_installment_month = '2026-03'
        WHERE card_id = 4 AND first_installment_month = '2026-04' AND description LIKE '%MERPAGO%'
    """)
    purchases_updated = cursor.rowcount
    print(f"Updated {purchases_updated} purchases.")
    
    # 2. Update installment schedule
    cursor.execute("""
        UPDATE installmentschedule
        SET year_month = '2026-03'
        WHERE purchase_id IN (
            SELECT id FROM purchase WHERE card_id = 4 AND description LIKE '%MERPAGO%' 
            AND purchase_date >= '2026-01-01'
        ) AND year_month = '2026-04'
    """)
    schedules_updated = cursor.rowcount
    print(f"Updated {schedules_updated} installment schedules for month 4 -> 3.")
    
    # 3. Update installment schedule para las cuotas siguientes
    # Si habian 3 cuotas: 2026-04, 2026-05, 2026-06 -> ahora deben ser 2026-03, 2026-04, 2026-05
    cursor.execute("""
        UPDATE installmentschedule
        SET year_month = '2026-04'
        WHERE purchase_id IN (
            SELECT id FROM purchase WHERE card_id = 4 AND description LIKE '%MERPAGO%' 
            AND purchase_date >= '2026-01-01'
        ) AND year_month = '2026-05'
    """)
    print(f"Updated {cursor.rowcount} installment schedules for month 5 -> 4.")

    cursor.execute("""
        UPDATE installmentschedule
        SET year_month = '2026-05'
        WHERE purchase_id IN (
            SELECT id FROM purchase WHERE card_id = 4 AND description LIKE '%MERPAGO%' 
            AND purchase_date >= '2026-01-01'
        ) AND year_month = '2026-06'
    """)
    print(f"Updated {cursor.rowcount} installment schedules for month 6 -> 5.")


    conn.commit()
    conn.close()

if __name__ == '__main__':
    fix_db()
