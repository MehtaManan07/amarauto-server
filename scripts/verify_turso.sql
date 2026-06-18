-- Amar Automobiles — full Turso verification suite (Phase 1 + data load).
-- Run as ONE command:   turso db shell amarauto < server/scripts/verify_turso.sql
-- (pure SQL, no dot-commands, so it pipes cleanly; 'section' label avoids reserved words)

SELECT '==== 1. ROW COUNTS (expect: users 21, parties 690, stages 4, products 883, raw_materials 232, operations 164, pending 124, bom_lines 2085, product_components 0, batches 0) ====' AS section;
SELECT 'users' tbl, COUNT(*) n FROM users
UNION ALL SELECT 'parties', COUNT(*) FROM parties
UNION ALL SELECT 'stages', COUNT(*) FROM stages
UNION ALL SELECT 'products', COUNT(*) FROM products
UNION ALL SELECT 'raw_materials', COUNT(*) FROM raw_materials
UNION ALL SELECT 'operations', COUNT(*) FROM operations
UNION ALL SELECT 'pending_operations', COUNT(*) FROM pending_operations
UNION ALL SELECT 'bom_lines', COUNT(*) FROM bom_lines
UNION ALL SELECT 'product_components', COUNT(*) FROM product_components
UNION ALL SELECT 'batches', COUNT(*) FROM batches;

SELECT '==== 2. MIGRATION VERSION (expect: pending_ops_0002) ====' AS section;
SELECT version_num FROM alembic_version;

SELECT '==== 2b. ALL TABLES (expect: 15 app tables + alembic_version = 16) ====' AS section;
SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;

SELECT '==== 3. STAGES SEEDED (expect: cutting1 stitching2 finishing3 assembly4) ====' AS section;
SELECT id, name, sequence, is_active FROM stages ORDER BY sequence;

SELECT '==== 4. RESTRUCTURED SCHEMA — bom_lines + work_logs columns ====' AS section;
SELECT sql FROM sqlite_master WHERE name='bom_lines';
SELECT sql FROM sqlite_master WHERE name='work_logs';

SELECT '==== 5. OPERATIONS resolution (expect: total 164, with_stage 135, with_rate 159, with_side 0) ====' AS section;
SELECT COUNT(*) total, COUNT(stage_id) with_stage, COUNT(rate) with_rate, COUNT(side) with_side FROM operations;

SELECT '==== 6. OPERATIONS INBOX (expect: 124 pending; top = Cushport parts) ====' AS section;
SELECT status, COUNT(*) n FROM pending_operations GROUP BY status;
SELECT raw_product_col, component, COUNT(*) n FROM pending_operations
GROUP BY raw_product_col, component ORDER BY n DESC LIMIT 8;

SELECT '==== 7. BOM SUM-DONT-DEDUP (expect: TWO rows for A001/BLACK/cutting — 9.22 panel + 1.66 trim) ====' AS section;
SELECT rm.name material, b.batch_size, b.qty_per_batch,
       ROUND(b.qty_per_batch / b.batch_size, 4) per_unit
FROM bom_lines b
JOIN products p ON b.product_id = p.id
JOIN raw_materials rm ON b.raw_material_id = rm.id
JOIN stages st ON b.stage_id = st.id
WHERE p.part_no = 'A001' AND b.style = 'BLACK' AND LOWER(st.name) = 'cutting';

SELECT '==== 8. FULL RECIPE A001/BLACK across stages (expect: cutting -> stitching -> finishing) ====' AS section;
SELECT st.sequence seq, st.name stage, rm.name material, b.qty_per_batch, b.batch_size
FROM bom_lines b
JOIN products p ON b.product_id = p.id
JOIN stages st ON b.stage_id = st.id
JOIN raw_materials rm ON b.raw_material_id = rm.id
WHERE p.part_no = 'A001' AND b.colour = 'BLACK'
ORDER BY st.sequence;

SELECT '==== 9. BOM stage split + coverage (expect: cutting 644 / stitching 565 / finishing 876; 56 with BOM, 23 with ops — rest of ops still in inbox) ====' AS section;
SELECT st.name stage, COUNT(*) n FROM bom_lines b JOIN stages st ON b.stage_id = st.id GROUP BY st.name;
SELECT (SELECT COUNT(DISTINCT product_id) FROM bom_lines) products_with_bom,
       (SELECT COUNT(DISTINCT product_id) FROM operations) products_with_ops;

SELECT '==== 10. REFERENTIAL INTEGRITY (expect: 0, 0, 0 — no orphans) ====' AS section;
SELECT
 (SELECT COUNT(*) FROM bom_lines b LEFT JOIN products p ON b.product_id=p.id WHERE p.id IS NULL) AS bom_orphan_product,
 (SELECT COUNT(*) FROM bom_lines b LEFT JOIN raw_materials r ON b.raw_material_id=r.id WHERE r.id IS NULL) AS bom_orphan_rawmat,
 (SELECT COUNT(*) FROM operations o LEFT JOIN products p ON o.product_id=p.id WHERE p.id IS NULL) AS ops_orphan_product;
