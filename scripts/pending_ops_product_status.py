"""
Snapshot of pending_operations grouped by raw_product_col, with a (loose) flag for
whether a matching product exists in the DB.

NOTE: product_status is from a fuzzy LIKE match on raw free text — treat 'product EXISTS'
with suspicion (false positives). The 9 EXISTS rows are all on Appendix D's confirmed-
missing list. Authoritative missing-product list lives in the resolver / plan Appendix D.

Run against live Turso on 2026-06-19.
"""

PENDING_OPS_PRODUCT_STATUS = [
    {"raw_product_col": "s10011M", "op_count": 4, "product_status": "product EXISTS"},
    {"raw_product_col": "s10011S", "op_count": 4, "product_status": "product EXISTS"},
    {"raw_product_col": "s1008 pabla", "op_count": 4, "product_status": "product EXISTS"},
    {"raw_product_col": "S005CST-old", "op_count": 1, "product_status": "product EXISTS"},
    {"raw_product_col": "S005M-plain / emboss", "op_count": 1, "product_status": "product EXISTS"},
    {"raw_product_col": "SC001AST", "op_count": 1, "product_status": "product EXISTS"},
    {"raw_product_col": "s10010", "op_count": 1, "product_status": "product EXISTS"},
    {"raw_product_col": "s1001v", "op_count": 1, "product_status": "product EXISTS"},
    {"raw_product_col": "steering cover", "op_count": 1, "product_status": "product EXISTS"},
    {"raw_product_col": "Cushport-Half ટેકા", "op_count": 28, "product_status": "product MISSING"},
    {"raw_product_col": "Cushport-ટેકા", "op_count": 26, "product_status": "product MISSING"},
    {"raw_product_col": "Cushport-બેઠક", "op_count": 18, "product_status": "product MISSING"},
    {"raw_product_col": "Cushport-નેક પીલો", "op_count": 6, "product_status": "product MISSING"},
    {"raw_product_col": "S1005", "op_count": 5, "product_status": "product MISSING"},
    {"raw_product_col": "C003 kia", "op_count": 4, "product_status": "product MISSING"},
    {"raw_product_col": "Cushport-નેટ", "op_count": 4, "product_status": "product MISSING"},
    {"raw_product_col": "Cushport-બફ લેધર", "op_count": 4, "product_status": "product MISSING"},
    {"raw_product_col": "Cushport-હેડ રેસ્ટ", "op_count": 3, "product_status": "product MISSING"},
    {"raw_product_col": "Cushport- વેલ્ક્રો", "op_count": 2, "product_status": "product MISSING"},
    {"raw_product_col": "S005CST", "op_count": 2, "product_status": "product MISSING"},
    {"raw_product_col": "S1001", "op_count": 2, "product_status": "product MISSING"},
    {"raw_product_col": "S1002", "op_count": 2, "product_status": "product MISSING"},
]

def print_missing_products():
    print("Missing products:")
    for row in PENDING_OPS_PRODUCT_STATUS:
        if row["product_status"] == "product MISSING":
            print(f"{row['raw_product_col']} (op count: {row['op_count']})")
            
if __name__ == "__main__":
    print_missing_products()